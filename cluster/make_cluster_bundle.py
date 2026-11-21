"""Pack the runnable web demo (page + API + trained models) into one zip for a cluster node.

    python cluster/make_cluster_bundle.py [--out PATH]

The zip holds what `python whistle.py serve` reads, and nothing else:
    whistle.py, src/whistlepipe/, configs/          the backend (FastAPI inference API) and its settings
    web/                                            the frontend (page, fonts, footage, example excerpts)
    models/detector/<S5 detector>/                  whistle detector checkpoint (configs/pipeline.toml [decisions.s5])
    models/vaegmm/<run_id>/                         VAE checkpoint, GMM, component features (configs/inference.toml [model])
    preprocessed/dataset_info.json, images.csv      processing hash and centre frequencies of the training whistles
    setup_node.sh, run_node.sh, requirements-node.txt, README_CLUSTER.md     (from cluster/node/)
    offline/                                        portable Python + Linux wheels, only if cluster/offline/ exists
                                                    (python cluster/make_offline_kit.py; for a node without internet)
    CODE_VERSION.json, MANIFEST.sha256              code lineage (no .git on the node) and a checksum of every file

Not packed: raw audio, preprocessed images, training caches, tests, docs (not needed to run the demo).
A <zip>.sha256 file is written beside the zip, to check the copy after it has been through HDFS.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from whistlepipe.config import load_pipeline_config  # noqa: E402
from whistlepipe.infer import load_inference_config, model_paths  # noqa: E402
from whistlepipe.vaegmm.config import load_vaegmm_config  # noqa: E402

TOP = "whistle_app"
STORED = {".mp4", ".jpg", ".png", ".woff2", ".flac", ".whl", ".gz"}        # already compressed
CODE_PATHS = ("src", "configs", "whistle.py", "web")


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True, check=True).stdout.strip()


def tree(d: Path) -> list[Path]:
    return sorted(p for p in d.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def collect() -> list[Path]:
    icfg, pcfg, vcfg = load_inference_config(), load_pipeline_config(), load_vaegmm_config()
    mp = model_paths(icfg, vcfg)
    dataset = ROOT / pcfg["paths"]["dataset_dir"]
    encounters = vcfg["deviations"].get("encounters")
    csvs = sorted(dataset.glob("encounter_*/images.csv"))
    if encounters is not None:
        csvs = [c for c in csvs if c.parent.name in {f"encounter_{e}" for e in encounters}]
    files = [ROOT / "whistle.py", ROOT / "requirements.txt"]
    files += [p for p in tree(ROOT / "src" / "whistlepipe") if p.suffix == ".py"]
    files += sorted((ROOT / "configs").glob("*.toml"))
    files += tree(ROOT / "web")
    files += tree((ROOT / pcfg["decisions"]["s5"]["checkpoint"]).parent)
    files += [mp["vae"], mp["run_dir"] / "checkpoints" / "final.pt", mp["run_dir"] / "train_info.json",
              mp["gmm"], mp["gmm"].with_suffix(".json"), mp["component_features"], mp["component_features"].with_suffix(".json")]
    files += [dataset / "dataset_info.json", *csvs]
    missing = [str(f.relative_to(ROOT)) for f in files if not f.is_file()]
    if missing:
        raise SystemExit("missing, so the demo would not run on the node:\n  " + "\n  ".join(missing))
    return list(dict.fromkeys(files))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "cluster" / "dist" / f"{TOP}.zip"))
    args = ap.parse_args()
    entries: list[tuple[str, bytes | Path, int]] = [(str(f.relative_to(ROOT)).replace("\\", "/"), f, 0o644) for f in collect()]
    for f in sorted((ROOT / "cluster" / "node").iterdir()):                  # LF line endings: bash rejects CRLF
        entries.append((f.name, f.read_bytes().replace(b"\r\n", b"\n"), 0o755 if f.suffix == ".sh" else 0o644))
    offline = ROOT / "cluster" / "offline"
    if offline.is_dir():
        entries += [("offline/" + str(f.relative_to(offline)).replace("\\", "/"), f, 0o644) for f in tree(offline)]

    sha = {}
    for name, src, _ in entries:
        h = hashlib.sha256()
        if isinstance(src, bytes):
            h.update(src)
        else:
            with open(src, "rb") as fh:
                while chunk := fh.read(1 << 20):
                    h.update(chunk)
        sha[name] = h.hexdigest()
    version = {"git_commit": git("rev-parse", "HEAD"),
               "git_uncommitted_code_changes": bool(git("status", "--porcelain", "--", "src", "configs", "whistle.py")),
               "uncommitted_files": [ln.split(maxsplit=1)[1] for ln in git("status", "--porcelain", "--", *CODE_PATHS).splitlines()],
               "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "files_sha256": sha}
    manifest = "".join(f"{h}  {n}\n" for n, h in sha.items()).encode()
    entries += [("CODE_VERSION.json", json.dumps(version, indent=2).encode(), 0o644), ("MANIFEST.sha256", manifest, 0o644)]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    now = time.localtime()[:6]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, src, mode in entries:
            zi = zipfile.ZipInfo(f"{TOP}/{name}", now)
            zi.create_system, zi.external_attr = 3, (0o100000 | mode) << 16          # Unix modes: unzip keeps run scripts executable
            zi.compress_type = zipfile.ZIP_STORED if Path(name).suffix.lower() in STORED else zipfile.ZIP_DEFLATED
            if isinstance(src, bytes):
                z.writestr(zi, src)
            else:
                with open(src, "rb") as fh, z.open(zi, "w") as dst:
                    while chunk := fh.read(1 << 20):
                        dst.write(chunk)
    h = hashlib.sha256()
    with open(out, "rb") as fh:
        while chunk := fh.read(1 << 20):
            h.update(chunk)
    Path(str(out) + ".sha256").write_bytes(f"{h.hexdigest()}  {out.name}\n".encode())
    print(f"{out}  ({out.stat().st_size / 1e6:.1f} MB, {len(entries)} files, commit {version['git_commit'][:7]}, "
          f"uncommitted: {version['uncommitted_files'] or 'none'})")
    print(f"{out}.sha256  {h.hexdigest()}")
    print("offline kit: " + ("included (no internet needed on the node)" if offline.is_dir() else
                             "not included (the node downloads Python and the packages)"))


if __name__ == "__main__":
    main()
