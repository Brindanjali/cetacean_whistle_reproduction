# Changelog

Notable changes to this project, release by release. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) as described in [`project/RELEASES.md`](project/RELEASES.md). Day-by-day detail is in [`WORKLOG.md`](WORKLOG.md).

## [Unreleased]

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
