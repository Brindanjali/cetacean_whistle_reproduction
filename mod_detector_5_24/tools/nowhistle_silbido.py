"""No-whistle test, Silbido: false alarms per minute, next to our detectors, with paired ranges.

    python mod_detector_5_24/tools/nowhistle_silbido.py

Reads the unpacked silbido_nowhistle_detections.zip in results/nowhistle/silbido/ (run_silbido_nowhistle.m: nowhistle/<tag>/
<file>.det for silbido-graph (default, 10 dB), -thr8 and -thr12; its log; the manifest it checked) and our detectors'
results/nowhistle/summary.json (colab_nowhistle_test.py). Same rules as ours: the benchmark rule (median pitch 5-24 kHz,
>= 150 ms) and all tracks the detector outputs. Minutes come from the manifest (the WAV lengths Silbido read).
Ranges: 95 % bootstrap over encounters within each group (10,000 resamples, seed 2026); the difference to Silbido is
paired (the same resampled encounters for both methods). Writes results/nowhistle/silbido_summary.md and .json.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "mod_detector_5_24"))
import dclde2011 as D  # noqa: E402

RES = ROOT / "results" / "nowhistle"
SIL = RES / "silbido"
MANIFEST_MD5 = "1a47c5a9d22842861b6db9d034670ae3"   # printed by colab_silbido_audio.py on 13 Nov 2026
TAGS = {"silbido-graph": "Silbido, default (10 dB)", "silbido-graph-thr8": "Silbido, 8 dB (more sensitive)",
        "silbido-graph-thr12": "Silbido, 12 dB (less sensitive)"}
OURS = {"ridgenet-5-24": "ours, 5-24 kHz (paper)", "ridgenet-v2c": "ours, 2-24 kHz"}
BENCH, ALL = "benchmark rule (5-24 kHz, >= 150 ms)", "all tracks the detector outputs"
GROUPS = ("beaked whale", "sperm whale")
SEED, N_BOOT = 2026, 10000


def main() -> None:
    man = SIL / "nowhistle_wav_manifest.csv"
    if hashlib.md5(man.read_bytes()).hexdigest() != MANIFEST_MD5:
        sys.exit("STOP: the manifest Silbido used is not the one made in Colab on 13 Nov")
    log = (SIL / "silbido_nowhistle_log.txt").read_text(encoding="utf-8")
    if MANIFEST_MD5 not in log:
        sys.exit("STOP: the Silbido log does not show the expected manifest MD5")
    with open(man, encoding="utf-8") as fh:
        files = list(csv.DictReader(fh))
    minutes = {}                      # (group, encounter) -> minutes
    for f in files:
        k = (f["group"], f["encounter_id"])
        minutes[k] = minutes.get(k, 0.0) + float(f["duration_s"]) / 60

    counts = {}                       # method -> rule -> (group, encounter) -> detections
    for tag in TAGS:
        c = {BENCH: {}, ALL: {}}
        for f in files:
            det = SIL / "nowhistle" / tag / f["wav_file"].replace(".wav", ".det")
            tr = D.read_tonals(det)
            k = (f["group"], f["encounter_id"])
            c[ALL][k] = c[ALL].get(k, 0) + len(tr)
            c[BENCH][k] = c[BENCH].get(k, 0) + int(sum(t[-1] - t[0] >= 0.150 and 5000 <= np.median(fr) <= 24000 for t, fr in tr))
        counts[tag] = c
    ours = json.loads((RES / "summary.json").read_text())["results"]
    for name in OURS:                 # per-encounter counts back from the stored per-minute rates
        c = {}
        for rule in (BENCH, ALL):
            c[rule] = {}
            for g in GROUPS:
                r = ours[name][rule][g]
                for enc, rate in r["per_encounter_per_minute"].items():
                    c[rule][(g, enc)] = int(round(rate * minutes[(g, enc)]))
                assert sum(c[rule][(g, e)] for e in r["per_encounter_per_minute"]) == r["detections"], (name, rule, g)
        counts[name] = c

    rng = np.random.default_rng(SEED)
    picks = {g: [rng.integers(0, n, n) for _ in range(N_BOOT)]
             for g, n in ((g, sum(1 for k in minutes if k[0] == g)) for g in GROUPS)}
    picks["both"] = None

    def stats(method, rule, group):
        groups = GROUPS if group == "both" else (group,)
        tot_n = sum(counts[method][rule][k] for k in minutes if k[0] in groups)
        tot_m = sum(m for k, m in minutes.items() if k[0] in groups)
        return tot_n, tot_m, boot(lambda keys: sum(counts[method][rule][k] for k in keys), groups)

    def boot(f, groups):
        """per-minute value for each resample; 'both' = both groups resampled separately, then pooled"""
        out = np.empty(N_BOOT)
        keys = {g: [k for k in minutes if k[0] == g] for g in groups}
        for b in range(N_BOOT):
            sel = [keys[g][j] for g in groups for j in picks[g][b]]
            out[b] = f(sel) / sum(minutes[k] for k in sel)
        return out

    res, md = {"seed": SEED, "n_boot": N_BOOT, "manifest_md5": MANIFEST_MD5, "rates": {}, "differences": {}}, []
    md += ["# No-whistle test: Silbido next to our detectors", "",
           "False alarms per minute on 2017 beaked whale and sperm whale recordings (no whistling species logged within "
           "15 min; the same 146 files for every method). Range: 95 % bootstrap over encounters (seed 2026). Silbido 3.0, "
           "classic graph search, run 13 Nov 2026 with `run_silbido_nowhistle.m` on channel 0 resampled to 192 kHz. Made by "
           "`mod_detector_5_24/tools/nowhistle_silbido.py`.", ""]
    for rule in (BENCH, ALL):
        md += [f"## {rule[0].upper() + rule[1:]}", "", "| Method | Beaked whales | Sperm whales | Both |", "|---|---|---|---|"]
        for method, label in {**OURS, **TAGS}.items():
            cells = []
            for g in (*GROUPS, "both"):
                n, m, b = stats(method, rule, g)
                lo, hi = np.percentile(b, [2.5, 97.5])
                res["rates"].setdefault(method, {}).setdefault(rule, {})[g] = {
                    "detections": n, "minutes": round(m, 2), "per_minute": n / m, "range95": [float(lo), float(hi)]}
                cells.append(f"{n / m:.2f} ({lo:.2f} to {hi:.2f}); {n}")
            md.append(f"| {label} | " + " | ".join(cells) + " |")
        md.append("")
    md += ["## Paired differences, benchmark rule (per minute; ours minus Silbido default)", "",
           "| Comparison | Beaked whales | Sperm whales | Both |", "|---|---|---|---|"]
    for name, label in OURS.items():
        cells = []
        for g in (*GROUPS, "both"):
            groups = GROUPS if g == "both" else (g,)
            a = boot(lambda keys: sum(counts[name][BENCH][k] for k in keys), groups)  # noqa: B023
            s = boot(lambda keys: sum(counts["silbido-graph"][BENCH][k] for k in keys), groups)
            d = a - s
            m = res["rates"][name][BENCH][g]["minutes"]
            n_a = res["rates"][name][BENCH][g]["detections"]
            n_s = res["rates"]["silbido-graph"][BENCH][g]["detections"]
            lo, hi = np.percentile(d, [2.5, 97.5])
            res["differences"].setdefault(name, {})[g] = {"per_minute": (n_a - n_s) / m, "range95": [float(lo), float(hi)]}
            cells.append(f"{(n_a - n_s) / m:+.2f} ({lo:+.2f} to {hi:+.2f})")
        md.append(f"| {label} minus Silbido | " + " | ".join(cells) + " |")
    md += ["", "Cells: per minute (95 % range); number of detections. A range that does not include 0 means a clear "
           "difference.", ""]
    (RES / "silbido_summary.json").write_text(json.dumps(res, indent=2))
    (RES / "silbido_summary.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
