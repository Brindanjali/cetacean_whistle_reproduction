"""Pack what the 5-24 kHz detector notebook needs on Colab into one zip (upload it to Google Drive).

    python mod_detector_5_24/make_colab_bundle_5_24.py [--out PATH]

Contents: src/whistlepipe/ (without __pycache__), configs/, whistle.py, this folder's configs, launcher, file list and
DCLDE 2011 benchmark, the trained ridgenet-5-24 checkpoint once it exists, metadata/manifest_363.csv (names of all encounter-191 files; the background picker needs the full list) and
CODE_VERSION.json (git commit, uncommitted-change flag, SHA-256 of every packed file), as colab/make_colab_bundle.py does.
Also packs the committed results/dclde2011_detections/ score files (not the .det files, only their SHA-256 in
CODE_VERSION.json "committed_dets_sha256") and colab_download_dclde2011.py, for colab_verify_scores.py; and, for
colab_nowhistle_test.py, nowhistle_files.csv, nowhistle_guide.md and the 2-24 kHz checkpoint (models/detector/ridgenet-v2c/);
and, for colab_silbido_audio.py, silbido/run_silbido_nowhistle.m and silbido/silbido_nowhistle_guide.html; and, for
colab_silbido_pictures.py, results/nowhistle/silbido/nowhistle/silbido-graph/*.det and results/nowhistle/key.csv.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True, check=True).stdout.strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "dist" / "whistle_code_5_24.zip"))
    args = ap.parse_args()
    files = sorted(p for p in (ROOT / "src" / "whistlepipe").rglob("*.py") if "__pycache__" not in p.parts)
    files += sorted((ROOT / "configs").glob("*.toml")) + [ROOT / "whistle.py", ROOT / "metadata" / "manifest_363.csv"]
    files += [HERE / n for n in ("pipeline.toml", "detector.toml", "whistle_5_24.py", "background_files.csv", "dclde2011.py")]
    files += [p for p in [HERE / "models" / "detector" / "ridgenet-5-24" / "checkpoint.pt"] if p.exists()]   # after training
    # Committed DCLDE 2011 results (colab_verify_scores.py re-scores them): the small score/info files are packed; the
    # .det files are not (they are read from Drive), only their SHA-256, so the cell can check Drive holds the same bytes.
    res = ROOT / "results" / "dclde2011_detections"
    res_files = sorted(p for p in res.rglob("*") if p.is_file() and "_superseded_9_recordings" not in p.parts)
    files += [p for p in res_files if p.suffix != ".det"] + [HERE / "colab_download_dclde2011.py", HERE / "false_alarm_guide.md"]
    # no-whistle test (colab_nowhistle_test.py): the pre-chosen file list, its guide, and the 2-24 kHz detector
    files += [HERE / "nowhistle_files.csv", HERE / "nowhistle_guide.md", ROOT / "models" / "detector" / "ridgenet-v2c" / "checkpoint.pt"]
    # Silbido no-whistle run (colab_silbido_audio.py copies these next to the prepared audio for the colleague)
    files += [HERE / "silbido" / "run_silbido_nowhistle.m", HERE / "silbido" / "silbido_nowhistle_guide.html"]
    # Silbido pictures (colab_silbido_pictures.py): Silbido's no-whistle detections at default settings, and the key of
    # the 40 pictures already sorted for our detectors (10 of them are shown again)
    files += sorted((ROOT / "results" / "nowhistle" / "silbido" / "nowhistle" / "silbido-graph").glob("*.det"))
    files += [ROOT / "results" / "nowhistle" / "key.csv"]
    rel = lambda f: str(f.relative_to(ROOT)).replace("\\", "/")   # noqa: E731
    version = {"git_commit": git("rev-parse", "HEAD"),
               "git_uncommitted_code_changes": bool(git("status", "--porcelain", "--", "src", "configs", "whistle.py", "mod_detector_5_24", "results")),
               "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "files_sha256": {rel(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
               "committed_dets_sha256": {rel(f): hashlib.sha256(f.read_bytes()).hexdigest() for f in res_files if f.suffix == ".det"}}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, "whistle_code/" + str(f.relative_to(ROOT)).replace("\\", "/"))
        z.writestr("whistle_code/CODE_VERSION.json", json.dumps(version, indent=2))
    print(f"{out}  ({out.stat().st_size / 1e6:.2f} MB, {len(files)} files, commit {version['git_commit'][:7]}, "
          f"uncommitted changes: {version['git_uncommitted_code_changes']})")


if __name__ == "__main__":
    main()
