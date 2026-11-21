"""Download what setup_node.sh would otherwise fetch from the internet, for a node without internet access.

    python cluster/make_offline_kit.py          -> cluster/offline/   (then: python cluster/make_cluster_bundle.py)

    cluster/offline/<portable Python 3.11 tarball>   python-build-standalone, checksum checked (about 30 MB)
    cluster/offline/wheels/                          Linux x86_64 / CPython 3.11 wheels: CPU PyTorch + requirements-node.txt

make_cluster_bundle.py packs cluster/offline/ as whistle_app/offline/ when it exists; setup_node.sh then installs from it.
The wheels are for Linux on x86_64 with glibc >= 2.28 (Ubuntu 20.04 and newer), not for this Windows laptop.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "cluster" / "offline"
SETUP = ROOT / "cluster" / "node" / "setup_node.sh"
PLATFORMS = ["manylinux_2_28_x86_64", "manylinux_2_27_x86_64", "manylinux_2_17_x86_64", "manylinux2014_x86_64",
             "manylinux_2_5_x86_64", "manylinux1_x86_64", "linux_x86_64"]


def pip_download(*args: str) -> None:
    cmd = [sys.executable, "-m", "pip", "download", "--disable-pip-version-check", "--only-binary=:all:",
           "--python-version", "3.11", "--implementation", "cp", "--abi", "cp311", "--abi", "abi3", "--abi", "none",
           *[a for p in PLATFORMS for a in ("--platform", p)], "--platform", "any", "-d", str(OUT / "wheels"), *args]
    subprocess.run(cmd, check=True)


def main() -> None:
    text = SETUP.read_text(encoding="utf-8")                      # one source of truth for the Python version and checksum
    tar = re.search(r'^PY_TAR="([^"]+)"', text, re.M).group(1)
    sha = re.search(r'^PY_SHA="([^"]+)"', text, re.M).group(1)
    url = re.search(r'^PY_URL="([^"]+)"', text, re.M).group(1).replace("$PY_TAR", tar)
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / tar
    if not dst.exists():
        print(f"downloading {url}")
        urllib.request.urlretrieve(url.replace("+", "%2B"), dst)
    if hashlib.sha256(dst.read_bytes()).hexdigest() != sha:
        dst.unlink()
        raise SystemExit(f"{tar}: checksum mismatch, deleted")
    print(f"{dst.name}: checksum ok")

    torch = re.search(r'^TORCH="([^"]+)"', text, re.M).group(1)
    pip_download(f"torch=={torch}", "--index-url", "https://download.pytorch.org/whl/cpu", "--extra-index-url", "https://pypi.org/simple")
    pip_download("-r", str(ROOT / "cluster" / "node" / "requirements-node.txt"))
    wheels = sorted((OUT / "wheels").glob("*.whl"))
    size = sum(p.stat().st_size for p in [dst, *wheels]) / 1e6
    print(f"{OUT}: Python + {len(wheels)} wheels, {size:.0f} MB.  Next: python cluster/make_cluster_bundle.py")


if __name__ == "__main__":
    main()
