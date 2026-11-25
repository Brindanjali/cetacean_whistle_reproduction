# Colab cell: check that the committed DCLDE 2011 benchmark scores reproduce exactly (step 1 of the preprint plan).
# Paste this whole file into ONE Colab cell and run it. A CPU runtime is enough (~15-30 min, mostly the scorer's SNR pass).
# It only READS Google Drive: nothing is detected, trained or written there. All new files go to /content/verify_scores/.
# Needs in Google Drive, under MyDrive/whistle_detector_5_24/:
#   code/whistle_code_5_24.zip   <- python mod_detector_5_24/make_colab_bundle_5_24.py (from a clean, committed repository)
#   dclde2011/                   <- colab_download_dclde2011.py (12 recordings and their answer keys)
#   dclde2011_detections/        <- the .det files whose scores are committed in results/dclde2011_detections/
# What it does:
#   1. lists the Drive folder;  2. unpacks the code bundle and prints its version;  3. checks recordings and answer keys
#   (size and MD5);  4. copies the .det files to the Colab disk and checks they are byte-identical to the committed ones;
#   5. scorer self-test;  6. re-scores every committed score file with the flags its name encodes;
#   7. compares each new score file with the committed one, field by field.
# If anything differs it says STOP: change nothing, send the whole output.
import ast
import contextlib
import hashlib
import importlib
import io
import json
import math
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path

CHECK_MD5 = True   # also check the MD5 of every recording and answer key (adds a few minutes); sizes are always checked
LOCAL_TEST = os.environ.get("VERIFY_LOCAL_TEST") == "1"   # only for testing on a PC with a fake Drive; leave unset on Colab
CONTENT = os.environ.get("VERIFY_CONTENT", "/content")
DRIVE = f"{CONTENT}/drive/MyDrive/whistle_detector_5_24"
CODE = f"{CONTENT}/whistle_code"
SCRATCH = Path(f"{CONTENT}/verify_scores")         # --data points here; scores are written to <SCRATCH>/dclde2011_detections/
DATA = SCRATCH / "dclde2011"
RES = "results/dclde2011_detections/"
KEY = {("ridgenet-5-24_keep-harmonics", "score_gt2011_min150ms_ov0.json"): 67.1,   # main result: ours
       ("silbido-graph", "score_gt2011_min150ms_ov0.json"): 74.6}                  # main result: Silbido
SELFTEST = (12, "100.00", "99.93", 1516, 1)   # identity case: files, recall, precision, expected GT, false positives


def fail(msg):
    if LOCAL_TEST:
        print(f"  [local test, not fatal] {msg}")
    else:
        raise SystemExit(f"STOP: {msg}\nChange nothing; copy the whole output and send it.")


def digest(path, algo):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


from google.colab import drive
drive.mount(f"{CONTENT}/drive")

print("===== 1. what is in Google Drive =====")
if not os.path.isdir(DRIVE):
    raise SystemExit(f"STOP: {DRIVE} not found")
for p in sorted(Path(DRIVE).iterdir()):
    print(f"  {p.name}/" if p.is_dir() else f"  {p.name}  ({p.stat().st_size / 1e6:.1f} MB)")
for sub in ("dclde2011", "dclde2011_detections"):
    root = Path(DRIVE, sub)
    n = sum(1 for p in root.rglob("*") if p.is_file()) if root.is_dir() else 0
    print(f"  {sub}/: {n} files")
    if sub == "dclde2011_detections" and root.is_dir():
        for t in sorted(q for q in root.iterdir() if q.is_dir()):
            print(f"    {t.name}/: {len(list(t.rglob('*.det')))} .det, {len(list(t.glob('score_*.json')))} score files")

print("\n===== 2. code bundle =====")
ZIP = f"{DRIVE}/code/whistle_code_5_24.zip"
if not os.path.exists(ZIP):
    raise SystemExit(f"STOP: {ZIP} not found: upload the bundle built from this repository")
shutil.rmtree(CODE, ignore_errors=True)
with zipfile.ZipFile(ZIP) as z:
    z.extractall(CONTENT)
version = json.load(open(f"{CODE}/CODE_VERSION.json"))
print(json.dumps({k: v for k, v in version.items() if k not in ("files_sha256", "committed_dets_sha256")}, indent=2))
if "committed_dets_sha256" not in version:
    raise SystemExit("STOP: this is the OLD code bundle: delete it from Drive and upload the one built from this repository")
if version["git_uncommitted_code_changes"]:
    fail("the bundle was built with uncommitted changes; commit first, then rebuild it")
bad = [f for f, h in version["files_sha256"].items() if digest(f"{CODE}/{f}", "sha256") != h]
if bad:
    fail(f"files in the bundle do not match CODE_VERSION.json: {bad}")
else:
    print(f"  {len(version['files_sha256'])} packed files match CODE_VERSION.json")

print("\n===== 3. recordings and answer keys in Drive =====")
src = open(f"{CODE}/mod_detector_5_24/colab_download_dclde2011.py").read()
listing = next(n.value.value for n in ast.parse(src).body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "FILES")
want = [(p, int(s), m) for p, s, m in (l.split(",") for l in listing.strip().splitlines()) if p.endswith((".wav", ".ann"))]
problems = []
for p, size, md5 in want:
    f = Path(DRIVE, "dclde2011", p)
    if not f.exists():
        status = "MISSING"
    elif f.stat().st_size != size:
        status = f"WRONG SIZE ({f.stat().st_size}, expected {size})"
    elif CHECK_MD5 and digest(f, "md5") != md5:
        status = "WRONG MD5"
    else:
        status = "ok"
    if status != "ok":
        problems.append(p)
    print(f"  {status:8s} {p}" if status == "ok" else f"  {status}  {p}", flush=True)
n_wav = sum(p.endswith(".wav") and p not in problems for p, _, _ in want)
n_ann11 = sum(p.startswith("development/") and p.endswith(".ann") and p not in problems for p, _, _ in want)
n_ann25 = sum(p.startswith("annotations2025/") and p not in problems for p, _, _ in want)
print(f"  {n_wav} of 12 recordings, {n_ann11} of 12 answer keys (2011), {n_ann25} of 12 answer keys (2025) "
      f"present and correct (sizes{' and MD5' if CHECK_MD5 else ''})")
if problems:
    fail(f"{len(problems)} recording/answer-key files missing or different: {problems}")

print("\n===== 4. detections: copy to the Colab disk, check they are the committed bytes =====")
shutil.rmtree(SCRATCH, ignore_errors=True)
DATA.mkdir(parents=True)
for sub in ("development", "annotations2025"):   # --data links to the Drive recordings; the scorer never writes there
    try:
        os.symlink(f"{DRIVE}/dclde2011/{sub}", DATA / sub, target_is_directory=True)
    except OSError:
        if not LOCAL_TEST:
            raise
        shutil.copytree(f"{DRIVE}/dclde2011/{sub}", DATA / sub)   # Windows without symlink rights
det_problems = []
for f, h in sorted(version["committed_dets_sha256"].items()):
    rel = f[len(RES):]
    src_f, dst = Path(DRIVE, "dclde2011_detections", rel), SCRATCH / "dclde2011_detections" / rel
    if not src_f.exists():
        det_problems.append(f"missing in Drive: {rel}")
        continue
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_f, dst)
    if digest(dst, "sha256") != h:
        det_problems.append(f"different from the committed file: {rel}")
print(f"  {len(version['committed_dets_sha256']) - len(det_problems)} of {len(version['committed_dets_sha256'])} .det files "
      f"copied and byte-identical to results/dclde2011_detections/")
if det_problems:
    raise SystemExit("STOP: .det files in Drive are not the committed ones:\n  " + "\n  ".join(det_problems))

sys.path.insert(0, f"{CODE}/mod_detector_5_24")
import dclde2011 as D
importlib.reload(D)
print(f"  scorer: {D.__file__}")

print("\n===== 5. scorer self-test (answer key scored against itself) =====")
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    D.main(["--data", str(DATA), "selftest"])
print(buf.getvalue(), end="")
m = re.search(r"^identity\s+files (\d+)\s+recall\s+([\d.]+)\s+precision\s+([\d.]+)\s+\(GT expected (\d+), false pos (\d+)\)",
              buf.getvalue(), re.M)
got = (int(m[1]), m[2], m[3], int(m[4]), int(m[5])) if m else None
print(f"  identity: {got}; expected {SELFTEST} -> {'MATCH' if got == SELFTEST else 'MISMATCH'}")
if got != SELFTEST:
    fail("self-test numbers differ from the expected ones")

print("\n===== 6. re-score every committed score file =====")
NAME = re.compile(r"^score_gt(2011|2025)(?:_min(\d+(?:\.\d+)?)ms)?(_fullband)?(?:_ov(\d+(?:\.\d+)?))?\.json$")
jobs = []
for f in sorted(version["files_sha256"]):
    tag, _, name = f[len(RES):].partition("/") if f.startswith(RES) else ("", "", "")
    if not name.startswith("score_"):
        continue
    m = NAME.match(name)
    old = json.load(open(f"{CODE}/{f}"))
    if not m:
        fail(f"cannot read the settings from the file name {f}")
        continue
    gt, ms, full, ov = m[1], float(m[2] or 0), bool(m[3]), float(m[4]) if m[4] else 0.3
    flags = ["--gt", gt] + (["--min-det-ms", m[2]] if m[2] else []) + (["--full-band"] if full else []) + \
            (["--min-overlap", m[4]] if m[4] else [])
    # the settings stored inside the committed file must agree with its name
    inside = (old["gt"], old["min_overlap"], old["min_detection_s"], old["band_hz"] is None)
    if inside != (gt, ov, ms / 1000, full):
        fail(f"{f}: settings inside the file {inside} do not match its name")
    if old["n_files"] != 12:
        print(f"  skipped (not a 12-recording score): {f}")
        continue
    jobs.append((tag, name, flags, old))
print(f"  {len(jobs)} score files to reproduce")
for tag, name, flags, _ in jobs:
    print(f"\n--- {tag}/{name}:  score --tag {tag} {' '.join(flags)}", flush=True)
    D.main(["--data", str(DATA), "score", "--tag", tag] + flags)


def diff(a, b, path=""):
    """Differences between committed (a) and new (b), as (path, committed, new)."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in list(a) + [k for k in b if k not in a]:
            if k not in a or k not in b:
                out.append((f"{path}/{k}", a.get(k, "<absent>"), b.get(k, "<absent>")))
            else:
                out += diff(a[k], b[k], f"{path}/{k}")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [(f"{path} (length)", len(a), len(b))]
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in diff(x, y, f"{path}[{i}]")]
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return []
    return [] if a == b and type(a) == type(b) else [(path, a, b)]


print("\n===== 7. committed vs new, field by field =====")
rows, all_ok = [], True
for tag, name, _, old in jobs:
    new = json.load(open(SCRATCH / "dclde2011_detections" / tag / name))
    partial = LOCAL_TEST and new["n_files"] < 12   # local test: only the recordings present can be compared
    if partial:
        a = {k: old[k] for k in ("gt", "band_hz", "min_overlap", "min_detection_s")} | {"files": {s: old["files"][s] for s in new["files"]}}
        b = {k: new[k] for k in ("gt", "band_hz", "min_overlap", "min_detection_s")} | {"files": new["files"]}
    else:
        a, b = old, new
    d = diff(a, b)
    all_ok &= not d
    o, n = old["species_average"], new["species_average"]
    res = ("MATCH" if not d else f"MISMATCH ({len(d)} fields)") + (f" [local test: {new['n_files']} file(s) only]" if partial else "")
    rows.append((f"{tag}/{name}", res, f"{o['precision']:.1f} / {o['recall']:.1f} / {o['f1']:.1f}",
                 "-" if partial else f"{n['precision']:.1f} / {n['recall']:.1f} / {n['f1']:.1f}", d))
w = max(len(r[0]) for r in rows)
print(f"  {'score file':{w}s}  {'committed P / R / F1':22s}  {'new P / R / F1':22s}  result")
for f, res, oc, nc, d in rows:  # noqa: B007
    print(f"  {f:{w}s}  {oc:22s}  {nc:22s}  {res}")
for f, res, oc, nc, d in rows:  # noqa: B007
    if d:
        print(f"\n  differences in {f} (first 15 of {len(d)}):")
        for path, x, y in d[:15]:
            rel = f"  (relative difference {abs(x - y) / max(abs(x), 1e-300):.1e})" if isinstance(x, float) and isinstance(y, float) else ""
            print(f"    {path}: committed {x!r}, new {y!r}{rel}")

print("\n  key numbers (species-average F1, scored without the 30 % rule, detections >= 150 ms):")
for (tag, name), f1 in KEY.items():
    hit = [(o, json.load(open(SCRATCH / "dclde2011_detections" / tag / name))) for t, nm, _, o in jobs if (t, nm) == (tag, name)]
    if not hit:
        print(f"    {tag}: not scored")
        all_ok = False
        continue
    o, n = hit[0]
    new_f1 = "-" if LOCAL_TEST and n["n_files"] < 12 else f"{n['species_average']['f1']:.1f}"
    print(f"    {tag:30s} expected {f1}  committed {o['species_average']['f1']:.1f}  new {new_f1}")
    if round(o["species_average"]["f1"], 1) != f1:
        all_ok = False

if all_ok:
    print(f"\nRESULT: all {len(jobs)} committed score files reproduce exactly"
          + (" (LOCAL TEST: only the recordings present were compared)" if LOCAL_TEST else "") + ".")
else:
    print("\nRESULT: STOP. Something does not match. Change nothing; copy the whole output and send it.")
print("Drive was only read; the new score files are in", SCRATCH / "dclde2011_detections")
