"""The simulated sea between the sender and the hydrophone (PLAN.md section 6): echoes, absorption and Doppler.

Echoes and absorption are one linear filter. The image method gives four paths (direct, off the surface, off the bottom, and off
the surface and then the bottom). Each path's amplitude falls as 1 / length, loses Thorp's frequency-dependent absorption over its
own length, and arrives after its own delay. The filter is applied in the frequency domain, so delays need not be whole samples.

Doppler is one time-scaling of the whole recording: y(t) = x(s t) with s = 1 + v / c. A closing source (v > 0) raises every pitch
and brings every later whistle in earlier, by v / c of the time elapsed.

The direct path keeps gain 1 at the reference pitch, so the SNR set by the channel always means the level of the direct path at
the hydrophone, whatever the range. Range changes the echoes and the tone of the sound, not how loud the direct path is.

What this model leaves out: a moving sea surface (echoes here are steady), different Doppler on different paths, and sound-speed
layers that bend the paths.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

import numpy as np
from scipy import fft as sfft
from scipy import signal

from .config import default_config


@dataclass(frozen=True)
class Sea:
    range_m: float                  # horizontal distance from the source to the hydrophone
    water_depth_m: float
    source_depth_m: float
    receiver_depth_m: float
    speed_mps: float = 0.0          # how fast the two close on each other; negative = moving apart
    echoes: bool = True             # False = no echoes and no absorption (Doppler alone)

    def __post_init__(self) -> None:
        if self.range_m <= 0:
            raise ValueError(f"range must be positive, got {self.range_m} m")
        for name, z in (("source", self.source_depth_m), ("receiver", self.receiver_depth_m)):
            if not 0 < z < self.water_depth_m:
                raise ValueError(f"the {name} depth {z} m must lie inside the {self.water_depth_m} m water column")


def draw(rng: np.random.Generator, cfg: dict | None = None) -> Sea:
    """One random sea within the ranges of config.toml."""
    c = (cfg or default_config())["sea"]
    lo, hi = (float(v) for v in c["water_depth_m"])
    return Sea(range_m=1000.0 * float(rng.choice(np.asarray(c["ranges_km"], dtype=np.float64))),
               water_depth_m=float(np.exp(rng.uniform(np.log(lo), np.log(hi)))),
               source_depth_m=float(rng.uniform(*c["source_depth_m"])),
               receiver_depth_m=float(rng.uniform(*c["receiver_depth_m"])),
               speed_mps=float(rng.uniform(-float(c["max_speed_mps"]), float(c["max_speed_mps"]))))


def thorp_db_per_km(freq_hz) -> np.ndarray:
    """Thorp's absorption of sound in sea water."""
    f2 = (np.asarray(freq_hz, dtype=np.float64) / 1000.0) ** 2
    return 0.11 * f2 / (1.0 + f2) + 44.0 * f2 / (4100.0 + f2) + 2.75e-4 * f2 + 0.003


def paths(s: Sea, cfg: dict | None = None) -> tuple[np.ndarray, np.ndarray]:
    """(length in m, reflection gain) of the direct, surface, bottom and surface-bottom paths."""
    c = (cfg or default_config())["sea"]
    top, floor = float(c["surface_reflection"]), float(c["bottom_reflection"])
    zs, zr, d = s.source_depth_m, s.receiver_depth_m, s.water_depth_m
    depth_change = np.array([zr - zs, zr + zs, 2 * d - zs - zr, 2 * d + zs - zr], dtype=np.float64)
    return np.hypot(s.range_m, depth_change), np.array([1.0, top, floor, top * floor], dtype=np.float64)


def response(freq_hz, s: Sea, ref_hz: float, cfg: dict | None = None) -> np.ndarray:
    """Complex gain of echoes and absorption. The direct path has zero delay, and gain 1 at ref_hz."""
    cfg = cfg or default_config()
    freq = np.asarray(freq_hz, dtype=np.float64)
    length, reflect = paths(s, cfg)
    speed = float(cfg["sea"]["sound_speed_mps"])
    loss_db_per_m = thorp_db_per_km(freq) / 1000.0
    h = np.zeros(freq.shape, dtype=np.complex128)
    for path_m, r in zip(length, reflect):
        if r != 0.0:
            h += r * (length[0] / path_m) * 10 ** (-loss_db_per_m * path_m / 20) * np.exp(-2j * np.pi * freq * (path_m - length[0]) / speed)
    return h * 10 ** (float(thorp_db_per_km(ref_hz)) * length[0] / 1000.0 / 20)


def _through_paths(x: np.ndarray, fs: int, s: Sea, ref_hz: float, cfg: dict) -> np.ndarray:
    length, _ = paths(s, cfg)
    latest = float(length.max() - length[0]) / float(cfg["sea"]["sound_speed_mps"])
    n_out = len(x) + int(np.ceil((latest + float(cfg["sea"]["tail_guard_s"])) * fs))
    n_fft = sfft.next_fast_len(n_out, real=True)
    spectrum = sfft.rfft(x, n_fft, workers=-1)
    spectrum *= response(sfft.rfftfreq(n_fft, 1.0 / fs), s, ref_hz, cfg)
    return sfft.irfft(spectrum, n_fft, workers=-1)[:n_out]


def time_scale(speed_mps: float, cfg: dict | None = None) -> Fraction:
    """s = 1 + v / c as an exact ratio, close enough that a long message drifts by far less than one sample."""
    c = (cfg or default_config())["sea"]
    return Fraction(1.0 + float(speed_mps) / float(c["sound_speed_mps"])).limit_denominator(int(c["doppler_max_denominator"]))


def _doppler(x: np.ndarray, speed_mps: float, cfg: dict) -> np.ndarray:
    s = time_scale(speed_mps, cfg)
    if s == 1:
        return x
    return signal.resample_poly(x, s.denominator, s.numerator, window=("kaiser", float(cfg["sea"]["doppler_kaiser_beta"])))


def propagate(audio: np.ndarray, fs: int, s: Sea, ref_hz: float, cfg: dict | None = None) -> np.ndarray:
    """What reaches the hydrophone before the ocean noise is added: echoes and absorption, then Doppler."""
    cfg = cfg or default_config()
    x = np.asarray(audio, dtype=np.float64)
    if s.echoes:
        x = _through_paths(x, int(fs), s, float(ref_hz), cfg)
    return _doppler(x, s.speed_mps, cfg)
