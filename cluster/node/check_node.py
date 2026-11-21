"""Does this machine have what the whistle app needs?  Runs on any Python 3 (also the 3.8 of Ubuntu 20.04).

    python3 check_node.py                      check the Python that runs it: version, packages, machine, internet
    python3 check_node.py --run                and, if nothing is missing, run the real app once (model, analysis,
                                               generation, web server + page), without a browser
    /path/to/other/python check_node.py        check another Python, e.g. the mentor's Anaconda

Nothing is installed or changed. The test run writes only into runs/ inside this folder.
"""
import os
import platform
import shutil
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_PY = (3, 11)
# import name, pip name, conda name, minimum, version the app was built and tested with, what it is for
PACKAGES = [
    ("torch", "torch", "pytorch (+ cpuonly)", "2.11", "2.14.0", "runs the detector and the VAE"),
    ("numpy", "numpy", "numpy", "2.1", "2.4.4", "arrays"),
    ("scipy", "scipy", "scipy", "1.16", "1.17.1", "signal processing"),
    ("soundfile", "soundfile", "pysoundfile (conda-forge)", "0.13", "0.13.1", "reads WAV/FLAC/OGG/MP3"),
    ("matplotlib", "matplotlib", "matplotlib", "3.8", "3.10.8", "draws the result images"),
    ("PIL", "pillow", "pillow", "10.0", "12.3.0", "saves images"),
    ("fastapi", "fastapi", "fastapi", "0.110", "0.141.1", "the API (backend)"),
    ("uvicorn", "uvicorn", "uvicorn", "0.29", "0.54.0", "the web server"),
    ("python_multipart|multipart", "python-multipart", "python-multipart", "0.0.9", "0.0.32", "file uploads"),
    ("pydantic", "pydantic", "pydantic", "2.0", "2.13.3", "API request checking"),
]


def vtuple(v):
    out = []
    for part in str(v).replace("+", ".").split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        if not digits:
            break
        out.append(int(digits))
    return tuple(out)


def dist_version(pip_name, module):
    try:
        from importlib.metadata import version            # Python >= 3.8
        return version(pip_name)
    except Exception:
        return getattr(module, "__version__", "?")


def line(ok, label, detail):
    print("  %-4s %-22s %s" % ({True: "OK", False: "NO", None: "--"}[ok], label, detail))


def check_python():
    v = sys.version_info
    ok = v[:2] >= MIN_PY
    line(ok, "Python", "%d.%d.%d at %s (needs %d.%d or newer)" % (v[0], v[1], v[2], sys.executable, MIN_PY[0], MIN_PY[1]))
    return ok


def check_packages():
    missing = []
    for imports, pip_name, conda, minimum, tested, why in PACKAGES:
        mod, err = None, None
        for name in imports.split("|"):
            try:
                mod = __import__(name)
                break
            except Exception as e:                        # noqa: BLE001
                err = e
        if mod is None:
            line(False, pip_name, "missing (%s)  -> %s" % (why, type(err).__name__))
            missing.append((pip_name, conda, minimum, tested))
            continue
        ver = dist_version(pip_name, mod)
        ok = vtuple(ver) >= vtuple(minimum)
        note = "" if ok else "  TOO OLD, needs >= %s" % minimum
        if pip_name == "torch":
            try:
                note += "  (GPU usable: %s)" % mod.cuda.is_available()
            except Exception:                             # noqa: BLE001
                pass
        if pip_name == "soundfile":
            try:
                mod.info(os.path.join(HERE, "web", "data", "examples", "encounter-191.flac"))
                note += "  (reads FLAC: yes)"
            except Exception as e:                        # noqa: BLE001
                ok, note = False, note + "  (cannot read FLAC: %s)" % e
        line(ok, pip_name, "%s%s" % (ver, note))
        if not ok:
            missing.append((pip_name, conda, minimum, tested))
    return missing


def check_machine():
    line(None, "System", "%s, %s" % (platform.platform(), " ".join(platform.libc_ver())))
    line(None, "CPU cores", str(os.cpu_count()))
    try:
        with open("/proc/meminfo") as f:
            mem = {k: int(v.split()[0]) for k, v in (ln.split(":", 1) for ln in f)}
        line(mem.get("MemAvailable", 0) > 2 * 1024 * 1024, "Free memory",
             "%.1f GB available of %.1f GB (needs about 2 GB)" % (mem.get("MemAvailable", 0) / 1048576, mem["MemTotal"] / 1048576))
    except Exception:                                     # noqa: BLE001
        line(None, "Free memory", "unknown")
    free = shutil.disk_usage(HERE).free / 1e9
    line(free > 2, "Free disk here", "%.1f GB (setup needs about 1.5 GB)" % free)
    gpu = shutil.which("nvidia-smi")
    line(None, "NVIDIA GPU", "nvidia-smi found" if gpu else "none (the app runs on CPU)")
    line(None, "hdfs command", shutil.which("hdfs") or "not found")
    conda = shutil.which("conda")
    line(None, "conda command", conda or "not found on PATH")


def check_internet():
    for host in ("pypi.org", "download.pytorch.org", "github.com"):
        try:
            socket.create_connection((host, 443), timeout=8).close()
            line(True, "internet " + host, "reachable")
        except Exception as e:                            # noqa: BLE001
            line(False, "internet " + host, "not reachable (%s)" % type(e).__name__)


def run(cmd, timeout=900):
    t = time.time()
    p = subprocess.run(cmd, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, timeout=timeout)
    tail = [ln for ln in p.stdout.strip().splitlines() if ln.strip()][-3:]
    line(p.returncode == 0, cmd[2], "%.0f s  %s" % (time.time() - t, " | ".join(tail)[:300]))
    return p.returncode == 0


def test_run():
    py, ok = sys.executable, True
    ok &= run([py, "whistle.py", "model-status", "--device", "cpu"])
    ok &= run([py, "whistle.py", "infer", "web/data/examples/encounter-191.flac", "--device", "cpu"])
    ok &= run([py, "whistle.py", "generate", "--n", "4", "--device", "cpu"])
    port = 8765
    srv = subprocess.Popen([py, "whistle.py", "serve", "--port", str(port), "--device", "cpu"], cwd=HERE,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        import json
        import urllib.request
        page = status = None
        for _ in range(120):
            try:
                page = urllib.request.urlopen("http://127.0.0.1:%d/" % port, timeout=5).read()
                status = json.loads(urllib.request.urlopen("http://127.0.0.1:%d/api/status" % port, timeout=5).read())
                break
            except Exception:                             # noqa: BLE001
                if srv.poll() is not None:
                    break
                time.sleep(1)
        good = bool(page) and status is not None and all(status["model"]["ready"].values())
        line(good, "web server", ("page %d bytes, API: %s" % (len(page), status["model"]["message"])) if status else
             "did not start: " + (srv.stdout.read().decode(errors="replace")[-300:] if srv.poll() is not None else "no answer"))
        ok &= good
    finally:
        srv.terminate()
        srv.wait(timeout=30)
    return ok


def main():
    print("== Python")
    py_ok = check_python()
    print("== Packages (10 the app imports; pip/conda add about 20 small dependencies by themselves)")
    missing = check_packages()
    print("== Machine")
    check_machine()
    print("== Internet")
    check_internet()
    print("== Result")
    if py_ok and not missing:
        print("  This Python has everything the app needs.")
        if "--run" in sys.argv:
            print("== Test run of the real app on CPU (takes about a minute)")
            print("  THE APP RUNS HERE." if test_run() else "  The test run failed; see the NO lines above.")
        else:
            print("  Next: %s check_node.py --run   (test run of the real app)" % os.path.basename(sys.executable))
        return 0
    if not py_ok:
        print("  This Python is too old: the app needs Python %d.%d or newer." % MIN_PY)
    if missing:
        print("  Missing or too old: " + ", ".join(m[0] for m in missing))
    print("  Request for the mentor (one Python %d.%d environment with these packages):" % MIN_PY)
    print("    python>=3.11  " + "  ".join("%s>=%s" % (m[0] if m[0] != "torch" else "torch(CPU)", m[2])
                                          for m in (missing if py_ok else [(p[1], p[2], p[3], p[4]) for p in PACKAGES])))
    print("  Or, if this node has internet:  bash setup_node.sh   (gets Python 3.11 and the packages by itself)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
