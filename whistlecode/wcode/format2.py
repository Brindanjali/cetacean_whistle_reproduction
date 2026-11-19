"""Message format v2 (PLAN.md section 4.6): text <-> 6-bit whistle symbols.

A frame on the air is

    3 signature whistles | 7 header symbols | payload symbols

- text:    5 bits per character when every character is in the 32-character alphabet (compact mode), otherwise raw UTF-8
- header:  mode (1 bit), spare (1 bit, always 0), length (8 bits), nonce (8 bits) = 3 symbols, scrambled with the key-only
           stream, then RS(7, 3) over GF(64)
- payload: message bits + CRC-16 + zero padding, cut into 6-bit symbols, scrambled with the key-and-nonce stream, split
           into blocks of at most 63 symbols with parity max(8, ceil(data / 2)) each, then interleaved in time

One symbol is one whistle: the high 4 bits choose the shape and the low 2 bits choose the pitch. ERASED (-1) marks a whistle
the receiver missed or could not read.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass

import numpy as np

from . import fec, framing
from .config import default_config
from .framing import DecodeError, FramingError
from .keys import HEADER, PAYLOAD, check_key, check_nonce, mask, new_nonce

ERASED = framing.ERASED
COMPACT, RAW = 0, 1
C_EXP = 6
SYMBOL_BITS = 6
CRC_BITS = 16


# ---------------------------------------------------------------------------------------------- bits
def to_bits(values, width: int) -> np.ndarray:
    """Integers -> bits, most significant first."""
    v = np.asarray(values, dtype=np.int64).reshape(-1)
    return ((v[:, None] >> np.arange(width - 1, -1, -1)) & 1).astype(np.uint8).reshape(-1)


def from_bits(bits, width: int) -> np.ndarray:
    """Bits, most significant first -> integers. The number of bits must be a multiple of width."""
    b = np.asarray(bits, dtype=np.int64).reshape(-1)
    if len(b) % width:
        raise ValueError(f"{len(b)} bits are not a multiple of {width}")
    return (b.reshape(-1, width) << np.arange(width - 1, -1, -1)).sum(axis=1)


def _packed(bits: np.ndarray) -> bytes:
    return np.packbits(bits).tobytes()


# ---------------------------------------------------------------------------------------------- sizes
def _symbol_mask(part: str, key: str, n: int, nonce: int | None, cfg: dict) -> np.ndarray:
    """n scrambler symbols: the low 6 bits of each mask byte."""
    return np.frombuffer(mask(part, key, n, nonce, cfg), dtype=np.uint8).astype(np.int64) & 0x3F


def _char_bits(mode: int) -> int:
    return 5 if mode == COMPACT else 8


def data_symbols(mode: int, length: int) -> int:
    """Symbols holding the message and its CRC, before parity."""
    return math.ceil((_char_bits(mode) * int(length) + CRC_BITS) / SYMBOL_BITS)


def parity_of(data: int, cfg: dict) -> int:
    f = cfg["format2"]
    return max(int(f["payload_parity_min"]), math.ceil(int(data) * float(f["payload_parity_ratio"])))


def blocks(n_data: int, cfg: dict | None = None) -> list[tuple[int, int]]:
    """(data symbols, parity symbols) of each code block: the fewest equal blocks that fit max_block_symbols."""
    cfg = cfg or default_config()
    top = int(cfg["format2"]["max_block_symbols"])
    b = 1
    while True:
        sizes = [n_data // b + (i < n_data % b) for i in range(b)]
        out = [(d, parity_of(d, cfg)) for d in sizes]
        if all(d + p <= top for d, p in out):
            return out
        b += 1


def payload_symbols(mode: int, length: int, cfg: dict | None = None) -> int:
    """Whistles in the payload of a message."""
    return sum(d + p for d, p in blocks(data_symbols(mode, length), cfg))


def air_order(lengths: list[int]) -> list[tuple[int, int]]:
    """(block, position) of each whistle in time: one symbol from each block in turn, so a burst of losses spreads out."""
    out = []
    for i in range(max(lengths, default=0)):
        out += [(b, i) for b, n in enumerate(lengths) if i < n]
    return out


# ---------------------------------------------------------------------------------------------- text <-> bits
def split_message(message: bytes | str, cfg: dict | None = None) -> tuple[int, int, np.ndarray]:
    """Message -> (mode, length, message bits). Text is never changed: lowercase letters make the message raw."""
    cfg = cfg or default_config()
    f = cfg["format2"]
    alphabet = f["alphabet"]
    if isinstance(message, str):
        if message and all(c in alphabet for c in message):
            mode, length = COMPACT, len(message)
            bits = to_bits([alphabet.index(c) for c in message], 5)
        else:
            raw = message.encode("utf-8")
            mode, length = RAW, len(raw)
            bits = to_bits(list(raw), 8)
    elif isinstance(message, (bytes, bytearray)):
        mode, length = RAW, len(message)
        bits = to_bits(list(bytes(message)), 8)
    else:
        raise FramingError(f"a message is text or bytes, not {type(message).__name__}")
    lo, hi = int(f["min_length"]), int(f["max_length"])
    if not lo <= length <= hi:
        unit = "characters" if mode == COMPACT else "bytes"
        raise FramingError(f"the message is {length} {unit}; {lo}-{hi} can be sent")
    return mode, length, bits


def _crc(mode: int, length: int, bits: np.ndarray) -> int:
    """CRC-16 over the mode, the length and the message bits."""
    return framing.crc16(bytes([mode, length]) + _packed(bits))


# ---------------------------------------------------------------------------------------------- encoding
@dataclass(frozen=True)
class Frame:
    mode: int
    length: int
    nonce: int
    header_symbols: np.ndarray      # 7 symbols
    payload_symbols: np.ndarray     # in the order they are played

    @property
    def symbols(self) -> np.ndarray:
        return np.concatenate([self.header_symbols, self.payload_symbols])


def encode_header(mode: int, length: int, key: str, nonce: int, cfg: dict | None = None) -> np.ndarray:
    cfg = cfg or default_config()
    f = cfg["format2"]
    bits = np.concatenate([to_bits([mode], 1), to_bits([0], 1), to_bits([length], 8), to_bits([check_nonce(nonce)], 8)])
    data = from_bits(bits, SYMBOL_BITS) ^ _symbol_mask(HEADER, check_key(key), int(f["header_data_symbols"]), None, cfg)
    return np.frombuffer(fec.encode(bytes(data.tolist()), int(f["header_parity"]), c_exp=C_EXP), dtype=np.uint8).astype(np.int64)


def encode_payload(mode: int, length: int, bits: np.ndarray, key: str, nonce: int, cfg: dict | None = None) -> np.ndarray:
    cfg = cfg or default_config()
    all_bits = np.concatenate([bits, to_bits([_crc(mode, length, bits)], CRC_BITS)])
    all_bits = np.concatenate([all_bits, np.zeros(-len(all_bits) % SYMBOL_BITS, dtype=np.uint8)])
    data = from_bits(all_bits, SYMBOL_BITS)
    data = data ^ _symbol_mask(PAYLOAD, key, len(data), nonce, cfg)
    words, start = [], 0
    for d, p in blocks(len(data), cfg):
        words.append(fec.encode(bytes(data[start:start + d].tolist()), p, c_exp=C_EXP))
        start += d
    return np.array([words[b][i] for b, i in air_order([len(w) for w in words])], dtype=np.int64)


def encode(message: bytes | str, key: str, nonce: int | None = None, cfg: dict | None = None) -> Frame:
    """Message -> Frame. A fresh random nonce is drawn unless one is given."""
    cfg = cfg or default_config()
    check_key(key)
    mode, length, bits = split_message(message, cfg)
    nonce = new_nonce() if nonce is None else check_nonce(nonce)
    return Frame(mode, length, nonce, encode_header(mode, length, key, nonce, cfg),
                 encode_payload(mode, length, bits, key, nonce, cfg))


@dataclass(frozen=True)
class Explained:
    """Every intermediate step of encode(), for showing how a message becomes whistles (the project page)."""
    frame: Frame
    message_bits: np.ndarray        # the text as bits
    char_bits: int                  # 5 (compact) or 8 (raw)
    crc: int
    pad_bits: int                   # zero bits that fill the last symbol
    plain: np.ndarray               # data symbols before scrambling (message + CRC + padding)
    scrambled: np.ndarray           # the same after the key-and-nonce scrambler
    blocks: list                    # (data, parity) of each code block
    payload_source: list            # per payload whistle in air order: (block, position, data symbol index or None = parity)


def explain(message: bytes | str, key: str, nonce: int, cfg: dict | None = None) -> Explained:
    """encode(), keeping each step. The frame is exactly the one encode() makes for the same message, key and nonce."""
    cfg = cfg or default_config()
    check_key(key)
    nonce = check_nonce(nonce)
    mode, length, bits = split_message(message, cfg)
    crc = _crc(mode, length, bits)
    all_bits = np.concatenate([bits, to_bits([crc], CRC_BITS)])
    pad = -len(all_bits) % SYMBOL_BITS
    plain = from_bits(np.concatenate([all_bits, np.zeros(pad, dtype=np.uint8)]), SYMBOL_BITS)
    scrambled = plain ^ _symbol_mask(PAYLOAD, key, len(plain), nonce, cfg)
    plan = blocks(len(plain), cfg)
    first = np.cumsum([0] + [d for d, _ in plan])
    source = [(b, i, int(first[b] + i) if i < plan[b][0] else None) for b, i in air_order([d + p for d, p in plan])]
    frame = Frame(mode, length, nonce, encode_header(mode, length, key, nonce, cfg), encode_payload(mode, length, bits, key, nonce, cfg))
    return Explained(frame, bits, _char_bits(mode), crc, pad, plain, scrambled, plan, source)


# ---------------------------------------------------------------------------------------------- decoding
@dataclass(frozen=True)
class Header:
    mode: int
    length: int
    nonce: int
    n_errors: int
    n_erasures: int


@dataclass(frozen=True)
class Message:
    mode: int
    payload: bytes                  # compact messages: their text as ASCII
    nonce: int
    n_errors: int                   # whistles repaired that were wrong and not marked as lost
    n_erasures: int                 # whistles restored after being marked as lost

    @property
    def text(self) -> str | None:
        """The message as text, or None when it is not valid UTF-8 (a binary message)."""
        try:
            return self.payload.decode("utf-8")
        except UnicodeDecodeError:
            return None


def _repair(received: np.ndarray, nsym: int, stage: str) -> fec.FecResult:
    erased = np.where(received == ERASED)[0].tolist()
    try:
        return fec.decode(bytes(np.where(received == ERASED, 0, received).tolist()), nsym, erased, c_exp=C_EXP)
    except fec.FecError as e:
        raise DecodeError(stage, str(e)) from e


def repairs(word: np.ndarray, nsym: int, doubt: np.ndarray | None, spare: int, stage: str) -> list[fec.FecResult]:
    """Every distinct repair of one code block, most trusted first.

    The block is first repaired as received. If doubt is given (higher = less sure of that whistle), the most doubtful whistles
    are then treated as lost, one more at a time: a wrong whistle that is marked lost costs half as much to repair. At least
    `spare` parity symbols stay unused, so a repair can still be told apart from noise."""
    out, seen, last = [], set(), None
    known = np.where(word != ERASED)[0]
    order = known if doubt is None else known[np.argsort(-doubt[known], kind="stable")]
    n_lost = len(word) - len(known)
    extra_max = 0 if doubt is None else max(0, nsym - spare - n_lost)
    for extra in range(extra_max + 1):
        trial = word.copy()
        trial[order[:extra]] = ERASED
        try:
            r = _repair(trial, nsym, stage)
        except DecodeError as e:
            last = e
            continue
        if r.codeword not in seen:
            seen.add(r.codeword)
            out.append(r)
    if not out:
        raise last
    return out


def _check_symbols(symbols, n: int, what: str) -> np.ndarray:
    s = np.asarray(symbols, dtype=np.int64).reshape(-1)
    if len(s) != n:
        raise FramingError(f"the {what} has {n} symbols, got {len(s)}")
    if len(s) and (s.min() < ERASED or s.max() > 63):
        raise FramingError("symbols must be 0-63, or -1 for a lost whistle")
    return s


def _damage(word: np.ndarray, r: fec.FecResult) -> tuple[int, int]:
    """(whistles that were wrong, whistles that were lost) in a received block, judged by its repair."""
    lost = word == ERASED
    fixed = np.frombuffer(r.codeword, dtype=np.uint8).astype(np.int64)
    return int(((word != fixed) & ~lost).sum()), int(lost.sum())


def header_candidates(symbols, key: str, cfg: dict | None = None, doubt=None) -> list[Header]:
    """Every valid reading of the header's whistles, most trusted first. Raises DecodeError when there is none."""
    cfg = cfg or default_config()
    f = cfg["format2"]
    k, nsym = int(f["header_data_symbols"]), int(f["header_parity"])
    word = _check_symbols(symbols, k + nsym, "header")
    doubt = None if doubt is None else np.asarray(doubt, dtype=np.float64)
    lo, hi = int(f["min_length"]), int(f["max_length"])
    out, why = [], "no valid header"
    for r in repairs(word, nsym, doubt, int(f["soft_spare_parity"]), "header_fec"):
        data = np.frombuffer(r.data, dtype=np.uint8).astype(np.int64) ^ _symbol_mask(HEADER, check_key(key), k, None, cfg)
        bits = to_bits(data, SYMBOL_BITS)
        mode, spare = int(bits[0]), int(bits[1])
        length, nonce = int(from_bits(bits[2:10], 8)[0]), int(from_bits(bits[10:18], 8)[0])
        if spare != 0:
            why = "the spare bit is set"
        elif not lo <= length <= hi:
            why = f"length {length} is outside {lo}-{hi}"
        else:
            out.append(Header(mode, length, nonce, *_damage(word, r)))
    if not out:
        raise DecodeError("header_invalid", why)
    return out


def decode_header(symbols, key: str, cfg: dict | None = None, doubt=None) -> Header:
    """The most trusted valid reading of the header's whistles."""
    return header_candidates(symbols, key, cfg, doubt)[0]


def _message_from(data: list[np.ndarray], header: Header, key: str, cfg: dict) -> bytes | None:
    """The message held by repaired data symbols, or None when its CRC fails."""
    n_data = data_symbols(header.mode, header.length)
    clear = np.concatenate(data) ^ _symbol_mask(PAYLOAD, key, n_data, header.nonce, cfg)
    bits = to_bits(clear, SYMBOL_BITS)
    n_msg = _char_bits(header.mode) * header.length
    msg_bits, crc_bits, pad = bits[:n_msg], bits[n_msg:n_msg + CRC_BITS], bits[n_msg + CRC_BITS:]
    if pad.any() or int(from_bits(crc_bits, CRC_BITS)[0]) != _crc(header.mode, header.length, msg_bits):
        return None
    if header.mode == COMPACT:
        alphabet = cfg["format2"]["alphabet"]
        return "".join(alphabet[int(c)] for c in from_bits(msg_bits, 5)).encode("ascii")
    return bytes(from_bits(msg_bits, 8).astype(np.uint8).tolist())


def decode_payload(symbols, header: Header, key: str, cfg: dict | None = None, doubt=None) -> Message:
    """The payload's whistle symbols, in the order they were played -> the message, checked by its CRC.

    With doubt (one value per whistle, higher = less sure), blocks that cannot be repaired as received are retried with their
    most doubtful whistles treated as lost. At most soft_max_combinations combinations are checked against the CRC."""
    cfg = cfg or default_config()
    f = cfg["format2"]
    plan = blocks(data_symbols(header.mode, header.length), cfg)
    s = _check_symbols(symbols, sum(d + p for d, p in plan), "payload")
    order = air_order([d + p for d, p in plan])
    words = [np.full(d + p, ERASED, dtype=np.int64) for d, p in plan]
    doubts = [np.zeros(d + p) for d, p in plan]
    given = None if doubt is None else np.asarray(doubt, dtype=np.float64)
    for n, (b, i) in enumerate(order):
        words[b][i] = s[n]
        if given is not None:
            doubts[b][i] = given[n]
    options = [repairs(w, p, None if given is None else u, int(f["soft_spare_parity"]), "payload_fec")
               for w, u, (_, p) in zip(words, doubts, plan)]
    for combo in itertools.islice(itertools.product(*options), int(f["soft_max_combinations"])):
        payload = _message_from([np.frombuffer(r.data, dtype=np.uint8).astype(np.int64) for r in combo], header, key, cfg)
        if payload is not None:
            damage = [_damage(w, r) for w, r in zip(words, combo)]
            return Message(header.mode, payload, header.nonce, sum(d[0] for d in damage), sum(d[1] for d in damage))
    raise DecodeError("crc", "the repaired payload fails its CRC")
