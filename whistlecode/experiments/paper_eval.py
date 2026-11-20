"""The WhistleCode test campaign for the paper (PLAN.md section 8): frozen settings, fresh messages, every result kept.

Nothing here tunes anything. The settings are those of config.toml as committed; frozen.json records the hashes of every file
the results depend on. The messages come from a seed never used during development (SEED), so no result below was seen while
the receiver was being tuned. Encounter-276 noise was used for two earlier checks (PLAN.md "Sea channel test" and "Normal
conditions proved") but never for tuning.

Experiments (PLAN.md section 8.3; the ids in brackets are the plan's):

    clean     [E1]   the full set straight from the sender into the receiver (no channel)
    final    [Final] the full set in encounter-276 noise at 10 dB
    snr214    [E2]   the sweep set at 13 SNRs from -5 to 25 dB in encounter-214 noise (the tuning noise)
    snr276    [E2]   the same in encounter-276 noise (the test noise)
    baseline  [E8]   the chirp modem of wcode/baseline.py, same messages and SNRs, encounter-276 noise
    range     [E3]   echoes and absorption at 0.2, 0.5, 1 and 2 km, at 5, 10 and 20 dB, no Doppler
    doppler   [E3]   Doppler alone at closing speeds from -3 to +3 m/s, 15 dB
    sea       [E3]   a random sea per message (range, depths, speed: echoes, absorption and Doppler), at 5, 10 and 20 dB
    tau       [E5]   latent variation tau = 0.25, 0.75 and 1.0 at 10 dB in encounter-214 noise (0.5 is snr214 at 10 dB)
    empty            50 one-minute recordings of encounter-276 noise with no message, 10 random keys each

Every trial also tries the recording with a wrong key, and reads the frame at the true start ("oracle sync"), so failures to
find the frame can be told apart from whistle errors. Detected tracks are kept, so receiver variations can be scored later
without running the detector again (paper_analysis.py).

    python whistlecode/experiments/paper_eval.py run [--only clean final ...] [--quick]
    python whistlecode/experiments/paper_eval.py empty [--quick]
    python whistlecode/experiments/paper_eval.py status

A run picks up where it stopped: trials already in trials.jsonl are skipped. Results: whistlecode/outputs/paper[_quick]/<experiment>/
(gitignored): trials.jsonl, log.txt and tracks/*.npz.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import platform
import subprocess
import sys
import time
import traceback
import zlib
from pathlib import Path

import numpy as np

WC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WC))

from wcode import bank as bank_mod  # noqa: E402
from wcode import baseline, channel, detect, layout, receiver, sea, sender  # noqa: E402
from wcode.config import PROJECT_ROOT, default_config  # noqa: E402

SEED = 20261120                    # [DECISION] fresh: development used 20261118 and 20261119
SWEEP_SNRS = (-5.0, -2.5, 0.0, 2.5, 5.0, 7.5, 10.0, 12.5, 15.0, 17.5, 20.0, 22.5, 25.0)   # [PLAN] 8.3, E2
SEA_SNRS = (5.0, 10.0, 20.0)       # [PLAN] 8.3, E3
RANGES_KM = (0.2, 0.5, 1.0, 2.0)   # [PLAN] section 6
SPEEDS_MPS = (-3.0, -2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0, 3.0)   # [DECISION] both signs: the slot window is asymmetric
TAUS = (0.25, 0.75, 1.0)           # [PLAN] 8.3, E5 (tau = 0 turns the recorded voices off as well, so it is left out)
N_SWEEP = 50                       # [PLAN] 8.1: sweep set, 50 messages per test point
SWEEP_CHARS = (8, 32)              # [DECISION] the plan's 8-32 bytes as compact text, format v2's main use
N_FULL_BYTES, FULL_BYTES = 150, (4, 64)   # [PLAN] 8.1: full set, 150 random binary payloads ...
N_FULL_TEXT, FULL_CHARS = 50, (10, 60)    # [PLAN] ... and 50 sentences in capitals ([DECISION] 10-60 characters, the web page's limit)
EMPTY_RECORDINGS, EMPTY_S, EMPTY_KEYS = 50, 60.0, 10   # [PLAN] 8.2: 50 minutes of noise; [DECISION] 10 keys per minute
WRONG_KEY_SUFFIX = "/wrong"
FRAME_TOLERANCE_S = 0.15

VOCAB = ("MEET AT DAWN DUSK NOON NORTH SOUTH EAST WEST REEF SHOAL BAY CAPE POINT HOLD POSITION WAIT FOR SIGNAL THE TIDE TURNS "
         "SOON BRING TWO THREE FOUR BOATS CROSS CHANNEL SAFE ROUTE CLEAR AHEAD RETURN BEFORE NIGHT STORM COMING WIND RISING CALM "
         "SEA FOG LIFTING DEPTH FIFTY METRES SURFACE NOW DIVE STAY DEEP POD MOVING FAST SLOW HEADING OPEN WATER NEAR SHORE ALL "
         "WELL SEND HELP SUPPLIES LOW FUEL ENGINE FAILED ANCHOR DOWN UP DRIFTING CURRENT STRONG WEAK RENDEZVOUS AT BUOY SEVEN NINE "
         "ELEVEN MILES KNOTS ARRIVED LEAVING TOMORROW TONIGHT CONFIRM REPEAT ABORT PROCEED GO NO CHANGE PLAN LISTEN QUIET RADIO "
         "SILENCE OBSERVED VESSEL CONTACT LOST FOUND NETS SIGHTED WHALES FEEDING HERE THERE").split()


# ---------------------------------------------------------------------------------------------- messages and conditions
def sentence(n: int, rng: np.random.Generator) -> str:
    """Exactly n characters of capital words, ending with a full stop."""
    words: list[str] = []
    while len(" ".join(words)) < n - 1:
        words.append(str(rng.choice(VOCAB)))
    s = " ".join(words)[:n - 1]
    if s.endswith(" "):
        s = s[:-1] + "S"
    return s + "."


def _key(rng: np.random.Generator) -> str:
    return f"paper-{int(rng.integers(2 ** 32)):08x}"


def message_sets() -> dict[str, list[dict]]:
    rng = np.random.default_rng([SEED, 1])
    sweep = [{"id": f"s{i:02d}", "kind": "text", "text": sentence(int(rng.integers(SWEEP_CHARS[0], SWEEP_CHARS[1] + 1)), rng),
              "key": _key(rng), "nonce": int(rng.integers(256))} for i in range(N_SWEEP)]
    rng = np.random.default_rng([SEED, 2])
    full = []
    for i in range(N_FULL_BYTES):
        n = int(rng.integers(FULL_BYTES[0], FULL_BYTES[1] + 1))
        full.append({"id": f"b{i:03d}", "kind": "bytes", "hex": rng.bytes(n).hex(), "key": _key(rng), "nonce": int(rng.integers(256))})
    for i in range(N_FULL_TEXT):
        full.append({"id": f"t{i:02d}", "kind": "text", "text": sentence(int(rng.integers(FULL_CHARS[0], FULL_CHARS[1] + 1)), rng),
                     "key": _key(rng), "nonce": int(rng.integers(256))})
    return {"sweep": sweep, "full": full}


def payload_of(m: dict) -> str | bytes:
    return m["text"] if m["kind"] == "text" else bytes.fromhex(m["hex"])


def expected_bytes(m: dict) -> bytes:
    return m["text"].encode("utf-8") if m["kind"] == "text" else bytes.fromhex(m["hex"])


def experiments() -> dict[str, tuple[str, list[dict]]]:
    return {
        "clean": ("full", [{"clean": True}]),
        "final": ("full", [{"encounter": 276, "snr": 10.0}]),
        "snr214": ("sweep", [{"encounter": 214, "snr": s} for s in SWEEP_SNRS]),
        "snr276": ("sweep", [{"encounter": 276, "snr": s} for s in SWEEP_SNRS]),
        "baseline": ("sweep", [{"encounter": 276, "snr": s, "modem": "baseline"} for s in SWEEP_SNRS]),
        "range": ("sweep", [{"encounter": 276, "snr": s, "range_km": r} for r in RANGES_KM for s in SEA_SNRS]),
        "doppler": ("sweep", [{"encounter": 276, "snr": 15.0, "speed_mps": v} for v in SPEEDS_MPS]),
        "sea": ("sweep", [{"encounter": 276, "snr": s, "random_sea": True} for s in SEA_SNRS]),
        "tau": ("sweep", [{"encounter": 214, "snr": 10.0, "tau": t} for t in TAUS]),
    }


def trial_seed(exp: str, ci: int, mi: int) -> int:
    return int(np.random.SeedSequence([SEED, zlib.crc32(exp.encode()), ci, mi]).generate_state(1)[0])


def sea_state(cond: dict, mi: int, cfg: dict) -> sea.Sea | None:
    """The message's own random sea (the same in every condition), with the condition's range or speed."""
    if not any(k in cond for k in ("range_km", "speed_mps", "random_sea")):
        return None
    s = sea.draw(np.random.default_rng([SEED, 7, mi]), cfg)
    if "range_km" in cond:
        return dataclasses.replace(s, range_m=1000.0 * float(cond["range_km"]), speed_mps=0.0, echoes=True)
    if "speed_mps" in cond:
        return dataclasses.replace(s, speed_mps=float(cond["speed_mps"]), echoes=False)
    return s


# ---------------------------------------------------------------------------------------------- the frozen record
def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def frozen_record(cfg: dict, tx: sender.Sender) -> dict:
    def git(*a: str) -> str:
        try:
            return subprocess.run(["git", *a], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception as e:  # noqa: BLE001
            return f"unavailable ({e})"

    import torch
    model = tx.cb.info["model"]
    return {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "seed": SEED,
            "git_commit": git("rev-parse", "HEAD"), "git_whistlecode_changes": git("status", "--short", "--", "whistlecode"),
            "config_toml_sha256": _sha256(WC / "config.toml"), "codebook_sha256": tx.codebook_sha256, "bank_sha256": tx.bank.sha256,
            "checkpoint_sha256": model.get("checkpoint_sha256"), "gmm_sha256": model.get("gmm_sha256"),
            "realism_enabled": bool(cfg["realism"]["enabled"]), "real_shapes": bool(cfg["realism"]["real_shapes"]),
            "tau": float(cfg["transmit"]["tau"]),
            "code_sha256": {str(p.relative_to(WC)).replace("\\", "/"): _sha256(p)
                            for p in sorted([*(WC / "wcode").glob("*.py"), Path(__file__).resolve()])},
            "python": platform.python_version(), "numpy": np.__version__,
            "torch": torch.__version__, "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "none",
            "machine": platform.platform()}


# ---------------------------------------------------------------------------------------------- one trial
class Context:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.bank = bank_mod.load(cfg)
        self.detector = detect.Detector(cfg)
        self._modems: dict[str, tuple] = {}

    def modem(self, name: str) -> tuple[sender.Sender, receiver.Receiver, dict]:
        if name not in self._modems:
            if name == "whistlecode":
                c = self.cfg
                tx = sender.Sender(c, rhythm_bank=self.bank)
                rx = receiver.Receiver(c, rhythm_bank=self.bank, detector=self.detector)
            elif name == "baseline":
                path = baseline.build(self.cfg)
                c = baseline.config(self.cfg)
                tx = sender.Sender(c, codebook_path=path, check_model=False, rhythm_bank=self.bank)
                rx = receiver.Receiver(c, codebook_path=path, check_model=False, rhythm_bank=self.bank, detector=self.detector)
            else:
                raise ValueError(f"unknown modem {name!r}")
            self._modems[name] = (tx, rx, c)
        return self._modems[name]


def save_tracks(path: Path, tracks: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    freq = np.concatenate([t.freq_hz for t in tracks]).astype(np.float32) if tracks else np.zeros(0, np.float32)
    np.savez_compressed(path, start_s=np.array([t.start_s for t in tracks], dtype=np.float64),
                        n=np.array([len(t.freq_hz) for t in tracks], dtype=np.int64), freq_hz=freq,
                        hop_s=np.array(tracks[0].hop_s if tracks else 0.0))


def load_tracks(path: Path) -> list:
    z = np.load(path)
    hop, edges = float(z["hop_s"]), np.concatenate([[0], np.cumsum(z["n"])])
    return [detect.Track(float(s), z["freq_hz"][a:b].astype(np.float64), hop) for s, a, b in zip(z["start_s"], edges[:-1], edges[1:])]


def _counts(read: receiver.SlotReadout, truth: np.ndarray) -> dict:
    lost = read.symbols == -1
    wrong = (~lost) & (read.symbols != truth)
    missed = np.asarray(read.missed, dtype=bool)
    return {"lost": int(lost.sum()), "missed": int(missed.sum()), "doubtful": int((lost & ~missed).sum()), "wrong": int(wrong.sum()),
            "shape_wrong": int(((~lost) & ((read.symbols >> 2) != (truth >> 2))).sum()),
            "pitch_wrong": int(((~lost) & ((read.symbols & 3) != (truth & 3))).sum())}


def run_trial(ctx: Context, exp: str, ci: int, cond: dict, mi: int, m: dict, tracks_dir: Path) -> dict:
    tx, rx, cfg = ctx.modem(cond.get("modem", "whistlecode"))
    key, expected = m["key"], expected_bytes(m)
    seed = trial_seed(exp, ci, mi)
    times = {}
    t = time.perf_counter()
    sent = tx.send(payload_of(m), key, int(m["nonce"]), tau=cond.get("tau"))
    times["send_s"] = time.perf_counter() - t
    state = sea_state(cond, mi, cfg)
    t = time.perf_counter()
    if cond.get("clean"):
        audio, fs, true_start, scale = sent.audio, sent.fs, sent.lead_in_s, 1.0
    else:
        heard = channel.through_channel(sent.audio, sent.fs, float(cond["snr"]), tx.pool, int(cond["encounter"]), seed, cfg, tx.pcfg, state)
        audio, fs, scale = heard.audio, heard.fs, float(heard.time_scale)
        true_start = heard.offset_s + sent.lead_in_s / scale
    times["channel_s"] = time.perf_counter() - t
    t = time.perf_counter()
    tracks = rx.tracks(audio, fs)
    times["detect_s"] = time.perf_counter() - t
    t = time.perf_counter()
    got = rx.decode_tracks(tracks, key)
    times["decode_s"] = time.perf_counter() - t
    save_tracks(tracks_dir / f"{ci:02d}_{mi:03d}.npz", tracks)

    # whistle by whistle, at the true frame start (what perfect synchronisation would read)
    ts = receiver.TrackSet(tracks)
    n_pre = int(cfg["framing"]["n_preamble"])
    n_head = int(cfg["format2"]["header_data_symbols"]) + int(cfg["format2"]["header_parity"])
    slots = [d.slot for d in sent.data[n_pre:]]
    truth = sent.frame.symbols
    read = rx.read_slots(ts, slots, true_start)
    head_part = receiver.SlotReadout(read.symbols[:n_head], 0, 0, read.doubt[:n_head], None if read.missed is None else read.missed[:n_head])
    body_part = receiver.SlotReadout(read.symbols[n_head:], 0, 0, read.doubt[n_head:], None if read.missed is None else read.missed[n_head:])
    whole = _counts(read, truth)
    head_layout = layout.header_layout(key, rx.bank, rx.pool, cfg)
    oracle = rx._attempt(ts, head_layout, true_start, 0.0, key)
    t = time.perf_counter()
    wrong_key = rx.decode_tracks(tracks, key + WRONG_KEY_SUFFIX)
    times["wrong_key_s"] = time.perf_counter() - t
    c = float(cfg["sea"]["sound_speed_mps"])
    ok = bool(got.ok)
    return {
        "exp": exp, "cond_index": ci, "cond": cond, "msg_index": mi, "msg_id": m["id"], "kind": m["kind"], "seed": seed,
        "mode": int(sent.frame.mode), "length": int(sent.frame.length), "info_bits": 8 * len(expected) if m["kind"] == "bytes" else 5 * len(m["text"]),
        "duration_s": float(sent.duration_s), "true_start_s": float(true_start), "time_scale": scale,
        "n_symbols": int(len(truth)), "n_header": n_head, "n_preamble": n_pre, "n_cover": int(sent.n_cover),
        "n_cover_moved": int(sent.n_cover_moved), "n_cover_stuck": int(sent.n_cover_stuck), "n_fell_back": int(sent.n_fell_back),
        "n_clicks": int(sent.n_clicks), "n_tracks": len(tracks),
        "ok": ok, "exact": bool(ok and got.payload == expected and got.mode == sent.frame.mode),
        "stage": got.stage, "detail": got.detail, "attempts": int(got.attempts),
        "frame_found": bool(got.offset_s is not None and abs(got.offset_s - true_start) <= FRAME_TOLERANCE_S),
        "frame_error_ms": None if got.offset_s is None else 1000.0 * (got.offset_s - true_start),
        "oracle_ok": bool(oracle is not None and oracle.ok), "oracle_exact": bool(oracle is not None and oracle.ok and oracle.payload == expected),
        "oracle_stage": None if oracle is None else oracle.stage,
        "wrong_key_accepted": bool(wrong_key.ok), "wrong_key_stage": wrong_key.stage,
        "repaired_wrong": int(got.n_repaired_wrong), "repaired_lost": int(got.n_repaired_lost),
        "whistles": whole, "header": _counts(head_part, truth[:n_head]), "payload": _counts(body_part, truth[n_head:]),
        "sea": dataclasses.asdict(state) if state is not None else None,
        "drift_ms": 1000.0 * (state.speed_mps / c if state is not None else 0.0) * float(sent.duration_s),
        "times": {k: round(v, 3) for k, v in times.items()},
    }


# ---------------------------------------------------------------------------------------------- running
def _done(path: Path) -> set[tuple[int, int]]:
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if "error" not in r:
                out.add((int(r["cond_index"]), int(r["msg_index"])))
    return out


def run(names: list[str], quick: bool, out_root: Path) -> int:
    cfg = default_config()
    ctx = Context(cfg)
    tx, _, _ = ctx.modem("whistlecode")
    out_root.mkdir(parents=True, exist_ok=True)
    sets = message_sets()
    (out_root / "messages.json").write_text(json.dumps(sets, indent=1), encoding="utf-8")
    frozen = out_root / "frozen.json"
    record = frozen_record(cfg, tx)
    if frozen.exists():
        old = json.loads(frozen.read_text(encoding="utf-8"))
        for k in ("config_toml_sha256", "codebook_sha256", "bank_sha256", "checkpoint_sha256", "gmm_sha256", "seed"):
            if old.get(k) != record.get(k):
                raise SystemExit(f"{k} changed since this campaign started ({old.get(k)} -> {record.get(k)}); "
                                 f"start a new campaign folder instead of mixing results")
    else:
        frozen.write_text(json.dumps(record, indent=1), encoding="utf-8")
    plan = experiments()
    for name in names:
        set_name, conds = plan[name]
        msgs = sets[set_name]
        if quick:
            conds, msgs = [conds[0]] + ([conds[-1]] if len(conds) > 1 else []), msgs[:1] + msgs[-1:]
        d = out_root / name
        d.mkdir(parents=True, exist_ok=True)
        done = _done(d / "trials.jsonl")
        total = len(conds) * len(msgs)
        t0 = time.perf_counter()
        n_new = 0
        with open(d / "trials.jsonl", "a", encoding="utf-8") as f, open(d / "log.txt", "a", encoding="utf-8") as lg:
            def log(s: str) -> None:
                print(s, flush=True)
                lg.write(s + "\n")
                lg.flush()

            log(f"=== {name}: {len(conds)} conditions x {len(msgs)} messages; {len(done)} already done  [{time.strftime('%H:%M:%S')}]")
            for ci, cond in enumerate(conds):
                for mi, m in enumerate(msgs):
                    if (ci, mi) in done:
                        continue
                    try:
                        r = run_trial(ctx, name, ci, cond, mi, m, d / "tracks")
                        verdict = "OK" if r["exact"] else f"FAILED at {r['stage']}"
                        note = (f"{r['whistles']['lost']} lost, {r['whistles']['wrong']} wrong of {r['n_symbols']}"
                                f"{'; WRONG KEY ACCEPTED' if r['wrong_key_accepted'] else ''}")
                    except Exception as e:  # noqa: BLE001  (one bad trial must not stop an overnight run; it is recorded and counted)
                        r = {"exp": name, "cond_index": ci, "cond": cond, "msg_index": mi, "msg_id": m["id"], "error": repr(e),
                             "traceback": traceback.format_exc()}
                        verdict, note = "ERROR", repr(e)
                    f.write(json.dumps(r) + "\n")
                    f.flush()
                    n_new += 1
                    left = (time.perf_counter() - t0) / n_new * (total - len(done) - n_new) / 60
                    log(f"{name} {json.dumps(cond)} {m['id']} ({len(done) + n_new}/{total}): {verdict}; {note}  "
                        f"[{(time.perf_counter() - t0) / 60:.1f} min, ~{left:.0f} min left]")
            log(f"=== {name} finished: {n_new} new trials in {(time.perf_counter() - t0) / 60:.1f} min")
    return 0


def run_empty(quick: bool, out_root: Path) -> int:
    """Recordings with no message, tried with random keys: the receiver must report nothing (PLAN.md section 8.2)."""
    cfg = default_config()
    ctx = Context(cfg)
    tx, rx, _ = ctx.modem("whistlecode")
    fs = int(cfg["synth"]["fs_hz"])
    d = out_root / "empty"
    d.mkdir(parents=True, exist_ok=True)
    n, k = (2, 2) if quick else (EMPTY_RECORDINGS, EMPTY_KEYS)
    rows, t0 = [], time.perf_counter()
    for i in range(n):
        rng = np.random.default_rng([SEED, 99, i])
        x, used = channel.noise_stretch(276, int(EMPTY_S * fs), rng, cfg, tx.pcfg)
        tracks = rx.tracks(x.astype(np.float32), fs)
        save_tracks(d / "tracks" / f"00_{i:03d}.npz", tracks)
        for j in range(k):
            key = _key(rng)
            got = rx.decode_tracks(tracks, key)
            rows.append({"recording": i, "files": used, "key": key, "n_tracks": len(tracks), "false_message": bool(got.ok),
                         "stage": got.stage})
        print(f"empty {i + 1}/{n}: {len(tracks)} tracks, {sum(r['false_message'] for r in rows)} false messages so far  "
              f"[{(time.perf_counter() - t0) / 60:.1f} min]", flush=True)
    (d / "trials.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return 0


def status(out_root: Path) -> int:
    plan = experiments()
    for name, (set_name, conds) in plan.items():
        p = out_root / name / "trials.jsonl"
        rows = [json.loads(s) for s in p.read_text(encoding="utf-8").splitlines() if s.strip()] if p.exists() else []
        ok = [r for r in rows if "error" not in r]
        total = len(conds) * (N_SWEEP if set_name == "sweep" else N_FULL_BYTES + N_FULL_TEXT)
        print(f"{name:9s} {len(ok):5d}/{total:<5d} trials, {sum(r['exact'] for r in ok):5d} exact, {len(rows) - len(ok)} errors, "
              f"{sum(r['wrong_key_accepted'] for r in ok)} wrong-key accepts, {sum(r['ok'] and not r['exact'] for r in ok)} wrong texts")
    p = out_root / "empty" / "trials.jsonl"
    if p.exists():
        rows = [json.loads(s) for s in p.read_text(encoding="utf-8").splitlines() if s.strip()]
        print(f"empty     {len(rows)} tries, {sum(r['false_message'] for r in rows)} false messages")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=("run", "empty", "status"))
    ap.add_argument("--only", nargs="+", choices=tuple(experiments()), help="experiments to run (default: all, in the listed order)")
    ap.add_argument("--quick", action="store_true", help="2 messages under the first and last condition, into outputs/paper_quick")
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")
    out_root = PROJECT_ROOT / "whistlecode" / "outputs" / ("paper_quick" if args.quick else "paper")
    if args.command == "status":
        return status(out_root)
    if args.command == "empty":
        return run_empty(args.quick, out_root)
    return run(args.only or list(experiments()), args.quick, out_root)


if __name__ == "__main__":
    sys.exit(main())
