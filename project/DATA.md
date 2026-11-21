# Data catalogue

Every dataset the project uses: where it comes from, where it lives, its size, its role, and how it is verified. Where each copy is kept and how to restore it: [STORAGE.md](STORAGE.md). Index of all systems: [README.md](README.md).

## Raw recordings: NOAA DCLDE 2022, ship 1705 (HICEAS 2017)

**Source:** `gs://noaa-passive-bioacoustic/dclde/2022/dclde_2022_1705/audio/` (public). 60 s FLAC files, 500 kHz, 6 channels, about 190 MB each. Only channel 0 is used ([D-003](DECISIONS.md#d-003)). Licence and credit: [LICENSING.md](LICENSING.md).

**Verification:** [`metadata/manifest_all.csv`](../metadata/manifest_all.csv) holds the SHA-256, size, rate, channels and duration of all 1,415 files. The pipeline checks each file against it before processing and refuses files that are not in it; the raw folders are opened read-only. `python tools/repo.py checksums verify --raw` re-checks the files present (long). Encounter first and last files: [`metadata/whale_encounters_1705.csv`](../metadata/whale_encounters_1705.csv).

| Encounter | Files | Images | Raw audio on the laptop | Role |
|---|---|---|---|---|
| **191** | 363 | 63,490 | `encounter_191_audio/` (65 GB) | **VAE training** (the only training encounter, [D-005](DECISIONS.md#d-005)); WhistleCode rhythm bank and pitch pool |
| **214** | 124 | 6,677 | `encounter_214_audio/` (23 GB) | **WhistleCode development** noise and whistles (tuning, R2-R4) |
| **276** | 120 | 14,151 | `encounter_276_audio/` (22 GB) | **WhistleCode test** noise and whistles. Nothing is tuned on it ([D-009](DECISIONS.md#d-009)) |
| 279 | 145 | 33,517 | deleted after processing | dataset only |
| 280 | 104 | 15,803 | deleted after processing | dataset only |
| 308 | 162 | 21,894 | deleted after processing | dataset only; optional fresh WhistleCode test (needs 33 files, about 6 GB: YOU-4) |
| 331 | 331 | 20,439 | deleted after processing | dataset only |
| 416 | 66 | 4,183 | deleted after processing | dataset only |
| **Total** | **1,415** | **180,154** | 110 GB | |

`metadata/manifest_363.csv` is the original encounter-191 manifest (absolute paths from the first machine); `manifest_all.csv` supersedes it and marks which rows match it.

## Derived data

| Dataset | Where | Size | In git | Made by | Verified by |
|---|---|---|---|---|---|
| **Whistle image dataset** (128 × 128 contours, 8 encounters) | `preprocessed/` | 19 GB | no | `python whistle.py build-dataset` (S1-S9, detector ridgenet-v2c) | `dataset_info.json` (counts, detector hash `c00d66a0`, processing config hash `78f1bb1b`); per-encounter `images.csv` in [`checksums/models.sha256`](checksums/models.sha256) |
| Preprocessing check outputs | `preprocessing_checks/` | 127 MB | no | `python whistle.py run` / `validate-run` | regenerable |
| **Synthetic detector data** (whistle-free backgrounds with injected shapes; validation and test sets) | `data/synthetic/` | 691 MB | no | `python whistle.py build-backgrounds`, `build-ridge-masks` | `backgrounds/test.json`, build log |
| Detector benchmark (DCLDE 2011, 12 recordings; 145.5 min whistle-free) | Google Drive, `mod_detector_5_24/` scripts | — | scores not yet (DET-2) | `mod_detector_5_24/dclde2011.py` | — |
| WhistleCode noise cache, campaigns, job folders | `whistlecode/outputs/` | 5.9 GB | no | WhistleCode commands and experiments | campaign records (`paper/RESULTS.md` header hashes) |

## Rules

- **Raw audio is never written to.** New files enter only through the manifest.
- **Data splits are fixed** ([D-009](DECISIONS.md#d-009)): 191 trains the model, 214 develops WhistleCode, 276 tests it. Campaign v2 uses seed 20261205, which no development run may use.
- **No dataset is overwritten.** A rebuilt dataset gets a new config hash and is recorded here.
- **Personal data:** none. The recordings hold no people. The listening test (WC-R4) stores no personal data.
