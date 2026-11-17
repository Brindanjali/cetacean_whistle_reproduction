"""classify.py: the vectorised banded DTW equals a plain double loop, and the decision rule erases ambiguous calls."""
import math

import numpy as np
import pytest

from wcode import classify
from wcode.contour import Contour


def naive_dtw(a, b, frac, bmin):
    la, lb = len(a), len(b)
    half = max(bmin, math.ceil(frac * max(la, lb)))
    slope = (lb - 1) / max(la - 1, 1)
    D = np.full((la, lb), np.inf)
    for i in range(la):
        for j in range(lb):
            if abs(j - i * slope) > half:
                continue
            c = abs(a[i] - b[j])
            if i == 0 and j == 0:
                D[i, j] = c
                continue
            best = min(D[i - 1, j] if i else np.inf, D[i, j - 1] if j else np.inf, D[i - 1, j - 1] if i and j else np.inf)
            D[i, j] = c + best
    return D[-1, -1] / max(la, lb)


def test_matches_the_plain_loop():
    rng = np.random.default_rng(0)
    qs = [np.cumsum(rng.normal(0, 200, rng.integers(1, 40))) for _ in range(25)]
    ts = [np.cumsum(rng.normal(0, 200, rng.integers(1, 40))) for _ in range(9)]
    got = classify.dtw_matrix(qs, ts, 0.2, 5, max_pairs=50)          # small chunks: exercises the length sorting
    want = np.array([[naive_dtw(q, t, 0.2, 5) for t in ts] for q in qs])
    assert np.allclose(got, want, equal_nan=False)


def test_constant_offset_and_identity():
    x = np.linspace(-800, 900, 30)
    flat = np.zeros(30)
    d = classify.dtw_matrix([x, flat + 50.0], [x, flat], 0.2, 5)
    assert d[0, 0] == pytest.approx(0.0)
    assert d[1, 1] == pytest.approx(50.0)               # on a flat contour an offset cannot be warped away
    # (on a sweep it partly can: DTW slides along the ramp, which is why contours are compared centred)


def test_duration_term_is_asymmetric(cfg):
    a = Contour(np.zeros(20), 0.005)
    b = Contour(np.zeros(30), 0.005)
    d = classify.distances([a, b], [a, b], cfg)
    c = cfg["classify"]
    assert d[0, 0] == pytest.approx(0.0) and d[1, 1] == pytest.approx(0.0)
    assert d[0, 1] == pytest.approx(c["duration_weight_short_hz_per_ms"] * 50.0)     # the track is 50 ms shorter
    assert d[1, 0] == pytest.approx(c["duration_weight_long_hz_per_ms"] * 50.0)      # the track is 50 ms longer


def test_track_offsets_from_the_known_fc():
    from wcode.detect import Track

    t = Track(1.0, np.array([7000.0, 7400.0, 8200.0]), 0.005)
    assert t.contour(7500.0).offset_hz.tolist() == [-500.0, -100.0, 700.0]
    assert t.contour().offset_hz.tolist() == [-600.0, -200.0, 600.0]                # re-centred on its own mid-range


def test_decide_erases_ambiguous_calls():
    dist = np.array([[10.0, 100.0, 50.0],      # clear: column 0
                     [90.0, 100.0, 300.0],     # 90 / 100 = 0.9 > 0.8: erased
                     [0.0, 0.0, 5.0]])         # a tie at zero: erased
    best, amb = classify.decide(dist, 0.8)
    assert best[0] == 0 and not amb[0]
    assert amb[1] and amb[2]
