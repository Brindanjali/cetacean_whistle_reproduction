# Model registry

Every trained model and derived model file: what it is, where it came from, its status, and its SHA-256. The full hashes are in [`checksums/models.sha256`](checksums/models.sha256); `python tools/repo.py checksums verify` checks the files on disk against them. Index of all systems: [README.md](README.md).

**Statuses:** *live* (used by the page or the current results), *final* (the version results are reported on), *kept* (superseded, kept for lineage), *failed* (recorded, never used).

**Rules:** a model file is never overwritten or moved: a new model gets a new folder. A new or changed file updates this page and the manifest (`checksums make`), and is logged.

## VAE (run V1, encounter 191)

| Name | File | Epoch | SHA-256 | In git | Status |
|---|---|---|---|---|---|
| **Nyx** | `models/vaegmm/V1_L64_b1e-4_critic_E191/checkpoints/final.pt` | 101 | `fcb1a2e69324` | yes | **final, live** (paper results, WhistleCode, Try it model 1) |
| Nyx (copy) | `.../V1_L64_b1e-4_critic_E191/checkpoints/last.pt` | 101 | `fcb1a2e69324` | yes | kept (identical to `final.pt`) |
| **Delphi** | `models/vaegmm/V1_L64_b1e-4_critic_E191_epoch150/checkpoints/final.pt` | 150 | `1db44d81e03c` | yes | **live** (Try it model 2); no paper evaluation yet (REP-1) |
| all-data run | `models/vaegmm/V1_L64_b1e-4_critic/` | 7 | — | records only | kept: stopped at epoch 7 when the scope was cut to encounter 191 |

Lineage: each folder's `train_info.json` records the configuration and its hash, the dataset hash, software versions, device and git commit; `train_log.jsonl` holds every epoch. Training: Colab A100, batch 5,772, learning rates scaled linearly ([D-004](DECISIONS.md#d-004)). Nyx is the epoch-101 checkpoint of the run that later resumed to 150 ([D-007](DECISIONS.md#d-007)).

## Gaussian mixtures (K = 3,000)

| File | Fitted on | Iterations | SHA-256 | In git | Status |
|---|---|---|---|---|---|
| `V1_L64_b1e-4_critic_E191/gmm_K3000/gmm.npz` | Nyx latents (`8f0ec4d5`) | 111, converged | `d8087ed21f42` | no | **final, live** |
| `V1_L64_b1e-4_critic_E191/gmm_K3000_reg10x/gmm.npz` | Nyx latents, ridge × 10 | 121, converged | `334efd1643cc` | no | kept (sensitivity check, reported only) |
| `V1_L64_b1e-4_critic_E191/gmm_K3000_reg0.1x/` | Nyx latents, ridge × 0.1 | — | — | records only | failed (`FAILED.json`) |
| `V1_L64_b1e-4_critic_E191_epoch150/gmm_K3000/gmm.npz` | Delphi latents (`c2ff43d9`) | 150, converged | `4354547ecc64` | no | **live** (post-fit check passed) |

Each fit folder also holds `gmm.json` (settings, seed 20261022, final log-likelihood) and `fit_log.jsonl`. Component features (`component_features.npy`) and latents (`latents_mu.npy`) are listed in the manifest too. Refits from the same latents are bit-identical, so these files can be rebuilt ([STORAGE.md](STORAGE.md)).

## Whistle detector (RidgeNet, replacement S5)

| Version | Weights | SHA-256 | Status |
|---|---|---|---|
| ridgenet-v1 | 14,209 | `58798cb46632` | kept (first design) |
| ridgenet-v2a | 16,545 | `6b2a9b0ca0e9` | kept |
| ridgenet-v2b | 14,209 | `179a78a6b314` | kept (one attempt ran out of memory: `models/detector/_failed/`) |
| **ridgenet-v2c** | 14,209 | `c00d66a0e70e` | **final, live** ([D-002](DECISIONS.md#d-002)): built the dataset; WhistleCode's receiver |
| ridgenet-v2d | 16,545 | `eb7459f43a4f` | kept |
| ridgenet-v2e | 14,209 | `ae932aab54d1` | kept |
| ridgenet-5-24 | 14,209 | `6636c9f6728d` | final for the detector paper (`mod_detector_5_24/`) |

All are in git (`models/detector/<version>/checkpoint.pt`), with `train_info.json`, and evaluations where run. The comparisons that chose v2c are the `compare_*.json` files in `models/detector/`.

## WhistleCode alphabet

| File | Built from | SHA-256 | In git | Status |
|---|---|---|---|---|
| `whistlecode/outputs/codebook/codebook.npz` | Nyx + its GMM | `cd322a0267ea` | no | **final, live**; frozen for campaign v1 |
| `whistlecode/outputs/bank/bank.npz` | real rhythms of encounters 191 and 214 | `bed9a617f435` | no | **live** |

The codebook refuses to load against other model files (it stores the checkpoint's hash). Campaign v1's frozen record (`whistlecode/paper/RESULTS.md`) lists the hashes it ran with.

## Try it model names

`configs/inference.toml` maps the page's model selector to these files: model 1 = Nyx, model 2 = Delphi, each with its own GMM. Don't refresh the main run folder to epoch 150 without repointing model 1.
