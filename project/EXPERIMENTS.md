# Experiment register

Every training run, fit, gate, benchmark and test campaign: the question it answers, how it was run, where its record is, and what it showed. Index of all systems: [README.md](README.md).

**Rules**

- **A row is added before the run starts**, with status *running*, the seed and the output folder. It gets its result when the run ends, including when it fails.
- **Output folders are never reused.** A rerun gets a new folder and a new row.
- **The record is the evidence.** The "Record" column points at the files that hold the numbers; reported numbers are traced in [TRACEABILITY.md](TRACEABILITY.md#results).
- **Commit** is the commit that recorded the result (the run's own `train_info.json` or frozen record names the code commit it ran on).

## Whistle model

| ID | Date | Question | How | Record | Verdict | Commit |
|---|---|---|---|---|---|---|
| EXP-001 | 2026-10-08 to 10-21 | Which replacement detector design finds whistles best on synthetic data? | `python whistle.py train`, `eval-synth`, `compare-synth`; versions v1, v2a-v2e | `models/detector/compare_*.json`, `models/detector/<version>/` | **v2c adopted** ([D-002](DECISIONS.md#d-002)); v2b once ran out of memory (`_failed/`) | `8cf3ed4` |
| EXP-002 | 2026-10-21 | Build the whistle image dataset from all eight encounters | `python whistle.py build-dataset`, detector v2c | `preprocessed/dataset_info.json` (config hash `78f1bb1b`) | 1,415 / 1,415 files, 0 failed, 180,154 images | `8cf3ed4`, `2cf1fc1` |
| EXP-003 | 2026-10-22 to 11-03 | Are data, numerics, resume, overfitting, timing and features sound before training? | `python whistle.py vae-gates` (G1-G6) | `models/vaegmm/_gates/` | G1, G2, G3, G5, G6 passed; **G4 not met** (0.416 against ≤ 0.3), accepted by the owner (`G4_owner_acceptance_*.json`) | `f6827ce`, `5925df3` |
| EXP-004 | 2026-10-29 | Train V1 on all encounters | `train-vae`, Colab A100 | `models/vaegmm/V1_L64_b1e-4_critic/` | stopped at epoch 7 when the scope was cut ([D-005](DECISIONS.md#d-005)) | — |
| EXP-005 | 2026-11-03 to 11-08 | Train V1 on encounter 191 | `train-vae`, Colab A100, batch 5,772 | `models/vaegmm/V1_L64_b1e-4_critic_E191/train_info.json`, `train_log.jsonl` | epoch 101 reached; finalised as **Nyx** (`fcb1a2e6`) | `9ac87a0`, `c4ac1b3` |
| EXP-006 | 2026-11-08 | Fit the GMM (K = 3,000) on Nyx's latents | `fit-gmm`, seed 20261022 | `.../gmm_K3000/gmm.json`, `post_training/out/gmm_check_K3000.json` | converged in 111 iterations; post-fit check passed | `7350157` |
| EXP-007 | 2026-11-08 | How sensitive is the fit to the ridge? | `fit-gmm --reg-rel` × 10 and × 0.1 | `.../gmm_K3000_reg10x/`, `.../gmm_K3000_reg0.1x/FAILED.json` | × 10 converged (121 iterations, reported only); × 0.1 failed | `7350157` |
| EXP-008 | 2026-11-08 to 11-09 | How close is the reproduction to the paper (epoch 101)? | `vae-eval`; `post_training/compare_paper.py`, `table6_warm.py` | `.../E191/eval/`, `.../E191/figures/`, `post_training/out/paper_comparison.csv` | SSIM 0.990 (paper 0.986); other Table 1 and Table 3 values below the paper; Fig. 12 structure reproduced; decoder size and cost identical | `3e32da5`, `119fb82`, `e0e0122` |
| EXP-009 | 2026-11-18 | Resume V1 from epoch 101 on another Colab GPU | Colab notebook, resume | none kept | **diverged twice; discarded** ([INC-001](INCIDENTS.md#inc-001)) | — |
| EXP-010 | 2026-11-20 | Resume V1 to epoch 150 on a Colab A100 | notebook with pre-flight check and rollback guard | `models/vaegmm/V1_L64_b1e-4_critic_E191_epoch150/` | completed at epoch 150; **Delphi** (`1db44d81`) | `65ab4c9` |
| EXP-011 | 2026-11-20 | Fit the GMM on Delphi's latents | `fit-gmm --experiment V1_L64_b1e-4_critic_E191_epoch150` | `.../E191_epoch150/gmm_K3000/`, `post_training/out/gmm_check_V1_..._epoch150_K3000.json` | converged in 150 iterations; check passed | `cd0797d` |
| EXP-025 | 2026-11-27 | How close is Delphi (epoch 150) to the paper? (REP-1) | `vae-eval recon`, `conditional`, `figures`, `cost` with `--experiment V1_L64_b1e-4_critic_E191_epoch150`; `post_training/table6_warm.py --run-id`, `compare_paper.py --run-id`; Table 3 seed 20261025, figures 7, cost 0; RTX 5060; code `51daac1` (the two scripts' new `--run-id` uncommitted) | `.../E191_epoch150/eval/`, `.../E191_epoch150/figures/`, `post_training/out/paper_comparison_V1_L64_b1e-4_critic_E191_epoch150.csv`, `table6_warm_V1_L64_b1e-4_critic_E191_epoch150.json` | Table 1: MSE 5.42, PSNR 34.81 dB, SSIM 0.9934 (paper 0.9861), KL 757.7: only SSIM reproduced; Table 3: recall 84.7-96.9 %, precision 74.5-79.7 %, F1 79.3-85.8 % (paper 90.1-94.4 %); Fig. 12 diagonal the row minimum in 13 of 13 rows; decoder size identical, warm B = 16 0.114 ms per image (paper 0.11) | `8b220b7` |
| EXP-026 | 2026-11-27 | Fig. 11 for Delphi (epoch 150) at K = 3,000: silhouette, Davies-Bouldin, Calinski-Harabasz ([D-029](DECISIONS.md#d-029)) | `vae-eval cluster --experiment V1_L64_b1e-4_critic_E191_epoch150 --K 3000` on the existing `gmm_K3000` (14 s); RTX 5060; code `8b220b7`. Fits at K = 1,000 to 15,000 were started first and stopped at the owner's request (K = 1,000 had finished, K = 5,000 had just begun); both folders were moved out of the repository and are not used | `.../E191_epoch150/eval/fig11_clustering.json`, `post_training/out/paper_comparison_V1_L64_b1e-4_critic_E191_epoch150.csv` | silhouette 0.091 (paper 0.401), Davies-Bouldin 1.478 (paper 0.767): the latent clusters are much less separated than the paper's; Calinski-Harabasz 398.8 (paper 21.2) is not comparable in size (it grows with the number of images, and the paper's scale is unstated) | `580ce3f` |
| EXP-027 | 2026-11-27 | Table 2 for Delphi (epoch 150) at K = 3,000: FID₁, FID₂, precision, recall, F1 ([D-030](DECISIONS.md#d-030)) | `vae-eval gen --experiment V1_L64_b1e-4_critic_E191_epoch150 --K 3000`; 63,490 generated against 63,490 real images, generation seed 20261023; RTX 5060; code `8b220b7` + the fixes of this run | `.../E191_epoch150/eval/gen_gmm_K3000.json` (25 min; feature batch 64) | FID₁ 29.48 (paper 2.64-4.37 at K = 1k-15k), FID₂ 49.03 (paper 68.45-72.81); precision / recall / F1 10.0 / 3.2 / 4.8 % on raw images (the primary input) and 64.5 / 52.6 / 57.9 % thresholded at 0.1, against the paper's ≈ 90 / 87 / 89 %. Check of the metric: two halves of the real images score 87.0 / 86.7 % (raw) and 87.8 / 88.1 % (thresholded) against each other, so the gap is in the generated images. They are softer than the real ones (peak 0.91 against 1.00, no exact-zero background against 64 % of real pixels); not tested as the cause | — |
| EXP-012 | 2026-10-28 to 10-31 | Does a 5-24 kHz detector work on another public benchmark? | `mod_detector_5_24/` (Colab training; `dclde2011.py`) | `mod_detector_5_24/models/detector/ridgenet-5-24/`; scores on Google Drive (DET-2) | trained; DCLDE 2011 comparison with Silbido reported in the detector draft | `29b444e`, `f388805` |

## WhistleCode

| ID | Date | Question | How | Record | Verdict | Commit |
|---|---|---|---|---|---|---|
| EXP-013 | 2026-11-18 | Choose the 16 symbol shapes and the signature whistle | `build-codebook` | `whistlecode/outputs/codebook/` (`cd322a02`) | built and verified | `6b1a594` |
| EXP-014 | 2026-11-18 | Gate F1: does message format v2 survive the detector? | `experiments/f1_gate.py`, `f1b_diagnose.py` | `outputs/f1_gate/`, `outputs/f1_gate_own_length/`, `outputs/f1b_diagnose/` | **failed**; the format was finalised anyway, with the diagnosis | `ab33238`, `b511c7f` |
| EXP-015 | 2026-11-18 to 11-19 | Does the whole pipeline deliver text through real noise? | `experiments/e2e_run.py` | `outputs/e2e_*` | normal conditions proved: 90 / 90 messages in encounter-214 noise, 87 / 90 in 276 | `876a5b9` |
| EXP-016 | 2026-11-19 | Can a trained detector tell our whistles from real ones? | `experiments/realism_score.py` | `outputs/realism_score_*` | VAE shapes kept as the voice ([D-011](DECISIONS.md#d-011)) | `80a122e` |
| EXP-017 | 2026-11-19 | How does it cope with echoes and Doppler? | `experiments/sea_run.py` | `outputs/sea_run/`, `outputs/sea_run_read/` | echoes and Doppler cost most messages (no drift correction yet) | `b07e67a` |
| EXP-018 | 2026-11-19 to 11-20 | **Campaign v1**: the frozen test against the pass marks of PLAN.md 8.6 | `paper_eval.py`, `paper_covert.py`, `paper_analysis.py`; seed 20261120; frozen git `ea18d032` | `outputs/paper/`; [`whistlecode/paper/RESULTS.md`](../whistlecode/paper/RESULTS.md), `paper/tables/`, `paper/figures/` | E1 PASS, final run 84.5 % FAIL, false messages 0 PASS, shape AUC 0.944 FAIL, rhythm 0.440 PASS / 0.684 FAIL | `416936c` |
| EXP-019 | 2026-11-21 | How does narrowband SNR relate to in-band SNR? | `experiments/snr_inband.py`, 12 files per encounter | `outputs/snr_inband/` | gap 22.3 dB (214) and 25.3 dB (276), medians | `87a6e42` |
| EXP-020 | 2026-11-21 | WC-R2: does Doppler and clock-drift correction work? (encounter 214 only) | `experiments/drift_dev.py` | `outputs/drift_dev/`, `drift_dev_*.log` | Doppler ±3 m/s: 49-50 / 50 at every speed; random sea 18 / 42 / 39 of 50; **adopted** ([D-012](DECISIONS.md#d-012)) | `4ab82e1` |

## Planned

| ID | Task | Question | Data | Notes |
|---|---|---|---|---|
| EXP-021 | WC-R3 | What gives the whistle shapes away, and do the epoch-150 voice, tau or codebook choice fix it? | encounter 214 only | adoption rule: AUC down by ≥ 0.03, ≤ 2 of 50 messages lost at 10 dB |
| EXP-022 | WC-R4 | Matched-filter modem, listening test, whistle-against-noise classifier, species likelihood | 214 (develop), 276 (campaign) | listening test needs YOU-5 |
| EXP-023 | WC-R5 | In-air test between two laptops | room recording | pass: ≥ 18 / 20 exact, no wrong text |
| EXP-024 | WC-R6 | **Campaign v2**, once, overnight | 276 (and 308 if YOU-4) | seed 20261205; pass marks v2 frozen in PLAN.md 8.7 |

Outputs under `whistlecode/outputs/` are not in git (5.9 GB). What matters for the paper is copied into `whistlecode/paper/`.

## New entry template

```
| EXP-0NN | YYYY-MM-DD | <the question, one line> | <command or script, seed, machine> | <output folder (new)> | running | — |
```
