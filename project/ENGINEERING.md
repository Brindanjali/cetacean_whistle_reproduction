# Engineering: code quality, testing, CI, environment, configuration

The rules for the code itself. Index of all systems: [README.md](README.md).

## Code quality

**Tool:** [ruff](https://docs.astral.sh/ruff/) 0.3.5 (the version in `constraints.txt`), lint only. Settings: `[tool.ruff]` in [`pyproject.toml`](../pyproject.toml).

- **Rules on:** pyflakes (`F`: unused and undefined names), the import, statement and syntax checks (`E4`, `E7`, `E9`), and bugbear (`B`: likely bugs).
- **House style allowed:** several short statements on one line, small named lambdas, `l`/`I`/`O` as maths names, imports after a `sys.path` insert, lines up to 140 characters. These are ignored on purpose (the list, with reasons, is in `pyproject.toml`).
- **No auto-formatter** ([D-016](DECISIONS.md#d-016)). `ruff format` would rewrite 121 files in a style the code does not use, burying the history the week before the code freeze.
- **A false alarm** is silenced on its line, with the reason: `# noqa: B023 -- runs during this job only`. A whole rule is never switched off to hide one case.

**Where it runs:** the pre-commit hook (staged `.py` files), `python tools/repo.py check lint`, and CI (whole repository).

## Testing

Two suites, run with pytest. Settings and markers: `[tool.pytest.ini_options]` in `pyproject.toml`.

| Suite | Folder | Tests | Run in CI (the rest skip there) | Command |
|---|---|---|---|---|
| Reproduction | `tests/` | 202 | 199 | `python -m pytest` |
| WhistleCode | `whistlecode/tests/` | 269 | 208 | `python -m pytest whistlecode/tests` |

On the project laptop every test runs. In CI (and any fresh clone) 64 tests skip because git does not hold the files they read; they are tier 2 below.

**Tiers**

| Tier | What | Where it runs | When |
|---|---|---|---|
| 1. Fast tests | Every test that needs only what git holds (synthetic fixtures, the two VAE checkpoints in git) | laptop and CI | every commit |
| 2. Local-data tests | Tests that read the raw audio, the built dataset, the GMM or the codebook. They skip themselves when the files are absent | laptop | every commit (`check tests`) |
| 3. Gates and campaigns | Training gates G1-G6, the GMM post-fit check, WhistleCode gate F1, campaign v1 and v2 | laptop, Colab | deliberately; each one is an [experiment](EXPERIMENTS.md) |

**Markers** (a test without one is tier 1):

- `gpu`: needs a CUDA device; skipped without one.
- `realdata`: reads one real raw file, read-only; skipped without the raw audio.
- `localdata`: needs the dataset or model files that git does not hold; skipped without them. A fixture that needs them requests the `local_data` fixture instead (both in `whistlecode/tests/conftest.py`).

**Rules**

- **New behaviour gets a test.** A bug fix gets a test that fails before the fix.
- **Known numbers are pinned.** Results the paper states exactly are tests, so a change that breaks them fails: for example, the decoder's 557,318,144 Table 6 FLOPs (`tests/test_vaegmm_model.py`), a known WhistleCode frame (`test_wc_framing.py::test_known_frame`) and the whistle counts per message that PLAN.md states (`test_wc_format2.py`).
- **Tests never touch real data in place.** Raw folders are read-only; tests write only to pytest's temporary folders.
- **Only this project's plugins run.** pytest is told not to load `pytest-asyncio` (`-p no:asyncio` in `pyproject.toml`), which another project installed in the shared Python and which breaks under pytest 9.
- **A skip is not a pass.** CI's skip list (`-rs`) is read when a test is added, so a test that always skips in CI is noticed.

## CI

[`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs on every push to `main`, every pull request, every `v*` tag, and on demand.

| Job | What | Blocks? |
|---|---|---|
| Lint, secrets, links, checksums | `ruff check .`; the secret scan over all files and every past commit; relative Markdown links; checksums of the models git holds | yes |
| Tests (CPU) | CPU PyTorch and the pinned requirements, then `check config` and both suites (tier 1) | yes |
| Dependency audit | `pip-audit` on the server image's pins and the lock file; each vulnerable package becomes a warning on the run, with the version that fixes it | no (it fails only if the audit cannot run; read its warnings before a release) |

**Reading a run.** GitHub shows the logs only to signed-in users, so CI also posts failing tests, lint findings and audit warnings as annotations, which anyone can read. `python tools/repo.py ci-report` prints the latest run: each job, the failed step and its annotations.

A red CI run on `main` is fixed before any other work. The README badge shows the state of `main`.

## Environment and dependencies

| File | Holds | Used by |
|---|---|---|
| [`.python-version`](../.python-version) | Python 3.11 | CI, pyenv, uv |
| [`requirements.txt`](../requirements.txt) | reproduction packages, lower bounds | everyone |
| [`whistlecode/requirements.txt`](../whistlecode/requirements.txt) | WhistleCode's extra packages (`reedsolo`, exact; `cryptography` for `serve --lan`) | everyone |
| [`deploy/requirements-serve.txt`](../deploy/requirements-serve.txt) | the web server image, exact pins | `deploy/Dockerfile` |
| [`constraints.txt`](../constraints.txt) | **the lock file:** exact versions of all 57 packages in use, including the ones they pull in | CI; a new machine |

**Set up a machine** (CPU; for a GPU, install `torch` and `torchvision` from the PyTorch index for your CUDA version first):

```
pip install -r requirements.txt -r whistlecode/requirements.txt -c constraints.txt
git config core.hooksPath .githooks
python tools/repo.py check
```

**Rules**

- **A new package** goes into the right requirements file with a comment saying why, its licence goes into [LICENSING.md](LICENSING.md), and the lock is rewritten: `python tools/repo.py lock`.
- **An upgrade** is a change like any other: rewrite the lock, run `check`, log it. PyTorch upgrades also need the training-resume check (gate G3), because checkpoints record the version.
- `constraints.txt` is written by the tool, never by hand. It drops local build labels (`+cu130`), so CPU and CUDA builds of one version both satisfy it.

## Configuration

Every setting lives in a TOML file. No number that changes a result is written into the code.

| File | Holds |
|---|---|
| `configs/pipeline.toml` | preprocessing S1-S9 |
| `configs/detector.toml` | the RidgeNet detector and tracker |
| `configs/vaegmm.toml` | VAE training, the GMM and evaluation |
| `configs/inference.toml` | Try it, the server and the model selector |
| `whistlecode/config.toml` | WhistleCode: format, codebook, channel, receiver, web |
| `mod_detector_5_24/*.toml` | the 5-24 kHz detector variant |

**Rules**

- **Evidence tags.** Every value carries `[EXPLICIT]`, `[IMPLIED]` or `[UNSPECIFIED]` (from the paper), `[DECISION]` (chosen here) or `[REPLACEMENT]` (the new detector design). See the README, "Research integrity".
- **Locked sections.** The `[paper]` sections of `pipeline.toml` and `vaegmm.toml` hold the paper's values. The loaders refuse to run if one differs from the specification.
- **Every run records its configuration.** Runs, datasets and fits save the full effective configuration and its hash (`config_effective_hash` in `train_info.json`, `processing_config_hash` in `dataset_info.json`), so a result can always be traced to the settings that made it.
- **Frozen settings.** A campaign records the hash of `whistlecode/config.toml` it ran with (`paper/RESULTS.md` header). Settings frozen by a pass-mark protocol (`whistlecode/PLAN.md` 8.6, 8.7) are not changed until that campaign has run.
- **Check:** `python tools/repo.py check config` loads every file through its own loader.
