"""Shared key (and per-message nonce) -> byte masks and random streams (PLAN.md section 4.1).

Every value is derived from SHA-256 over length-prefixed parts

    domain | part ("header" or "payload") | stream name | key (UTF-8) [| nonce byte]

so the streams are independent of each other, and adding a stream later never shifts an existing one.

- "header" streams use the key only: the receiver must read them before it knows the nonce.
- "payload" streams use the key and the nonce, so messages under one key do not share a rhythm or a scrambler.

[DECISION] Byte masks (the scrambler) come from SHA-256 in counter mode and never depend on the NumPy version.
           Continuous draws (timing, pitch, variation) come from NumPy PCG64 generators seeded from the digest.
"""
from __future__ import annotations

import hashlib
import secrets

import numpy as np

from .config import default_config

HEADER = "header"
PAYLOAD = "payload"


def check_key(key: str) -> str:
    if not isinstance(key, str) or not key:
        raise ValueError("the key must be a non-empty string")
    return key


def check_nonce(nonce: int) -> int:
    if isinstance(nonce, bool) or not isinstance(nonce, (int, np.integer)) or not 0 <= int(nonce) <= 255:
        raise ValueError(f"the nonce must be an integer 0-255, got {nonce!r}")
    return int(nonce)


def new_nonce() -> int:
    """A fresh random nonce for one message (operating-system randomness)."""
    return secrets.randbelow(256)


def _names(part: str, cfg: dict) -> list[str]:
    if part == HEADER:
        return list(cfg["keys"]["header_streams"])
    if part == PAYLOAD:
        return list(cfg["keys"]["payload_streams"])
    raise ValueError(f"part must be {HEADER!r} or {PAYLOAD!r}, got {part!r}")


def seed(part: str, name: str, key: str, nonce: int | None = None, cfg: dict | None = None) -> bytes:
    """32-byte SHA-256 seed of one stream. Header streams take no nonce; payload streams need one."""
    cfg = cfg or default_config()
    if name not in _names(part, cfg):
        raise ValueError(f"unknown {part} stream {name!r}; config.toml [keys] lists {_names(part, cfg)}")
    if part == HEADER and nonce is not None:
        raise ValueError("header streams depend on the key only; pass nonce=None")
    if part == PAYLOAD and nonce is None:
        raise ValueError("payload streams need the message nonce")
    parts = [cfg["keys"]["domain"].encode("utf-8"), part.encode("ascii"), name.encode("ascii"),
             check_key(key).encode("utf-8")]
    if nonce is not None:
        parts.append(bytes([check_nonce(nonce)]))
    h = hashlib.sha256()
    for p in parts:
        h.update(len(p).to_bytes(4, "big"))
        h.update(p)
    return h.digest()


def mask(part: str, key: str, n: int, nonce: int | None = None, cfg: dict | None = None) -> bytes:
    """n scrambler bytes: SHA-256(seed || counter) blocks, counter = 0, 1, ..."""
    if n < 0:
        raise ValueError("n must be >= 0")
    s = seed(part, "scrambler", key, nonce, cfg)
    out = bytearray()
    counter = 0
    while len(out) < n:
        out += hashlib.sha256(s + counter.to_bytes(8, "big")).digest()
        counter += 1
    return bytes(out[:n])


def stream(part: str, name: str, key: str, nonce: int | None = None, cfg: dict | None = None) -> np.random.Generator:
    """A fresh NumPy generator for one named stream (same key and nonce -> same draws)."""
    return np.random.Generator(np.random.PCG64(int.from_bytes(seed(part, name, key, nonce, cfg), "big")))
