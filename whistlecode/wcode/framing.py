"""Message <-> frame <-> 4-bit whistle symbols (PLAN.md section 4.2).

A frame on the air is

    n_preamble signature whistles | header whistles | payload whistles

- header  = RS(2 + header_parity, 2) over [length, nonce] XOR the header mask (key only)
- payload = RS(k + nsym, k) over (message + CRC-16) XOR the payload mask (key + nonce), k = length + 2,
            nsym = max(payload_parity_min, ceil(k * payload_parity_ratio))

Every codeword byte becomes two 4-bit symbols, high nibble first; one symbol is one whistle. The preamble carries no
symbols (the transmitter adds the signature whistles). ERASED (-1) marks a whistle the receiver missed or could not
classify; a byte with an erased half goes to Reed-Solomon as erased.
"""
from __future__ import annotations

import binascii
from dataclasses import dataclass

import numpy as np

from . import fec
from .config import default_config, payload_parity
from .keys import HEADER, PAYLOAD, check_key, check_nonce, mask, new_nonce

ERASED = -1


class FramingError(ValueError):
    """The input cannot be framed (empty, too long, wrong symbol count)."""


class DecodeError(Exception):
    """The received symbols do not give a message. stage: header_fec, header_invalid, payload_fec or crc."""

    def __init__(self, stage: str, detail: str):
        super().__init__(f"{stage}: {detail}")
        self.stage = stage
        self.detail = detail


# ---------------------------------------------------------------------------------------------- byte helpers
def crc16(data: bytes) -> int:
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflection, no final XOR ("123456789" -> 0x29B1)."""
    return binascii.crc_hqx(bytes(data), 0xFFFF)


def xor(a: bytes, b: bytes) -> bytes:
    if len(a) != len(b):
        raise ValueError("xor needs equal lengths")
    return bytes(x ^ y for x, y in zip(a, b))


def bytes_to_symbols(data: bytes) -> np.ndarray:
    """Each byte -> two symbols 0-15, high nibble first."""
    b = np.frombuffer(bytes(data), dtype=np.uint8).astype(np.int16)
    return np.stack([b >> 4, b & 0x0F], axis=1).reshape(-1)


def symbols_to_bytes(symbols) -> tuple[bytes, list[int]]:
    """Pairs of symbols -> bytes, plus the positions of bytes with at least one ERASED half (written as 0)."""
    s = np.asarray(symbols, dtype=np.int64).reshape(-1)
    if len(s) % 2:
        raise FramingError(f"an even number of symbols is needed, got {len(s)}")
    if len(s) and (s.min() < ERASED or s.max() > 15):
        raise FramingError("symbols must be 0-15, or -1 for an erased whistle")
    pairs = s.reshape(-1, 2)
    erased = np.where((pairs == ERASED).any(axis=1))[0]
    vals = np.where(pairs == ERASED, 0, pairs)
    out = (vals[:, 0] << 4) | vals[:, 1]
    return bytes(out.astype(np.uint8).tolist()), erased.tolist()


# ---------------------------------------------------------------------------------------------- sizes
def header_bytes(cfg: dict) -> int:
    return int(cfg["framing"]["header_data_bytes"]) + int(cfg["fec"]["header_parity"])


def payload_k(length: int, cfg: dict) -> int:
    return int(length) + int(cfg["framing"]["crc_bytes"])


def payload_bytes(length: int, cfg: dict) -> int:
    k = payload_k(length, cfg)
    return k + payload_parity(k, cfg)


def frame_counts(length: int, cfg: dict | None = None) -> dict:
    """Whistles in a frame with a payload of `length` bytes."""
    cfg = cfg or default_config()
    pre = int(cfg["framing"]["n_preamble"])
    hdr = 2 * header_bytes(cfg)
    pay = 2 * payload_bytes(length, cfg)
    return {"preamble": pre, "header": hdr, "payload": pay, "total": pre + hdr + pay}


def _check_length(length: int, cfg: dict) -> int:
    lo, hi = int(cfg["framing"]["min_payload_bytes"]), int(cfg["framing"]["max_payload_bytes"])
    if not lo <= length <= hi:
        raise FramingError(f"the message is {length} bytes; {lo}-{hi} bytes can be sent")
    return length


# ---------------------------------------------------------------------------------------------- encoding
@dataclass(frozen=True)
class Frame:
    payload: bytes
    nonce: int
    header_codeword: bytes
    payload_codeword: bytes
    n_preamble: int

    @property
    def length(self) -> int:
        return len(self.payload)

    @property
    def header_symbols(self) -> np.ndarray:
        return bytes_to_symbols(self.header_codeword)

    @property
    def payload_symbols(self) -> np.ndarray:
        return bytes_to_symbols(self.payload_codeword)

    @property
    def symbols(self) -> np.ndarray:
        """Header then payload symbols: every whistle after the preamble, in order."""
        return np.concatenate([self.header_symbols, self.payload_symbols])

    @property
    def n_whistles(self) -> int:
        return self.n_preamble + len(self.symbols)


def message_bytes(message: bytes | str, cfg: dict | None = None) -> bytes:
    cfg = cfg or default_config()
    if isinstance(message, str):
        data = message.encode(cfg["framing"]["text_encoding"])
    elif isinstance(message, (bytes, bytearray)):
        data = bytes(message)
    else:
        raise FramingError(f"a message is text or bytes, not {type(message).__name__}")
    _check_length(len(data), cfg)
    return data


def encode_header(length: int, nonce: int, key: str, cfg: dict | None = None) -> bytes:
    cfg = cfg or default_config()
    data = bytes([_check_length(length, cfg), check_nonce(nonce)])
    return fec.encode(xor(data, mask(HEADER, key, len(data), cfg=cfg)), int(cfg["fec"]["header_parity"]))


def encode_payload(payload: bytes, nonce: int, key: str, cfg: dict | None = None) -> bytes:
    cfg = cfg or default_config()
    payload = message_bytes(payload, cfg)
    data = payload + crc16(payload).to_bytes(2, "big")
    k = len(data)
    return fec.encode(xor(data, mask(PAYLOAD, key, k, nonce, cfg)), payload_parity(k, cfg))


def encode(message: bytes | str, key: str, nonce: int | None = None, cfg: dict | None = None) -> Frame:
    """Message (text or bytes) -> Frame. A fresh random nonce is drawn unless one is given."""
    cfg = cfg or default_config()
    check_key(key)
    payload = message_bytes(message, cfg)
    nonce = new_nonce() if nonce is None else check_nonce(nonce)
    return Frame(payload=payload, nonce=nonce,
                 header_codeword=encode_header(len(payload), nonce, key, cfg),
                 payload_codeword=encode_payload(payload, nonce, key, cfg),
                 n_preamble=int(cfg["framing"]["n_preamble"]))


# ---------------------------------------------------------------------------------------------- decoding
@dataclass(frozen=True)
class Header:
    length: int
    nonce: int
    n_errors: int
    n_erasures: int


@dataclass(frozen=True)
class Message:
    payload: bytes
    nonce: int
    n_errors: int        # payload bytes repaired that were wrong and not marked as erased
    n_erasures: int      # payload bytes restored from erasures

    @property
    def text(self) -> str | None:
        """The payload as UTF-8 text, or None when it is not valid UTF-8 (a binary message)."""
        try:
            return self.payload.decode("utf-8")
        except UnicodeDecodeError:
            return None


def _fec_decode(symbols, nsym: int, stage: str, cfg: dict) -> fec.FecResult:
    received, erased = symbols_to_bytes(symbols)
    try:
        return fec.decode(received, nsym, erased, fill=int(cfg["fec"]["erased_fill"]))
    except fec.FecError as e:
        raise DecodeError(stage, str(e)) from e


def decode_header(symbols, key: str, cfg: dict | None = None) -> Header:
    """The header's whistle symbols -> length and nonce."""
    cfg = cfg or default_config()
    check_key(key)
    n = 2 * header_bytes(cfg)
    if len(symbols) != n:
        raise FramingError(f"the header has {n} symbols, got {len(symbols)}")
    r = _fec_decode(symbols, int(cfg["fec"]["header_parity"]), "header_fec", cfg)
    length, nonce = xor(r.data, mask(HEADER, key, len(r.data), cfg=cfg))
    lo, hi = int(cfg["framing"]["min_payload_bytes"]), int(cfg["framing"]["max_payload_bytes"])
    if not lo <= length <= hi:
        raise DecodeError("header_invalid", f"length {length} is outside {lo}-{hi}")
    return Header(length=length, nonce=nonce, n_errors=r.n_errors, n_erasures=r.n_erasures)


def decode_payload(symbols, header: Header, key: str, cfg: dict | None = None) -> Message:
    """The payload's whistle symbols -> message, checked by its CRC."""
    cfg = cfg or default_config()
    n = 2 * payload_bytes(header.length, cfg)
    if len(symbols) != n:
        raise FramingError(f"a {header.length}-byte payload has {n} symbols, got {len(symbols)}")
    k = payload_k(header.length, cfg)
    r = _fec_decode(symbols, payload_parity(k, cfg), "payload_fec", cfg)
    data = xor(r.data, mask(PAYLOAD, key, k, header.nonce, cfg))
    payload, crc = data[:-2], int.from_bytes(data[-2:], "big")
    if crc16(payload) != crc:
        raise DecodeError("crc", "the repaired payload fails its CRC")
    return Message(payload=payload, nonce=header.nonce, n_errors=r.n_errors, n_erasures=r.n_erasures)


def decode(symbols, key: str, cfg: dict | None = None) -> tuple[Header, Message]:
    """Header + payload symbols (everything after the preamble) -> (Header, Message).

    Symbols past the frame's end are ignored; missing ones at the end count as erased."""
    cfg = cfg or default_config()
    s = np.asarray(symbols, dtype=np.int64).reshape(-1)
    nh = 2 * header_bytes(cfg)
    if len(s) < nh:
        s = np.concatenate([s, np.full(nh - len(s), ERASED)])
    header = decode_header(s[:nh], key, cfg)
    npay = 2 * payload_bytes(header.length, cfg)
    pay = s[nh:nh + npay]
    if len(pay) < npay:
        pay = np.concatenate([pay, np.full(npay - len(pay), ERASED)])
    return header, decode_payload(pay, header, key, cfg)
