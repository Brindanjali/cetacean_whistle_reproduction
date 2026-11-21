"""schedule.py and transmitter.py: slots from the key, and message -> WAV (PLAN.md sections 4.3 and 4.4)."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from wcode import channel, classify, codebook, detect, framing, model, schedule, transmitter
from wcode.contour import Contour

WC = Path(__file__).resolve().parents[1]
HOP = 1024 / 192000


# ---------------------------------------------------------------------------------------------- schedule
@pytest.mark.localdata
def test_counts_and_parts(cfg):
    s = schedule.frame_slots("reef42", 7, 2, cfg)
    assert len(s) == 39 and [x.index for x in s] == list(range(39))
    assert [x.part for x in s] == ["preamble"] * 3 + ["header"] * 12 + ["payload"] * 24


@pytest.mark.localdata
def test_intervals_and_pitches_in_range(cfg):
    s = schedule.frame_slots("reef42", 7, 140, cfg)
    gaps = np.diff([x.start_s for x in s])
    lo, hi = cfg["schedule"]["interval_s"]
    f_lo, f_hi = cfg["synth"]["fc_range_hz"]
    assert s[0].start_s == 0.0 and gaps.min() >= lo and gaps.max() <= hi
    assert all(f_lo <= x.fc_hz <= f_hi for x in s)
    assert gaps.min() * 1000 > cfg["codebook"]["duration_ms"][1]         # whistles can never overlap


@pytest.mark.localdata
def test_header_slots_use_the_key_only(cfg):
    a, b = schedule.frame_slots("k", 1, 5, cfg), schedule.frame_slots("k", 200, 60, cfg)
    assert a[:15] == b[:15]
    assert schedule.header_slots("k", cfg) == a[:15]
    assert schedule.header_slots("k2", cfg) != a[:15]


@pytest.mark.localdata
def test_payload_slots_change_with_the_nonce(cfg):
    a, b = schedule.frame_slots("k", 1, 5, cfg), schedule.frame_slots("k", 2, 5, cfg)
    assert [x.start_s for x in a[15:]] != [x.start_s for x in b[15:]]
    assert [x.fc_hz for x in a[15:]] != [x.fc_hz for x in b[15:]]
    assert a == schedule.frame_slots("k", 1, 5, cfg)                     # and repeat exactly


def test_interval_rule_is_enforced(cfg):
    from wcode.config import ConfigError, validate

    cfg["schedule"]["interval_s"] = [0.4, 0.9]
    with pytest.raises(ConfigError):
        validate(cfg)


# ---------------------------------------------------------------------------------------------- transmitter
@pytest.fixture(scope="module")
def fake_book(tmp_path_factory, local_data):
    """17 well-separated synthetic types: tau = 0 needs no VAE."""
    from wcode.config import default_config

    cfg = default_config()
    path = tmp_path_factory.mktemp("book")
    types = []
    for i in range(16):
        c = Contour(np.linspace(-200 - 60 * i, 200 + 60 * i, 30 + 3 * i) * (1 if i % 2 else -1), HOP)
        types.append(codebook.WhistleType(100 + i, i, np.zeros(64), np.eye(64), c, 50.0))
    sig = codebook.WhistleType(999, None, np.zeros(64), np.eye(64), Contour(800 * np.sin(np.linspace(0, 6.28, 50)), HOP), 70.0)
    codebook.save(path, codebook.Codebook(types, sig, {"model": model.check_lineage(cfg), "quick": False}))
    return path


@pytest.fixture(scope="module")
def tx_unit(fake_book):
    return transmitter.Transmitter(codebook_path=fake_book)


def test_types_follow_the_frame(tx_unit):
    tx = tx_unit.send("HI", "reef42", 7, tau=0)
    fr = framing.encode("HI", "reef42", 7)
    got = [w.type_index for w in tx.whistles]
    assert got[:3] == [transmitter.SIGNATURE] * 3 and got[3:] == fr.symbols.tolist()
    assert all(w.redraws == 0 and not w.fell_back for w in tx.whistles)


def test_audio_level_and_length(tx_unit, cfg):
    tx = tx_unit.send("HI", "reef42", 7, tau=0)
    assert tx.audio.dtype == np.float32 and tx.fs == 96000
    assert 20 * np.log10(np.abs(tx.audio).max()) == pytest.approx(cfg["transmit"]["peak_dbfs"], abs=0.01)
    last = tx.whistles[-1]
    end = tx.lead_in_s + last.slot.start_s + last.contour.duration_ms / 1000 + cfg["transmit"]["tail_s"]
    assert tx.duration_s == pytest.approx(end, abs=2 / tx.fs)
    assert np.abs(tx.audio[:int(0.49 * tx.fs)]).max() == 0.0             # the lead-in is silent


def test_same_input_same_audio(tx_unit):
    a, b = tx_unit.send("MEET", "k", 3, tau=0), tx_unit.send("MEET", "k", 3, tau=0)
    assert np.array_equal(a.audio, b.audio)
    c = tx_unit.send("MEET", "k", 4, tau=0)
    assert len(c.audio) != len(a.audio) or not np.array_equal(a.audio, c.audio)


def test_each_whistle_is_where_the_schedule_says(tx_unit):
    tx = tx_unit.send("HI", "reef42", 7, tau=0)
    for w in tx.whistles:
        s0 = int((tx.lead_in_s + w.slot.start_s) * tx.fs)
        n = int(w.contour.duration_ms / 1000 * tx.fs)
        seg = tx.audio[s0:s0 + n]
        assert np.abs(seg).max() > 0.2
        spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        f = np.fft.rfftfreq(len(seg), 1 / tx.fs)
        span = w.contour.span_hz / 2 + 150
        assert abs(f[np.argmax(spec)] - w.slot.fc_hz) <= span
        silent_after = tx.audio[s0 + n + 96:s0 + n + 96 + int(0.05 * tx.fs)]
        assert len(silent_after) == 0 or np.abs(silent_after).max() == 0.0     # no overlap into the gap


def test_bad_inputs(tx_unit):
    with pytest.raises(framing.FramingError):
        tx_unit.send("x" * 141, "k", 1, tau=0)
    with pytest.raises(ValueError):
        tx_unit.send("HI", "", 1, tau=0)
    with pytest.raises(ValueError):
        tx_unit.send("HI", "k", 1, tau=-0.1)


def test_write_wav_and_manifest(tx_unit, tmp_path):
    tx = tx_unit.send("SECRET TEXT", "my-private-key", 9, tau=0)
    p = transmitter.write_wav(tmp_path / "m.wav", tx, manifest=True)
    x, fs = sf.read(p, dtype="float32")
    assert fs == 96000 and np.array_equal(x, tx.audio)
    raw = p.with_suffix(".json").read_text(encoding="utf-8")
    assert "my-private-key" not in raw and "SECRET" not in raw
    m = json.loads(raw)
    assert m["n_whistles"] == len(tx.whistles) and m["whistles"][0]["type"] == "signature"
    with pytest.raises(ValueError):
        transmitter.write_wav(p, tx)                                     # never overwritten silently
    with pytest.raises(ValueError):
        transmitter.write_wav(tmp_path / "m.flac", tx)


# ---------------------------------------------------------------------------------------------- the real codebook
@pytest.fixture(scope="module")
def tx_real():
    from wcode.config import default_config

    cfg = default_config()
    if not (codebook.out_dir(cfg) / "codebook.npz").exists():
        pytest.skip("no codebook built on this machine")
    try:
        return transmitter.Transmitter(cfg)
    except codebook.CodebookError as e:
        pytest.skip(str(e))


def test_varied_shapes_pass_the_self_check(tx_real, cfg):
    tx = tx_real.send("HI THERE", "reef42", 7)
    assert tx.tau == cfg["transmit"]["tau"] and tx.n_fell_back <= len(tx.whistles) // 10
    templates = [t.contour for t in tx_real.cb.all_types]
    kept = [w for w in tx.whistles if not w.fell_back]
    d = classify.distances([w.contour for w in kept], templates, cfg)
    best, amb = classify.decide(d, cfg["classify"]["ambiguity_ratio"])
    assert best.tolist() == [w.type_index for w in kept] and not amb.any()
    lo, hi = cfg["codebook"]["duration_ms"]
    assert all(lo <= w.contour.duration_ms <= hi for w in kept)
    same = {}
    for w in kept:                                                       # the same symbol does not repeat one shape
        same.setdefault(w.type_index, []).append(tuple(np.round(w.contour.offset_hz, 3)))
    assert any(len(set(v)) > 1 for v in same.values() if len(v) > 1)


def test_message_survives_the_detector(tx_real, cfg):
    """The WAV at 30 dB SNR, read with the real detector at the known slots: the exact message comes back.
    (Near-silent noise would not work: the detector misses whistles far above its noise floor, see config.toml.)"""
    tx = tx_real.send("HI", "reef42", 7)
    noise = np.random.default_rng(0).normal(0, 0.01, len(tx.audio))
    amp = channel.amplitude_for_snr(30.0, 8000.0, channel.bin_levels(noise, tx.fs), tx.fs, cfg)
    x = noise + tx.audio.astype(np.float64) * amp / tx.gain
    tracks = detect.Detector(cfg).tracks(x, tx.fs)
    starts = [tx.lead_in_s + w.slot.start_s for w in tx.whistles[3:]]
    fcs = [w.slot.fc_hz for w in tx.whistles[3:]]
    found = detect.match(tracks, starts, fcs, cfg)
    templates = [t.contour for t in tx_real.cb.types]
    symbols = np.full(len(found), framing.ERASED)
    for i, (m, fc) in enumerate(zip(found, fcs)):
        if m is not None:
            best, amb = classify.decide(classify.distances([m.contour(fc)], templates, cfg), cfg["classify"]["ambiguity_ratio"])
            symbols[i] = framing.ERASED if amb[0] else int(best[0])
    _, msg = framing.decode(symbols, "reef42", cfg)
    assert msg.text == "HI"


def test_send_command(tx_real, tmp_path, capsys):
    spec = importlib.util.spec_from_file_location("whistlecode_cli_tx", WC / "whistlecode.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    out = tmp_path / "msg.wav"
    args = ["send", "HI", "--key", "reef42", "--nonce", "7", "--tau", "0", "--out", str(out), "--manifest"]
    assert cli.main(args) == 0
    assert "3 preamble + 7 header + 13 payload = 23 data" in capsys.readouterr().out
    assert out.exists() and out.with_suffix(".json").exists()
    before = out.read_bytes()
    assert cli.main(args) == 2                                           # refuses to overwrite
    assert "already exists" in capsys.readouterr().err and out.read_bytes() == before
    assert cli.main([*args, "--force"]) == 0
