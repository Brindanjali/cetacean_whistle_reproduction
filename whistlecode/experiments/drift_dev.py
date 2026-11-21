"""WC-R2 development runs: Doppler and clock-drift correction, on encounter-214 noise only (PLAN.md section 8.7).

Encounter 276 is never touched here; it belongs to campaign v2. The messages come from DEV_SEED, which no other run uses
(development used 20261118 and 20261119, campaign v1 20261120, campaign v2 is reserved 20261205).

    run      sends the dev messages through the channel, runs the detector and saves the tracks and the truth
    score    decodes the saved tracks with the receiver variants below, and reads every whistle at the true start
    empty    50 one-minute stretches of encounter-214 noise with no message, 10 random keys each, through both receivers
    report   prints the tables of the scored results (and the adoption check on campaign v1's encounter-214 sweep)

Experiments ([DECISION] all at encounter 214):

    doppler214   Doppler alone, 15 dB, closing speeds -3 to +3 m/s (v1's speeds; mark D's six are among them)
    sea214       a random sea per message (as v1's E3 sea), 5, 10 and 20 dB
    snr214dev    no sea, 5, 10, 15 and 20 dB (guards against losses at zero speed while tuning)

The adoption check (rule in PLAN.md 8.7) runs on campaign v1's saved encounter-214 sweep tracks (outputs/paper/snr214), which
were not used while the drift correction was developed: `score --v1-sweep`.

    python whistlecode/experiments/drift_dev.py run --only doppler214
    python whistlecode/experiments/drift_dev.py score [--v1-sweep]
    python whistlecode/experiments/drift_dev.py empty
    python whistlecode/experiments/drift_dev.py report

Results: whistlecode/outputs/drift_dev/ (gitignored).
"""
from __future__ import annotations

import argparse
import copy
import dataclasses
import json
import sys
import time
import traceback
import zlib
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

WC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WC))
sys.path.insert(0, str(WC / "experiments"))

import paper_eval as pe  # noqa: E402
from wcode import bank as bank_mod  # noqa: E402
from wcode import channel, detect, format2, layout, receiver, sea, sender  # noqa: E402
from wcode.config import PROJECT_ROOT, default_config  # noqa: E402

DEV_SEED = 20261121                 # [DECISION] WC-R2 development only
ENCOUNTER = 214                     # [PLAN] 8.7: second-round development uses encounter-214 noise only
SPEEDS_MPS = (-3.0, -2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0, 3.0)
OUT = PROJECT_ROOT / "whistlecode" / "outputs" / "drift_dev"
V1 = PROJECT_ROOT / "whistlecode" / "outputs" / "paper"
VARIANTS = {"before": {"drift_correction": False}, "after": {"drift_correction": True}}
ADOPTION_SNRS = (5.0, 10.0, 15.0, 20.0)


def messages() -> list[dict]:
    rng = np.random.default_rng([DEV_SEED, 1])
    return [{"id": f"d{i:02d}", "kind": "text", "text": pe.sentence(int(rng.integers(8, 33)), rng), "key": f"dev-{int(rng.integers(2 ** 32)):08x}",
             "nonce": int(rng.integers(256))} for i in range(pe.N_SWEEP)]


def experiments() -> dict[str, list[dict]]:
    return {
        "doppler214": [{"snr": 15.0, "speed_mps": v} for v in SPEEDS_MPS],
        "sea214": [{"snr": s, "random_sea": True} for s in (5.0, 10.0, 20.0)],
        "snr214dev": [{"snr": s} for s in ADOPTION_SNRS],
    }


def sea_state(cond: dict, mi: int, cfg: dict) -> sea.Sea | None:
    if "speed_mps" not in cond and not cond.get("random_sea"):
        return None
    s = sea.draw(np.random.default_rng([DEV_SEED, 7, mi]), cfg)
    if "speed_mps" in cond:
        return dataclasses.replace(s, speed_mps=float(cond["speed_mps"]), echoes=False)
    return s


# ---------------------------------------------------------------------------------------------- run
def run(names: list[str]) -> int:
    cfg = default_config()
    b = bank_mod.load(cfg)
    tx = sender.Sender(cfg, rhythm_bank=b)
    det = detect.Detector(cfg)
    rx = receiver.Receiver(cfg, rhythm_bank=b, detector=det)
    msgs = messages()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "messages.json").write_text(json.dumps(msgs, indent=1), encoding="utf-8")
    plan = experiments()
    for name in names:
        d = OUT / name
        d.mkdir(parents=True, exist_ok=True)
        done = pe._done(d / "trials.jsonl")
        t0, n_new = time.perf_counter(), 0
        total = len(plan[name]) * len(msgs)
        with open(d / "trials.jsonl", "a", encoding="utf-8") as f:
            for ci, cond in enumerate(plan[name]):
                for mi, m in enumerate(msgs):
                    if (ci, mi) in done:
                        continue
                    try:
                        seed = int(np.random.SeedSequence([DEV_SEED, zlib.crc32(name.encode()), ci, mi]).generate_state(1)[0])
                        sent = tx.send(m["text"], m["key"], int(m["nonce"]))
                        state = sea_state(cond, mi, cfg)
                        heard = channel.through_channel(sent.audio, sent.fs, float(cond["snr"]), tx.pool, ENCOUNTER, seed, cfg, tx.pcfg, state)
                        scale = float(heard.time_scale)
                        true_start = heard.offset_s + sent.lead_in_s / scale
                        tracks = rx.tracks(heard.audio, heard.fs)
                        pe.save_tracks(d / "tracks" / f"{ci:02d}_{mi:03d}.npz", tracks)
                        r = {"exp": name, "cond_index": ci, "cond": cond, "msg_index": mi, "msg_id": m["id"], "seed": seed,
                             "true_start_s": float(true_start), "time_scale": scale, "duration_s": float(sent.duration_s),
                             "n_symbols": int(len(sent.frame.symbols)), "n_tracks": len(tracks),
                             "sea": dataclasses.asdict(state) if state is not None else None}
                    except Exception as e:  # noqa: BLE001
                        r = {"exp": name, "cond_index": ci, "cond": cond, "msg_index": mi, "error": repr(e), "traceback": traceback.format_exc()}
                    f.write(json.dumps(r) + "\n")
                    f.flush()
                    n_new += 1
                    print(f"{name} {json.dumps(cond)} {m['id']} ({len(done) + n_new}/{total}) "
                          f"[{(time.perf_counter() - t0) / 60:.1f} min]", flush=True)
    return 0


# ---------------------------------------------------------------------------------------------- score
_worker: dict = {}


def _rx(variant: str) -> receiver.Receiver:
    if variant not in _worker:
        cfg = copy.deepcopy(default_config())
        cfg["receiver"].update(VARIANTS[variant])
        b = _worker.get("_bank") or bank_mod.load(cfg)
        _worker["_bank"] = b
        _worker[variant] = receiver.Receiver(cfg, rhythm_bank=b)
    return _worker[variant]


def _truth(m: dict, rx: receiver.Receiver):
    fr = format2.encode(pe.payload_of(m), m["key"], int(m["nonce"]), rx.cfg)
    head, pay = layout.frame_layout(fr, m["key"], rx.bank, rx.pool, rx.cfg)
    n_pre = int(rx.cfg["framing"]["n_preamble"])
    return fr, (head.slots + pay.slots)[n_pre:]


def _score_one(job: tuple) -> dict:
    tracks_path, row, m = job
    tracks = pe.load_tracks(Path(tracks_path))
    expected = pe.expected_bytes(m)
    out = {"exp": row["exp"], "cond_index": row["cond_index"], "msg_index": row["msg_index"], "time_scale": row.get("time_scale", 1.0),
           "duration_s": row.get("duration_s"), "cond": row["cond"]}
    for v in VARIANTS:
        rx = _rx(v)
        t = time.perf_counter()
        got = rx.decode_tracks(tracks, m["key"])
        out[v] = {"exact": bool(got.ok and got.payload == expected), "wrong_text": bool(got.ok and got.payload != expected),
                  "stage": got.stage, "scale": got.time_scale, "decode_s": round(time.perf_counter() - t, 3),
                  "frame_error_ms": None if got.offset_s is None or "true_start_s" not in row else 1000 * (got.offset_s - row["true_start_s"])}
        wrong = rx.decode_tracks(tracks, m["key"] + pe.WRONG_KEY_SUFFIX)
        out[v]["wrong_key_accepted"] = bool(wrong.ok)
    if "true_start_s" in row:
        rx = _rx("before")
        fr, slots = _truth(m, rx)
        truth = fr.symbols
        start, s = float(row["true_start_s"]), float(row["time_scale"])
        out["read_true_start"] = pe._counts(rx.read_slots(receiver.TrackSet(tracks), slots, start), truth)
        warped = receiver.TrackSet(receiver.warp(tracks, start, s))
        out["read_true_drift"] = pe._counts(rx.read_slots(warped, slots, start), truth)
        out["n_symbols"] = int(len(truth))
    return out


def score(v1_sweep: bool, workers: int) -> int:
    jobs = []
    if v1_sweep:
        sets = pe.message_sets()
        rows = [json.loads(s) for s in (V1 / "snr214" / "trials.jsonl").read_text(encoding="utf-8").splitlines() if s.strip()]
        for r in rows:
            if "error" in r or float(r["cond"]["snr"]) not in ADOPTION_SNRS:
                continue
            m = sets["sweep"][r["msg_index"]]
            row = {"exp": "v1_snr214", "cond_index": r["cond_index"], "msg_index": r["msg_index"], "cond": r["cond"]}
            jobs.append((str(V1 / "snr214" / "tracks" / f"{r['cond_index']:02d}_{r['msg_index']:03d}.npz"), row, m))
        dest = OUT / "scores_v1_snr214.jsonl"
    else:
        msgs = messages()
        for name in experiments():
            p = OUT / name / "trials.jsonl"
            if not p.exists():
                continue
            for s in p.read_text(encoding="utf-8").splitlines():
                r = json.loads(s) if s.strip() else None
                if r and "error" not in r:
                    jobs.append((str(OUT / name / "tracks" / f"{r['cond_index']:02d}_{r['msg_index']:03d}.npz"), r, msgs[r["msg_index"]]))
        dest = OUT / "scores.jsonl"
    t0 = time.perf_counter()
    results = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for i, r in enumerate(pool.map(_score_one, jobs, chunksize=4)):
            results.append(r)
            if (i + 1) % 100 == 0:
                print(f"scored {i + 1}/{len(jobs)} [{(time.perf_counter() - t0) / 60:.1f} min]", flush=True)
    dest.write_text("".join(json.dumps(r) + "\n" for r in results), encoding="utf-8")
    print(f"{len(results)} trials scored into {dest} in {(time.perf_counter() - t0) / 60:.1f} min")
    return 0


# ---------------------------------------------------------------------------------------------- report
def _cond_label(c: dict) -> str:
    if "speed_mps" in c:
        return f"{c['speed_mps']:+.1f} m/s, {c['snr']:g} dB"
    return f"{'random sea, ' if c.get('random_sea') else ''}{c['snr']:g} dB"


def empty(workers: int) -> int:
    """Encounter-214 noise with no message, 10 random keys per minute: neither receiver may report a message."""
    cfg = default_config()
    tx = sender.Sender(cfg)
    det = detect.Detector(cfg)
    fs = int(cfg["synth"]["fs_hz"])
    d = OUT / "empty214"
    jobs = []
    for i in range(pe.EMPTY_RECORDINGS):
        rng = np.random.default_rng([DEV_SEED, 99, i])
        path = d / "tracks" / f"00_{i:03d}.npz"
        x, _ = channel.noise_stretch(ENCOUNTER, int(pe.EMPTY_S * fs), rng, cfg, tx.pcfg)
        if not path.exists():
            pe.save_tracks(path, det.tracks(channel.quiet_floor(x.astype(np.float32), fs, cfg), fs))
        jobs.extend((str(path), f"dev-empty-{int(rng.integers(2 ** 32)):08x}") for _ in range(pe.EMPTY_KEYS))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(_empty_one, jobs, chunksize=10))
    (d / "trials.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(rows)} tries: false messages before {sum(r['before'] for r in rows)}, after {sum(r['after'] for r in rows)}")
    return 0


def _empty_one(job: tuple) -> dict:
    path, key = job
    tracks = pe.load_tracks(Path(path))
    return {"tracks": Path(path).name, "key": key, **{v: bool(_rx(v).decode_tracks(tracks, key).ok) for v in VARIANTS}}


def report() -> int:
    for fname in ("scores.jsonl", "scores_v1_snr214.jsonl"):
        p = OUT / fname
        if not p.exists():
            continue
        rows = [json.loads(s) for s in p.read_text(encoding="utf-8").splitlines() if s.strip()]
        print(f"\n## {fname}\n")
        dt = {v: np.median([r[v]["decode_s"] for r in rows]) for v in VARIANTS}
        print(f"median decode time: before {dt['before']:.3f} s, after {dt['after']:.3f} s\n")
        print("| Experiment | Condition | n | Exact before | Exact after | After failed at (sync / header / payload) | Wrong text b/a | Wrong-key b/a | Lost/wrong at true start | Lost/wrong with true drift | Scale error (median, ppm) |")
        print("|---|---|---|---|---|---|---|---|---|---|---|")
        groups: dict = {}
        for r in rows:
            groups.setdefault((r["exp"], r["cond_index"]), []).append(r)
        for (exp, ci), g in sorted(groups.items()):
            n = len(g)
            eb = sum(r["before"]["exact"] for r in g)
            ea = sum(r["after"]["exact"] for r in g)
            wt = f"{sum(r['before']['wrong_text'] for r in g)}/{sum(r['after']['wrong_text'] for r in g)}"
            wk = f"{sum(r['before']['wrong_key_accepted'] for r in g)}/{sum(r['after']['wrong_key_accepted'] for r in g)}"
            if "read_true_start" in g[0]:
                ns = sum(r["n_symbols"] for r in g)
                a = f"{100 * sum(r['read_true_start']['lost'] for r in g) / ns:.1f} / {100 * sum(r['read_true_start']['wrong'] for r in g) / ns:.1f} %"
                b = f"{100 * sum(r['read_true_drift']['lost'] for r in g) / ns:.1f} / {100 * sum(r['read_true_drift']['wrong'] for r in g) / ns:.1f} %"
                errs = [1e6 * (r["after"]["scale"] - r["time_scale"]) for r in g if r["after"]["exact"]]
                se = f"{np.median(np.abs(errs)):.0f}" if errs else "-"
            else:
                a = b = se = "-"
            st = " / ".join(str(sum((not r["after"]["exact"]) and r["after"]["stage"] == x for r in g)) for x in ("sync", "header", "payload"))
            print(f"| {exp} | {_cond_label(g[0]['cond'])} | {n} | {eb} | {ea} | {st} | {wt} | {wk} | {a} | {b} | {se} |")
    p = OUT / "empty214" / "trials.jsonl"
    if p.exists():
        rows = [json.loads(s) for s in p.read_text(encoding="utf-8").splitlines() if s.strip()]
        print(f"\nNo message, encounter-214 noise: {len(rows)} tries, false messages before {sum(r['before'] for r in rows)}, "
              f"after {sum(r['after'] for r in rows)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=("run", "score", "empty", "report"))
    ap.add_argument("--only", nargs="+", choices=tuple(experiments()))
    ap.add_argument("--v1-sweep", action="store_true", help="score campaign v1's encounter-214 sweep tracks (the adoption check)")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")
    if args.command == "run":
        return run(args.only or list(experiments()))
    if args.command == "score":
        return score(args.v1_sweep, args.workers)
    if args.command == "empty":
        return empty(args.workers)
    return report()


if __name__ == "__main__":
    sys.exit(main())
