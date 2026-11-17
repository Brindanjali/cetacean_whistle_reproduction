"""The reproduction code WhistleCode imports (read-only): puts src/ on sys.path once and re-exports what is used.

Nothing here changes the reproduction; WhistleCode never writes under src/, configs/, models/ or preprocessed/.
"""
from __future__ import annotations

import sys

from .config import PROJECT_ROOT

_SRC = str(PROJECT_ROOT / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from whistlepipe import dsp, sonify  # noqa: E402,F401
from whistlepipe.audio import AudioSignal  # noqa: E402,F401
from whistlepipe.config import load_pipeline_config  # noqa: E402,F401
from whistlepipe.detector import RidgeDetector  # noqa: E402,F401
from whistlepipe.detector.ridgenet import resolve_device  # noqa: E402,F401
from whistlepipe.representation import s7_vectors  # noqa: E402,F401
from whistlepipe.tracking import run_s6  # noqa: E402,F401
