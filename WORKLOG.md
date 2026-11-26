# Work log

The single place for what is planned, what is waiting, and what has been done in this project: the message system (WhistleCode), the whistle model (VAE-GMM), the detector paper, the web page and the repository itself. Every change to the project adds a line here ([how](#how-this-log-works)).

**Updated:** 2026-11-27

## At a glance

| Area | Where it stands | Next |
|---|---|---|
| Whistle model (VAE-GMM) | Complete. Dataset built; model V1 trained to epoch 150; Gaussian mixtures for epochs 101 and 150; paper evaluation done on both checkpoints (epoch 150: REP-1, 2026-11-27) | Nothing required |
| Message system (WhistleCode) | v1 built and tested (campaign v1). Second round: R0, R1 and R2 (drift correction, adopted) done | **WC-R3** shape covertness |
| Detector paper | A draft exists (`docs/private/Mentor_Review_1.pdf`, never in git); its to-do file is older than the draft | DET-1, DET-2 |
| Web page and deployment | The page retold as Falsetto (WEB-5, done 2026-11-26): the film drawn from real records in WebGL (Listen, Learn, Speak, Hide, Hear), then Encode, Decode and Record; Try it (Nyx and Delphi) on `model.html`. Self-hosted with Docker and Tailscale, live from `main` (`f5b794e`); `/healthz` and a Docker healthcheck. Audit bugs BUG-2 to BUG-7 and BUG-13 fixed | **WEB-6** done and merged into `main` (`9f91c3b`, 2026-11-27): Listen redrawn, Learn and Speak bolder, Try it back on the page; in v1.0.0; Try it back on the page after Decode (D-028); WEB-4 (hide the API docs, list the routes); WEB-1 static examples are out of date |
| Engineering | 25 systems in place ([`project/README.md`](project/README.md)): tracker, Definition of Done, review, lint, tests, CI, lock file, releases, monitoring, registers, security. v0.9.0 and v0.10.0 tagged (CI green on v0.10.0); code licensed under Apache 2.0; no pin has a known advisory, and the server image installs exactly the pins. Whole-project audit 2026-11-23 ([`project/AUDIT_2026-11-23.md`](project/AUDIT_2026-11-23.md)): records and numbers sound; 11 bugs recorded | Audit bugs still open: BUG-8, BUG-10 to BUG-12; OPS-10 to OPS-13 |
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
- [x] **YOU-10** Commit, then release v0.10.0 and rebuild the server so the page runs pillow 13: `python tools/repo.py release-check 0.10.0` prints the tag commands; then `docker compose -f deploy/docker-compose.yml up -d --build` and the deployment checklist in `project/RELEASES.md`. Note from the 2026-11-23 audit: the printed command tags HEAD, which now also holds the changes listed under [Unreleased]; tag the release commit instead: `git tag -a v0.10.0 9697663 -m "v0.10.0"`. Rebuild and deployment done 2026-11-24 (see Done); left for you: the tag and the pushes. Done 2026-11-24: v0.10.0 tagged on `9697663` and pushed; CI run 45323960151 on the tag is green.
- [ ] **YOU-11** Attach both `gmm.npz` files (about 100 MB each) and the WhistleCode codebook to a GitHub release, so a clone can generate whistles and run WhistleCode without the 68 GB of encounter-191 audio. Files: `models/vaegmm/V1_L64_b1e-4_critic_E191/gmm_K3000/gmm.npz`, `models/vaegmm/V1_L64_b1e-4_critic_E191_epoch150/gmm_K3000/gmm.npz`, `whistlecode/outputs/codebook/codebook.npz` and `codebook.json`. Then the README's "What runs from a clone" table gets a download line with their SHA-256 (OPS-9).
- [ ] **YOU-12** Check that the college's own course material in `docs/course/` may be published in a public repository (for example `Acoustic Projects Review-I Guidelines.pdf`). Your own notes and slides there are yours to publish.
- [ ] **YOU-13** Optional: add your name (or your institution) to `README.md` "About this project" and `CITATION.cff`. A named author is the strongest single sign that a repository is legitimate; it stays a handle until you decide (D-023).
- [x] **YOU-15** Commit WEB-6 on the branch `web-scene-v2` and merge it into `main` before the v1.0.0 freeze (29 Nov), with the commands Claude gave on 2026-11-27. Until then the live page shows the branch's working tree: the Docker container serves this folder as it is. Done 2026-11-27: committed `0abb2b3`, merged into `main` as `9f91c3b`, pushed (the first attempt skipped `git add`, so nothing was committed until the second).
- [ ] **YOU-14** Choose the project's final name (Falsetto is temporary, D-024). Then rename the GitHub repository, whose name still says "reproduction": Settings → General → Repository name, or `gh repo rename <name>` (GitHub forwards the old address). Then `git remote set-url origin https://github.com/anonymus-k-dot/<name>.git`, and ask Claude to update the links and the places D-024 lists.
- [x] **YOU-9** Delete the three local branches already merged into `main`: `git branch -d preprocessing-v2c-multi-encounter vaegmm-colab-training vaegmm-training`. Optionally the two merged remote ones: `git push origin --delete preprocessing-v2c-multi-encounter vaegmm-training`.

### Bugs

Format and severity levels: `project/WORKFLOW.md`, "Task tracker".

- [x] **BUG-1** (high, CI) The WhistleCode suite fails on GitHub (first run, 2026-11-21, run 44936177193): `cryptography`, which `serve --lan` and its test import, is in no requirements file, so CI never installs it. Fix made 2026-11-22 (added to `whistlecode/requirements.txt` and `constraints.txt`); tick when the next run is green. Fixed: run 44937841060 (`81162fe`) is green.

Found by the audit of 2026-11-23; details, places and fixes in `project/AUDIT_2026-11-23.md`. BUG-2 to BUG-5 matter because the page is open to the internet (`"AllowFunnel": true`); until they are fixed, `"AllowFunnel": false` in `deploy/tailscale/serve.json` keeps it to your own devices.

- [x] **BUG-2** (high, web) A small upload decodes to gigabytes: Decode and Try it read every channel of the whole file as float32, with no limit on sample rate or channels. A silent 8-channel FLAC at 655 kHz, 300 s long, is about 1.7 MB and decodes to 6.3 GB (measured ratio about 3,750 to 1). A few uploads exhaust the memory (`whistlecode/wcode/web.py` `read_audio`, `src/whistlepipe/audio.py` `read_upload`). Fixed 2026-11-23: one channel read in blocks, never past the length limit; rate and channel caps.
- [x] **BUG-3** (high, web) `POST /api/analyze-example` does not clamp `n_samples` (`/api/analyze` does): `{"example": ..., "n_samples": 100000}` makes the worker decode and save 100,000 images per whistle; a negative value crashes the job (`src/whistlepipe/server.py`, `infer.py` `Engine.analyze`). Fixed 2026-11-23: clamped to 0-8 on both routes.
- [x] **BUG-4** (high, web) No limit on waiting jobs or stored uploads: each request adds a queued job that is never pruned, and each upload (up to 200 MB) is written to disk first. Posting in a loop fills the disk and the queue (`wcode/web.py` and `server.py`, class `Jobs`). Fixed 2026-11-23: request sizes enforced as the body arrives, two uploads at once, six waiting jobs, uploads deleted after their job.
- [x] **BUG-5** (medium, web) `POST /api/reload-model` is open to anyone: each call re-reads about 200 MB of model files and holds a server thread while the running job finishes; repeated calls stall the page (`src/whistlepipe/server.py`). Fixed 2026-11-23: off unless `[server] allow_reload = true`.
- [x] **BUG-6** (medium, web) Decoded message text is written to the decode job's `result.json` (kept for the newest 60 jobs, readable by anyone with the job ID), although `web.py` and `.github/SECURITY.md` say message text is never written to disk. Keys are not written. Fixed 2026-11-24: the message is kept in memory with its job and added to `result.json` only as it is served.
- [x] **BUG-7** (medium, web) Tracebacks reach the browser, although `.github/SECURITY.md` says they do not: a failed job's `error.txt` is served by `/api/wc/files/<id>/error.txt`, `/api/results/<id>/error.txt` and the results zip, and the error message names it. Fixed 2026-11-24: no route or zip serves `error.txt`; the message gives only the error's type.
- [ ] **BUG-8** (medium, monitoring) `python tools/repo.py health` crashes with a JSON error when the server answers with a non-JSON error page (as a proxy does when the app is down); confirmed against a plain 404 page. With `--every`, monitoring stops at the first outage.
- [x] **BUG-9** (medium, deploy) The server image pins only its direct packages: `deploy/Dockerfile` installs `requirements-serve.txt` without `constraints.txt`, so starlette, anyio, h11 and the rest float to the newest at build time, and CI audits the pins rather than the image. `.github/SECURITY.md` says the image pins every package. Seen 2026-11-24 in the rebuilt image: 14 of 38 packages differ from `constraints.txt` (starlette 1.10.0 for 1.7.0, python-dateutil 4.0.0 for 2.9.0.post0, and filelock 4.2.4, older than the lock's 4.2.12, from the PyTorch index); the live checks passed on them. Fixed 2026-11-24: the image installs with `-c constraints.txt` (all 39 locked packages match) and pins pip 26.2.2.
- [ ] **BUG-10** (low, web) The page polls a job for ever when the server no longer knows it (after a restart the job route answers 404): "Working…" never ends (`web/lab.js`, `web/message.js`).
- [ ] **BUG-11** (low, tools) `python tools/repo.py ci-report` crashes with a traceback on an HTTP error from GitHub (a 504 happened on 2026-11-23).
- [ ] **BUG-12** (low, web) `web/serve.py` (local only) fails with an unhandled error on the header `Range: bytes=-`.
- [x] **BUG-13** (low, web) Job folders can be pruned out of order, once `keep_jobs` folders exist. WhistleCode (`wcode/web.py` `Jobs._prune`) sorts folders by name, and two jobs made in the same second differ only in their random suffix, so the newer one can go first (found 2026-11-24 by a new test). Try it (`server.py` `Jobs._prune`) sorts a folder whose upload is still being copied, not yet a job, as the oldest, so a job submitted meanwhile can delete it, and the upload's job then fails. Fixed 2026-11-24: both servers prune through `guard.JobFolders`, in the order the folders were made, and keep a folder that is not a job yet for 10 minutes.

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
- [ ] **WC-R3a** A lead from the 2026-11-23 audit: 2,796 of the 3,000 mixture components have fewer than 65 members (the latent size is 64), and the codebook accepts components with 32, so each symbol's samples vary in at most 31 directions, narrowed again by tau 0.5. Compare the spread of real whistles assigned to each codebook component with the spread of its samples (`project/AUDIT_2026-11-23.md`).
- [ ] **WC-R4** Baselines and listeners: matched-filter modem, listening test (needs YOU-5), whistle-against-noise classifier, likelihood under the species model, ECSM3 if its definition can be found.
- [ ] **WC-R5** In-air test between two laptops (20 messages at 2 m; also 1 m and 4 m).
- [ ] **WC-R6** Freeze, then run campaign v2 once, overnight (seed 20261205; encounter 276; encounter 308 if YOU-4).
- [ ] **WC-R7** Reframe the documents and the page:
  - new title; done 2026-11-23 (temporary name Falsetto, D-024);
  - README leads with WhistleCode; done 2026-11-23;
  - page story Listen → Learn → Speak → Hide → Hear;
  - correct `TEST_PROTOCOL.md`'s outdated "epoch 150 was not completed"; done 2026-11-26;
  - reconcile the data-whistle share (one in four vs a third); done 2026-11-26 (one in four can carry data, about a third of a played message does).
- [ ] **WC-R7a** Claim wording from the 2026-11-23 audit (`project/AUDIT_2026-11-23.md`), each as a dated revision, not an edited row:
  - C4 "never accepts a false message": state what was measured (0 in 7,900; 95 % bounds 0.08 % and 0.6 %) and the design's worst case, up to 384 CRC-16 checks per decode, about 0.6 % per decode of noise;
  - `THREAT_MODEL.md` "What may be said today": the timing passes only on its own, not inside sea noise (C6 failed);
  - README "a fresh sample ... no shape repeats exactly": the samples are tempered (tau 0.5), and a whistle that fails its self-check falls back to its type's mean shape.
- [ ] **WC-R8** Write-up and review slides.

### Detector paper

- [ ] **DET-1** Bring `mod_detector_5_24/TODO.md` (last changed 31 Oct) up to date with the draft. The draft reports a Silbido comparison on 12 DCLDE 2011 recordings and a false-alarm test on 145.5 min of whistle-free recordings.
- [ ] **DET-2** Copy the DCLDE 2011 score files from Google Drive into `mod_detector_5_24/results/` and commit them.
- [ ] **DET-3** Real-data test of the 2-24 kHz detector on hand-labelled 2017 recordings (from `TODO.md`; needs a labeller and a tool).
- [ ] **DET-4** Act on the mentor's review of the draft, when it arrives.

### Whistle model

- [x] **REP-1** Optional: paper evaluation (Tables 1, 3, 6; Figs. 7-10, 12) for the epoch-150 model, in its own folder so model 1 is untouched. Done 2026-11-27 (EXP-025).

### Web page and deployment

- [ ] **WEB-1** Re-run `python whistle.py export-web`. The static examples in `web/data/` date from 24 Oct, before any model existed.
- [ ] **WEB-2** Replace the film's hand-made research illustration (Listen → Learn → Imagine) with real model output. This is the page's Phase 4; it overlaps WC-R7.
- [x] **WEB-3** Decide what to do with the untracked `cluster/` kit (running the demo on the college cluster): commit it, or ignore it. Decided: commit it (D-021).
- [ ] **WEB-4** From the 2026-11-23 audit: hide Try it's `/api/docs` and `/api/openapi.json` on the public page, and list every route (with `/api/reload-model`) in `docs/ARCHITECTURE.md` and the exposure table of `.github/SECURITY.md`; point model 1 at `final.pt` instead of `last.pt` (byte-identical today) in `configs/inference.toml`, so a resume in that folder cannot change Nyx.
- [x] **WEB-5** Retell the page as Falsetto, after the v1.0.0 freeze, following `web/PLAN.md`. The film becomes Listen → Learn → Speak → Hide → Hear, built from real data exported by a new `export-film` and drawn as one 3D scene in WebGL (all 63,490 whistles in Learn); Encode and Decode follow the film directly; Try it moves to its own `model.html`; the footer states the limits. This carries out WC-R7's page story and includes WEB-2. Needs first: the data-whistle share settled (WC-R7). Phases P1-P6, about 7½ days. Ships as v1.1.0. Progress 2026-11-26: started on the branch `web-retelling`; P1-P5 done and deployed to the public page from the branch (2026-11-26, P6); left: merge after the v1.0.0 freeze, release v1.1.0, deploy the tag; frame times on a visible screen. Done 2026-11-26: P1-P6 on the branch, merged into `main` (`f5b794e`); in v1.0.0. Open: frame times on a visible 240 Hz screen.
- [x] **WEB-6** Redraw the film's 3D scene, following `web/PLAN-SCENE.md` (D-026): deep-water light, glow, lit surfaces, ribbons, one spline camera; full quality on the RTX 5060, stepping down by itself on weaker chips. On the branch `web-scene-v2`. Steps S1 (style frame: the drawing and Listen, for your approval), S2 Learn and Speak, S3 Hide and Hear, S4 camera and labels, S5 checks, S6 records. Merges before the v1.0.0 freeze only if S5 passes by 28 Nov. Progress 2026-11-26: S1 built (the drawing and Listen); waiting for your approval of its screenshots. Revised 2026-11-26 (D-027): you rejected the first style frame; the look is now fine lines over the page's own water; the second S1 waits for your approval. 2026-11-27: S1 approved, S2 done (Learn and Speak bolder, no new design), S3 and S4 dropped at your request (Hide and Hear, and the camera, stay as WEB-5); left: S5 checks and the commit. Done 2026-11-27: S5 checks passed and records written; the commit and the merge into `main` are YOU-15.

### Repository housekeeping

- [x] **OPS-1** Decide which untracked files in `docs/` go into git: the week 1-2 notes, the training-plan PDF, the review slides, and the detector draft. Decided: all but the draft, in `docs/course/` (D-020).
- [x] **OPS-2** Keep `docs/Whistle extraction.pdf` out of git: it is a published Elsevier paper, and the repository is public. Now in the ignored `docs/private/`.
- [x] **OPS-3** Engineering systems for a one-owner, one-engineer team (`project/README.md`).
- [x] **OPS-4** Read the first CI run on GitHub (after YOU-7) and fix anything that fails only on Linux. CI has not run yet; the tests were simulated locally on a git-only copy. First run read 2026-11-22: lint, secrets, links, checksums, configs and the reproduction suite passed; the WhistleCode suite failed (BUG-1); the audit flagged eight packages (OPS-7). Tick when a run is green. Green since run 44937841060.
- [ ] **OPS-5** Copy the records behind three reported results into git (`whistlecode/paper/records/`): EXP-015 (normal conditions), EXP-019 (SNR gap), EXP-020 (R2). Today they exist only in `whistlecode/outputs/` (`project/TRACEABILITY.md`, "Gap").
- [ ] **OPS-6** Confirm the reuse terms of the two NOAA files in `metadata/` (`DCLDE2020_DetectionData.xlsx`, `Dataset_DCLDE_Oahu.pdf`) and note them in `project/LICENSING.md`.
- [x] **OPS-7** Upgrade the eight pinned packages with published advisories (OSV, 2026-11-22) to the versions that fix them: anyio 4.14.2, certifi 2026.10.18, cryptography 49.0.0, filelock 4.2.1, fsspec 2026.6.0, pillow 13.0.0, pytest 9.0.3, setuptools 84.1.0. Needs your OK to download them. Then `python tools/repo.py lock`, `check`, update `deploy/requirements-serve.txt` and redeploy. Pillow 13 is a major version: check the page's pictures. Done 2026-11-22 (your OK); the redeploy is YOU-10.

- [x] **OPS-8** README audit and fixes: the facts checked out, but the presentation read as a product launch by an anonymous account (no author or "unofficial" line, "covert" in the tagline, highlights that picked the best numbers, many brand names, decoration badges). Fix every README except `mod_detector_5_24/`.
- [ ] **OPS-9** After YOU-11: add the release download (files and SHA-256) to the README's "What runs from a clone" table and to `project/MODELS.md`.
- [ ] **OPS-10** Say in `project/MODELS.md` and `project/TRACEABILITY.md` which records were made from uncommitted code (`git_uncommitted_code_changes: true`): the epoch-101 mixture every WhistleCode result uses, both `component_features.json`, Table 6 and its warm supplement, the reg10x fit, 14 of 19 gate records. Optionally refit the epoch-101 mixture from a clean commit into a new folder and compare its SHA-256 with `d8087ed2…` (refits are bit-identical).
- [ ] **OPS-11** Tests for the untested modules: `whistlecode/wcode/baseline.py` (behind claim C9), `src/whistlepipe/webexport.py`, `ratecheck.py`, `vaegmm/gates.py`.
- [ ] **OPS-12** Small fixes from the audit: `CITATION.cff` keyword "covert communication"; `CHANGELOG.md` compare links (`[0.10.0]` before its tag exists, `[0.9.0]` missing); the byte-order mark at the start of `whistlecode/wcode/receiver.py`; the local Windows path in `docs/course/Notes-W-4.md`; format v2 values unchecked by `wcode/config.py validate()`; `release-check` cannot tag a given commit; ruff pinned at 0.3.5 (March 2024).
- [ ] **OPS-13** WhistleCode's sender and receiver must draw the same slot positions and pitches from NumPy's `Generator` (`wcode/keys.py stream`, `layout.py`), whose output NumPy does not promise to keep across versions, and nothing checks the NumPy version. Record it with the codebook and refuse a mismatch, or derive the draws from SHA-256 as the scrambler does (a format change: after campaign v2).

## Decided not to do

| What | Decided | Why |
|---|---|---|
| Fig. 11 and Tables 2, 4, 5 of the paper | 2026-11-09 | No GMM fits at other K; the FID and precision/recall weights download was declined |
| Review-I enhancements 01-03 (realism loss, learned conditioning, three-axis evaluation) | Mid-Nov | Superseded, first by WhistleFlow, then by WhistleCode |
| WhistleFlow (audio-native model) | 2026-11-17 | Replaced by WhistleCode; folder removed 2026-11-20 |
| Real recorded shapes as WhistleCode's voice | 2026-11-19 | VAE shapes are final |

## Done

Newest first. Older history is grouped by stage. Commit hashes are given where the work was committed; an entry's own commit is the one that adds it.

### 2026-11-27

- **Whistle model (REP-1 done, EXP-025)**: the paper evaluation run on the epoch-150 checkpoint (Delphi) only, at your request; nothing was rerun on epoch 101. `vae-eval recon`, `conditional`, `figures` and `cost` with `--experiment V1_L64_b1e-4_critic_E191_epoch150`, then `table6_warm.py` and `compare_paper.py` with `--run-id` (about 15 minutes on the RTX 5060). Table 1: MSE 5.42, PSNR 34.81 dB, SSIM 0.9934, KL 757.7 against the paper's 0.578 / 44.53 / 0.9861 / 43.19, so only SSIM is reproduced; Table 3: recall 84.7-96.9 %, precision 74.5-79.7 %, F1 79.3-85.8 % (paper F1 90.1-94.4 %); Fig. 12 diagonal is the row minimum in 13 of 13 rows; decoder 368,097 parameters, 557.3 MFLOPs; warm B = 16 0.114 ms per image (paper 0.11). New: `models/vaegmm/V1_L64_b1e-4_critic_E191_epoch150/eval/`, `.../figures/`, `post_training/out/paper_comparison_V1_L64_b1e-4_critic_E191_epoch150.csv`, `post_training/out/table6_warm_V1_L64_b1e-4_critic_E191_epoch150.json`.
- **Whistle model (scripts)**: `post_training/compare_paper.py` and `post_training/table6_warm.py` take `--run-id` [DECISION: outputs for another run are named after it, as `gmm_check.py` does, so epoch 101's files stay as they are]; `table6_warm.py` now refuses to overwrite an earlier result. `compare_paper.py` without options rewrites epoch 101's CSV byte for byte.
- **Records (REP-1)**: `project/EXPERIMENTS.md` (EXP-025 moved from Planned and filled in), `project/TRACEABILITY.md` (R-08 and four Delphi rows), `project/MODELS.md`, `docs/TECHNICAL_REFERENCE.md` (an epoch-150 evaluation record, commands), `README.md` (status row, one epoch-150 paragraph, the limitation line; the headline tables stay on epoch 101 per D-007 [DECISION]), `CHANGELOG.md` [Unreleased].
- **Repository (WEB-6 merged)**: you committed WEB-6 on `web-scene-v2` (`0abb2b3`, 19 files), merged it into `main` (`9f91c3b`) and pushed; YOU-15 ticked. The live page (Docker, serving this folder) serves it: `/healthz` ok, Try it at `#try`, the new scene, `model.html` leading to `#try`. CI run 45907128190 on `9f91c3b` started; its result is not yet in. Records: `project/RELEASES.md` (what is live), D-027 and D-028 status in `project/DECISIONS.md`, `web/PLAN-SCENE.md` status, `docs/INDEX.md` row.
- **Web (WEB-6, Hide and Hear left as they are)**: you chose to leave Hide and Hear as in WEB-5, so step S3 is dropped. Step S4 (smoothing the camera between beats) is left out too: you asked for small changes only, and the camera keeps its WEB-5 moves apart from Listen's new opening. Recorded in `web/PLAN-SCENE.md` (steps table and "Progress") and a dated update on D-027 in `project/DECISIONS.md`. Next: the checks (S5), then the commit.
- **Web (WEB-6 done)**: `python tools/repo.py check` passes (lint, configs, secrets, links, checksums, both test suites); the Definition of Done walked (no page test suite exists: the page was checked in Chrome and Edge, see S5). WEB-6 ticked; the commit and the merge into `main` are YOU-15. `web/gl.js` header comment updated.
- **Web (WEB-6 S5, checks)**: in headless Chrome and Edge on the RTX 5060 against `whistlecode serve`: the whole page without errors; WebGL off, a lost context and reduced motion all fall back as designed; Edge draws the film and Try it. Review of the diff found one fault, fixed in `web/scene.js`: the new label style turned the key in Hear into capitals ("REEF-42"); the key keeps its case now. Also: the scene's header comment updated, an unused class removed from `web/index.html`, Listen's two labels traced in `project/TRACEABILITY.md`, results in `web/PLAN-SCENE.md` "Progress".

### 2026-11-26

- **Web (WEB-6 S2, Learn and Speak bolder)**: at your request no new design for Learn and Speak, only more boldness. `web/scene.js`: Learn's points crisp, larger and stronger, drawn over the water so crowded parts keep their colour, fading with distance; the followed whistle stays marked in amber until Speak. Speak's 64 strokes solid and twice as thick, the followed one amber; the cloud dims behind the lattice; "Hear it" an amber dot; labels without arrows. `web/gl.js`: multisampling off (every line and point smooths its own edge; it cost the Radeon 7 ms a frame in Learn). GPU time at 2560 × 1600: Radeon 610M at most 2.4 ms median (Learn's 95th percentile 5.6 ms), RTX 5060 under 1 ms. Recorded in `web/PLAN-SCENE.md` "Progress", a dated update on D-027 and `CHANGELOG.md`. Not committed.
- **Web (WEB-6 S1 approved)**: you approved the second Listen style frame (fine lines on the page's blue). Recorded in D-027 and `web/PLAN-SCENE.md` "Progress". Next: S2, Learn and Speak.
- **Web (Try it back on the page, D-028)**: at your request, Try it with its Nyx / Delphi selector is back on the film's page, as 08 after Decode, with a header link "Try it"; nothing before it changed. `web/index.html` (the section, from `model.html`'s markup, unchanged but for its number; the header link; `lab.js` loaded; the footer's `model.html` link replaced by Try it's image note; the lab's aria-label), `web/message.js` (the index marks and glides to Try it like Encode and Decode), `web/lab.js` (header comment), `web/model.html` (now a redirect to `./#try`), `web/styles.css` (the `model.html`-only rules removed). Docs updated: `README.md`, `web/README.md`, `deploy/README.md`, `docs/ARCHITECTURE.md`, `docs/INDEX.md`, `docs/TECHNICAL_REFERENCE.md`, `whistlecode/whistlecode.py` help text; D-028 in `project/DECISIONS.md` (D-025 superseded in part); `CHANGELOG.md`. Checked with `whistlecode serve` in the in-app browser: the link lands on Try it and is marked; Nyx and Delphi offered; Nyx analysed the encounter-191 example (30 whistles); Delphi imagined 2 whistles; `/model.html` lands on `#try`; no console errors. Not committed.
- **Web (WEB-6, direction revised)**: you rejected the first style frame (dark water, glow, the translucent sheet) as childish and unprofessional and asked for the old theme, minimal and sophisticated. Recorded as D-027 in `project/DECISIONS.md` (D-026's look superseded; its index row says so). `web/PLAN-SCENE.md` rewritten for the new direction, with a plan for every beat; the first style frame stays in its "Progress". `docs/INDEX.md` row and `CHANGELOG.md` [Unreleased] line updated.
- **Web (WEB-6 S1, second style frame)**: `web/gl.js` and `web/scene.js` rebuilt from the WEB-5 versions. `gl.js` gains `Lines` (fine lines drawn over the water) and `GpuTimer`, the browser's anti-aliasing and the high-performance request; the bloom pipeline is gone. Listen: a dotted floor of the image's pixel grid, the contour's trace, 27 hairlines (one per frame) and the contour as an amber line along their tops, then one line from above; labels in the page's style; the "loudness" label removed, because the training image's height is not loudness. GPU time at 2560 × 1600: 0.05 ms a frame on the RTX 5060, 0.1 ms on the Radeon 610M. Learn to Hear unchanged. Not committed; waiting for your approval.
- **Web (WEB-6 plan)**: you judged the film's 3D scene odd and unprofessional and approved a redraw: `web/PLAN-SCENE.md` (new; listed in `docs/INDEX.md`), decision D-026 in `project/DECISIONS.md` (index row, entry, 4 inline tags in the tag table), to-do WEB-6. Work on the new branch `web-scene-v2`; `main` untouched.
- **Web (graphics chip)**: you asked for the RTX 5060. Measured: Chrome on Windows gives WebGL the Radeon 610M whatever the page asks (`powerPreference` default, low-power and high-performance all gave the Radeon); launched with `--force_high_performance_gpu` it gives the RTX 5060. A page cannot choose; the chip is set per browser in Windows. The scene now asks for `high-performance` anyway (`web/gl.js`).
- **Web (WEB-6 S1, style frame)**: `web/gl.js` gains the new picture (`Frame`: high-range multisampled buffer, bloom, tone mapping, the water behind, vignette, grain), smooth ribbons (`Ribbons`), quality steps and a GPU timer. `web/scene.js`: Listen redrawn as a sheet of light on a dark glass floor with its reflection, an amber contour ribbon that draws itself, new labels, a three-quarter camera; drifting particles in the water; Learn to Hear unchanged in drawing, now over the new water. GPU time at 2560 × 1600: RTX 5060 about 1 ms a frame at full quality; Radeon 610M 9-10 ms at the step it starts on, 2.8 ms once the canvas resolution is halved (planned for S5). Details in `web/PLAN-SCENE.md` "Progress"; `CHANGELOG.md` [Unreleased]. Not committed; waiting for your approval of the look.
- **Web (plan)**: the page reviewed as Falsetto. The message system sits at the bottom; the header mark still reads "Whistle VAE-GMM"; the research beats and Try it tell the whistle model's story; the page never states its limits. Plan for the full retelling written: `web/PLAN.md` (new; listed in `docs/INDEX.md`); to-do WEB-5. No page file changed.
- **Web (plan)**: `web/PLAN.md` gains "The 3D scene". The research beats are drawn with WebGL 2, hand-written with no library, so Learn shows all 63,490 whistles (exported as `learn.bin`). Plus fallbacks for reduced motion and missing WebGL, and checks for them. No computer-made whales and no pre-rendered video. P3 grows to 4 days; WEB-5 is now about 7½ days.
- **Web (plan) approved**: you approved `web/PLAN.md`. Its main choices are recorded as D-025 in `project/DECISIONS.md` (index row, entry, and the plan's 14 inline tags in the tag table). The plan's status line is now "approved"; so is its row in `docs/INDEX.md`. Work starts after the v1.0.0 freeze.
- **WhistleCode docs (WC-R7)**: the data-whistle share reconciled. One in four bank whistles *can* carry data (19,432 of 73,791). The sender uses every eligible whistle its spacing allows, so about a third of a played message *does* (33-36 % in `RESULTS.md` section 6). `whistlecode/paper/TEST_PROTOCOL.md` gets dated corrections of that row and of its outdated "epoch 150 was not completed"; `whistlecode/RELATED_WORK.md` gets a dated reconciliation note; `docs/INDEX.md` lists the protocol as current.
- **Web (WEB-5 started)**: at your request the retelling started before the freeze, on the new branch `web-retelling`, so `main` stays ready to freeze as v1.0.0. The branch merges after the freeze; whether its structure phase (P2) goes into v1.0.0 is your call at the freeze.
- **WhistleCode (WEB-5 P1)**: new `export-film` writes the page film's data from real records to `web/film/`, about 600 KB, in git:
  - New code: `whistlecode/wcode/film.py`, the `[film]` section of `whistlecode/config.toml`, the command in `whistlecode/whistlecode.py`, `.gitignore` letting `web/film/*.wav` through, and `.gitattributes` marking `web/film/*.bin` and `*.wav` binary.
  - Sender: `whistlecode/wcode/sender.py` now records each cover whistle as played and the click times (`Transmission.covers`, `clicks_s`). The audio is unchanged.
  - Tests: new `whistlecode/tests/test_wc_film.py` (8 tests), and one new test in `test_wc_pipeline.py`.
  - Export result: seed 0 decoded "MEET AT DAWN" exactly in encounter-214 noise at 10 dB, with 1 wrong whistle repaired. 31 data and 51 cover whistles (38 % data). All 63,490 latents, with 60 % of their variance on three axes.
- **Web (WEB-5 P2)**: the page restructured, then checked in the browser on `whistlecode serve`:
  - `web/index.html` (title, header, opening question, last line of the film, the lab opening on 04 · Encode, footer with the limits and a link to the model page);
  - new `web/model.html` (Try it);
  - new `web/water.js` (tide and sea moved out of `web/lab.js`);
  - `web/app.js` and `web/message.js` (the `#lab` anchor, header marking);
  - `web/styles.css`.
  - Records: `web/README.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/TECHNICAL_REFERENCE.md`, `docs/INDEX.md`, `deploy/README.md`, `deploy/docker-compose.yml` (comment), `project/TRACEABILITY.md` (where the page states C7 and C10), `CHANGELOG.md` `[Unreleased]`, `web/PLAN.md` (Progress).
  - Stale section numbers removed from comments in `whistlecode/wcode/web.py`, `whistlecode/tests/test_wc_web.py`, `whistlecode/config.toml` and `web/message.js`.
- **Web (WEB-5 P3)**: the film's research section is one WebGL 2 scene, drawn only from `web/film/`:
  - Code: new `web/gl.js`; `web/scene.js` rewritten (five beats: Listen, Learn, Speak, Hide, Hear); `web/shots.js` (timings, 6 screens, header stops); `web/index.html` (five beats and their words, header links, the `#gl` canvas, numbering 06 · Encode and 07 · Decode); `web/app.js` ("Hear it" plays `film/hear_it.wav`, the scene's readiness and both canvases); `web/styles.css`; `web/audio-engine.js` removed.
  - Checked in the in-app browser on the Radeon 610M: every beat by screenshot; the scene costs a median 0.8 ms per frame, 1.9 ms at the 95th percentile, at 3840 × 2400; the fallbacks for a lost context, no WebGL 2 and reduced motion; "Hear it"; the header links. Details in `web/PLAN.md` (Progress).
  - Records: `web/PLAN.md`, `web/README.md`, `web/CREDITS.md` (the film's sound is now a real data whistle), `docs/ARCHITECTURE.md`, `project/TRACEABILITY.md` (every number and claim in the film's words, with its record), `CHANGELOG.md`.
- **Repository (WEB-5 merged)**: you merged `web-retelling` into `main` (`f5b794e`) before the freeze and deleted the branch. The retold page is part of v1.0.0, and the live page runs from `main`. Records: `project/DECISIONS.md` (D-025 status and update), `project/RELEASES.md` (what is live, version plan), `web/PLAN.md`, `web/README.md`, `README.md`, `docs/INDEX.md`, `CHANGELOG.md`; WEB-5 ticked.
- **Deploy (WEB-5 P6)**: with your go-ahead, the retold page is live: `docker compose -f deploy/docker-compose.yml up -d --build` from the branch `web-retelling` at `e983ad4`. The full check and checksums passed; the app was healthy in 14 s; `repo.py health` was UP at v0.10.0 over Funnel; the public page loads its 720p videos and the film's data with no console errors; Try it found 30 whistles in an example; Encode and Decode round-tripped "HI". Untagged by exception (D-025 update), because v1.1.0 follows the v1.0.0 freeze. Records: `project/RELEASES.md` (What is live), `project/DECISIONS.md`, `web/PLAN.md`. Note: the container serves the checked-out tree, so switching to `main` puts the old page back.
- **Web (WEB-5 P4 and P5)**:
  - P4: the words of `web/index.html` were checked against the records and corrected where they said more (Speak, Hide, Learn, Listen); `project/TRACEABILITY.md` and `CHANGELOG.md` follow.
  - P5: headless Chrome and Edge on the Radeon 610M; Edge, no WebGL, no server, reduced motion, the message server with a send and decode round trip, and frame times alternated against `main`. Results and what is still open are in `web/PLAN.md` (Progress). No code changed.

### 2026-11-25

- **Detector 5-24 kHz**: full 5-24 kHz detector added from the RidgeTrace v1 repository: `mod_detector_5_24/` (DCLDE 2011 benchmark, no-whistle and false-alarm tests, Silbido scripts and detections, tools, guides), `results/` (DCLDE 2011 detections and scores, no-whistle, false alarms, Silbido thresholds and pictures), `docs/whistle_detector_guide.md` and two detector figures. Paper files left out. Lint fixes by `ruff --fix`; 4 `noqa` for intended loop lambdas and unused loop names.

### 2026-11-24

- **Deployment (BUG-9)**: the server image installs every package at its locked version, and the page runs on it.
  - `deploy/Dockerfile`: pip 26.2.2 first (the base image's 24.0 has 12 advisories, OSV); PyTorch with `--no-deps` from its index; then `requirements-serve.txt` with `-c constraints.txt`, naming torch (for its dependencies) and setuptools (from the base image), and `pip check`. The build context is now the repository (`deploy/docker-compose.yml` and `docker-compose.gpu.yml`: `context: ..`, `dockerfile: deploy/Dockerfile`); new `deploy/Dockerfile.dockerignore` lets in only `constraints.txt` and `deploy/requirements-serve.txt` (context 2.27 kB).
  - New `tests/test_deploy.py` (2 tests): the server pins agree with the lock; the Dockerfile's torch pin is the lock's, it installs with the lock, pins pip, and copies exactly what the ignore file lets in.
  - Rebuilt and redeployed: all 39 locked packages in the image match `constraints.txt` (before: 14 of 38 differed, and setuptools was 79.0.1); pip 26.2.2 and wheel 0.46.3 have no advisory. The live checks of the earlier deployment passed again (limits, reload 403, Encode and Decode "HI", Try it, page without console errors), and the public address is UP with v0.10.0. The CUDA image (`docker-compose.gpu.yml`) was not rebuilt: its build is unverified.
  - Docs: `.github/SECURITY.md` (Dependencies), `deploy/README.md`, `project/ENGINEERING.md`, `project/RELEASES.md` (checklist, What is live), `CHANGELOG.md`.
  - The `RUN` line's continuations were restored after the build; the rebuild was all cached, and the app was recreated on that image (`7d2f5b4d1cae`), healthy, with Decode, Try it and the public address checked again.
- **Release v0.10.0 (YOU-10)**: you tagged `9697663` as v0.10.0 and pushed it; CI run 45323960151 on the tag is green (lint, secrets, links, checksums, tests, dependency audit).

- **Deployment (YOU-10, rebuild)**: the server image rebuilt (`docker compose -f deploy/docker-compose.yml up -d --build`) and the page redeployed at `1613c18` (v0.10.0 plus the [Unreleased] fixes), following the checklist in `project/RELEASES.md`.
  - Before: `python tools/repo.py release-check 0.10.0` passed (release, lint, config, secrets, links, 28 checksums, 212 + 272 tests).
  - After: the app is healthy; `repo.py health` is UP with v0.10.0 on localhost and on the public Funnel address. Live checks: request bodies over 64 kB refused with 413 (with a length, and chunked without one), a 300 MB upload refused on its announced length, `reload-model` 403; Encode "HI" decoded back as "HI" (a wrong key reads nothing), with the text null in the job's `result.json` on disk, served with `no-store`, and the upload deleted; Try it's example (model1, GMM samples) and generation ran and drew their figures; the page loads with no console errors and its three film videos ready.
  - The image runs Pillow 13.0.0, but 14 of its 38 packages differ from `constraints.txt` (BUG-9; note added there and in `.github/SECURITY.md`).
  - Docs: `project/RELEASES.md` (What is live), `.github/SECURITY.md` (Dependencies). Tagging v0.10.0 and pushing stay with you (YOU-10).

- **Web (BUG-13)**: job folders are pruned in the order they were made, and never while their upload is still arriving. Tests run on the project laptop.
  - New `JobFolders` in `src/whistlepipe/guard.py`: makes job folders, noting the order; prunes the oldest beyond `keep_jobs` (earlier runs' folders first, by the time in their names, then this run's in the order made); keeps queued and running jobs, and a folder that is not a job yet for `grace_s` (600 s) [DECISION], after which a failed request's leftover folder goes like any other. Both `Jobs` classes (`whistlecode/wcode/web.py`, `src/whistlepipe/server.py`) use it; `whistlecode/wcode/repro.py` re-exports it.
  - Tests: `tests/test_guard.py` (2 new: same-second order, folders still needed), `tests/test_server.py` (an arriving upload's folder survives five jobs), `whistlecode/tests/test_wc_web.py` (the oldest of three same-second jobs goes first).
  - Docs: `docs/ARCHITECTURE.md` (guard.py row), `CHANGELOG.md` (Unreleased, Fixed).
- **Web (BUG-6, BUG-7)**: the last two public-page bugs from the audit. Tests run on the project laptop.
  - BUG-6: `whistlecode/wcode/web.py` `Jobs` writes a decode job's message fields (`MEMORY_ONLY`: `text`, `hex`) to `result.json` as null and keeps them in memory with the job (`Jobs.held`, dropped when the job is pruned); `/api/wc/files/<id>/result.json` adds them back as it serves the file, with `Cache-Control: no-store`. `web/message.js` shows "No longer held by the server" if the server restarted in between.
  - BUG-7: `whistlecode/wcode/web.py` and `src/whistlepipe/server.py` never serve `error.txt` (new `private()`, used by the file routes and the results zip); an internal error's message gives the error's type and no longer names the file.
  - Tests: `whistlecode/tests/test_wc_web.py` (message off disk, served from memory and dropped with its job; `error.txt` refused; the real-model decode leaves no text on disk), `tests/test_server.py` (`error.txt` refused by the file route and the zip).
  - New BUG-13 (job folders pruned out of order), found by the new WhistleCode test.
  - Docs: `.github/SECURITY.md` (Text and keys, Errors rows now true), `deploy/README.md`, `CHANGELOG.md` (Unreleased, Security).

### 2026-11-23

- **Web (BUG-2 to BUG-5)**: the public page's limits, from the audit. Both servers; tests run on the project laptop.
  - New `src/whistlepipe/guard.py`: `read_channel` (one channel of an audio file, read in blocks, never past a set length) and `RequestLimit` (an ASGI middleware that refuses a request body over its route's limit while it arrives, before Starlette stores it, and more than a set number of uploads arriving at once).
  - BUG-2: `src/whistlepipe/audio.py` `read_upload` and `whistlecode/wcode/web.py` `read_audio` read one channel through `read_channel`, and refuse rates above `max_sample_rate_hz` (768 kHz, `configs/inference.toml` `[input]`) or `max_rate_hz` (192 kHz, `whistlecode/config.toml` `[web]`) and more than 8 channels.
  - BUG-3: `src/whistlepipe/server.py` clamps `n_samples` to 0-2 x the default on `/api/analyze-example` as on `/api/analyze`; `infer.py` `Engine.analyze` treats a negative value as 0.
  - BUG-4: both servers add `RequestLimit` (uploads up to `max_upload_mb`, other bodies up to `max_request_kb` = 64, `max_uploads_at_once` = 2) and refuse a new job while `max_queued` = 6 wait (503, `Jobs.room`); a job's `input.*` file is deleted when it ends. New settings in `[server]` of `configs/inference.toml` and `[web]` of `whistlecode/config.toml`; `whistlecode/wcode/repro.py` re-exports the guard.
  - BUG-5: `POST /api/reload-model` answers 403 unless `[server] allow_reload = true` (default false).
  - Tests: new `tests/test_guard.py` (4); `tests/test_server.py` (limits, reload switch), `tests/test_infer.py` (rate and channel caps), `whistlecode/tests/test_wc_web.py` (caps, full queue, oversized requests, input deleted).
  - Docs: `.github/SECURITY.md` (exposure table; BUG-6 and BUG-7 marked as not yet true), `docs/ARCHITECTURE.md`, `deploy/README.md`, `web/README.md`, `docs/TECHNICAL_REFERENCE.md`, `CHANGELOG.md` (Unreleased, Security). `whistlecode/config.toml` has a new SHA-256, so campaign v1's frozen run would no longer resume (it is complete; campaign v2 freezes its own).
- **Repository (audit)**: review of the whole project at `d00bde5`, with no code changed. Report: new `project/AUDIT_2026-11-23.md`.
  - **Checked:** `tools/repo.py check` (lint, configs, secrets, 311 links, 28 checksums, 202 + 269 tests) and CI run 45214754247, all green; the web servers, inference, the message format and receiver, tools, CI, hook and Docker files read in full; the rest searched for unsafe patterns; Tables 1, 3, 6, both mixture fits, dataset sums and the campaign statistics checked against their records (all match); every commit and file hash quoted in the documents verified.
  - **Found:** BUG-2 to BUG-12 (three high: the public page can be made to run out of memory, compute or disk; two statements in `.github/SECURITY.md` are not true of the code); claim wording for WC-R7a; a lead for WC-R3 (WC-R3a); WEB-4; OPS-10 to OPS-13; a tagging note on YOU-10.
  - Registers: this file (bugs, items, "At a glance"), `docs/INDEX.md` (the report).
- **Docs (WC-R7, first part; D-024)**: the repository no longer presents itself as a reproduction of Park et al. The project is the message system, under the temporary name Falsetto.
  - `README.md`: leads with the message system (what it does, delivery and covertness results beside their pass marks, what is new with the incomplete-search caveat, limitations); the VAE-GMM is "the whistle model", checked against the paper. No numbers changed.
  - `CITATION.cff` (title, abstract; Park et al. moved from preferred-citation to references), `pyproject.toml` (name, description), `NOTICE`, `web/index.html` (title, description, footer), `web/CREDITS.md`, `docs/ARCHITECTURE.md`, `docs/TECHNICAL_REFERENCE.md`, `docs/INDEX.md`, CI step names (`.github/workflows/ci.yml`, `tools/repo.py`), `whistlecode/PLAN.md` (one term).
  - Registers: `project/DECISIONS.md` (D-013 decided, D-024), `project/TRACEABILITY.md` (C14), `project/ENGINEERING.md`, `project/EXPERIMENTS.md`, `project/LICENSING.md`, `project/WORKFLOW.md`, `CHANGELOG.md`; area headings here renamed. New owner item YOU-14 (final name, repository rename). Code, `whistlecode/` documents and frozen records keep their old terms.
- **Docs (OPS-8)**: README audit, then fixes in every README except `mod_detector_5_24/README.md`. Every number in the main README was checked against its record first (citation against the paper PDF, dataset sums, `paper_comparison.csv`, `RESULTS.md`, test counts 202 + 269, CI green); none was wrong.
  - `README.md`: new title (the repository's name) and an "independent, unofficial; not affiliated with or endorsed by the authors" line; "covert" replaced by the paper's own term, biomimetic underwater communication; "Highlights" replaced by "At a glance", which states the gaps (PSNR, KL, Table 3 precision) beside the matches; only the CI and licence badges remain; checkpoints called epoch 101 and epoch 150 (the page's names Nyx and Delphi mentioned once); status as of 23 Nov, web demo "runs locally" instead of "deployed"; MSE footnote (spec §3.7); the 7,900 false-message tries broken down; DCLDE 2011 score shown beside Li et al. 2023's best, as context; full references for Li et al. 2020 (the paper's ref. [30]) and 2023 and for refs. [31]-[33]; new "What runs from a clone" table with download sizes (68 GB for encounter 191, about 270 GB for all eight); "Not peer reviewed" limitation; new "About this project" section (course project, one maintainer, written with Claude Code at the maintainer's direction); hard-coded test counts removed.
  - `CITATION.cff`: abstract added (unofficial, course project); keyword "covert underwater communication" is now "biomimetic underwater communication".
  - `project/README.md`: "Two people run it" replaced by one maintainer working with an AI assistant (Claude Code); title "How the project is run".
  - `web/README.md`, `deploy/README.md`: written for "your computer" instead of "this laptop"; example LAN address instead of a real one; the frame-time note says what machine it was measured on.
  - `cluster/node/README_CLUSTER.md`: framed as a course-lab exercise on the college's teaching cluster; the lab's IP addresses and the "sample" anecdotes removed. It stays in `cluster/node/` because `make_cluster_bundle.py` packs it into `whistle_app.zip`.
  - Registers: `docs/INDEX.md` (three descriptions), `project/TRACEABILITY.md` (DCLDE 2011 score, Li et al. baseline, download sizes), `project/DECISIONS.md` (D-023), `CHANGELOG.md`. New owner items YOU-11 (release the GMMs and codebook), YOU-12 (course material rights), YOU-13 (optional name); follow-up OPS-9.

### 2026-11-22

- **Security**: the eight packages with published advisories upgraded on the project laptop (OPS-7, with your OK): anyio 4.16.0, certifi 2026.11.20, cryptography 50.0.2, filelock 4.2.12, fsspec 2026.9.0, pillow 13.0.0, pytest 9.2.0, setuptools 84.2.1 (and typing-extensions 4.16.0, pygments 2.20.0 with them).
  - `constraints.txt` rewritten (57 packages); `deploy/requirements-serve.txt` pins pillow 13.0.0. All 57 pins re-checked against OSV: no advisories.
  - pytest 9 broke collection through an old `pytest-asyncio` that another project installed in the shared Python; `pyproject.toml` now blocks that plugin (`-p no:asyncio`). Both suites pass on the new versions (202 + 269).
  - Pillow 13 still accepts `Image.fromarray(..., mode="L")` without a warning and gives identical images, so no code changed.
  - `tools/repo.py audit-report` merges a package listed in both pinned files and repeated advisory IDs.
  - Outside this project: `pytest-asyncio` 0.23.5 in the shared Python now conflicts with pytest 9 (`pip check`); whichever project uses it needs a pytest-asyncio release that supports pytest 9, or its own environment.
- **Release**: 0.10.0 prepared (`CHANGELOG.md`, `pyproject.toml`, `CITATION.cff`, `README.md` badge, `project/RELEASES.md`); tagging and the server rebuild are YOU-10. Docs: `.github/SECURITY.md` (audit state), `project/ENGINEERING.md` (57 packages, plugin rule).
- **CI**: the first run after the fix is green (run 44937841060, `81162fe`); BUG-1 and OPS-4 closed.
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
