"""keys.py: masks and streams are deterministic, independent, and separated by part, stream, key and nonce."""
import numpy as np
import pytest

from wcode import keys
from wcode.keys import HEADER, PAYLOAD


def test_known_answers():
    # Sender and receiver must derive the same bytes on every machine: these must never change.
    assert keys.mask(HEADER, "reef42", 4).hex() == "e90cc11b"
    assert keys.mask(PAYLOAD, "reef42", 4, nonce=7).hex() == "0dea93c0"


def test_deterministic():
    assert keys.mask(PAYLOAD, "k", 50, 3) == keys.mask(PAYLOAD, "k", 50, 3)
    a = keys.stream(PAYLOAD, "timing", "k", 3).random(5)
    b = keys.stream(PAYLOAD, "timing", "k", 3).random(5)
    assert np.array_equal(a, b)


def test_separated_by_nonce_key_and_part():
    base = keys.mask(PAYLOAD, "k", 32, 3)
    assert keys.mask(PAYLOAD, "k", 32, 4) != base
    assert keys.mask(PAYLOAD, "k2", 32, 3) != base
    assert keys.mask(PAYLOAD, "kk", 32, 3) != keys.mask(PAYLOAD, "k", 32, 3)
    assert keys.mask(HEADER, "k", 32) != base


def test_streams_are_independent():
    t = keys.stream(PAYLOAD, "timing", "k", 3).random(8)
    p = keys.stream(PAYLOAD, "pitch", "k", 3).random(8)
    v = keys.stream(PAYLOAD, "variation", "k", 3).random(8)
    assert not np.allclose(t, p) and not np.allclose(t, v) and not np.allclose(p, v)
    hdr = keys.stream(HEADER, "timing", "k").random(8)
    assert not np.allclose(hdr, t)


def test_mask_prefix_and_lengths():
    long = keys.mask(HEADER, "k", 100)
    for n in (0, 1, 31, 32, 33, 64, 65):
        m = keys.mask(HEADER, "k", n)
        assert len(m) == n and m == long[:n]


def test_mask_bytes_look_uniform():
    m = np.frombuffer(keys.mask(PAYLOAD, "k", 100_000, 0), dtype=np.uint8)
    counts = np.bincount(m, minlength=256)
    assert counts.min() > 300 and counts.max() < 500       # expected 390.6 each
    assert abs(m.mean() - 127.5) < 1.0


def test_unicode_key():
    assert len(keys.mask(HEADER, "baleine-🐋-clé", 8)) == 8


@pytest.mark.parametrize("call", [
    lambda: keys.seed(HEADER, "scrambler", "k", nonce=1),         # header streams take no nonce
    lambda: keys.seed(PAYLOAD, "scrambler", "k"),                 # payload streams need one
    lambda: keys.seed(PAYLOAD, "nope", "k", 1),                   # unknown stream
    lambda: keys.seed(HEADER, "variation", "k"),                  # variation is a payload stream only
    lambda: keys.seed("body", "scrambler", "k"),                  # unknown part
    lambda: keys.seed(HEADER, "scrambler", ""),                   # empty key
    lambda: keys.seed(PAYLOAD, "scrambler", "k", 256),
    lambda: keys.seed(PAYLOAD, "scrambler", "k", -1),
    lambda: keys.seed(PAYLOAD, "scrambler", "k", True),
    lambda: keys.mask(HEADER, "k", -1),
])
def test_rejects_bad_input(call):
    with pytest.raises(ValueError):
        call()


def test_new_nonce_range():
    vals = {keys.new_nonce() for _ in range(2000)}
    assert min(vals) >= 0 and max(vals) <= 255 and len(vals) > 200
