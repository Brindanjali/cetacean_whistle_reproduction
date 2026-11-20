"""Covertness tests for the paper (PLAN.md section 8.5): can our whistles, or their timing, be told from real ones?

Part 1, whistle shapes [E7]. Real whistles of encounter 276, which no part of the sender has used, are detected in the raw
recordings. Coded data whistles are sent through encounter-214 noise at 15 and 20 dB and picked up by the same detector. Both
sides are restricted to the same range (100-450 ms, centre 5-12 kHz), balanced by signal-to-noise band, and split by recording
or message so no test whistle shares a recording with a training whistle (experiments/realism_score.py, unchanged). Reported:

- the discriminator score (ROC AUC of gradient boosting on 14 shape, loudness and harmonic features; 0.50 = cannot tell);
- the Wasserstein-1 distance of each of the reproduction's 7 contour features (L, f_min, f_max, df, f_start, f_end, f_c);
- the same for real encounter-214 whistles, the score two real encounters get.

Senders compared, all on the same fresh messages: WhistleCode as deployed (tau 0.5), tau 0.25 / 0.75 / 1.0, the sender without
the realism library ("plain"), and the chirp baseline.

Part 2, rhythm [E9]. 44 s windows of detected tracks, 11 timing features (experiments/f1_gate.py, unchanged). A classifier is
trained on real encounter-214 windows against coded windows of half the messages and tested on real encounter-276 windows
against coded windows of the other half, then the halves swap. Coded windows come from the campaign's saved tracks
(paper_eval.py): the message alone ("clean") and inside encounter-276 noise at 10 dB ("final"; trained on snr214 at 10 dB).
A positive control replays format v1's steady 0.55-0.95 s gaps as timing only.

    python whistlecode/experiments/paper_covert.py shapes [--quick]
    python whistlecode/experiments/paper_covert.py rhythm

Results: whistlecode/outputs/paper/covert_shapes.json and covert_rhythm.json (gitignored).
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.stats import wasserstein_distance
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

WC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WC))
sys.path.insert(0, str(WC / "experiments"))

import f1_gate  # noqa: E402
import paper_eval  # noqa: E402
import realism_score as rs  # noqa: E402
from wcode import baseline, channel, detect, realism, sender  # noqa: E402
from wcode.config import PROJECT_ROOT, default_config  # noqa: E402

OUT = PROJECT_ROOT / "whistlecode" / "outputs" / "paper"
BASIC = ("L_ms", "f_min_hz", "f_max_hz", "df_hz", "f_start_hz", "f_end_hz", "f_c_hz")
SPAN_HZ = (300.0, 5000.0)          # [PLAN] 8.5: in-range real whistles also span 0.3-5 kHz
TAUS = (0.25, 0.75, 1.0)


# ---------------------------------------------------------------------------------------------- part 1: whistle shapes
def basic7(t: detect.Track) -> list[float]:
    f = np.asarray(t.freq_hz, dtype=np.float64)
    lo, hi = float(f.min()), float(f.max())
    return [t.duration_ms, lo, hi, hi - lo, float(f[0]), float(f[-1]), 0.5 * (lo + hi)]


def in_range(t: detect.Track) -> bool:
    f = np.asarray(t.freq_hz)
    return SPAN_HZ[0] <= float(f.max() - f.min()) <= SPAN_HZ[1]


def real_whistles(encounter: int, det: detect.Detector, cfg: dict, pcfg, n_files: int) -> list[tuple]:
    """(14 features, SNR, group, 7 basic features) of each in-range real whistle (realism_score.real_rows, plus basic7)."""
    files = channel.noise_files(encounter)
    rows = []
    for g, i in enumerate(np.linspace(0, len(files) - 1, n_files).astype(int).tolist()):
        x = channel.load_noise(files[i], cfg, pcfg)
        mag, floor = rs.spectrum(x)
        for t in det.tracks(x, realism.FS):
            got = rs.features(t, mag, floor)
            if got is not None and in_range(t):
                rows.append((got[0], got[1], f"{encounter}-{g}", basic7(t)))
    return rows


def coded_whistles(name: str, tx: sender.Sender, det: detect.Detector, cfg: dict, n_messages: int) -> list[tuple]:
    """The same as realism_score.coded_rows, with fresh messages and the basic features kept."""
    rng = np.random.default_rng([paper_eval.SEED, 11])
    alphabet = np.array(list(cfg["format2"]["alphabet"]))
    rows = []
    for snr in rs.S["snr_db"]:
        for m in range(n_messages):
            text = "".join(rng.choice(alphabet, int(rs.S["message_chars"])))
            seed = int(rng.integers(2 ** 31))
            sent = tx.send(text, f"covert-{seed}", seed % 256)
            heard = channel.through_channel(sent.audio, sent.fs, snr, tx.pool, seed=seed, cfg=cfg, pcfg=tx.pcfg)
            start = heard.offset_s + sent.lead_in_s
            tracks = det.tracks(heard.audio, heard.fs)
            t0 = np.array([t.start_s for t in tracks])
            fc = np.array([t.centre_hz for t in tracks])
            mag, floor = rs.spectrum(heard.audio)
            for d in sent.data:
                at = start + d.slot.start_s
                ok = np.where((t0 >= at - rs.S["slot_early_s"]) & (t0 <= at + rs.S["slot_late_s"]) & (np.abs(fc - d.fc_hz) <= rs.S["pitch_window_hz"]))[0]
                if len(ok):
                    t = tracks[int(ok[np.argmin(np.abs(t0[ok] - at))])]
                    got = rs.features(t, mag, floor)
                    if got is not None and in_range(t):
                        rows.append((got[0], got[1], f"{name}-{snr:g}-{m}", basic7(t)))
    return rows


def w1(real: list[tuple], other: list[tuple]) -> dict:
    a, b = np.array([r[3] for r in real]), np.array([r[3] for r in other])
    return {k: round(float(wasserstein_distance(a[:, j], b[:, j])), 2) for j, k in enumerate(BASIC)}


def shapes(quick: bool) -> int:
    cfg = default_config()
    t_all = time.perf_counter()
    n_files, n_messages, splits = (6, 2, 2) if quick else (int(rs.S["real_files"]), int(rs.S["messages_per_snr"]), int(rs.S["splits"]))
    rs.S["seed"] = paper_eval.SEED                 # fresh splits as well as fresh messages
    det = detect.Detector(cfg)
    deployed = sender.Sender(cfg)
    b = deployed.bank
    senders = {"whistlecode": (deployed, cfg)}
    for tau in TAUS:
        c = copy.deepcopy(cfg)
        c["transmit"]["tau"] = tau
        senders[f"tau_{tau:g}"] = (sender.Sender(c, rhythm_bank=b, library=deployed.library), c)
    plain_cfg = copy.deepcopy(cfg)
    plain_cfg["realism"]["enabled"] = False
    senders["plain"] = (sender.Sender(plain_cfg, rhythm_bank=b), plain_cfg)
    bcfg = baseline.config(cfg)
    senders["baseline"] = (sender.Sender(bcfg, codebook_path=baseline.build(cfg), check_model=False, rhythm_bank=b), bcfg)

    print("collecting real whistles", flush=True)
    real = real_whistles(276, det, cfg, deployed.pcfg, n_files)
    reference = real_whistles(214, det, cfg, deployed.pcfg, n_files)
    print(f"  encounter 276: {len(real)}, encounter 214: {len(reference)} in-range whistles", flush=True)
    sides = {"real_214": reference}
    for name, (tx, c) in senders.items():
        t = time.perf_counter()
        sides[name] = coded_whistles(name, tx, det, c, n_messages)
        print(f"  {name}: {len(sides[name])} data whistles [{(time.perf_counter() - t) / 60:.1f} min]", flush=True)
    results = {}
    for name, rows in sides.items():
        s = rs.score([r[:3] for r in real], [r[:3] for r in rows], splits)
        results[name] = {**s, "whistles": len(rows), "w1": w1(real, rows)}
        print(f"{name:12s} AUC {s['score']:.3f} +/- {s['spread']:.3f}  W1 {results[name]['w1']}", flush=True)
    out = OUT.with_name(OUT.name + ("_quick" if quick else ""))
    out.mkdir(parents=True, exist_ok=True)
    summary = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "quick": quick, "settings": rs.S,
               "real_encounter_276_whistles": len(real), "span_hz": SPAN_HZ, "features": rs.FEATURES, "basic_features": BASIC,
               "results": results, "minutes": round((time.perf_counter() - t_all) / 60, 1)}
    (out / "covert_shapes.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"written to {out / 'covert_shapes.json'} in {summary['minutes']} min")
    return 0


# ---------------------------------------------------------------------------------------------- part 2: rhythm
def real_windows(encounter: int) -> np.ndarray:
    bk = f1_gate.Bank(encounter)
    return np.array([f1_gate.rhythm_features(bk.on[idx] - s, bk.off[idx] - s) for s, idx in bk.windows])


def coded_windows(exp: str, cond_index: int | None = None) -> list[tuple[int, list[float]]]:
    """(message index, features) of every 44 s window inside each received message of a campaign experiment."""
    d = OUT / exp
    rows = [json.loads(s) for s in (d / "trials.jsonl").read_text(encoding="utf-8").splitlines() if s.strip()]
    out = []
    for r in rows:
        if "error" in r or (cond_index is not None and r["cond_index"] != cond_index):
            continue
        tracks = paper_eval.load_tracks(d / "tracks" / f"{r['cond_index']:02d}_{r['msg_index']:03d}.npz")
        on = np.array([t.start_s for t in tracks])
        off = np.array([t.start_s + len(t.freq_hz) * t.hop_s for t in tracks])
        s, end = float(r["true_start_s"]), float(r["true_start_s"]) + float(r["duration_s"])
        while s + f1_gate.WIN <= end:
            k = (on >= s) & (on < s + f1_gate.WIN)
            if k.sum() >= int(f1_gate.S["min_whistles_per_window"]):
                out.append((int(r["msg_index"]), f1_gate.rhythm_features(on[k] - s, off[k] - s)))
            s += f1_gate.WIN
    return out


def steady_windows(n: int, rng: np.random.Generator) -> list[tuple[int, list[float]]]:
    """Format v1 timing: starts 0.55-0.95 s apart, codebook lengths (19-78 frames), as timing only."""
    hop = 1024 / 192000
    out = []
    for i in range(n):
        on = np.cumsum(rng.uniform(0.55, 0.95, 80))
        on = on[on < f1_gate.WIN]
        off = on + rng.integers(19, 79, len(on)) * hop
        out.append((i, f1_gate.rhythm_features(on, off)))
    return out


def auc_two_halves(real_train: np.ndarray, coded_train: list, real_test: np.ndarray, coded_test: list) -> dict:
    scores = []
    for half in (0, 1):
        ctr = np.array([f for m, f in coded_train if m % 2 == half])
        cte = np.array([f for m, f in coded_test if m % 2 != half])
        X = np.vstack([real_train, ctr])
        y = np.r_[np.zeros(len(real_train)), np.ones(len(ctr))]
        model = HistGradientBoostingClassifier(max_depth=3, max_iter=150, random_state=0, class_weight="balanced").fit(X, y)
        p = model.predict_proba(np.vstack([real_test, cte]))[:, 1]
        scores.append(float(roc_auc_score(np.r_[np.zeros(len(real_test)), np.ones(len(cte))], p)))
    return {"score": float(np.mean(scores)), "halves": scores, "coded_train_windows": len(coded_train),
            "coded_test_windows": len(coded_test), "real_train_windows": int(len(real_train)), "real_test_windows": int(len(real_test))}


def rhythm() -> int:
    r214, r276 = real_windows(214), real_windows(276)
    print(f"real windows: 214 {len(r214)}, 276 {len(r276)}", flush=True)
    results = {}
    clean = coded_windows("clean")
    results["alone"] = auc_two_halves(r214, clean, r276, clean)
    noisy_train = coded_windows("snr214", paper_eval.SWEEP_SNRS.index(10.0))
    noisy_test = coded_windows("final")
    results["in_noise_10dB"] = auc_two_halves(r214, noisy_train, r276, noisy_test)
    rng = np.random.default_rng([paper_eval.SEED, 12])
    results["steady_v1_control"] = auc_two_halves(r214, steady_windows(200, rng), r276, steady_windows(200, rng))
    for k, v in results.items():
        print(f"{k:20s} AUC {v['score']:.3f} (halves {v['halves'][0]:.3f}, {v['halves'][1]:.3f}); coded windows {v['coded_test_windows']}")
    summary = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "window_s": f1_gate.WIN,
               "features": ["rate per min", "median gap", "gap CV", "burstiness", "local variation", "gap p10", "gap p90",
                            "longest silence", "busy fraction", "overlap fraction", "clumping"],
               "pass_mark": 0.60, "results": results}
    (OUT / "covert_rhythm.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(f"written to {OUT / 'covert_rhythm.json'}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=("shapes", "rhythm"))
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")
    return shapes(args.quick) if args.command == "shapes" else rhythm()


if __name__ == "__main__":
    sys.exit(main())
