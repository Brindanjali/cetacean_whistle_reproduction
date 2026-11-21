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

Drift (WC-R2; PLAN.md section 7 step 4). A moving source, or two sound cards whose clocks differ, stretches or squeezes the
recording in time: a moment t of the sent file is heard at t / s, with s = 1 + v / c for a closing speed v. Over a two-minute
message 1 m/s moves the last whistles by 80 ms, more than the slot windows allow. With receiver.drift_correction on:

- the frame search votes for (start, s) pairs over a grid of time scales, not for a start alone. Starts closer than 0.1 s are
  one candidate, ranked by votes; its time scale is the one whose matches sit tightest (a Gaussian score), so the header is read
  on roughly the right clock;
- once a header reading gives the nonce, every whistle whose place the key and nonce give (data slots and cover whistles, from
  the start signal to the last payload whistle) is matched again: a finer grid search over the whole range of time scales finds
  the line that most whistles sit on, and a least-squares fit over the whistles near that line refines it;
- the tracks are then moved onto the sender's clock (warp) and the payload is read as before.

The number of frame starts and header readings tried is unchanged, so the chance of a false message stays the same.
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
    time_scale: float = 1.0         # the time scale the payload was read with (channel.Received.time_scale; 1 = no drift)
    drift_matches: int = 0          # whistles the whole-message drift fit used (0 = not fitted)


def warp(tracks: list, t0: float, scale: float) -> list:
    """Tracks moved onto the sender's clock around t0, for a recording heard at time scale `scale` (a moment t of the sent file
    heard at t / scale, as channel.Received.time_scale). A track heard at t0 + d was sent at t0 + d * scale; its frames last
    hop * scale, and its pitch is divided by scale."""
    if scale == 1.0:
        return list(tracks)
    return [detect.Track(t0 + (t.start_s - t0) * scale, t.freq_hz / scale, t.hop_s * scale) for t in tracks]


@dataclass(frozen=True)
class _Known:
    """Whistles whose place the key gives, paired with every detected track at one of their pitches."""
    tau: np.ndarray                 # time from the frame's first whistle, on the sender's clock
    weight: np.ndarray              # vote weight
    j: np.ndarray                   # pairs: a known whistle ...
    k: np.ndarray                   # ... and a track within pitch_window_hz of one of its pitches


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

    def _pairs(self, tr: TrackSet, known: list) -> _Known:
        pw = float(self.cfg["receiver"]["pitch_window_hz"])
        js, ks = [np.zeros(0, np.int64)], [np.zeros(0, np.int64)]
        for j, (_, pitches, _) in enumerate(known):
            near = np.where(np.abs(tr.fc[:, None] - pitches[None, :]).min(axis=1) <= pw)[0]
            js.append(np.full(len(near), j, dtype=np.int64))
            ks.append(near.astype(np.int64))
        return _Known(np.array([t for t, _, _ in known], dtype=np.float64), np.array([w for _, _, w in known], dtype=np.float64),
                      np.concatenate(js), np.concatenate(ks))

    def _scales(self, step: float) -> np.ndarray:
        """Time scales searched: 1 alone without drift correction, else 1 +/- drift_max in steps of `step`."""
        r = self.cfg["receiver"]
        if not bool(r["drift_correction"]):
            return np.array([1.0])
        n = int(round(float(r["drift_max"]) / step))
        return 1.0 + step * np.arange(-n, n + 1)

    def find_frame(self, tr: TrackSet, head: layout.Layout) -> list[tuple[float, float, float]]:
        """Candidate frame starts as (time, votes, time scale), best first."""
        r = self.cfg["receiver"]
        step, tol, n_out = float(r["sync_bin_s"]), float(r["sync_tolerance_s"]), int(r["sync_candidates"])
        if not len(tr.t0):
            return []
        kn = self._pairs(tr, self._known_whistles(head))
        if not len(kn.j):
            return []
        drift = bool(r["drift_correction"])
        sigma = float(r["drift_sync_sigma_s"]) if drift else None
        guard_s = 0.1
        guard = max(1, int(round(guard_s / step)))
        cands = []
        for s in self._scales(float(r["drift_sync_step"])):
            votes_at = tr.t0[kn.k] - kn.tau[kn.j] / s
            lo = float(votes_at.min())
            bins = ((votes_at - lo) / step).astype(np.int64)
            hist = np.bincount(bins, kn.weight[kn.j], int(bins.max()) + 1)
            smooth = np.convolve(hist, np.ones(3), "same")
            for _ in range(n_out * 3):
                j = int(np.argmax(smooth))
                if smooth[j] <= 0:
                    break
                cands.append((*self._refine(tr, kn, lo + (j + 0.5) * step, float(s), tol, sigma), float(s)))
                smooth[max(0, j - guard):j + guard + 1] = 0.0
        cands.sort(key=lambda c: -c[1])
        if not drift:
            return [(start, votes, s) for start, votes, _, s in cands[:n_out]]
        out: list[tuple[float, float, float]] = []
        for c in cands:                             # starts within guard_s are one candidate, ranked by its best votes ...
            if any(abs(c[0] - o[0]) <= guard_s for o in out):
                continue
            group = [d for d in cands if abs(d[0] - c[0]) <= guard_s]
            start, votes, _, s = max(group, key=lambda d: (d[2], -abs(d[3] - 1.0)))   # ... read at its tightest time scale
            out.append((start, votes, s))
            if len(out) == n_out:
                break
        return out

    @staticmethod
    def _refine(tr: TrackSet, kn: _Known, start: float, scale: float, tol: float, sigma: float | None = None) -> tuple[float, float, float]:
        """Move a candidate start to the median of its matches, and count the votes that really match. Also a Gaussian score of
        how tightly the matches sit around the moved start (sigma; the votes again when sigma is None)."""
        dt = tr.t0[kn.k] - (start + kn.tau[kn.j] / scale)
        ok = np.abs(dt) <= tol
        if not ok.any():
            return start, 0.0, 0.0
        jj, dd = kn.j[ok], dt[ok]
        order = np.lexsort((np.abs(dd), jj))            # for each known whistle, its closest track (first in track order on ties)
        jj, dd = jj[order], dd[order]
        first = np.r_[True, jj[1:] != jj[:-1]]
        res, w = dd[first], kn.weight[jj[first]]
        shift = float(np.median(res))
        votes = float(w.sum())
        tight = votes if sigma is None else float((w * np.exp(-0.5 * ((res - shift) / sigma) ** 2)).sum())
        return start + shift, votes, tight

    def _fit_drift(self, tr: TrackSet, kn: _Known, start: float, scale: float) -> tuple[float, float, int]:
        """(start, time scale, whistles used): the line that most of the known whistles sit on, over the whole message.

        A grid search over every time scale finds, for each, the 30 ms offset window with the most votes; the best scale wins
        (ties go to the scale nearest 1). A least-squares fit over the closest track of each whistle within
        drift_fit_tolerance_s of that line refines it, up to three times. The start is then the median of the matches, as in the frame
        search. Too few matches keep the frame search's start and scale."""
        r = self.cfg["receiver"]
        tol, fit_tol, need = float(r["sync_tolerance_s"]), float(r["drift_fit_tolerance_s"]), int(r["drift_min_matches"])
        scales = self._scales(float(r["drift_fine_step"]))
        rates = 1.0 / scales                            # seconds heard per second sent
        if not len(kn.j):
            return start, scale, 0
        tau, tk, w, jj = kn.tau[kn.j], tr.t0[kn.k], kn.weight[kn.j], kn.j
        spread = float(np.abs(rates - 1.0 / scale).max())
        near = np.abs(tk - start - tau / scale) <= tol + spread * tau
        tau, tk, w, jj = tau[near], tk[near], w[near], jj[near]
        if len(tau) < need:
            return start, scale, 0
        bin_s = 0.01
        nb = int(np.ceil(2 * tol / bin_s))
        res = tk[None, :] - start - rates[:, None] * tau[None, :]
        b = np.floor((res + tol) / bin_s).astype(np.int64)
        ok = (b >= 0) & (b < nb)
        rows = np.broadcast_to(np.arange(len(rates))[:, None], res.shape)
        hist = np.bincount((rows * nb + b)[ok], np.broadcast_to(w, res.shape)[ok], len(rates) * nb).reshape(len(rates), nb)
        smooth = hist[:, :-2] + hist[:, 1:-1] + hist[:, 2:]
        at = smooth.argmax(axis=1)
        score = smooth[np.arange(len(rates)), at]
        i = int(np.lexsort((np.abs(scales - 1.0), -score))[0])
        rate, b0 = float(rates[i]), start - tol + (int(at[i]) + 1.5) * bin_s
        used = np.zeros(0, dtype=np.int64)
        for _ in range(3):
            d = tk - b0 - rate * tau
            m = np.where(np.abs(d) <= fit_tol)[0]
            m = m[np.lexsort((np.abs(d[m]), jj[m]))]
            m = m[np.r_[True, jj[m][1:] != jj[m][:-1]]] if len(m) else m
            if len(m) < need or float(np.ptp(tau[m])) <= 0:
                break
            used = m
            slope, intercept = np.polyfit(tau[m], tk[m], 1)
            rate, b0 = float(slope), float(intercept)
        if not len(used):
            return start, scale, 0
        rate = float(np.clip(rate, rates.min(), rates.max()))
        return float(np.median(tk[used] - rate * tau[used])), 1.0 / rate, int(len(used))

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
    def _attempt(self, tr: TrackSet, head: layout.Layout, start_s: float, votes: float, key: str, scale: float = 1.0,
                 fit: bool = True) -> Reception:
        """Read the frame that starts at start_s, heard at time scale `scale`. With drift correction on (and fit), the payload is
        read at the start and time scale of the whole-message drift fit; fit=False reads it at start_s and scale as given
        (oracle synchronisation in the experiments)."""
        common = {"sync_votes": votes, "n_tracks": len(tr.tracks), "header_slots": tuple(head.slots)}
        r = self.cfg["receiver"]
        soft, drift = bool(r["soft_repair"]), bool(r["drift_correction"])
        th = tr if scale == 1.0 else TrackSet(warp(tr.tracks, start_s, scale))
        hdr = self.read_slots(th, [s for s in head.slots if s.part == layout.HEADER], start_s)
        try:
            readings = format2.header_candidates(hdr.symbols, key, self.cfg, hdr.doubt if soft else None)
        except DecodeError as e:
            return Reception(False, "header", str(e), header=hdr, offset_s=start_s, time_scale=scale, **common)
        failed = None
        for h in readings[:int(r["max_header_readings"])]:
            n = format2.payload_symbols(h.mode, h.length, self.cfg)
            pay = layout.payload_layout(key, h.nonce, n, head, self.bank, self.pool, self.cfg)
            t0, s, n_fit = start_s, scale, 0
            if drift and fit:
                t0, s, n_fit = self._fit_drift(tr, self._pairs(tr, self._known_whistles(head) + self._known_whistles(pay)), start_s, scale)
            tp = tr if s == 1.0 else TrackSet(warp(tr.tracks, t0, s))
            body = self.read_slots(tp, pay.slots, t0)
            where = {"offset_s": t0, "time_scale": s, "drift_matches": n_fit}
            try:
                m = format2.decode_payload(body.symbols, h, key, self.cfg, body.doubt if soft else None)
            except (DecodeError, FramingError) as e:
                failed = failed or Reception(False, "payload", str(e), mode=h.mode, nonce=h.nonce, header=hdr, body=body,
                                             payload_slots=tuple(pay.slots), length=h.length, **where, **common)
                continue
            return Reception(True, "done", "", m.payload, m.text, m.mode, m.nonce, header=hdr, body=body,
                             n_repaired_wrong=h.n_errors + m.n_errors, n_repaired_lost=h.n_erasures + m.n_erasures,
                             payload_slots=tuple(pay.slots), length=h.length, **where, **common)
        return failed

    def decode_tracks(self, tracks: list, key: str) -> Reception:
        tr = TrackSet(tracks)
        head = layout.header_layout(key, self.bank, self.pool, self.cfg)
        found = self.find_frame(tr, head)
        if not found:
            return Reception(False, "sync", "no whistles match the key's timing", n_tracks=len(tracks))
        best = None
        for i, (start, votes, scale) in enumerate(found):
            got = self._attempt(tr, head, start, votes, key, scale)
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
