# How the project is run

How this project is run: who does what, where each record lives, and what checks it. The project has one maintainer, called the owner in these files, who works with an AI coding assistant:

- **The owner** decides, approves, downloads, commits and pushes, and does anything only a person can do (volunteers, licences, the course mentor).
- **Claude Code**, the AI assistant, writes most of the code and documents at the owner's direction, keeps the records below current in the same turn as the work, runs the checks, and lists what waits on the owner.

Each entry below is a plain file in this repository or a check, not an outside service. They are checked by one command (`python tools/repo.py check`), a git hook and CI.

## The records and checks

| # | What | Lives in | Checked by |
|---|---|---|---|
| 1 | Work log | [`../WORKLOG.md`](../WORKLOG.md) "Done" | pre-commit hook (refuses a commit without `WORKLOG.md`) |
| 2 | Task tracker | [`../WORKLOG.md`](../WORKLOG.md) "To do" and "Bugs" | [WORKFLOW.md](WORKFLOW.md#task-tracker) rules |
| 3 | Definition of Done | [WORKFLOW.md](WORKFLOW.md#definition-of-done) | checklist before every commit |
| 4 | Code review | [WORKFLOW.md](WORKFLOW.md#code-review) | review before the commit commands are given |
| 5 | Code quality | [`../pyproject.toml`](../pyproject.toml) `[tool.ruff]`, [ENGINEERING.md](ENGINEERING.md#code-quality) | hook (staged files), CI |
| 6 | Testing | `tests/`, `whistlecode/tests/`, [ENGINEERING.md](ENGINEERING.md#testing) | `check`, CI |
| 7 | Continuous integration | [`../.github/workflows/ci.yml`](../.github/workflows/ci.yml), [ENGINEERING.md](ENGINEERING.md#ci) | GitHub Actions on every push |
| 8 | Environment and dependencies | requirements files, [`../constraints.txt`](../constraints.txt), [`../.python-version`](../.python-version), [ENGINEERING.md](ENGINEERING.md#environment-and-dependencies) | CI installs from the lock file |
| 9 | Configuration | `configs/`, `whistlecode/config.toml`, [ENGINEERING.md](ENGINEERING.md#configuration) | the loaders (locked `[paper]` sections), `check config` |
| 10 | Releases and versions | [`../CHANGELOG.md`](../CHANGELOG.md), [RELEASES.md](RELEASES.md) | `tools/repo.py release-check` |
| 11 | Deployment | [`../deploy/`](../deploy/README.md), [RELEASES.md](RELEASES.md#deployment) | checklist and "what is live" record |
| 12 | Monitoring | `/healthz`, Docker healthcheck, [RELEASES.md](RELEASES.md#monitoring) | `tools/repo.py health` |
| 13 | Requirements traceability | [TRACEABILITY.md](TRACEABILITY.md#requirements) | updated with every claim or result |
| 14 | Experiment tracking | [EXPERIMENTS.md](EXPERIMENTS.md) | one row per run, before the run starts |
| 15 | Model registry | [MODELS.md](MODELS.md), [`checksums/models.sha256`](checksums/models.sha256) | `check checksums` |
| 16 | Data catalogue | [DATA.md](DATA.md), [`../metadata/manifest_all.csv`](../metadata/manifest_all.csv) | the pipeline's SHA-256 check, `checksums verify --raw` |
| 17 | Results traceability | [TRACEABILITY.md](TRACEABILITY.md#results) | every reported number names its record |
| 18 | Documentation index | [`../docs/INDEX.md`](../docs/INDEX.md) | `check links` |
| 19 | Decision records | [DECISIONS.md](DECISIONS.md) | one entry per project-level choice |
| 20 | Handover | [HANDOVER.md](HANDOVER.md), [`../CLAUDE.md`](../CLAUDE.md) | read at the start of every session |
| 21 | Architecture map | [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) | updated when a component or route changes |
| 22 | Backup and storage | [STORAGE.md](STORAGE.md) | monthly restore check |
| 23 | Security and secrets | [`../.github/SECURITY.md`](../.github/SECURITY.md) | hook and CI secret scan, dependency audit |
| 24 | Licensing | [LICENSING.md](LICENSING.md) | third-party inventory |
| 25 | Incident post-mortems | [INCIDENTS.md](INCIDENTS.md) | one entry per failure that cost work |

## Daily use

```
python tools/repo.py check            # everything (about 2 minutes); --quick skips the test suites
python tools/repo.py check lint links # just those
python tools/repo.py health           # is the web server up?
python tools/repo.py ci-report        # the last CI run on GitHub: jobs, failed steps, annotations
```

The ID prefixes used across these files: YOU, WC, DET, REP, WEB, OPS (tasks), BUG, D (decisions), EXP (experiments), INC (incidents), R and C (requirements and claims).
