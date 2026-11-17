"""Receiver steps 1 and 4 (PLAN.md section 7): detect whistle tracks with the reproduction's own chain, and match
them to expected slots.

Detection runs S2-S7 of the reproduction (resample to 192 kHz, 2 kHz high-pass, STFT, ridgenet-v2c, tracker,
whistle vectors) exactly as the dataset was built, without the S8/S9 images (classifier B adds those in P4).
Every track is kept, including the ones S8 would reject as too long or too wide.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import model, repro
from .config import PROJECT_ROOT, default_config
from .contour import Contour, from_track


@dataclass(frozen=True)
class Track:
    start_s: float              # start of the track's first STFT frame
    freq_hz: np.ndarray         # absolute frequency per frame
    hop_s: float

    @property
    def centre_hz(self) -> float:
        return 0.5 * float(self.freq_hz.max() + self.freq_hz.min())

    @property
    def duration_ms(self) -> float:
        return len(self.freq_hz) * self.hop_s * 1000.0

    def contour(self, fc_hz: float | None = None) -> Contour:
        """Offsets from fc_hz (the slot's expected centre frequency, classifier A's input), or from the track's own
        mid-range when no fc is given."""
        if fc_hz is None:
            return from_track(self.freq_hz, self.hop_s)
        return Contour(self.freq_hz - float(fc_hz), self.hop_s)


class Detector:
    def __init__(self, cfg: dict | None = None, dev=None):
        self.cfg = cfg or default_config()
        self.pcfg = repro.load_pipeline_config()
        ck = PROJECT_ROOT / self.pcfg["decisions"]["s5"]["checkpoint"]
        self.det = repro.RidgeDetector.from_checkpoint(ck, self.pcfg, str(dev or model.device(self.cfg)))

    def tracks(self, x: np.ndarray, fs: float) -> list[Track]:
        d, p = repro.dsp, self.pcfg
        sig = repro.AudioSignal(np.asarray(x, dtype=np.float32), float(fs), "whistlecode", {})
        s4 = d.s4_stft(d.s3_highpass(d.s2_resample(sig, p), p), p)
        vectors = repro.s7_vectors(repro.run_s6(self.det.predict(s4), p).tracks, p)
        return [Track(v.start_frame * s4.hop_s, np.asarray(v.freq_hz, dtype=np.float64), float(s4.hop_s)) for v in vectors]


def match(tracks: list[Track], starts_s, centres_hz, cfg: dict | None = None) -> list[Track | None]:
    """For each expected (start, centre): the track starting between slot_early_ms before and slot_late_ms after it,
    with its centre within pitch_window_hz; the closest start wins, ties go to the longer track. None = not found."""
    c = (cfg or default_config())["detect"]
    early, late, pw = float(c["slot_early_ms"]) / 1000, float(c["slot_late_ms"]) / 1000, float(c["pitch_window_hz"])
    if not tracks:
        return [None] * len(starts_s)
    t0 = np.array([t.start_s for t in tracks])
    fc = np.array([t.centre_hz for t in tracks])
    n = np.array([len(t.freq_hz) for t in tracks])
    out = []
    for s, f in zip(starts_s, centres_hz):
        ok = np.where((t0 >= s - early) & (t0 <= s + late) & (np.abs(fc - f) <= pw))[0]
        if len(ok) == 0:
            out.append(None)
            continue
        best = min(ok, key=lambda i: (abs(t0[i] - s), -n[i]))
        out.append(tracks[best])
    return out
