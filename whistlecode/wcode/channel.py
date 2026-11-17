"""The channel (PLAN.md section 6).

Built so far (P1 needs it for the confusion pass): real ocean noise from the encounter recordings and narrowband SNR.
P3 adds multipath, absorption and Doppler, which act on the signal before the noise is added.

Noise: channel 0 of a raw 500 kHz file, resampled to the synthesis rate and high-passed at 2 kHz with the
reproduction's own filter. The result is cached as float32 .npy (gitignored), so each file is decoded once.

Narrowband SNR, as in the synthetic generator: a whistle's level in its own 93.75 Hz bin (at its mean frequency)
is the target SNR above the median noise level in that bin.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

from . import repro
from .config import PROJECT_ROOT, default_config


def noise_files(encounter: int) -> list[Path]:
    d = PROJECT_ROOT / f"encounter_{int(encounter)}_audio"
    files = sorted(d.glob("*.flac"))
    if not files:
        raise FileNotFoundError(f"no .flac files in {d}")
    return files


def _read_channel(path: Path, channel: int, full_scale: float, block: int = 4_000_000) -> tuple[np.ndarray, int]:
    """One channel of a multichannel FLAC, read in blocks (a 6-channel 500 kHz minute would be 720 MB as float32)."""
    parts = []
    with sf.SoundFile(str(path)) as f:
        if channel >= f.channels:
            raise ValueError(f"{path.name} has {f.channels} channels; channel {channel} requested")
        fs = int(f.samplerate)
        for blk in f.blocks(blocksize=block, dtype="int16", always_2d=True):
            parts.append(blk[:, channel].copy())
    return np.concatenate(parts).astype(np.float64) / full_scale, fs


def load_noise(path: Path, cfg: dict | None = None, pcfg=None) -> np.ndarray:
    """Channel-0 noise at the synthesis rate, high-passed, float32 (cached)."""
    cfg = cfg or default_config()
    pcfg = pcfg or repro.load_pipeline_config()
    fs = int(cfg["synth"]["fs_hz"])
    ch = int(cfg["channel"]["noise_channel"])
    path = Path(path)
    cache = PROJECT_ROOT / cfg["channel"]["noise_cache_dir"] / path.parent.name / f"{path.stem}_ch{ch}_{fs}hz_hp2k.npy"
    if cache.exists():
        return np.load(cache)
    x, fs_in = _read_channel(path, ch, float(pcfg["decisions"]["s1"]["int16_full_scale"]))
    up, down = repro.dsp.resample_ratio(fs_in, fs)
    y = signal.resample_poly(x, up, down, window=("kaiser", float(pcfg["decisions"]["s2"]["kaiser_beta"])))
    y = signal.sosfiltfilt(repro.dsp.highpass_sos(fs, pcfg), y).astype(np.float32)
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_suffix(".tmp.npy")
    np.save(tmp, y)
    os.replace(tmp, cache)
    return y


def _window(fs: float, bin_hz: float) -> np.ndarray:
    n = int(round(fs / bin_hz))
    return signal.get_window("hamming", n, fftbins=True)


def bin_levels(x: np.ndarray, fs: float, bin_hz: float = 93.75) -> np.ndarray:
    """Median raw |STFT| per frequency bin (bin k at k x bin_hz), Hamming window, 50 % overlap."""
    w = _window(fs, bin_hz)
    _, _, z = signal.stft(np.asarray(x, np.float64), fs, window=w, nperseg=len(w), noverlap=len(w) // 2,
                          boundary=None, padded=False)
    return np.median(np.abs(z), axis=1) * w.sum()      # scipy divides by sum(w); undo it


def amplitude_for_snr(snr_db: float, f_mean_hz: float, levels: np.ndarray, fs: float, cfg: dict | None = None) -> float:
    """Amplitude of a tone at f_mean_hz whose peak |STFT| sits snr_db above the median noise level of its bin."""
    c = (cfg or default_config())["channel"]
    bin_hz = float(c["snr_bin_hz"])
    snr = min(float(snr_db), float(c["max_snr_db"]))
    k = int(np.clip(round(f_mean_hz / bin_hz), 0, len(levels) - 1))
    return 10 ** (snr / 20) * float(levels[k]) / (_window(fs, bin_hz).sum() / 2)
