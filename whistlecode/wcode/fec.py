"""Reed-Solomon over GF(2^8) with erasures, through reedsolo 1.7.0 (PLAN.md section 4.2).

One call handles one codeword: k data bytes followed by nsym parity bytes, with k + nsym <= 255 (a shortened code).
It repairs any mix of e wrong bytes and f erased bytes with 2e + f <= nsym. Beyond that it raises FecError, or in
rare cases returns a different valid codeword; the payload CRC catches those.

The rest of WhistleCode calls only encode() and decode(), so the library can be replaced without touching them.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass

import reedsolo

RS_MAX_N = 255


class FecError(Exception):
    """The codeword could not be repaired."""


@dataclass(frozen=True)
class FecResult:
    data: bytes          # the k data bytes
    codeword: bytes      # the repaired codeword (data + parity)
    n_errors: int        # bytes that were wrong and not marked as erased
    n_erasures: int      # bytes marked as erased


@functools.lru_cache(maxsize=None)
def _codec(nsym: int) -> reedsolo.RSCodec:
    return reedsolo.RSCodec(nsym, nsize=RS_MAX_N)


def _check_nsym(nsym: int) -> int:
    if isinstance(nsym, bool) or not isinstance(nsym, int) or not 1 <= nsym < RS_MAX_N:
        raise ValueError(f"nsym must be an integer 1-254, got {nsym!r}")
    return nsym


def encode(data: bytes, nsym: int) -> bytes:
    """data (k bytes) -> codeword (k + nsym bytes), systematic: the data comes first, unchanged."""
    _check_nsym(nsym)
    data = bytes(data)
    if not data:
        raise ValueError("nothing to encode")
    if len(data) + nsym > RS_MAX_N:
        raise ValueError(f"{len(data)} data + {nsym} parity bytes exceed one codeword ({RS_MAX_N})")
    return bytes(_codec(nsym).encode(data))


def decode(received: bytes, nsym: int, erase_pos=(), fill: int = 0) -> FecResult:
    """Repair one codeword. erase_pos lists byte positions known to be lost (their values are ignored)."""
    _check_nsym(nsym)
    buf = bytearray(received)
    n = len(buf)
    if not nsym < n <= RS_MAX_N:
        raise ValueError(f"a codeword with {nsym} parity bytes must be {nsym + 1}-{RS_MAX_N} bytes long, got {n}")
    erased = sorted({int(p) for p in erase_pos})
    if erased and not (0 <= erased[0] and erased[-1] < n):
        raise ValueError(f"erasure positions must lie in 0-{n - 1}")
    if len(erased) > nsym:
        raise FecError(f"{len(erased)} erased bytes, more than the {nsym} parity bytes can restore")
    for p in erased:
        buf[p] = fill
    try:
        data, codeword, _ = _codec(nsym).decode(buf, erase_pos=erased or None)
    except reedsolo.ReedSolomonError as e:
        raise FecError(str(e)) from e
    erased_set = set(erased)
    n_err = sum(1 for i, (a, b) in enumerate(zip(buf, codeword)) if a != b and i not in erased_set)
    return FecResult(bytes(data), bytes(codeword), n_err, len(erased))
