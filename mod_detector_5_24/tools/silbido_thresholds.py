"""Silbido sensitivity: its peak threshold at 8, 10 (default) and 12 dB on DCLDE 2011 and on the no-whistle test.

    python mod_detector_5_24/tools/silbido_thresholds.py --data PATH/dclde2011

--data: a DCLDE 2011 folder with development/<species>/<stem>.wav and .ann for all 12 test recordings (the layout of
colab_download_dclde2011.py; here D:/silbido_run/dclde2011, whose recordings run_silbido_nowhistle.m checked by MD5).
Scores results/nowhistle/silbido/dclde2011/silbido-graph-thr8/ and -thr12/ (from run_silbido_nowhistle.m, 13 Nov 2026)
with the same scorer and rules as the committed results, writing the same score files as `dclde2011.py score` (2011
answer key, >= 150 ms; with and without the 30 % rule; 5-24 kHz and all frequencies) to results/silbido_thresholds/<tag>/
(kept out of results/dclde2011_detections/, whose files colab_verify_scores.py re-scores from Drive). The default
(silbido-graph, 5 Nov, in results/dclde2011_detections/) is re-scored too and must equal its committed score files.
Writes results/silbido_thresholds/silbido_thresholds.md and .json, with the no-whistle rates from
results/nowhistle/silbido_summary.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "mod_detector_5_24"))
import dclde2011 as D  # noqa: E402

RES = ROOT / "results" / "dclde2011_detections"
NEW = ROOT / "results" / "nowhistle" / "silbido" / "dclde2011"   # the 13 Nov threshold runs
OUTD = ROOT / "results" / "silbido_thresholds"
TAGS = {"silbido-graph-thr8": "Silbido, 8 dB", "silbido-graph": "Silbido, 10 dB (default)",
        "silbido-graph-thr12": "Silbido, 12 dB"}
OURS = "ridgenet-5-24_keep-harmonics"
VARIANTS = [(False, 0.0), (False, 0.3), (True, 0.0), (True, 0.3)]   # (full band, min overlap)
BENCH = "benchmark rule (5-24 kHz, >= 150 ms)"


def name(full_band: bool, ov: float) -> str:
    return f"score_gt2011_min150ms{'_fullband' if full_band else ''}{'' if ov == 0.3 else f'_ov{ov:g}'}.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    a = ap.parse_args()
    missing = [f"{sp}/{st}" for sp, st in D.TEST_FILES
               if not ((a.data / "development" / sp / f"{st}.wav").exists() and D.gt_path(a.data, sp, st, "2011").exists())]
    if missing:
        sys.exit(f"STOP: recordings or answer keys missing in {a.data}: {missing}")
    band = D.band_hz(D.load_cfg([]))
    scores = {}
    for tag in TAGS:
        for fb, ov in VARIANTS:
            det_dir = RES / tag if tag == "silbido-graph" else NEW / tag
            res = D.score_set(a.data, det_dir, "2011", band, fb, ov, min_det_s=0.150)
            if res["n_files"] != 12:
                sys.exit(f"STOP: {tag} scored {res['n_files']} of 12 files")
            if tag == "silbido-graph":   # committed 5 Nov: must reproduce exactly
                old = json.loads((RES / tag / name(fb, ov)).read_text())
                if json.dumps(old, sort_keys=True) != json.dumps(json.loads(json.dumps(res)), sort_keys=True):
                    sys.exit(f"STOP: re-scoring {tag}/{name(fb, ov)} does not reproduce the committed file")
            else:
                (OUTD / tag).mkdir(parents=True, exist_ok=True)
                (OUTD / tag / name(fb, ov)).write_text(json.dumps(res, indent=2))
            scores[(tag, fb, ov)] = res
    print("default (5 Nov) re-scored: all 4 committed score files reproduced exactly")
    ours = {(fb, ov): json.loads((RES / OURS / name(fb, ov)).read_text()) for fb, ov in VARIANTS}
    nw = json.loads((ROOT / "results" / "nowhistle" / "silbido_summary.json").read_text())["rates"]

    def row(label, res, nw_rate):
        av = res["species_average"]
        fp = sum(v["false_pos"] for v in res["files"].values())
        r = nw_rate[BENCH]["both"]
        return (f"| {label} | {av['precision']:.1f} | {av['recall']:.1f} | {av['f1']:.1f} | {fp} | "
                f"{r['per_minute']:.2f} ({r['range95'][0]:.2f} to {r['range95'][1]:.2f}) |")

    md = ["# Silbido at three detection thresholds", "",
          "Silbido 3.0, classic graph search, Silbido's default settings except the peak threshold (`energy_thresh`). "
          "DCLDE 2011: Li et al. 2023 test set, 2011 answer key, species average of 3 species-pooled scores, detections "
          ">= 150 ms. No-whistle: false alarms per minute on 146 beaked and sperm whale minutes, benchmark rule "
          "(5-24 kHz, >= 150 ms), 95 % range over encounters. The 10 dB DCLDE scores are the 5 Nov run (re-scored here "
          "unchanged; the 13 Nov repeat gives the same scores). Made by `mod_detector_5_24/tools/silbido_thresholds.py`.",
          ""]
    out_json = {"dclde2011": {}, "nowhistle_benchmark_rule_both": {}}
    for fb, ov in VARIANTS:
        md += [f"## DCLDE 2011: {'all frequencies' if fb else '5-24 kHz'}, {'with' if ov else 'no'} 30 % rule"
               f"{' (main scoring)' if (fb, ov) == (False, 0.0) else ''}", "",
               "| Method | Precision | Recall | F1 | False alarms (DCLDE) | No-whistle false alarms per minute |",
               "|---|---|---|---|---|---|"]
        md.append(row("ours, 5-24 kHz (paper)", ours[(fb, ov)], nw["ridgenet-5-24"]))
        for tag, label in TAGS.items():
            md.append(row(label, scores[(tag, fb, ov)], nw[tag]))
            out_json["dclde2011"].setdefault(name(fb, ov), {})[tag] = scores[(tag, fb, ov)]["species_average"]
        out_json["dclde2011"][name(fb, ov)][OURS] = ours[(fb, ov)]["species_average"]
        md.append("")
    for k in ("ridgenet-5-24", *TAGS):
        out_json["nowhistle_benchmark_rule_both"][k] = nw[k][BENCH]["both"]
    (OUTD / "silbido_thresholds.md").write_text("\n".join(md), encoding="utf-8")
    (OUTD / "silbido_thresholds.json").write_text(json.dumps(out_json, indent=2))
    print("\n".join(md))


if __name__ == "__main__":
    main()
