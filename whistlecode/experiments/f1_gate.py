"""Gate test F1 for message format v2 (PLAN.md section 4.6). No format code depends on this file.

Real stretches of the rhythm bank (encounters 191 and 214) are played with their cover whistles. The current 16 shapes go
into the data slots, stretched to the real whistles' lengths and placed at one of four candidate pitches. The audio is mixed
into real encounter-214 noise and read with the real detector, twice per data whistle: with the true pitch given, and
choosing among the four candidates. Format v1 is measured in the same noise as the reference.

Adopted only if all of these hold at 10 and 15 dB:
  a. the wrong pitch is chosen for at most 1 % of detected data whistles;
  b. predicted v2 message success for 12, 20 and 60 characters is at least that of v1;
  c. the rhythm of the detected tracks scores at most 0.60 against real whistles.

    python whistlecode/experiments/f1_gate.py [--quick] [--own-length]

--own-length runs the same test with the limits unchanged, but data whistles keep their own lengths instead of being stretched
to the real whistles' lengths, and are read with classifier A's length clue.

Results: whistlecode/outputs/f1_gate/results.json, or f1_gate_own_length/ (gitignored).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from scipy.stats import binom
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

WC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WC))

from wcode import channel, classify, detect, schedule, synth, transmitter  # noqa: E402
from wcode.config import PROJECT_ROOT, default_config, payload_parity  # noqa: E402
from wcode.contour import Contour, centred  # noqa: E402

SETTINGS = {                       # [DECISION] all from PLAN.md section 4.6, or chosen here for this experiment where marked
    "bank_encounters": [191, 214],
    "window_s": 44.0,
    "min_whistles_per_window": 10,
    "noise_encounter": 214,
    "snr_db": [10.0, 15.0, 20.0],
    "gate_snr_db": [10.0, 15.0],
    "sends_per_shape": 200,
    "stretch_start_s": 8.0,        # chosen here: where the 44 s stretch sits inside a 60 s noise file
    "data_length_s": [0.10, 0.45],
    "slot_early_s": 0.06,
    "slot_late_s": 0.15,
    "min_data_spacing_s": 0.35,
    "data_after_s": 0.10,
    "collision_hz": 1000.0,
    "follow_s": 0.10,
    "pitch_window_hz": 500.0,
    "cover_extra_snr_db": [0.0, 10.0],   # chosen here: cover whistles are as loud as the data whistle, or up to 10 dB louder
    "cover_move_clearance_hz": 1500.0,   # chosen here
    "cover_pitch_range_hz": [3000.0, 17000.0],   # chosen here
    "shape_pool_per_type": 300,    # chosen here: varied shapes drawn once per type, tau from config.toml
    "seed": 20261118,
    "max_wrong_pitch": 0.01,
    "max_rhythm_score": 0.60,
    "message_chars": [12, 20, 60],
    "rhythm_noise": "quietest half of the noise files",   # chosen here: a stretch already is a full chorus
}
S = SETTINGS
WIN = float(S["window_s"])


# ---------------------------------------------------------------------------------------------- the rhythm bank
class Bank:
    """All detector tracks of one encounter, in time order, with 44 s windows."""

    def __init__(self, encounter: int):
        z = np.load(PROJECT_ROOT / "preprocessed" / f"encounter_{encounter}" / "contours.npz")
        self.encounter, self.hop = encounter, float(z["frame_s"])
        stems = {s: self._file_time(s) for s in np.unique(z["source_file"]).tolist()}
        t = np.array([stems[s] for s in z["source_file"].tolist()]) + z["start_s"]
        order = np.argsort(t, kind="stable")
        offsets, freq = z["offsets"], z["freq_hz"]
        self.on = t[order] - t[order[0]]
        self.off = self.on + z["n_frames"][order] * self.hop
        self.freq = [freq[offsets[i]:offsets[i + 1]].astype(np.float64) for i in order]
        self.source = z["source_file"][order]
        self.windows = []
        s = 0.0
        while s + WIN <= self.on[-1]:
            idx = np.where((self.on >= s) & (self.on < s + WIN))[0]
            if len(idx) >= int(S["min_whistles_per_window"]):
                self.windows.append((s, idx))
            s += WIN

    @staticmethod
    def _file_time(stem: str) -> float:
        p = stem.split("_")
        return datetime.strptime(p[1] + p[2], "%Y%m%d%H%M%S").timestamp() + int(p[3]) / 1000


def data_slots(on: np.ndarray, off: np.ndarray) -> np.ndarray:
    """Indices of the real whistles that can carry data (PLAN.md section 4.6)."""
    lo, hi = S["data_length_s"]
    out, allowed = [], -1e9
    for i, (a, b) in enumerate(zip(on, off)):
        near = np.searchsorted(on, [a - S["slot_early_s"], a + S["slot_late_s"]])
        if lo <= b - a <= hi and a >= allowed and near[1] - near[0] == 1:
            out.append(i)
            allowed = a + max(S["min_data_spacing_s"], b - a + S["data_after_s"])
    return np.array(out, dtype=np.int64)


# ---------------------------------------------------------------------------------------------- rhythm features
def rhythm_features(on: np.ndarray, off: np.ndarray) -> list[float]:
    o = np.argsort(on)
    on, off = on[o], off[o]
    n = len(on)
    ioi = np.diff(on)
    m, s = ioi.mean(), ioi.std()
    busy, last, gaps = 0.0, 0.0, []
    for a, b in zip(on, off):
        if a > last:
            gaps.append(a - last)
        busy += max(0.0, b - max(a, last))
        last = max(last, b)
    gaps.append(max(0.0, WIN - last))
    overlap = np.mean([np.any((on < off[i]) & (off > on[i]) & (np.arange(n) != i)) for i in range(n)])
    counts = np.histogram(on, bins=np.arange(0, WIN + 2, 2.0))[0]
    lv = 3 * np.mean(((ioi[:-1] - ioi[1:]) / np.maximum(ioi[:-1] + ioi[1:], 1e-6)) ** 2)
    return [n / WIN * 60, float(np.median(ioi)), s / max(m, 1e-6), (s - m) / max(s + m, 1e-6), lv, float(np.percentile(ioi, 10)),
            float(np.percentile(ioi, 90)), max(gaps), busy / WIN, float(overlap), counts.var() / max(counts.mean(), 1e-6)]


def rhythm_score(real: dict, coded: list[dict], snr: float, quiet_only: bool) -> float | None:
    """Train on one bank encounter (all SNRs), test on the other at this SNR, both ways; mean AUC."""
    scores = []
    for tr, te in ((191, 214), (214, 191)):
        use = [c for c in coded if not quiet_only or c["quiet"]]
        ctr = np.array([c["features"] for c in use if c["encounter"] == tr])
        cte = np.array([c["features"] for c in use if c["encounter"] == te and c["snr"] == snr])
        if len(ctr) < 5 or len(cte) < 5:
            return None
        X = np.vstack([real[tr], ctr])
        y = np.r_[np.zeros(len(real[tr])), np.ones(len(ctr))]
        m = HistGradientBoostingClassifier(max_depth=3, max_iter=150, random_state=0, class_weight="balanced").fit(X, y)
        p = m.predict_proba(np.vstack([real[te], cte]))[:, 1]
        scores.append(roc_auc_score(np.r_[np.zeros(len(real[te])), np.ones(len(cte))], p))
    return float(np.mean(scores))


# ---------------------------------------------------------------------------------------------- predicted message success
def block_ok(n: int, nsym: int, lost: float, wrong: float) -> float:
    """P(2e + f <= nsym) for n independent symbols."""
    total = 0.0
    q = wrong / max(1.0 - lost, 1e-12)
    for f in range(0, min(n, nsym) + 1):
        total += float(binom.pmf(f, n, lost) * binom.cdf((nsym - f) // 2, n - f, q))
    return total


def success_v1(chars: int, lost: float, wrong: float, cfg: dict) -> float:
    """Format v1: two whistles per byte, header RS(6, 2), payload of chars bytes."""
    b_lost = 1 - (1 - lost) ** 2
    b_wrong = (1 - lost) ** 2 - (1 - lost - wrong) ** 2
    k = chars + 2
    nsym = payload_parity(k, cfg)
    return block_ok(6, 4, b_lost, b_wrong) * block_ok(k + nsym, nsym, b_lost, b_wrong)


def v2_blocks(chars: int) -> list[tuple[int, int]]:
    """(symbols, parity) of each code block for a compact-alphabet message."""
    data = math.ceil((5 * chars + 16) / 6)
    b = 1
    while True:
        d = [data // b + (i < data % b) for i in range(b)]
        out = [(x + max(8, math.ceil(x / 2)), max(8, math.ceil(x / 2))) for x in d]
        if max(n for n, _ in out) <= 63:
            return out
        b += 1


def success_v2(chars: int, lost: float, wrong: float) -> float:
    """Format v2: one whistle per symbol, header RS(7, 3), payload blocks over GF(64)."""
    p = block_ok(7, 4, lost, wrong)
    for n, nsym in v2_blocks(chars):
        p *= block_ok(n, nsym, lost, wrong)
    return p


# ---------------------------------------------------------------------------------------------- audio helpers
def stretch(a: np.ndarray, n: int) -> np.ndarray:
    return np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(a)), a)


def frames_of(length_s: float, hop: float) -> int:
    return max(2, int(round(length_s / hop)))


class Noise:
    """Encounter-214 noise files in random order, with their levels; the quietest half is marked."""

    def __init__(self, cfg: dict, pcfg, rng: np.random.Generator):
        self.cfg, self.pcfg, self.fs = cfg, pcfg, float(cfg["synth"]["fs_hz"])
        e = int(S["noise_encounter"])
        with open(PROJECT_ROOT / "preprocessed" / f"encounter_{e}" / "files.csv", encoding="utf-8-sig") as f:
            counts = {r["file"]: int(r["n_contours"] or 0) for r in csv.DictReader(f)}
        self.median = float(np.median(list(counts.values())))
        self.counts = counts
        self.files = [channel.noise_files(e)[i] for i in rng.permutation(len(channel.noise_files(e)))]
        self.i = 0
        self.levels: dict[str, np.ndarray] = {}

    def next(self, exclude=frozenset()):
        need = int((S["stretch_start_s"] + WIN + 4.0) * self.fs)
        while True:
            path = self.files[self.i % len(self.files)]
            self.i += 1
            if path.stem in exclude:
                continue
            x = channel.load_noise(path, self.cfg, self.pcfg)
            if len(x) < need:
                continue
            if path.stem not in self.levels:
                self.levels[path.stem] = channel.bin_levels(x, self.fs, float(self.cfg["channel"]["snr_bin_hz"]))
            return x.astype(np.float64), self.levels[path.stem], self.counts.get(path.stem, 0) <= self.median


def tone(c: Contour, fc: float, rng: np.random.Generator, cfg: dict, fs: float) -> np.ndarray:
    """A cover whistle: as synth.whistle, without the harmonic when it would not fit below the Nyquist frequency."""
    s = cfg["synth"]
    f = synth.instantaneous_hz(c, fc, fs)
    phase = 2 * np.pi * np.cumsum(f) / fs
    x = np.cos(phase)
    if f.max() * 2 < 0.98 * fs / 2:
        x = x + 10 ** (float(s["harmonic2_db"]) / 20) * np.cos(2 * phase)
    return x * synth.envelope(rng, len(x), fs, s["taper"], s["ripple_depth"], s["ripple_rate_hz"])


def add(x: np.ndarray, start_s: float, w: np.ndarray, fs: float) -> None:
    s0 = int(round(start_s * fs))
    n = min(len(w), len(x) - s0)
    if n > 0 and s0 >= 0:
        x[s0:s0 + n] += w[:n]


def stretched_distances(queries: list[np.ndarray], frames: np.ndarray, templates: list[Contour], cfg: dict) -> np.ndarray:
    """(Q, T) banded DTW between each query and the templates stretched to that slot's known length."""
    c = cfg["classify"]
    T = len(templates)
    out = np.zeros((len(queries), T))
    cache: dict[int, list[np.ndarray]] = {}
    order = np.argsort([len(q) for q in queries], kind="stable")
    for c0 in range(0, len(queries), 256):
        sel = order[c0:c0 + 256]
        bs = []
        for i in sel:
            n = int(frames[i])
            if n not in cache:
                cache[n] = [stretch(t.offset_hz, n) for t in templates]
            bs.extend(cache[n])
        qa, lq = classify._pad([queries[i] for i in sel])
        b, lb = classify._pad(bs)
        d = classify.dtw_pairs(np.repeat(qa, T, axis=0), np.repeat(lq, T), b, lb, float(c["dtw_band_frac"]), int(c["dtw_band_min"]))
        out[sel] = d.reshape(len(sel), T)
    return out


def deck(sends: int, rng: np.random.Generator) -> list[int]:
    return rng.permutation(np.repeat(np.arange(16), sends)).tolist()


# ---------------------------------------------------------------------------------------------- format v1 reference
def measure_v1(snr: float, sends: int, tx, shapes, noise: Noise, det, rng, cfg, log) -> dict:
    fs, lo_hi = float(cfg["synth"]["fs_hz"]), cfg["schedule"]["interval_s"]
    templates = [t.contour for t in tx.cb.types]
    d = deck(sends, rng)
    n, missed = 0, 0
    labels, queries = [], []
    while d:
        x, levels, _ = noise.next()
        t, starts, fcs, labs = 0.5, [], [], []
        while d and t < len(x) / fs - 1.0:
            s = d.pop()
            c = shapes[s][int(rng.integers(len(shapes[s])))]
            fc = float(rng.choice(tx.pool))
            a = channel.amplitude_for_snr(snr, fc + float(c.offset_hz.mean()), levels, fs, cfg)
            add(x, t, a * synth.whistle(c, fc, rng, cfg, fs), fs)
            starts.append(t), fcs.append(fc), labs.append(s)
            t += float(rng.uniform(*lo_hi))
        for s, fc, m in zip(labs, fcs, detect.match(det.tracks(x, fs), starts, fcs, cfg)):
            n += 1
            if m is None:
                missed += 1
            else:
                labels.append(s)
                queries.append(m.contour(fc))
    best, amb = classify.decide(classify.distances(queries, templates, cfg), float(cfg["classify"]["ambiguity_ratio"]))
    labels = np.array(labels)
    erased, wrong = int(amb.sum()), int(((best != labels) & ~amb).sum())
    log(f"  v1 reference at {snr:g} dB: {n} sent, {missed} missed, {erased} erased, {wrong} wrong")
    return {"sent": n, "missed": missed, "erased": erased, "wrong": wrong, "lost_rate": (missed + erased) / n, "wrong_rate": wrong / n}


# ---------------------------------------------------------------------------------------------- format v2 trial
def measure_v2(snr: float, sends: int, banks: dict, tx, shapes, noise: Noise, det, rng, cfg, log,
               own_length: bool = False) -> tuple[dict, list[dict]]:
    fs = float(cfg["synth"]["fs_hz"])
    templates = [t.contour for t in tx.cb.types]
    lead = float(S["stretch_start_s"])
    pw = float(S["pitch_window_hz"])
    remaining = sends * 16
    d = deck(sends, rng)
    order = {e: [int(i) for i in rng.permutation(len(b.windows))] for e, b in banks.items()}
    rows, coded = [], []
    moved_n, unmoved_n, cover_n, stretches = 0, 0, 0, 0
    which = 0
    while remaining > 0:
        e = list(banks)[which % len(banks)]
        which += 1
        b = banks[e]
        if not order[e]:
            order[e] = [int(i) for i in rng.permutation(len(b.windows))]
        t0, idx = b.windows[order[e].pop()]
        on, off = b.on[idx] - t0, b.off[idx] - t0
        slots = data_slots(on, off)
        if len(slots) == 0:
            continue
        x, levels, quiet = noise.next(frozenset(b.source[idx].tolist()))
        is_data = np.zeros(len(on), bool)
        is_data[slots] = True
        info = []
        for i in slots:
            if not d:
                d = deck(1, rng)
            s = d.pop()
            remaining -= 1
            u = float(rng.random())
            cand = np.quantile(tx.pool, (np.arange(4) + u) / 4)
            band = int(rng.integers(4))
            n = frames_of(off[i] - on[i], b.hop)
            base = shapes[s][int(rng.integers(len(shapes[s])))]
            c = base if own_length else Contour(stretch(base.offset_hz, n), b.hop)
            a = channel.amplitude_for_snr(snr, cand[band] + float(c.offset_hz.mean()), levels, fs, cfg)
            add(x, lead + on[i], a * synth.whistle(c, float(cand[band]), rng, cfg, fs), fs)
            info.append({"start": lead + on[i], "shape": s, "band": band, "cand": cand, "frames": n, "fc": float(cand[band]),
                         "on": on[i], "off": on[i] + c.n_frames * c.hop_s if own_length else off[i]})
        lo_p, hi_p = S["cover_pitch_range_hz"]
        for j in np.where(~is_data)[0]:
            f = b.freq[idx[j]]
            mid, span = 0.5 * (f.max() + f.min()), float(f.max() - f.min())
            hits = [g["fc"] for g in info if on[j] < g["off"] + S["follow_s"] and off[j] > g["on"]]
            clash = [p for p in hits if f.min() - S["collision_hz"] < p < f.max() + S["collision_hz"]]
            cover_n += 1
            if clash:
                for _ in range(30):
                    m2 = float(rng.uniform(lo_p + span / 2, hi_p - span / 2))
                    if all(abs(m2 - p) >= span / 2 + S["cover_move_clearance_hz"] for p in hits):
                        mid = m2
                        moved_n += 1
                        break
                else:
                    unmoved_n += 1
            c = Contour(centred(f), b.hop)
            a = channel.amplitude_for_snr(snr + float(rng.uniform(*S["cover_extra_snr_db"])), mid, levels, fs, cfg)
            add(x, lead + on[j], a * tone(c, mid, rng, cfg, fs), fs)
        tracks = det.tracks(x, fs)
        stretches += 1
        ts = np.array([t.start_s for t in tracks]) if tracks else np.zeros(0)
        cs = np.array([t.centre_hz for t in tracks]) if tracks else np.zeros(0)
        ns = np.array([len(t.freq_hz) for t in tracks]) if tracks else np.zeros(0, int)
        for g in info:
            near = (ts >= g["start"] - S["slot_early_s"]) & (ts <= g["start"] + S["slot_late_s"])
            dist = np.abs(cs[:, None] - g["cand"][None, :]) if len(cs) else np.zeros((0, 4))
            pick = lambda m: None if not m.any() else min(np.where(m)[0], key=lambda k: (abs(ts[k] - g["start"]), -ns[k]))
            ka = pick(near & (np.abs(cs - g["fc"]) <= pw))
            kb = pick(near & (dist.min(axis=1) <= pw)) if len(cs) else None
            band_hat = None if kb is None else int(np.argmin(dist[kb]))
            rows.append({"shape": g["shape"], "band": g["band"], "frames": g["frames"], "band_hat": band_hat,
                         "qa": None if ka is None else tracks[ka].freq_hz - g["fc"],
                         "qb": None if kb is None else tracks[kb].freq_hz - g["cand"][band_hat]})
        w = (ts >= lead) & (ts < lead + WIN)
        if int(w.sum()) >= int(S["min_whistles_per_window"]):
            tr_on = ts[w] - lead
            coded.append({"encounter": e, "snr": snr, "quiet": bool(quiet),
                          "features": rhythm_features(tr_on, tr_on + ns[w] * b.hop)})
        if stretches % 10 == 0:
            log(f"  v2 at {snr:g} dB: {stretches} stretches, {max(remaining, 0)} data whistles to go")

    ratio = float(cfg["classify"]["ambiguity_ratio"])
    n = len(rows)
    shape = np.array([r["shape"] for r in rows])
    band = np.array([r["band"] for r in rows])

    def read(key: str):
        hit = np.array([r[key] is not None for r in rows])
        q = [r[key] for r in rows if r[key] is not None]
        frames = np.array([r["frames"] for r in rows])[hit]
        if own_length:
            return hit, classify.distances([Contour(a, templates[0].hop_s) for a in q], templates, cfg)
        return hit, stretched_distances(q, frames, templates, cfg)

    hit_a, dist_a = read("qa")
    hit_b, dist_b = read("qb")
    best_a, amb_a = classify.decide(dist_a, ratio)
    best_b, amb_b = classify.decide(dist_b, ratio)
    band_hat = np.array([r["band_hat"] if r["band_hat"] is not None else -1 for r in rows])[hit_b]
    wrong_pitch = band_hat != band[hit_b]
    wrong_a = (best_a != shape[hit_a]) & ~amb_a
    wrong_b = ((best_b != shape[hit_b]) | wrong_pitch) & ~amb_b
    res = {"data_whistles": n, "stretches": stretches,
           "cover_whistles": cover_n, "cover_moved": moved_n, "cover_could_not_move": unmoved_n,
           "true_pitch_given": {"missed": int((~hit_a).sum()), "erased": int(amb_a.sum()), "wrong": int(wrong_a.sum()),
                                "lost_rate": ((~hit_a).sum() + amb_a.sum()) / n, "wrong_rate": wrong_a.sum() / n},
           "four_candidates": {"missed": int((~hit_b).sum()), "erased": int(amb_b.sum()), "wrong": int(wrong_b.sum()),
                               "lost_rate": ((~hit_b).sum() + amb_b.sum()) / n, "wrong_rate": wrong_b.sum() / n,
                               "detected": int(hit_b.sum()), "wrong_pitch": int(wrong_pitch.sum()),
                               "wrong_pitch_rate": float(wrong_pitch.mean()) if hit_b.any() else 1.0},
           "ratio_sensitivity": {}}
    for r in (0.80, 0.85, 0.90, 0.95):
        bb, aa = classify.decide(dist_b, r)
        ww = ((bb != shape[hit_b]) | wrong_pitch) & ~aa
        res["ratio_sensitivity"][f"{r:.2f}"] = {"lost_rate": ((~hit_b).sum() + aa.sum()) / n, "wrong_rate": ww.sum() / n}
    return res, coded


# ---------------------------------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quick", action="store_true", help="a small check run at 15 dB, written to a *_quick folder")
    ap.add_argument("--own-length", action="store_true", help="data whistles keep their own lengths instead of being stretched")
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")
    t_all = time.perf_counter()
    cfg = default_config()
    out = PROJECT_ROOT / "whistlecode" / "outputs" / ("f1_gate" + ("_own_length" if args.own_length else "") + ("_quick" if args.quick else ""))
    out.mkdir(parents=True, exist_ok=True)
    lines = []

    def log(m: str) -> None:
        lines.append(m)
        print(m, flush=True)

    snrs = [15.0] if args.quick else [float(s) for s in S["snr_db"]]
    gate_snrs = [15.0] if args.quick else [float(s) for s in S["gate_snr_db"]]
    sends = 6 if args.quick else int(S["sends_per_shape"])
    pool_n = 8 if args.quick else int(S["shape_pool_per_type"])
    for name, got, want in (("v1", success_v1(12, 0.10, 0.03, cfg), 0.75), ("v2", success_v2(12, 0.10, 0.03), 0.975)):
        if abs(got - want) > 0.01:
            raise RuntimeError(f"predicted success of {name} is {got:.3f}, the plan's calculation says {want}")

    rng = np.random.default_rng(int(S["seed"]))
    tx = transmitter.Transmitter(cfg)
    det = detect.Detector(cfg)
    log(f"loading the rhythm bank: encounters {S['bank_encounters']}")
    banks = {e: Bank(e) for e in S["bank_encounters"]}
    real = {e: np.array([rhythm_features(b.on[i] - s, b.off[i] - s) for s, i in b.windows]) for e, b in banks.items()}
    log("  windows: " + ", ".join(f"{e}: {len(b.windows)}" for e, b in banks.items()))
    log(f"drawing {pool_n} varied shapes per type (tau = {cfg['transmit']['tau']})")
    drawn, _, fell = tx._shapes(np.repeat(np.arange(16), pool_n), float(cfg["transmit"]["tau"]), rng)
    shapes = [drawn[i * pool_n:(i + 1) * pool_n] for i in range(16)]
    log(f"  {int(fell.sum())} of {len(drawn)} fell back to the type's mean")
    noise = Noise(cfg, tx.pcfg, rng)

    results, coded = {}, []
    for snr in snrs:
        t0 = time.perf_counter()
        log(f"\n=== {snr:g} dB ===")
        v1 = measure_v1(snr, sends, tx, shapes, noise, det, rng, cfg, log)
        v2, c = measure_v2(snr, sends, banks, tx, shapes, noise, det, rng, cfg, log, own_length=args.own_length)
        coded += c
        results[f"{snr:g}"] = {"v1": v1, "v2": v2}
        log(f"  finished in {time.perf_counter() - t0:.0f} s")

    verdict = {"pitch": True, "success": True, "rhythm": True}
    log("\n=== results ===")
    for snr in snrs:
        r = results[f"{snr:g}"]
        v1, a, b = r["v1"], r["v2"]["true_pitch_given"], r["v2"]["four_candidates"]
        score_q = rhythm_score(real, coded, snr, True)
        score_all = rhythm_score(real, coded, snr, False)
        r["rhythm_score_quiet_noise"], r["rhythm_score_all_noise"] = score_q, score_all
        r["predicted"] = {str(c): {"v1": success_v1(c, v1["lost_rate"], v1["wrong_rate"], cfg),
                                   "v2": success_v2(c, b["lost_rate"], b["wrong_rate"])} for c in S["message_chars"]}
        ok_pitch = b["wrong_pitch_rate"] <= S["max_wrong_pitch"]
        ok_success = all(p["v2"] >= p["v1"] for p in r["predicted"].values())
        ok_rhythm = score_q is not None and score_q <= S["max_rhythm_score"]
        r["passed"] = {"pitch": ok_pitch, "success": ok_success, "rhythm": ok_rhythm}
        if snr in gate_snrs:
            verdict = {k: verdict[k] and r["passed"][k] for k in verdict}
        log(f"\n{snr:g} dB   lost / wrong whistles: v1 {v1['lost_rate']:.1%} / {v1['wrong_rate']:.1%}   "
            f"v2 true pitch {a['lost_rate']:.1%} / {a['wrong_rate']:.1%}   v2 four candidates {b['lost_rate']:.1%} / {b['wrong_rate']:.1%}")
        log(f"  wrong pitch: {b['wrong_pitch_rate']:.2%} of {b['detected']} detected data whistles  [{'pass' if ok_pitch else 'FAIL'}]")
        log("  predicted success v1 -> v2: " + ", ".join(f"{c} chars {p['v1']:.1%} -> {p['v2']:.1%}" for c, p in r["predicted"].items())
            + f"  [{'pass' if ok_success else 'FAIL'}]")
        log(f"  rhythm score: {score_q if score_q is None else round(score_q, 3)} on quiet noise, "
            f"{score_all if score_all is None else round(score_all, 3)} on all noise  [{'pass' if ok_rhythm else 'FAIL'}]")
    adopted = all(verdict.values())
    log(f"\nGATE: {'PASSED' if adopted else 'FAILED'}  (pitch {verdict['pitch']}, message success {verdict['success']}, rhythm {verdict['rhythm']})")
    summary = {"quick": args.quick, "own_length": args.own_length, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "settings": S, "adopted": adopted,
               "verdict": verdict, "codebook_sha256": tx.codebook_sha256, "results": results,
               "minutes": round((time.perf_counter() - t_all) / 60, 1)}
    (out / "results.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    (out / "log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"written to {out} in {summary['minutes']} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
