"""Message -> WAV in format v2 (PLAN.md section 4.6).

Every whistle of the walked bank stretches is played at its real time:

- data whistles: one of the 16 shapes at its own length, at the pitch chosen by the symbol's two low bits;
- preamble whistles: the signature shape at the pitch the key gives;
- cover whistles: the real contour at its real pitch. A cover whistle that would collide with a data whistle moves to another
  pitch and keeps its time and length.

All the randomness comes from the key and nonce, so the same message, key and nonce always give the same audio.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import bank, format2, keys, layout, synth, transmitter
from .config import default_config
from .contour import Contour, centred
from .transmitter import SIGNATURE, write_wav  # noqa: F401  (write_wav is part of this module's interface)


@dataclass(frozen=True)
class SentData:
    slot: layout.Slot
    symbol: int                     # 0-63, or -1 for a preamble whistle
    type_index: int                 # 0-15 = shape, 16 = signature
    band: int                       # which candidate pitch
    fc_hz: float
    contour: Contour
    redraws: int
    fell_back: bool


@dataclass(frozen=True)
class Transmission:
    audio: np.ndarray               # float32, mono
    fs: int
    frame: format2.Frame
    data: list                      # SentData, in time order
    n_cover: int
    n_cover_moved: int
    n_cover_stuck: int              # collided, and no free pitch was found
    lead_in_s: float
    tau: float
    codebook_sha256: str
    bank_sha256: str

    @property
    def duration_s(self) -> float:
        return len(self.audio) / self.fs

    @property
    def n_fell_back(self) -> int:
        return sum(d.fell_back for d in self.data)

    @property
    def n_redrawn(self) -> int:
        return sum(d.redraws > 0 for d in self.data)

    def manifest(self) -> dict:
        """What was sent, for debugging and evaluation. It holds neither the key nor the message text."""
        return {"format": 2, "fs_hz": self.fs, "duration_s": round(self.duration_s, 4), "lead_in_s": self.lead_in_s, "tau": self.tau,
                "nonce": self.frame.nonce, "mode": self.frame.mode, "length": self.frame.length,
                "codebook_sha256": self.codebook_sha256, "bank_sha256": self.bank_sha256,
                "n_data_whistles": len(self.data), "n_cover_whistles": self.n_cover, "n_cover_moved": self.n_cover_moved,
                "n_cover_stuck": self.n_cover_stuck, "n_redrawn": self.n_redrawn, "n_fell_back": self.n_fell_back,
                "whistles": [{"index": d.slot.index, "part": d.slot.part, "start_s": round(d.slot.start_s, 6), "fc_hz": round(d.fc_hz, 2),
                              "symbol": d.symbol, "type": "signature" if d.type_index == SIGNATURE else d.type_index, "band": d.band,
                              "duration_ms": round(d.contour.duration_ms, 2), "redraws": d.redraws, "fell_back": d.fell_back}
                             for d in self.data]}


def _add(x: np.ndarray, start_s: float, w: np.ndarray, fs: float) -> None:
    s0 = int(round(start_s * fs))
    n = min(len(w), len(x) - s0)
    if n > 0:
        x[s0:s0 + n] += w[:n]


class Sender(transmitter.Transmitter):
    """Uses the v1 transmitter's codebook loading and shape drawing, with the format v2 frame and the rhythm bank."""

    def __init__(self, cfg: dict | None = None, codebook_path=None, check_model: bool = True, rhythm_bank: bank.Bank | None = None):
        super().__init__(cfg, codebook_path, check_model)
        self.bank = rhythm_bank if rhythm_bank is not None else bank.load(self.cfg)

    def _cover_pitch(self, f: np.ndarray, t_on: float, t_off: float, data_on, data_off, data_fc, rng) -> tuple[float, int]:
        """(mid-range pitch of a cover whistle, 0 = stays, 1 = moved, 2 = collides and could not move)."""
        c = self.cfg["sender"]
        lo, hi, mid, span = float(f.min()), float(f.max()), 0.5 * float(f.min() + f.max()), float(f.max() - f.min())
        over = (t_on < data_off + float(c["follow_s"])) & (t_off > data_on)
        hits = data_fc[over]
        near = float(c["collision_hz"])
        if not np.any((hits > lo - near) & (hits < hi + near)):
            return mid, 0
        p_lo, p_hi = c["cover_pitch_range_hz"]
        a, b = float(p_lo) + span / 2, float(p_hi) - span / 2
        clear = span / 2 + float(c["cover_move_clearance_hz"])
        if a < b:
            for _ in range(int(c["cover_move_tries"])):
                m = float(rng.uniform(a, b))
                if np.all(np.abs(m - hits) >= clear):
                    return m, 1
        return mid, 2

    def send(self, message: bytes | str, key: str, nonce: int | None = None, tau: float | None = None) -> Transmission:
        cfg = self.cfg
        tau = float(cfg["transmit"]["tau"] if tau is None else tau)
        if tau < 0:
            raise ValueError("tau must be >= 0")
        fr = format2.encode(message, key, nonce, cfg)
        head, pay = layout.frame_layout(fr, key, self.bank, self.pool, cfg)
        slots = head.slots + pay.slots
        n_pre = int(cfg["framing"]["n_preamble"])
        symbols = np.concatenate([np.full(n_pre, -1, dtype=np.int64), fr.symbols])
        idx = np.where(symbols < 0, SIGNATURE, symbols >> 2)
        bands = np.where(symbols < 0, 0, symbols & 3)
        rng = keys.stream(keys.PAYLOAD, "variation", key, fr.nonce, cfg)
        shapes, redraws, fell = self._shapes(idx, tau, rng)
        data = [SentData(s, int(y), int(i), int(b), float(s.candidates_hz[int(b)]), c, int(r), bool(f))
                for s, y, i, b, c, r, f in zip(slots, symbols, idx, bands, shapes, redraws, fell)]

        fs = int(cfg["synth"]["fs_hz"])
        lead, tail = float(cfg["transmit"]["lead_in_s"]), float(cfg["transmit"]["tail_s"])
        amp = float(cfg["sender"]["data_amplitude"])
        d_on = np.array([d.slot.start_s for d in data])
        d_off = d_on + np.array([d.contour.n_frames * d.contour.hop_s for d in data])
        d_fc = np.array([d.fc_hz for d in data])
        end_s = max(pay.end_s, float(d_off.max()))
        x = np.zeros(int(np.ceil((lead + end_s + tail) * fs)))
        for d in data:
            _add(x, lead + d.slot.start_s, amp * synth.whistle(d.contour, d.fc_hz, rng, cfg, fs), fs)

        extra_lo, extra_hi = cfg["sender"]["cover_extra_db"]
        counts = [0, 0, 0]
        covers = head.covers + pay.covers
        for cv in covers:
            f = self.bank.contour_hz(cv.bank_index)
            t_off = cv.start_s + len(f) * self.bank.hop_s
            mid, state = self._cover_pitch(f, cv.start_s, t_off, d_on, d_off, d_fc, rng)
            counts[state] += 1
            level = amp * 10 ** (float(rng.uniform(float(extra_lo), float(extra_hi))) / 20)
            _add(x, lead + cv.start_s, level * synth.cover_whistle(Contour(centred(f), self.bank.hop_s), mid, rng, cfg, fs), fs)
        return Transmission(x.astype(np.float32), fs, fr, data, len(covers), counts[1], counts[2], lead, tau,
                            self.codebook_sha256, self.bank.sha256)
