"""format2.py and the GF(64) code: text <-> 6-bit whistle symbols (PLAN.md section 4.6)."""
import numpy as np
import pytest

from wcode import fec, format2
from wcode.framing import DecodeError, FramingError


# ---------------------------------------------------------------------------------------------- GF(64)
def test_gf64_repairs_up_to_the_limit():
    rng = np.random.default_rng(0)
    for _ in range(200):
        k, nsym = int(rng.integers(3, 30)), int(rng.integers(4, 20))
        data = bytes(rng.integers(0, 64, k).tolist())
        word = bytearray(fec.encode(data, nsym, c_exp=6))
        n_err = int(rng.integers(0, nsym // 2 + 1))
        n_era = int(rng.integers(0, nsym - 2 * n_err + 1))
        pos = rng.choice(len(word), n_err + n_era, replace=False)
        for p in pos[:n_err]:
            word[p] ^= int(rng.integers(1, 64))
        r = fec.decode(bytes(word), nsym, pos[n_err:].tolist(), c_exp=6)
        assert r.data == data and r.n_errors == n_err and r.n_erasures == n_era


def test_gf64_and_gf256_can_alternate():
    a = fec.encode(b"\x01\x02\x03", 4, c_exp=6)
    b = fec.encode(b"\xf1\xf2\xf3", 4)
    assert fec.decode(a, 4, c_exp=6).data == b"\x01\x02\x03"
    assert fec.decode(b, 4).data == b"\xf1\xf2\xf3"
    assert fec.encode(b"\x01\x02\x03", 4, c_exp=6) == a


def test_gf64_refuses_values_that_do_not_fit():
    with pytest.raises(ValueError):
        fec.encode(bytes([64]), 4, c_exp=6)
    with pytest.raises(ValueError):
        fec.encode(bytes(60), 4, c_exp=6)


# ---------------------------------------------------------------------------------------------- sizes from the plan
@pytest.mark.parametrize("text, whistles", [("HI", 23), ("MEET AT DAWN", 31), ("A" * 20, 40), ("A" * 60, 90), ("A" * 140, 190)])
def test_whistle_counts_match_the_plan(cfg, text, whistles):
    fr = format2.encode(text, "k", 1, cfg)
    assert fr.mode == format2.COMPACT
    assert 3 + len(fr.symbols) == whistles


def test_blocks_fit_gf64(cfg):
    for mode in (format2.COMPACT, format2.RAW):
        for length in range(1, 141):
            plan = format2.blocks(format2.data_symbols(mode, length), cfg)
            assert all(d + p <= 63 and p >= 8 and p >= d / 2 for d, p in plan)
            assert sum(d for d, _ in plan) == format2.data_symbols(mode, length)


def test_air_order_visits_every_symbol_once():
    order = format2.air_order([5, 4, 4])
    assert len(order) == len(set(order)) == 13
    assert order[:4] == [(0, 0), (1, 0), (2, 0), (0, 1)]


# ---------------------------------------------------------------------------------------------- round trips
@pytest.mark.parametrize("message", ["HI", "MEET AT DAWN.", "A", "Z" * 140, "lower case", "café 東京", b"\x00\xff\x80"])
def test_round_trip(cfg, message):
    fr = format2.encode(message, "reef42", 200, cfg)
    h = format2.decode_header(fr.header_symbols, "reef42", cfg)
    assert (h.mode, h.length, h.nonce) == (fr.mode, fr.length, 200)
    m = format2.decode_payload(fr.payload_symbols, h, "reef42", cfg)
    assert m.payload == (message if isinstance(message, bytes) else message.encode("utf-8"))


def test_case_is_never_changed(cfg):
    assert format2.encode("Hi", "k", 1, cfg).mode == format2.RAW
    assert format2.encode("HI", "k", 1, cfg).mode == format2.COMPACT


def test_repairs_lost_and_wrong_whistles(cfg):
    rng = np.random.default_rng(3)
    fr = format2.encode("MEET AT DAWN", "k", 9, cfg)                     # 13 data + 8 parity symbols
    got = fr.payload_symbols.copy()
    pos = rng.choice(len(got), 6, replace=False)
    got[pos[:4]] = format2.ERASED
    got[pos[4]] = (got[pos[4]] + 1) % 64
    h = format2.decode_header(fr.header_symbols, "k", cfg)
    m = format2.decode_payload(got, h, "k", cfg)
    assert m.text == "MEET AT DAWN" and (m.n_errors, m.n_erasures) == (1, 4)


def test_header_survives_four_lost_whistles(cfg):
    fr = format2.encode("HI", "k", 77, cfg)
    got = fr.header_symbols.copy()
    got[[0, 2, 4, 6]] = format2.ERASED
    h = format2.decode_header(got, "k", cfg)
    assert (h.length, h.nonce, h.n_erasures) == (2, 77, 4)


def test_a_burst_of_losses_spreads_across_blocks(cfg):
    fr = format2.encode("A" * 140, "k", 5, cfg)                          # three blocks of 60
    got = fr.payload_symbols.copy()
    got[30:54] = format2.ERASED                                          # 8 per block: exactly the limit is 20
    h = format2.decode_header(fr.header_symbols, "k", cfg)
    assert format2.decode_payload(got, h, "k", cfg).text == "A" * 140


def test_too_much_damage_is_reported(cfg):
    fr = format2.encode("HI", "k", 1, cfg)
    h = format2.decode_header(fr.header_symbols, "k", cfg)
    got = fr.payload_symbols.copy()
    got[:10] = format2.ERASED
    with pytest.raises(DecodeError) as e:
        format2.decode_payload(got, h, "k", cfg)
    assert e.value.stage == "payload_fec"


def test_wrong_key_never_returns_the_message(cfg):
    fr = format2.encode("MEET AT DAWN", "right", 4, cfg)
    with pytest.raises((DecodeError, FramingError)):                     # a wrong key may also read a wrong length
        h = format2.decode_header(fr.header_symbols, "wrong", cfg)
        format2.decode_payload(fr.payload_symbols, h, "wrong", cfg)


def test_crc_covers_the_length_and_mode(cfg):
    fr = format2.encode("HELLO", "k", 4, cfg)
    h = format2.decode_header(fr.header_symbols, "k", cfg)
    other = format2.Header(format2.RAW, h.length, h.nonce, 0, 0)
    with pytest.raises((DecodeError, FramingError)):
        format2.decode_payload(fr.payload_symbols, other, "k", cfg)


def test_scrambling_hides_repeats(cfg):
    fr = format2.encode("A" * 60, "k", 4, cfg)
    assert len(set(fr.payload_symbols.tolist())) > 20


@pytest.mark.parametrize("bad", ["", "x" * 141, "A" * 141, b""])
def test_bad_lengths(cfg, bad):
    with pytest.raises(FramingError):
        format2.encode(bad, "k", 1, cfg)
