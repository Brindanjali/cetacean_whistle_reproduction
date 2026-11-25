"""Statistics for the DCLDE 2011 benchmark: how sure are we about the gap between our detector and Silbido?

    python mod_detector_5_24/tools/dclde2011_stats.py [--n-boot 10000] [--seed 0]

Reads only the committed score files in results/dclde2011_detections/ (they hold per-recording counts); no audio.
Writes results/dclde2011_stats/stats.json and stats.md.

1. Bootstrap 95 % ranges: resample the recordings with replacement, 3 per species (keeping the species balance), pool
   the counts per species and average over species exactly as dclde2011.py does; repeat n-boot times and take the 2.5th
   and 97.5th percentiles. Both methods use the SAME resampled recordings each time, which gives a paired range for the
   difference (ours - Silbido). With only 3 recordings per species there are just 10 distinct resamples per species, so
   the ranges are approximate.
2. Paired Wilcoxon signed-rank test on per-recording F1, recall and precision (12 pairs; ties dropped, exact p-value).
   Per-recording values are noisy for recordings with few whistles (Qx-Dc-SC03 has 9).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "results" / "dclde2011_detections"
OUT = ROOT / "results" / "dclde2011_stats"
OURS, SIL = "ridgenet-5-24_keep-harmonics", "silbido-graph"
COMPARISONS = [   # (label, score file name); the same file name is compared for both methods
    ("5-24 kHz, no 30 % rule (main)", "score_gt2011_min150ms_ov0.json"),
    ("5-24 kHz, with 30 % rule", "score_gt2011_min150ms.json"),
    ("all frequencies, no 30 % rule", "score_gt2011_min150ms_fullband_ov0.json"),
    ("all frequencies, with 30 % rule", "score_gt2011_min150ms_fullband.json"),
]
COUNTS = ("detections_matched", "false_pos", "gt_matched", "gt_expected")


def load(tag: str, name: str):
    d = json.load(open(RES / tag / name))
    assert d["n_files"] == 12, f"{tag}/{name}: {d['n_files']} files"
    stems = list(d["files"])
    species = sorted({v["species"] for v in d["files"].values()})
    c = np.array([[d["files"][s][k] for k in COUNTS] for s in stems], float)   # (12 recordings, 4 counts)
    sp = np.array([species.index(d["files"][s]["species"]) for s in stems])
    return d, stems, sp, c


def prf(c):
    """c (..., 4) pooled counts -> precision, recall, F1 in percent (as dclde2011.summarise)."""
    det, fp, match, exp = np.moveaxis(c, -1, 0)
    p = 100 * det / (det + fp)
    r = 100 * match / exp
    return p, r, np.where(p + r > 0, 2 * p * r / (p + r), 0.0)


def species_average(c, sp, idx):
    """idx (n_boot, 12): chosen recordings, grouped so that idx[:, sp==k] are species k's picks. -> (n_boot, 3) P/R/F1."""
    out = []
    for k in np.unique(sp):
        pooled = c[idx[:, sp == k]].sum(axis=1)          # (n_boot, 4)
        out.append(np.stack(prf(pooled), axis=-1))       # (n_boot, 3)
    return np.mean(out, axis=0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-boot", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    report, md = {"n_boot": a.n_boot, "seed": a.seed, "comparisons": {}}, []
    for label, name in COMPARISONS:
        d_o, stems, sp, c_o = load(OURS, name)
        d_s, stems_s, sp_s, c_s = load(SIL, name)
        assert stems == stems_s and (sp == sp_s).all()
        # resample within species: for each species, pick 3 of its recordings with replacement
        idx = np.empty((a.n_boot, len(stems)), int)
        for k in np.unique(sp):
            members = np.flatnonzero(sp == k)
            idx[:, members] = rng.choice(members, size=(a.n_boot, len(members)), replace=True)
        point = {m: species_average(c, sp, np.arange(len(stems))[None])[0] for m, c in (("ours", c_o), ("silbido", c_s))}
        for m, d in (("ours", d_o), ("silbido", d_s)):   # must equal the committed species averages
            ref = [d["species_average"][k] for k in ("precision", "recall", "f1")]
            assert np.allclose(point[m], ref, rtol=0, atol=1e-9), (m, name, point[m], ref)
        boot = {"ours": species_average(c_o, sp, idx), "silbido": species_average(c_s, sp, idx)}
        boot["difference"] = boot["ours"] - boot["silbido"]
        point["difference"] = point["ours"] - point["silbido"]
        res = {"file": name, "metrics": {}}
        for j, metric in enumerate(("precision", "recall", "f1")):
            e = {m: {"value": float(point[m][j]),
                     "range95": [float(v) for v in np.percentile(boot[m][:, j], [2.5, 97.5])]} for m in boot}
            e["difference"]["share_of_resamples_ours_better"] = float((boot["difference"][:, j] > 0).mean())
            po, ps = prf(c_o)[j], prf(c_s)[j]                       # per recording
            diff = po - ps
            w = stats.wilcoxon(po, ps, zero_method="wilcox", method="exact")
            e["per_recording"] = {"ours_better": int((diff > 0).sum()), "silbido_better": int((diff < 0).sum()),
                                  "ties": int((diff == 0).sum()), "wilcoxon_statistic": float(w.statistic),
                                  "wilcoxon_p_two_sided": float(w.pvalue),
                                  "ours": dict(zip(stems, po.round(4).tolist())), "silbido": dict(zip(stems, ps.round(4).tolist()))}
            res["metrics"][metric] = e
        report["comparisons"][label] = res
        md += [f"### {label}  (`{name}`)", "",
               "| | Ours | Silbido | Ours - Silbido | Recordings ours / Silbido better / tie | Wilcoxon p |",
               "|---|---|---|---|---|---|"]
        for metric, e in res["metrics"].items():
            f = lambda m: f"{e[m]['value']:.1f} ({e[m]['range95'][0]:.1f} to {e[m]['range95'][1]:.1f})"  # noqa: B023, E731
            pr = e["per_recording"]
            md.append(f"| {metric} | {f('ours')} | {f('silbido')} | {f('difference')} | "
                      f"{pr['ours_better']} / {pr['silbido_better']} / {pr['ties']} | {pr['wilcoxon_p_two_sided']:.3f} |")
        md.append("")
    head = ["# DCLDE 2011: uncertainty of the comparison (12 recordings, species average)", "",
            f"Values in brackets: bootstrap 95 % range ({a.n_boot} resamples, 3 recordings per species drawn with "
            f"replacement, seed {a.seed}; approximate, only 3 recordings per species). The difference range is paired "
            "(same resamples for both methods). Wilcoxon: paired signed-rank test on per-recording values, two-sided, "
            "exact, ties dropped. Made by `mod_detector_5_24/tools/dclde2011_stats.py` from the committed score files.", ""]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "stats.json").write_text(json.dumps(report, indent=2))
    (OUT / "stats.md").write_text("\n".join(head + md))
    print("\n".join(head + md))
    print(f"saved {OUT / 'stats.json'} and {OUT / 'stats.md'}")


if __name__ == "__main__":
    main()
