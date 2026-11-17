"""framing.py: message <-> frame <-> whistle symbols, including damaged whistles (PLAN.md section 4.2)."""
import random

import numpy as np
import pytest

from wcode import framing
from wcode.config import payload_parity
from wcode.framing import ERASED, DecodeError, FramingError


# ---------------------------------------------------------------------------------------------- helpers
def test_crc16_check_value():
    assert framing.crc16(b"123456789") == 0x29B1          # CRC-16/CCITT-FALSE check value


def test_symbols_high_nibble_first():
    assert framing.bytes_to_symbols(b"\xab\x0f").tolist() == [10, 11, 0, 15]
    assert framing.symbols_to_bytes([10, 11, 0, 15]) == (b"\xab\x0f", [])


def test_erased_half_erases_the_byte():
    data, erased = framing.symbols_to_bytes([10, ERASED, ERASED, 15, 1, 2])
    assert erased == [0, 1] and data[2] == 0x12


@pytest.mark.parametrize("symbols", [[1, 2, 3], [16, 0], [-2, 0]])
def test_symbols_to_bytes_rejects(symbols):
    with pytest.raises(FramingError):
        framing.symbols_to_bytes(symbols)


# ---------------------------------------------------------------------------------------------- sizes
@pytest.mark.parametrize("length, total", [(2, 39), (20, 81), (140, 441)])
def test_frame_counts_match_the_plan(cfg, length, total):
    c = framing.frame_counts(length, cfg)
    assert c["preamble"] == 3 and c["header"] == 12 and c["total"] == total


def test_message_length_limits(cfg):
    framing.encode("x" * 140, "k", 0, cfg)
    framing.encode("é" * 70, "k", 0, cfg)                  # 140 UTF-8 bytes
    for bad in ("", "x" * 141, "é" * 71):
        with pytest.raises(FramingError):
            framing.encode(bad, "k", 0, cfg)


# ---------------------------------------------------------------------------------------------- encoding
def test_known_frame(cfg):
    fr = framing.encode("HI", "reef42", 7, cfg)
    assert fr.header_codeword.hex() == "eb0b3d125a95"
    assert fr.payload_codeword.hex() == "45a3d347707945726b8a3c91"
    assert fr.n_whistles == 39 and len(fr.symbols) == 36
    assert fr.symbols.min() >= 0 and fr.symbols.max() <= 15


def test_random_nonce_when_not_given(cfg):
    nonces = {framing.encode("HI", "k", cfg=cfg).nonce for _ in range(200)}
    assert len(nonces) > 50


def test_scrambler_hides_repetition(cfg):
    fr = framing.encode("A" * 24, "k", 1, cfg)
    assert len(set(fr.payload_symbols[:48].tolist())) >= 12     # "AAAA..." does not become one repeated whistle
    assert not np.array_equal(fr.payload_symbols, framing.encode("A" * 24, "k", 2, cfg).payload_symbols)
    assert not np.array_equal(fr.header_symbols, framing.encode("A" * 24, "k2", 1, cfg).header_symbols)


def test_deterministic(cfg):
    a, b = framing.encode("MEET AT DAWN", "k", 9, cfg), framing.encode("MEET AT DAWN", "k", 9, cfg)
    assert a == b


# ---------------------------------------------------------------------------------------------- decoding
@pytest.mark.parametrize("message", ["HI", "MEET AT DAWN", "café ☕ 🐋", "x" * 140])
def test_round_trip_text(cfg, message):
    fr = framing.encode(message, "reef42", 200, cfg)
    header, msg = framing.decode(fr.symbols, "reef42", cfg)
    assert (header.length, header.nonce) == (len(message.encode()), 200)
    assert msg.text == message and msg.n_errors == 0 and msg.n_erasures == 0


def test_round_trip_binary(cfg):
    payload = bytes([0xFF, 0xFE, 0x00, 0x80]) + bytes(range(100))
    _, msg = framing.decode(framing.encode(payload, "k", 0, cfg).symbols, "k", cfg)
    assert msg.payload == payload and msg.text is None


def byte_damage(sent, got):
    a, b = np.asarray(sent).reshape(-1, 2), np.asarray(got).reshape(-1, 2)
    erased = (b == ERASED).any(1)
    return int(((~erased) & (a != b).any(1)).sum()), int(erased.sum())


def damage(symbols, n_wrong, n_erased, rng):
    got = symbols.copy()
    pos = rng.sample(range(len(got)), n_wrong + n_erased)
    for p in pos[:n_wrong]:
        got[p] = (got[p] + rng.randint(1, 15)) % 16
    for p in pos[n_wrong:]:
        got[p] = ERASED
    return got


def test_damaged_whistles(cfg):
    """Random wrong and erased whistles: within the limits the exact message comes back; beyond them decoding
    fails with DecodeError, and a wrong message is never returned."""
    rng = random.Random(0)
    within = beyond = 0
    for trial in range(400):
        length = rng.randint(1, 140)
        payload = bytes(rng.getrandbits(8) for _ in range(length))
        fr = framing.encode(payload, f"key{trial}", rng.randint(0, 255), cfg)
        n = len(fr.symbols)
        n_wrong = rng.randint(0, n // 10)
        n_erased = rng.randint(0, n // 5)
        got = damage(fr.symbols, n_wrong, n_erased, rng)
        nh = len(fr.header_symbols)
        he, hf = byte_damage(fr.symbols[:nh], got[:nh])
        pe, pf = byte_damage(fr.symbols[nh:], got[nh:])
        ok_h = 2 * he + hf <= cfg["fec"]["header_parity"]
        ok_p = 2 * pe + pf <= payload_parity(length + 2, cfg)
        if ok_h and ok_p:
            within += 1
            header, msg = framing.decode(got, f"key{trial}", cfg)
            assert msg.payload == payload and (header.n_errors, header.n_erasures) == (he, hf)
            assert (msg.n_errors, msg.n_erasures) == (pe, pf)
        else:
            beyond += 1
            try:
                _, msg = framing.decode(got, f"key{trial}", cfg)
            except DecodeError:
                continue
            assert msg.payload == payload                # luck beyond the limit is fine; a wrong message is not
    assert within >= 100 and beyond >= 100               # both regimes were exercised


def test_header_limits(cfg):
    fr = framing.encode("HELLO", "k", 5, cfg)
    s = fr.symbols.copy()
    s[0:8] = ERASED                                      # 4 header bytes erased: the most RS(6, 2) restores
    assert framing.decode(s, "k", cfg)[1].text == "HELLO"
    s = fr.symbols.copy()
    s[0] = (s[0] + 1) % 16
    s[5] = (s[5] + 1) % 16                               # 2 header bytes wrong: also restorable
    assert framing.decode(s, "k", cfg)[1].text == "HELLO"
    s = fr.symbols.copy()
    s[0:10] = ERASED                                     # 5 header bytes erased: the header is lost
    with pytest.raises(DecodeError) as e:
        framing.decode(s, "k", cfg)
    assert e.value.stage == "header_fec"


def test_wrong_key_never_gives_the_message(cfg):
    fr = framing.encode("SECRET PLAN", "right", 33, cfg)
    for other in ("wrong", "Right", "right ", "r", "another key"):
        with pytest.raises(DecodeError):
            framing.decode(fr.symbols, other, cfg)


def test_missing_tail_counts_as_erased(cfg):
    fr = framing.encode("MEET AT DAWN", "k", 1, cfg)
    _, msg = framing.decode(fr.symbols[:-6], "k", cfg)   # the last 3 bytes never arrived
    assert msg.text == "MEET AT DAWN" and msg.n_erasures == 3


def test_extra_symbols_are_ignored(cfg):
    fr = framing.encode("MEET AT DAWN", "k", 1, cfg)
    _, msg = framing.decode(np.concatenate([fr.symbols, [3, 4, 5, 6]]), "k", cfg)
    assert msg.text == "MEET AT DAWN"


def test_symbol_count_checks(cfg):
    fr = framing.encode("HI", "k", 1, cfg)
    with pytest.raises(FramingError):
        framing.decode_header(fr.header_symbols[:-2], "k", cfg)
    header = framing.decode_header(fr.header_symbols, "k", cfg)
    with pytest.raises(FramingError):
        framing.decode_payload(fr.payload_symbols[:-2], header, "k", cfg)
