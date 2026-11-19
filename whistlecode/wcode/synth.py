"""Contour -> whistle audio (PLAN.md section 4.4): a phase-continuous FM tone at fc + contour offset, a Tukey envelope
with a slow amplitude ripple, and a 2nd harmonic.

envelope() is ported from src/whistlepipe/synth/whistles.py (SynthSampler._envelope). The only intended difference
is the taper range, narrowed from 0.15-0.6 to 0.15-0.3 so the fade-in lasts at most 68 ms on a 450 ms whistle and the
detector does not find the start late. tests/test_wc_synth.py checks the port against the original.
"""
from __future__ import annotations

import csv

import numpy as np
from scipy import signal as sps

from .config import PROJECT_ROOT, default_config
from .contour import Contour


def fc_pool(cfg: dict | None = None) -> np.ndarray:
    """Centre frequencies of the real whistles of fc_source_encounter that lie in fc_range_hz (PLAN.md section 4.3)."""
    s = (cfg or default_config())["synth"]
    path = PROJECT_ROOT / "preprocessed" / f"encounter_{int(s['fc_source_encounter'])}" / "images.csv"
    with open(path, encoding="utf-8-sig") as f:
        fc = np.array([float(r["center_hz"]) for r in csv.DictReader(f)])
    lo, hi = s["fc_range_hz"]
    fc = fc[(fc >= lo) & (fc <= hi)]
    if not len(fc):
        raise ValueError(f"no centre frequencies in {lo}-{hi} Hz in {path}")
    return fc


def envelope(rng: np.random.Generator, n: int, fs: float, taper=(0.15, 0.3), ripple_depth=(0.0, 0.3),
             ripple_rate_hz=(1.0, 5.0)) -> np.ndarray:
    """Same random draws, in the same order, as SynthSampler._envelope."""
    env = sps.windows.tukey(n, rng.uniform(*taper))
    t = np.arange(n) / fs
    env = env * (1 + rng.uniform(*ripple_depth) * np.sin(2 * np.pi * rng.uniform(*ripple_rate_hz) * t + rng.uniform(0, 6.28)))
    return env / max(env.max(), 1e-9)


def instantaneous_hz(contour: Contour, fc_hz: float, fs: float) -> np.ndarray:
    """Per-sample frequency: fc + the contour, interpolated between frame centres and held at both ends."""
    n = int(round(contour.n_frames * contour.hop_s * fs))
    t = (np.arange(n) + 0.5) / fs
    centres = (np.arange(contour.n_frames) + 0.5) * contour.hop_s
    return fc_hz + np.interp(t, centres, contour.offset_hz)


def whistle(contour: Contour, fc_hz: float, rng: np.random.Generator, cfg: dict | None = None,
            fs: float | None = None) -> np.ndarray:
    """One whistle, float64. The fundamental has amplitude 1 at the envelope's peak; scale it for the wanted SNR."""
    s = (cfg or default_config())["synth"]
    fs = float(fs or s["fs_hz"])
    f = instantaneous_hz(contour, fc_hz, fs)
    if f.max() * 2 >= fs / 2:
        raise ValueError(f"the 2nd harmonic of a whistle reaching {f.max():.0f} Hz does not fit below {fs / 2:.0f} Hz")
    phase = 2 * np.pi * np.cumsum(f) / fs
    x = np.cos(phase) + 10 ** (float(s["harmonic2_db"]) / 20) * np.cos(2 * phase)
    return x * envelope(rng, len(x), fs, s["taper"], s["ripple_depth"], s["ripple_rate_hz"])


def cover_whistle(contour: Contour, fc_hz: float, rng: np.random.Generator, cfg: dict | None = None,
                  fs: float | None = None) -> np.ndarray:
    """A cover whistle: as whistle(), without the harmonic when a high real whistle's harmonic would not fit."""
    s = (cfg or default_config())["synth"]
    fs = float(fs or s["fs_hz"])
    f = instantaneous_hz(contour, fc_hz, fs)
    phase = 2 * np.pi * np.cumsum(f) / fs
    x = np.cos(phase)
    if f.max() * 2 < 0.98 * fs / 2:
        x = x + 10 ** (float(s["harmonic2_db"]) / 20) * np.cos(2 * phase)
    return x * envelope(rng, len(x), fs, s["taper"], s["ripple_depth"], s["ripple_rate_hz"])


def voiced_whistle(contour: Contour, fc_hz: float, env_db: np.ndarray, h2_db: np.ndarray, h3_db: np.ndarray, tone_db: float = 0.0,
                   fade_ms: float = 5.0, fs: float = 96000.0) -> np.ndarray:
    """A whistle with a recorded voice: its loudness pattern (0 dB = the median level) and its 2nd and 3rd harmonics.

    tone_db lowers the 2nd harmonic by that much and the 3rd by twice that much, as distance does. Harmonics that would pass the
    Nyquist frequency are left out."""
    f = instantaneous_hz(contour, fc_hz, fs)
    n = len(f)
    u = np.linspace(0.0, 1.0, n)
    level = lambda v: 10 ** (np.interp(u, np.linspace(0.0, 1.0, len(v)), v) / 20)
    phase = 2 * np.pi * np.cumsum(f) / fs
    limit = 0.98 * fs / 2
    x = np.cos(phase) + level(np.asarray(h2_db) - float(tone_db)) * (2 * f < limit) * np.cos(2 * phase) \
        + level(np.asarray(h3_db) - 2 * float(tone_db)) * (3 * f < limit) * np.cos(3 * phase)
    x = x * level(env_db)
    m = min(int(round(float(fade_ms) / 1000 * fs)), n // 2)
    if m > 0:
        ramp = 0.5 - 0.5 * np.cos(np.pi * (np.arange(m) + 0.5) / m)
        x[:m] *= ramp
        x[-m:] *= ramp[::-1]
    return x
