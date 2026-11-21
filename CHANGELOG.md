# Changelog

Notable changes to this project, release by release. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) as described in [`project/RELEASES.md`](project/RELEASES.md). Day-by-day detail is in [`WORKLOG.md`](WORKLOG.md).

## [Unreleased]

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

[Unreleased]: https://github.com/anonymus-k-dot/cetacean_whistle_reproduction/compare/v0.9.0...HEAD
[0.9.0]: https://github.com/anonymus-k-dot/cetacean_whistle_reproduction/releases/tag/v0.9.0
