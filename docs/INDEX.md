# Documentation index

Every document in the repository: what it is the authority on, and its state. When two documents disagree, the one listed as the authority wins, and the other is corrected. Checked 2026-11-21. Engineering systems: [`project/README.md`](../project/README.md).

## Start here

| Document | Authority on |
|---|---|
| [`README.md`](../README.md) | what the project is (and that it is unofficial), its results, what runs from a clone, the repository layout |
| [`WORKLOG.md`](../WORKLOG.md) | what is planned, waiting and done; the current state ("At a glance") |
| [`CHANGELOG.md`](../CHANGELOG.md) | what changed in each release |
| [`project/HANDOVER.md`](../project/HANDOVER.md) | how to pick the work up cold |
| [`CLAUDE.md`](../CLAUDE.md) | the rules Claude follows in this repository |

## The whistle model and its record

| Document | Authority on | State |
|---|---|---|
| [`resources/PREPROCESSING_SPECIFICATION.md`](../resources/PREPROCESSING_SPECIFICATION.md) | paper evidence for every preprocessing stage; parameter table | current |
| [`resources/TRAINING_SPECIFICATION.md`](../resources/TRAINING_SPECIFICATION.md) | training specification, discrepancies, deviations, gates | current (updated for epoch 150) |
| `resources/VAE-GMM Cetacean Whistles.pdf` | Park et al.'s paper, whose method the whistle model follows (CC BY-NC-ND 4.0) | — |
| [`docs/TECHNICAL_REFERENCE.md`](TECHNICAL_REFERENCE.md) | dataset layout, lineage, detector experiments, training record, inference, every command | current |
| [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) | how the components, modules, server and deployment fit together | current |
| `docs/figures/` | figures used in the course documents | — |

## WhistleCode

| Document | Authority on | State |
|---|---|---|
| [`whistlecode/PLAN.md`](../whistlecode/PLAN.md) | design, experiments, pass marks (8.6, 8.7 frozen), parameters, revision history | current |
| [`whistlecode/THREAT_MODEL.md`](../whistlecode/THREAT_MODEL.md) | adversaries, security properties, the claims C1-C13 | current |
| [`whistlecode/RELATED_WORK.md`](../whistlecode/RELATED_WORK.md) | literature, comparison table, novelty statement | WC-R1a open |
| [`whistlecode/paper/TEST_PROTOCOL.md`](../whistlecode/paper/TEST_PROTOCOL.md) | campaign methods (for a paper's Methods section) | current (epoch-150 line and data-whistle share corrected 2026-11-26, WC-R7) |
| [`whistlecode/paper/RESULTS.md`](../whistlecode/paper/RESULTS.md) | campaign v1 verdicts, tables and figures | frozen record |

## Page, deployment, other machines

| Document | Authority on | State |
|---|---|---|
| [`web/README.md`](../web/README.md) | running the two pages (the film with Encode, Decode and Record; Try it on `model.html`); the film's data; video files | static examples out of date (WEB-1) |
| [`web/PLAN.md`](../web/PLAN.md) | the plan to retell the page as Falsetto (WEB-5): story beats, the 3D scene, data export, changes by file, checks | approved (D-025); in progress on the branch `web-retelling` (P1 and P2 done) |
| [`web/CREDITS.md`](../web/CREDITS.md) | footage and font sources and licences | current |
| [`deploy/README.md`](../deploy/README.md) | self-hosting with Docker and Tailscale Funnel | current |
| [`cluster/node/README_CLUSTER.md`](../cluster/node/README_CLUSTER.md) | course lab: running the demo on the college's teaching cluster | current |
| `colab/train_V1_colab.ipynb` | the VAE training run on Colab (its first cell explains each step) | current |

## Detector paper

| Document | Authority on | State |
|---|---|---|
| [`mod_detector_5_24/README.md`](../mod_detector_5_24/README.md) | the 5-24 kHz detector and the DCLDE 2011 benchmark | current |
| [`mod_detector_5_24/TODO.md`](../mod_detector_5_24/TODO.md) | the detector paper's open work | older than the draft (DET-1) |
| `docs/private/Mentor_Review_1.pdf` | the draft itself (local only, never in git) | under mentor review (DET-4) |

## Engineering systems (`project/`)

| Document | Authority on |
|---|---|
| [`project/README.md`](../project/README.md) | how the project is run: who does what, each record and check, where it lives |
| [`project/WORKFLOW.md`](../project/WORKFLOW.md) | task tracker rules, Definition of Done, code review |
| [`project/ENGINEERING.md`](../project/ENGINEERING.md) | code quality, testing, CI, environment, configuration |
| [`project/RELEASES.md`](../project/RELEASES.md) | versions, release procedure, deployment checklist, monitoring |
| [`project/TRACEABILITY.md`](../project/TRACEABILITY.md) | requirements and claims to tests; reported numbers to records |
| [`project/EXPERIMENTS.md`](../project/EXPERIMENTS.md) | every run, fit, gate and campaign |
| [`project/MODELS.md`](../project/MODELS.md) | every model file, its status and checksum |
| [`project/DATA.md`](../project/DATA.md) | every dataset, its role and verification |
| [`project/DECISIONS.md`](../project/DECISIONS.md) | project-level decisions |
| [`project/STORAGE.md`](../project/STORAGE.md) | where files live, backups, restore |
| [`project/LICENSING.md`](../project/LICENSING.md) | licences of the project and of everything third-party |
| [`project/INCIDENTS.md`](../project/INCIDENTS.md) | failures and what now prevents them |
| [`project/AUDIT_2026-11-23.md`](../project/AUDIT_2026-11-23.md) | the whole-project audit of 2026-11-23: findings, places and fixes (tracked as BUG-2 to BUG-12 and the items it names in `WORKLOG.md`) |
| [`.github/SECURITY.md`](../.github/SECURITY.md) | secrets, the public page's exposure, reporting a problem |

## Course (`docs/course/`)

The course deliverables, in git: the Review-I guidelines (PDF, and [`Review-I-Guidelines.md`](course/Review-I-Guidelines.md) with the plan and milestones M1-M8), the week 1, 2 and 4 notes ([`Notes-W-4.md`](course/Notes-W-4.md), [`Notes-W-4-filled.md`](course/Notes-W-4-filled.md) and their results table), the VAE-GMM training plan and the Review-I slides (`Review_ppt.pptx`).

## Local only (not in git)

| Folder | Holds |
|---|---|
| `docs/explainers/` | four standalone explainer pages (pipeline, training, end to end) |
| `docs/private/` | the detector paper draft and a copyrighted reference paper |
| `floorplan/` | an interactive map of the code |
