"""End-to-end run of the complete pipeline: text -> WAV -> real noise -> detector -> text (PLAN.md "Final idea", step 4).

Every trial sends one message with its own key through encounter-214 noise and reads it back knowing nothing but the key. The
whistles are also read at the true frame position, so whistle errors can be separated from failures to find the frame.
Recordings with no message are read too: the receiver must report nothing.

    python whistlecode/experiments/e2e_run.py [--quick] [--trials 10] [--tag name]

Results: whistlecode/outputs/e2e[_tag]/results.json, trials.jsonl and log.txt (gitignored).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

WC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WC))

from wcode import channel, detect, format2, receiver, sender  # noqa: E402
from wcode.config import PROJECT_ROOT, default_config  # noqa: E402

WORDS = ("MEET AT DAWN NORTH REEF HOLD POSITION WAIT FOR SIGNAL THE TIDE TURNS SOON BRING TWO BOATS CROSS CHANNEL "
         "SAFE ROUTE CLEAR AHEAD RETURN BEFORE NIGHT").split()
SNRS = (10.0, 15.0, 20.0)
LENGTHS = (12, 20, 60)
FRAME_TOLERANCE_S = 0.15


def make_text(n: int, rng: np.random.Generator) -> str:
    out = ""
    while len(out) < n:
        out += str(rng.choice(WORDS)) + " "
    return out[:n - 1].rstrip().ljust(n - 1, "X") + "."


def one_trial(tx: sender.Sender, rx: receiver.Receiver, text: str, key: str, snr: float, seed: int, cfg: dict) -> dict:
    sent = tx.send(text, key, seed % 256)
    heard = channel.through_channel(sent.audio, sent.fs, snr, tx.pool, seed=seed, cfg=cfg, pcfg=tx.pcfg)
    tracks = rx.detector.tracks(heard.audio, heard.fs)
    got = rx.decode_tracks(tracks, key)
    true_start = heard.offset_s + sent.lead_in_s
    ts = receiver.TrackSet(tracks)
    n_pre = int(cfg["framing"]["n_preamble"])
    slots = [d.slot for d in sent.data[n_pre:]]
    read = rx.read_slots(ts, slots, true_start)
    truth = sent.frame.symbols
    lost = read.symbols == format2.ERASED
    wrong = (~lost) & (read.symbols != truth)
    shape_wrong = (~lost) & ((read.symbols >> 2) != (truth >> 2))
    pitch_wrong = (~lost) & ((read.symbols & 3) != (truth & 3))
    return {"text_length": len(text), "snr_db": snr, "seed": seed, "ok": bool(got.ok), "exact": bool(got.ok and got.text == text),
            "stage": got.stage, "detail": got.detail, "attempts": got.attempts,
            "frame_found": got.offset_s is not None and abs(got.offset_s - true_start) <= FRAME_TOLERANCE_S,
            "duration_s": sent.duration_s, "n_data": len(truth), "n_lost": int(lost.sum()), "n_missed": read.n_missed,
            "n_doubtful": read.n_doubtful, "n_wrong": int(wrong.sum()), "n_shape_wrong": int(shape_wrong.sum()),
            "n_pitch_wrong": int(pitch_wrong.sum()), "n_tracks": len(tracks), "n_cover": sent.n_cover,
            "n_cover_moved": sent.n_cover_moved, "n_cover_stuck": sent.n_cover_stuck}


def no_message_trial(tx: sender.Sender, rx: receiver.Receiver, key: str, seed: int, cfg: dict) -> dict:
    rng = np.random.default_rng(seed)
    x, _ = channel.noise_stretch(int(cfg["channel"]["noise_encounter"]), int(60 * cfg["synth"]["fs_hz"]), rng, cfg, tx.pcfg)
    got = rx.receive(x.astype(np.float32), cfg["synth"]["fs_hz"], key)
    return {"seed": seed, "false_message": bool(got.ok), "stage": got.stage}


def summarise(rows: list[dict]) -> dict:
    n = len(rows)
    whistles = sum(r["n_data"] for r in rows)
    return {"trials": n, "exact": sum(r["exact"] for r in rows), "success_rate": sum(r["exact"] for r in rows) / max(n, 1),
            "wrong_text_accepted": sum(r["ok"] and not r["exact"] for r in rows), "frame_found": sum(r["frame_found"] for r in rows),
            "failed_at": {s: sum((not r["ok"]) and r["stage"] == s for r in rows) for s in ("sync", "header", "payload")},
            "lost_rate": sum(r["n_lost"] for r in rows) / max(whistles, 1), "missed_rate": sum(r["n_missed"] for r in rows) / max(whistles, 1),
            "doubtful_rate": sum(r["n_doubtful"] for r in rows) / max(whistles, 1), "wrong_rate": sum(r["n_wrong"] for r in rows) / max(whistles, 1),
            "shape_wrong_rate": sum(r["n_shape_wrong"] for r in rows) / max(whistles, 1),
            "pitch_wrong_rate": sum(r["n_pitch_wrong"] for r in rows) / max(whistles, 1),
            "median_duration_s": float(np.median([r["duration_s"] for r in rows])) if rows else None}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--quick", action="store_true", help="two trials per setting at 15 dB")
    ap.add_argument("--trials", type=int, default=10, help="messages per SNR and length")
    ap.add_argument("--tag", default="", help="suffix of the output folder")
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")
    cfg = default_config()
    name = "e2e" + (f"_{args.tag}" if args.tag else "") + ("_quick" if args.quick else "")
    out = PROJECT_ROOT / "whistlecode" / "outputs" / name
    out.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []

    def log(m: str) -> None:
        lines.append(m)
        print(m, flush=True)

    snrs, trials = ((15.0,), 2) if args.quick else (SNRS, args.trials)
    tx = sender.Sender(cfg)
    rx = receiver.Receiver(cfg, rhythm_bank=tx.bank, detector=detect.Detector(cfg))
    rng = np.random.default_rng(20261118)
    rows: list[dict] = []
    t0 = time.perf_counter()
    with open(out / "trials.jsonl", "w", encoding="utf-8") as f:
        for snr in snrs:
            for length in LENGTHS:
                for i in range(trials):
                    seed = int(rng.integers(2 ** 31))
                    r = one_trial(tx, rx, make_text(length, rng), f"trial-{seed}", snr, seed, cfg)
                    rows.append(r)
                    f.write(json.dumps(r) + "\n")
                    f.flush()
                    log(f"{snr:g} dB, {length} chars, trial {i + 1}/{trials}: {'OK' if r['exact'] else 'FAILED at ' + r['stage']}; "
                        f"{r['n_lost']} lost, {r['n_wrong']} wrong of {r['n_data']} whistles  [{(time.perf_counter() - t0) / 60:.1f} min]")
    empties = [no_message_trial(tx, rx, f"empty-{i}", 1000 + i, cfg) for i in range(2 if args.quick else 10)]

    log("\n=== results ===")
    table = {}
    for snr in snrs:
        table[f"{snr:g}"] = {}
        for length in LENGTHS:
            s = summarise([r for r in rows if r["snr_db"] == snr and r["text_length"] == length])
            table[f"{snr:g}"][str(length)] = s
            log(f"{snr:g} dB, {length:3d} chars: {s['exact']}/{s['trials']} exact, frame found {s['frame_found']}/{s['trials']}, "
                f"lost {s['lost_rate']:.1%}, wrong {s['wrong_rate']:.1%} (shape {s['shape_wrong_rate']:.1%}, pitch {s['pitch_wrong_rate']:.1%}), "
                f"failed at {s['failed_at']}, median {s['median_duration_s']:.0f} s")
        s = summarise([r for r in rows if r["snr_db"] == snr])
        table[f"{snr:g}"]["all"] = s
        log(f"{snr:g} dB, all     : {s['exact']}/{s['trials']} exact, lost {s['lost_rate']:.1%}, wrong {s['wrong_rate']:.1%}")
    bad = sum(r["ok"] and not r["exact"] for r in rows)
    false_msgs = sum(e["false_message"] for e in empties)
    log(f"wrong text accepted: {bad} of {len(rows)} messages; messages reported in recordings with none: {false_msgs} of {len(empties)}")
    summary = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "quick": args.quick, "trials_per_setting": trials,
               "noise_encounter": cfg["channel"]["noise_encounter"], "results": table, "wrong_text_accepted": bad,
               "no_message_trials": len(empties), "false_messages": false_msgs, "minutes": round((time.perf_counter() - t0) / 60, 1)}
    (out / "results.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    (out / "log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    log(f"written to {out} in {summary['minutes']} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
