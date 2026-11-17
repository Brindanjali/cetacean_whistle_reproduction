"""WhistleCode tests: python -m pytest whistlecode/tests (from the repository root)."""
import sys
from pathlib import Path

import pytest

WC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WC))

from wcode.config import default_config  # noqa: E402


@pytest.fixture
def cfg():
    return default_config()
