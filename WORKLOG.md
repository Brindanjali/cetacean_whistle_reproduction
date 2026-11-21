# Work log

The single place for what is planned, what is waiting, and what has been done in this project: the reproduction, WhistleCode, the detector paper, the web page and the repository itself. Every change to the project adds a line here ([how](#how-this-log-works)).

**Updated:** 2026-11-22

## At a glance

| Area | Where it stands | Next |
|---|---|---|
| Reproduction (VAE-GMM) | Complete. Dataset built; model V1 trained to epoch 150; Gaussian mixtures for epochs 101 and 150; paper evaluation done on epoch 101 | Nothing required (epoch-150 evaluation is optional: REP-1) |
| WhistleCode | v1 built and tested (campaign v1). Second round: R0, R1 and R2 (drift correction, adopted) done | **WC-R3** shape covertness |
| Detector paper | A draft exists (`docs/private/Mentor_Review_1.pdf`, never in git); its to-do file is older than the draft | DET-1, DET-2 |
| Web page and deployment | Film, Try it (models Nyx and Delphi), Encode, Decode and Record; self-hosted with Docker and Tailscale; `/healthz` and a Docker healthcheck | WEB-1 static examples are out of date |
| Engineering | 25 systems in place ([`project/README.md`](project/README.md)): tracker, Definition of Done, review, lint, tests, CI, lock file, releases, monitoring, registers, security. v0.9.0 tagged; code licensed under Apache 2.0. The first CI run failed (BUG-1, fixed; waiting for the next run) | Push, then `python tools/repo.py ci-report` (BUG-1, OPS-4); OPS-7 package upgrades |
| Course | Week 7 of 8 | Final review at the end of Week 8 |

## Key dates

- **29 Nov 2026**: end of Week 8, final evaluation and review: report, slides, code freeze (milestone M8 of the plan in `docs/course/Review-I-Guidelines.md`). The frozen code is released as **v1.0.0** (`project/RELEASES.md`).

## To do

IDs stay with an item for life. When an item is finished, tick it and add a line under its date in [Done](#done).

### Waiting on you

Only you can do these.

- [ ] **YOU-1** Agree the pivot to covert biomimetic communication with your mentor and team.
- [ ] **YOU-2** Get the paywalled papers through your college library (list in `whistlecode/RELATED_WORK.md` section 7).
- [x] **YOU-3** Enable the pre-commit checks once in this clone (work log, secrets, lint): `git config core.hooksPath .githooks`.
- [ ] **YOU-4** Decide on the optional encounter-308 download (33 files, about 6 GB) for a never-used test encounter. Needed only by WC-R6.
- [ ] **YOU-5** Find 10 volunteers for the listening test (WC-R4): 20 pairs each, anonymous.
- [x] **YOU-6** Choose a licence for the code (the README says none is chosen). Recommended: MIT; reasons and steps in `project/LICENSING.md`. Decided: Apache 2.0 (D-022).
- [x] **YOU-7** After committing the engineering systems: tag and push release v0.9.0 (`python tools/repo.py release-check 0.9.0` prints the commands), then check the first CI run on GitHub (Actions tab).
- [ ] **YOU-8** First backup of the three things that exist only on this laptop: `whistlecode/outputs/paper/`, `docs/private/` and the WhistleCode result summaries. Commands in `project/STORAGE.md`; then monthly.
- [x] **YOU-9** Delete the three local branches already merged into `main`: `git branch -d preprocessing-v2c-multi-encounter vaegmm-colab-training vaegmm-training`. Optionally the two merged remote ones: `git push origin --delete preprocessing-v2c-multi-encounter vaegmm-training`.

### Bugs

Format and severity levels: `project/WORKFLOW.md`, "Task tracker".

- [ ] **BUG-1** (high, CI) The WhistleCode suite fails on GitHub (first run, 2026-11-21, run 44936177193): `cryptography`, which `serve --lan` and its test import, is in no requirements file, so CI never installs it. Fix made 2026-11-22 (added to `whistlecode/requirements.txt` and `constraints.txt`); tick when the next run is green.

### WhistleCode, second round

The plan, pass marks and rules are frozen in `whistlecode/PLAN.md` section 8.7.

- [x] **WC-R0** Threat model, claims, frozen pass marks v2.
- [x] **WC-R1** Literature review and novelty statement, with review fixes.
- [ ] **WC-R1a** Remaining literature:
  - search IEEE Xplore, Google Scholar and CNKI;
  - read the four open-access papers and the seven with no abstract;
  - re-check the novelty statement.
- [x] **WC-R2** Doppler and clock-drift correction in the receiver. Develop on encounter 214 only.
- [ ] **WC-R3** Shape covertness: find what gives the shapes away, try the epoch-150 voice (Delphi), tau and codebook choice. Shape AUC is 0.944 against a mark of 0.75. **Next.**
- [ ] **WC-R4** Baselines and listeners: matched-filter modem, listening test (needs YOU-5), whistle-against-noise classifier, likelihood under the species model, ECSM3 if its definition can be found.
- [ ] **WC-R5** In-air test between two laptops (20 messages at 2 m; also 1 m and 4 m).
- [ ] **WC-R6** Freeze, then run campaign v2 once, overnight (seed 20261205; encounter 276; encounter 308 if YOU-4).
- [ ] **WC-R7** Reframe the documents and the page:
  - new title;
  - README leads with WhistleCode;
  - page story Listen → Learn → Speak → Hide → Hear;
  - correct `TEST_PROTOCOL.md`'s outdated "epoch 150 was not completed";
  - reconcile the data-whistle share (one in four vs a third).
- [ ] **WC-R8** Write-up and review slides.

### Detector paper

- [ ] **DET-1** Bring `mod_detector_5_24/TODO.md` (last changed 31 Oct) up to date with the draft. The draft reports a Silbido comparison on 12 DCLDE 2011 recordings and a false-alarm test on 145.5 min of whistle-free recordings.
- [ ] **DET-2** Copy the DCLDE 2011 score files from Google Drive into `mod_detector_5_24/results/` and commit them.
- [ ] **DET-3** Real-data test of the 2-24 kHz detector on hand-labelled 2017 recordings (from `TODO.md`; needs a labeller and a tool).
- [ ] **DET-4** Act on the mentor's review of the draft, when it arrives.

### Reproduction

- [ ] **REP-1** Optional: paper evaluation (Tables 1, 3, 6; Figs. 7-10, 12) for the epoch-150 model, in its own folder so model 1 is untouched.

### Web page and deployment

- [ ] **WEB-1** Re-run `python whistle.py export-web`. The static examples in `web/data/` date from 24 Oct, before any model existed.
- [ ] **WEB-2** Replace the film's hand-made research illustration (Listen → Learn → Imagine) with real model output. This is the page's Phase 4; it overlaps WC-R7.
- [x] **WEB-3** Decide what to do with the untracked `cluster/` kit (running the demo on the college cluster): commit it, or ignore it. Decided: commit it (D-021).

### Repository housekeeping

- [x] **OPS-1** Decide which untracked files in `docs/` go into git: the week 1-2 notes, the training-plan PDF, the review slides, and the detector draft. Decided: all but the draft, in `docs/course/` (D-020).
- [x] **OPS-2** Keep `docs/Whistle extraction.pdf` out of git: it is a published Elsevier paper, and the repository is public. Now in the ignored `docs/private/`.
- [x] **OPS-3** Engineering systems for a one-owner, one-engineer team (`project/README.md`).
- [ ] **OPS-4** Read the first CI run on GitHub (after YOU-7) and fix anything that fails only on Linux. CI has not run yet; the tests were simulated locally on a git-only copy. First run read 2026-11-22: lint, secrets, links, checksums, configs and the reproduction suite passed; the WhistleCode suite failed (BUG-1); the audit flagged eight packages (OPS-7). Tick when a run is green.
- [ ] **OPS-5** Copy the records behind three reported results into git (`whistlecode/paper/records/`): EXP-015 (normal conditions), EXP-019 (SNR gap), EXP-020 (R2). Today they exist only in `whistlecode/outputs/` (`project/TRACEABILITY.md`, "Gap").
- [ ] **OPS-6** Confirm the reuse terms of the two NOAA files in `metadata/` (`DCLDE2020_DetectionData.xlsx`, `Dataset_DCLDE_Oahu.pdf`) and note them in `project/LICENSING.md`.
- [ ] **OPS-7** Upgrade the eight pinned packages with published advisories (OSV, 2026-11-22) to the versions that fix them: anyio 4.14.2, certifi 2026.10.18, cryptography 49.0.0, filelock 4.2.1, fsspec 2026.6.0, pillow 13.0.0, pytest 9.0.3, setuptools 84.1.0. Needs your OK to download them. Then `python tools/repo.py lock`, `check`, update `deploy/requirements-serve.txt` and redeploy. Pillow 13 is a major version: check the page's pictures.

## Decided not to do

| What | Decided | Why |
|---|---|---|
| Fig. 11 and Tables 2, 4, 5 of the paper | 2026-11-09 | No GMM fits at other K; the FID and precision/recall weights download was declined |
| Review-I enhancements 01-03 (realism loss, learned conditioning, three-axis evaluation) | Mid-Nov | Superseded, first by WhistleFlow, then by WhistleCode |
| WhistleFlow (audio-native model) | 2026-11-17 | Replaced by WhistleCode; folder removed 2026-11-20 |
| Real recorded shapes as WhistleCode's voice | 2026-11-19 | VAE shapes are final |

## Done

Newest first. Older history is grouped by stage. Commit hashes are given where the work was committed; an entry's own commit is the one that adds it.

### 2026-11-22

- **Repository**: code licensed under the Apache License 2.0 (YOU-6, D-022). `LICENSE` is the unmodified apache.org text (SHA-256 `cfc7749b…3d30`); new `NOTICE` names the copyright holders and lists the third-party material the licence does not cover. Recorded in `pyproject.toml`, `CITATION.cff`, `README.md`, `project/LICENSING.md`, `project/DECISIONS.md` and `CHANGELOG.md`.
- **CI**: first run read (OPS-4). Cause of the WhistleCode-suite failure found (BUG-1): `cryptography` missing from the requirements; now in `whistlecode/requirements.txt` and `constraints.txt` (56 packages).
  - `.github/workflows/ci.yml`: failing tests (`pytest-github-actions-annotate-failures`) and lint findings become annotations, which anyone can read without signing in; the dependency audit turns findings into warnings and fails only if it cannot run; `actions/checkout` v5 and `actions/setup-python` v6 replace versions on a deprecated Node.js.
  - `tools/repo.py`: new `ci-report` (the latest run's jobs, failed steps and annotations, from GitHub's public API) and `audit-report` (used by CI).
  - Audit of the pins against OSV: eight packages have published advisories (OPS-7). Noted in `.github/SECURITY.md`.
  - Docs: `project/ENGINEERING.md` (CI, environment), `project/HANDOVER.md` and `project/README.md` (`ci-report`).
- **Repository**: the three merged branches are deleted (YOU-9); v0.9.0 is tagged and pushed (YOU-7); the pre-commit checks are on (YOU-3).

### 2026-11-21

- **Repository**: engineering systems for the whole project (OPS-3), indexed in the new `project/README.md`.
  - **Process:** task tracker rules with a new "Bugs" list in this file, Definition of Done and code review (`project/WORKFLOW.md`).
  - **Code:** `pyproject.toml` (version 0.9.0, ruff lint settings, pytest settings; replaces `pytest.ini`), `.python-version`, `.editorconfig`, the lock file `constraints.txt`, and the rules for quality, test tiers, CI, environment and configuration (`project/ENGINEERING.md`).
  - **Checks:** new `tools/repo.py` (one `check` command for lint, configs, secrets, links, checksums and both test suites, plus `lock`, `health` and `release-check`); `.githooks/pre-commit` now also scans staged files for secrets and lints staged Python files; CI in `.github/workflows/ci.yml` (lint, secret scan of files and history, links, checksums, both suites on CPU, advisory dependency audit).
  - **Releases and monitoring:** `CHANGELOG.md`, `CITATION.cff`, `project/RELEASES.md` (versions, release steps, deployment checklist, what is live, monitoring); `GET /healthz` in `whistlecode/wcode/web.py` (with `project_version()` in `whistlecode/wcode/config.py`) and a Docker healthcheck in `deploy/docker-compose.yml`.
  - **Registers:** `project/TRACEABILITY.md`, `EXPERIMENTS.md` (EXP-001 to EXP-025), `MODELS.md` with `project/checksums/models.sha256` (28 files; all match), `DATA.md`, `DECISIONS.md` (D-001 to D-021), `INCIDENTS.md` (INC-001, INC-002), `STORAGE.md`, `LICENSING.md`, `HANDOVER.md`; `.github/SECURITY.md`; `docs/INDEX.md` and `docs/ARCHITECTURE.md`.
  - **Tests:** 4 new `/healthz` tests (`whistlecode/tests/test_wc_web.py`). A git-only copy of the repository (what CI sees) showed 42 WhistleCode tests crashing instead of skipping without the local dataset and latents. Ten are now marked `localdata`, and four fixtures request the new `local_data` fixture (`whistlecode/tests/conftest.py`, `test_wc_codebook.py`, `test_wc_contour_synth.py`, `test_wc_pipeline.py`, `test_wc_transmitter.py`, `test_wc_realism.py`). Result: laptop 202 + 269 passed; git-only copy 199 + 208 passed, 3 + 61 skipped, none failed.
  - **Lint fixes:** unused imports and loop variables removed in 25 files across `src/`, `tests/`, `whistlecode/` and `mod_detector_5_24/`; seven false alarms annotated. No behaviour change.
  - **Layout:** `docs/` sorted into `course/` (in git), `explainers/` and `private/` (both ignored); `.gitignore` covers every `encounter_*_audio/`, `.ruff_cache/`, `floorplan/`. Caches deleted. The `cluster/` kit and the untracked course files are ready to commit (D-020, D-021). Ticks OPS-1, OPS-2 and WEB-3.
  - **Scans:** no secret in 374 files or in the full history; 286 relative links and anchors, none broken; all 28 recorded checksums match.
- **WhistleCode**: R2 Doppler and clock-drift correction, adopted.
  - **Receiver** (`whistlecode/wcode/receiver.py`, new `[receiver] drift_*` settings in `whistlecode/config.toml`): the frame search also searches time scales of 1 ± 0.25 %. A whole-message fit over every known whistle then refines the drift, and the payload is read on the sender's clock. With `drift_correction = false` it is exactly campaign v1's receiver.
  - **Measured on encounter-214 noise only,** with the new `whistlecode/experiments/drift_dev.py` (results in `whistlecode/outputs/drift_dev/`, not in git):
    - Doppler at 15 dB, -3 to +3 m/s: 49-50 of 50 exact at every speed (was 0-50).
    - Random sea at 5 / 10 / 20 dB: 18 / 42 / 39 of 50 (was 4 / 15 / 14). Echoes remain the main loss.
  - **Adoption check** on campaign v1's encounter-214 sweep: 8 / 50 / 49 / 50 → 10 / 50 / 49 / 50 at 5 / 10 / 15 / 20 dB. No wrong text, wrong-key message or message in empty noise.
  - **Campaign script** (`whistlecode/experiments/paper_eval.py`): oracle synchronisation now also reads at the true time scale.
  - **Tests and docs:** 13 new receiver test cases (`whistlecode/tests/test_wc_pipeline.py`), including sound-card offsets of -120 to +250 ppm on synthetic tracks. `whistlecode/PLAN.md` updated (new "Drift correction" section, sections 7, 13 and 14). Stale "no drift correction" lines corrected in `README.md` and `docs/TECHNICAL_REFERENCE.md`.
- **Repository**: work log system added: this file, the log rule in `CLAUDE.md`, and an optional git check in `.githooks/pre-commit` (enable with YOU-3).
- **WhistleCode**: R1 review fixes:
  - **SNR gap** measured on real noise with the new `whistlecode/experiments/snr_inband.py`: 22.3 dB (encounter 214) and 25.3 dB (276).
  - **Literature:** 2012-2023 searched.
  - **Threat model:** adversary A6 added.
  - **Novelty statement:** narrowed.
  - **Campaign v2 measures:** defined (`87a6e42`).
- **WhistleCode**: R1 literature review, with a comparison against ten published schemes and a draft novelty statement; adversary A5 added (`a961a13`).
- **WhistleCode**: R0. Threat model and claims (`whistlecode/THREAT_MODEL.md`); second-round protocol and pass marks v2 frozen in `PLAN.md` 8.7 (`ed87eb4`).
- **Project**: pivot. The project is now presented as covert biomimetic communication, with the reproduction as its foundation.

### 2026-11-20

- **Repository**: WhistleFlow removed (`2bccef6`).
- **Docs**: training spec updated for the completed 150-epoch run (`41bc878`); README rewritten, with technical detail moved to `docs/TECHNICAL_REFERENCE.md` (`4131ba0`).
- **Web**: Try it model selector. The models are named Nyx (epoch 101) and Delphi (epoch 150) (`7297e32`, `55d6d55`, `456c779`, `30d4261`).
- **Reproduction**: epoch-150 model given its own GMM (K = 3,000, check passed) and component features (`cd0797d`).
- **Reproduction**: V1 training resumed on a Colab A100 and completed at epoch 150. The notebook gained a pre-flight check and an epoch rollback guard (`65ab4c9`).
- **WhistleCode**: paper test campaign v1, 4,200 trials and 500 empty tries (`416936c`):
  - **Passed:** E1 clean channel; 0 false messages.
  - **Failed:** final run 84.5 %; shape AUC 0.944.
- **Deploy**: Docker and Tailscale Funnel; 720p film clips for visitors (`ea18d03`).

### 2026-11-19

- **Web**: Record option in Decode, with the microphone feeding the decoder (`7e13cc5`, `7789bd4`, `c8279cd`, `9067143`).
- **WhistleCode**: https and `--lan` serving for a second computer (`48edcd1`, `f7f5059`, `595b15d`, `d88b247`).
- **WhistleCode**: Encode and Decode places on the project page (`f2d7efe`).
- **WhistleCode**: each whistle read at its known time, which proved normal conditions: 90/90 messages in encounter-214 noise and 87/90 in 276 (`876a5b9`).
- **WhistleCode**: multipath and Doppler sea channel (`b07e67a`); recorded voices, virtual animals and clicks in the sender (`80a122e`).

### 2026-11-18

- **WhistleCode**: format v2 pipeline built end to end (`09081db`):
  - **Gate test F1 failed** (`ab33238`); the idea was finalised anyway (`b511c7f`).
  - **Format work:** compact format and borrowed real rhythm planned (`baabc1f`, `919f9b8`).
  - **Earlier phases:** P0-P2 built: framing, Reed-Solomon, codebook, transmitter (`cb57336`, `f69038d`, `6b1a594`, `6f00a2e`).
- **Reproduction**: two attempts to resume V1 on another Colab GPU diverged and were discarded (no commit).

### 2026-11-15 to 2026-11-17

- **WhistleCode**: plan for hiding messages in whistles (`fab768e`, `4744a91`, `106a1b2`).
- **WhistleFlow**: proposal started (`deb1e3f`), then dropped on 17 Nov.
- **Cluster**: kit for running the demo on the college cluster (`cluster/`, not in git). `.gitignore` updated for the cluster files (`e629415`).

### 2026-11-08 to 2026-11-09: reproduction evaluated (epoch 101)

- Table 6 cost, with a warm-GPU supplement (`e0e0122`). Fig. 11 and Tables 2, 4, 5 recorded as not computed (`539d09f`).
- Table 3, Fig. 12 and Figs. 7-10 (`119fb82`); component features and Table 1 (`3e32da5`).
- GMM fitted at K = 3,000: 111 iterations, check passed (`7350157`).
- V1 finalised at epoch 101; notebook cells 10-11 run on the laptop (`c4ac1b3`).

### 2026-11-01 to 2026-11-03: main training

- V1 trained on a Colab A100 to epoch 101 (`9ac87a0`), after review fixes (`7eb7a1a`).
- Scope cut to encounter 191, 150 epochs, K = 3,000 (`0151aba`).
- Week 4 logbook, results table and Review-I answers (`9cbcc68`, `914e6e2`); `plot-waveform` command (`95dc069`).

### 2026-10-28 to 2026-10-31: training set-up and detector benchmark

- DCLDE 2011 benchmark of the 5-24 kHz detector (`f388805`); public docs fixed after an audit (`6f2fe93`); `.gitignore` updated (`a2968a7`).
- Detector 5-24 kHz variant trained (`63e11ae`, `d20fbe1`, `29b444e`).
- First all-data V1 run on Colab, stopped at epoch 7 (no commit).
- Cross-entropy loss, micro-batching, Colab notebook and bundle (`5925df3`). Gate G3 passed; G4 not met, and accepted by the owner.
- Teammate branch merged, starting with spelling fixes (pull requests #1-#3).

### 2026-10-22 to 2026-10-24: model code and web page

- 3D scene, underwater Try it and visual overhaul (`9fae208`, `ffbaa5f`, `fdab69d`, `1df2c68`).
- Inference pipeline, image-to-sound and the Try it demo (`f23674d`).
- Project web page added, and its scroll stutter fixed (`6e5bd21`, `f31bcd2`).
- VAE-GMM training, GMM fitting and evaluation code, with the audited training specification (`f6827ce`). Gates G1, G2, G5 and G6 passed.

### 2026-10-08 to 2026-10-21: data and preprocessing

- Final dataset: 180,154 whistle images from 1,415 files in 8 encounters, with detector `ridgenet-v2c` (`8cf3ed4`, `2cf1fc1`).
- Detector versions v1-v2e compared on synthetic data; v2c adopted.
- Preprocessing S1-S9, the specification and the first detector (`02f445c`, 8 Oct).

## How this log works

- **Every change gets a line** under today's date in Done, newest date first. The line names the area (Reproduction, WhistleCode, Detector, Web, Deploy, Docs, Repository) and says in plain words what changed and where. Add a new date heading when needed.
- **Planned work goes into To do** with an ID before it starts. Only items for you go under "Waiting on you". When it is finished, tick it (`[x]`) and log it under Done.
- **Bugs go under "Bugs"** as `BUG-n`, with how to make them happen and how bad they are (`project/WORKFLOW.md`).
- **Update "At a glance" and "Updated"** when the picture changes.
- **Don't rewrite old entries.** Correct them with a new dated line.
- **Commits.** Include `WORKLOG.md` in every commit. Once YOU-3 is done, git refuses a commit that changes other files without it. To skip the check for one commit, use `WORKLOG_SKIP=1 git commit ...` in Git Bash, or `$env:WORKLOG_SKIP=1; git commit ...` in PowerShell, then `Remove-Item Env:WORKLOG_SKIP`.
