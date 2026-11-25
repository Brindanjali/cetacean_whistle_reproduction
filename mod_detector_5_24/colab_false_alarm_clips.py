# Colab cell: pictures of false alarms for the false-alarm analysis (step 3 of the preprint plan).
# Paste this whole file into ONE Colab cell and run it. A CPU runtime is enough (~15-25 min, mostly the scorer's SNR pass).
# Needs in Google Drive, under MyDrive/whistle_detector_5_24/:
#   code/whistle_code_5_24.zip   <- python mod_detector_5_24/make_colab_bundle_5_24.py (from a clean, committed repository)
#   dclde2011/                   <- the 12 recordings and answer keys
#   dclde2011_detections/        <- the committed .det files (ridgenet-5-24_keep-harmonics/, silbido-graph/)
# What it does:
#   1. unpacks the bundle; copies the .det files to the Colab disk and checks they are the committed bytes;
#   2. re-scores both methods with the MAIN setting (5-24 kHz, detections >= 150 ms, no 30 % rule), listing every
#      detection's verdict, and checks the scores equal the committed ones (nothing about scoring changes);
#   3. picks up to PER_GROUP false alarms per method per recording (fixed random seed), for the 4 weakest recordings;
#   4. draws one picture per false alarm; the pictures are shuffled and named FA001, FA002, ... so the sorting is blind;
#   5. writes ONE NEW Drive folder, MyDrive/whistle_detector_5_24/false_alarms_v1/ (it stops if that folder exists, so
#      a sheet you already filled is never overwritten). Nothing else in Drive is changed.
import csv
import hashlib
import importlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

PER_GROUP = 20   # false alarms per (method, recording); fewer if a recording has fewer
SEED = 2026
RECORDINGS = ["palmyra092007FS192-070925-023000", "Qx-Tt-SCI0608-N1-060814-121518",   # the weakest recordings for
              "Qx-Dc-CC0411-TAT11-CH2-041114-154040-s", "palmyra092007FS192-071004-032342"]  # ours and for Silbido
METHODS = {"ours": "ridgenet-5-24_keep-harmonics", "silbido": "silbido-graph"}
SETTING = ["--min-det-ms", "150", "--min-overlap", "0"]   # main scoring
SCORE = "score_gt2011_min150ms_ov0"
LOCAL_TEST = os.environ.get("VERIFY_LOCAL_TEST") == "1"   # only for testing on a PC with a fake Drive; leave unset on Colab
CONTENT = os.environ.get("VERIFY_CONTENT", "/content")
DRIVE = f"{CONTENT}/drive/MyDrive/whistle_detector_5_24"
CODE = f"{CONTENT}/whistle_code"
SCRATCH = Path(f"{CONTENT}/false_alarm_work")
DATA = SCRATCH / "dclde2011"
OUT_NAME = "false_alarms_v1"
OUT = SCRATCH / OUT_NAME
RES = "results/dclde2011_detections/"
if LOCAL_TEST:
    RECORDINGS = ["palmyra102006-061020-204327_4"]   # the one recording available on the PC


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


from google.colab import drive
drive.mount(f"{CONTENT}/drive")
if os.path.exists(f"{DRIVE}/{OUT_NAME}"):
    raise SystemExit(f"STOP: {DRIVE}/{OUT_NAME} already exists. Nothing was changed. If you really want new pictures, "
                     f"rename that folder in Drive first (your filled sheet is in it).")

print("===== 1. code bundle and detections =====")
shutil.rmtree(CODE, ignore_errors=True)
with zipfile.ZipFile(f"{DRIVE}/code/whistle_code_5_24.zip") as z:
    z.extractall(CONTENT)
version = json.load(open(f"{CODE}/CODE_VERSION.json"))
print({k: v for k, v in version.items() if k not in ("files_sha256", "committed_dets_sha256")})
if "--list-detections" not in open(f"{CODE}/mod_detector_5_24/dclde2011.py").read():
    raise SystemExit("STOP: old code bundle (no --list-detections): rebuild it from the repository and upload it")
if version["git_uncommitted_code_changes"] and not LOCAL_TEST:
    raise SystemExit("STOP: the bundle was built with uncommitted changes; commit first, then rebuild it")
shutil.rmtree(SCRATCH, ignore_errors=True)
DATA.mkdir(parents=True)
for sub in ("development", "annotations2025"):   # --data links to the Drive recordings; the scorer never writes there
    try:
        os.symlink(f"{DRIVE}/dclde2011/{sub}", DATA / sub, target_is_directory=True)
    except OSError:
        if not LOCAL_TEST:
            raise
        shutil.copytree(f"{DRIVE}/dclde2011/{sub}", DATA / sub)   # Windows without symlink rights
bad = []
for f, h in version["committed_dets_sha256"].items():
    rel = f[len(RES):]
    if rel.split("/")[0] not in METHODS.values():
        continue
    src, dst = Path(DRIVE, "dclde2011_detections", rel), SCRATCH / "dclde2011_detections" / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        bad.append(f"missing: {rel}")
        continue
    shutil.copyfile(src, dst)
    if sha256(dst) != h:
        bad.append(f"different from the committed file: {rel}")
if bad:
    raise SystemExit("STOP: .det files in Drive are not the committed ones:\n  " + "\n  ".join(bad))
print("  .det files copied and byte-identical to the committed ones")

sys.path.insert(0, f"{CODE}/mod_detector_5_24")
import dclde2011 as D
importlib.reload(D)

print("\n===== 2. score both methods (main setting), listing every detection =====")
listing = {}
for m, tag in METHODS.items():
    D.main(["--data", str(DATA), "score", "--tag", tag, "--list-detections"] + SETTING)
    new = json.load(open(SCRATCH / "dclde2011_detections" / tag / f"{SCORE}.json"))
    old = json.load(open(f"{CODE}/{RES}{tag}/{SCORE}.json"))
    if LOCAL_TEST:
        old = {**old, "files": {s: old["files"][s] for s in new["files"]}}
        new, old = new["files"], old["files"]
    if json.dumps(new, sort_keys=True) != json.dumps(old, sort_keys=True):
        raise SystemExit(f"STOP: {tag} scores differ from the committed {SCORE}.json. Change nothing; send the output.")
    print(f"  {m}: scores identical to the committed {SCORE}.json")
    with open(SCRATCH / "dclde2011_detections" / tag / f"{SCORE}_detections.csv") as fh:
        listing[m] = list(csv.DictReader(fh))

print("\n===== 3. sample false alarms =====")
import numpy as np
rng = np.random.default_rng(SEED)
picks = []
for stem in RECORDINGS:
    for m in METHODS:
        fa = [r for r in listing[m] if r["recording"] == stem and r["status"] == "false_alarm"]
        chosen = sorted(rng.choice(len(fa), size=min(PER_GROUP, len(fa)), replace=False)) if fa else []
        picks += [{"method": m, **fa[i]} for i in chosen]
        print(f"  {stem[:38]:38s} {m:8s} {len(fa):4d} false alarms, {len(chosen)} picked")
order = rng.permutation(len(picks))
for n, i in enumerate(order, 1):
    picks[i]["id"] = f"FA{n:03d}"
picks.sort(key=lambda p: p["id"])

print(f"\n===== 4. draw {len(picks)} pictures =====")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy import signal

(OUT / "pictures").mkdir(parents=True)
band = D.band_hz(D.load_cfg([]))
for stem in RECORDINGS:
    mine = [p for p in picks if p["recording"] == stem]
    if not mine:
        continue
    sp = mine[0]["species"]
    wav, ann = DATA / "development" / sp / f"{stem}.wav", D.gt_path(DATA, sp, stem, "2011")
    gts, snr, skipped = D.load_gt(wav, ann)
    expected, _ = D.expected_mask(gts, snr, skipped, band, False)
    x, fs = D.read_wav(wav)
    tracks = {m: D.read_tonals(SCRATCH / "dclde2011_detections" / tag / sp / f"{stem}.det") for m, tag in METHODS.items()}
    for p in mine:
        t, f = tracks[p["method"]][int(p["det_index"])]
        pad = max(0.5, (1.5 - (t[-1] - t[0])) / 2)                    # at least 1.5 s shown, 0.5 s either side
        a, b = max(0.0, t[0] - pad), min(len(x) / fs, t[-1] + pad)
        fr, tt, S = signal.spectrogram(x[int(a * fs):int(b * fs)], fs, window="hann", nperseg=2048, noverlap=1536,
                                       mode="magnitude")
        k = (fr >= 2000) & (fr <= 40000)
        db = 20 * np.log10(S[k] + 1e-12)
        db -= np.median(db, axis=1, keepdims=True)                     # flatten the background per frequency
        ext = [a + tt[0], a + tt[-1], fr[k][0] / 1e3, fr[k][-1] / 1e3]
        fig, axs = plt.subplots(2, 1, figsize=(11, 8), sharex=True, constrained_layout=True)
        for ax in axs:
            ax.imshow(db, origin="lower", aspect="auto", extent=ext, cmap="gray_r", vmin=0, vmax=25)
            ax.set_ylabel("pitch (kHz)")
        axs[0].set_title(f"{p['id']}   top: plain   |   bottom: same, with lines (red = the detection to judge)")
        ax = axs[1]
        for hz in band:
            ax.axhline(hz / 1e3, color="grey", ls=":", lw=0.8)
        for tr, fq in tracks[p["method"]]:                             # the same method's other detections nearby
            if tr[-1] >= a and tr[0] <= b and not (len(tr) == len(t) and np.array_equal(tr, t)):
                ax.plot(tr, fq / 1e3, color="tab:blue", ls="--", lw=1)
        for (tg, fg), e in zip(gts, expected):                         # experts' marks
            if tg[-1] >= a and tg[0] <= b:
                ax.plot(tg, fg / 1e3, color="limegreen" if e else "gold", ls="-" if e else "--", lw=1.3)
        ax.plot(t, f / 1e3, color="red", lw=2, alpha=0.85)
        ax.set_xlim(ext[0], ext[1])
        ax.set_ylim(ext[2], ext[3])
        ax.set_xlabel("time in recording (s)")
        ax.legend(handles=[Line2D([], [], color="red", lw=2, label="detection to judge"),
                           Line2D([], [], color="limegreen", label="marked whistle (counted)"),
                           Line2D([], [], color="gold", ls="--", label="marked whistle (not counted)"),
                           Line2D([], [], color="tab:blue", ls="--", label="other detections, same detector"),
                           Line2D([], [], color="grey", ls=":", label="5 and 24 kHz")],
                  loc="upper right", fontsize=7, framealpha=0.8)
        fig.savefig(OUT / "pictures" / f"{p['id']}.png", dpi=90)
        plt.close(fig)
    del x
    print(f"  {stem}: {len(mine)} pictures", flush=True)

print("\n===== 5. sheet, key, guide; copy to Drive =====")
with open(OUT / "sheet.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["id", "category", "sure", "notes"])
    w.writerows([[p["id"], "", "", ""] for p in picks])
(OUT / "do_not_open_until_done").mkdir()
with open(OUT / "do_not_open_until_done" / "key.csv", "w", newline="") as fh:
    cols = ["id", "method", "species", "recording", "det_index", "start_s", "end_s", "min_hz", "max_hz", "median_hz"]
    w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(picks)
shutil.copyfile(f"{CODE}/mod_detector_5_24/false_alarm_guide.md", OUT / "GUIDE.md")
(OUT / "made_by.json").write_text(json.dumps({"git_commit": version["git_commit"], "seed": SEED, "per_group": PER_GROUP,
                                              "recordings": RECORDINGS, "setting": SETTING, "n_pictures": len(picks)}, indent=2))
shutil.make_archive(str(SCRATCH / OUT_NAME), "zip", OUT)
shutil.move(str(SCRATCH / f"{OUT_NAME}.zip"), OUT / f"{OUT_NAME}.zip")
shutil.copytree(OUT, f"{DRIVE}/{OUT_NAME}")
print(f"  {len(picks)} pictures, sheet.csv, GUIDE.md and the answer key saved to {DRIVE}/{OUT_NAME}/")
if not LOCAL_TEST:
    drive.flush_and_unmount()   # make sure Drive has finished writing
print("\nDONE. Open GUIDE.md in that Drive folder and start sorting. Do not open do_not_open_until_done/ until finished.")
