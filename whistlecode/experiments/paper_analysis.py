"""Tables, figures and receiver ablations for the paper, from the campaign of paper_eval.py and paper_covert.py.

    python whistlecode/experiments/paper_analysis.py ablate      # receiver variations on the saved tracks (no detector)
    python whistlecode/experiments/paper_analysis.py examples    # example spectrogram and the two alphabets
    python whistlecode/experiments/paper_analysis.py report      # tables (Markdown + CSV) and figures

Rates carry 95 % Wilson intervals. A count of zero events out of n carries the one-sided 95 % upper bound 1 - 0.05^(1/n).
Results go to whistlecode/paper/ (tables/, figures/, RESULTS.md), which is meant to be kept; the raw trials stay in
whistlecode/outputs/paper/ (gitignored).
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import statistics
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

WC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WC))
sys.path.insert(0, str(WC / "experiments"))

import paper_eval as pe  # noqa: E402
from wcode.config import PROJECT_ROOT, default_config  # noqa: E402

RAW = PROJECT_ROOT / "whistlecode" / "outputs" / "paper"
PAPER = WC / "paper"
ERASED = -1

# chart roles (dataviz reference palette, light, validated on #ffffff: slots 1-3 pass all-pairs; aqua needs direct labels)
INK, INK2, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
S1, S2, S3 = "#2a78d6", "#eb6834", "#1baf7a"
ORDINAL = ("#86b6ef", "#2a78d6", "#104281")      # validated ordinal blue ramp, light -> dark


# ---------------------------------------------------------------------------------------------- statistics
def wilson(k: int, n: int, z: float = 1.959964) -> tuple[float, float, float]:
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def zero_upper(n: int) -> float:
    return 1 - 0.05 ** (1 / n) if n else float("nan")


def pct(k: int, n: int) -> str:
    p, lo, hi = wilson(k, n)
    return f"{100 * p:.1f} % ({100 * lo:.1f}-{100 * hi:.1f})" if n else "-"


def load(exp: str) -> tuple[list[dict], int]:
    p = RAW / exp / "trials.jsonl"
    if not p.exists():
        return [], 0
    rows = [json.loads(s) for s in p.read_text(encoding="utf-8").splitlines() if s.strip()]
    good = {(r["cond_index"], r["msg_index"]): r for r in rows if "error" not in r}      # a retried trial replaces its error row
    errors = {(r["cond_index"], r["msg_index"]) for r in rows if "error" in r} - set(good)
    return list(good.values()), len(errors)


def summary(rows: list[dict]) -> dict:
    n = len(rows)
    sym = sum(r["n_symbols"] for r in rows) or 1
    w = lambda k: sum(r["whistles"][k] for r in rows) / sym
    k = sum(r["exact"] for r in rows)
    p, lo, hi = wilson(k, n)
    return {"n": n, "exact": k, "rate": p, "lo": lo, "hi": hi, "oracle_exact": sum(r["oracle_exact"] for r in rows),
            "frame_found": sum(r["frame_found"] for r in rows), "wrong_text": sum(r["ok"] and not r["exact"] for r in rows),
            "wrong_key": sum(r["wrong_key_accepted"] for r in rows),
            "failed_at": dict(Counter(r["stage"] for r in rows if not r["ok"])),
            "lost": w("lost"), "missed": w("missed"), "doubtful": w("doubtful"), "wrong": w("wrong"),
            "shape_wrong": w("shape_wrong"), "pitch_wrong": w("pitch_wrong"),
            "bps": statistics.median(r["info_bits"] / r["duration_s"] for r in rows) if rows else float("nan"),
            "duration_s": statistics.median(r["duration_s"] for r in rows) if rows else float("nan")}


def failures(rows: list[dict]) -> tuple[int, int, int]:
    """Failed messages split by where they failed: wrong frame start (none of the receiver's frame candidates was within
    FRAME_TOLERANCE_S of the true start), else the header or the payload."""
    bad = [r for r in rows if not r["exact"]]
    sync = sum(not r["frame_found"] for r in bad)
    rest = [r for r in bad if r["frame_found"]]
    return sync, sum(r["stage"] in ("sync", "header") for r in rest), sum(r["stage"] not in ("sync", "header") for r in rest)


def by_cond(rows: list[dict]) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for r in rows:
        out.setdefault(int(r["cond_index"]), []).append(r)
    return dict(sorted(out.items()))


# ---------------------------------------------------------------------------------------------- receiver ablations
VARIANTS = {
    "deployed": {},
    "no_soft_repair": {"soft_repair": False},
    "ratio_0.75": {"ambiguity_ratio": 0.75},
    "ratio_0.95": {"ambiguity_ratio": 0.95},
    "no_doubt_erasures": {"ambiguity_ratio": 1.0},
    "errors_only": {"ambiguity_ratio": 1.0, "soft_repair": False, "errors_only": True},
}
_worker: dict = {}


def _receiver(variant: str):
    from wcode import bank, receiver

    if variant in _worker:
        return _worker[variant]
    cfg = copy.deepcopy(default_config())
    v = VARIANTS[variant]
    if "soft_repair" in v:
        cfg["receiver"]["soft_repair"] = v["soft_repair"]
    if "ambiguity_ratio" in v:
        cfg["classify"]["ambiguity_ratio"] = v["ambiguity_ratio"]
    b = _worker.get("_bank") or bank.load(cfg)
    _worker["_bank"] = b

    class ErrorsOnly(receiver.Receiver):
        """Every whistle is given a symbol: a missed one gets 0, so Reed-Solomon sees errors only, never erasures."""

        def read_slots(self, tr, slots, start_s):
            r = super().read_slots(tr, slots, start_s)
            n = len(r.symbols)
            return receiver.SlotReadout(np.where(r.symbols == ERASED, 0, r.symbols), 0, 0, np.zeros(n), np.zeros(n, dtype=bool))

    cls = ErrorsOnly if v.get("errors_only") else receiver.Receiver
    _worker[variant] = cls(cfg, rhythm_bank=b)
    return _worker[variant]


def _ablate_one(job: tuple) -> dict:
    exp, ci, mi, key, expected_hex = job
    tracks = pe.load_tracks(RAW / exp / "tracks" / f"{ci:02d}_{mi:03d}.npz")
    out = {"exp": exp, "cond_index": ci, "msg_index": mi}
    for v in VARIANTS:
        got = _receiver(v).decode_tracks(tracks, key)
        out[v] = bool(got.ok and got.payload == bytes.fromhex(expected_hex))
        out[v + "_wrong_text"] = bool(got.ok and got.payload != bytes.fromhex(expected_hex))
    return out


def ablate() -> int:
    sets = pe.message_sets()
    jobs = []
    for exp in ("snr214", "snr276"):
        rows, _ = load(exp)
        for r in rows:
            m = sets["sweep"][r["msg_index"]]
            jobs.append((exp, r["cond_index"], r["msg_index"], m["key"], pe.expected_bytes(m).hex()))
    t0 = time.perf_counter()
    results = []
    with ProcessPoolExecutor(max_workers=8) as pool:
        for i, r in enumerate(pool.map(_ablate_one, jobs, chunksize=8)):
            results.append(r)
            if (i + 1) % 100 == 0:
                print(f"ablations {i + 1}/{len(jobs)} [{(time.perf_counter() - t0) / 60:.1f} min]", flush=True)
    (RAW / "ablations.jsonl").write_text("".join(json.dumps(r) + "\n" for r in results), encoding="utf-8")
    print(f"written to {RAW / 'ablations.jsonl'} in {(time.perf_counter() - t0) / 60:.1f} min")
    return 0


# ---------------------------------------------------------------------------------------------- figures (shared look)
def _style():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "figure.facecolor": "#ffffff", "axes.facecolor": "#ffffff", "savefig.facecolor": "#ffffff",
        "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8, "legend.fontsize": 8,
        "text.color": INK, "axes.labelcolor": INK2, "xtick.color": MUTED, "ytick.color": MUTED,
        "axes.edgecolor": AXIS, "axes.linewidth": 0.8, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
        "lines.linewidth": 2.0, "lines.markersize": 5, "legend.frameon": False, "font.family": "DejaVu Sans"})
    return plt


def _save(fig, name: str) -> None:
    d = PAPER / "figures"
    d.mkdir(parents=True, exist_ok=True)
    fig.savefig(d / f"{name}.png", dpi=200, bbox_inches="tight")
    fig.savefig(d / f"{name}.pdf", bbox_inches="tight")


def _line(ax, x, rows_by_x, color, label, marker="o", band=True, label_at_end=True, dy=0.0):
    k = np.array([sum(r["exact"] for r in rows_by_x[v]) for v in x])
    n = np.array([len(rows_by_x[v]) for v in x])
    ci = np.array([wilson(int(a), int(b)) for a, b in zip(k, n)])
    ax.plot(x, 100 * ci[:, 0], color=color, marker=marker, markeredgecolor="#ffffff", markeredgewidth=1.0, label=label, zorder=3)
    if band:
        # shaded only between 0 % and 100 % (plus one point each side), so flat runs at the floor or ceiling don't stack
        inner = (k > 0) & (k < n)
        show = inner | np.r_[inner[1:], False] | np.r_[False, inner[:-1]]
        ax.fill_between(x, 100 * ci[:, 1], 100 * ci[:, 2], where=show, color=color, alpha=0.13, linewidth=0, zorder=2)
    if label_at_end:
        ax.annotate(label, (x[-1], 100 * ci[-1, 0] + dy), xytext=(6, 0), textcoords="offset points", va="center", color=INK2, fontsize=8)


# ---------------------------------------------------------------------------------------------- examples
def examples() -> int:
    """Fig.: an example message (sent file and what the hydrophone hears) and the two whistle alphabets."""
    from scipy import signal

    from wcode import baseline, channel, codebook, sender

    plt = _style()
    cfg = default_config()
    tx = sender.Sender(cfg)
    m = pe.message_sets()["sweep"][0]
    sent = tx.send(pe.payload_of(m), m["key"], m["nonce"])
    heard = channel.through_channel(sent.audio, sent.fs, 10.0, tx.pool, 276, 1, cfg, tx.pcfg)
    span = 30.0
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 4.6), sharex=True)
    for ax, x, t0, title, quiet in ((axes[0], sent.audio, 0.0, "a  Sent file: whistles and clicks only, silent in between", True),
                                    (axes[1], heard.audio, heard.offset_s, "b  At the hydrophone: encounter-276 sea noise, SNR 10 dB", False)):
        seg = x[int(t0 * sent.fs):int((t0 + span) * sent.fs)]
        f, t, z = signal.spectrogram(seg, sent.fs, nperseg=1024, noverlap=768)
        keep = (f >= 2000) & (f <= 16000)
        db = 10 * np.log10(z[keep] + 1e-20)
        top = np.percentile(db, 99.9)
        bottom = top - 45 if quiet else np.percentile(db, 75)      # the sent file is mostly digital silence: a fixed range
        ax.pcolormesh(t, f[keep] / 1000, db, cmap="Greys", vmin=bottom, vmax=top, shading="auto", rasterized=True)
        ax.set_ylabel("kHz")
        ax.set_title(title, loc="left", color=INK)
        ax.grid(False)
    n_pre = int(cfg["framing"]["n_preamble"])
    for i, d in enumerate(sent.data):
        t = sent.lead_in_s + d.slot.start_s
        if t > span:
            break
        color = S2 if i < n_pre else S1
        for ax in axes:
            ax.plot([t, t + d.contour.n_frames * d.contour.hop_s], [16.4, 16.4], color=color, lw=3, solid_capstyle="butt", clip_on=False)
    from matplotlib.lines import Line2D
    fig.legend([Line2D([], [], color=S2, lw=3), Line2D([], [], color=S1, lw=3)],
               ["start signal (3 signature whistles)", "data whistles (header and payload); every other whistle is cover"],
               loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.04))
    axes[1].set_xlabel("time from the start of the file (s)")
    for ax in axes:
        ax.set_ylim(2, 16.8)
    _save(fig, "fig_example_message")
    plt.close(fig)

    cb, bcb = codebook.load(cfg), baseline.chirp_codebook(cfg)
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), sharey=True)
    for ax, book, title in ((axes[0], cb, "a  WhistleCode types (VAE-GMM)"), (axes[1], bcb, "b  Baseline chirps")):
        for k, wt in enumerate(book.types):
            c = wt.contour
            tt = np.arange(c.n_frames) * c.hop_s * 1000
            ax.plot(tt + (k % 4) * 480, c.offset_hz / 1000 + (3 - k // 4) * 3.2, color=S1, lw=1.6)
            ax.text((k % 4) * 480, (3 - k // 4) * 3.2 + 1.35, f"{k}", color=MUTED, fontsize=7)
        ax.set_title(title, loc="left", color=INK)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.grid(False)
        for s in ax.spines.values():
            s.set_visible(False)
    axes[0].plot([0, 200], [-1.9, -1.9], color=INK2, lw=1)
    axes[0].text(0, -2.5, "200 ms", fontsize=7, color=INK2, va="top")
    axes[0].plot([-40, -40], [-1.9, -0.9], color=INK2, lw=1)
    axes[0].text(-50, -1.4, "1 kHz", fontsize=7, color=INK2, ha="right", va="center")
    _save(fig, "fig_alphabets")
    plt.close(fig)
    print(f"figures written to {PAPER / 'figures'}")
    return 0


# ---------------------------------------------------------------------------------------------- report
class Report:
    def __init__(self):
        self.lines: list[str] = []
        (PAPER / "tables").mkdir(parents=True, exist_ok=True)

    def h(self, s: str) -> None:
        self.lines += ["", s, ""]

    def p(self, s: str) -> None:
        self.lines.append(s)

    def table(self, name: str, head: list[str], rows: list[list]) -> None:
        with open(PAPER / "tables" / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows([head, *rows])
        self.lines += ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
        self.lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
        self.lines.append("")


def report() -> int:
    plt = _style()
    R = Report()
    frozen = json.loads((RAW / "frozen.json").read_text(encoding="utf-8"))
    plan = pe.experiments()
    data = {e: load(e) for e in plan}
    errors = {e: d[1] for e, d in data.items()}
    rows = {e: d[0] for e, d in data.items()}
    complete = {e: len(rows[e]) == len(plan[e][1]) * (pe.N_SWEEP if plan[e][0] == "sweep" else pe.N_FULL_BYTES + pe.N_FULL_TEXT)
                for e in plan}

    R.p("# WhistleCode: test results for the paper")
    R.p("")
    R.p(f"Generated {time.strftime('%Y-%m-%d %H:%M')} by `experiments/paper_analysis.py report` from the campaign in "
        f"`outputs/paper/` (seed {frozen['seed']}, started {frozen['created_utc']}).")
    R.p("")
    R.p(f"Frozen: git {frozen['git_commit'][:8]}, config.toml {frozen['config_toml_sha256'][:12]}, codebook "
        f"{frozen['codebook_sha256'][:12]}, rhythm bank {frozen['bank_sha256'][:12]}, VAE checkpoint (epoch 101) "
        f"{frozen['checkpoint_sha256'][:12]}, GMM {frozen['gmm_sha256'][:12]}. Rates: 95 % Wilson intervals in brackets.")
    R.p("")
    R.p("Noise: the sent file never contains any sea background (the sea supplies it). Recordings of encounters 214 (tuning) and "
        "276 (test) stand in for the sea only on the receiving side of these simulations. No message has yet been played "
        "through a speaker and recorded. Methods: `TEST_PROTOCOL.md`.")
    missing = [e for e in plan if not complete[e]]
    if missing or any(errors.values()):
        R.p("")
        R.p(f"**Incomplete:** {', '.join(f'{e} ({len(rows[e])} trials)' for e in missing) or 'none'}; trials that raised an error: "
            f"{sum(errors.values())}.")

    verdicts: list[tuple] = []           # (test, pass mark, measured, verdict), tabled at the top once every section has run
    vpos = len(R.lines)

    # --- headline: E1 and final
    R.h("## 1. Clean channel (E1) and the frozen final run")
    head = ["Test", "Messages", "Exact", "Binary payloads", "Text payloads", "Whistles lost / wrong",
            "Failed at (frame / header / payload)", "Wrong text accepted", "Wrong-key accepts", "Pass mark", "Verdict"]
    body = []
    for e, mark, need in (("clean", "100 % exact", 1.0), ("final", ">= 95 % exact", 0.95)):
        rs_ = rows[e]
        if not rs_:
            continue
        s = summary(rs_)
        b = [r for r in rs_ if r["kind"] == "bytes"]
        t = [r for r in rs_ if r["kind"] == "text"]
        verdict = "PASS" if s["rate"] >= need and s["wrong_text"] == 0 else "FAIL"
        verdicts.append((("E1 clean channel" if e == "clean" else "Final run, encounter 276, 10 dB"), mark, pct(s["exact"], s["n"]),
                         verdict + ("" if complete[e] else " (incomplete)")))
        body.append(["E1 clean, no channel" if e == "clean" else "Final: encounter 276, 10 dB", s["n"], pct(s["exact"], s["n"]),
                     f"{sum(r['exact'] for r in b)}/{len(b)}", f"{sum(r['exact'] for r in t)}/{len(t)}",
                     f"{100 * s['lost']:.1f} % / {100 * s['wrong']:.1f} %", " / ".join(str(x) for x in failures(rs_)),
                     s["wrong_text"], s["wrong_key"], mark, verdict + ("" if complete[e] else " (incomplete)")])
    R.table("t1_clean_final", head, body)
    R.p("Failed at: frame = none of the receiver's 8 frame candidates lay within "
        f"{1000 * pe.FRAME_TOLERANCE_S:.0f} ms of the true start; header / payload = the frame was found but that part could not "
        "be repaired, or its CRC failed.")
    R.p("")

    fin = rows["final"]
    if fin:
        R.p("**Final run by message size** (number of data whistles, header included; preamble excluded):")
        R.p("")
        head = ["Data whistles", "Messages", "Exact", "Binary / text exact", "Whistles lost / wrong", "Failed at (frame / header / payload)",
                "Exact with the frame start given"]
        body = []
        for lo, hi in ((0, 60), (60, 80), (80, 100), (100, 120), (120, 10 ** 6)):
            rr = [r for r in fin if lo <= r["n_symbols"] < hi]
            if not rr:
                continue
            s = summary(rr)
            b = [r for r in rr if r["kind"] == "bytes"]
            t = [r for r in rr if r["kind"] == "text"]
            body.append([f"{lo}-{hi - 1}" if hi < 10 ** 6 else f">= {lo}", s["n"], pct(s["exact"], s["n"]),
                         f"{sum(r['exact'] for r in b)}/{len(b)} / {sum(r['exact'] for r in t)}/{len(t)}",
                         f"{100 * s['lost']:.1f} % / {100 * s['wrong']:.1f} %", " / ".join(str(x) for x in failures(rr)),
                         f"{s['oracle_exact']}/{s['n']}"])
        R.table("t1b_final_by_size", head, body)

    # --- SNR sweep
    R.h("## 2. Message success against SNR (E2, E8)")
    R.p("The sweep set: 50 compact-text messages of 8-32 characters, the same messages at every point. SNR is narrowband (per "
        "93.75 Hz bin), measured at the quietest level a data whistle can have; WhistleCode's data whistles sit 0-5 dB above it, "
        "the baseline's 2.5 dB above it.")
    R.p("")
    head = ["SNR (dB)"] + [f"{lab}" for lab in ("WhistleCode, 214 noise", "WhistleCode, 276 noise", "Chirp baseline, 276 noise")] + \
           ["276: lost / wrong whistles", "Baseline: lost / wrong"]
    body = []
    sweeps = {e: by_cond(rows[e]) for e in ("snr214", "snr276", "baseline")}
    for ci, snr in enumerate(pe.SWEEP_SNRS):
        line = [f"{snr:g}"]
        for e in ("snr214", "snr276", "baseline"):
            rr = sweeps[e].get(ci, [])
            line.append(pct(sum(r["exact"] for r in rr), len(rr)))
        for e in ("snr276", "baseline"):
            rr = sweeps[e].get(ci, [])
            s = summary(rr) if rr else None
            line.append(f"{100 * s['lost']:.1f} / {100 * s['wrong']:.1f} %" if s else "-")
        body.append(line)
    R.table("t2_snr_sweep", head, body)

    fig, ax = plt.subplots(figsize=(6.0, 3.6))
    for e, color, lab, dy in (("snr214", S3, "WhistleCode, 214 (tuning)", 3), ("snr276", S1, "WhistleCode, 276 (test)", -3),
                              ("baseline", S2, "Chirp baseline, 276", 0)):
        cs = [ci for ci in range(len(pe.SWEEP_SNRS)) if sweeps[e].get(ci)]
        if cs:
            _line(ax, [pe.SWEEP_SNRS[c] for c in cs], {pe.SWEEP_SNRS[c]: sweeps[e][c] for c in cs}, color, lab, dy=dy, label_at_end=False)
    ax.set_xlabel("narrowband SNR (dB)")
    ax.set_ylabel("messages decoded exactly (%)")
    ax.set_ylim(-3, 103)
    ax.set_xticks(pe.SWEEP_SNRS[::2])
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, title="noise encounter", title_fontsize=8)
    _save(fig, "fig_success_vs_snr")
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0), sharey=True)
    for ax, key, title in ((axes[0], "lost", "a  Data whistles lost (missed or doubtful)"), (axes[1], "wrong", "b  Data whistles read wrong")):
        for e, color, lab in (("snr214", S3, "WhistleCode (214)"), ("snr276", S1, "WhistleCode (276)"), ("baseline", S2, "Baseline (276)")):
            cs = [ci for ci in range(len(pe.SWEEP_SNRS)) if sweeps[e].get(ci)]
            if cs:
                ax.plot([pe.SWEEP_SNRS[c] for c in cs], [100 * summary(sweeps[e][c])[key] for c in cs], color=color, marker="o",
                        markeredgecolor="#ffffff", label=lab)
        ax.set_title(title, loc="left", color=INK)
        ax.set_xlabel("narrowband SNR (dB)")
    axes[0].set_ylabel("% of data whistles (true frame start)")
    axes[1].legend(loc="upper right")
    _save(fig, "fig_whistle_errors_vs_snr")
    plt.close(fig)

    # --- sea
    R.h("## 3. The simulated sea (E3), encounter-276 noise")
    rng_rows = by_cond(rows["range"])
    conds = plan["range"][1]
    head = ["Range (km)"] + [f"{s:g} dB" for s in pe.SEA_SNRS] + ["Lost / wrong whistles (all SNRs)"]
    body = []
    for r_km in pe.RANGES_KM:
        idx = [i for i, c in enumerate(conds) if c["range_km"] == r_km]
        line = [f"{r_km:g}"] + [pct(sum(x["exact"] for x in rng_rows.get(i, [])), len(rng_rows.get(i, []))) for i in idx]
        allr = [x for i in idx for x in rng_rows.get(i, [])]
        s = summary(allr) if allr else None
        body.append(line + [f"{100 * s['lost']:.1f} / {100 * s['wrong']:.1f} %" if s else "-"])
    ref = ["no echoes (snr276)"] + [pct(sum(x["exact"] for x in sweeps["snr276"].get(pe.SWEEP_SNRS.index(s), [])),
                                        len(sweeps["snr276"].get(pe.SWEEP_SNRS.index(s), []))) for s in pe.SEA_SNRS] + [""]
    R.p("**Echoes and absorption** (image method, four paths, Thorp absorption; no Doppler):")
    R.p("")
    R.table("t3a_range", head, [ref] + body)

    dop = by_cond(rows["doppler"])
    head = ["Closing speed (m/s)", "Exact", "Timing drift over a median message (ms)", "Lost / wrong whistles"]
    body = []
    for ci, v in enumerate(pe.SPEEDS_MPS):
        rr = dop.get(ci, [])
        s = summary(rr) if rr else None
        body.append([f"{v:+g}", pct(s["exact"], s["n"]) if s else "-",
                     f"{statistics.median(abs(r['drift_ms']) for r in rr):.0f}" if rr else "-",
                     f"{100 * s['lost']:.1f} / {100 * s['wrong']:.1f} %" if s else "-"])
    R.p("**Doppler alone** at 15 dB (one time-scaling per message; positive = closing, heard early):")
    R.p("")
    R.table("t3b_doppler", head, body)

    sea_rows = by_cond(rows["sea"])
    head = ["SNR (dB)", "Exact", "Lost / wrong whistles", "Failed at (frame / header / payload)"]
    body = []
    for ci, snr in enumerate(pe.SEA_SNRS):
        rr = sea_rows.get(ci, [])
        if rr:
            s = summary(rr)
            body.append([f"{snr:g}", pct(s["exact"], s["n"]), f"{100 * s['lost']:.1f} / {100 * s['wrong']:.1f} %",
                         " / ".join(str(x) for x in failures(rr))])
    R.p("**Random sea** per message (range 0.2-2 km, water 50-1,000 m, closing speed up to 3 m/s; echoes, absorption and Doppler):")
    R.p("")
    R.table("t3c_random_sea", head, body)

    if dop:
        fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0))
        cs = sorted(dop)
        _line(axes[0], [pe.SPEEDS_MPS[c] for c in cs], {pe.SPEEDS_MPS[c]: dop[c] for c in cs}, S1, "", label_at_end=False)
        axes[0].set_xlabel("closing speed (m/s)")
        axes[0].set_ylabel("messages decoded exactly (%)")
        axes[0].set_title("a  Doppler alone, 15 dB", loc="left", color=INK)
        axes[0].set_ylim(-3, 103)
        for j, snr in enumerate(pe.SEA_SNRS):
            pts = [(r_km, rng_rows.get(i, [])) for i, c in enumerate(conds) for r_km in [c["range_km"]] if c["snr"] == snr]
            pts = [(a, b) for a, b in pts if b]
            if pts:
                _line(axes[1], [a for a, _ in pts], {a: b for a, b in pts}, ORDINAL[j], f"{snr:g} dB", band=False, label_at_end=False)
        axes[1].set_xscale("log")
        axes[1].set_xticks(list(pe.RANGES_KM))
        axes[1].set_xticklabels([f"{r:g}" for r in pe.RANGES_KM])
        axes[1].minorticks_off()
        axes[1].set_xlabel("range (km)")
        axes[1].set_title("b  Echoes and absorption", loc="left", color=INK)
        axes[1].set_ylim(-3, 103)
        axes[1].legend(title="SNR", loc="center left", bbox_to_anchor=(0.0, 0.47))
        _save(fig, "fig_sea")
        plt.close(fig)

    # --- tau
    R.h("## 4. Latent variation tau (E5), encounter-214 noise, 10 dB")
    tau_rows = by_cond(rows["tau"])
    head = ["tau", "Exact", "Lost / wrong whistles"]
    body = []
    ten = sweeps["snr214"].get(pe.SWEEP_SNRS.index(10.0), [])
    entries = [(t, tau_rows.get(i, [])) for i, t in enumerate(pe.TAUS)] + [(0.5, ten)]
    for t, rr in sorted(entries, key=lambda e: e[0]):
        if rr:
            s = summary(rr)
            body.append([f"{t:g}" + (" (deployed; snr214 at 10 dB)" if t == 0.5 else ""), pct(s["exact"], s["n"]),
                         f"{100 * s['lost']:.1f} / {100 * s['wrong']:.1f} %"])
    R.table("t4_tau", head, body)

    # --- false messages
    R.h("## 5. False messages")
    all_trials = [r for e in plan for r in rows[e]]
    n_wrong_key = len(all_trials)
    k_wrong_key = sum(r["wrong_key_accepted"] for r in all_trials)
    k_wrong_text = sum(r["ok"] and not r["exact"] for r in all_trials)
    k_oracle_wrong = sum(r["oracle_ok"] and not r["oracle_exact"] for r in all_trials)
    empty = [json.loads(s) for s in (RAW / "empty" / "trials.jsonl").read_text(encoding="utf-8").splitlines() if s.strip()] \
        if (RAW / "empty" / "trials.jsonl").exists() else []
    k_empty = sum(r["false_message"] for r in empty)
    head = ["Check", "Tries", "False messages", "95 % upper bound on the rate"]
    body = [["Recording with a message, receiver holds the right key: wrong text accepted", len(all_trials), k_wrong_text,
             f"{100 * zero_upper(len(all_trials)):.2f} %" if k_wrong_text == 0 else pct(k_wrong_text, len(all_trials))],
            ["Recording with a message, wrong key", n_wrong_key, k_wrong_key,
             f"{100 * zero_upper(n_wrong_key):.2f} %" if k_wrong_key == 0 else pct(k_wrong_key, n_wrong_key)],
            [f"No message: {len({r['recording'] for r in empty})} min of encounter-276 noise, random keys", len(empty), k_empty,
             f"{100 * zero_upper(len(empty)):.2f} %" if k_empty == 0 else pct(k_empty, len(empty))]]
    R.table("t5_false_messages", head, body)
    k_false = k_wrong_text + k_wrong_key + k_empty
    verdicts.append(("False messages (wrong text, wrong key, no message)", "0",
                     f"{k_false} in {len(all_trials) * 2 + len(empty)} tries", "PASS" if k_false == 0 else "FAIL"))
    if k_oracle_wrong:
        R.p(f"Reading at the true start also accepted {k_oracle_wrong} wrong texts.")

    # --- throughput and cost
    R.h("## 6. Throughput and computing cost")
    full = rows["clean"]
    head = ["Payload", "Messages", "Median length", "Median data whistles", "Median whistles played", "Median airtime (s)",
            "Median information rate (bit/s)"]
    body = []
    for kind, lab, unit in (("text", "Compact text", "characters"), ("bytes", "Binary", "bytes")):
        rr = [r for r in full if r["kind"] == kind]
        if rr:
            body.append([lab, len(rr), f"{statistics.median(r['length'] for r in rr):g} {unit}",
                         f"{statistics.median(r['n_symbols'] + r['n_preamble'] for r in rr):g}",
                         f"{statistics.median(r['n_symbols'] + r['n_preamble'] + r['n_cover'] for r in rr):g}",
                         f"{statistics.median(r['duration_s'] for r in rr):.0f}",
                         f"{statistics.median(r['info_bits'] / r['duration_s'] for r in rr):.2f}"])
    sw = rows["snr276"]
    if sw:
        body.append(["Sweep set (text, 8-32 characters)", len({r["msg_index"] for r in sw}),
                     f"{statistics.median(r['length'] for r in sw):g} characters",
                     f"{statistics.median(r['n_symbols'] + r['n_preamble'] for r in sw):g}",
                     f"{statistics.median(r['n_symbols'] + r['n_preamble'] + r['n_cover'] for r in sw):g}",
                     f"{statistics.median(r['duration_s'] for r in sw):.0f}",
                     f"{statistics.median(r['info_bits'] / r['duration_s'] for r in sw):.2f}"])
    R.table("t6_throughput", head, body)
    timed = [r for e in ("final", "snr214", "snr276") for r in rows[e]]
    if timed:
        audio_min = sum(r["duration_s"] for r in timed) / 60
        R.p(f"Computing cost on the laptop ({frozen['gpu']}; two campaign workers and the covertness test sharing it), "
            f"median per message: send {statistics.median(r['times']['send_s'] for r in timed):.2f} s, detect "
            f"{statistics.median(r['times']['detect_s'] for r in timed):.2f} s, decode {statistics.median(r['times']['decode_s'] for r in timed):.2f} s; "
            f"detection runs at {sum(r['times']['detect_s'] for r in timed) / audio_min:.1f} s per minute of audio "
            f"({len(timed)} messages, {audio_min:.0f} min of audio).")

    # --- covertness
    R.h("## 7. Covertness (E7, E9)")
    shapes_p, rhythm_p = RAW / "covert_shapes.json", RAW / "covert_rhythm.json"
    if shapes_p.exists():
        cs_ = json.loads(shapes_p.read_text(encoding="utf-8"))
        names = {"real_214": "Real whistles, encounter 214 (reference)", "whistlecode": "WhistleCode as deployed (tau 0.5)",
                 "tau_0.25": "WhistleCode, tau 0.25", "tau_0.75": "WhistleCode, tau 0.75", "tau_1": "WhistleCode, tau 1.0",
                 "plain": "Without the realism library", "baseline": "Chirp baseline"}
        head = ["Whistles compared with real encounter-276 whistles", "Whistles", "Discriminator AUC", "Main clues"] + \
               [f"W1 {k}" for k in ("L (ms)", "df (Hz)", "f_start (Hz)", "f_end (Hz)", "f_c (Hz)")]
        body = []
        for k, lab in names.items():
            if k in cs_["results"]:
                r = cs_["results"][k]
                body.append([lab, r["whistles"], f"{r['score']:.3f} +/- {r['spread']:.3f}",
                             ", ".join(c["feature"] for c in r["main_clues"][:3])] +
                            [f"{r['w1'][f]:.0f}" for f in ("L_ms", "df_hz", "f_start_hz", "f_end_hz", "f_c_hz")])
        R.p(f"In-range whistles only (100-450 ms, centre 5-12 kHz, span 0.3-5 kHz); {cs_['real_encounter_276_whistles']} real "
            "encounter-276 whistles. AUC: 0.50 = indistinguishable, 1.00 = always told apart; mean +/- s.d. over 5 splits by "
            "recording. Pass mark (E7): AUC <= 0.75 for the deployed sender.")
        R.p("")
        R.table("t7a_covert_shapes", head, body)
        if "whistlecode" in cs_["results"]:
            v = cs_["results"]["whistlecode"]["score"]
            verdicts.append(("E7 whistle-shape discriminator, deployed sender", "AUC <= 0.75",
                             f"{v:.3f} (two real encounters: {cs_['results'].get('real_214', {}).get('score', float('nan')):.3f})",
                             "PASS" if v <= 0.75 else "FAIL"))
        fig, ax = plt.subplots(figsize=(6.0, 2.9))
        order = [k for k in names if k in cs_["results"]]
        vals = [cs_["results"][k]["score"] for k in order]
        err = [cs_["results"][k]["spread"] for k in order]
        y = np.arange(len(order))[::-1]
        ax.barh(y, vals, xerr=err, color=[INK2 if k == "real_214" else (S1 if k == "whistlecode" else "#86b6ef") for k in order],
                height=0.62, error_kw={"ecolor": INK2, "elinewidth": 1, "capsize": 2})
        for _kk, yy, v, e_ in zip(order, y, vals, err):
            if v + e_ < 0.75 < v + e_ + 0.06:          # the label would sit on the pass-mark line: put it inside the bar
                ax.text(v - 0.008, yy, f"{v:.3f}", va="center", ha="right", fontsize=8, color="#ffffff")
            else:
                ax.text(v + e_ + 0.008, yy, f"{v:.3f}", va="center", fontsize=8, color=INK)
        ax.set_yticks(y)
        ax.set_yticklabels([names[k] for k in order], color=INK)
        ax.axvline(0.75, color=S2, lw=1.2, ls="--")
        ax.set_ylim(y[-1] - 0.6, y[0] + 1.1)
        ax.text(0.755, y[0] + 0.72, "pass mark 0.75", color=INK2, fontsize=7.5, va="center")
        ax.set_xlim(0.5, 1.07)
        ax.set_xlabel("AUC against real encounter-276 whistles (0.5 = indistinguishable)")
        ax.grid(axis="y", visible=False)
        _save(fig, "fig_covert_shapes")
        plt.close(fig)
    if rhythm_p.exists():
        cr = json.loads(rhythm_p.read_text(encoding="utf-8"))["results"]
        labs = {"alone": "WhistleCode stream on its own", "in_noise_10dB": "WhistleCode inside encounter-276 noise, 10 dB",
                "steady_v1_control": "Control: format v1's steady 0.55-0.95 s gaps"}
        head = ["44 s windows", "Coded windows (test)", "Real windows (train 214 / test 276)", "Rhythm AUC", "Pass mark (E9)"]
        body = [[labs[k], v["coded_test_windows"], f"{v['real_train_windows']} / {v['real_test_windows']}", f"{v['score']:.3f}",
                 ("PASS" if v["score"] <= 0.60 else "FAIL") + " (<= 0.60)" if k != "steady_v1_control" else "-"] for k, v in cr.items()]
        R.table("t7b_covert_rhythm", head, body)
        for k in ("alone", "in_noise_10dB"):
            if k in cr:
                verdicts.append((f"E9 rhythm: {labs[k]}", "AUC <= 0.60", f"{cr[k]['score']:.3f}",
                                 "PASS" if cr[k]["score"] <= 0.60 else "FAIL"))

    # --- ablations
    abl_p = RAW / "ablations.jsonl"
    if abl_p.exists():
        R.h("## 8. Receiver ablations (saved tracks of E2, no detector re-run)")
        ab = [json.loads(s) for s in abl_p.read_text(encoding="utf-8").splitlines() if s.strip()]
        lab = {"deployed": "Receiver as deployed (ratio 0.85, soft repair)",
               "no_soft_repair": "No soft repair (no retries that mark the most doubtful whistles as lost)",
               "ratio_0.75": "Stricter doubt rule (ratio 0.75)", "ratio_0.95": "Looser doubt rule (ratio 0.95)",
               "no_doubt_erasures": "No up-front doubt rule (ratio 1.0; soft repair still erases the most doubtful in turn)",
               "errors_only": "Errors only: every whistle given a symbol, no erasures, no soft repair"}
        R.p("Each variant decodes the same saved detector tracks with the key only. Ratio = distance to the best shape / distance "
            "to the second best; above it a whistle is erased before repair. Soft repair retries a failed block with the most "
            "doubtful whistles marked lost, one more at a time, leaving 2 parity symbols unused.")
        R.p("")
        snrs = [5.0, 7.5, 10.0, 15.0, 20.0]
        head = ["Receiver", "Noise"] + [f"{s:g} dB" for s in snrs] + ["All 13 SNRs", "Wrong text"]
        body = []
        for v, name in lab.items():
            for exp in ("snr214", "snr276"):
                rr = [a for a in ab if a["exp"] == exp]
                line = [name, exp[3:]]
                for s in snrs:
                    sub = [a for a in rr if a["cond_index"] == pe.SWEEP_SNRS.index(s)]
                    line.append(f"{sum(a[v] for a in sub)}/{len(sub)}")
                line += [f"{sum(a[v] for a in rr)}/{len(rr)}", sum(a[v + "_wrong_text"] for a in rr)]
                body.append(line)
        oracle = []
        for exp in ("snr214", "snr276"):
            rr = sweeps[exp]
            line = ["Frame start given (oracle sync)", exp[3:]]
            for s in snrs:
                sub = rr.get(pe.SWEEP_SNRS.index(s), [])
                line.append(f"{sum(r['oracle_exact'] for r in sub)}/{len(sub)}")
            allr = rows[exp]
            line += [f"{sum(r['oracle_exact'] for r in allr)}/{len(allr)}", sum(r["oracle_ok"] and not r["oracle_exact"] for r in allr)]
            oracle.append(line)
        R.table("t8_ablations", head, body + oracle)

    n0 = len(R.lines)
    R.h("## Verdicts against the pass marks (set in PLAN.md section 8.6 before these runs)")
    R.table("t0_verdicts", ["Test", "Pass mark", "Measured", "Verdict"], [list(v) for v in verdicts])
    block = R.lines[n0:]
    del R.lines[n0:]
    R.lines[vpos:vpos] = block

    PAPER.mkdir(parents=True, exist_ok=True)
    (PAPER / "RESULTS.md").write_text("\n".join(R.lines) + "\n", encoding="utf-8")
    print(f"written {PAPER / 'RESULTS.md'}, tables/ and figures/")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=("ablate", "examples", "report"))
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")
    return {"ablate": ablate, "examples": examples, "report": report}[args.command]()


if __name__ == "__main__":
    sys.exit(main())
