"""WhistleCode tests: python -m pytest whistlecode/tests (from the repository root)."""
import sys
from pathlib import Path

import pytest

WC = Path(__file__).resolve().parents[1]
ROOT = WC.parent
sys.path.insert(0, str(WC))

from wcode.config import default_config  # noqa: E402

# Files git does not hold that some tests read: the built dataset (the pitch pool) and the epoch-101 latents (the
# lineage check). Without them (a fresh clone, CI) those tests are skipped; on the project laptop they run.
# A test says so with the `localdata` marker (pyproject.toml [tool.pytest]); a fixture, by requesting `local_data`.
LOCAL_DATA = (
    ROOT / "preprocessed" / "encounter_191" / "images.csv",
    ROOT / "models" / "vaegmm" / "V1_L64_b1e-4_critic_E191" / "latents_mu.npy",
)


def _skip_without_local_data():
    missing = [p for p in LOCAL_DATA if not p.exists()]
    if missing:
        pytest.skip(f"local data not on this machine: {missing[0].relative_to(ROOT).as_posix()}")


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    if item.get_closest_marker("localdata"):
        _skip_without_local_data()


@pytest.fixture(scope="session")
def local_data():
    """Request this from a fixture that reads the local dataset or model files."""
    _skip_without_local_data()


@pytest.fixture
def cfg():
    return default_config()
