"""Audio -> message in format v2 (PLAN.md section 4.6).

1. Detect whistle tracks with the reproduction's detector and tracker.
2. Find the frame. The key gives the time and pitch of every whistle of the preamble and header stretch, so each pair of a
   detected track and a known whistle at a similar pitch votes for one frame start. The true start collects many votes, while
   unrelated whistles spread theirs thinly.
3. Read the 7 header slots and repair them, which gives the mode, length and nonce.
4. Rebuild the payload slots from the key and nonce, read them, repair them, unscramble and check the CRC.

Reading a slot: take the track starting nearest the slot's time within -60/+150 ms and within 500 Hz of a candidate pitch. The
nearest candidate gives the two pitch bits and classifier A gives the four shape bits. A missing track or an ambiguous shape is
marked as lost, which costs Reed-Solomon half as much as a wrong symbol.

Several frame starts are tried, best first. Only a message that passes its CRC is returned.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from . import bank, classify, codebook, detect, format2, layout, schedule
from .config import default_config
from .framing import DecodeError, FramingError

STAGES = ("sync", "header", "payload", "done")      # how far an attempt got


@dataclass(frozen=True)
class SlotReadout:
    symbols: np.ndarray             # 0-63, or ERASED
    n_missed: int                   # no track found
    n_doubtful: int                 # track found, shape ambiguous
    doubt: np.ndarray               # closest / second-closest shape distance of each read whistle (higher = less sure)


@dataclass(frozen=True)
class Reception:
    ok: bool
    stage: str                      # the stage the best attempt reached
    detail: str
    payload: bytes | None = None
    text: str | None = None
    mode: int | None = None
    nonce: int | None = None
    offset_s: float | None = None   # where the frame's first whistle was found
    sync_votes: float = 0.0
    attempts: int = 0
    n_tracks: int = 0
    header: SlotReadout | None = None
    body: SlotReadout | None = None
    n_repaired_wrong: int = 0
    n_repaired_lost: int = 0


class TrackSet:
    """Detected tracks as arrays, for fast lookups."""

    def __init__(self, tracks: list):
        self.tracks = tracks
        self.t0 = np.array([t.start_s for t in tracks], dtype=np.float64)
        self.fc = np.array([t.centre_hz for t in tracks], dtype=np.float64)
        self.n = np.array([len(t.freq_hz) for t in tracks], dtype=np.int64)


class Receiver:
    def __init__(self, cfg: dict | None = None, codebook_path=None, check_model: bool = True, rhythm_bank: bank.Bank | None = None,
                 detector: detect.Detector | None = None):
        self.cfg = cfg or default_config()
        self.cb = codebook.load(self.cfg, Path(codebook_path) if codebook_path else codebook.out_dir(self.cfg), check=check_model)
        self.templates = [t.contour for t in self.cb.types]
        self.bank = rhythm_bank if rhythm_bank is not None else bank.load(self.cfg)
        self.pool = schedule.pitch_pool(self.cfg)
        self._detector = detector

    @property
    def detector(self) -> detect.Detector:
        if self._detector is None:
            self._detector = detect.Detector(self.cfg)
        return self._detector

    # ------------------------------------------------------------------------------------------ finding the frame
    def _known_whistles(self, head: layout.Layout) -> list[tuple[float, np.ndarray, float]]:
        """(time, possible pitches, vote weight) of every whistle whose place the key gives."""
        w = float(self.cfg["receiver"]["sync_preamble_weight"])
        out = [(s.start_s, np.array(s.candidates_hz), w if s.part == layout.PREAMBLE else 1.0) for s in head.slots]
        for c in head.covers:
            f = self.bank.contour_hz(c.bank_index)
            out.append((c.start_s, np.array([0.5 * (f.max() + f.min())]), 1.0))
        return out

    def find_frame(self, tr: TrackSet, head: layout.Layout) -> list[tuple[float, float]]:
        """Candidate frame starts as (time, votes), best first."""
        r = self.cfg["receiver"]
        pw, step, tol = float(r["pitch_window_hz"]), float(r["sync_bin_s"]), float(r["sync_tolerance_s"])
        if not len(tr.t0):
            return []
        known = self._known_whistles(head)
        times, weights = [], []
        for t, pitches, w in known:
            near = np.abs(tr.fc[:, None] - pitches[None, :]).min(axis=1) <= pw
            times.append(tr.t0[near] - t)
            weights.append(np.full(int(near.sum()), w))
        votes_at = np.concatenate(times)
        vote_w = np.concatenate(weights)
        if not len(votes_at):
            return []
        lo = float(votes_at.min())
        bins = ((votes_at - lo) / step).astype(np.int64)
        hist = np.bincount(bins, vote_w, int(bins.max()) + 1)
        smooth = np.convolve(hist, np.ones(3), "same")
        guard = max(1, int(round(0.1 / step)))
        out = []
        for _ in range(int(r["sync_candidates"]) * 3):
            j = int(np.argmax(smooth))
            if smooth[j] <= 0:
                break
            out.append(self._refine(tr, known, lo + (j + 0.5) * step, pw, tol))
            smooth[max(0, j - guard):j + guard + 1] = 0.0
        out.sort(key=lambda c: -c[1])
        return out[:int(r["sync_candidates"])]

    @staticmethod
    def _refine(tr: TrackSet, known, start: float, pw: float, tol: float) -> tuple[float, float]:
        """Move a candidate start to the median of its matches, and count the votes that really match."""
        residuals, votes = [], 0.0
        for t, pitches, w in known:
            dt = tr.t0 - (start + t)
            ok = np.where((np.abs(dt) <= tol) & (np.abs(tr.fc[:, None] - pitches[None, :]).min(axis=1) <= pw))[0]
            if len(ok):
                residuals.append(float(dt[ok[np.argmin(np.abs(dt[ok]))]]))
                votes += w
        return (start + float(np.median(residuals)) if residuals else start), votes

    # ------------------------------------------------------------------------------------------ reading slots
    def read_slots(self, tr: TrackSet, slots: list, start_s: float) -> SlotReadout:
        c = self.cfg["detect"]
        early, late = float(c["slot_early_ms"]) / 1000, float(c["slot_late_ms"]) / 1000
        pw = float(self.cfg["receiver"]["pitch_window_hz"])
        by_shape = self.cfg["receiver"]["track_choice"] == "best_shape"
        symbols = np.full(len(slots), format2.ERASED, dtype=np.int64)
        doubt = np.zeros(len(slots))
        queries, rows = [], []
        for i, s in enumerate(slots):
            t = start_s + s.start_s
            cand = np.asarray(s.candidates_hz)
            near = np.where((tr.t0 >= t - early) & (tr.t0 <= t + late))[0]
            if not len(near):
                continue
            for k in near[np.abs(tr.fc[near, None] - cand[None, :]).min(axis=1) <= pw]:
                band = int(np.argmin(np.abs(tr.fc[k] - cand)))
                queries.append(tr.tracks[int(k)].contour(float(cand[band])))
                rows.append((i, band, int(k), abs(float(tr.t0[k]) - t)))
        if not queries:
            return SlotReadout(symbols, len(slots), 0, doubt)
        dist = classify.distances(queries, self.templates, self.cfg)
        best, ambiguous = classify.decide(dist, float(self.cfg["classify"]["ambiguity_ratio"]))
        closest = np.sort(dist, axis=1)
        ratio = closest[:, 0] / np.maximum(closest[:, 1], 1e-9)
        chosen: dict[int, tuple] = {}
        for r, (i, _, k, dt) in enumerate(rows):
            rank = (float(closest[r, 0]), dt) if by_shape else (dt, -int(tr.n[k]))
            if i not in chosen or rank < chosen[i][0]:
                chosen[i] = (rank, r)
        n_doubtful = 0
        for i, (_, r) in chosen.items():
            if ambiguous[r]:
                n_doubtful += 1
            else:
                symbols[i] = (int(best[r]) << 2) | rows[r][1]
                doubt[i] = float(ratio[r])
        return SlotReadout(symbols, len(slots) - len(chosen), n_doubtful, doubt)

    # ------------------------------------------------------------------------------------------ one frame start
    def _attempt(self, tr: TrackSet, head: layout.Layout, start_s: float, votes: float, key: str) -> Reception:
        common = {"offset_s": start_s, "sync_votes": votes, "n_tracks": len(tr.tracks)}
        r = self.cfg["receiver"]
        soft = bool(r["soft_repair"])
        hdr = self.read_slots(tr, [s for s in head.slots if s.part == layout.HEADER], start_s)
        try:
            readings = format2.header_candidates(hdr.symbols, key, self.cfg, hdr.doubt if soft else None)
        except DecodeError as e:
            return Reception(False, "header", str(e), header=hdr, **common)
        failed = None
        for h in readings[:int(r["max_header_readings"])]:
            n = format2.payload_symbols(h.mode, h.length, self.cfg)
            pay = layout.payload_layout(key, h.nonce, n, head, self.bank, self.pool, self.cfg)
            body = self.read_slots(tr, pay.slots, start_s)
            try:
                m = format2.decode_payload(body.symbols, h, key, self.cfg, body.doubt if soft else None)
            except (DecodeError, FramingError) as e:
                failed = failed or Reception(False, "payload", str(e), mode=h.mode, nonce=h.nonce, header=hdr, body=body, **common)
                continue
            return Reception(True, "done", "", m.payload, m.text, m.mode, m.nonce, header=hdr, body=body,
                             n_repaired_wrong=h.n_errors + m.n_errors, n_repaired_lost=h.n_erasures + m.n_erasures, **common)
        return failed

    def decode_tracks(self, tracks: list, key: str) -> Reception:
        tr = TrackSet(tracks)
        head = layout.header_layout(key, self.bank, self.pool, self.cfg)
        found = self.find_frame(tr, head)
        if not found:
            return Reception(False, "sync", "no whistles match the key's timing", n_tracks=len(tracks))
        best = None
        for i, (start, votes) in enumerate(found):
            got = self._attempt(tr, head, start, votes, key)
            if got.ok:
                return Reception(**{**got.__dict__, "attempts": i + 1})
            if best is None or STAGES.index(got.stage) > STAGES.index(best.stage):
                best = got
        return Reception(**{**best.__dict__, "attempts": len(found)})

    def receive(self, audio: np.ndarray, fs: float, key: str) -> Reception:
        return self.decode_tracks(self.detector.tracks(np.asarray(audio, dtype=np.float32), fs), key)

    def receive_file(self, path: str | Path, key: str) -> Reception:
        x, fs = sf.read(str(path), dtype="float32", always_2d=True)
        return self.receive(x[:, 0], fs, key)
