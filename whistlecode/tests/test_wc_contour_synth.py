"""contour.py and synth.py: image -> centred contour, and contour -> whistle audio (envelope ported from the
reproduction's synthetic generator)."""
import numpy as np
import pytest

from wcode import contour, repro, synth
from wcode.contour import Contour

BIN = 93.75


@pytest.fixture(scope="module")
def pcfg():
    return repro.load_pipeline_config()


def test_centred():
    assert contour.centred([1.0, 3.0, 5.0]).tolist() == [-2.0, 0.0, 2.0]


def test_from_image_flat_with_gap(pcfg):
    img = np.zeros((128, 128), np.float32)
    img[60, 40:60] = 1.0
    img[60, 70:75] = 1.0                                   # 10 empty columns in between
    c, gap = contour.from_image(img, pcfg)
    assert gap == 10 and c.n_frames == 35 and c.span_hz == pytest.approx(0.0)
    assert c.duration_ms == pytest.approx(35 * 1024 / 192000 * 1000)


def test_from_image_sweep(pcfg):
    img = np.zeros((128, 128), np.float32)
    for i, col in enumerate(range(30, 70)):
        img[80 - i // 2, col] = 1.0                        # rises 19 rows over 40 columns
    c, gap = contour.from_image(img, pcfg)
    assert gap == 0 and c.span_hz == pytest.approx(19 * BIN)
    assert c.offset_hz[0] == pytest.approx(-c.offset_hz[-1])     # centred on its mid-range


def test_from_image_empty(pcfg):
    assert contour.from_image(np.zeros((128, 128), np.float32), pcfg) == (None, 0)


def test_envelope_is_the_generators(cfg):
    from whistlepipe.synth.whistles import SynthSampler

    orig = SynthSampler.__new__(SynthSampler)          # only _envelope is used, which needs fs alone
    orig.fs = 96000.0
    for seed in range(5):
        r1, r2 = np.random.default_rng(seed), np.random.default_rng(seed)
        a = orig._envelope(r1, 30000)
        b = synth.envelope(r2, 30000, 96000.0, taper=(0.15, 0.6))       # the generator's own taper range
        assert np.allclose(a, b)
        assert r1.random() == r2.random()              # the same number of draws


def test_whistle_frequency_and_harmonic(cfg):
    fs = 96000.0
    c = Contour(np.zeros(60), 1024 / 192000)           # flat, 320 ms
    x = synth.whistle(c, 8000.0, np.random.default_rng(0), cfg, fs)
    assert len(x) == round(60 * 1024 / 192000 * fs)
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    f = np.fft.rfftfreq(len(x), 1 / fs)
    k1, k2 = np.argmin(abs(f - 8000)), np.argmin(abs(f - 16000))
    assert abs(f[np.argmax(spec)] - 8000) < 10
    assert 20 * np.log10(spec[k2 - 3:k2 + 4].max() / spec[k1 - 3:k1 + 4].max()) == pytest.approx(-12.0, abs=0.5)


def test_whistle_follows_the_contour(cfg):
    fs = 96000.0
    c = Contour(np.linspace(-1500, 1500, 60), 1024 / 192000)
    f = synth.instantaneous_hz(c, 9000.0, fs)
    assert f[0] == pytest.approx(7500, abs=30) and f[-1] == pytest.approx(10500, abs=30)


def test_whistle_rejects_aliasing_harmonic(cfg):
    with pytest.raises(ValueError):
        synth.whistle(Contour(np.zeros(10), 0.005), 9000.0, np.random.default_rng(0), cfg, fs=32000.0)


@pytest.mark.localdata
def test_fc_pool(cfg):
    fc = synth.fc_pool(cfg)
    lo, hi = cfg["synth"]["fc_range_hz"]
    assert len(fc) > 1000 and fc.min() >= lo and fc.max() <= hi
