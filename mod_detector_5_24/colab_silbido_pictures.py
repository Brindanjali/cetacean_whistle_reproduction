# Colab cell: blind pictures of Silbido's no-whistle detections, to sort by eye like ours (step 1b).
# Paste this whole file into ONE Colab cell and run it. A CPU runtime is enough (~5 min). Nothing is downloaded from
# the internet: it reads the audio Silbido itself heard, already in your Drive.
# Needs in Google Drive:
#   MyDrive/whistle_detector_5_24/code/whistle_code_5_24.zip  (python mod_detector_5_24/make_colab_bundle_5_24.py,
#       from a clean, committed repository; it packs Silbido's no-whistle detections and the earlier picture key)
#   MyDrive/whistle_detector_5_24/silbido_nowhistle_v1/nowhistle_wav/  (made by colab_silbido_audio.py on 13 Nov)
#   MyDrive/whistle_detector_5_24/nowhistle_v1/dets/  (our detections, made by colab_nowhistle_test.py)
# What it does:
#   1. checks the audio against its manifest (size and MD5; the manifest must be the 13 Nov one);
#   2. picks 10 of Silbido's detections per group (beaked / sperm whale) that pass the benchmark rule (5-24 kHz,
#      >= 150 ms), with a fixed seed, exactly as colab_nowhistle_test.py picked ours;
#   3. adds 10 of the 40 pictures you already sorted for our detectors (redrawn the same way, new ids), so you cannot
#      tell which pictures are Silbido's, and so we can check that your sorting is consistent between sessions;
#   4. draws the 30 pictures in the same style as before, in random order, ids SB001...; writes sheet.csv to fill in,
#      GUIDE.md (the same categories as last time) and the hidden key in do_not_open_until_done/.
# Output folder: MyDrive/whistle_detector_5_24/silbido_pictures_v1/ (never overwritten: if sheet.csv exists it stops).
import csv
import hashlib
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

PICS_PER_GROUP = 10        # Silbido pictures per group, as for each of our detectors
N_REPEATS = 10             # pictures of ours shown again, to hide which are Silbido's and to check consistency
SEED = 2026
MANIFEST_MD5 = "1a47c5a9d22842861b6db9d034670ae3"   # printed by colab_silbido_audio.py on 13 Nov 2026
LOCAL_TEST = os.environ.get("VERIFY_LOCAL_TEST") == "1"   # only for testing on a PC; leave unset on Colab
CONTENT = os.environ.get("VERIFY_CONTENT", "/content")
DRIVE = f"{CONTENT}/drive/MyDrive/whistle_detector_5_24"
CODE = f"{CONTENT}/whistle_code"
WAV = Path(DRIVE) / "silbido_nowhistle_v1" / "nowhistle_wav"
OURS = Path(DRIVE) / "nowhistle_v1" / "dets"
OUT = Path(DRIVE) / "silbido_pictures_v1"
SIL_TAG = "silbido-graph"
LO, HI, MIN_S = 5000.0, 24000.0, 0.150   # benchmark rule

from google.colab import drive
drive.mount(f"{CONTENT}/drive")

print("===== 1. code bundle and audio =====")
if (OUT / "sheet.csv").exists():
    raise SystemExit(f"STOP: {OUT}/sheet.csv already exists: the pictures were made before (your sheet is kept). "
                     "Sort them, or delete that folder to make them again.")
shutil.rmtree(CODE, ignore_errors=True)
with zipfile.ZipFile(f"{DRIVE}/code/whistle_code_5_24.zip") as z:
    z.extractall(CONTENT)
version = json.load(open(f"{CODE}/CODE_VERSION.json"))
print({k: v for k, v in version.items() if k not in ("files_sha256", "committed_dets_sha256")})
SIL = Path(os.environ.get("VERIFY_SILBIDO_DETS", f"{CODE}/results/nowhistle/silbido/nowhistle/{SIL_TAG}"))
OLD_KEY = Path(os.environ.get("VERIFY_OLD_KEY", f"{CODE}/results/nowhistle/key.csv"))
for need in (SIL, OLD_KEY, Path(f"{CODE}/mod_detector_5_24/nowhistle_guide.md")):
    if not need.exists():
        raise SystemExit(f"STOP: old code bundle (no {need}): rebuild it from the repository and upload it")
if version["git_uncommitted_code_changes"] and not LOCAL_TEST:
    raise SystemExit("STOP: the bundle was built with uncommitted changes; commit first, then rebuild it")
sys.path.insert(0, f"{CODE}/mod_detector_5_24")
import numpy as np
import soundfile as sf
import dclde2011 as D

man = WAV / "nowhistle_wav_manifest.csv"
man_md5 = hashlib.md5(man.read_bytes()).hexdigest()
if man_md5 != MANIFEST_MD5 and not LOCAL_TEST:
    raise SystemExit(f"STOP: {man} is not the manifest of 13 Nov (MD5 {man_md5})")
with open(man, encoding="utf-8") as fh:
    FILES = list(csv.DictReader(fh))
print(f"  manifest MD5 {man_md5}: {len(FILES)} files")


def wav_ok(row) -> bool:
    p = WAV / row["wav_file"]
    if not p.exists() or p.stat().st_size != int(row["size_bytes"]):
        return False
    h = hashlib.md5()
    with open(p, "rb") as f:
        for blk in iter(lambda: f.read(1 << 22), b""):
            h.update(blk)
    return h.hexdigest() == row["md5"]


print("\n===== 2. Silbido's detections under the benchmark rule =====")
rng = np.random.default_rng(SEED)
cands = {}
for row in FILES:
    tr = D.read_tonals(SIL / row["wav_file"].replace(".wav", ".det"))
    cands.setdefault(row["group"], []).extend(
        (row["source_flac"], i, float(t[0]), float(t[-1]), float(np.median(f)))
        for i, (t, f) in enumerate(tr) if t[-1] - t[0] >= MIN_S and LO <= np.median(f) <= HI)
picks = []
for group, c in sorted(cands.items()):
    c = sorted(c)
    idx = sorted(rng.choice(len(c), size=min(PICS_PER_GROUP, len(c)), replace=False)) if c else []
    picks += [{"method": SIL_TAG, "recording": group, "file": c[j][0], "det_index": c[j][1], "start_s": round(c[j][2], 3),
               "end_s": round(c[j][3], 3), "median_hz": round(c[j][4], 1), "repeat_of": ""} for j in idx]
    print(f"  {SIL_TAG} {group:12s}: {len(c)} detections, {len(idx)} picked")

print("\n===== 3. repeats of pictures you already sorted =====")
with open(OLD_KEY, encoding="utf-8") as fh:
    old = list(csv.DictReader(fh))
for j in sorted(rng.choice(len(old), size=min(N_REPEATS, len(old)), replace=False)):
    o = old[j]
    picks.append({"method": f"{o['method']} (repeat)", "recording": o["recording"], "file": o["file"],
                  "det_index": int(o["det_index"]), "start_s": float(o["start_s"]), "end_s": float(o["end_s"]),
                  "median_hz": float(o["median_hz"]), "repeat_of": o["id"]})
print(f"  {sum(1 for p in picks if p['repeat_of'])} of {len(old)} earlier pictures redrawn under new ids")
for n, j in enumerate(rng.permutation(len(picks)), 1):
    picks[j]["id"] = f"SB{n:03d}"
picks.sort(key=lambda p: p["id"])

print("\n===== 4. pictures =====")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy import signal
row_of = {r["source_flac"]: r for r in FILES}
for sub in ("pictures", "do_not_open_until_done"):
    (OUT / sub).mkdir(parents=True, exist_ok=True)


def tracks_of(p):
    if p["repeat_of"]:
        return D.read_tonals(OURS / p["method"].replace(" (repeat)", "") / f"{p['file']}.det")
    return D.read_tonals(SIL / row_of[p["file"]]["wav_file"].replace(".wav", ".det"))


for fname in sorted({p["file"] for p in picks}):
    row = row_of[fname]
    if not wav_ok(row):
        raise SystemExit(f"STOP: {row['wav_file']} in Drive is missing or differs from the manifest")
    x16, fs = sf.read(WAV / row["wav_file"], dtype="int16")
    x = x16.astype(np.float64) / 32768.0   # the same scale as the earlier pictures
    for p in [p for p in picks if p["file"] == fname]:
        p["encounter_id"] = row["encounter_id"]
        tracks = tracks_of(p)
        t, f = tracks[p["det_index"]]
        if p["repeat_of"] and (round(float(t[0]), 3), round(float(t[-1]), 3)) != (p["start_s"], p["end_s"]):
            raise SystemExit(f"STOP: our detection for {p['repeat_of']} in Drive is not the one in the key")
        pad = max(0.5, (1.5 - (t[-1] - t[0])) / 2)
        a0, b0 = max(0.0, t[0] - pad), min(len(x) / fs, t[-1] + pad)
        fr, tt, S = signal.spectrogram(x[int(a0 * fs):int(b0 * fs)], fs, window="hann", nperseg=2048, noverlap=1536,
                                       mode="magnitude")
        k = (fr >= 2000) & (fr <= 40000)
        db = 20 * np.log10(S[k] + 1e-12)
        db -= np.median(db, axis=1, keepdims=True)
        ext = [a0 + tt[0], a0 + tt[-1], fr[k][0] / 1e3, fr[k][-1] / 1e3]
        fig, axs = plt.subplots(2, 1, figsize=(11, 8), sharex=True, constrained_layout=True)
        for ax in axs:
            ax.imshow(db, origin="lower", aspect="auto", extent=ext, cmap="gray_r", vmin=0, vmax=25)
            ax.set_ylabel("pitch (kHz)")
        axs[0].set_title(f"{p['id']}   top: plain   |   bottom: same, with lines (red = the detection to judge)")
        for hz in (LO, HI):
            axs[1].axhline(hz / 1e3, color="grey", ls=":", lw=0.8)
        for tr_, fq in tracks:
            if tr_[-1] >= a0 and tr_[0] <= b0 and not (len(tr_) == len(t) and np.array_equal(tr_, t)):
                axs[1].plot(tr_, fq / 1e3, color="tab:blue", ls="--", lw=1)
        axs[1].plot(t, f / 1e3, color="red", lw=2, alpha=0.85)
        axs[1].set_xlim(ext[0], ext[1])
        axs[1].set_ylim(ext[2], ext[3])
        axs[1].set_xlabel("time in file (s)")
        axs[1].legend(handles=[Line2D([], [], color="red", lw=2, label="detection to judge"),
                               Line2D([], [], color="tab:blue", ls="--", label="other detections, same detector"),
                               Line2D([], [], color="grey", ls=":", label="5 and 24 kHz")],
                      loc="upper right", fontsize=7, framealpha=0.8)
        fig.savefig(OUT / "pictures" / f"{p['id']}.png", dpi=90)
        plt.close(fig)
    print(f"  {fname}: pictures drawn", flush=True)

with open(OUT / "do_not_open_until_done" / "key.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["id", "method", "recording", "encounter_id", "file", "det_index", "start_s",
                                       "end_s", "median_hz", "repeat_of"])
    w.writeheader()
    w.writerows(picks)
shutil.copyfile(f"{CODE}/mod_detector_5_24/nowhistle_guide.md", OUT / "GUIDE.md")
with open(OUT / "sheet.csv", "w", newline="") as fh:   # written last: its presence means the pictures are complete
    w = csv.writer(fh)
    w.writerow(["id", "category", "sure", "notes"])
    w.writerows([[p["id"], "", "", ""] for p in picks])
print(f"  {len(picks)} pictures ({sum(1 for p in picks if not p['repeat_of'])} Silbido, "
      f"{sum(1 for p in picks if p['repeat_of'])} repeats), sheet.csv and GUIDE.md saved; code commit "
      f"{version['git_commit'][:7]}")
if not LOCAL_TEST:
    drive.flush_and_unmount()   # make sure Drive has finished writing
print(f"\nDONE. Open {OUT}/GUIDE.md, then sort the pictures in sheet.csv (do not open do_not_open_until_done/).")
