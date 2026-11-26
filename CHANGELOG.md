# Changelog

Notable changes to this project, release by release. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) as described in [`project/RELEASES.md`](project/RELEASES.md). Day-by-day detail is in [`WORKLOG.md`](WORKLOG.md).

## [Unreleased]

### Added

- **`export-film`** (`python whistlecode/whistlecode.py export-film`): the page film's data from real records only, written to `web/film/` and kept in git (WEB-5, `web/PLAN.md`). One real send of "MEET AT DAWN", decoded in encounter-214 sea noise at 10 dB with the first exact noise seed; all 63,490 latents on three principal axes with their mixture components; the codebook's shapes; one training image. A test fails if the model or codebook changes after the export.
- **The whistle model's own page** (`web/model.html`): Try it, with its model selector, moved off the film's page.
- **The film's research section is drawn from real records** (WEB-5 P3): five beats, Listen → Learn → Speak → Hide → Hear, as one WebGL 2 scene with no library (`web/scene.js`, `web/gl.js`). A real encounter-191 whistle rises as a landscape; all 63,490 whistles appear as points, the codebook's 16 families light up and unfold into a lattice of 64 whistles; one real send of "MEET AT DAWN" runs as a river of time; the key's whistles rise, the one the receiver misread in the sea is repaired, and the message whistles become the letters. "Hear it" plays a data whistle cut from that send. Without WebGL 2, or after a lost context, the words stand over still water; with reduced motion, each beat shows its settled picture.
- **The sender records each cover whistle as played** (its pitch after any move) and the times of the recorded clicks (`Transmission.covers`, `clicks_s`). The audio is unchanged.

### Changed

- **The film's words, final pass** (WEB-5 P4): each beat says only what its record holds. Speak no longer calls a whistle "a letter" (a whistle carries six bits, a letter five); Hide's "about a third" now counts whistles only, not clicks; Learn says the whistles come from one encounter; Listen says where its whistle was recorded (off Hawai‘i, 2017); the line before the beats asks whether a whistle that can carry a name can carry a message.
- **The page tells Falsetto's story first** (on the branch `web-retelling`): the header reads "Falsetto"; Encode and Decode follow the film directly, brought in by the tide; the film's last line leads to Encode; the footer states the limits (simulation only; the coded shapes can still be told from real ones). The tide and the sea moved from `lab.js` to `web/water.js`, unchanged.
- **Data-whistle share reconciled** (WC-R7): one in four rhythm-bank whistles can carry data, and about a third of a played message does. `TEST_PROTOCOL.md` is corrected, with a dated note, and so is its outdated line on epoch 150.

- **The project is presented as what it now is** (D-024): a biomimetic messaging system that hides short text messages in synthetic false killer whale whistles, under the temporary name Falsetto, and no longer as a reproduction of Park et al. The README leads with the message system and its results beside their pass marks; the VAE-GMM generator is "the whistle model", which follows Park et al.'s method and is checked against their paper. `CITATION.cff` cites the project and lists the paper under references. `pyproject.toml`, `NOTICE`, the page's title and footer and the CI step names follow. No numbers changed.
- **README files rewritten for credibility** (no numbers changed): the main README now says the work is an independent, unofficial course project, written with an AI assistant; states the gaps to the paper beside the matches; uses the paper's term "biomimetic" instead of "covert"; names checkpoints by epoch; shows the DCLDE 2011 score beside Li et al.'s; gives full references; and has a "What runs from a clone" table with download sizes. `CITATION.cff` gains an abstract. `project/README.md`, `web/README.md`, `deploy/README.md` and `cluster/node/README_CLUSTER.md` are written for an outside reader.

### Fixed

- **Job folders are pruned in the order they were made** (BUG-13). Two jobs made in the same second were ordered by their random suffix, so a newer one could be deleted first, and Try it could delete the folder of an upload still being copied, failing its job. Both servers now prune through `JobFolders` in `src/whistlepipe/guard.py`.

### Security

Fixes for the public page, from the whole-project audit (`project/AUDIT_2026-11-23.md`, BUG-2 to BUG-7):

- **Uploads can no longer decode to gigabytes.** Try it and Decode read only the channel they use, in blocks and never past the length limit, and refuse sample rates above 768 kHz (Try it) or 192 kHz (Decode) and more than 8 channels. A 1.7 MB FLAC used to decode to 6.3 GB.
- **New whistles per whistle are capped** at twice the default on `/api/analyze-example` too, as they already were on `/api/analyze`; negative values count as none.
- **Request sizes, uploads and the queue are limited.** A body over its route's limit (the upload size for `/api/analyze` and `/api/wc/decode`, 64 kB for every other request) is refused with 413 while it arrives, before anything is stored; at most two uploads may arrive at once and six jobs wait, beyond which the server answers "busy" (503); an upload is deleted when its job ends. New module `src/whistlepipe/guard.py`.
- **`POST /api/reload-model` is off** unless `[server] allow_reload = true` in `configs/inference.toml` (403 otherwise): anyone who could open the page could make the server re-read every model file.
- **A decoded message is no longer written to disk** (BUG-6). Decode kept it in the job's `result.json`, readable by anyone with the job ID; it is now kept in memory with its job and added to `result.json` only as that is served. The page shows "No longer held by the server" if the server restarted in between.
- **The server image installs the locked versions** (BUG-9). It installed only its ten direct pins, so the rest floated at build time: 14 of 38 packages differed from `constraints.txt`, among them an older filelock from the PyTorch index and setuptools 79.0.1 from the base image, both below their advisory fixes. The image now installs PyTorch alone from its index and everything else with `-c constraints.txt`, runs `pip check`, and replaces the base image's pip 24.0 (12 advisories) with 26.2.2. The build context is the repository, of which `deploy/Dockerfile.dockerignore` lets in two files.
- **Tracebacks are no longer served** (BUG-7). A job that fails inside the code still saves `error.txt` in its folder for whoever runs the server, but no file route or results zip serves it, and the error message no longer names it.

## [0.10.0] - 2026-11-22

### Security

- Eight packages with published advisories upgraded to versions that fix them: anyio 4.16.0, certifi 2026.11.20, cryptography 50.0.2, filelock 4.2.12, fsspec 2026.9.0, pillow 13.0.0 (also in the server image), pytest 9.2.0, setuptools 84.2.1. All 57 pins now have no known advisories.

### Added

- **Licence**: Apache License 2.0 (`LICENSE`), with a `NOTICE` listing the third-party material it does not cover.
- **`tools/repo.py ci-report`**: the latest CI run's jobs, failed steps and annotations, read from GitHub without signing in; **`audit-report`** turns the dependency audit into warnings on the run.

### Changed

- CI posts failing tests and lint findings as annotations; the dependency audit reports vulnerable packages as warnings instead of failing; `actions/checkout` v5 and `actions/setup-python` v6 (the old ones ran on a deprecated Node.js).
- pytest no longer loads the `pytest-asyncio` plugin (`-p no:asyncio`): the project has no asyncio tests, and an old copy installed for another project broke collection under pytest 9.
- `audit-report` merges a package listed in both pinned files, and repeated advisory IDs.

### Fixed

- CI's WhistleCode suite failed on GitHub because `cryptography` (used by `serve --lan` and its test) was in no requirements file. It is now in `whistlecode/requirements.txt` and the lock file.

## [0.9.0] - 2026-11-21

The first versioned release. It covers everything up to this date.

### Added

- **Engineering systems** ([`project/README.md`](project/README.md)): task tracker with a bug list, Definition of Done and code review ([`project/WORKFLOW.md`](project/WORKFLOW.md)); lint settings, test tiers and markers, CI, the lock file `constraints.txt` and configuration rules ([`project/ENGINEERING.md`](project/ENGINEERING.md)); releases, deployment checklist and monitoring ([`project/RELEASES.md`](project/RELEASES.md)); requirement, result, experiment, model, data, decision, incident, storage and licensing registers; a documentation index and an architecture map ([`docs/INDEX.md`](docs/INDEX.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)); a security policy ([`.github/SECURITY.md`](.github/SECURITY.md)).
- **`tools/repo.py`**: one command for every check (lint, config, secrets, links, checksums, tests), plus `lock`, `health` and `release-check`.
- **`GET /healthz`** on the web server, and a Docker healthcheck that uses it.
- **Pre-commit hook**: secret scan and lint of staged files, next to the work-log check.
- **WhistleCode R0-R2**: threat model and claims, frozen protocol and pass marks v2, literature review and novelty statement, and Doppler and clock-drift correction in the receiver (adopted on encounter 214).
- **WhistleCode campaign v1**: 4,200 trials and 500 empty-recording tries ([`whistlecode/paper/RESULTS.md`](whistlecode/paper/RESULTS.md)).
- **Web page**: the scroll film, Try it with the model selector (Nyx, Delphi), Encode, Decode and Record; self-hosting with Docker and Tailscale Funnel.
- **Reproduction**: preprocessing S1-S9 over 1,415 files (180,154 images); the RidgeNet replacement detector (v2c adopted); VAE run V1 to epoch 150; GMMs at K = 3,000 for epochs 101 and 150; paper evaluation of epoch 101 (Tables 1, 3, 6; Figs. 7-10, 12).
- **Detector variant** for 5-24 kHz and its DCLDE 2011 benchmark (`mod_detector_5_24/`).

### Changed

- `pytest.ini` replaced by `pyproject.toml`, which also holds the version and the lint settings.
- `docs/` sorted into `course/` (course notes and reviews), `explainers/` (local pages, not in git) and `private/` (never in git).
- Ten WhistleCode tests that need the local dataset are marked `localdata`, so they skip cleanly where the data is absent.

### Fixed

- Unused imports and unused loop variables found by the new lint settings.

[Unreleased]: https://github.com/anonymus-k-dot/cetacean_whistle_reproduction/compare/v0.10.0...HEAD
[0.10.0]: https://github.com/anonymus-k-dot/cetacean_whistle_reproduction/compare/v0.9.0...v0.10.0
[0.9.0]: https://github.com/anonymus-k-dot/cetacean_whistle_reproduction/releases/tag/v0.9.0
