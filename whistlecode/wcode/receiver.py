"""Audio -> message in format v2 (PLAN.md section 4.6).

1. Detect whistle tracks with the reproduction's detector and tracker.
2. Find the frame. The key gives the time and pitch of every whistle of the preamble and header stretch, so each pair of a
   detected track and a known whistle at a similar pitch votes for one frame start. The true start collects many votes, while
   unrelated whistles spread theirs thinly.
3. Read the 7 header slots and repair them, which gives the mode, length and nonce.
4. Rebuild the payload slots from the key and nonce, read them, repair them, unscramble and check the CRC.

Reading a slot: the key gives the moment a whistle starts, and each shape has its own length, so each of the 16 shapes is compared
with only the part of a track where that shape would sound. The detector often joins a little of the sound before or after a
whistle onto its track, and those frames are ignored. The nearest candidate pitch to that part gives the two pitch bits, and the
closest shape gives the four shape bits. A missing track or an ambiguous shape is marked as lost, which costs Reed-Solomon half as
much as a wrong symbol.

Several frame starts are tried, best first. Only a message that passes its CRC is returned.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from . import bank, channel, classify, codebook, detect, format2, layout, schedule
from .config import default_config
from .framing import DecodeError, FramingError

STAGES = ("sync", "header", "payload", "done")      # how far an attempt got


@dataclass(frozen=True)
class SlotReadout:
    symbols: np.ndarray             # 0-63, or ERASED
    n_missed: int                   # no track found
    n_doubtful: int                 # track found, shape ambiguous
    doubt: np.ndarray               # closest / second-closest shape distance of each read whistle (higher = less sure)
    missed: np.ndarray | None = None    # per slot: True = no track found (ERASED and not missed = doubtful)


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
    header_slots: tuple = ()        # the slots the best attempt read (preamble included), from the key alone
    payload_slots: tuple = ()       # ... and from the key and the nonce it read
    length: int | None = None       # the message length the header gave (characters or bytes)


class TrackSet:
    """Detected tracks as arrays, for fast lookups."""

    def __init__(self, tracks: list):
        self.tracks = tracks
        self.t0 = np.array([t.start_s for t in tracks], dtype=np.float64)
        self.fc = np.array([t.centre_hz for t in tracks], dtype=np.float64)
        self.n = np.array([len(t.freq_hz) for t in tracks], dtype=np.int64)
        self.t1 = np.array([t.start_s + len(t.freq_hz) * t.hop_s for t in tracks], dtype=np.float64)


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
    def _shape_fits(self, tr: TrackSet, slots: list, start_s: float) -> dict[tuple[int, int], dict[int, tuple[float, int]]]:
        """{(slot, track): {shape: (distance, pitch band)}}, each shape compared with the part of the track where it would sound."""
        r = self.cfg["receiver"]
        late = float(self.cfg["detect"]["slot_late_ms"]) / 1000
        pw = float(r["pitch_window_hz"])
        before, after = float(r["slot_guard_ms"]) / 1000, float(r["slot_tail_ms"]) / 1000
        overlap = float(r["min_overlap_ms"]) / 1000
        min_frames = int(r["min_track_frames"])
        missing_w, extra_w = float(r["missing_weight_hz_per_ms"]), float(r["extra_weight_hz_per_ms"])
        lengths = np.array([t.duration_ms for t in self.templates]) / 1000.0
        queries, shapes, costs, rows = [], [], [], []
        for i, s in enumerate(slots):
            t = start_s + s.start_s
            cand = np.asarray(s.candidates_hz)
            for k in np.where((tr.t0 <= t + late) & (tr.t1 >= t + overlap))[0]:
                track = tr.tracks[int(k)]
                when = track.start_s + (np.arange(len(track.freq_hz)) + 0.5) * track.hop_s
                for shape, length in enumerate(lengths):
                    part = track.freq_hz[(when >= t - before) & (when <= t + length + after)]
                    if len(part) < min_frames:
                        continue
                    middle = 0.5 * (float(part.max()) + float(part.min()))
                    band = int(np.argmin(np.abs(middle - cand)))
                    if abs(middle - cand[band]) > pw:
                        continue
                    missing_ms = 1000.0 * max(0.0, float(length) - len(part) * track.hop_s)
                    extra_ms = 1000.0 * max(0.0, float(tr.t1[k]) - (t + float(length) + after))
                    queries.append(part - cand[band])
                    shapes.append(shape)
                    costs.append(missing_w * missing_ms + extra_w * extra_ms)
                    rows.append((i, int(k), shape, band))
        fits: dict[tuple[int, int], dict[int, tuple[float, int]]] = {}
        if queries:
            dist = classify.pair_distances(queries, np.array(shapes), self.templates, self.cfg) + np.array(costs)
            for (i, k, shape, band), d in zip(rows, dist):
                fits.setdefault((i, k), {})[shape] = (float(d), band)
        return fits

    def read_slots(self, tr: TrackSet, slots: list, start_s: float) -> SlotReadout:
        symbols = np.full(len(slots), format2.ERASED, dtype=np.int64)
        doubt = np.zeros(len(slots))
        limit = float(self.cfg["classify"]["ambiguity_ratio"])
        chosen: dict[int, list] = {}
        for (i, _), fit in self._shape_fits(tr, slots, start_s).items():
            ranked = sorted((d, shape, band) for shape, (d, band) in fit.items())
            if i not in chosen or ranked[0][0] < chosen[i][0][0]:      # the track that some shape explains best
                chosen[i] = ranked
        n_doubtful = 0
        for i, ranked in chosen.items():
            d, shape, band = ranked[0]
            ratio = d / max(ranked[1][0], 1e-9) if len(ranked) > 1 else 0.0
            if ratio > limit:
                n_doubtful += 1
            else:
                symbols[i] = (shape << 2) | band
                doubt[i] = ratio
        missed = np.ones(len(slots), dtype=bool)
        missed[list(chosen)] = False
        return SlotReadout(symbols, len(slots) - len(chosen), n_doubtful, doubt, missed)

    # ------------------------------------------------------------------------------------------ one frame start
    def _attempt(self, tr: TrackSet, head: layout.Layout, start_s: float, votes: float, key: str) -> Reception:
        common = {"offset_s": start_s, "sync_votes": votes, "n_tracks": len(tr.tracks), "header_slots": tuple(head.slots)}
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
                failed = failed or Reception(False, "payload", str(e), mode=h.mode, nonce=h.nonce, header=hdr, body=body,
                                             payload_slots=tuple(pay.slots), length=h.length, **common)
                continue
            return Reception(True, "done", "", m.payload, m.text, m.mode, m.nonce, header=hdr, body=body,
                             n_repaired_wrong=h.n_errors + m.n_errors, n_repaired_lost=h.n_erasures + m.n_erasures,
                             payload_slots=tuple(pay.slots), length=h.length, **common)
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

    def tracks(self, audio: np.ndarray, fs: float) -> list:
        """Whistle tracks in a recording; digital silence gets a faint noise floor first (channel.quiet_floor)."""
        return self.detector.tracks(channel.quiet_floor(audio, fs, self.cfg), fs)

    def receive(self, audio: np.ndarray, fs: float, key: str) -> Reception:
        return self.decode_tracks(self.tracks(audio, fs), key)

    def receive_file(self, path: str | Path, key: str) -> Reception:
        x, fs = sf.read(str(path), dtype="float32", always_2d=True)
        return self.receive(x[:, 0], fs, key)
