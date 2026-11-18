"""When and at what pitch each whistle of a frame is sent (PLAN.md section 4.3).

Timing and pitch never depend on the symbols, so the receiver can re-create them:

- the preamble and header slots come from the key alone, because the receiver has not read the nonce yet;
- the payload slots come from the key and the nonce, and follow the last header slot.

Times are in seconds from the start of the first preamble whistle.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import framing, keys, synth
from .config import default_config

PREAMBLE, HEADER, PAYLOAD = "preamble", "header", "payload"


@dataclass(frozen=True)
class Slot:
    index: int          # position in the frame, from 0
    part: str           # preamble, header or payload
    start_s: float      # whistle start, from the start of the frame
    fc_hz: float        # the whistle's mid-range frequency


def pitch_pool(cfg: dict | None = None) -> np.ndarray:
    """The sorted centre frequencies slots draw from; sender and receiver must use the same pool."""
    return np.sort(synth.fc_pool(cfg or default_config()))


def _draw(part: str, key: str, nonce: int | None, n: int, cfg: dict, pool: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lo, hi = cfg["schedule"]["interval_s"]
    gaps = keys.stream(part, "timing", key, nonce, cfg).uniform(float(lo), float(hi), n)
    fcs = pool[keys.stream(part, "pitch", key, nonce, cfg).integers(0, len(pool), n)]
    return gaps, fcs


def header_slots(key: str, cfg: dict | None = None, pool: np.ndarray | None = None) -> list[Slot]:
    """The preamble and header slots, from the key alone."""
    cfg = cfg or default_config()
    pool = pitch_pool(cfg) if pool is None else pool
    n_pre = int(cfg["framing"]["n_preamble"])
    n = n_pre + 2 * framing.header_bytes(cfg)
    gaps, fcs = _draw(keys.HEADER, key, None, n, cfg, pool)
    starts = np.concatenate([[0.0], np.cumsum(gaps[:n - 1])])
    return [Slot(i, PREAMBLE if i < n_pre else HEADER, float(starts[i]), float(fcs[i])) for i in range(n)]


def payload_slots(key: str, nonce: int, length: int, after: Slot, cfg: dict | None = None,
                  pool: np.ndarray | None = None) -> list[Slot]:
    """The payload slots of a `length`-byte message, following the last header slot `after`."""
    cfg = cfg or default_config()
    pool = pitch_pool(cfg) if pool is None else pool
    n = 2 * framing.payload_bytes(length, cfg)
    gaps, fcs = _draw(keys.PAYLOAD, key, nonce, n, cfg, pool)
    starts = after.start_s + np.cumsum(gaps)
    return [Slot(after.index + 1 + i, PAYLOAD, float(starts[i]), float(fcs[i])) for i in range(n)]


def frame_slots(key: str, nonce: int, length: int, cfg: dict | None = None, pool: np.ndarray | None = None) -> list[Slot]:
    """Every slot of a frame, in order."""
    cfg = cfg or default_config()
    pool = pitch_pool(cfg) if pool is None else pool
    head = header_slots(key, cfg, pool)
    return head + payload_slots(key, nonce, length, head[-1], cfg, pool)
