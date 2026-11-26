# Technical reference

This is the engineering record behind the [project README](../README.md): how each part is built, where every file lives,
and what was measured along the way. Paper evidence for each stage is in
[`resources/PREPROCESSING_SPECIFICATION.md`](../resources/PREPROCESSING_SPECIFICATION.md); the VAE-GMM training, GMM
fitting and evaluation follow [`resources/TRAINING_SPECIFICATION.md`](../resources/TRAINING_SPECIFICATION.md). Nothing
from either specification is repeated here beyond what is needed to run and extend the code.

**Contents:** [Evidence tags](#evidence-tags) · [Layout](#layout) · [Setup](#setup) · [Commands](#commands) ·
[Dataset layout](#dataset-layout) · [Storage and lineage](#storage-and-lineage) · [S5 contract](#s5-contract) ·
[Synthetic training](#synthetic-training) · [Evaluation categories](#evaluation-categories) ·
[Implementation decisions](#implementation-decisions) · [Dataset record](#dataset-record) ·
[ridgenet-v1 validation record](#ridgenet-v1-validation-record) · [S5 detector experiments](#s5-detector-experiments) ·
[VAE-GMM](#vae-gmm) · [Inference and the web demo](#inference-and-the-web-demo) · [Known limitations](#known-limitations)

---

## Evidence tags

Used in `configs/*.toml`, the code docstrings and the documentation.

| Tag | Meaning |
|---|---|
| `[EXPLICIT]` / `[IMPLIED]` / `[UNSPECIFIED]` | From the specification: what the paper states, implies, or leaves open |
| `[DECISION]` | Implementation decision made here because the paper leaves it open (never paper evidence) |
| `[REPLACEMENT]` | Part of the new S5/S6 design |

The `[paper]` section of `configs/pipeline.toml` is locked: `config.py` refuses to run if any value differs from the
specification. The `[paper]` section of `configs/vaegmm.toml` is locked in the same way by `vaegmm/config.py`.

## Layout

```
encounter_<id>_audio/  RAW, immutable, one folder per encounter (8 folders, 1,415 files). Opened read-only; storage.py
                       refuses any write inside them. Encounter 191 also feeds the synthetic backgrounds (synth_raw_dir).
metadata/  resources/  provided inputs and the specification; manifest_all.csv = SHA-256 of every raw file (build-manifest)
configs/pipeline.toml  paper-defined [paper] + implementation decisions [decisions.*] + storage + validation sets
configs/detector.toml  S5 architecture, synthetic-data generator, training  (all [REPLACEMENT])
configs/vaegmm.toml    VAE-GMM training, GMM fitting and evaluation ([paper] section locked by vaegmm/config.py)
configs/inference.toml inference / web demo settings and the models on offer (not part of any training or processing hash)
src/whistlepipe/       audio.py(S1) dsp.py(S2-S4) detector/(S5) tracking.py(S6) representation.py(S7-S9)
                       pipeline.py(orchestrator) storage.py(lineage/policy) dataset.py(final layout) manifest.py
                       checks.py plotting.py cli.py
                       synth/(synthetic training data)  train.py  evaluate.py  vaegmm/(VAE-GMM)
                       infer.py(inference engine) sonify.py(image -> sound) server.py(web API) webexport.py ratecheck.py
web/                   the project webpage: index.html (scroll film, Encode, Decode, Try it), film/ (the film's data,
                       from export-film, in git); web/media4k/*.mp4 and web/data/ are not in git
whistlecode/           WhistleCode: hiding text in whistles (its own CLI, config, tests, plan and paper results)
deploy/                Docker + Tailscale Funnel deployment of the whole page
colab/                 Colab notebook for the main VAE training + make_colab_bundle.py (its output colab/dist/ is not in git)
post_training/         laptop versions of notebook cells 10-11, finalize_run.py, gmm_check.py, table6_warm.py,
                       compare_paper.py; out/ = their records
mod_detector_5_24/     5-24 kHz detector variant for the DCLDE 2011 benchmark (own configs and outputs)
tests/                 pytest, small synthetic fixtures; none needs the full dataset
models/detector/<ver>/ checkpoint.pt, train_info.json, calibration.json, eval_*.json
models/vaegmm/<run_id>/  VAE runs: train_info.json, train_log.jsonl, sample grids, checkpoints/final.pt (+ last.pt),
                       gmm_K<k>/, eval/, figures/; _gates/ = gate records. gmm.npz and *.npy files are not in git
data/synthetic/        background banks (real S3 audio windows) and cached synthetic val/test sets
preprocessed/          FINAL dataset, one folder per encounter: see "Dataset layout"
preprocessing_checks/<run_id>/   small check runs with full debug detail (never overwritten): see "Storage and lineage"
```

## Setup

* **Python 3.11 or newer** (`tomllib`), then `pip install -r requirements.txt` (and `whistlecode/requirements.txt` for
  WhistleCode). For a CUDA GPU, install `torch` and `torchvision` from the PyTorch index for your CUDA version first.
  Versions in use: Python 3.11.0, numpy 2.4.4, scipy 1.17.1, soundfile 0.13.1 (libsndfile 1.2.2), torch 2.14.0+cu130
  (dataset build, `preprocessed/dataset_info.json`); Python 3.13, torch 2.11 on Colab (V1 `train_info.json`).
* **Raw audio** (not in git, about 190 MB per file): NOAA DCLDE 2022, ship 1705 (R/V Lasker),
  `gs://noaa-passive-bioacoustic/dclde/2022/dclde_2022_1705/audio/`. `metadata/whale_encounters_1705.csv` gives each
  encounter's first and last file prefix; the false killer whale encounters used here are the eight in
  `configs/pipeline.toml` `[paths].raw_dirs`. Put each encounter's files in `encounter_<id>_audio/` in the project root.
  `metadata/manifest_all.csv` already holds the SHA-256 of every file; `build-manifest` creates it for a new collection.
* **Licence:** none has been chosen yet. The paper PDF in `resources/` is CC BY-NC-ND 4.0 (its first page).

## Commands

From the project root.

```bash
python -m pytest                                   # the whistle model's tests
python -m pytest whistlecode/tests                 # the message system's tests (WhistleCode)
python whistle.py list-sets                        # validation sets (val1/val5/val10 from encounter 191, per_encounter) + files per encounter
python whistle.py build-backgrounds                # real-background banks for synthetic training (S1-S3 on 56 non-validation files)
python whistle.py build-ridge-masks                # label-free masks of real faint whistles in the training backgrounds; needed
                                                   #   before training with synth.labels.ignore_background_ridges = true (v2c, v2e)
python whistle.py train --version ridgenet-v1      # train S5 on SYNTHETIC data (checkpoints are never overwritten; --resume continues
                                                   #   after an interruption; full settings of v2c-v2e: models/detector/<ver>/detector_config.json)
python whistle.py eval-synth --split val --calibrate   # synthetic validation + threshold calibration
python whistle.py eval-synth --split test              # synthetic test
python whistle.py compare-synth --versions ridgenet-v1 ridgenet-v2c --split val   # paired comparison (first = baseline)
python whistle.py build-manifest                   # once: hash every raw file -> metadata/manifest_all.csv (never overwritten;
                                                   #   check runs and build-dataset refuse files that are not in it)
python whistle.py run --run-id v2c_check1_1file --set val1 --last s4 --storage debug     # check runs -> preprocessing_checks/
python whistle.py run --run-id v2c_check2_val5 --set val5 --storage debug
python whistle.py run --run-id v2c_check3_per_encounter --set per_encounter --storage debug
python whistle.py validate-run --run-id v2c_check3_per_encounter   # automated gate: lineage, output validity, cross-stage counts
python whistle.py report --run-id v2c_check3_per_encounter         # compact per-file table
python whistle.py plot-waveform                    # S1 waveform of the val1 file, S1/S2 samples overlaid, S1 vs S2 spectra
                                                   #   -> docs/figures/waveform_<stem>.png (--file <stem>, --zoom-s, --zoom-ms)
python whistle.py build-dataset                    # FINAL dataset -> preprocessed/ (only after the checks pass; resumable)
python whistle.py build-dataset --encounters 191 214   # a subset of encounters
python whistle.py validate-dataset                 # automated checks of preprocessed/
```

Any stage range: `--first s5 --last s6 --from-run preprocessing_checks/<earlier run>` (needs that run to hold the previous
stage's intermediate). `--override key=value` changes a config value for one run and is recorded in the run manifest.

The VAE-GMM commands are in [VAE-GMM](#vae-gmm), inference and the web demo in
[Inference and the web demo](#inference-and-the-web-demo), and WhistleCode's in [`whistlecode/PLAN.md`](../whistlecode/PLAN.md)
(`python whistlecode/whistlecode.py --help`).

## Dataset layout

`preprocessed/`, built by `build-dataset`:

```
preprocessed/
  README.txt  dataset_info.json          what every file is; detector, config + hash, software, counts per encounter
  encounter_<id>/images.npy              (N, 128, 128) float32 in [0, 1]: all whistle images of the encounter
  encounter_<id>/images.csv              one row per image (row i <-> images.npy[i]): source file, time, frequencies, contour_id
  encounter_<id>/contours.npz            S7 contours (Hz per 5.333 ms frame); image_index = -1 + no_image_reason too_long/too_wide
  encounter_<id>/files.csv               one row per raw file: OK/FAILED, n_images, first_image_index, n_too_long/n_too_wide,
                                         manifest status, detector_background_split, hash check
  _details/                              not needed for training:
      logs/encounter_<id>_*              run log, per-file stage stats, run manifest, summary, build record
      per_file/encounter_<id>/<stem>.json   lineage of each raw file (same content as meta/<stem>.json below)
      failed/encounter_<id>/<stem>/      traceback + intermediates of a failed file
      detector_output/encounter_<id>/<stem>/   S5 confidence (float16) + S6 tracks ([dataset].keep_detector_output)
```

Each encounter is run through the normal pipeline into a temporary run (`_details/work/`), packed into the four files and
the temporary run is deleted. The folder is written as `encounter_<id>.partial/` and renamed last, so it exists only when
complete; re-running `build-dataset` skips complete encounters and redoes interrupted ones; it stops if a complete
encounter's raw folder gained or lost files since it was built (delete that encounter folder to rebuild it). One dataset =
one processing config (`[paper]` + `[decisions]`, without the S5 device) and one detector checkpoint (anything else is
refused); paths and the list of raw folders are not part of it, so encounters can be added later. Every raw file must be in
`manifest_all.csv` before a build starts.

* **Raw-file status** (`manifest_all.csv`): VALID, SHORT (header shorter than 60 s; processed), SUSPECT_TRUNCATED (far fewer
  bytes than the header length implies, e.g. a cut-off download: a FLAC header keeps the full length), INVALID, UNREADABLE.
  S1 checks the decoded length of every file against its header, so truncated files FAIL with a clear error; failures of
  non-VALID/SHORT files are *expected* (listed by `validate-dataset`, not counted as problems).
* **Detector-background files:** 56 files of encounter 191 provided quiet windows for the detector's synthetic data (24
  train, 16 val, 16 test; `data/synthetic/backgrounds/*.json`). They are processed like every other file and marked in
  `files.csv` `detector_background_split`, so they can be checked or excluded.
* **Code version:** every run manifest, build record and `dataset_info.json` records the git commit and whether `src/`,
  `configs/` or `whistle.py` had uncommitted changes (`git_uncommitted_code_changes`); commit before a final build.

## Storage and lineage

Check runs: `preprocessing_checks/<run_id>/` contains `run_manifest.json` (full config snapshot + hashes, software
versions, detector checkpoint SHA-256, file list, options), `summary.json`, `logs/`, `intermediate/<stem>/`,
`final/<stem>/`, `meta/<stem>.json`, `failed/<stem>/`, `diagnostics/`.

* **Lineage** `meta/<stem>.json`: raw path/size/mtime/**SHA-256 (verified against `metadata/manifest_all.csv`)** → config
  hash → per-stage diagnostics (shapes, rate, duration, range, counts, rejections, timings) → detector name/version/
  checkpoint hash → stored outputs. Each file also records `unchanged_after_processing` (raw immutability audit).
* **Policy** (`[storage]`): `debug` keeps S1–S6 (+S8) intermediates and plots; `normal` keeps S5/S6; `minimal` keeps none.
  S7 vectors, S9 images and lineage are kept in **every** mode. A **failed** file always keeps every intermediate that
  existed, plus the traceback, under `failed/<stem>/`.
* Runs are isolated by `--run-id`; an existing run is never overwritten.

## S5 contract

`detector/interface.py`. Input: S4 log-magnitude spectrogram `(T, 1025)` float32 dB on the 93.75 Hz × 5.333 ms grid.
Output: `DetectionMap.conf` `(T, F)` float32 in [0, 1], one value per S4 node for bins `[bin_lo, bin_hi]` = 2–24 kHz
(`[DECISION]` for the upper edge); semantics = confidence that the node lies on a whistle contour (fundamental or
harmonic). No thresholding in S5. Output is independent of the internal tiling (tested), deterministic, and CPU/GPU-
consistent (tested; TF32 is disabled because it changed S6 tracks between devices). Replace the detector by implementing
`WhistleDetector.predict(spec) -> DetectionMap`; nothing else changes.

**RidgeNet** (`detector/ridgenet.py`, ~14k parameters): fully convolutional, no pooling, dilated 3×3 blocks; receptive
field ±19 frames × ±9 bins. Input conditioning (local per-bin noise-floor subtraction, clip, scale;
`detector/conditioning.py`) is *internal to S5* and shared by training and inference; the S4 output is never modified.

## Synthetic training

No real ground truth is used or fabricated. Real S3 audio windows (3 s) from raw files that belong to **no** validation
set serve as backgrounds, screened by a purely classical label-free ridge score (windows with persistent narrow-band
ridges are dropped). Synthetic whistles (random contours incl. crossings/parallel pairs, 0–5 simultaneous, harmonics,
variable SNR) and synthetic clicks/sweeps are added in the time domain and passed through the *same* S4 function. Labels
(Gaussian ridge targets; nodes of invisible whistle parts are ignored, not forced negative) come only from the known
contours. The generator never imports a detector (tested). Train/val/test use disjoint background files.

**Known limitations:** encounter 191 is whistle-dense, so clean windows are scarce (see
`data/synthetic/backgrounds/*.json`); residual weak real whistles may remain in backgrounds as unlabeled negatives;
synthetic metrics therefore describe the synthetic task only.

## Evaluation categories

Kept separate.

* **A — synthetic** (`eval-synth`): node PR and track-level recall/precision against the generator's ground truth.
* **B — real-data engineering validation** (`validate-run`, `report`, diagnostics figures): consistency, counts,
  rejections, timing, visual inspection. **No real-data precision/recall/F1 is computed or claimed.**
* **C — manually annotated real data**: not available; not implemented.

The paper's counts (228,673 vectors, ≈ 91.98 per file) are **not** optimisation targets.

## Implementation decisions

These are NOT paper evidence; the full list is the `[DECISION]` / `[REPLACEMENT]` tags in `configs/pipeline.toml`.

S1 channel 0 (arbitrary; a six-channel survey showed no anomalous channel) · S2 polyphase Kaiser FIR 48/125 · S3
4th-order Butterworth, zero-phase, after S2 (−6 dB at 2 kHz) · S4 periodic Hamming, dB output, no padding · S5 band 2–24
kHz and all of its internals · S6 entire tracker and its settings · S8 centre frequency = (f_min+f_max)/2, whistle centred
in time, complex 12 kHz baseband derived from the paper grid, 2.7 ms edge ramps, tracks > 128 frames **rejected**
(counted, not cropped) · S9 linear magnitude, per-image max normalisation, row 0 = highest frequency (0 Hz on row 63).

## Dataset record

ridgenet-v2c, 8 encounters: the training data. Built 2026-10-21 by `build-dataset` into `preprocessed/`
(`dataset_info.json`): git commit `8cf3ed4` with no uncommitted code changes, processing config `78f1bb1b…`, detector
`ridgenet-v2c` (`c00d66a0…`), manifest `d20f4b38…`. Before the build, the check runs `v2c_check1_1file` (S1–S4),
`v2c_check2_val5` (5 files, 766 images) and `v2c_check3_per_encounter` (one file per encounter, 1,174 tracks, 1,098
images) finished with every file OK, and `validate-run` passes on both full check runs (0 problems, one detector
checkpoint; re-run 2026-10-31).

| Encounter | Files | Tracks after S6 | Rejected in S8 (> 128 frames) | Images |
|---|---:|---:|---:|---:|
| 191 | 363 | 67,236 | 3,746 | 63,490 |
| 214 | 124 | 6,825 | 148 | 6,677 |
| 276 | 120 | 14,653 | 502 | 14,151 |
| 279 | 145 | 36,171 | 2,654 | 33,517 |
| 280 | 104 | 16,972 | 1,169 | 15,803 |
| 308 | 162 | 23,599 | 1,705 | 21,894 |
| 331 | 331 | 20,903 | 464 | 20,439 |
| 416 | 66 | 4,253 | 70 | 4,183 |
| **Total** | **1,415** | **190,612** | **10,458 (5.5 %)** | **180,154** |

1,415/1,415 files OK, 0 failed. Images per file: mean 127.3, median 95, max 1,003 (2 files have none). S6 rejections: too
short 71,546, harmonic 19,962, low observed fraction 7,375, synchronous comb 329, duplicate 32, too steep 1. Median whistle
= 40 frames (213 ms); 37.3 % of images are shorter than 30 frames. Time: 71.5 min in total, 3.0 s per file (RTX 5060
Laptop GPU). The S6 settings are those frozen in the v1 work below (threshold 0.5, not recalibrated for v2c). The paper's
228,673 vectors from 2,486 files are not a target and not comparable (different S5/S6, different selection of files).

## ridgenet-v1 validation record

Encounter 191 only; superseded. The v1 run folders (`runs/…`) were deleted on 2026-10-21 to make room for the v2c
multi-encounter dataset; the numbers below are the record of that work. The v2c dataset that replaced it is recorded above.

| Run | Files | What happened |
|---|---|---|
| `phase1_1file` | 1 (`1705_20170930_015147_062`) | S1–S4 gate. 12/12 independent checks pass: S1 equals the raw channel bit-for-bit; S2 spectrum preserved (median −0.07 dB); S3 measured gain −6.01 dB at 2 kHz, ≈0 dB above 5 kHz; S4 matches scipy within 0.03 dB. A six-channel survey showed no anomalous channel. |
| `phase2_5files`, `phase3_10files` | 5, 10 | First full S1–S9 passes. Automated gate passed, but **visual inspection found a pulse-train artefact** (17 near-identical short tracks in one burst). → S6 rule `synchronous_comb` added. |
| `…_r2` | 5, 10 | Repeated after the rule. Artefact removed (23 → 6 tracks in that window), gate passed. |
| `…_r3` | 5, 10 | Repeated after an **S5 numerics fix**: CUDA TF32 made confidences differ from CPU by up to 7e-3 and changed S6 tracks between devices; TF32 is now off (difference 5e-6, identical tracks). Gate passed. |
| `phase4_full363` | 363 | First full run; **superseded** (pre-numerics-fix). |
| **`phase4_full363_r2`** | **363** | **Final.** 363/363 OK, 0 failed, one config hash (`19aaca0b…`), one detector checkpoint (`58798cb4…`), all 363 raw SHA-256 equal to the manifest, raw files unchanged. |

Configuration was frozen after the synthetic validation (S6 gate 3 bins, gap 12 frames, threshold 0.5) and not changed
between the real-data phases except for the two documented fixes above, each followed by repeating the affected gates.

**Final run numbers:** 61,326 tracks → **57,990 images** (mean 159.8, median 106 per file; max 926). S6 rejections: too
short 29,848, low observed fraction 4,486, harmonic 7,782, synchronous comb 699, duplicate 10, too steep 3. S8: 3,336
tracks rejected as longer than 128 frames (5.4 %). Median whistle = 36 frames (192 ms); 40.9 % of images are shorter than
30 frames. Time: **3.2 s per file** (19.3 min total): S1 1.31 s (FLAC decode of the 6-channel file) is the largest part, S2
0.36, S3 0.14, S4 0.24, S5 0.19 (GPU; ≈0.65 CPU), S6 0.39, S7–S9 0.07, SHA-256 check 0.13. Disk: 5.8 GB for the run in
`normal` mode. The paper's counts are not targets and are not comparable (different S5/S6, different selection of files).

**Synthetic evaluation (category A; `models/detector/ridgenet-v1/eval_*.json`):** track recall of visible synthetic
fundamentals 0.737 (validation, where S6 gate/gap were chosen) and **0.704 (held-out test)**; by median ridge SNR: ≥10 dB
94–99 %, 5–10 dB 52–55 %, <5 dB ≈ 0 %. 1.02–1.04 tracks per recovered whistle. **0.00 false tracks/min on 4.6 min of
contamination-free negatives** (phase-randomised real backgrounds + synthetic clicks/sweeps). Precision against labels on
real-background samples (0.60–0.62) is only a lower bound because unlabeled real whistles in those backgrounds count as
false.

## S5 detector experiments

Synthetic category A; they led to `ridgenet-v2c`, which the pipeline uses. Goal: better detection with at most **+25 % S5
time** (budget defined by measured latency, not parameter count). Measured on a real 60 s spectrogram: depthwise-separable
designs are *slower* despite fewer multiply-adds (GPU 1.3–1.7×, CPU 4–6×); 18 channels doubles CPU time; so the feasible
family is 16 channels, 6–7 dense blocks. All candidates: same synthetic stream/seed, same frozen S6, **paired**
whistle-by-whistle comparison on fixed sets (`python whistle.py compare-synth ...`, results in
`models/detector/compare_*.json`).

| Version | Change vs v1 | Recall val | 5–10 dB val | Paired vs v1 (val) | S5 time |
|---|---|---|---|---|---|
| v1 | — | 0.737 | 0.554 | — | 1.0× |
| v2a | wider context (7 blocks, ±35 × ±23) | 0.710 | 0.482 | +15 / −32, p = 0.019 (**worse**) | GPU −14 / +5 %, CPU −38 / +17 % (two runs) |
| v2b | data only: SNR emphasis, crossings, time-reversed backgrounds (trained from a separate session; evaluated here) | 0.739 | 0.571 | +14 / −13, p = 1 (no effect) | 1.0× (v1's network) |
| **v2c** | v2b + **background-label fix** | **0.760** | **0.631** | **+30 / −16, p = 0.054** | **1.0× (v1's network)** |
| v2d | v2c + wider context | 0.759 | 0.619 | +23 / −10; vs v2c +16 / −17, p = 1 | GPU +20 %, CPU +60 % (one run) |
| v2e | label fix with v1's SNR balance | 0.755 | 0.625 | +24 / −13; vs v2c +10 / −13, p = 0.68 | 1.0× (v1's network) |

S5 time = change against v1 per 60-s file, as stored in `compare_*.json`. v2b, v2c and v2e are v1's network (14,209
weights) with other training data, yet their stored times range from −34 % to +0 % on the CPU: one comparison run's timing
is noise of that size, so only v2d's slowdown is clearly real.

* **Background-label fix** (`synth.labels.ignore_background_ridges`): a label-free classical statistic (median
  dB-above-floor along 25-frame lines, max over 13 slopes; threshold calibrated on phase-randomised noise) marks probable
  *real* faint whistles in the training backgrounds; those nodes get loss weight 0 instead of being taught as negatives.
  Masks 2.2 % of background nodes, ~70 % of which is real structure (0.65 % noise loss). Isolated effect, v2c vs v2b:
  **+24 / −11, p = 0.041**.
* **Held-out test, v1 vs v2c (run once):** recall **0.704 → 0.729**, 5–10 dB **0.519 → 0.647**, paired **+28 / −14,
  p = 0.044**, 0.00 false tracks/min on contamination-free negatives. Cost: clear whistles (≥ 10 dB) drop 3–4 points; the
  same dip appears in v2b/v2e, so it comes from time reversal and/or the extra crossing scenes (not yet separated), not
  from the label fix or SNR mix.
* **Real data (category B, no ground truth), 10 Phase-3 files:** v2c keeps 82–100 % of v1's tracks and adds 13 % more; the
  extra tracks inspected in a quiet file sit on faint visible ridges. S5 time unchanged (0.23 → 0.21 s); S6 0.62 → 0.66 s
  (more tracks to link).
* **v2c is adopted** (`[decisions.s5].checkpoint`) for the multi-encounter dataset; the S6 threshold 0.5 was kept (not
  recalibrated for v2c). The check runs and the dataset build were re-run with it (see [Dataset record](#dataset-record)).
* **Out of domain:** the 5–24 kHz variant `ridgenet-5-24` ([`mod_detector_5_24/`](../mod_detector_5_24/README.md)) was
  scored on the 9 DCLDE 2011 test files of Li et al. (2023): species-average P 53.6, R 84.9, F1 65.2 (harmonics kept,
  detections ≥ 150 ms, 5–24 kHz; Li et al.'s best over 5–50 kHz: 88.8 / 85.8 / 87.2). The score files are on Drive, not
  yet in the repository ([`mod_detector_5_24/TODO.md`](../mod_detector_5_24/TODO.md)).

## VAE-GMM

Authoritative: [`resources/TRAINING_SPECIFICATION.md`](../resources/TRAINING_SPECIFICATION.md) (discrepancy report,
corrected specification, decisions, deviations, gates); configuration `configs/vaegmm.toml` (its `[paper]` section is
locked in `vaegmm/config.py`). Deviations from stated paper values: the batch size on one GPU (paper 7 × 128 = 896) with
learning rates scaled linearly, lr × B / 896, K = 3,000 instead of 10,000, and the reduced scope below (spec §2.1).

### Main run V1 (`V1_L64_b1e-4_critic_E191`)

* **Scope:** encounter 191 only (363 files, 63,490 images), 150 epochs, **B = 5772, lr 6.442e-3 (VAE) / 1.288e-3
  (critic)**, 11 steps per epoch, TF32 off. It also uses cuDNN autotuning (same maths, not bit-deterministic; spec §3.9).
  Parameters: encoder 589,408, decoder 368,097, critic 184,609.
* **Epochs 1–101** (Colab A100 80 GB, commit `7eb7a1a`, started 2026-11-03): 127.9 s per epoch, rec 171.2 at epoch 101.
  The run stopped there and was first finalised at epoch 101 on 2026-11-08 (`post_training/finalize_run.py`: final.pt =
  byte copy of last.pt, `train_info.json` status `stopped_early`, SHA-256 `fcb1a2e6…`).
* **Epochs 102–150** (Colab A100 80 GB, 2026-11-20): resumed from the epoch-101 checkpoint with micro-batches of 2,886, a
  pre-flight check of the first update (notebook cell 8b) and an epoch rollback guard (cell 9); 130 s per epoch, no
  rollbacks. Epoch 150: rec 161.9, KL 738.2 (epoch 101: 171.2 / 830.6); `final.pt` SHA-256 `1db44d81…`, global step
  1,650, status `complete`. Two earlier resume attempts on a different Colab GPU (2026-11-18, whole batch) diverged from
  the first update and were discarded; the cause is not proven (leading hypothesis: a cuDNN kernel choice for the
  decoder's last output at that batch size, which is above the 32-bit index limit).
* **Both checkpoints are kept**, each in its own folder with its own GMM:

  | Model (page name) | Folder | Checkpoint | GMM K = 3,000 | Used for |
  |---|---|---|---|---|
  | `model1` (Nyx) | `models/vaegmm/V1_L64_b1e-4_critic_E191/` | epoch 101 (`fcb1a2e6…`) | 111 iterations, mean ll 221.71, `gmm.npz` `d8087ed2…`; check passed (FFD 4.63, NN ratio 1.02) | paper evaluation, WhistleCode, Try it (default) |
  | `model2` (Delphi) | `models/vaegmm/V1_L64_b1e-4_critic_E191_epoch150/` | epoch 150 (`1db44d81…`) | 150 iterations, mean ll 211.04, `gmm.npz` `4354547e…`; check passed (FFD 4.47, NN ratio 1.04) | paper evaluation (EXP-025), Try it |

  The paper evaluation (Tables 1, 3, 6; Figs. 7–10, 12) and the WhistleCode campaign are frozen on epoch 101; epoch 150
  was evaluated as well, in its own folder (below). To evaluate epoch 150 further, work in the `_epoch150` folder (`--experiment V1_L64_b1e-4_critic_E191_epoch150`). Refreshing the main
  folder instead would silently turn `model1` into epoch 150, and stale outputs block it: `encode` reuses an existing
  `latents_mu.npy` and `fit_gmm` refuses an existing `gmm_K3000/gmm.npz`.
* **Fallback and earlier runs:** `V1_L64_b1e-4_critic_E191_B896` (never started) uses the paper's batch and learning
  rates. The earlier all-data run `V1_L64_b1e-4_critic` (B = 5376) stopped at epoch 7 and is not used.
* **After training, on the laptop** (`post_training/`, the Colab notebook's cells 10-11 and the GMM check):
  `finalize_run.py` closes a run stopped early; `cell10_progress.py` writes the loss curves to `post_training/out/`;
  `cell11_check_encode.py` checks the data lineage and the last epoch, then encodes `latents_mu.npy`;
  `gmm_check.py [--tag T] [--run-id R]` checks a fit after `fit-gmm` (spec §3.5 diagnostics, pass criteria in its
  docstring) and writes `post_training/out/gmm_check_*.json` + three figures.
* **Laptop gates and the `configs/vaegmm.toml` default:** B = 128, 1.4286e-4 / 2.8571e-5.

### Evaluation record (epoch 101)

Side by side with the paper: `post_training/out/paper_comparison.csv` (`python post_training/compare_paper.py`).

* **Table 1** (L = 64): MSE 8.52, PSNR 32.84 dB, SSIM 0.9898, KL 860.6, against the paper's 0.5778, 44.53 dB, 0.9861,
  43.19; only SSIM is reproduced (likely causes in spec §3.10).
* **Table 3 / Fig. 12:** the Fig. 12 structure is reproduced (every diagonal entry is its row's minimum), but recall,
  precision and F1 are lower than the paper's (F1 75–83 % vs 90–94 %).
* **Figs. 7–10** are made (`figures/`).
* **Table 6:** decoder size matches the paper (368,097 parameters, 557.3 MFLOPs); with the paper's 0.5 s pause the laptop
  GPU wakes from idle on every trial, so a warm supplement is reported too (B = 16: 0.120 ms per image warm vs the paper's
  0.11 ms).
* **GMM:** ridge sensitivity ×10 fitted, ×0.1 not feasible (spec §3.5).
* **Not computed**, by the owner's decision (2026-11-09): Fig. 11 (no GMM fits at other K) and Tables 2, 4 and 5 (FID and
  precision/recall need the Inception-V3 / VGG-16 weights, which are not downloaded).

### Evaluation record (epoch 150, Delphi)

Side by side with the paper: `post_training/out/paper_comparison_V1_L64_b1e-4_critic_E191_epoch150.csv`
(`python post_training/compare_paper.py --run-id V1_L64_b1e-4_critic_E191_epoch150`), EXP-025, 2026-11-27.

* **Table 1** (L = 64): MSE 5.42, PSNR 34.81 dB, SSIM 0.9934, KL 757.7, against the paper's 0.5778, 44.53 dB, 0.9861,
  43.19; only SSIM is reproduced.
* **Table 3 / Fig. 12:** every diagonal entry of Fig. 12 is its row's minimum (13 of 13); recall 84.7–96.9 %, precision
  74.5–79.7 %, F1 79.3–85.8 %, against the paper's 98.2–99.3 %, 82.7–90.8 %, 90.1–94.4 %.
* **Figs. 7–10** are made (`.../E191_epoch150/figures/`).
* **Table 6:** the same decoder (368,097 parameters, 557.3 MFLOPs). Paper protocol: B = 1 1.31 ms (paper 1.7 ms); warm
  GPU (`table6_warm.py --run-id`): B = 16 0.114 ms and B = 32 0.110 ms per image (paper 0.11 and 0.054). The web
  server's container was running during the timing.

### Commands

Every run's actual values are in its `train_info.json` (`spec`, `deviations`, `runtime`).

```bash
python whistle.py vae-experiments                         # experiment matrix V1-V8 (spec §3.8)
python whistle.py vae-gates                               # gates that do not train: G1 data, G2 numerics, G6 features
python whistle.py vae-gates --gate all --allow-training   # + G3 smoke, G4 overfit, G5 timing (short trainings)
python whistle.py train-vae --experiment V1               # main model, 150 epochs on encounter 191 (--resume continues an interrupted run)
# Colab A100: colab/train_V1_colab.ipynb (code bundle: python colab/make_colab_bundle.py)
python whistle.py fit-gmm --experiment V1 --K 3000        # encode unrotated means, full-covariance EM (V1: 111 iterations, 4.3 min on the RTX 5060)
python post_training/gmm_check.py                         # post-fit check of that fit (--tag for the ridge-sensitivity fits)
python whistle.py fit-gmm --experiment V1_L64_b1e-4_critic_E191_epoch150             # model 2's own GMM
python post_training/gmm_check.py --run-id V1_L64_b1e-4_critic_E191_epoch150
python whistle.py vae-eval recon --experiment V1_L64_b1e-4_critic_E191_epoch150   # model 2's Table 1 (also conditional, cost, figures)
python post_training/table6_warm.py --run-id V1_L64_b1e-4_critic_E191_epoch150
python post_training/compare_paper.py --run-id V1_L64_b1e-4_critic_E191_epoch150
python whistle.py vae-eval recon --experiment V1          # Table 1
python whistle.py fetch-eval-weights --approved           # Inception-V3 + VGG-16 weights (only after approval)
python whistle.py vae-eval gen --experiment V1 --K 10000  # Table 2 (FID1, FID2, P/R/F1); --source prior for Table 4 (1)
python whistle.py vae-eval cluster --experiment V1        # Fig. 11 (needs the 7 K fits)
python whistle.py vae-eval components --experiment V1     # 500 samples per component (Fig. 8)
python whistle.py vae-eval conditional --experiment V1    # Table 3 + Fig. 12
python whistle.py vae-eval cost --experiment V1           # Table 6
python whistle.py vae-eval figures --experiment V1        # Figs. 7-10
python whistle.py train-ldm --experiment V1 --T 250 500 1000   # Table 5 LDM baseline
```

Outputs: `models/vaegmm/<run_id>/` (`train_info.json` with full lineage, `train_log.jsonl`, `checkpoints/`,
`latents_mu.npy`, `gmm_K<k>/`, `eval/`, `figures/`); gate records in `models/vaegmm/_gates/`. Runs and GMM fits are never
overwritten.

## Inference and the web demo

A recording goes through S2-S9 exactly as the training data did (`configs/pipeline.toml`; the processing hash is checked
against `preprocessed/dataset_info.json`), then through the trained model, and every image is turned back into sound by
the paper's own Fig. 2 chain (threshold 0.05 -> contour -> constant-amplitude tone) at the whistle's own centre frequency
(`sonify.py`). Settings: `configs/inference.toml`. Uploads: WAV/FLAC/OGG/MP3, any rate >= 32 kHz (below 48 kHz the top of
the 2-24 kHz detector band is missing and the result says so), any number of channels (one is analysed: `--channel` or
the page's Channel box, default 0), up to 120 s.

```bash
python whistle.py model-status              # are the trained files where inference looks for them? (--all: every model on offer)
python whistle.py infer recording.wav       # -> runs/infer/<id>/: result.json, overview.png, per-whistle PNG + WAV
python whistle.py generate --n 8            # new whistles from the GMM; --condition 1..13 = Table 3, --fc 9000 fixes the pitch
python whistle.py serve                     # the page + API on http://127.0.0.1:8000 (Try it is section 08, #try)
python whistlecode/whistlecode.py serve     # the same, plus WhistleCode's Encode and Decode places
python whistle.py export-web                # example excerpts + pre-rendered results -> web/data/ (static hosting)
python whistlecode/whistlecode.py export-film   # the film's data from real records -> web/film/ (in git; web/PLAN.md)
python whistle.py check-rates               # detector on 96 / 48 kHz copies of real files vs the 500 kHz originals
                                            #   (--rates 96000 48000 44100 adds 44.1 kHz)
```

**Models on offer.** `[[models]]` in `configs/inference.toml` lists the models a visitor can choose between in Try it; the
first is the default, and every one is loaded when the server starts. Each entry is `[model]` with the entry's own keys
replaced; `id` is stable (the page and the API use it), `name` is what the page shows. Requests carry `model`, results
name it, and an unknown id gives HTTP 400. Today: `model1` "Nyx" (epoch 101) and `model2` "Delphi" (epoch 150).

The trained files are read from where the training commands write them; nothing else needs to change after training
(`serve` also offers `POST /api/reload-model` when `[server] allow_reload = true`; it is off by default, so restart the
server instead):

| File (per model's run folder) | Written by | Enables |
|---|---|---|
| `checkpoints/last.pt` or `final.pt` (the entry's `checkpoint`) | `train-vae` (every epoch; `final.pt` at the end, or after `post_training/finalize_run.py` for a run stopped early) | recreation (decoder of the encoder mean); a mid-training checkpoint is labelled as such |
| `gmm_K3000/gmm.npz` + `gmm.json` | `fit-gmm` | whistle type (eqs. 11-12), new whistles of that type, generation |
| `gmm_K3000/component_features.npy` | `vae-eval components` | generation under a Table 3 condition (eqs. 9-10 + rejection) |

Until the files exist, the input side (detection, images, the recording and its contour as sound) works and the model
panels say what is missing. With the VAE but no GMM, "new whistles" come from the encoder's own spread (a standard VAE
step, labelled as not the paper's method).

**Checked so far:** on 25 real training images, the tone run back through S2-S4 follows the image's contour to a median
of 0.6 Hz per image (worst image 1.1 Hz; re-measured 2026-10-31 with the round trip of tests/test_sonify.py, which itself
only requires < 23 Hz, a quarter of a row); the detector on 96 / 48 / 44.1 kHz copies of 8 real files (one per encounter,
1,174 tracks) finds 99.8 / 99.4 / 99.7 % of the 500 kHz tracks at 99.7 / 99.5 / 99.1 % precision (2026-10-23,
`python whistle.py check-rates --rates 96000 48000 44100`; record in `runs/infer/_checks/`).

The page itself, WhistleCode's Encode / Decode / Record places and serving two computers are documented in
[`web/README.md`](../web/README.md); self-hosting on the internet in [`deploy/README.md`](../deploy/README.md).

## Known limitations

Observed, not hidden.

* **No real-data accuracy is known.** Only synthetic metrics and engineering validation exist; do not read them as
  recall/precision on real whistles. The S5 detector is a replacement and is **not** claimed equivalent to the paper's.
* Encounter 191, the only source of detector backgrounds, is whistle-dense, so clean background windows are scarce (middle
  of the encounter unusable); synthetic validation therefore covers quiet-to-moderate backgrounds, and dense scenes were
  judged only by inspection (the v1 figures of that inspection were deleted with the run folders on 2026-10-21; the v2c
  check runs keep theirs in `preprocessing_checks/<run_id>/diagnostics/`).
* S5 is nearly blind below about 5 dB local SNR (synthetic test recall 0 % for v1, 5 % for v2c); S6 can fragment or swap
  identities in very dense crossings.
* The comb rule can discard a real whistle that starts at the same instant as a pulse-train lattice (observed once in 15
  files).
* `min_track_frames = 12` admits many short fragments (37 % of the dataset's images < 30 frames) and tracks > 128 frames
  are rejected. Both are replacement decisions; `images.csv` carries `n_frames`, so a dataset-level filter can be applied
  later **without** re-running preprocessing — but that is a deliberate downstream decision, not something tuned to the
  paper.
* Single channel (index 0, arbitrary); channel fusion is not implemented.
* The VAE is trained on one encounter with about 46× fewer optimiser updates than the paper (1,650 vs ≈ 76,800); Table 1
  reproduces only SSIM, and Table 3 trails the paper in value while matching its structure.
* WhistleCode uses epoch 101. The paper evaluation was run on both checkpoints (epoch 150 on 2026-11-27); epoch 150
  has not been used for messages.
* WhistleCode is tested in simulation only: drift correction (WC-R2) is measured on encounter-214 development noise only, shape covertness fails (discriminator AUC 0.944),
  and no message has been played through a speaker and recorded ([`whistlecode/paper/RESULTS.md`](../whistlecode/paper/RESULTS.md)).
