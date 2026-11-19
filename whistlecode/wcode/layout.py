"""Where a message sits in the rhythm bank (PLAN.md section 4.6). The receiver re-creates all of this from the key and nonce.

- The key alone picks the stretch for the preamble and header, because the receiver has not read the nonce yet.
- The key and nonce pick the stretch for the payload, which follows after a real silence.

A walk starts at a real silence and plays every bank whistle at its real time. Whistles that can carry data become data slots
while enough are still needed, and the walk stops at the next real silence after the last data slot. If a stretch runs out,
the walk continues at another start point.

Times are in seconds from the first whistle of the frame. Each data slot has four candidate pitches, the quantiles (b + u) / 4
of the real pitch pool, where u comes from the key and the two data bits choose b.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import format2, keys
from .bank import Bank, BankError
from .config import default_config

PREAMBLE, HEADER, PAYLOAD = "preamble", "header", "payload"
MAX_DRAWS = 1000


@dataclass(frozen=True)
class Slot:
    index: int                      # position among the frame's data whistles
    part: str                       # preamble, header or payload
    start_s: float
    candidates_hz: tuple            # four pitches; the preamble has one
    bank_index: int


@dataclass(frozen=True)
class CoverSlot:
    bank_index: int
    start_s: float


@dataclass(frozen=True)
class Layout:
    slots: list
    covers: list
    end_s: float                    # end of the last whistle
    join_gap_s: float               # the real silence left before whatever follows
    segments: tuple = ()            # (bank start, bank end, shift): add shift to a bank time to get its time in the frame


def _segment(b: Bank, i0: int, need: int, cfg: dict) -> tuple[int, list[int]]:
    """Walk from whistle i0: (last whistle played, whistles used as data slots)."""
    c = cfg["bank"]
    spacing, after, silence = float(c["min_data_spacing_s"]), float(c["data_after_s"]), float(c["min_silence_s"])
    run, n = int(b.run[i0]), len(b)
    picks: list[int] = []
    allowed = -np.inf
    j = i0
    while True:
        if len(picks) < need and b.eligible[j] and b.on[j] >= allowed:
            picks.append(j)
            allowed = float(b.on[j]) + max(spacing, float(b.off[j] - b.on[j]) + after)
        at_end = j + 1 >= n or int(b.run[j + 1]) != run
        if at_end or (len(picks) == need and b.silence_after[j] >= silence):
            return j, picks
        j += 1


def _walk(b: Bank, rng: np.random.Generator, need: int, t0: float, cfg: dict):
    """Data slots (bank index, time), cover whistles (bank index, time), end time, the silence after it, and the bank stretches."""
    c = cfg["bank"]
    data: list[tuple[int, float]] = []
    covers: list[tuple[int, float]] = []
    segments: list[tuple[float, float, float]] = []
    t, end, gap = float(t0), float(t0), 0.0
    draws = 0
    while len(data) < need:
        draws += 1
        if draws > MAX_DRAWS:
            raise BankError(f"could not find {need} data slots in the rhythm bank")
        i0 = int(b.starts[int(rng.integers(len(b.starts)))])
        last, picks = _segment(b, i0, need - len(data), cfg)
        if not picks:
            continue
        shift = t - float(b.on[i0])
        chosen = set(picks)
        for j in range(i0, last + 1):
            (data if j in chosen else covers).append((j, float(b.on[j]) + shift))
        end = float(b.off[i0:last + 1].max()) + shift
        segments.append((float(b.on[i0]), end - shift, shift))
        gap = float(np.clip(b.silence_after[last], float(c["min_silence_s"]), float(c["max_join_gap_s"])))
        t = end + gap
    return data, covers, end, gap, tuple(segments)


def _layout(data, covers, end: float, gap: float, segments: tuple, u: np.ndarray, pool: np.ndarray, first_index: int,
            n_preamble: int, part: str) -> Layout:
    slots = []
    for i, ((j, t), ui) in enumerate(zip(data, u)):
        if i < n_preamble:
            slots.append(Slot(first_index + i, PREAMBLE, t, (float(np.quantile(pool, ui)),), j))
        else:
            q = (np.arange(4) + ui) / 4
            slots.append(Slot(first_index + i, part, t, tuple(float(f) for f in np.quantile(pool, q)), j))
    return Layout(slots, [CoverSlot(j, t) for j, t in covers], end, gap, segments)


def header_layout(key: str, b: Bank, pool: np.ndarray, cfg: dict | None = None) -> Layout:
    """The preamble and header, from the key alone."""
    cfg = cfg or default_config()
    n_pre = int(cfg["framing"]["n_preamble"])
    f = cfg["format2"]
    need = n_pre + int(f["header_data_symbols"]) + int(f["header_parity"])
    data, covers, end, gap, segments = _walk(b, keys.stream(keys.HEADER, "position", key, None, cfg), need, 0.0, cfg)
    u = keys.stream(keys.HEADER, "pitch", key, None, cfg).random(need)
    return _layout(data, covers, end, gap, segments, u, pool, 0, n_pre, HEADER)


def payload_layout(key: str, nonce: int, n_symbols: int, head: Layout, b: Bank, pool: np.ndarray, cfg: dict | None = None) -> Layout:
    """The payload's slots, from the key and nonce, following the header."""
    cfg = cfg or default_config()
    rng = keys.stream(keys.PAYLOAD, "position", key, nonce, cfg)
    data, covers, end, gap, segments = _walk(b, rng, n_symbols, head.end_s + head.join_gap_s, cfg)
    u = keys.stream(keys.PAYLOAD, "pitch", key, nonce, cfg).random(n_symbols)
    return _layout(data, covers, end, gap, segments, u, pool, len(head.slots), 0, PAYLOAD)


def frame_layout(frame: format2.Frame, key: str, b: Bank, pool: np.ndarray, cfg: dict | None = None) -> tuple[Layout, Layout]:
    """(header layout, payload layout) of a frame."""
    cfg = cfg or default_config()
    head = header_layout(key, b, pool, cfg)
    return head, payload_layout(key, frame.nonce, len(frame.payload_symbols), head, b, pool, cfg)
