# Colab cell: prepare the no-whistle recordings for the Silbido run (the colleague with MATLAB).
# Paste this whole file into ONE Colab cell and run it. A CPU runtime is enough (~45 min for 146 one-minute files).
# SAFE TO RE-RUN: files already prepared are skipped, so if Colab disconnects, just run the cell again.
# Needs in Google Drive: MyDrive/whistle_detector_5_24/code/whistle_code_5_24.zip
#   (python mod_detector_5_24/make_colab_bundle_5_24.py, from a clean, committed repository).
# What it does:
#   1. for each file in mod_detector_5_24/nowhistle_files.csv (the same 146 files as colab_nowhistle_test.py):
#      download it from NOAA's public bucket, check its size and MD5, and keep exactly the audio our detector uses:
#      channel 0 (S1), resampled 500 -> 192 kHz (S2), with mod_detector_5_24/pipeline.toml. No high-pass (Silbido
#      applies its own 5 kHz low cut-off, as on DCLDE 2011, whose files are 192 kHz). Saved as 16-bit mono WAV, the
#      same format as the DCLDE 2011 files (the originals are 16-bit too);
#   2. writes nowhistle_wav_manifest.csv (size and MD5 of every WAV; the MATLAB script checks them) and copies the
#      MATLAB script and its guide next to the audio.
# Output, the folder to SHARE with the colleague (Viewer):  MyDrive/whistle_detector_5_24/silbido_nowhistle_v1/
#     run_silbido_nowhistle.m, silbido_nowhistle_guide.html, nowhistle_wav/ (146 WAVs, ~3.4 GB, and the manifest)
# Progress notes (not to share): MyDrive/whistle_detector_5_24/silbido_nowhistle_work/
import base64
import csv
import hashlib
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

LOCAL_TEST = os.environ.get("VERIFY_LOCAL_TEST") == "1"   # only for testing on a PC; leave unset on Colab
CONTENT = os.environ.get("VERIFY_CONTENT", "/content")
DRIVE = f"{CONTENT}/drive/MyDrive/whistle_detector_5_24"
CODE = f"{CONTENT}/whistle_code"
OUT = Path(DRIVE) / "silbido_nowhistle_v1"
WAV = OUT / "nowhistle_wav"
WORK = Path(DRIVE) / "silbido_nowhistle_work"
TMP = Path(CONTENT) / "silbido_audio_tmp"
URL = "https://storage.googleapis.com/noaa-passive-bioacoustic/dclde/2022/dclde_2022_1705/audio/"
MANIFEST = "nowhistle_wav_manifest.csv"
COLS = ["wav_file", "source_flac", "group", "encounter_id", "n_samples", "duration_s", "size_bytes", "md5"]

from google.colab import drive
drive.mount(f"{CONTENT}/drive")

print("===== 1. code bundle =====")
shutil.rmtree(CODE, ignore_errors=True)
with zipfile.ZipFile(f"{DRIVE}/code/whistle_code_5_24.zip") as z:
    z.extractall(CONTENT)
version = json.load(open(f"{CODE}/CODE_VERSION.json"))
print({k: v for k, v in version.items() if k not in ("files_sha256", "committed_dets_sha256")})
for need in ("mod_detector_5_24/nowhistle_files.csv", "mod_detector_5_24/silbido/run_silbido_nowhistle.m",
             "mod_detector_5_24/silbido/silbido_nowhistle_guide.html"):
    if not os.path.exists(f"{CODE}/{need}"):
        raise SystemExit(f"STOP: old code bundle (no {need}): rebuild it from the repository and upload it")
if version["git_uncommitted_code_changes"] and not LOCAL_TEST:
    raise SystemExit("STOP: the bundle was built with uncommitted changes; commit first, then rebuild it")
if importlib.util.find_spec("soundfile") is None:
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "soundfile"], check=True)
sys.path.insert(0, f"{CODE}/src")
import numpy as np
import soundfile as sf
import whistlepipe.config as C
from whistlepipe import audio, dsp

cfg = C.load_pipeline_config(f"{CODE}/mod_detector_5_24/pipeline.toml", [])
fs_out = int(cfg["paper"]["fs_target_hz"])
print(f"  channel {cfg['decisions']['s1']['channel_index']}, {cfg['paper']['fs_raw_hz']} -> {fs_out} Hz "
      f"({cfg['decisions']['s2']['method']}, Kaiser beta {cfg['decisions']['s2']['kaiser_beta']}), 16-bit WAV")

with open(f"{CODE}/mod_detector_5_24/nowhistle_files.csv", encoding="utf-8") as fh:
    FILES = list(csv.DictReader(fh))
if LOCAL_TEST and os.environ.get("VERIFY_FILES"):
    with open(os.environ["VERIFY_FILES"], encoding="utf-8") as fh:
        FILES = list(csv.DictReader(fh))
print(f"  {len(FILES)} files ({sum(f['group'] == 'beaked whale' for f in FILES)} beaked whale, "
      f"{sum(f['group'] == 'sperm whale' for f in FILES)} sperm whale)")
for d in (WAV, WORK, TMP):
    d.mkdir(parents=True, exist_ok=True)


def md5_of(path: Path, b64: bool) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 22), b""):
            h.update(blk)
    return base64.b64encode(h.digest()).decode() if b64 else h.hexdigest()


def fetch(row) -> Path:
    """Download one file to the Colab disk and check its size and MD5 (3 tries)."""
    dst = TMP / row["file"]
    for attempt in range(1, 4):
        try:
            if LOCAL_TEST and os.environ.get("VERIFY_LOCAL_SOURCE"):
                shutil.copyfile(Path(os.environ["VERIFY_LOCAL_SOURCE"]) / row["file"], dst)
            else:
                urllib.request.urlretrieve(URL + row["file"], dst)
            if dst.stat().st_size == int(row["size_bytes"]) and md5_of(dst, True) == row["md5_base64"]:
                return dst
            print(f"    {row['file']}: size or MD5 differs (attempt {attempt}), retrying")
        except Exception as e:
            print(f"    {row['file']}: {e} (attempt {attempt}), retrying")
        time.sleep(5)
    raise RuntimeError(f"{row['file']}: download failed 3 times; run the cell again later")


print("\n===== 2. prepare the audio (skips files already done) =====")
todo = [r for r in FILES if not (WORK / f"{r['file']}.json").exists()]
print(f"  {len(FILES) - len(todo)} already done, {len(todo)} to do")
t_start = time.time()
for i, row in enumerate(todo, 1):
    t0 = time.time()
    src = fetch(row)
    s1 = audio.s1_select_channel(src, cfg)
    s2 = dsp.s2_resample(s1, cfg)
    q = np.round(s2.samples * 32768.0)   # back to 16-bit counts, the scale S1 read them in
    n_clip = int(((q > 32767) | (q < -32768)).sum())
    x16 = np.clip(q, -32768, 32767).astype(np.int16)
    name = row["file"].replace(".flac", ".wav")
    local = TMP / name
    sf.write(local, x16, fs_out, subtype="PCM_16", format="WAV")
    back, fs_back = sf.read(local, dtype="int16")
    assert fs_back == fs_out and np.array_equal(back, x16), f"{name}: WAV read-back differs"
    entry = {"wav_file": name, "source_flac": row["file"], "group": row["group"], "encounter_id": row["encounter_id"],
             "n_samples": len(x16), "duration_s": round(len(x16) / fs_out, 6), "size_bytes": local.stat().st_size,
             "md5": md5_of(local, False), "n_clipped": n_clip, "int16_peak_source": s1.meta["int16_peak"]}
    shutil.copyfile(local, WAV / (name + ".part"))
    os.replace(WAV / (name + ".part"), WAV / name)
    if (WAV / name).stat().st_size != entry["size_bytes"]:
        raise RuntimeError(f"{name}: copy to Drive has the wrong size; run the cell again")
    (WORK / f"{row['file']}.json").write_text(json.dumps(entry))   # written last: marks the file as done
    src.unlink()
    local.unlink()
    left = (time.time() - t_start) / i * (len(todo) - i) / 60
    print(f"  [{i}/{len(todo)}] {row['group']:12s} enc {row['encounter_id']:>3s} {name}: "
          f"{entry['duration_s']:.1f} s{f', {n_clip} samples clipped' if n_clip else ''}  "
          f"({time.time() - t0:.0f} s, about {left:.0f} min left)")

print("\n===== 3. check and write the manifest =====")
rows, problems = [], []
for r in FILES:
    e = json.loads((WORK / f"{r['file']}.json").read_text())
    p = WAV / e["wav_file"]
    if not p.exists() or p.stat().st_size != e["size_bytes"]:
        problems.append(e["wav_file"])
    rows.append(e)
if problems:
    for e in problems:
        (WORK / f"{e.replace('.wav', '.flac')}.json").unlink(missing_ok=True)   # so the next run redoes them
    raise SystemExit(f"STOP: {len(problems)} WAV files missing or the wrong size in Drive ({problems[:3]}...); "
                     "run the cell again")
extra = sorted(p.name for p in WAV.iterdir() if p.name != MANIFEST and p.name not in {e["wav_file"] for e in rows})
if extra:
    raise SystemExit(f"STOP: unexpected files in {WAV}: {extra[:5]}; delete them and run the cell again")
with open(WAV / (MANIFEST + ".part"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, COLS, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
os.replace(WAV / (MANIFEST + ".part"), WAV / MANIFEST)
for f in ("run_silbido_nowhistle.m", "silbido_nowhistle_guide.html"):
    shutil.copyfile(f"{CODE}/mod_detector_5_24/silbido/{f}", OUT / f)
(WORK / "code_version.json").write_text(json.dumps({k: v for k, v in version.items() if k != "files_sha256"}))
shutil.rmtree(TMP, ignore_errors=True)
tot_min = sum(e["duration_s"] for e in rows) / 60
tot_gb = sum(e["size_bytes"] for e in rows) / 1e9
clipped = sum(e["n_clipped"] for e in rows)
print(f"  {len(rows)} WAV files, {tot_min:.1f} min, {tot_gb:.2f} GB; samples clipped in total: {clipped}")
print(f"  manifest MD5: {md5_of(WAV / MANIFEST, False)}  (the MATLAB log must show the same)")
print(f"  code commit {version['git_commit'][:7]}")
print(f"\nDONE. Share this folder with the colleague (Viewer): {OUT}")
