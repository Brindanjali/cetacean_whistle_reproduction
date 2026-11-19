"""How the complete pipeline copes with the simulated sea (PLAN.md section 6).

The same 90 messages as e2e_run.py are sent under four conditions, all in encounter-276 noise, which the receiver was never tuned on:

    noise    ocean noise only
    echoes   echoes and absorption
    doppler  Doppler only
    all      echoes, absorption and Doppler

Every message keeps one random sea (range, depths, speed) under all four conditions, so differences between them come from the
effect that was switched on. There is no pass mark: the run measures how much of the noise-only result survives.

    python whistlecode/experiments/sea_run.py [--quick] [--trials 10] [--conditions noise echoes doppler all] [--tag name]

Results: whistlecode/outputs/sea_run[_tag]/results.json, trials.jsonl and log.txt (gitignored).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from pathlib import Path

import numpy as np

WC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WC))
sys.path.insert(0, str(WC / "experiments"))

import e2e_run  # noqa: E402
from wcode import detect, receiver, sea, sender  # noqa: E402
from wcode.config import PROJECT_ROOT, default_config  # noqa: E402

NOISE_ENCOUNTER = 276
CONDITIONS = {"noise": (False, False), "echoes": (True, False), "doppler": (False, True), "all": (True, True)}
DRIFT_BINS_MS = ((0.0, 30.0), (30.0, 60.0), (60.0, 150.0), (150.0, float("inf")))   # the receiver allows 60 ms early, 150 ms late


def messages(snrs: tuple, trials: int) -> list[dict]:
    """The messages of e2e_run.py, drawn in the same order from the same seed."""
    rng = np.random.default_rng(20261118)
    out = []
    for snr in snrs:
        for length in e2e_run.LENGTHS:
            for _ in range(trials):
                seed = int(rng.integers(2 ** 31))
                out.append({"snr": snr, "length": length, "seed": seed, "text": e2e_run.make_text(length, rng)})
    return out


def sea_for(condition: str, seed: int, cfg: dict) -> sea.Sea | None:
    echoes, doppler = CONDITIONS[condition]
    if not (echoes or doppler):
        return None
    s = sea.draw(np.random.default_rng([seed, 20261119]), cfg)
    return dataclasses.replace(s, echoes=echoes, speed_mps=s.speed_mps if doppler else 0.0)


def count(rows: list[dict]) -> str:
    return f"{sum(r['exact'] for r in rows)}/{len(rows)}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quick", action="store_true", help="one message per length at 15 dB")
    ap.add_argument("--trials", type=int, default=10, help="messages per SNR and length")
    ap.add_argument("--conditions", nargs="+", choices=tuple(CONDITIONS), default=list(CONDITIONS))
    ap.add_argument("--tag", default="", help="suffix of the output folder")
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")
    cfg = default_config()
    name = "sea_run" + (f"_{args.tag}" if args.tag else "") + ("_quick" if args.quick else "")
    out = PROJECT_ROOT / "whistlecode" / "outputs" / name
    out.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []

    def log(m: str) -> None:
        lines.append(m)
        print(m, flush=True)

    snrs, trials = ((15.0,), 1) if args.quick else (e2e_run.SNRS, args.trials)
    todo = messages(snrs, trials)
    tx = sender.Sender(cfg)
    rx = receiver.Receiver(cfg, rhythm_bank=tx.bank, detector=detect.Detector(cfg))
    c = float(cfg["sea"]["sound_speed_mps"])
    rows: list[dict] = []
    t0 = time.perf_counter()
    with open(out / "trials.jsonl", "w", encoding="utf-8") as f:
        for condition in args.conditions:
            for i, m in enumerate(todo):
                state = sea_for(condition, m["seed"], cfg)
                r = e2e_run.one_trial(tx, rx, m["text"], f"trial-{m['seed']}", m["snr"], m["seed"], cfg, NOISE_ENCOUNTER, state)
                r["condition"] = condition
                r["sea"] = dataclasses.asdict(state) if state is not None else None
                r["drift_ms"] = 1000.0 * (state.speed_mps / c if state is not None else 0.0) * r["duration_s"]    # + = heard early
                rows.append(r)
                f.write(json.dumps(r) + "\n")
                f.flush()
                log(f"{condition}, {m['snr']:g} dB, {m['length']} chars, {i + 1}/{len(todo)}: {'OK' if r['exact'] else 'FAILED at ' + r['stage']}; "
                    f"{r['n_lost']} lost, {r['n_wrong']} wrong of {r['n_data']}; drift {r['drift_ms']:+.0f} ms  "
                    f"[{(time.perf_counter() - t0) / 60:.1f} min]")
    empties = [e2e_run.no_message_trial(tx, rx, f"empty-{i}", 2000 + i, cfg, NOISE_ENCOUNTER) for i in range(2 if args.quick else 10)]

    log("\n=== results ===")
    table = {}
    for condition in args.conditions:
        part = [r for r in rows if r["condition"] == condition]
        s = e2e_run.summarise(part)
        by_snr = {f"{snr:g}": count([r for r in part if r["snr_db"] == snr]) for snr in snrs}
        by_length = {str(n): count([r for r in part if r["text_length"] == n]) for n in e2e_run.LENGTHS}
        entry = {**s, "by_snr": by_snr, "by_length": by_length}
        log(f"{condition:8s}: {s['exact']}/{s['trials']} exact ({' / '.join(by_snr.values())} at {' / '.join(by_snr)} dB; "
            f"{' / '.join(by_length.values())} for {' / '.join(by_length)} chars), frame found {s['frame_found']}/{s['trials']}, "
            f"lost {s['lost_rate']:.1%}, wrong {s['wrong_rate']:.1%}, failed at {s['failed_at']}")
        if CONDITIONS[condition][0]:
            km = sorted({r["sea"]["range_m"] / 1000.0 for r in part})
            entry["by_range_km"] = {f"{k:g}": count([r for r in part if r["sea"]["range_m"] / 1000.0 == k]) for k in km}
            log(f"          by range: " + ", ".join(f"{k} km {v}" for k, v in entry["by_range_km"].items()))
        if CONDITIONS[condition][1]:
            entry["by_drift_ms"] = {f"{lo:g}-{hi:g}": count([r for r in part if lo <= abs(r["drift_ms"]) < hi]) for lo, hi in DRIFT_BINS_MS}
            entry["closing"] = count([r for r in part if r["drift_ms"] > 0])
            entry["opening"] = count([r for r in part if r["drift_ms"] <= 0])
            log("          by timing drift over the message: " + ", ".join(f"{k} ms {v}" for k, v in entry["by_drift_ms"].items()))
            log(f"          closing {entry['closing']}, moving apart {entry['opening']}")
        table[condition] = entry
    bad = sum(r["ok"] and not r["exact"] for r in rows)
    false_msgs = sum(e["false_message"] for e in empties)
    log(f"wrong text accepted: {bad} of {len(rows)} messages; messages reported in recordings with none: {false_msgs} of {len(empties)}")
    summary = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "quick": args.quick, "trials_per_setting": trials,
               "noise_encounter": NOISE_ENCOUNTER, "results": table, "wrong_text_accepted": bad, "no_message_trials": len(empties),
               "false_messages": false_msgs, "minutes": round((time.perf_counter() - t0) / 60, 1)}
    (out / "results.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    (out / "log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"written to {out} in {summary['minutes']} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
