# Decision records

Project-level choices: what was decided, why, what else was considered, and what follows from it. Index of all systems: [README.md](README.md).

**Two levels of decision**

- **Here:** choices that later work depends on (scope, models, data splits, protocols, tools, layout). One entry each, numbered D-001 upwards, never renumbered.
- **Inline `[DECISION]` tags:** the many parameter-level choices where the paper is silent. They stay next to the value they decide, in the TOML files and specifications ([tag index](#inline-decision-tags)).

**Rules:** a decision is never edited away. A changed mind gets a new entry that says "Supersedes D-0NN", and the old entry gets "Superseded by D-0NN". Dropped work is also listed in `WORKLOG.md` "Decided not to do".

## Index

| ID | Date | Decision | Status |
|---|---|---|---|
| [D-001](#d-001) | 2026-10-08 | Reproduce stage by stage, with evidence tags and locked paper values | in force |
| [D-002](#d-002) | 2026-10-21 | RidgeNet v2c replaces the paper's unavailable detector | in force |
| [D-003](#d-003) | 2026-10-08 | Use hydrophone channel 0 only | in force |
| [D-004](#d-004) | 2026-11-03 | Batch 5,772 on one GPU, learning rates scaled linearly | in force |
| [D-005](#d-005) | 2026-11-02 | Train on encounter 191 only, 150 epochs, K = 3,000 | in force |
| [D-006](#d-006) | 2026-11-09 | Fig. 11 and Tables 2, 4, 5 are not computed | in force |
| [D-007](#d-007) | 2026-11-20 | Epoch 101 (Nyx) stays the final model; epoch 150 (Delphi) is a second model | in force |
| [D-008](#d-008) | 2026-10-28 | Gate G4 accepted without a longer run | in force |
| [D-009](#d-009) | 2026-11-21 | Data splits: 191 trains, 214 develops, 276 tests | in force |
| [D-010](#d-010) | 2026-11-20 | Pass marks are frozen before the runs; failures are reported as measured | in force |
| [D-011](#d-011) | 2026-11-19 | VAE shapes are WhistleCode's final voice | in force |
| [D-012](#d-012) | 2026-11-21 | Doppler and clock-drift correction adopted | in force |
| [D-013](#d-013) | 2026-11-21 | Present the project as covert biomimetic communication | waiting on the mentor (YOU-1) |
| [D-014](#d-014) | 2026-11-20 | Self-host the page with Docker and Tailscale Funnel | in force |
| [D-015](#d-015) | 2026-10-23 | The page is desktop-only | in force |
| [D-016](#d-016) | 2026-11-21 | Lint with ruff; no auto-formatter | in force |
| [D-017](#d-017) | 2026-11-21 | Engineering systems as plain files in the repository | in force |
| [D-018](#d-018) | 2026-11-21 | Top-level folders stay where they are; only `docs/` is reorganised | in force |
| [D-019](#d-019) | 2026-11-21 | One release version for the repository: 0.9.0 now, 1.0.0 at the freeze | in force |
| [D-020](#d-020) | 2026-11-21 | What from `docs/` goes into git | in force |
| [D-021](#d-021) | 2026-11-21 | The cluster kit goes into git | in force |

## Reproduction

### D-001

**Reproduce stage by stage, with evidence tags and locked paper values.** Every value is tagged as paper evidence (`[EXPLICIT]`, `[IMPLIED]`, `[UNSPECIFIED]`) or a choice made here (`[DECISION]`, `[REPLACEMENT]`). The paper's values sit in locked `[paper]` sections that the code refuses to change. *Why:* a reproduction is only useful if every difference from the paper can be seen. *Alternatives:* adapt an existing implementation (none was available). *Consequence:* every deviation is listed in the specifications and in each run's `train_info.json`.

### D-002

**RidgeNet v2c replaces the paper's S5 detector.** The paper's detector (its reference [31]) and tracker are unavailable. RidgeNet, a new 14,209-weight network trained only on synthetic whistles, meets the functional requirements of spec §11. Versions v1 and v2a-v2e were compared on synthetic data (EXP-001), and v2c was adopted. *Consequence:* it is a replacement, not claimed to be equivalent; its accuracy on real data is unknown (DET-3).

### D-003

**Use hydrophone channel 0 only.** The recordings have six channels and the paper does not say which it used. Channel 0 was chosen arbitrarily. *Consequence:* listed as a limitation in the README.

### D-004

**Batch 5,772 on one GPU, with learning rates scaled linearly** (lr × B / 896), instead of the paper's 7 × 128 = 896. *Why:* one Colab A100 80 GB, and a time budget. *Alternative:* the paper's batch of 896, kept as the fallback run. *Consequence:* the main run has no gate of its own at this batch size; it was watched through its loss curves and sample grids.

### D-005

**Train on encounter 191 only, for 150 epochs, with K = 3,000** (the paper: more data, K = 10,000). *Why:* the course timeline and Colab budget; the first all-data run was stopped at epoch 7 (EXP-004). *Consequence:* reduced scope, listed in the README limitations. WhistleCode also keeps K = 3,000 (`whistlecode/PLAN.md` 3.1).

### D-006

**Fig. 11 and Tables 2, 4 and 5 are not computed.** They need GMM fits at other K and the Inception-V3 and VGG-16 weights, whose download the owner declined. *Decided by:* the owner, 2026-11-09.

### D-007

**Epoch 101 (Nyx) stays the final model** for the paper results and WhistleCode campaign v1. The resumed run's epoch 150 (Delphi) lives in its own folder with its own GMM and is Try it's model 2. *Why:* every result so far was made with epoch 101; replacing it would invalidate them. *Consequence:* the main run folder must not be refreshed to epoch 150 without repointing model 1. Delphi's paper evaluation is optional (REP-1), and its use as WhistleCode's voice is tested in WC-R3.

### D-008

**Gate G4 accepted without a longer run.** The overfit test reached 0.416 against a mark of ≤ 0.3 in 3,000 steps, with a steady fall that extrapolated to the mark at about 3,300-3,500 steps (not measured). *Decided by:* the owner, 2026-10-28. Records: `models/vaegmm/_gates/G4_*`.

## WhistleCode

### D-009

**Data splits are fixed:** encounter 191 trains the model and supplies the rhythm bank; encounter 214 is for WhistleCode development; encounter 276 is the test set, used only by the frozen campaigns. Encounter 308 is an optional fresh test (YOU-4). Campaign v2's message seed (20261205) is used by no development run. Source: `whistlecode/PLAN.md` 8.7. *Why:* nothing may be tuned on the data that judges it.

### D-010

**Pass marks are frozen before the runs, and a failure is reported as measured.** Campaign v1's marks were fixed in PLAN.md 8.6, campaign v2's in 8.7 (2026-11-21), before any work they judge. A failed mark is never rewritten as a pass. *Consequence:* campaign v1's two failures (final run 84.5 %, shape AUC 0.944) stand in every document.

### D-011

**The VAE's own shapes are WhistleCode's final voice.** Real recorded shapes were tried as the sender's voice (EXP-016) and rejected. The sender keeps real recorded voices, rhythm and clicks around the VAE shapes.

### D-012

**Doppler and clock-drift correction is adopted in the receiver** (WC-R2). On encounter 214 only, it raised Doppler results from 0-50 to 49-50 of 50 at every speed from -3 to +3 m/s, and met the receiver adoption rule of PLAN.md 8.7 (EXP-020). It can be switched off (`drift_correction = false`), which gives exactly campaign v1's receiver.

### D-013

**Present the project as covert biomimetic communication**, with the reproduction as its foundation. *Why:* WhistleCode is the project's own contribution. *Status:* needs the mentor's and team's agreement (YOU-1); the documents are reframed in WC-R7.

## Page and deployment

### D-014

**Self-host the page with Docker and Tailscale Funnel.** Free, a fixed https address (which the microphone needs), and the laptop's GPU. *Alternative:* a paid cloud host. *Consequence:* the page is up only while the laptop is on (see `project/RELEASES.md`).

### D-015

**The page is designed for desktop browsers only.** Phone layouts are not built or audited.

## Engineering

### D-016

**Lint with ruff; no auto-formatter.** Rules: pyflakes, import and statement checks, and bugbear, with the house style allowed (settings in `pyproject.toml`). *Why:* the code is consistent in its own compact style, and `ruff format` would rewrite 121 files the week before the code freeze. *Alternative:* adopt `ruff format` after the freeze, in one commit of its own.

### D-017

**The engineering systems are plain files in the repository**, checked by `tools/repo.py`, a git hook and GitHub Actions. *Why:* one owner and one engineer need no ticket tracker or dashboards; files are versioned with the code and readable offline. *Alternative:* GitHub Issues and Projects (possible later; the IDs would carry over).

### D-018

**The top-level folders stay where they are; only `docs/` is reorganised.** *Why:* the paths of `encounter_*_audio/`, `preprocessed/`, `models/` and `post_training/` are written into lineage records (`train_info.json`, manifests), the Colab notebooks and the Google Drive copy. Moving them would break records that must not be rewritten. `docs/` had no such references and is now sorted into `course/`, `explainers/` and `private/`. Each folder's purpose is in the README's layout section and in `docs/INDEX.md`.

### D-019

**One release version for the whole repository**, in `pyproject.toml`: 0.9.0 for today's state, 1.0.0 at the code freeze (29 Nov). `whistlepipe.__version__` stays the preprocessing pipeline's own version, because dataset records store it.

### D-020

**What from `docs/` goes into git** (OPS-1, OPS-2). In git: the week 1 and 2 notes, the training-plan PDF and the review slides, in `docs/course/`. Never in git, kept in `docs/private/`: the unpublished detector paper draft (the repository is public, and publishing a draft could hurt its review) and the Elsevier paper (copyright).

### D-021

**The cluster kit (`cluster/`) goes into git** (WEB-3): two bundle scripts and the node scripts for running the demo on the college cluster. It holds no secrets (checked by the secret scan); its build outputs stay ignored.

## Inline decision tags

Where the parameter-level `[DECISION]` tags are (counted 2026-11-21; `git grep -c "\[DECISION"` gives the current numbers):

| File | Tags |
|---|---|
| `whistlecode/config.toml` | 109 |
| `whistlecode/PLAN.md` | 42 |
| `configs/vaegmm.toml` | 38 |
| `resources/TRAINING_SPECIFICATION.md` | 33 |
| `configs/pipeline.toml` | 26 |
| `mod_detector_5_24/pipeline.toml` | 26 |
| `configs/inference.toml` | 15 |
| Code docstrings and comments (`src/`, `whistlecode/`, `post_training/`) | about 35 |
