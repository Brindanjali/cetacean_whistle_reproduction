"""The baseline modem of PLAN.md section 8.5: WhistleCode with its whale shapes replaced by straight-line chirps.

Everything else is the same: the format v2 frame, the key and nonce, the rhythm bank with its cover whistles, the four pitch
candidates per slot and the receiver. Comparing the two shows what sounding like a whale costs in reliability, and what it buys
in covertness.

- `[PLAN]` 16 straight-line chirps of 200 ms whose total sweeps are spaced evenly from -1.5 to +1.5 kHz (symbol 7 or 8 is close
  to a constant tone).
- `[DECISION]` The signature whistle is a 300 ms up-then-down chirp of 1 kHz, a shape none of the 16 chirps can take.
- `[DECISION]` Chirps are played without the realism library (no recorded voices or clicks) and without latent variation
  (tau = 0): the baseline is meant to be a plain modem.
- `[DECISION]` Its data whistles sit 2.5 dB above the channel's reference level. WhistleCode's data whistles sit 0-5 dB above it
  (realism.data_level_db), so both are compared at the same median level.

The chirp codebook is written once to `whistlecode/outputs/baseline_codebook` and has the same file format as the real one.
"""
from __future__ import annotations

import copy
from pathlib import Path

import numpy as np

from . import codebook
from .config import PROJECT_ROOT, default_config
from .contour import Contour, centred

CHIRP_MS = 200.0
SWEEPS_HZ = tuple(np.linspace(-1500.0, 1500.0, 16).tolist())
SIGNATURE_MS = 300.0
SIGNATURE_RISE_HZ = 1000.0
DATA_LEVEL_DB = 2.5


def out_dir() -> Path:
    return PROJECT_ROOT / "whistlecode" / "outputs" / "baseline_codebook"


def chirp_codebook(cfg: dict | None = None) -> codebook.Codebook:
    """The 16 chirps and the signature, with the real codebook's frame hop and latent size (the latents are never used)."""
    cfg = cfg or default_config()
    real = codebook.load(cfg)
    hop = real.types[0].contour.hop_s
    dim = int(real.types[0].mean.shape[0])
    n = int(round(CHIRP_MS / 1000.0 / hop))
    x = np.linspace(-0.5, 0.5, n)
    zeros, flat = np.zeros(dim), np.zeros((dim, dim))
    types = [codebook.WhistleType(-1, k, zeros, flat, Contour(centred(s * x), hop), 0.0) for k, s in enumerate(SWEEPS_HZ)]
    m = int(round(SIGNATURE_MS / 1000.0 / hop))
    rise = SIGNATURE_RISE_HZ * (1.0 - 2.0 * np.abs(np.linspace(-0.5, 0.5, m)))
    sig = codebook.WhistleType(-2, None, zeros, flat, Contour(centred(rise), hop), 0.0)
    info = {"kind": "baseline chirp modem (PLAN.md section 8.5)", "model": real.info["model"], "chirp_ms": CHIRP_MS,
            "sweeps_hz": list(SWEEPS_HZ), "signature_ms": SIGNATURE_MS, "signature_rise_hz": SIGNATURE_RISE_HZ,
            "frames_per_chirp": n, "hop_s": hop, "quick": False}
    return codebook.Codebook(types, sig, info)


def build(cfg: dict | None = None, path: Path | None = None) -> Path:
    path = Path(path or out_dir())
    codebook.save(path, chirp_codebook(cfg))
    return path


def config(cfg: dict | None = None) -> dict:
    """The settings the baseline runs with: no latent variation, and data whistles at DATA_LEVEL_DB above the reference.

    The channel scales a message so that `sender.data_amplitude * 10 ** (median_level_db / 20)` sits at the SNR. The plain sender
    plays data whistles at `data_amplitude`, so a reference of -DATA_LEVEL_DB puts them DATA_LEVEL_DB above the SNR. The realism
    library is never loaded for a codebook given by path (sender.Sender), whatever `realism.enabled` says."""
    c = copy.deepcopy(cfg or default_config())
    c["transmit"]["tau"] = 0.0
    c["realism"]["enabled"] = True
    c["realism"]["median_level_db"] = -DATA_LEVEL_DB
    return c
