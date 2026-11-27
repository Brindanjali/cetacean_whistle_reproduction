"""Our V1 results next to the paper's (Table 1 row L = 64, Table 3, Table 6 and, where the run has them, Table 2,
Fig. 11 and Table 4's prior-sampling row; transcribed from the paper PDF, pages 10-14).

Reads models/vaegmm/<run_id>/eval/table1_recon.json and table3_fig12_K<K>.json; writes post_training/out/paper_comparison.csv
and prints both tables. The paper's Table 3 uses K = 10,000 and 228,673 images (all encounters); ours K = 3,000 and the
63,490 images of encounter 191, so N differs by design. Our primary Table 3 weights are eq. 10 (configs/vaegmm.toml).

    python post_training/compare_paper.py
    python post_training/compare_paper.py --run-id V1_L64_b1e-4_critic_E191_epoch150

--run-id compares another run (default: V1's); its CSV is named paper_comparison_<run_id>.csv, so V1's stays as it is.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from whistlepipe.vaegmm.cli import EXPERIMENTS  # noqa: E402
from whistlepipe.vaegmm.config import load_vaegmm_config, main_k, resolve  # noqa: E402

RUN_ID = EXPERIMENTS["V1"]["run_id"]
OUT = ROOT / "post_training" / "out"

PAPER_T1_L64 = {"MSE": 0.5778, "PSNR_dB": 44.5274, "SSIM": 0.9861, "KL_latent": 43.1929}
# no: (N, W1 [ms for L, Hz otherwise], FFD, recall %, precision %, F1 %)
PAPER_T3 = {1: (30593, 1.0075, 0.0899, 98.94, 83.95, 90.83), 2: (8202, 1.7744, 1.4866, 99.33, 83.19, 90.54),
            3: (21409, 1.2985, 0.7703, 99.18, 87.31, 92.87), 4: (33972, 5.9156, 1.1677, 98.71, 88.07, 93.09),
            5: (21056, 3.4688, 1.2994, 98.81, 89.03, 93.66), 6: (28503, 3.3562, 0.2531, 99.07, 85.37, 91.71),
            7: (58918, 1.4625, 0.0599, 99.01, 85.08, 91.51), 8: (59624, 2.8969, 0.1105, 99.04, 84.96, 91.46),
            9: (22851, 2.9156, 0.3384, 98.69, 84.93, 91.29), 10: (19354, 3.9938, 0.6993, 98.71, 84.55, 91.08),
            11: (27062, 3.5906, 0.2902, 98.74, 86.04, 91.95), 12: (10712, 5.6063, 1.1084, 98.17, 90.84, 94.36),
            13: (48642, 3.5156, 0.1313, 98.93, 82.66, 90.07)}
# Table 6, VAE-GMM L = 64 (page 14): params, FLOPs, inference latency (B = 1), per-image latency at B = 16 and B = 32
PAPER_T6 = {"decoder_params": 368e3, "decoder_FLOPs": 557e6, "B1_latency_ms": 1.7, "B16_per_image_ms": 0.11,
            "B32_per_image_ms": 0.054}
# Table 2 (page 10), L = 64, beta = 1e-4: K -> (FID1, FID2, recall %, precision %, F1 %). It has no K = 3,000 row.
PAPER_T2 = {1000: (4.37, 72.81, 86.52, 89.58, 88.02), 5000: (3.04, 69.99, 86.92, 91.33, 89.07),
            10000: (2.68, 68.74, 87.21, 91.99, 89.54), 15000: (2.64, 68.45, 87.54, 92.34, 89.88)}
# Table 4 (page 13), ablation: row -> (FID1, FID2, recall %, precision %, F1 %); rows 3 and 4 at L = 64, K = 10,000
PAPER_T4 = {"(1) standard VAE": (91.83, 502.41, 23.70, 37.51, 29.05), "(2) WGAN-GP": (13.82, 202.51, 61.47, 83.17, 70.70),
            "(3) VAE-GMM w/o WGAN-GP": (7.37, 182.84, 80.58, 92.96, 86.33),
            "(4) VAE-GMM w/ WGAN-GP": (2.68, 68.74, 87.21, 91.99, 89.54)}
# Fig. 11 (page 11), values printed at the points: K -> (silhouette, Davies-Bouldin, Calinski-Harabasz)
PAPER_F11 = {1000: (0.167, 1.07, 17.8), 3000: (0.401, 0.767, 21.2), 5000: (0.517, 0.621, 24.9), 7000: (0.638, 0.547, 24.9),
             10000: (0.745, 0.448, 31.3), 12000: (0.78, 0.455, 29.8), 15000: (0.798, 0.425, 29.0)}


def out_name(run_id: str) -> str:
    return "paper_comparison.csv" if run_id == RUN_ID else f"paper_comparison_{run_id}.csv"


def warm_name(run_id: str) -> str:
    return "table6_warm.json" if run_id == RUN_ID else f"table6_warm_{run_id}.json"


def compare(cfg, run_id: str, K: int) -> list[dict]:
    """The run's rows next to the paper's, printed as tables."""
    ev = resolve(cfg["paths"]["runs_dir"]) / run_id / "eval"
    rows = []
    t1 = json.loads((ev / "table1_recon.json").read_text(encoding="utf-8"))
    print("Table 1, L = 64          ours        paper")
    for k, ours in (("MSE", t1["MSE_per_image_sse"]), ("PSNR_dB", t1["PSNR_dB"]), ("SSIM", t1["SSIM"]), ("KL_latent", t1["KL_latent"])):
        print(f"  {k:10s} {ours:14.4f} {PAPER_T1_L64[k]:12.4f}")
        rows.append({"table": "1", "row": "L=64", "metric": k, "ours": ours, "paper": PAPER_T1_L64[k]})
    t3 = json.loads((ev / f"table3_fig12_K{K}.json").read_text(encoding="utf-8"))
    w = t3["weights_primary"]
    print(f"\nTable 3 (ours: K = {K}, weights {w}; paper: K = 10,000)")
    print(" no feature  range    N ours/paper    W1 ours/paper        FFD ours/paper   recall %       precision %    F1 %")
    for r in t3["rows"]:
        p = PAPER_T3[r["no"]]
        m = r[w]
        ours = (r["N"], m["W1"], m["FFD"], 100 * m["recall"], 100 * m["precision"], 100 * m["f1"])
        print(f" {r['no']:2d} {r['feature']:7s} {r['c1']:3}-{r['c2']:<3} {ours[0]:6d}/{p[0]:<6d} {ours[1]:7.3f}/{p[1]:<7.3f} {m['W1_unit']:2s} "
              f"{ours[2]:7.3f}/{p[2]:<7.3f} {ours[3]:6.2f}/{p[3]:<6.2f} {ours[4]:6.2f}/{p[4]:<6.2f} {ours[5]:6.2f}/{p[5]:<6.2f}")
        for name, o, pv in zip(("N", f"W1_{m['W1_unit']}", "FFD", "recall_pct", "precision_pct", "F1_pct"), ours, p):
            rows.append({"table": "3", "row": f"condition {r['no']} ({r['feature']} {r['c1']}-{r['c2']})", "metric": name,
                         "ours": o, "paper": pv})
    z = t3["fig12_lnFFD"]["Z"]
    diag = [z[i][i] for i in range(len(z))]
    off = [z[i][j] for i in range(len(z)) for j in range(len(z)) if i != j]
    print(f"\nFig. 12: diagonal ln FFD {min(diag):.2f} .. {max(diag):.2f}; off-diagonal {min(off):.2f} .. {max(off):.2f}; "
          f"rows whose diagonal is the row minimum: {sum(z[i][i] == min(z[i]) for i in range(len(z)))} of {len(z)}")
    t6p = ev / "table6_cost.json"
    if t6p.exists():
        t6 = json.loads(t6p.read_text(encoding="utf-8"))
        print(f"\nTable 6 (ours on {t6.get('gpu_name') or t6['device']}; the paper does not name its timing GPU)")
        print("  metric                 decoder only   GMM sampling + decoder   paper")
        ours = {"decoder_params": (t6["decoder_params"], None), "decoder_FLOPs": (t6["decoder_table6_flops"], None)}
        for B, key in ((1, "B1_latency_ms"), (16, "B16_per_image_ms"), (32, "B32_per_image_ms")):
            what = "batch_s" if B == 1 else "per_image_s"
            ours[key] = tuple(1e3 * t6[f"B{B}_{m}_{what}"] for m in ("decoder_only", "gmm_sampling_plus_decoder"))
        for key, (a, b) in ours.items():
            print(f"  {key:22s} {a:12.4g}   {'' if b is None else f'{b:12.4g}':>22s}   {PAPER_T6[key]:.4g}")
            rows.append({"table": "6", "row": "VAE-GMM L=64 decoder only", "metric": key, "ours": a, "paper": PAPER_T6[key]})
            if b is not None:
                rows.append({"table": "6", "row": "VAE-GMM L=64 GMM sampling + decoder", "metric": key, "ours": b,
                             "paper": PAPER_T6[key]})
        wp = OUT / warm_name(run_id)
        if wp.exists():
            w6 = json.loads(wp.read_text(encoding="utf-8"))
            print("  warm GPU, no pause (post_training/table6_warm.py):")
            for B, key in ((1, "B1_latency_ms"), (16, "B16_per_image_ms"), (32, "B32_per_image_ms")):
                what = "batch_s" if B == 1 else "per_image_s"
                a, b = (1e3 * w6[f"B{B}_{m}_{what}"] for m in ("decoder_only", "gmm_sampling_plus_decoder"))
                print(f"  {key:22s} {a:12.4g}   {b:22.4g}   {PAPER_T6[key]:.4g}")
                for row, v in (("decoder only, warm", a), ("GMM sampling + decoder, warm", b)):
                    rows.append({"table": "6", "row": f"VAE-GMM L=64 {row}", "metric": key, "ours": v, "paper": PAPER_T6[key]})
    t2p = ev / f"gen_gmm_K{K}.json"
    if t2p.exists():
        t2 = json.loads(t2p.read_text(encoding="utf-8"))
        pr = t2[t2.get("primary_PR", "PR_raw")]
        ours = (t2["FID1"], t2["FID2"], 100 * pr["recall"], 100 * pr["precision"], 100 * pr["f1"])
        names = ("FID1", "FID2", "recall_pct", "precision_pct", "F1_pct")
        print(f"\nTable 2, L = 64, beta = 1e-4 (ours: K = {K}, {t2['n_generated']:,} generated; the paper has no K = {K} row)")
        print(f"  {'':16s} {'FID1':>7s} {'FID2':>7s} {'recall %':>9s} {'precision %':>12s} {'F1 %':>7s}")
        print(f"  {'ours K=' + str(K):16s} {ours[0]:7.2f} {ours[1]:7.2f} {ours[2]:9.2f} {ours[3]:12.2f} {ours[4]:7.2f}")
        for pk, pv in PAPER_T2.items():
            print(f"  {'paper K=' + str(pk):16s} {pv[0]:7.2f} {pv[1]:7.2f} {pv[2]:9.2f} {pv[3]:12.2f} {pv[4]:7.2f}")
            for name, o, v in zip(names, ours, pv):
                rows.append({"table": "2", "row": f"ours K={K} vs paper K={pk}", "metric": name, "ours": o, "paper": v})
    f11p = ev / "fig11_clustering.json"
    if f11p.exists():
        f11 = json.loads(f11p.read_text(encoding="utf-8"))
        print("\nFig. 11 (ours: encounter 191, 63,490 images; paper: 228,673 images)")
        print("      K   silhouette ours/paper   DBI ours/paper     CH ours/paper")
        for r in f11["rows"]:
            ps, pd, pc = PAPER_F11[r["K"]]
            print(f"  {r['K']:6d}   {r['silhouette']:8.3f}/{ps:<8.3f}    {r['davies_bouldin']:6.3f}/{pd:<6.3f}   "
                  f"{r['calinski_harabasz']:9.4g}/{pc:<6.4g}")
            for name, o, pv in (("silhouette", r["silhouette"], ps), ("davies_bouldin", r["davies_bouldin"], pd),
                                ("calinski_harabasz", r["calinski_harabasz"], pc)):
                rows.append({"table": "Fig. 11", "row": f"K={r['K']}", "metric": name, "ours": o, "paper": pv})
    t4p = ev / "gen_prior.json"
    if t4p.exists():
        t4 = json.loads(t4p.read_text(encoding="utf-8"))
        names = ("FID1", "FID2", "recall_pct", "precision_pct", "F1_pct")
        pr = t4[t4.get("primary_PR", "PR_raw")]
        ours = (t4["FID1"], t4["FID2"], 100 * pr["recall"], 100 * pr["precision"], 100 * pr["f1"])
        print("\nTable 4, supplementary row: this VAE decoded from z ~ N(0, I), no mixture (the paper's row 1 is a "
              "standard VAE, beta = 1)")
        print(f"  {'':26s} {'FID1':>7s} {'FID2':>7s} {'recall %':>9s} {'precision %':>12s} {'F1 %':>7s}")
        print(f"  {'ours, N(0, I)':26s} {ours[0]:7.2f} {ours[1]:7.2f} {ours[2]:9.2f} {ours[3]:12.2f} {ours[4]:7.2f}")
        if t2p.exists():
            g = (t2["FID1"], t2["FID2"], 100 * t2["PR_raw"]["recall"], 100 * t2["PR_raw"]["precision"],
                 100 * t2["PR_raw"]["f1"])
            print(f"  {'ours, mixture K=' + str(K):26s} {g[0]:7.2f} {g[1]:7.2f} {g[2]:9.2f} {g[3]:12.2f} {g[4]:7.2f}")
        for row, pv in PAPER_T4.items():
            print(f"  {'paper ' + row:26s} {pv[0]:7.2f} {pv[1]:7.2f} {pv[2]:9.2f} {pv[3]:12.2f} {pv[4]:7.2f}")
        for name, o, v in zip(names, ours, PAPER_T4["(1) standard VAE"]):
            rows.append({"table": "4", "row": "ours N(0, I) vs paper (1) standard VAE", "metric": name, "ours": o,
                         "paper": v})
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", default=RUN_ID, help="the run to compare (default: V1's main run)")
    args = ap.parse_args()
    cfg = load_vaegmm_config()
    K = main_k(cfg)
    print(f"run {args.run_id}")
    rows = compare(cfg, args.run_id, K)
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / out_name(args.run_id)
    with open(out, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=["table", "row", "metric", "ours", "paper"])
        wr.writeheader()
        wr.writerows(rows)
    print("wrote", out.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
