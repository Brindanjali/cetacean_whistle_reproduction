"""channel.py (noise, narrowband SNR) and detect.py (the reproduction's detector, slot matching)."""
import numpy as np
import pytest
from scipy import signal

from wcode import channel, detect, synth
from wcode.contour import Contour


def test_narrowband_snr_is_exact_for_a_bin_centred_tone(cfg):
    fs = 96000.0
    rng = np.random.default_rng(0)
    noise = rng.normal(0, 0.01, int(10 * fs))
    levels = channel.bin_levels(noise, fs)
    f0 = 85 * 93.75                                     # on a bin centre: no scalloping
    a = channel.amplitude_for_snr(15.0, f0, levels, fs, cfg)
    tone = a * np.cos(2 * np.pi * f0 * np.arange(int(2 * fs)) / fs)
    w = signal.get_window("hamming", 1024, fftbins=True)
    _, _, z = signal.stft(tone, fs, window=w, nperseg=1024, noverlap=512, boundary=None, padded=False)
    peak = np.median(np.abs(z[85]) * w.sum())
    assert 20 * np.log10(peak / levels[85]) == pytest.approx(15.0, abs=0.05)


def test_snr_cap(cfg):
    levels = np.ones(600)
    capped = channel.amplitude_for_snr(80.0, 8000.0, levels, 96000.0, cfg)
    assert capped == pytest.approx(channel.amplitude_for_snr(cfg["channel"]["max_snr_db"], 8000.0, levels, 96000.0, cfg))


def T(start, f0, f1, n=40, hop=0.005):
    return detect.Track(start, np.linspace(f0, f1, n), hop)


def test_match_windows_and_ties(cfg):
    tracks = [T(1.00, 7000, 9000), T(1.10, 7500, 8500, n=80), T(1.10, 7500, 8500, n=20), T(2.00, 12000, 13000)]
    m = detect.match(tracks, [1.02, 1.11, 2.00, 3.0, 0.90], [8000, 8000, 8000, 8000, 8000], cfg)
    assert m[0] is tracks[0]                            # closest start
    assert m[1] is tracks[1]                            # a tie on start goes to the longer track
    assert m[2] is None                                 # right time, wrong pitch (12.5 kHz vs 8 kHz)
    assert m[3] is None                                 # nothing near 3 s
    assert m[4] is tracks[0]                            # 100 ms late is inside the +150 ms window


def test_detector_finds_a_synthetic_whistle(cfg):
    fs = 96000.0
    rng = np.random.default_rng(1)
    x = rng.normal(0, 0.01, int(8 * fs))
    c = Contour(np.linspace(-800, 800, 45), 1024 / 192000)        # 240 ms up-sweep
    w = synth.whistle(c, 9000.0, rng, cfg, fs)
    a = channel.amplitude_for_snr(20.0, 9000.0, channel.bin_levels(x, fs), fs, cfg)
    x[int(4.0 * fs):int(4.0 * fs) + len(w)] += a * w
    tracks = detect.Detector(cfg).tracks(x, fs)
    m = detect.match(tracks, [4.0], [9000.0], cfg)[0]
    assert m is not None
    assert abs(m.centre_hz - 9000.0) < 200
    assert abs(m.duration_ms - c.duration_ms) < 40
