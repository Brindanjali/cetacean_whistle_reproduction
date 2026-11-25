# Colab cell: no-whistle test. Both of our detectors on 2017 beaked whale and sperm whale recordings (species that click
# but don't whistle), so every detection is a false alarm: we measure false alarms per minute.
# Paste this whole file into ONE Colab cell and run it. A CPU runtime is enough (~1-1.5 h for 146 one-minute files).
# SAFE TO RE-RUN: files already done are skipped, so if Colab disconnects, just run the cell again.
# Needs in Google Drive: MyDrive/whistle_detector_5_24/code/whistle_code_5_24.zip
#   (python mod_detector_5_24/make_colab_bundle_5_24.py, from a clean, committed repository).
# What it does:
#   1. unpacks the bundle; loads both detectors with settings fixed in advance:
#        ridgenet-5-24 : mod_detector_5_24/pipeline.toml, harmonics kept (the DCLDE benchmark setting)
#        ridgenet-v2c  : configs/pipeline.toml as is (the 2-24 kHz detector, as used for the VAE-GMM dataset)
#   2. for each file in mod_detector_5_24/nowhistle_files.csv (146 files, chosen in advance): download it from NOAA's
#      public bucket to the Colab disk, check its size and MD5, run both detectors, save the detections to Drive,
#      delete the recording. Nothing is stored in Drive except small detection and result files.
#   3. counts false alarms per minute, per detector, for beaked and sperm whales (summary.md in the Drive folder);
#   4. draws blind pictures of 10 detections per detector per group (fixed seed) for checking by eye, with sheet.csv
#      to fill in (skipped if sheet.csv already exists, so a sheet you started is never overwritten).
# Output folder: MyDrive/whistle_detector_5_24/nowhistle_v1/
import base64
import csv
import hashlib
import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

PICS_PER_GROUP = 10   # pictures per detector per group (beaked / sperm)
SEED = 2026
LOCAL_TEST = os.environ.get("VERIFY_LOCAL_TEST") == "1"   # only for testing on a PC; leave unset on Colab
CONTENT = os.environ.get("VERIFY_CONTENT", "/content")
DRIVE = f"{CONTENT}/drive/MyDrive/whistle_detector_5_24"
CODE = f"{CONTENT}/whistle_code"
OUT = Path(DRIVE) / "nowhistle_v1"
TMP = Path(CONTENT) / "nowhistle_tmp"
URL = "https://storage.googleapis.com/noaa-passive-bioacoustic/dclde/2022/dclde_2022_1705/audio/"
DETECTORS = {   # name -> (pipeline config inside the bundle, overrides); fixed before running
    "ridgenet-5-24": ("mod_detector_5_24/pipeline.toml", ["decisions.s6.suppress_harmonics=false"]),
    "ridgenet-v2c": ("configs/pipeline.toml", []),
}
BAND_RULE = (5000.0, 24000.0, 0.150)   # benchmark rule: median pitch in 5-24 kHz and at least 150 ms

from google.colab import drive
drive.mount(f"{CONTENT}/drive")

print("===== 1. code bundle and detectors =====")
shutil.rmtree(CODE, ignore_errors=True)
with zipfile.ZipFile(f"{DRIVE}/code/whistle_code_5_24.zip") as z:
    z.extractall(CONTENT)
version = json.load(open(f"{CODE}/CODE_VERSION.json"))
print({k: v for k, v in version.items() if k not in ("files_sha256", "committed_dets_sha256")})
for need in ("mod_detector_5_24/nowhistle_files.csv", "models/detector/ridgenet-v2c/checkpoint.pt"):
    if not os.path.exists(f"{CODE}/{need}"):
        raise SystemExit(f"STOP: old code bundle (no {need}): rebuild it from the repository and upload it")
if version["git_uncommitted_code_changes"] and not LOCAL_TEST:
    raise SystemExit("STOP: the bundle was built with uncommitted changes; commit first, then rebuild it")
if importlib.util.find_spec("soundfile") is None:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "soundfile"], check=True)
sys.path.insert(0, f"{CODE}/src")
sys.path.insert(0, f"{CODE}/mod_detector_5_24")
import numpy as np
import torch
import whistlepipe.config as C
from whistlepipe import audio, dsp
from whistlepipe.detector import RidgeDetector
from whistlepipe.tracking import run_s6
import dclde2011 as D
importlib.reload(D)

cfgs, dets = {}, {}
for name, (path, overrides) in DETECTORS.items():
    cfgs[name] = C.load_pipeline_config(f"{CODE}/{path}", overrides)
    ck = Path(f"{CODE}/{cfgs[name]['decisions']['s5']['checkpoint']}")
    dets[name] = RidgeDetector.from_checkpoint(ck, cfgs[name], "cpu")
    s5, s6 = cfgs[name]["decisions"]["s5"], cfgs[name]["decisions"]["s6"]
    print(f"  {name}: band {s5['band_lo_hz']:.0f}-{s5['band_hi_hz']:.0f} Hz, threshold {s6['peak_threshold']}, "
          f"harmonics {'removed' if s6['suppress_harmonics'] else 'kept'}, checkpoint {ck.relative_to(CODE)}")
a, b = cfgs.values()
same = all(a[k] == b[k] for k in ("paper",)) and all(a["decisions"][s] == b["decisions"][s] for s in ("s1", "s2", "s3", "s4"))
assert same, "the two configs differ before the network: the spectrogram cannot be shared"
first = next(iter(cfgs.values()))   # S1-S4 are identical for both, so the spectrogram is computed once per file

with open(f"{CODE}/mod_detector_5_24/nowhistle_files.csv", encoding="utf-8") as fh:
    FILES = list(csv.DictReader(fh))
if LOCAL_TEST and os.environ.get("VERIFY_FILES"):
    with open(os.environ["VERIFY_FILES"], encoding="utf-8") as fh:
        FILES = list(csv.DictReader(fh))
print(f"  {len(FILES)} files to process ({sum(f['group'] == 'beaked whale' for f in FILES)} beaked whale, "
      f"{sum(f['group'] == 'sperm whale' for f in FILES)} sperm whale)")
for sub in ["info", "pictures", "do_not_open_until_done"] + [f"dets/{n}" for n in DETECTORS]:
    (OUT / sub).mkdir(parents=True, exist_ok=True)
shutil.copyfile(f"{CODE}/mod_detector_5_24/nowhistle_files.csv", OUT / "nowhistle_files.csv")
TMP.mkdir(exist_ok=True)


def fetch(row) -> Path:
    """Download one file to the Colab disk and check its size and MD5 (3 tries)."""
    dst = TMP / row["file"]
    for attempt in range(1, 4):
        try:
            if LOCAL_TEST and os.environ.get("VERIFY_LOCAL_SOURCE"):
                shutil.copyfile(Path(os.environ["VERIFY_LOCAL_SOURCE"]) / row["file"], dst)
            else:
                urllib.request.urlretrieve(URL + row["file"], dst)
            h = hashlib.md5()
            with open(dst, "rb") as f:
                for blk in iter(lambda: f.read(1 << 22), b""):
                    h.update(blk)
            if dst.stat().st_size == int(row["size_bytes"]) and base64.b64encode(h.digest()).decode() == row["md5_base64"]:
                return dst
            print(f"    {row['file']}: size or MD5 differs (attempt {attempt}), retrying")
        except Exception as e:
            print(f"    {row['file']}: {e} (attempt {attempt}), retrying")
        time.sleep(5)
    raise RuntimeError(f"{row['file']}: download failed 3 times; run the cell again later")


def spectrogram(path: Path):
    s1 = audio.s1_select_channel(path, first)
    s2 = dsp.s2_resample(s1, first)
    s4 = dsp.s4_stft(dsp.s3_highpass(s2, first), first)
    return s1, s2, s4


print("\n===== 2. detection (skips files already done) =====")
todo = [r for r in FILES if not (OUT / "info" / f"{r['file']}.json").exists()]
print(f"  {len(FILES) - len(todo)} already done, {len(todo)} to do")
t_start = time.time()
for i, row in enumerate(todo, 1):
    t0 = time.time()
    path = fetch(row)
    s1, s2, s4 = spectrogram(path)
    t_c = s4.frame_center_times_s()
    info = {"file": row["file"], "encounter_id": row["encounter_id"], "group": row["group"],
            "duration_s": round(s1.duration_s, 3), "int16_peak": s1.meta["int16_peak"],
            "n_full_scale": s1.meta["n_full_scale"], "n_tracks": {}}
    with torch.no_grad():
        for name, det in dets.items():
            tr = run_s6(det.predict(s4), cfgs[name])
            tracks = [(t_c[k.frames], k.freq_hz.astype(np.float64)) for k in tr.tracks]
            D.write_tonals(OUT / "dets" / name / f"{row['file']}.det", tracks)
            info["n_tracks"][name] = len(tracks)
    info["seconds"] = round(time.time() - t0, 1)
    (OUT / "info" / f"{row['file']}.json").write_text(json.dumps(info))   # written last: marks the file as done
    path.unlink()
    left = (time.time() - t_start) / i * (len(todo) - i) / 60
    print(f"  [{i}/{len(todo)}] {row['group']:12s} enc {row['encounter_id']:>3s} {row['file']}: "
          f"{info['n_tracks']}  ({info['seconds']:.0f} s, about {left:.0f} min left)", flush=True)

print("\n===== 3. false alarms per minute =====")
infos = [json.loads((OUT / "info" / f"{r['file']}.json").read_text()) for r in FILES]
lo, hi, min_s = BAND_RULE
rng = np.random.default_rng(SEED)
RULES = {"benchmark rule (5-24 kHz, >= 150 ms)": lambda t, f: t[-1] - t[0] >= min_s and lo <= np.median(f) <= hi,
         "all tracks the detector outputs": lambda t, f: True}
summary, md = {"seed": SEED, "git_commit": version["git_commit"], "results": {}}, []
candidates = {}   # (detector, group) -> detections under the benchmark rule, for the pictures
for name in DETECTORS:
    per_file = {}
    for inf in infos:
        tr = D.read_tonals(OUT / "dets" / name / f"{inf['file']}.det")
        per_file[inf["file"]] = {rule: [i for i, (t, f) in enumerate(tr) if ok(t, f)] for rule, ok in RULES.items()}
        candidates.setdefault((name, inf["group"]), []).extend(
            (inf["file"], i, float(tr[i][0][0]), float(tr[i][0][-1]), float(np.median(tr[i][1])))
            for i in per_file[inf["file"]][next(iter(RULES))])
    for rule in RULES:
        for group in ("beaked whale", "sperm whale"):
            sel = [inf for inf in infos if inf["group"] == group]
            enc = {}
            for inf in sel:
                e = enc.setdefault(inf["encounter_id"], [0, 0.0])
                e[0] += len(per_file[inf["file"]][rule])
                e[1] += inf["duration_s"] / 60
            n, minutes = sum(v[0] for v in enc.values()), sum(v[1] for v in enc.values())
            rates = {k: v[0] / v[1] for k, v in enc.items()}
            keys = list(enc)
            boot = []
            for _ in range(10000):   # resample encounters: the range reflects encounter-to-encounter differences
                pick = [keys[j] for j in rng.integers(0, len(keys), len(keys))]
                boot.append(sum(enc[k][0] for k in pick) / sum(enc[k][1] for k in pick))
            summary["results"].setdefault(name, {}).setdefault(rule, {})[group] = {
                "minutes": round(minutes, 2), "detections": n, "per_minute": n / minutes,
                "range95_per_minute": [float(v) for v in np.percentile(boot, [2.5, 97.5])],
                "encounters": len(enc), "per_encounter_per_minute": {k: round(v, 3) for k, v in rates.items()}}
md += ["# No-whistle test: false alarms per minute", "",
       f"Both detectors on 2017 beaked whale and sperm whale recordings (no whistling species logged within 15 min; "
       f"files in `nowhistle_files.csv`). Every detection counts as a false alarm. Range: 95 % bootstrap over encounters "
       f"(seed {SEED}). Code commit {version['git_commit'][:7]}.", "",
       "| Detector | Rule | Beaked whales | Sperm whales |", "|---|---|---|---|"]
for name, by_rule in summary["results"].items():
    for rule, g in by_rule.items():
        cell = lambda x: (f"{x['per_minute']:.2f} /min ({x['range95_per_minute'][0]:.2f} to {x['range95_per_minute'][1]:.2f}); "   # noqa: E731
                          f"{x['detections']} in {x['minutes']:.1f} min, {x['encounters']} encounters")
        md.append(f"| {name} | {rule} | {cell(g['beaked whale'])} | {cell(g['sperm whale'])} |")
(OUT / "summary.json").write_text(json.dumps(summary, indent=2))
(OUT / "summary.md").write_text("\n".join(md) + "\n")
print("\n".join(md))

print("\n===== 4. pictures for checking by eye =====")
if (OUT / "sheet.csv").exists():
    print("  sheet.csv already exists in Drive: pictures not redrawn (your sheet is kept)")
else:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from scipy import signal
    picks = []
    for (name, group), cands in sorted(candidates.items()):
        cands = sorted(cands)
        idx = sorted(rng.choice(len(cands), size=min(PICS_PER_GROUP, len(cands)), replace=False)) if cands else []
        picks += [{"method": name, "recording": group, "file": cands[j][0], "det_index": cands[j][1],
                   "start_s": round(cands[j][2], 3), "end_s": round(cands[j][3], 3), "median_hz": round(cands[j][4], 1)}
                  for j in idx]
        print(f"  {name:14s} {group:12s}: {len(cands)} detections, {len(idx)} picked")
    for n, j in enumerate(rng.permutation(len(picks)), 1):
        picks[j]["id"] = f"NW{n:03d}"
    picks.sort(key=lambda p: p["id"])
    enc_of = {r["file"]: r["encounter_id"] for r in FILES}
    for fname in sorted({p["file"] for p in picks}):
        row = next(r for r in FILES if r["file"] == fname)
        path = fetch(row)
        s1, s2, _ = spectrogram(path)
        x, fs = s2.samples, s2.fs
        for p in [p for p in picks if p["file"] == fname]:
            p["encounter_id"] = enc_of[fname]
            tracks = D.read_tonals(OUT / "dets" / p["method"] / f"{fname}.det")
            t, f = tracks[p["det_index"]]
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
            for hz in (lo, hi):
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
        path.unlink()
        print(f"  {fname}: pictures drawn", flush=True)
    with open(OUT / "do_not_open_until_done" / "key.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "method", "recording", "encounter_id", "file", "det_index", "start_s",
                                           "end_s", "median_hz"])
        w.writeheader()
        w.writerows(picks)
    shutil.copyfile(f"{CODE}/mod_detector_5_24/nowhistle_guide.md", OUT / "GUIDE.md")
    with open(OUT / "sheet.csv", "w", newline="") as fh:   # written last: its presence means the pictures are complete
        w = csv.writer(fh)
        w.writerow(["id", "category", "sure", "notes"])
        w.writerows([[p["id"], "", "", ""] for p in picks])
    print(f"  {len(picks)} pictures, sheet.csv and GUIDE.md saved")

shutil.rmtree(TMP, ignore_errors=True)
if not LOCAL_TEST:
    drive.flush_and_unmount()   # make sure Drive has finished writing
print(f"\nDONE. Results: {OUT}/summary.md. Then open GUIDE.md there and sort the pictures in sheet.csv.")
