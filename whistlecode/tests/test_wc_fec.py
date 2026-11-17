"""fec.py: Reed-Solomon repairs every mix of e wrong and f erased bytes with 2e + f <= nsym, and fails cleanly beyond."""
import random

import pytest

from wcode import fec


def corrupt(cw: bytes, e: int, f: int, rng: random.Random):
    buf = bytearray(cw)
    pos = rng.sample(range(len(buf)), e + f)
    for p in pos[:e]:
        buf[p] ^= rng.randint(1, 255)
    for p in pos[e:]:
        buf[p] = rng.randint(0, 255)                 # erased values are ignored, whatever they are
    return bytes(buf), pos[e:]


def test_systematic():
    data = bytes(range(20))
    cw = fec.encode(data, 8)
    assert len(cw) == 28 and cw[:20] == data


def test_clean_decode():
    data = b"hello whistles"
    r = fec.decode(fec.encode(data, 8), 8)
    assert (r.data, r.n_errors, r.n_erasures) == (data, 0, 0)


def test_repairs_within_the_limit():
    rng = random.Random(0)
    for _ in range(400):
        k = rng.randint(1, 142)
        nsym = rng.choice([4, 8, max(8, -(-k // 2))])
        if k + nsym > 255:
            continue
        data = bytes(rng.getrandbits(8) for _ in range(k))
        cw = fec.encode(data, nsym)
        e = rng.randint(0, nsym // 2)
        f = rng.randint(0, nsym - 2 * e)
        bad, erased = corrupt(cw, e, f, rng)
        r = fec.decode(bad, nsym, erased)
        assert r.data == data and r.codeword == cw
        assert r.n_errors == e and r.n_erasures == f


def test_fails_cleanly_beyond_the_limit():
    rng = random.Random(1)
    raised = wrong = 0
    for _ in range(300):
        data = bytes(rng.getrandbits(8) for _ in range(20))
        cw = fec.encode(data, 8)
        bad, _ = corrupt(cw, 6, 0, rng)              # 6 wrong bytes > 4 repairable
        try:
            r = fec.decode(bad, 8)
            wrong += r.data != data
        except fec.FecError:
            raised += 1
    assert raised >= 290                             # the rest would be miscorrections, which the payload CRC catches
    assert raised + wrong == 300


def test_too_many_erasures():
    cw = fec.encode(b"abcdef", 4)
    with pytest.raises(fec.FecError):
        fec.decode(cw, 4, erase_pos=range(5))


@pytest.mark.parametrize("call", [
    lambda: fec.encode(b"", 8),
    lambda: fec.encode(bytes(250), 8),               # 258 > 255
    lambda: fec.encode(b"x", 0),
    lambda: fec.decode(bytes(5), 8),                 # shorter than the parity
    lambda: fec.decode(fec.encode(b"abc", 4), 4, erase_pos=[7]),
])
def test_rejects_bad_input(call):
    with pytest.raises(ValueError):
        call()
