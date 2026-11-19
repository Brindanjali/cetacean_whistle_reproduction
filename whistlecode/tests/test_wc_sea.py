"""sea.py: echoes, absorption and Doppler between the sender and the hydrophone."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from scipy import signal

from wcode import channel, schedule, sea

FS = 96000
WC = Path(__file__).resolve().parents[1]


def calm(**changes) -> sea.Sea:
    return sea.Sea(**{**dict(range_m=1000.0, water_depth_m=100.0, source_depth_m=10.0, receiver_depth_m=20.0), **changes})


def pulse(at_s: float, length_s: float, f_hz: float = 8000.0, width_s: float = 0.001) -> np.ndarray:
    t = np.arange(int(length_s * FS)) / FS - at_s
    return np.exp(-0.5 * (t / width_s) ** 2) * np.cos(2 * np.pi * f_hz * t)


def patch_noise(monkeypatch, level: float = 0.001):
    def fake(encounter, n, rng, cfg=None, pcfg=None):
        return np.random.default_rng(5).normal(0, level, n), ["noise.flac"]

    monkeypatch.setattr(channel, "noise_stretch", fake)


def test_thorp_known_values():
    assert sea.thorp_db_per_km(10000.0) == pytest.approx(1.187, abs=0.001)
    assert sea.thorp_db_per_km(20000.0) == pytest.approx(4.134, abs=0.001)


def test_the_four_paths(cfg):
    length, gain = sea.paths(calm(), cfg)
    assert length == pytest.approx(np.hypot(1000.0, [10.0, 30.0, 170.0, 190.0]))
    assert gain == pytest.approx([1.0, -0.9, 0.4, -0.36])


def test_direct_path_has_gain_one_at_the_reference_pitch_and_high_notes_lose_more(cfg):
    cfg["sea"]["surface_reflection"] = 0.0
    cfg["sea"]["bottom_reflection"] = 0.0
    h = sea.response(np.array([8000.0, 16000.0, 32000.0]), calm(range_m=2000.0), 8000.0, cfg)
    assert abs(h[0]) == pytest.approx(1.0)
    extra = 2.0 * (sea.thorp_db_per_km(16000.0) - sea.thorp_db_per_km(8000.0))
    assert 20 * np.log10(abs(h[1])) == pytest.approx(-extra, abs=0.01)
    assert abs(h[2]) < abs(h[1]) < 1.0


def test_an_echo_arrives_late_and_quiet_by_the_right_amount(cfg):
    cfg["sea"]["surface_reflection"] = 0.0                # leaves the direct path and the bottom echo
    s = calm(range_m=200.0)
    length, _ = sea.paths(s, cfg)
    y = np.abs(signal.hilbert(sea.propagate(pulse(0.1, 0.4), FS, s, 8000.0, cfg)))
    delay = (length[2] - length[0]) / 1500.0
    first = int(np.argmax(y[:int(0.12 * FS)]))
    second = first + int(0.02 * FS) + int(np.argmax(y[first + int(0.02 * FS):]))
    assert first / FS == pytest.approx(0.1, abs=2 / FS)
    assert (second - first) / FS == pytest.approx(delay, abs=2 / FS)
    loss = 10 ** (-float(sea.thorp_db_per_km(8000.0)) * (length[2] - length[0]) / 1000 / 20)
    assert y[second] / y[first] == pytest.approx(0.4 * length[0] / length[2] * loss, rel=0.02)


@pytest.mark.parametrize("f_hz", [6000.0, 7350.0, 9125.0, 11000.0, 13777.0])
def test_a_steady_tone_follows_the_filter_exactly(cfg, f_hz):
    s = calm(range_m=500.0)
    t = np.arange(FS) / FS
    x = np.cos(2 * np.pi * f_hz * t)
    y = sea.propagate(x, FS, s, 8000.0, cfg)
    h = sea.response(f_hz, s, 8000.0, cfg)
    middle = np.arange(int(0.3 * FS), int(0.7 * FS))
    want = np.real(h * np.exp(2j * np.pi * f_hz * t[middle]))
    assert np.max(np.abs(y[middle] - want)) < 1e-3


@pytest.mark.parametrize("speed, want_hz", [(3.0, 10020.0), (-3.0, 9980.0), (1.5, 10010.0)])
def test_doppler_shifts_the_pitch(cfg, speed, want_hz):
    x = np.cos(2 * np.pi * 10000.0 * np.arange(2 * FS) / FS)
    y = sea.propagate(x, FS, calm(speed_mps=speed, echoes=False), 8000.0, cfg)
    mid = y[int(0.5 * FS):int(1.5 * FS)]
    phase = np.unwrap(np.angle(signal.hilbert(mid)))[2000:-2000]
    slope = np.polyfit(np.arange(len(phase)) / FS, phase, 1)[0] / (2 * np.pi)
    assert slope == pytest.approx(want_hz, abs=0.01)


def test_doppler_moves_later_whistles_by_the_time_elapsed(cfg):
    x = pulse(18.0, 20.0)
    y = sea.propagate(x, FS, calm(speed_mps=3.0, echoes=False), 8000.0, cfg)
    heard = int(np.argmax(np.abs(signal.hilbert(y)))) / FS
    assert heard == pytest.approx(18.0 / 1.002, abs=2 / FS)        # 36 ms early after 18 s
    assert len(y) == pytest.approx(len(x) / 1.002, abs=2)


def test_a_still_sea_without_echoes_changes_nothing(cfg):
    x = pulse(0.1, 0.3)
    assert np.array_equal(sea.propagate(x, FS, calm(echoes=False), 8000.0, cfg), x)


def test_time_scale_is_accurate(cfg):
    for v in (-2.77, 0.31, 1.234, 3.0):
        assert float(sea.time_scale(v, cfg)) == pytest.approx(1 + v / 1500.0, abs=1e-8)
    assert sea.time_scale(0.0, cfg) == 1


def test_random_seas_are_repeatable_and_within_the_plan(cfg):
    draws = [sea.draw(np.random.default_rng(i), cfg) for i in range(300)]
    assert draws[7] == sea.draw(np.random.default_rng(7), cfg)
    assert {d.range_m for d in draws} == {200.0, 500.0, 1000.0, 2000.0}
    assert all(50 <= d.water_depth_m <= 1000 and 5 <= d.source_depth_m <= 30 and 5 <= d.receiver_depth_m <= 50 for d in draws)
    assert all(abs(d.speed_mps) <= 3 for d in draws)
    assert min(d.speed_mps for d in draws) < -2 and max(d.speed_mps for d in draws) > 2


def test_impossible_geometry_is_refused():
    with pytest.raises(ValueError, match="depth"):
        calm(receiver_depth_m=150.0)
    with pytest.raises(ValueError, match="range"):
        calm(range_m=0.0)


def test_channel_without_any_sea_effect_matches_the_plain_channel(cfg, monkeypatch):
    patch_noise(monkeypatch)
    audio = pulse(0.2, 0.5)
    pool = np.linspace(6000.0, 12000.0, 50)
    plain = channel.through_channel(audio, FS, 15.0, pool, seed=3, cfg=cfg)
    still = channel.through_channel(audio, FS, 15.0, pool, seed=3, cfg=cfg, sea=calm(echoes=False))
    assert np.array_equal(plain.audio, still.audio)
    assert plain.time_scale == still.time_scale == 1.0


def test_channel_adds_the_propagated_signal_with_the_plain_channels_gain(cfg, monkeypatch):
    patch_noise(monkeypatch)
    audio = pulse(0.2, 0.5)
    pool = np.linspace(6000.0, 12000.0, 50)
    s = calm(range_m=200.0, speed_mps=2.0)
    plain = channel.through_channel(audio, FS, 15.0, pool, seed=3, cfg=cfg)
    heard = channel.through_channel(audio, FS, 15.0, pool, seed=3, cfg=cfg, sea=s)
    played = sea.propagate(audio, FS, s, float(np.median(pool)), cfg)
    assert heard.gain == pytest.approx(plain.gain, rel=0.02)      # the noise stretch is longer, so its measured level differs a little
    assert heard.time_scale == pytest.approx(1 + 2.0 / 1500.0, abs=1e-8)
    assert heard.sea == s
    pad = int(cfg["channel"]["pad_s"] * FS)
    assert len(heard.audio) == len(played) + 2 * pad
    noise = np.random.default_rng(5).normal(0, 0.001, len(heard.audio))
    s0 = int(round(heard.offset_s * FS))
    noise[s0:s0 + len(played)] += heard.gain * played
    assert heard.audio == pytest.approx(noise.astype(np.float32), abs=1e-6)


def test_channel_command_applies_the_sea(cfg, monkeypatch, tmp_path, capsys):
    spec = importlib.util.spec_from_file_location("whistlecode_cli_sea", WC / "whistlecode.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    patch_noise(monkeypatch)
    monkeypatch.setattr(schedule, "pitch_pool", lambda c=None: np.linspace(6000.0, 12000.0, 50))
    wav = tmp_path / "msg.wav"
    sf.write(str(wav), pulse(0.2, 0.5).astype(np.float32), FS, subtype="FLOAT")
    out = tmp_path / "heard.wav"
    assert cli.main(["channel", str(wav), "--snr", "15", "--range", "1", "--doppler", "-1.5", "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "range 1 km" in text and "closing at -1.5 m/s" in text
    assert out.exists()
