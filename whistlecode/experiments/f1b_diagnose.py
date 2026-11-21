"""Why did gate test F1 fail? Stretched shapes and cover whistles, tested separately (PLAN.md section 4.6).

Every trial plays the same data whistles, at the same real bank times and pitches and in the same noise, four ways:

    native shape lengths or shapes stretched to the real whistle's length  x  without or with the cover whistles

Each data whistle is read with the true pitch given and by choosing among the four candidate pitches, as in F1.

    python whistlecode/experiments/f1b_diagnose.py [--quick]

Results: whistlecode/outputs/f1b_diagnose/results.json (gitignored).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import f1_gate as g  # noqa: E402

from wcode import channel, classify, detect, synth, transmitter  # noqa: E402
from wcode.config import PROJECT_ROOT, default_config  # noqa: E402
from wcode.contour import Contour, centred  # noqa: E402

S = g.S
CONDITIONS = [("native length, no cover", False, False), ("stretched, no cover", True, False),
              ("native length, with cover", False, True), ("stretched, with cover", True, True)]
SNRS = [10.0, 15.0]
SENDS = 100                        # per shape, per SNR
RATIOS = (0.80, 0.85, 0.90, 0.95, 1.01)      # 1.01 = never erase
LENGTH_BINS = [(0.10, 0.15), (0.15, 0.25), (0.25, 0.35), (0.35, 0.4501)]
STRETCH_BINS = [(0.0, 0.75), (0.75, 1.25), (1.25, 2.0), (2.0, 99.0)]


def render(x, on, off, is_data, freqs, hop, items, stretched, cover, snr, levels, trial_seed, tx, cfg, fs, lead):
    placed = []
    for it in items:
        c = Contour(g.stretch(it["base"].offset_hz, it["frames"]), hop) if stretched else it["base"]
        a = channel.amplitude_for_snr(snr, it["fc"] + float(c.offset_hz.mean()), levels, fs, cfg)
        g.add(x, lead + it["on"], a * synth.whistle(c, it["fc"], np.random.default_rng(it["seed"]), cfg, fs), fs)
        placed.append((it["on"], it["on"] + c.n_frames * hop, it["fc"]))
    if not cover:
        return
    lo_p, hi_p = S["cover_pitch_range_hz"]
    for j in np.where(~is_data)[0]:
        r = np.random.default_rng([trial_seed, int(j)])
        f = freqs[j]
        mid, span = 0.5 * (f.max() + f.min()), float(f.max() - f.min())
        hits = [p for a, b, p in placed if on[j] < b + S["follow_s"] and off[j] > a]
        if any(f.min() - S["collision_hz"] < p < f.max() + S["collision_hz"] for p in hits):
            for _ in range(30):
                m2 = float(r.uniform(lo_p + span / 2, hi_p - span / 2))
                if all(abs(m2 - p) >= span / 2 + S["cover_move_clearance_hz"] for p in hits):
                    mid = m2
                    break
        a = channel.amplitude_for_snr(snr + float(r.uniform(*S["cover_extra_snr_db"])), mid, levels, fs, cfg)
        g.add(x, lead + on[j], a * g.tone(Contour(centred(f), hop), mid, r, cfg, fs), fs)


def read_slots(tracks, items, lead):
    pw = float(S["pitch_window_hz"])
    ts = np.array([t.start_s for t in tracks]) if tracks else np.zeros(0)
    cs = np.array([t.centre_hz for t in tracks]) if tracks else np.zeros(0)
    ns = np.array([len(t.freq_hz) for t in tracks]) if tracks else np.zeros(0, int)
    out = []
    for it in items:
        s = lead + it["on"]
        near = (ts >= s - S["slot_early_s"]) & (ts <= s + S["slot_late_s"])
        dist = np.abs(cs[:, None] - it["cand"][None, :]) if len(cs) else np.zeros((0, 4))
        pick = lambda m: None if not m.any() else min(np.where(m)[0], key=lambda k: (abs(ts[k] - s), -ns[k]))  # noqa: B023 -- used at once
        ka = pick(near & (np.abs(cs - it["fc"]) <= pw))
        kb = pick(near & (dist.min(axis=1) <= pw)) if len(cs) else None
        hat = None if kb is None else int(np.argmin(dist[kb]))
        out.append({"shape": it["shape"], "band": it["band"], "frames": it["frames"], "native": it["base"].n_frames,
                    "overlaps": it["overlaps"], "band_hat": hat,
                    "qa": None if ka is None else tracks[ka].freq_hz - it["fc"],
                    "qb": None if kb is None else tracks[kb].freq_hz - it["cand"][hat]})
    return out


def outcomes(rows, key, dist, hit, ratio, use_pitch):
    """Per-row outcome: 0 correct, 1 missed, 2 erased, 3 wrong."""
    out = np.ones(len(rows), dtype=np.int64)
    shape = np.array([r["shape"] for r in rows])[hit]
    best, amb = classify.decide(dist, ratio) if len(dist) else (np.zeros(0, int), np.zeros(0, bool))
    wrong = best != shape
    if use_pitch:
        wrong = wrong | (np.array([r["band_hat"] for r in rows])[hit] != np.array([r["band"] for r in rows])[hit])
    res = np.where(amb, 2, np.where(wrong, 3, 0))
    out[hit] = res
    return out


def rates(o):
    n = max(1, len(o))
    missed, erased, wrong = (o == 1).sum() / n, (o == 2).sum() / n, (o == 3).sum() / n
    return {"n": int(len(o)), "missed": float(missed), "erased": float(erased), "wrong": float(wrong),
            "lost": float(missed + erased), "budget": float(missed + erased + 2 * wrong)}


def analyse(rows, stretched, templates, cfg, hop):
    ratio = float(cfg["classify"]["ambiguity_ratio"])
    frames = np.array([r["frames"] for r in rows])
    res = {}
    keep = {}
    for key, use_pitch in (("qa", False), ("qb", True)):
        hit = np.array([r[key] is not None for r in rows])
        q = [r[key] for r in rows if r[key] is not None]
        if stretched:
            dist = g.stretched_distances(q, frames[hit], templates, cfg)
        else:
            dist = classify.distances([Contour(a, hop) for a in q], templates, cfg)
        o = outcomes(rows, key, dist, hit, ratio, use_pitch)
        name = "true_pitch" if key == "qa" else "four_pitches"
        res[name] = rates(o)
        res[name]["by_ratio"] = {f"{r:.2f}": rates(outcomes(rows, key, dist, hit, r, use_pitch)) for r in RATIOS}
        keep[name] = o
    hit = np.array([r["band_hat"] is not None for r in rows])
    res["wrong_pitch_rate"] = float(np.mean([r["band_hat"] != r["band"] for r in rows if r["band_hat"] is not None])) if hit.any() else 1.0
    o = keep["true_pitch"]
    lengths = frames * hop
    factor = frames / np.array([r["native"] for r in rows])
    ov = np.array([r["overlaps"] for r in rows])
    res["by_real_length_ms"] = {f"{int(a * 1000)}-{int(round(b * 1000))}": rates(o[(lengths >= a) & (lengths < b)]) for a, b in LENGTH_BINS}
    res["by_stretch_factor"] = {f"{a:g}-{b:g}": rates(o[(factor >= a) & (factor < b)]) for a, b in STRETCH_BINS}
    res["by_cover_overlap"] = {"no cover whistle overlapping": rates(o[ov == 0]), "1 or more overlapping": rates(o[ov > 0])}
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quick", action="store_true", help="a small check run at 15 dB")
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")
    t_all = time.perf_counter()
    cfg = default_config()
    out = PROJECT_ROOT / "whistlecode" / "outputs" / ("f1b_diagnose_quick" if args.quick else "f1b_diagnose")
    out.mkdir(parents=True, exist_ok=True)
    lines = []

    def log(m):
        lines.append(m)
        print(m, flush=True)

    snrs = [15.0] if args.quick else SNRS
    sends = 3 if args.quick else SENDS
    pool_n = 8 if args.quick else int(S["shape_pool_per_type"])
    rng = np.random.default_rng(int(S["seed"]) + 1)
    tx = transmitter.Transmitter(cfg)
    det = detect.Detector(cfg)
    banks = {e: g.Bank(e) for e in S["bank_encounters"]}
    log(f"drawing {pool_n} varied shapes per type")
    drawn, _, _ = tx._shapes(np.repeat(np.arange(16), pool_n), float(cfg["transmit"]["tau"]), rng)
    shapes = [drawn[i * pool_n:(i + 1) * pool_n] for i in range(16)]
    templates = [t.contour for t in tx.cb.types]
    noise = g.Noise(cfg, tx.pcfg, rng)
    fs, lead = float(cfg["synth"]["fs_hz"]), float(S["stretch_start_s"])
    results = {}
    for snr in snrs:
        t0 = time.perf_counter()
        d = g.deck(sends, rng)
        rows = {name: [] for name, _, _ in CONDITIONS}
        order = {e: [int(i) for i in rng.permutation(len(b.windows))] for e, b in banks.items()}
        which, trials = 0, 0
        while d:
            e = list(banks)[which % len(banks)]
            which += 1
            b = banks[e]
            s0, idx = b.windows[order[e].pop()]
            on, off = b.on[idx] - s0, b.off[idx] - s0
            slots = g.data_slots(on, off)
            if len(slots) == 0:
                continue
            base_x, levels, _ = noise.next(frozenset(b.source[idx].tolist()))
            is_data = np.zeros(len(on), bool)
            is_data[slots] = True
            freqs = [b.freq[i] for i in idx]
            trial_seed = int(rng.integers(2 ** 31))
            items = []
            for i in slots:
                if not d:
                    break
                s = d.pop()
                cand = np.quantile(tx.pool, (np.arange(4) + float(rng.random())) / 4)
                band = int(rng.integers(4))
                items.append({"on": float(on[i]), "shape": s, "band": band, "cand": cand, "fc": float(cand[band]),
                              "frames": g.frames_of(off[i] - on[i], b.hop), "base": shapes[s][int(rng.integers(len(shapes[s])))],
                              "seed": int(rng.integers(2 ** 31)),
                              "overlaps": int(((on < off[i]) & (off > on[i]) & ~is_data).sum())})
            for name, stretched, cover in CONDITIONS:
                x = base_x.copy()
                render(x, on, off, is_data, freqs, b.hop, items, stretched, cover, snr, levels, trial_seed, tx, cfg, fs, lead)
                rows[name] += read_slots(det.tracks(x, fs), items, lead)
            trials += 1
            if trials % 10 == 0:
                log(f"  {snr:g} dB: {trials} trials, {len(d)} data whistles to go")
        results[f"{snr:g}"] = {name: analyse(rows[name], st, templates, cfg, b.hop) for name, st, _ in CONDITIONS}
        results[f"{snr:g}"]["trials"] = trials
        log(f"{snr:g} dB finished: {trials} trials in {time.perf_counter() - t0:.0f} s")

    ref = {}
    f1 = PROJECT_ROOT / "whistlecode" / "outputs" / "f1_gate" / "results.json"
    if f1.exists():
        ref = json.loads(f1.read_text(encoding="utf-8"))["results"]
    for snr in snrs:
        r = results[f"{snr:g}"]
        log(f"\n=== {snr:g} dB ({r['trials']} paired trials) ===")
        if f"{snr:g}" in ref:
            v = ref[f"{snr:g}"]["v1"]
            log(f"format v1 reference: lost {v['lost_rate']:.1%}, wrong {v['wrong_rate']:.1%}, repair budget {v['lost_rate'] + 2 * v['wrong_rate']:.3f}")
        log(f"{'condition':28s} {'missed':>7s} {'erased':>7s} {'wrong':>7s} {'budget':>7s} | four pitches: {'lost':>6s} {'wrong':>6s} {'budget':>7s} {'wrong pitch':>11s} | predicted 12/20/60 chars")
        for name, _, _ in CONDITIONS:
            a, b = r[name]["true_pitch"], r[name]["four_pitches"]
            p = [g.success_v2(c, b["lost"], b["wrong"]) for c in S["message_chars"]]
            r[name]["predicted_v2"] = dict(zip(map(str, S["message_chars"]), p))
            log(f"{name:28s} {a['missed']:7.1%} {a['erased']:7.1%} {a['wrong']:7.1%} {a['budget']:7.3f} |               {b['lost']:6.1%} {b['wrong']:6.1%} {b['budget']:7.3f} {r[name]['wrong_pitch_rate']:11.2%} | "
                + " / ".join(f"{x:.0%}" for x in p))
        for name, _, _ in CONDITIONS:
            br = r[name]["true_pitch"]["by_ratio"]
            log(f"  repair budget by erasure ratio, {name}: " + "  ".join(f"{k}: {v['budget']:.3f}" for k, v in br.items()))
        for name in ("stretched, no cover", "stretched, with cover"):
            log(f"  {name}, by real whistle length (true pitch given):")
            for k, v in r[name]["by_real_length_ms"].items():
                log(f"    {k:>9s} ms: n {v['n']:4d}  lost {v['lost']:6.1%}  wrong {v['wrong']:6.1%}  budget {v['budget']:.3f}")
            log(f"  {name}, by stretch factor (real length / shape's own length):")
            for k, v in r[name]["by_stretch_factor"].items():
                log(f"    {k:>9s}   : n {v['n']:4d}  lost {v['lost']:6.1%}  wrong {v['wrong']:6.1%}  budget {v['budget']:.3f}")
        for name in ("native length, with cover", "stretched, with cover"):
            log(f"  {name}, by cover whistles overlapping in time (true pitch given):")
            for k, v in r[name]["by_cover_overlap"].items():
                log(f"    {k:30s}: n {v['n']:4d}  lost {v['lost']:6.1%}  wrong {v['wrong']:6.1%}  budget {v['budget']:.3f}")
    summary = {"quick": args.quick, "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sends_per_shape": sends,
               "codebook_sha256": tx.codebook_sha256, "results": results, "minutes": round((time.perf_counter() - t_all) / 60, 1)}
    (out / "results.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    (out / "log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"\nwritten to {out} in {summary['minutes']} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
