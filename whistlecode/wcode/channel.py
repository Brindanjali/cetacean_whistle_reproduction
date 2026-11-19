"""The channel (PLAN.md section 6).

Built so far: real ocean noise from the encounter recordings and narrowband SNR. Multipath, absorption and Doppler come
later and act on the signal before the noise is added.

Noise: channel 0 of a raw 500 kHz file, resampled to the synthesis rate and high-passed at 2 kHz with the
reproduction's own filter. The result is cached as float32 .npy (gitignored), so each file is decoded once.

Narrowband SNR, as in the synthetic generator: a whistle's level in its own 93.75 Hz bin (at its mean frequency)
is the target SNR above the median noise level in that bin.

through_channel() plays a whole message into the noise with one gain, as a real source would. [DECISION] Its SNR is the
median over the pitches a data whistle can have, so individual whistles sit a little above or below the target wherever the
noise spectrum is uneven.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
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


@dataclass(frozen=True)
class Received:
    audio: np.ndarray           # float32, the message inside real noise
    fs: int
    snr_db: float
    gain: float                 # applied to the transmitted WAV
    offset_s: float             # where the WAV starts in the recording
    encounter: int
    noise_files: list


def noise_stretch(encounter: int, n: int, rng: np.random.Generator, cfg: dict | None = None, pcfg=None) -> tuple[np.ndarray, list]:
    """n samples of consecutive noise from a random place in an encounter."""
    cfg = cfg or default_config()
    files = noise_files(encounter)
    i = int(rng.integers(len(files)))
    parts, used, total = [], [], 0
    while total < n:
        path = files[i % len(files)]
        i += 1
        parts.append(load_noise(path, cfg, pcfg))
        used.append(path.name)
        total += len(parts[-1])
    x = np.concatenate(parts)
    s0 = int(rng.integers(0, len(x) - n + 1))
    return x[s0:s0 + n].astype(np.float64), used


def through_channel(audio: np.ndarray, fs: int, snr_db: float, pitches_hz: np.ndarray, encounter: int | None = None, seed: int = 0,
                    cfg: dict | None = None, pcfg=None) -> Received:
    """Play a format v2 WAV into real noise. pitches_hz: the pitches the SNR refers to (the sender's pitch pool)."""
    cfg = cfg or default_config()
    c = cfg["channel"]
    encounter = int(c["noise_encounter"] if encounter is None else encounter)
    if encounter == int(cfg["synth"]["fc_source_encounter"]):
        raise ValueError(f"encounter {encounter} trained the VAE, so it is never used as noise")
    if int(fs) != int(cfg["synth"]["fs_hz"]):
        raise ValueError(f"the channel works at {cfg['synth']['fs_hz']} Hz, got {fs} Hz")
    rng = np.random.default_rng(int(seed))
    pad = int(round(float(c["pad_s"]) * fs))
    x, used = noise_stretch(encounter, len(audio) + 2 * pad, rng, cfg, pcfg)
    levels = bin_levels(x[:int(float(c["level_window_s"]) * fs)], fs, float(c["snr_bin_hz"]))
    want = np.median([amplitude_for_snr(snr_db, float(f), levels, fs, cfg) for f in np.quantile(pitches_hz, np.linspace(0.02, 0.98, 25))])
    reference = float(cfg["realism"]["median_level_db"]) if cfg["realism"]["enabled"] else 0.0   # the quietest data whistle
    gain = float(want) / (float(cfg["sender"]["data_amplitude"]) * 10 ** (reference / 20))
    s0 = int(rng.integers(0, 2 * pad + 1))
    x[s0:s0 + len(audio)] += gain * np.asarray(audio, dtype=np.float64)
    return Received(x.astype(np.float32), int(fs), float(snr_db), gain, s0 / fs, encounter, used)
