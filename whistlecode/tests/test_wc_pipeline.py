"""The format v2 pipeline: rhythm bank, slot layout, sender, channel and receiver (PLAN.md section 4.6)."""
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from wcode import bank, channel, codebook, detect, format2, layout, receiver, sender
from wcode.contour import Contour
from wcode.framing import DecodeError

WC = Path(__file__).resolve().parents[1]
HOP = 1024 / 192000
KEY = "reef42"


# ---------------------------------------------------------------------------------------------- small fixtures
def fake_bank(n_groups: int = 120, seed: int = 0) -> bank.Bank:
    """Groups of eight whistles 0.5 s apart, separated by 1.5 s of silence. Every fourth whistle is too long to carry data."""
    rng = np.random.default_rng(seed)
    on, off, contours, starts, silence = [], [], [], [], []
    t = 0.0
    for _ in range(n_groups):
        for j in range(8):
            frames = 120 if j % 4 == 3 else int(rng.integers(30, 60))
            f0 = float(rng.uniform(6000, 11000))
            contours.append(np.linspace(f0 - 300, f0 + 300, frames, dtype=np.float32))
            if j == 0:
                starts.append(len(on))
            on.append(t)
            off.append(t + frames * HOP)
            silence.append(0.5 - frames * HOP if j < 7 else 1.5)
            t += 0.5 if j < 7 else frames * HOP + 1.5
    on, off = np.array(on), np.array(off)
    length = off - on
    return bank._bank({"on": on, "off": off, "first": np.cumsum([0] + [len(c) for c in contours], dtype=np.int64),
                       "freq": np.concatenate(contours), "run": np.zeros(len(on), dtype=np.int64),
                       "eligible": (length >= 0.10) & (length <= 0.45), "silence_after": np.array(silence),
                       "starts": np.array(starts, dtype=np.int64), "hop_s": np.array(HOP)})


@pytest.fixture(scope="module")
def small_bank():
    return fake_bank()


@pytest.fixture(scope="module")
def pool():
    return np.linspace(5000.0, 12000.0, 2001)


@pytest.fixture(scope="module")
def fake_book(tmp_path_factory):
    """16 well-separated shapes plus a signature: tau = 0 needs no VAE."""
    path = tmp_path_factory.mktemp("book")
    types = []
    for i in range(16):
        c = Contour(np.linspace(-200 - 60 * i, 200 + 60 * i, 30 + 3 * i) * (1 if i % 2 else -1), HOP)
        types.append(codebook.WhistleType(100 + i, i, np.zeros(64), np.eye(64), c, 50.0))
    sig = codebook.WhistleType(999, None, np.zeros(64), np.eye(64), Contour(800 * np.sin(np.linspace(0, 6.28, 50)), HOP), 70.0)
    codebook.save(path, codebook.Codebook(types, sig, {"model": {}, "quick": False}))
    return path


@pytest.fixture(scope="module")
def tx(fake_book, small_bank, local_data):
    return sender.Sender(codebook_path=fake_book, check_model=False, rhythm_bank=small_bank)


@pytest.fixture(scope="module")
def rx(fake_book, small_bank, local_data):
    return receiver.Receiver(codebook_path=fake_book, check_model=False, rhythm_bank=small_bank)


def tracks_of(sent: sender.Transmission, b: bank.Bank, offset: float = 0.0, drop=()) -> list:
    """What a perfect detector would report for a transmission, except the data whistles listed in drop."""
    out = [detect.Track(offset + d.slot.start_s, d.fc_hz + d.contour.offset_hz, HOP)
           for i, d in enumerate(sent.data) if i not in set(drop)]
    return sorted(out, key=lambda t: t.start_s)


# ---------------------------------------------------------------------------------------------- the real bank
@pytest.fixture(scope="module")
def real_bank():
    from wcode.config import PROJECT_ROOT, default_config

    cfg = default_config()
    if not all((PROJECT_ROOT / "preprocessed" / f"encounter_{e}" / "contours.npz").exists() for e in cfg["bank"]["encounters"]):
        pytest.skip("the preprocessed encounters are not on this machine")
    return bank.load(cfg)


def test_real_bank_matches_its_pin_and_rebuilds_identically(real_bank, cfg):
    assert real_bank.sha256 == cfg["bank"]["sha256"]
    assert bank.build(cfg).sha256 == real_bank.sha256


def test_real_bank_follows_the_data_rules(real_bank, cfg):
    c = cfg["bank"]
    b = real_bank
    length = b.off - b.on
    assert np.all(np.diff(b.on) >= 0)
    assert length[b.eligible].min() >= c["data_length_s"][0] and length[b.eligible].max() <= c["data_length_s"][1]
    for i in np.where(b.eligible)[0][::500]:
        near = (b.on >= b.on[i] - c["slot_early_s"]) & (b.on <= b.on[i] + c["slot_late_s"])
        assert near.sum() == 1


def test_a_changed_bank_is_refused(real_bank, cfg):
    cfg["bank"]["sha256"] = "0" * 64
    with pytest.raises(bank.BankError):
        bank.load(cfg)


# ---------------------------------------------------------------------------------------------- layout
def test_header_layout_uses_the_key_only(small_bank, pool, cfg):
    a = format2.encode("HI", KEY, 1, cfg)
    b = format2.encode("A LONGER MESSAGE", KEY, 200, cfg)
    ha, _ = layout.frame_layout(a, KEY, small_bank, pool, cfg)
    hb, _ = layout.frame_layout(b, KEY, small_bank, pool, cfg)
    assert [s.start_s for s in ha.slots] == [s.start_s for s in hb.slots]
    assert [s.part for s in ha.slots] == ["preamble"] * 3 + ["header"] * 7
    other = layout.header_layout("another key", small_bank, pool, cfg)
    assert [s.bank_index for s in other.slots] != [s.bank_index for s in ha.slots]


def test_payload_layout_changes_with_the_nonce_and_repeats(small_bank, pool, cfg):
    head = layout.header_layout(KEY, small_bank, pool, cfg)
    a = layout.payload_layout(KEY, 1, 30, head, small_bank, pool, cfg)
    b = layout.payload_layout(KEY, 2, 30, head, small_bank, pool, cfg)
    again = layout.payload_layout(KEY, 1, 30, head, small_bank, pool, cfg)
    assert [s.bank_index for s in a.slots] != [s.bank_index for s in b.slots]
    assert [s.start_s for s in a.slots] == [s.start_s for s in again.slots]
    assert a.slots[0].start_s >= head.end_s + cfg["bank"]["min_silence_s"]


def test_data_slots_keep_their_spacing_and_pitches(small_bank, pool, cfg):
    head = layout.header_layout(KEY, small_bank, pool, cfg)
    pay = layout.payload_layout(KEY, 9, 150, head, small_bank, pool, cfg)
    slots = head.slots + pay.slots
    assert len(pay.slots) == 150 and [s.index for s in slots] == list(range(160))
    assert np.diff([s.start_s for s in slots]).min() >= cfg["bank"]["min_data_spacing_s"] - 1e-9
    for s in slots[3:]:
        assert len(s.candidates_hz) == 4 and np.diff(s.candidates_hz).min() > 1000
    assert all(len(s.candidates_hz) == 1 for s in slots[:3])


def test_every_walked_whistle_is_played_once(small_bank, pool, cfg):
    head = layout.header_layout(KEY, small_bank, pool, cfg)
    used = [s.bank_index for s in head.slots] + [c.bank_index for c in head.covers]
    assert len(used) == len(set(used)) and len(head.covers) > 0
    times = sorted([s.start_s for s in head.slots] + [c.start_s for c in head.covers])
    assert times[0] == 0.0


# ---------------------------------------------------------------------------------------------- sender
def test_symbols_choose_shape_and_pitch(tx):
    sent = tx.send("HI", KEY, 7, tau=0)
    assert [d.type_index for d in sent.data[:3]] == [sender.SIGNATURE] * 3
    for d, y in zip(sent.data[3:], sent.frame.symbols):
        assert d.type_index == int(y) >> 2 and d.band == int(y) & 3 and d.fc_hz == d.slot.candidates_hz[d.band]


def test_same_input_same_audio(tx):
    a, b, c = tx.send("MEET", KEY, 3, tau=0), tx.send("MEET", KEY, 3, tau=0), tx.send("MEET", KEY, 4, tau=0)
    assert np.array_equal(a.audio, b.audio)
    assert len(a.audio) != len(c.audio) or not np.array_equal(a.audio, c.audio)


def test_audio_format_and_silent_lead_in(tx):
    sent = tx.send("HI", KEY, 7, tau=0)
    assert sent.audio.dtype == np.float32 and sent.fs == 96000
    assert np.abs(sent.audio[:int(0.49 * sent.fs)]).max() == 0.0
    assert np.abs(sent.audio).max() < 1.0


def test_manifest_hides_the_key_and_text(tx, tmp_path):
    sent = tx.send("SECRET TEXT", "my-private-key", 9, tau=0)
    p = sender.write_wav(tmp_path / "m.wav", sent, manifest=True)
    raw = p.with_suffix(".json").read_text(encoding="utf-8")
    assert "my-private-key" not in raw and "SECRET" not in raw
    assert json.loads(raw)["n_data_whistles"] == len(sent.data)


def test_colliding_cover_whistle_moves(tx, cfg):
    f = np.linspace(7800.0, 8200.0, 40)
    rng = np.random.default_rng(0)
    on, off, fc = np.array([1.0]), np.array([1.2]), np.array([8000.0])
    mid, state = tx._cover_pitch(f, 1.05, 1.25, on, off, fc, rng)
    assert state == 1 and abs(mid - 8000.0) >= 200 + cfg["sender"]["cover_move_clearance_hz"]
    assert tx._cover_pitch(f, 5.0, 5.2, on, off, fc, rng) == (8000.0, 0)                 # no overlap in time
    assert tx._cover_pitch(f + 4000, 1.05, 1.25, on, off, fc, rng) == (12000.0, 0)       # far away in pitch


# ---------------------------------------------------------------------------------------------- soft repair
def test_marking_doubtful_whistles_rescues_a_block(cfg):
    fr = format2.encode("MEET AT DAWN", KEY, 5, cfg)
    h = format2.decode_header(fr.header_symbols, KEY, cfg)
    got = fr.payload_symbols.copy()
    bad = [1, 4, 8, 12, 16]                                              # 5 wrong whistles: 2 x 5 is more than the 8 parity symbols
    got[bad] = (got[bad] + 1) % 64
    with pytest.raises(DecodeError):
        format2.decode_payload(got, h, KEY, cfg)
    doubt = np.zeros(len(got))
    doubt[bad] = 0.8
    assert format2.decode_payload(got, h, KEY, cfg, doubt).text == "MEET AT DAWN"


def test_soft_repair_never_invents_a_message(cfg):
    rng = np.random.default_rng(1)
    h = format2.Header(format2.COMPACT, 12, 5, 0, 0)
    n = format2.payload_symbols(format2.COMPACT, 12, cfg)
    for _ in range(300):
        with pytest.raises(DecodeError):
            format2.decode_payload(rng.integers(0, 64, n), h, KEY, cfg, rng.random(n))


# ---------------------------------------------------------------------------------------------- receiver, without audio
def test_reads_a_message_from_perfect_tracks(tx, rx, small_bank):
    sent = tx.send("MEET AT DAWN", KEY, 11, tau=0)
    got = rx.decode_tracks(tracks_of(sent, small_bank, 37.25), KEY)
    assert got.ok and got.text == "MEET AT DAWN" and got.nonce == 11
    assert got.offset_s == pytest.approx(37.25, abs=0.02)
    assert (got.n_repaired_wrong, got.n_repaired_lost) == (0, 0)


def test_survives_missing_whistles(tx, rx, small_bank):
    sent = tx.send("MEET AT DAWN", KEY, 11, tau=0)
    drop = [0, 4, 8, 12, 15, 20, 25, 29]                                 # a preamble whistle, two header and five payload whistles
    got = rx.decode_tracks(tracks_of(sent, small_bank, 3.0, drop), KEY)
    assert got.ok and got.text == "MEET AT DAWN" and got.n_repaired_lost == 7


def test_raw_text_comes_back_exactly(tx, rx, small_bank):
    message = "Meet at dawn, café"
    got = rx.decode_tracks(tracks_of(tx.send(message, KEY, 2, tau=0), small_bank, 1.0), KEY)
    assert got.ok and got.text == message and got.mode == format2.RAW


def test_a_stray_track_in_a_slot_does_not_win(tx, rx, small_bank):
    sent = tx.send("MEET AT DAWN", KEY, 11, tau=0)
    tracks = tracks_of(sent, small_bank, 2.0)
    for d in sent.data[3:]:                                              # a short flat noise track, closer in time than the whistle
        tracks.append(detect.Track(2.0 + d.slot.start_s + 0.001, np.full(6, d.fc_hz + 100.0), HOP))
    got = rx.decode_tracks(sorted(tracks, key=lambda t: t.start_s), KEY)
    assert got.ok and got.text == "MEET AT DAWN"


def test_wrong_key_and_empty_recordings_report_nothing(tx, rx, small_bank):
    sent = tx.send("MEET AT DAWN", KEY, 11, tau=0)
    assert not rx.decode_tracks(tracks_of(sent, small_bank, 2.0), "not the key").ok
    empty = rx.decode_tracks([], KEY)
    assert not empty.ok and empty.stage == "sync"


# ---------------------------------------------------------------------------------------------- drift (WC-R2)
LONG = "THE TIDE TURNS SOON BRING TWO BOATS ACROSS THE CHANNEL NOW"


def heard_at(sent: sender.Transmission, offset: float, scale: float, jitter_s: float = 0.0, seed: int = 0) -> list:
    """Perfect tracks of a transmission heard at a time scale (channel.Received.time_scale): a moment t of the sent file is heard
    at offset + t / scale, and every pitch is multiplied by scale. jitter_s: random error of each track's start."""
    jit = np.random.default_rng(seed).normal(0.0, jitter_s, len(sent.data))
    out = [detect.Track(offset + (d.slot.start_s + j) / scale, (d.fc_hz + d.contour.offset_hz) * scale, HOP / scale)
           for d, j in zip(sent.data, jit)]
    return sorted(out, key=lambda t: t.start_s)


def no_drift_receiver(fake_book, small_bank, cfg):
    cfg["receiver"]["drift_correction"] = False
    return receiver.Receiver(cfg, codebook_path=fake_book, check_model=False, rhythm_bank=small_bank)


def test_warp_puts_tracks_back_on_the_senders_clock():
    t = detect.Track(12.0, np.array([8000.0, 8100.0]), HOP)
    s = 1.002
    heard = detect.Track(2.0 + (12.0 - 2.0) / s, t.freq_hz * s, HOP / s)
    back = receiver.warp([heard], 2.0, s)[0]
    assert back.start_s == pytest.approx(12.0) and back.hop_s == pytest.approx(HOP) and back.freq_hz == pytest.approx(t.freq_hz)
    assert receiver.warp([t], 2.0, 1.0)[0] is t


@pytest.mark.parametrize("speed", [-3.0, -2.0, -1.0, 1.0, 2.0, 3.0])
def test_reads_a_message_heard_with_doppler(tx, rx, small_bank, fake_book, cfg, speed):
    sent = tx.send(LONG, KEY, 11, tau=0)
    s = 1.0 + speed / 1500.0
    tracks = heard_at(sent, 4.0, s, jitter_s=0.01, seed=int(speed * 10) % 7)
    got = rx.decode_tracks(tracks, KEY)
    assert got.ok and got.text == LONG
    assert got.time_scale == pytest.approx(s, abs=1e-4) and got.offset_s == pytest.approx(4.0, abs=0.02)
    assert not no_drift_receiver(fake_book, small_bank, cfg).decode_tracks(tracks, KEY).ok    # the gap this closes


@pytest.mark.parametrize("ppm", [-120.0, 45.0, 250.0])
def test_reads_a_message_through_mismatched_sound_card_clocks(tx, rx, small_bank, ppm):
    """Two sound cards at nominally the same rate differ by up to a few hundred parts per million (the in-air test, WC-R5)."""
    sent = tx.send(LONG, KEY, 5, tau=0)
    got = rx.decode_tracks(heard_at(sent, 1.5, 1.0 + ppm * 1e-6, jitter_s=0.005), KEY)
    assert got.ok and got.text == LONG and got.time_scale == pytest.approx(1.0 + ppm * 1e-6, abs=5e-5)


def test_no_drift_reads_at_scale_one(tx, rx, small_bank):
    got = rx.decode_tracks(tracks_of(tx.send(LONG, KEY, 11, tau=0), small_bank, 3.0), KEY)
    assert got.ok and got.time_scale == pytest.approx(1.0, abs=1e-5) and got.drift_matches > 0


def test_drift_correction_never_reads_a_wrong_key(tx, rx):
    sent = tx.send(LONG, KEY, 11, tau=0)
    for speed in (-3.0, 0.0, 2.0):
        assert not rx.decode_tracks(heard_at(sent, 2.0, 1.0 + speed / 1500.0), "not the key").ok


def test_without_drift_correction_the_frame_search_is_unchanged(tx, small_bank, fake_book, cfg):
    """With drift_correction off the receiver is campaign v1's: one time scale, and candidates ranked by votes alone."""
    old = no_drift_receiver(fake_book, small_bank, cfg)
    sent = tx.send("MEET AT DAWN", KEY, 11, tau=0)
    tr = receiver.TrackSet(tracks_of(sent, small_bank, 37.25))
    found = old.find_frame(tr, layout.header_layout(KEY, small_bank, old.pool, old.cfg))
    assert all(s == 1.0 for _, _, s in found) and found[0][0] == pytest.approx(37.25, abs=0.02)
    got = old.decode_tracks(tr.tracks, KEY)
    assert got.ok and got.time_scale == 1.0 and got.drift_matches == 0


# ---------------------------------------------------------------------------------------------- channel
def test_channel_sets_the_level_and_hides_the_start(monkeypatch, cfg):
    fs = 96000
    noise = np.random.default_rng(0).normal(0, 0.01, fs * 30)
    monkeypatch.setattr(channel, "noise_stretch", lambda enc, n, rng, c, p: (noise[:n].copy(), ["n.flac"]))
    audio = np.zeros(fs * 10, dtype=np.float32)
    audio[fs:fs + 4800] = cfg["sender"]["data_amplitude"]
    pool = np.linspace(5000.0, 12000.0, 101)
    a = channel.through_channel(audio, fs, 15.0, pool, seed=1, cfg=cfg)
    b = channel.through_channel(audio, fs, 21.0, pool, seed=1, cfg=cfg)
    c = channel.through_channel(audio, fs, 15.0, pool, seed=2, cfg=cfg)
    assert len(a.audio) == len(audio) + 2 * int(cfg["channel"]["pad_s"] * fs)
    assert b.gain / a.gain == pytest.approx(10 ** (6 / 20), rel=1e-6)
    assert a.offset_s != c.offset_s and 0 <= a.offset_s <= 2 * cfg["channel"]["pad_s"]
    s0 = int(round(a.offset_s * fs))
    np.testing.assert_allclose(a.audio[s0 + fs:s0 + fs + 100], (noise[s0 + fs:s0 + fs + 100] + a.gain * audio[fs:fs + 100]), atol=1e-5)


def test_channel_refuses_the_training_encounter_and_other_rates(cfg):
    pool = np.linspace(5000.0, 12000.0, 11)
    with pytest.raises(ValueError):
        channel.through_channel(np.zeros(100), 96000, 15.0, pool, encounter=191, cfg=cfg)
    with pytest.raises(ValueError):
        channel.through_channel(np.zeros(100), 48000, 15.0, pool, cfg=cfg)


# ---------------------------------------------------------------------------------------------- the whole chain
@pytest.fixture(scope="module")
def cli():
    from wcode.config import default_config

    if not (codebook.out_dir(default_config()) / "codebook.npz").exists():
        pytest.skip("no codebook built on this machine")
    spec = importlib.util.spec_from_file_location("whistlecode_cli_v2", WC / "whistlecode.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_send_channel_receive_commands(cli, tmp_path, capsys):
    """Text -> WAV -> real noise at 25 dB -> the real detector -> the exact text, knowing only the key."""
    msg, heard = str(tmp_path / "msg.wav"), str(tmp_path / "heard.wav")
    assert cli.main(["send", "MEET AT DAWN", "--key", KEY, "--nonce", "7", "--out", msg]) == 0
    assert cli.main(["channel", msg, "--snr", "25", "--seed", "3", "--out", heard]) == 0
    capsys.readouterr()
    assert cli.main(["receive", heard, "--key", KEY]) == 0
    assert "'MEET AT DAWN'" in capsys.readouterr().out
    assert cli.main(["receive", heard, "--key", "wrong key"]) == 1
    assert "FAILED" in capsys.readouterr().out
    assert cli.main(["channel", msg, "--snr", "25", "--out", heard]) == 2                # never overwritten silently
