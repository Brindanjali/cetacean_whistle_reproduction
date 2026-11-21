"""Message -> WAV in format v2 (PLAN.md section 4.6).

Every whistle of the walked bank stretches is played at its real time:

- data whistles: one of the 16 shapes at its own length, at the pitch chosen by the symbol's two low bits;
- preamble whistles: the signature shape at the pitch the key gives;
- cover whistles: the real contour at its real pitch. A cover whistle that would collide with a data whistle moves to another
  pitch and keeps its time and length.

With the realism library (realism.py), data whistles take the shape of a real whistle of their type, every whistle has a recorded
voice and belongs to one of a few virtual animals, and the clicks recorded during the walked stretches are played at their real
times. No sea background is ever added: the file is silent between sounds.

All the randomness comes from the key and nonce, so the same message, key and nonce always give the same audio.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import bank, format2, keys, layout, realism, synth, transmitter
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
    n_real_shapes: int = 0          # data whistles with the shape of a real whistle
    n_clicks: int = 0               # recorded clicks played

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
                "n_real_shapes": self.n_real_shapes, "n_clicks": self.n_clicks,
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

    def __init__(self, cfg: dict | None = None, codebook_path=None, check_model: bool = True, rhythm_bank: bank.Bank | None = None,
                 library: realism.Library | None = None):
        super().__init__(cfg, codebook_path, check_model)
        self.bank = rhythm_bank if rhythm_bank is not None else bank.load(self.cfg)
        wanted = bool(self.cfg["realism"]["enabled"]) and codebook_path is None      # a test codebook has no library of its own
        self.library = library if library is not None else (realism.load(self.cfg, self.codebook_sha256) if wanted else None)

    def _real_shapes(self, idx: np.ndarray, tau: float, rng: np.random.Generator):
        """One shape per slot: a real whistle of the type, not repeated until the type's real whistles run out."""
        n = len(idx)
        real = np.array([len(self.library.shapes[int(i)]) > 0 for i in idx])
        out: list = [None] * n
        redraws, fell = np.zeros(n, dtype=np.int64), np.zeros(n, dtype=bool)
        if (~real).any():
            drawn, r, f = self._shapes(idx[~real], tau, rng)
            for p, c, a, b in zip(np.where(~real)[0], drawn, r, f):
                out[int(p)], redraws[p], fell[p] = c, a, b
        decks: dict[int, list] = {}
        for p in np.where(real)[0]:
            t = int(idx[p])
            if not decks.get(t):
                decks[t] = rng.permutation(len(self.library.shapes[t])).tolist()
            out[int(p)] = self.library.shapes[t][decks[t].pop()]
        return out, redraws, fell, int(real.sum())

    def _render_real(self, x: np.ndarray, data: list, covers: list, segments: list, lead: float, rng: np.random.Generator) -> tuple:
        """Data and cover whistles with recorded voices and virtual animals, then the recorded clicks."""
        cfg, lib = self.cfg, self.library
        fs, amp = int(cfg["synth"]["fs_hz"]), float(cfg["sender"]["data_amplitude"])
        fade = float(cfg["realism"]["edge_fade_ms"])
        steady = np.flatnonzero(lib.steady)
        if not len(steady):
            raise realism.RealismError("the realism library has no steady voices for data whistles")
        d_on = np.array([d.slot.start_s for d in data])
        d_off = d_on + np.array([d.contour.n_frames * d.contour.hop_s for d in data])
        d_fc = np.array([d.fc_hz for d in data])
        events = sorted([(d.slot.start_s, 0, i) for i, d in enumerate(data)] + [(c.start_s, 1, i) for i, c in enumerate(covers)])
        animals = realism.group_of_animals(len(events), rng, cfg)
        counts = [0, 0, 0]
        for (_, kind, i), who in zip(events, animals):
            level = amp * 10 ** ((realism.data_level_db(who.level_db, cfg) if kind == 0 else who.level_db) / 20)
            if kind == 0:
                d, v = data[i], int(steady[int(rng.integers(len(steady)))])
                contour, fc, start = d.contour, d.fc_hz, d.slot.start_s
            else:
                cv, v = covers[i], int(rng.integers(len(lib.env_db)))
                f = self.bank.contour_hz(cv.bank_index)
                fc, state = self._cover_pitch(f, cv.start_s, cv.start_s + len(f) * self.bank.hop_s, d_on, d_off, d_fc, rng)
                counts[state] += 1
                contour, start = Contour(centred(f), self.bank.hop_s), cv.start_s
            w = synth.voiced_whistle(contour, fc, lib.env_db[v], lib.h2_db[v], lib.h3_db[v], who.tone_db, fade, fs)
            _add(x, lead + start, level * w, fs)
        order = np.argsort(d_on)
        played = realism.clicks_for(lib, segments, d_on[order], np.maximum.accumulate(d_off[order]),
                                    float(cfg["realism"]["click_guard_ms"]) / 1000)
        top = float(cfg["realism"]["click_peak_max"])
        for t, i in played:
            w = lib.click_wave[i].astype(np.float64) * lib.click_gain
            _add(x, lead + t, w * min(1.0, top / max(float(np.abs(w).max()), 1e-12)), fs)
        return counts, len(played)

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
        real_voices = self.library is not None and tau > 0
        n_real = 0
        if real_voices and bool(cfg["realism"]["real_shapes"]):
            shapes, redraws, fell, n_real = self._real_shapes(idx, tau, rng)
        else:
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
        covers = head.covers + pay.covers
        if real_voices:
            counts, n_clicks = self._render_real(x, data, covers, [*head.segments, *pay.segments], lead, rng)
            return Transmission(x.astype(np.float32), fs, fr, data, len(covers), counts[1], counts[2], lead, tau,
                                self.codebook_sha256, self.bank.sha256, n_real, n_clicks)
        for d in data:
            _add(x, lead + d.slot.start_s, amp * synth.whistle(d.contour, d.fc_hz, rng, cfg, fs), fs)

        extra_lo, extra_hi = cfg["sender"]["cover_extra_db"]
        counts = [0, 0, 0]
        for cv in covers:
            f = self.bank.contour_hz(cv.bank_index)
            t_off = cv.start_s + len(f) * self.bank.hop_s
            mid, state = self._cover_pitch(f, cv.start_s, t_off, d_on, d_off, d_fc, rng)
            counts[state] += 1
            level = amp * 10 ** (float(rng.uniform(float(extra_lo), float(extra_hi))) / 20)
            _add(x, lead + cv.start_s, level * synth.cover_whistle(Contour(centred(f), self.bank.hop_s), mid, rng, cfg, fs), fs)
        return Transmission(x.astype(np.float32), fs, fr, data, len(covers), counts[1], counts[2], lead, tau,
                            self.codebook_sha256, self.bank.sha256)
