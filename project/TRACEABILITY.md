# Traceability: requirements and results

Two directions of one chain: **requirement → test or experiment → record → status**, and **reported number → record → the run that made it**. Index of all systems: [README.md](README.md).

**Rules:** a new claim, pass mark or reported number gets a row here in the same change. A status is never improved without a new record. A failed mark stays failed ([D-010](DECISIONS.md#d-010)).

## Requirements

### Whistle model (Park et al.'s method)

Sources: [`resources/PREPROCESSING_SPECIFICATION.md`](../resources/PREPROCESSING_SPECIFICATION.md), [`resources/TRAINING_SPECIFICATION.md`](../resources/TRAINING_SPECIFICATION.md).

| ID | Requirement | Verified by | Status |
|---|---|---|---|
| R-01 | Preprocessing S1-S9 uses the paper's values, and refuses to run if a `[paper]` value changes | `tests/test_s1_s4.py`, `tests/test_s6_s9.py`, `tests/test_pipeline.py`; the locked `[paper]` sections | Met |
| R-02 | Every raw file matches its SHA-256 before processing; raw folders are read-only | `tests/test_dataset.py`; `metadata/manifest_all.csv`; EXP-002 (0 failed files) | Met |
| R-03 | The replacement detector meets the functional requirements of spec §11 | `tests/test_s5_detector.py`; EXP-001 | Met on synthetic data; real-data accuracy unknown (DET-3) |
| R-04 | The VAE matches the paper's architecture: decoder 368,097 parameters, 557.3 MFLOPs | `tests/test_vaegmm_model.py`; `train_info.json` (`n_params`, `decoder_table6_flops`) | Met |
| R-05 | Training resumes bit-identically at an epoch boundary | `tests/test_vaegmm_model.py::test_resume_at_epoch_boundary_is_bit_identical`; gate G3 | Met |
| R-06 | The GMM's EM matches scikit-learn from the same start, and GPU matches CPU | `tests/test_vaegmm_gmm_eval.py` | Met |
| R-07 | Every run, dataset and fit records its configuration hash, inputs' hashes, software and commit, and none is overwritten | `train_info.json`, `dataset_info.json`, `gmm.json` fields; `src/whistlepipe/storage.py` | Met |
| R-08 | Paper evaluation: Tables 1, 3, 6 and Figs. 7-10, 12 | EXP-008 | Met for Nyx (epoch 101); Delphi not evaluated (REP-1) |
| R-09 | Fig. 11 and Tables 2, 4, 5 | — | Not done, by decision ([D-006](DECISIONS.md#d-006)) |

### WhistleCode claims

Source: [`whistlecode/THREAT_MODEL.md`](../whistlecode/THREAT_MODEL.md) section 6 (state of 2026-11-21, campaign v1, Nyx, simulation with real ocean recordings).

| ID | Claim | Evidence | Status |
|---|---|---|---|
| C1 | Exact delivery on a clean channel | 200 / 200 (`t1_clean_final.csv`) | Supported |
| C2 | Exact delivery in real sea noise at moderate SNR | `t2_snr_sweep.csv` | Supported (simulated channel) |
| C3 | ≥ 95 % exact at 10 dB in held-out sea noise | 84.5 % (`t1_clean_final.csv`, `t1b_final_by_size.csv`) | Not supported |
| C4 | Never accepts a false message | 0 in 7,900 tries (`t5_false_messages.csv`) | Supported (simulated channel) |
| C5 | The timing passes as real whistling, stream on its own | rhythm AUC 0.440 (`t7b_covert_rhythm.csv`) | Supported |
| C6 | The timing passes as real whistling inside sea noise | rhythm AUC 0.684 (`t7b_covert_rhythm.csv`) | Not supported |
| C7 | The whistle shapes pass as real | shape AUC 0.944 (`t7a_covert_shapes.csv`) | Not supported; WC-R3 works on it |
| C8 | It survives the sea channel (echoes and Doppler) | `t3a_range.csv`, `t3b_doppler.csv`, `t3c_random_sea.csv` | Not supported in v1. R2 drift correction fixes Doppler on encounter 214 (EXP-020); to be tested in campaign v2 |
| C9 | More noise-robust than an artificial chirp alphabet | `t2_snr_sweep.csv` (baseline rows) | Supported, with a caveat (WC-R4 adds the fair modem) |
| C10 | Works over a physical acoustic link | — | Not tested (WC-R5) |
| C11 | Passes human listeners | — | Not tested (WC-R4, needs YOU-5) |
| C12 | Throughput | 1.08-1.38 bit/s median (`t6_throughput.csv`) | Measured |
| C13 | Message confidentiality | — | Not claimed |
| C14 | New: no published messaging system read so far draws its symbols from the components of a density model of whistles, each whistle a fresh sample (README, "What is new") | `whistlecode/RELATED_WORK.md` sections 4, 5 and 7 | Draft; the literature search is incomplete (WC-R1a) |

*Where the page states these (added 2026-11-26, WEB-5):* the footer of `web/index.html` says the system was "tested in simulation only: no message has been played into water yet" (C10, not tested) and that "a trained classifier can still tell the coded whistle shapes from real ones" (C7, not supported; shape AUC 0.944). The film's demonstration decode is one run, not a rate. Its record is `web/film/film.json` (`hear`; the seed rule and skipped seeds are in `provenance`).

*The film's words (added 2026-11-26, WEB-5 P3; wording revised in P4 the same day)*, each with what holds it:

| Words in `web/index.html` | Record |
|---|---|
| "63,490" whistles, "every whistle of one false killer whale encounter" (02 · Learn) | `latents_mu.json` `n`; `film.json` `learn.n`; encounter 191 only (D-005, `configs/vaegmm.toml` `[deviations]`) |
| "3,000 families" (02, 03) | `gmm.json` `n_components` (K = 3,000, D-005); `film.json` `learn.n_components` |
| "keeps 16 … at one of four pitches: 64 whistles, six bits each" (03 · Speak) | `whistlecode/outputs/codebook/codebook.json` (16 types and verification); `whistlecode/PLAN.md` section 4.6 (the four candidate pitches per slot, two bits; 16 shapes, four bits); `film.json` `speak.pitches_hz` |
| "About a third of the whistles you hear carry the message" (04 · Hide; whistles only, clicks not counted) | `whistlecode/paper/RESULTS.md` section 6 (median 66 of 198; 33-36 % across payload sets; reconciled 2026-11-26, WC-R7); this send: 31 of 82, `film.json` `hide.data_share` |
| "recorded off Hawai‘i in 2017" (01 · Listen) | `film.json` `listen.source_file` `1705_20170929_…` (HICEAS 2017, `web/CREDITS.md`) |
| "Without it, there is no message" (05 · Hear) | C4: no wrong-key message accepted, 0 in 3,700 (`t5_false_messages.csv`) |
| "Spare whistles repair what the sea broke" (05 · Hear) | C2 and Reed–Solomon (`whistlecode/PLAN.md` section 4.2); in this send 1 wrong whistle repaired, `film.json` `hear.repair` |

### WhistleCode pass marks v2

Source: [`whistlecode/PLAN.md`](../whistlecode/PLAN.md) section 8.7, frozen 2026-11-21. All are measured once, by campaign v2 (EXP-024).

| Mark | Test | Pass | Status |
|---|---|---|---|
| E1 | Clean channel, full set | 100 % exact | not yet run |
| Final | Encounter 276, 10 dB, full set | ≥ 95 % exact | not yet run |
| False | Wrong text, wrong-key messages, messages in noise | 0 | not yet run |
| E7 | Shape AUC against encounter-276 whistles | ≤ 0.75 | not yet run |
| E9 | Rhythm AUC, alone and in 10 dB noise | ≤ 0.60 for both | not yet run |
| D | Doppler -2 to +2 m/s, 15 dB | ≥ 90 % at each of six speeds | not yet run |
| S | Random sea, 20 dB | ≥ 80 % exact | not yet run |
| A | In-air test | ≥ 18 / 20 exact, no wrong text | not yet run |
| L | Listening test | 95 % Wilson interval includes 50 % | not yet run |
| F308 | Encounter 308, 10 dB (only if downloaded) | ≥ 95 % exact | not yet run |

## Results

Every number the README, the review slides or a paper reports, and the record that holds it. Records in **bold** are in git; the others exist only on the project laptop (see the note below).

### Whistle model

| Number | Record | Made by |
|---|---|---|
| 1,415 files, 0 failed, 180,154 images, 8 encounters | `preprocessed/dataset_info.json` | EXP-002 |
| SSIM 0.990 (paper 0.986); MSE, PSNR, KL of Table 1 | **`models/vaegmm/V1_L64_b1e-4_critic_E191/eval/table1_recon.json`**, **`post_training/out/paper_comparison.csv`** | EXP-008 |
| Table 3 rows; Fig. 12 diagonal for 13 conditions | **`.../E191/eval/table3_fig12_K3000.json`**, **`.../E191/figures/fig12_lnFFD.png`** | EXP-008 |
| Figs. 7-10 | **`.../E191/figures/`** | EXP-008 |
| Table 6: decoder 368,097 parameters, 557.3 MFLOPs, timing | **`.../E191/eval/table6_cost.json`**, **`post_training/out/table6_warm.json`** | EXP-008 |
| GMM: 111 iterations, converged; post-fit check | **`.../E191/gmm_K3000/gmm.json`**, **`post_training/out/gmm_check_K3000.json`** | EXP-006 |
| Delphi GMM: 150 iterations; check | **`.../E191_epoch150/gmm_K3000/gmm.json`**, **`post_training/out/gmm_check_V1_L64_b1e-4_critic_E191_epoch150_K3000.json`** | EXP-011 |
| Detector v2c: 14,209 weights; node precision 0.675, recall 0.715, F1 0.695 | **`models/detector/ridgenet-v2c/train_info.json`**, `preprocessed/dataset_info.json` | EXP-001 |
| Learning curves, epochs 1-150 | **`.../E191/train_log.jsonl`**, **`.../E191_epoch150/train_log.jsonl`** | EXP-005, EXP-010 |
| Detector 5-24 kHz on DCLDE 2011 (Li et al. 2023 test files): species-average P 53.6, R 84.9, F1 65.2 | `mod_detector_5_24/TODO.md` (summary); the score files are on Google Drive until DET-2 copies them into `mod_detector_5_24/results/` | the DCLDE 2011 benchmark (`mod_detector_5_24/dclde2011.py score`) |
| Li et al. 2023 best system on the same files: P 88.8, R 85.8, F1 87.2 (5-50 kHz, context only) | the published paper (J. Acoust. Soc. Am., doi:10.1121/10.0020274), as recorded in `mod_detector_5_24/TODO.md` | not ours |
| Raw audio: about 190 MB per file; 68 GB for encounter 191, about 23 GB each for 214 and 276, about 270 GB for all eight | `du -sb encounter_<id>_audio` on the project laptop, 2026-11-23 (all eight: 1,415 files × 190 MB) | measured |

### WhistleCode

All campaign-v1 numbers come from one frozen run (git `ea18d032`, config `5576d79bcaa1`, codebook `cd322a0267ea`, seed 20261120). Report: **[`whistlecode/paper/RESULTS.md`](../whistlecode/paper/RESULTS.md)**.

| Number | Record | Made by |
|---|---|---|
| Verdicts against the pass marks | **`whistlecode/paper/tables/t0_verdicts.csv`** | EXP-018 |
| E1 100 %; final run 84.5 % (97 % under 60 data whistles) | **`t1_clean_final.csv`**, **`t1b_final_by_size.csv`** | EXP-018 |
| Success against SNR (and the chirp baseline) | **`t2_snr_sweep.csv`**, **`figures/fig_success_vs_snr.png`** | EXP-018 |
| Sea: range, Doppler, random sea | **`t3a_range.csv`**, **`t3b_doppler.csv`**, **`t3c_random_sea.csv`**, **`figures/fig_sea.png`** | EXP-018 |
| Latent variation tau | **`t4_tau.csv`** | EXP-018 |
| 0 false messages in 7,900 tries | **`t5_false_messages.csv`** | EXP-018 |
| Throughput 1.08-1.38 bit/s; computing cost | **`t6_throughput.csv`** | EXP-018 |
| Shape AUC 0.944; rhythm AUC 0.440 / 0.684 | **`t7a_covert_shapes.csv`**, **`t7b_covert_rhythm.csv`**, **`figures/fig_covert_shapes.png`** | EXP-018 |
| Receiver ablations | **`t8_ablations.csv`** | EXP-018 |
| Normal conditions: 90 / 90 (214), 87 / 90 (276) | `whistlecode/outputs/e2e_*`; summary in **`whistlecode/PLAN.md`** ("Normal conditions proved") | EXP-015 |
| SNR gap 22.3 dB (214), 25.3 dB (276) | `whistlecode/outputs/snr_inband/results.json`; summary in **`PLAN.md`** 8.7 | EXP-019 |
| R2: Doppler 49-50 / 50; random sea 18 / 42 / 39 of 50; adoption 10 / 50 / 49 / 50 | `whistlecode/outputs/drift_dev/`; summary in **`PLAN.md`** ("Drift correction") | EXP-020 |

**Gap:** the records of EXP-015, EXP-019 and EXP-020 are only on the project laptop (`whistlecode/outputs/` is not in git). OPS-5 copies their summaries (a few kB of JSON) into `whistlecode/paper/records/`, so every reported number has a record in git.
