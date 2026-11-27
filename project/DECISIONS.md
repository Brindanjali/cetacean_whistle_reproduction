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
| [D-006](#d-006) | 2026-11-09 | Fig. 11 and Tables 2, 4, 5 are not computed | in force for Tables 4, 5; superseded for Delphi at K = 3,000 by D-029 (Fig. 11) and D-030 (Table 2), and for Table 4's supplementary row by D-031 |
| [D-007](#d-007) | 2026-11-20 | Epoch 101 (Nyx) stays the final model; epoch 150 (Delphi) is a second model | in force |
| [D-008](#d-008) | 2026-10-28 | Gate G4 accepted without a longer run | in force |
| [D-009](#d-009) | 2026-11-21 | Data splits: 191 trains, 214 develops, 276 tests | in force |
| [D-010](#d-010) | 2026-11-20 | Pass marks are frozen before the runs; failures are reported as measured | in force |
| [D-011](#d-011) | 2026-11-19 | VAE shapes are WhistleCode's final voice | in force |
| [D-012](#d-012) | 2026-11-21 | Doppler and clock-drift correction adopted | in force |
| [D-013](#d-013) | 2026-11-21 | Present the project as covert biomimetic communication | in force (owner, 2026-11-23); mentor still to be told (YOU-1) |
| [D-014](#d-014) | 2026-11-20 | Self-host the page with Docker and Tailscale Funnel | in force |
| [D-015](#d-015) | 2026-10-23 | The page is desktop-only | in force |
| [D-016](#d-016) | 2026-11-21 | Lint with ruff; no auto-formatter | in force |
| [D-017](#d-017) | 2026-11-21 | Engineering systems as plain files in the repository | in force |
| [D-018](#d-018) | 2026-11-21 | Top-level folders stay where they are; only `docs/` is reorganised | in force |
| [D-019](#d-019) | 2026-11-21 | One release version for the repository: 0.9.0 now, 1.0.0 at the freeze | in force |
| [D-020](#d-020) | 2026-11-21 | What from `docs/` goes into git | in force |
| [D-021](#d-021) | 2026-11-21 | The cluster kit goes into git | in force |
| [D-022](#d-022) | 2026-11-22 | The code is licensed under Apache 2.0 | in force |
| [D-023](#d-023) | 2026-11-23 | How the public README presents the project: unofficial, a course project, written with an AI assistant | in force; the reproduction framing replaced by D-024 |
| [D-024](#d-024) | 2026-11-23 | The project is the message system, under the temporary name Falsetto | in force |
| [D-025](#d-025) | 2026-11-26 | The page is retold as Falsetto: a real-data 3D film in WebGL, then Encode and Decode; Try it gets its own page | in force; done and merged into `main` 2026-11-26 (`f5b794e`), in v1.0.0 |
| [D-026](#d-026) | 2026-11-26 | The film's 3D scene is redrawn: deep-water light, glow, lit surfaces and ribbons; still hand-written WebGL 2, full quality on the RTX 5060 | look superseded by D-027 the same day; the redraw itself (WEB-6) stays |
| [D-027](#d-027) | 2026-11-26 | The redrawn scene keeps the page's own blue water and is drawn in fine lines: minimal, no glow | in force; merged into `main` 2026-11-27 (`9f91c3b`), in v1.0.0 |
| [D-028](#d-028) | 2026-11-26 | Try it, with its model selector (Nyx, Delphi), is back on the page as section 08, after Decode; `model.html` leads there | in force; merged into `main` 2026-11-27 (`9f91c3b`), in v1.0.0 |
| [D-029](#d-029) | 2026-11-27 | Fig. 11's clustering scores are computed for Delphi (epoch 150) at K = 3,000 only; no fits at other K | in force |
| [D-030](#d-030) | 2026-11-27 | Table 2 is computed for Delphi (epoch 150) at K = 3,000 only; the Inception-V3 and VGG-16 weights are downloaded | in force |
| [D-031](#d-031) | 2026-11-27 | Table 4's supplementary row (the β = 1e-4 VAE sampled from N(0, I)) is computed for Delphi (epoch 150) | in force |

## Whistle model

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

*Superseded in part by [D-029](#d-029)* (Fig. 11's scores at K = 3,000, for Delphi only) *and [D-030](#d-030)* (Table 2 at K = 3,000, for Delphi only).

### D-007

**Epoch 101 (Nyx) stays the final model** for the paper results and WhistleCode campaign v1. The resumed run's epoch 150 (Delphi) lives in its own folder with its own GMM and is Try it's model 2. *Why:* every result so far was made with epoch 101; replacing it would invalidate them. *Consequence:* the main run folder must not be refreshed to epoch 150 without repointing model 1. Delphi's paper evaluation is optional (REP-1), and its use as WhistleCode's voice is tested in WC-R3.

### D-008

**Gate G4 accepted without a longer run.** The overfit test reached 0.416 against a mark of ≤ 0.3 in 3,000 steps, with a steady fall that extrapolated to the mark at about 3,300-3,500 steps (not measured). *Decided by:* the owner, 2026-10-28. Records: `models/vaegmm/_gates/G4_*`.

### D-029

**Fig. 11's clustering scores are computed for Delphi (epoch 150) at K = 3,000 only.** Supersedes D-006 for that one point; Fig. 11's other K values and Tables 2, 4 and 5 stay not computed, no mixtures are fitted at other K, and Nyx gets no Fig. 11. *Decided by:* the owner, 2026-11-27: they want the epoch-150 tests only, and at K = 3,000 only. Fits at the paper's other six K were started and stopped at the owner's request (EXP-026). *Why:* the silhouette, Davies-Bouldin and Calinski-Harabasz scores at K = 3,000 need only Delphi's existing mixture. *Consequence:* Fig. 11 is one point, not a curve, so no figure is drawn; the scores are in `eval/fig11_clustering.json` and the comparison CSV.

### D-030

**Table 2 is computed for Delphi (epoch 150) at K = 3,000 only, and the feature-network weights are downloaded.** Supersedes D-006 for that one row; Table 2's other K and β rows and Tables 4 and 5 stay not computed (they need more fits or trainings), and Nyx gets no Table 2. *Decided by:* the owner, 2026-11-27: they asked for Table 2 at K = 3,000 on epoch 150 and approved the download of `inception_v3_google-0cc3c7bd.pth` (108.9 MB) and `vgg16-397923af.pth` (553.4 MB) from download.pytorch.org. *Why:* this row needs only Delphi's existing mixture and the two weight files. *Consequence:* the weights live in `models/eval_weights/` (gitignored, in the checksum registry); `fetch-eval-weights` now checks each file's SHA-256 against the prefix in its name. The paper's Table 2 has no K = 3,000 row (it has K = 1k, 5k, 10k, 15k), so the result is set beside those rows; K = 3,000 on our 63,490 images is closest to the paper's K = 10,000 in images per component (21.2 against 22.9).

### D-031

**Table 4's supplementary row, the β = 1e-4 VAE sampled from N(0, I), is computed for Delphi (epoch 150).** Supersedes D-006 for that one row. Table 4's rows 1-3 and Table 5 stay not computed (they need trainings); row 4 is the main model at K = 10,000, and at K = 3,000 it is Table 2's result (EXP-027). *Decided by:* the owner, 2026-11-27: they chose this row as the next test. *Why:* it needs no training and no fit, only Delphi's decoder, so it shows on our own model what the mixture adds over plain prior sampling. The paper's row 1 is a different model (a standard VAE, β = 1, no critic; training spec §1 item 4), so the result is set beside it, not matched to it. The spec planned this supplement on the row-3 VAE (no critic), which was never trained; Delphi has the critic, so the row is the main VAE without its mixture. *Consequence:* `.../E191_epoch150/eval/gen_prior.json`, with Table 2's generation seed, so the two rows differ only in where the latents come from.

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

**Present the project as covert biomimetic communication**, with the reproduction as its foundation. *Why:* WhistleCode is the project's own contribution. *Status:* needs the mentor's and team's agreement (YOU-1); the documents are reframed in WC-R7. *Update 2026-11-23:* decided by the owner ([D-024](#d-024)); the documents are reframed, the page's story is still to do (WC-R7).

## Page and deployment

### D-014

**Self-host the page with Docker and Tailscale Funnel.** Free, a fixed https address (which the microphone needs), and the laptop's GPU. *Alternative:* a paid cloud host. *Consequence:* the page is up only while the laptop is on (see `project/RELEASES.md`).

### D-015

**The page is designed for desktop browsers only.** Phone layouts are not built or audited.

### D-025

**The page is retold as Falsetto, following [`web/PLAN.md`](../web/PLAN.md)** (WEB-5). *Decided by:* the owner, who approved the plan on 2026-11-26. *What:*
- The film's research beats become Listen → Learn → Speak → Hide → Hear (WC-R7). They are one 3D scene drawn with WebGL 2 and no library, built only from real records that a new `export-film` command writes to `web/film/`, which is tracked in git. Learn shows all 63,490 whistles.
- Encode and Decode follow the film directly. Try it moves to its own page, `web/model.html`, which keeps the model selector.
- The header reads "Falsetto", and the footer states the limits (simulation only; the coded shapes can still be told from real ones).
- The demonstration decode uses encounter-214 noise, with a seed chosen by a rule fixed in advance. The film claims no success rate.
- The current footage stays as atmosphere; no computer-made whales and no pre-rendered video.

*Why:* the page told the whistle model's story, with the message system at the bottom (D-024). *Alternatives:*
- Only rename and reorder (the small version): the identity is fixed, but the story is not.
- Keep the 2D canvas: the cloud would be capped at about 1,500 points.
- Three.js: a dependency the scene does not need.

*Consequence:*
- WEB-2 is covered by WEB-5.
- Work starts after the v1.0.0 freeze and ships as v1.1.0.
- The data-whistle share (WC-R7) must be settled first.
- The plan's other `[DECISION]` tags stay inline in `web/PLAN.md`.

*Update 2026-11-26:* at the owner's request, the work started before the freeze, on the branch `web-retelling`. `main` stays ready to freeze as v1.0.0, and the branch merges after it. The prerequisite is met: the data-whistle share is reconciled (WC-R7).

*Update 2026-11-26 (P6):* the owner approved deploying the retold page before its release. It is live from the branch `web-retelling` (`e983ad4`), untagged and still numbered 0.10.0, because v1.1.0 can only follow the v1.0.0 freeze release. This is an exception to "deploy tagged releases" (`project/RELEASES.md`, What is live). After the freeze, the branch merges into `main` and is released as v1.1.0, and that tag is deployed.

*Superseded in part by [D-028](#d-028) (2026-11-26):* Try it is back on the film's page, after Decode, instead of on `model.html`.

*Update 2026-11-26 (merge):* the owner merged `web-retelling` into `main` before the freeze (`f5b794e`; the branch is deleted). So the retold page is part of the v1.0.0 freeze release instead of a later v1.1.0, and the live page, which serves the checked-out tree, now runs from `main`. The untagged exception above ends with the v1.0.0 tag.

### D-026

**The film's 3D scene is redrawn, following [`web/PLAN-SCENE.md`](../web/PLAN-SCENE.md)** (WEB-6). *Decided by:* the owner, who judged the WEB-5 scene odd and unprofessional and approved the plan on 2026-11-26. *What:*
- The research beats go dark, as in deep water, and only the data glows: a high-range picture with glow, tone mapping, depth of field and fog; solid lit surfaces instead of wireframes; smoothed ribbons instead of one-pixel lines; one spline camera path.
- Still hand-written WebGL 2 with no library.
- Full quality is designed for the owner's NVIDIA RTX 5060; the scene steps down by itself on weaker chips.
- Every shape, time and point still comes from `web/film/`.

*Why:* the owner wanted the 3D to look professional. *Alternatives:*
- Three.js: its stock glow is heavier than the scene can afford on a built-in chip, and the scene's camera, labels and fallbacks would be rewritten.
- Polish the WEB-5 drawing (thicker lines, darker ground): it keeps the wireframes and flat strokes that make it look odd.

*Consequence:*
- A page cannot choose the graphics chip: Chrome on Windows gives WebGL the Radeon 610M whatever the page asks (measured 2026-11-26). The RTX 5060 is set per browser in Windows.
- The work is on the branch `web-scene-v2`; it merges before the v1.0.0 freeze only if its checks pass by 28 Nov, otherwise it ships as v1.1.0.
- The plan's other `[DECISION]` tags stay inline in `web/PLAN-SCENE.md`.

*Superseded in part by [D-027](#d-027) (2026-11-26):* the look (deep water, glow, tone mapping, lit surfaces, quality steps). The redraw itself, hand-written WebGL 2, the graphics-chip finding and the timing rule stay.

### D-027

**The redrawn scene keeps the page's own blue water and is drawn in fine lines** (WEB-6, [`web/PLAN-SCENE.md`](../web/PLAN-SCENE.md)). Supersedes D-026's look. *Decided by:* the owner, who on 2026-11-26 judged the first style frame (dark water, glow, a translucent sheet of light) childish and unprofessional, and asked for the old theme, kept minimal, sophisticated and well planned. *What:*
- The canvas stays transparent over the page's water, as in WEB-5.
- The scene is fine white lines and small dots, with one amber accent (the whistle the film follows; the key in Hear) and coral only for the misread whistle. No glow, bloom, fills, particles or post-processing. Depth is shown by fading into the water.
- Labels in the page's mono with a soft shadow, numbers with units, never over the words.
- Listen is redrawn first as the style frame: a dotted floor of the image's pixel grid, the contour's trace, a hairline per frame and the contour as an amber line along their tops.

*Why:* the owner's judgement of the first style frame. *Alternatives:* keep the dark theme but tone down its glow (rejected with it). *Consequence:*
- `Frame`, the bloom, the drawn water and the quality steps are removed from `web/gl.js`; without post-processing, Listen costs about 0.1 ms per frame even on the Radeon 610M.
- The "loudness" label goes: the training image is the contour resynthesised at constant strength and drawn as an image, so its height is not loudness.

*Update 2026-11-26:* the owner approved the second Listen style frame.

*Update 2026-11-26 (Learn and Speak):* the owner asked that Learn and Speak keep their WEB-5 design and only gain boldness (crisper, stronger points; thicker strokes), not the full redesign planned for them. The canvas also drops multisampling: every line and point smooths its own edge.

*Update 2026-11-27:* the owner chose to leave Hide and Hear as in WEB-5; the camera keeps its WEB-5 moves apart from Listen's opening. WEB-6 is Listen redrawn, Learn and Speak made bolder, and Try it back on the page (D-028).

*Update 2026-11-27 (merge):* the owner committed WEB-6 (`0abb2b3`) and merged it into `main` (`9f91c3b`), so it ships in the v1.0.0 freeze release, and the live page, which serves the checked-out tree, runs it.

### D-028

**Try it is back on the page, as section 08 after Decode** (WEB-6 follow-up). Supersedes D-025's "Try it moves to its own page". *Decided by:* the owner, 2026-11-26: the old whistle models (Nyx and Delphi) belong in the current page too, and of the old page only Try it, with nothing before it changed. *What:*
- The Try it markup of `model.html` (the pre-WEB-5 section, unchanged but for its number) sits in the lab after Decode, with a header link "Try it" after Decode; `lab.js` is loaded by `index.html`.
- After Decode, not between the film and Encode where it was before WEB-5: so nothing before it on the page changes, Encode and Decode keep their numbers (06, 07), and the message system still comes straight after the film (D-024, D-025).
- `model.html` becomes a redirect to `./#try`, so old links and bookmarks still land on Try it, and the Try it markup exists once.
- The footer's link to `model.html` gives way to Try it's image note (0.68 s, ±6 kHz, a pure tone), which was on `model.html`.

*Consequence:* the docs that said Try it is on `model.html` say it is on the page (README, `web/README.md`, `deploy/README.md`, `docs/ARCHITECTURE.md`, `docs/INDEX.md`, `docs/TECHNICAL_REFERENCE.md`, `whistlecode.py`'s help).

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

### D-022

**The code and documents written here are licensed under the Apache License 2.0** (YOU-6). *Decided by:* the owner, 2026-11-22. *Why:* permissive like MIT, plus an explicit patent grant from every contributor, which suits a new communication scheme (WhistleCode). *Alternative:* MIT (shorter, no patent clause). *Consequence:* `LICENSE` holds the unmodified Apache text; `NOTICE` names the copyright holders and lists the third-party material the licence does not cover (the base paper, NOAA files, page footage and fonts). See `project/LICENSING.md`.

### D-023

**How the public README presents the project** (OPS-8). *Decided by:* the owner, 2026-11-23 ("fix all" after the README audit). *What:* the README says near the top that the work is an independent, unofficial reproduction, not affiliated with or endorsed by the paper's authors; an "About this project" section says it is a student course project with one maintainer and that much of the code and documentation was written with Claude Code at the maintainer's direction; the author stays the GitHub handle until the owner chooses to add a name (YOU-13); the headline states the gaps to the paper beside the matches; checkpoints are named by epoch, not by the page's names; only badges that update themselves (CI) or state a fact (licence) are shown. *Why:* the audit found every number correct, but an anonymous, unofficial-looking repository that leads with its best number reads as untrustworthy. *Alternative:* keep the launch-style README and rely on the detail further down. *Consequence:* the tagline uses the paper's own term, biomimetic underwater communication. This does not decide D-013: if the covert framing is agreed, WC-R7 should attribute the covert aim to the paper and put the measured covertness results (E7, E9) beside it.

### D-024

**The project is the message system, under the temporary name Falsetto** (WC-R7, first part). *Decided by:* the owner, 2026-11-23 ("this is a whole new project"; "give it a better temporary name"). *What:* the public documents present the project as a biomimetic underwater messaging system that hides short text messages in synthetic false killer whale whistles. The VAE-GMM generator, with its preprocessing and detector, is "the whistle model": one part of the project, which follows Park et al.'s method and is checked against their paper. The repository no longer calls itself a reproduction. The name Falsetto (false killer whale; a voice that imitates another) is temporary and was chosen by Claude Code. *Where the name appears*, for the final rename: `README.md`, `CITATION.cff` (title), `pyproject.toml` (`name`), `NOTICE`, `project/LICENSING.md`, `web/index.html` (`<title>`). *Not renamed:* the code and its comments (code files are hashed into run records), `whistlecode/` and its documents, which keep the working name WhistleCode and the term "the reproduction" (the README says so once), the frozen campaign records, old log entries, and the GitHub repository and local folder names (YOU-14). *Why:* the message system is the project's own contribution, and the reimplementation of the paper is now one part of it. *Alternative:* keep "reproduction" in the title, with WhistleCode as an extension. *Consequence:* D-013 is decided. D-023 still holds for the unofficial line, the author handle and the AI-assistant note; as it asked, the README puts the covert aim beside the measured covertness results (E7, E9).

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
| `web/PLAN.md` (added 2026-11-26) | 14 |
| `web/PLAN-SCENE.md` (added 2026-11-26) | 5 |
| Code docstrings and comments (`src/`, `whistlecode/`, `post_training/`) | about 35 |
