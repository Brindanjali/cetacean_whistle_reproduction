"""The VAE-GMM V1 files WhistleCode reads (PLAN.md section 3), with the checkpoint -> latents -> GMM chain check.

latents_mu.json records the SHA-256 of the checkpoint the latents were encoded with, and gmm.json the SHA-256 of the
latents the GMM was fitted on. check_lineage() refuses a set of files where that chain is broken (for example a new
final.pt with the old GMM after the training resume).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from . import repro
from .config import PROJECT_ROOT, WhistleCodeError, default_config


class ModelError(WhistleCodeError):
    pass


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


@dataclass(frozen=True)
class ModelFiles:
    run_dir: Path
    checkpoint: Path
    latents: Path
    latents_json: Path
    gmm: Path
    gmm_json: Path


def model_files(cfg: dict | None = None) -> ModelFiles:
    m = (cfg or default_config())["model"]
    run = PROJECT_ROOT / m["run_dir"]
    return ModelFiles(run, run / "checkpoints" / m["checkpoint"], run / m["latents"], run / m["latents_json"],
                      run / m["gmm"], run / m["gmm_json"])


def check_lineage(cfg: dict | None = None) -> dict:
    """SHA-256 of the checkpoint, latents and GMM, after checking that each was made from the one before."""
    f = model_files(cfg)
    for p in (f.checkpoint, f.latents, f.latents_json, f.gmm, f.gmm_json):
        if not p.exists():
            raise ModelError(f"missing model file {p}")
    ck, lat, gmm = sha256_file(f.checkpoint), sha256_file(f.latents), sha256_file(f.gmm)
    lj = json.loads(f.latents_json.read_text(encoding="utf-8"))
    gj = json.loads(f.gmm_json.read_text(encoding="utf-8"))
    if lj.get("checkpoint_sha256") != ck:
        raise ModelError(f"{f.latents.name} was encoded with another checkpoint than {f.checkpoint.name}; "
                         "encode the latents again and refit the GMM (PLAN.md section 3.3)")
    if gj.get("latents_sha256") != lat:
        raise ModelError(f"{f.gmm} was fitted on other latents than {f.latents.name}; refit the GMM (PLAN.md section 3.3)")
    return {"checkpoint": str(f.checkpoint.relative_to(PROJECT_ROOT)).replace("\\", "/"), "checkpoint_sha256": ck,
            "latents_sha256": lat, "gmm": str(f.gmm.relative_to(PROJECT_ROOT)).replace("\\", "/"), "gmm_sha256": gmm,
            "n_points": int(gj["diagnostics"]["n_points"]), "n_components": int(gj["n_components"])}


@dataclass
class GMM:
    weights: np.ndarray        # (K,)
    means: np.ndarray          # (K, D)
    covariances: np.ndarray    # (K, D, D)
    n_points: int

    @property
    def nk(self) -> np.ndarray:
        """Whistles per component (soft counts)."""
        return self.weights * self.n_points

    def cholesky(self, k: int) -> np.ndarray:
        return np.linalg.cholesky(self.covariances[k])


def load_gmm(cfg: dict | None = None) -> GMM:
    f = model_files(cfg)
    z = np.load(f.gmm)
    n = int(json.loads(f.gmm_json.read_text(encoding="utf-8"))["diagnostics"]["n_points"])
    return GMM(z["weights"].astype(np.float64), z["means"].astype(np.float64), z["covariances"].astype(np.float64), n)


def device(cfg: dict | None = None) -> torch.device:
    return repro.resolve_device((cfg or default_config())["model"]["device"])


def load_vae(cfg: dict | None = None, dev: torch.device | None = None):
    from whistlepipe.vaegmm.train import load_trained_vae

    cfg = cfg or default_config()
    f = model_files(cfg)
    vae, _ = load_trained_vae(f.run_dir, dev or device(cfg), f.checkpoint.name)
    vae.eval()
    return vae


@torch.no_grad()
def decode(vae, z: np.ndarray, batch: int = 256) -> np.ndarray:
    """Latents (N, D) -> images (N, 128, 128), float32, row 0 = highest frequency."""
    dev = next(vae.parameters()).device
    z = np.asarray(z, dtype=np.float32)
    out = [vae.decoder(torch.from_numpy(z[i:i + batch]).to(dev))[:, 0].float().cpu().numpy() for i in range(0, len(z), batch)]
    return np.concatenate(out) if out else np.zeros((0, 128, 128), np.float32)
