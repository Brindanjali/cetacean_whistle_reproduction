"""How easily can a trained detector tell our data whistles from real whistles? 0.50 = it cannot, 1.00 = it always can.

Real whistles come from encounter 276, which no part of the sender has used. Our data whistles are sent through real encounter-214
noise and picked up by the same detector. Both sides are compared like with like: the same length and pitch range, the same
spread of signal-to-noise ratios, and no absolute level or noise feature.

Three scores are reported:
  plain     the sender before the realism upgrade against encounter 276
  upgraded  the sender with real shapes, voices, animals and clicks against encounter 276
  real      real whistles of encounter 214 against encounter 276: the score two real encounters get, so the lowest to expect

    python whistlecode/experiments/realism_score.py [--quick]

Results: whistlecode/outputs/realism_score[_quick]/results.json (gitignored).
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import signal
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

WC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WC))

from wcode import channel, detect, realism, sender  # noqa: E402
from wcode.config import PROJECT_ROOT, default_config  # noqa: E402

SETTINGS = {"real_encounter": 276, "reference_encounter": 214, "real_files": 40, "messages_per_snr": 12, "snr_db": [15.0, 20.0],
            "message_chars": 60, "duration_ms": [100.0, 450.0], "centre_hz": [5000.0, 12000.0], "snr_bins_db": [10, 15, 20, 25, 30, 45],
            "splits": 5, "slot_early_s": 0.06, "slot_late_s": 0.15, "pitch_window_hz": 500.0, "seed": 20261118}
S = SETTINGS
FEATURES = ["duration", "span", "centre", "mean slope", "slope changes", "contour roughness", "net rise", "curve fit error",
            "loudness depth", "loudness roughness", "loudness tilt", "2nd harmonic", "3rd harmonic", "2nd harmonic change"]


def spectrum(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    _, _, z = signal.stft(np.asarray(x, dtype=np.float32), realism.FS, window="hann", nperseg=realism.NFFT,
                          noverlap=realism.NFFT - realism.HOP, boundary=None, padded=False)
    mag = np.abs(z) * 2
    return mag, np.maximum(np.median(mag, axis=1), 1e-12)


def features(t: detect.Track, mag: np.ndarray, floor: np.ndarray) -> tuple[list[float], float] | None:
    """(feature vector, median level above the noise in dB) of one detected whistle; None when it is out of the compared range."""
    f = np.asarray(t.freq_hz, dtype=np.float64)
    lo, hi = S["duration_ms"]
    c_lo, c_hi = S["centre_hz"]
    if len(f) < 8 or not lo <= t.duration_ms <= hi or not c_lo <= t.centre_hz <= c_hi:
        return None
    frames = np.round(t.start_s * realism.FS / realism.HOP + np.arange(len(f))).astype(np.int64)
    if frames[0] < 0 or frames[-1] >= mag.shape[1]:
        return None
    amps, levels = [], []
    for k in (1, 2, 3):
        centre = np.clip(np.round(k * f / realism.BIN_HZ).astype(np.int64), 1, mag.shape[0] - 2)
        amps.append(np.max([mag[centre + d, frames] for d in (-1, 0, 1)], axis=0))
        levels.append(floor[centre])
    a1 = np.maximum(amps[0], 1e-12)
    snr_db = float(np.median(20 * np.log10(a1 / levels[0])))
    env = 20 * np.log10(a1 / np.median(a1))
    h = [np.clip(20 * np.log10(np.maximum(amps[k], 1e-12) / a1), -40.0, 10.0) for k in (1, 2)]
    slope = np.diff(f) / t.hop_s
    smooth = np.convolve(slope, np.ones(5) / 5, "same")
    span = float(f.max() - f.min())
    x = np.arange(len(f)) / len(f)
    fit = np.polyval(np.polyfit(x, f, 3), x)
    third = max(1, len(env) // 3)
    return [t.duration_ms, span, t.centre_hz, float(np.mean(np.abs(slope))), float(np.mean(np.diff(np.sign(smooth)) != 0)),
            float(np.std(np.diff(f, 2))), float((f[-1] - f[0]) / max(span, 1.0)), float(np.std(f - fit)),
            float(np.percentile(env, 90) - np.percentile(env, 10)), float(np.std(np.diff(env))),
            float(np.mean(env[-third:]) - np.mean(env[:third])), float(np.median(h[0])), float(np.median(h[1])),
            float(np.std(h[0]))], snr_db


def real_rows(encounter: int, det: detect.Detector, cfg: dict, pcfg, n_files: int, log) -> list[tuple]:
    files = channel.noise_files(encounter)
    rows = []
    for g, i in enumerate(np.linspace(0, len(files) - 1, n_files).astype(int).tolist()):
        x = channel.load_noise(files[i], cfg, pcfg)
        mag, floor = spectrum(x)
        for t in det.tracks(x, realism.FS):
            got = features(t, mag, floor)
            if got is not None:
                rows.append((got[0], got[1], f"{encounter}-{g}"))
    log(f"  encounter {encounter}: {len(rows)} real whistles from {n_files} recordings")
    return rows


def coded_rows(name: str, tx: sender.Sender, det: detect.Detector, cfg: dict, n_messages: int, log) -> list[tuple]:
    rng = np.random.default_rng(int(S["seed"]))
    alphabet = np.array(list(cfg["format2"]["alphabet"]))
    rows = []
    for snr in S["snr_db"]:
        for m in range(n_messages):
            text = "".join(rng.choice(alphabet, int(S["message_chars"])))
            seed = int(rng.integers(2 ** 31))
            sent = tx.send(text, f"score-{seed}", seed % 256)
            heard = channel.through_channel(sent.audio, sent.fs, snr, tx.pool, seed=seed, cfg=cfg, pcfg=tx.pcfg)
            start = heard.offset_s + sent.lead_in_s
            tracks = det.tracks(heard.audio, heard.fs)
            t0 = np.array([t.start_s for t in tracks])
            fc = np.array([t.centre_hz for t in tracks])
            mag, floor = spectrum(heard.audio)
            for d in sent.data:
                at = start + d.slot.start_s
                ok = np.where((t0 >= at - S["slot_early_s"]) & (t0 <= at + S["slot_late_s"]) & (np.abs(fc - d.fc_hz) <= S["pitch_window_hz"]))[0]
                if len(ok):
                    got = features(tracks[int(ok[np.argmin(np.abs(t0[ok] - at))])], mag, floor)
                    if got is not None:
                        rows.append((got[0], got[1], f"{name}-{snr:g}-{m}"))
    log(f"  {name}: {len(rows)} data whistles from {2 * n_messages} messages")
    return rows


def matched(a: list[tuple], b: list[tuple], rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Equal numbers of both sides in every signal-to-noise band: (features, labels)."""
    edges = np.array(S["snr_bins_db"], dtype=np.float64)
    bins = [np.digitize([r[1] for r in side], edges) for side in (a, b)]
    X, y = [], []
    for k in range(1, len(edges)):
        ia, ib = np.flatnonzero(bins[0] == k), np.flatnonzero(bins[1] == k)
        n = min(len(ia), len(ib))
        if n:
            X += [a[int(i)][0] for i in rng.choice(ia, n, replace=False)] + [b[int(i)][0] for i in rng.choice(ib, n, replace=False)]
            y += [0] * n + [1] * n
    return np.array(X, dtype=np.float64), np.array(y)


def score(real: list[tuple], other: list[tuple], splits: int) -> dict:
    """Train on half of the recordings and messages, test on the other half."""
    aucs, importance = [], np.zeros(len(FEATURES))
    for s in range(splits):
        rng = np.random.default_rng(int(S["seed"]) + s)
        parts = []
        for side in (real, other):
            groups = sorted({r[2] for r in side})
            test = set(rng.permutation(groups)[:len(groups) // 2].tolist())
            parts.append(([r for r in side if r[2] not in test], [r for r in side if r[2] in test]))
        Xtr, ytr = matched(parts[0][0], parts[1][0], rng)
        Xte, yte = matched(parts[0][1], parts[1][1], rng)
        m = HistGradientBoostingClassifier(max_depth=4, max_iter=200, learning_rate=0.08, random_state=s).fit(Xtr, ytr)
        base = roc_auc_score(yte, m.predict_proba(Xte)[:, 1])
        aucs.append(float(base))
        for j in range(len(FEATURES)):
            shuffled = Xte.copy()
            shuffled[:, j] = rng.permutation(shuffled[:, j])
            importance[j] += (base - roc_auc_score(yte, m.predict_proba(shuffled)[:, 1])) / splits
    top = np.argsort(-importance)[:4]
    return {"score": float(np.mean(aucs)), "spread": float(np.std(aucs)), "test_whistles": int(len(yte)),
            "main_clues": [{"feature": FEATURES[int(i)], "score_drop": round(float(importance[int(i)]), 3)} for i in top]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quick", action="store_true", help="a small run, to check that everything works")
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")
    t_all = time.perf_counter()
    out = PROJECT_ROOT / "whistlecode" / "outputs" / ("realism_score" + ("_quick" if args.quick else ""))
    out.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []

    def log(m: str) -> None:
        lines.append(m)
        print(m, flush=True)

    n_files, n_messages, splits = (6, 2, 2) if args.quick else (int(S["real_files"]), int(S["messages_per_snr"]), int(S["splits"]))
    cfg = default_config()
    plain_cfg = copy.deepcopy(cfg)
    plain_cfg["realism"]["enabled"] = False
    upgraded = sender.Sender(cfg)
    plain = sender.Sender(plain_cfg, rhythm_bank=upgraded.bank)
    det = detect.Detector(cfg)
    log("collecting whistles")
    real = real_rows(int(S["real_encounter"]), det, cfg, upgraded.pcfg, n_files, log)
    reference = real_rows(int(S["reference_encounter"]), det, cfg, upgraded.pcfg, n_files, log)
    sides = {"plain": coded_rows("plain", plain, det, plain_cfg, n_messages, log),
             "upgraded": coded_rows("upgraded", upgraded, det, cfg, n_messages, log), "real": reference}
    results = {name: score(real, rows, splits) for name, rows in sides.items()}
    log("\n=== detection score against real encounter-276 whistles (0.50 = cannot tell them apart) ===")
    labels = {"plain": "sender before the upgrade", "upgraded": "upgraded sender", "real": "real encounter-214 whistles (reference)"}
    for name, r in results.items():
        clues = ", ".join(f"{c['feature']} ({c['score_drop']:.3f})" for c in r["main_clues"])
        log(f"{labels[name]:<42} {r['score']:.3f} +/- {r['spread']:.3f}   main clues: {clues}")
    summary = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "quick": args.quick, "settings": S, "results": results,
               "minutes": round((time.perf_counter() - t_all) / 60, 1)}
    (out / "results.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    (out / "log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"written to {out} in {summary['minutes']} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
