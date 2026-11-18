"""Reed-Solomon with erasures, through reedsolo 1.7.0 (PLAN.md sections 4.2 and 4.6).

Format v1 uses GF(2^8), where one symbol is a byte. Format v2 passes c_exp=6 for GF(2^6), where one symbol is one whistle.

One call handles one codeword: k data symbols followed by nsym parity symbols, with k + nsym <= 2^c_exp - 1 (a shortened
code). It repairs any mix of e wrong symbols and f erased symbols with 2e + f <= nsym. Beyond that it raises FecError, or
in rare cases returns a different valid codeword; the payload CRC catches those.

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
    data: bytes          # the k data symbols
    codeword: bytes      # the repaired codeword (data + parity)
    n_errors: int        # symbols that were wrong and not marked as erased
    n_erasures: int      # symbols marked as erased


@functools.lru_cache(maxsize=None)
def _codec(nsym: int, c_exp: int = 8) -> reedsolo.RSCodec:
    return reedsolo.RSCodec(nsym, nsize=2 ** c_exp - 1, c_exp=c_exp)


def _check_nsym(nsym: int, c_exp: int = 8) -> int:
    top = 2 ** c_exp - 2
    if isinstance(nsym, bool) or not isinstance(nsym, int) or not 1 <= nsym <= top:
        raise ValueError(f"nsym must be an integer 1-{top}, got {nsym!r}")
    return nsym


def _check_symbols(values: bytes, c_exp: int) -> None:
    if c_exp != 8 and values and max(values) >= 2 ** c_exp:
        raise ValueError(f"symbols must be below {2 ** c_exp}, got {max(values)}")


def encode(data: bytes, nsym: int, c_exp: int = 8) -> bytes:
    """data (k symbols) -> codeword (k + nsym symbols), systematic: the data comes first, unchanged."""
    _check_nsym(nsym, c_exp)
    data = bytes(data)
    if not data:
        raise ValueError("nothing to encode")
    _check_symbols(data, c_exp)
    max_n = 2 ** c_exp - 1
    if len(data) + nsym > max_n:
        raise ValueError(f"{len(data)} data + {nsym} parity symbols exceed one codeword ({max_n})")
    return bytes(_codec(nsym, c_exp).encode(data))


def decode(received: bytes, nsym: int, erase_pos=(), fill: int = 0, c_exp: int = 8) -> FecResult:
    """Repair one codeword. erase_pos lists symbol positions known to be lost (their values are ignored)."""
    _check_nsym(nsym, c_exp)
    buf = bytearray(received)
    n = len(buf)
    max_n = 2 ** c_exp - 1
    if not nsym < n <= max_n:
        raise ValueError(f"a codeword with {nsym} parity symbols must be {nsym + 1}-{max_n} symbols long, got {n}")
    erased = sorted({int(p) for p in erase_pos})
    if erased and not (0 <= erased[0] and erased[-1] < n):
        raise ValueError(f"erasure positions must lie in 0-{n - 1}")
    if len(erased) > nsym:
        raise FecError(f"{len(erased)} erased symbols, more than the {nsym} parity symbols can restore")
    for p in erased:
        buf[p] = fill
    _check_symbols(bytes(buf), c_exp)
    try:
        data, codeword, _ = _codec(nsym, c_exp).decode(buf, erase_pos=erased or None)
    except reedsolo.ReedSolomonError as e:
        raise FecError(str(e)) from e
    erased_set = set(erased)
    n_err = sum(1 for i, (a, b) in enumerate(zip(buf, codeword)) if a != b and i not in erased_set)
    return FecResult(bytes(data), bytes(codeword), n_err, len(erased))
