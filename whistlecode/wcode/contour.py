"""Whistle contours as WhistleCode compares them: frequency offset from the contour's own mid-range, one value per
5.333 ms frame (one S4 frame = one image column).

Measuring offsets from the mid-range makes a contour independent of its pitch: the transmitter places a type at
centre frequency fc (its mid-range is then fc), and the receiver compares shapes whatever fc was.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import repro


@dataclass(frozen=True)
class Contour:
    offset_hz: np.ndarray       # one value per frame, mid-range = 0
    hop_s: float

    def __post_init__(self):
        if len(self.offset_hz) < 1:
            raise ValueError("a contour needs at least one frame")

    @property
    def n_frames(self) -> int:
        return len(self.offset_hz)

    @property
    def duration_ms(self) -> float:
        return self.n_frames * self.hop_s * 1000.0

    @property
    def span_hz(self) -> float:
        return float(self.offset_hz.max() - self.offset_hz.min())


def centred(freq_hz) -> np.ndarray:
    f = np.asarray(freq_hz, dtype=np.float64)
    return f - 0.5 * (f.max() + f.min())


def image_hop_s(pcfg) -> float:
    return float(repro.sonify.grid(pcfg)["hop_s"])


def from_image(img: np.ndarray, pcfg, threshold: float = 0.05) -> tuple[Contour | None, int]:
    """128 x 128 image -> (centred contour, longest run of empty columns inside it), or (None, 0) when empty."""
    c = repro.sonify.image_contour(img, pcfg, threshold)
    if c is None:
        return None, 0
    active = np.where(np.asarray(img).max(axis=0) > threshold)[0]
    gap = int((np.diff(active) - 1).max()) if len(active) > 1 else 0
    return Contour(centred(c.offset_hz), float(c.hop_s)), gap


def from_track(freq_hz, hop_s: float) -> Contour:
    """A detected track (absolute Hz per frame) -> centred contour."""
    return Contour(centred(freq_hz), float(hop_s))
