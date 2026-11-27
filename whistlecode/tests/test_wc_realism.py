"""realism.py and the upgraded sender: real shapes, recorded voices, virtual animals and recorded clicks."""
import copy

import numpy as np
import pytest
from test_wc_pipeline import HOP, KEY, fake_bank, tracks_of

from wcode import channel, classify, codebook, realism, receiver, sender, synth
from wcode.contour import Contour


# ---------------------------------------------------------------------------------------------- fixtures
@pytest.fixture(scope="module")
def small_bank():
    return fake_bank()


@pytest.fixture(scope="module")
def book(tmp_path_factory):
    path = tmp_path_factory.mktemp("book")
    types = []
    for i in range(16):
        c = Contour(np.linspace(-200 - 60 * i, 200 + 60 * i, 30 + 3 * i) * (1 if i % 2 else -1), HOP)
        types.append(codebook.WhistleType(100 + i, i, np.zeros(64), np.eye(64), c, 50.0))
    sig = codebook.WhistleType(999, None, np.zeros(64), np.eye(64), Contour(800 * np.sin(np.linspace(0, 6.28, 50)), HOP), 70.0)
    codebook.save(path, codebook.Codebook(types, sig, {"model": {}, "quick": False}))
    return path


def fake_library(cb: codebook.Codebook, b, n_clicks: int = 4000, empty_type: int | None = None) -> realism.Library:
    """Slight variations of each codebook shape, flat voices, and one click every 50 ms along the start of the bank."""
    rng = np.random.default_rng(0)
    shapes = []
    for i, t in enumerate(cb.all_types):
        shapes.append([] if i == empty_type else
                      [Contour(t.contour.offset_hz * float(rng.uniform(0.97, 1.03)), t.contour.hop_s) for _ in range(5)])
    wave = np.zeros(192, np.float32)
    wave[58] = 1.0
    wave[59] = -0.6
    return realism.Library(shapes, np.zeros((6, realism.ENV_POINTS)), np.full((6, realism.HARMONIC_POINTS), -12.0),
                           np.full((6, realism.HARMONIC_POINTS), -24.0), np.array([True, True, True, True, False, False]),
                           b.on[0] + 0.05 * np.arange(n_clicks), np.tile(wave, (n_clicks, 1)), 0.1, {})


@pytest.fixture(scope="module")
def lib(book, small_bank):
    return fake_library(codebook.load(path=book, check=False), small_bank)


def real_shape_config():
    from wcode.config import default_config

    cfg = default_config()
    cfg["realism"]["real_shapes"] = True
    return cfg


@pytest.fixture(scope="module")
def tx(book, small_bank, lib, local_data):
    return sender.Sender(real_shape_config(), codebook_path=book, check_model=False, rhythm_bank=small_bank, library=lib)


# ---------------------------------------------------------------------------------------------- voices
def test_voice_follows_the_recorded_pattern():
    c = Contour(np.zeros(60), HOP)
    env = np.r_[np.zeros(32), np.full(32, -12.0)]
    x = synth.voiced_whistle(c, 8000.0, env, np.full(16, -60.0), np.full(16, -60.0), fade_ms=0.0)
    n = len(x)
    first, last = np.abs(x[n // 8:3 * n // 8]).max(), np.abs(x[5 * n // 8:7 * n // 8]).max()
    assert 20 * np.log10(last / first) == pytest.approx(-12.0, abs=0.5)


def test_harmonics_and_distance():
    c = Contour(np.zeros(90), HOP)
    level = lambda x, f: np.abs(np.fft.rfft(x * np.hanning(len(x))))[int(round(f * len(x) / 96000))]
    near = synth.voiced_whistle(c, 8000.0, np.zeros(64), np.full(16, -12.0), np.full(16, -24.0))
    far = synth.voiced_whistle(c, 8000.0, np.zeros(64), np.full(16, -12.0), np.full(16, -24.0), tone_db=6.0)
    assert 20 * np.log10(level(near, 16000) / level(near, 8000)) == pytest.approx(-12.0, abs=0.5)
    assert 20 * np.log10(level(near, 24000) / level(near, 8000)) == pytest.approx(-24.0, abs=0.5)
    assert 20 * np.log10(level(far, 16000) / level(far, 8000)) == pytest.approx(-18.0, abs=0.5)
    assert 20 * np.log10(level(far, 24000) / level(far, 8000)) == pytest.approx(-36.0, abs=0.5)


def test_whistle_starts_and_ends_silently_and_never_aliases():
    c = Contour(np.zeros(40), HOP)
    x = synth.voiced_whistle(c, 20000.0, np.zeros(64), np.full(16, -6.0), np.full(16, -6.0))
    assert abs(x[0]) < 0.01 and abs(x[-1]) < 0.01
    spec = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    assert spec[int(12000 * len(x) / 96000)] < 0.02 * spec.max()          # 3 x 20 kHz would fold back to 36 kHz; nothing appears low down


def test_voice_is_measured_from_a_recording(cfg):
    rng = np.random.default_rng(0)
    t = np.arange(96000 * 4) / 96000
    y = 1e-4 * rng.standard_normal(len(t))
    on, off = int(1.0 * 96000), int(1.3 * 96000)
    tone = 0.05 * (np.cos(2 * np.pi * 8000 * t) + 10 ** (-12 / 20) * np.cos(2 * np.pi * 16000 * t))
    y[on:off] += tone[on:off]
    frames = int(0.3 * 96000 / realism.HOP) - 2
    voices = realism._voices_of(y, [(1.0 + realism.HOP / 96000, np.full(frames, 8000.0))], cfg["realism"])
    assert len(voices) == 1
    env, h2, h3, steady, amp = voices[0]
    assert steady and np.median(h2) == pytest.approx(-12.0, abs=1.5) and np.median(h3) <= -30
    assert amp == pytest.approx(0.05, rel=0.25)


# ---------------------------------------------------------------------------------------------- clicks
def _train(y, times, amp=0.2):
    for t in times:
        p = int(t * 96000)
        y[p:p + 12] += amp * np.exp(-np.arange(12) / 3.0) * np.cos(2 * np.pi * 30000 * np.arange(12) / 96000)


def test_only_clean_clicks_in_regular_trains_are_kept(cfg):
    rng = np.random.default_rng(1)
    y = 1e-4 * rng.standard_normal(96000 * 6)
    train = 1.0 + 0.04 * np.arange(12)
    _train(y, train)
    _train(y, [3.0, 4.2])                                                 # isolated sharp sounds
    t, w = realism._clicks_of(y, cfg["realism"])
    assert len(t) == len(train) and np.allclose(t, train, atol=0.001)
    assert w.shape[1] == 192 and abs(w[0, 0]) < 1e-6 and abs(w[0, -1]) < 1e-6


def test_a_tone_is_not_a_click(cfg):
    t = np.arange(96000 * 3) / 96000
    y = 0.1 * np.cos(2 * np.pi * 9000 * t) + 1e-4 * np.random.default_rng(2).standard_normal(len(t))
    assert len(realism._clicks_of(y, cfg["realism"])[0]) == 0


def test_clicks_keep_real_times_and_avoid_data_whistles(lib):
    start = float(lib.click_t[10])
    base = start + 100.0                                                  # clicks every 50 ms from here; a data whistle 0.30-0.50 s later
    got = realism.clicks_for(lib, [(start, start + 0.975, 100.0)], np.array([base + 0.3]), np.array([base + 0.5]), 0.012)
    times = np.array([t for t, _ in got])
    assert times.min() == pytest.approx(base) and times.max() == pytest.approx(base + 0.95)
    assert not np.any((times > base + 0.288) & (times < base + 0.512))
    assert len(got) == 15                                                 # 20 clicks, five of them on the data whistle


# ---------------------------------------------------------------------------------------------- animals
def test_animals_share_one_loudness_range(cfg):
    a = realism.group_of_animals(3000, np.random.default_rng(0), cfg)
    levels = np.array([w.level_db for w in a])
    lo, hi = cfg["realism"]["level_range_db"]
    assert levels.min() >= lo and levels.max() <= hi and abs(np.median(levels) - cfg["realism"]["median_level_db"]) < 1.5
    assert len({round(w.tone_db, 6) for w in a}) == cfg["realism"]["n_animals"]
    same = np.mean([x.tone_db == y.tone_db for x, y in zip(a, a[1:])])
    assert 0.55 < same < 0.8


def test_channel_refers_to_the_typical_data_whistle(monkeypatch, cfg):
    noise = np.random.default_rng(0).normal(0, 0.01, 96000 * 20)
    monkeypatch.setattr(channel, "noise_stretch", lambda enc, n, rng, c, p: (noise[:n].copy(), ["n.flac"]))
    pool = np.linspace(5000.0, 12000.0, 51)
    upgraded = channel.through_channel(np.zeros(96000), 96000, 15.0, pool, cfg=cfg)
    cfg["realism"]["enabled"] = False
    plain = channel.through_channel(np.zeros(96000), 96000, 15.0, pool, cfg=cfg)
    assert plain.gain / upgraded.gain == pytest.approx(10 ** (cfg["realism"]["median_level_db"] / 20), rel=1e-6)


# ---------------------------------------------------------------------------------------------- the upgraded sender
def test_data_whistles_use_real_shapes_without_early_repeats(tx, lib):
    sent = tx.send("A" * 60, KEY, 3)
    assert sent.n_real_shapes == len(sent.data) and sent.n_clicks > 0
    for type_index in range(16):
        used = [id(d.contour) for d in sent.data if d.type_index == type_index]
        pool = {id(c) for c in lib.shapes[type_index]}
        assert set(used) <= pool and len(set(used[:len(pool)])) == min(len(used), len(pool))


def test_upgraded_audio_repeats_exactly(tx):
    a, b, c = tx.send("MEET", KEY, 3), tx.send("MEET", KEY, 3), tx.send("MEET", KEY, 4)
    assert np.array_equal(a.audio, b.audio) and not np.array_equal(a.audio[:len(c.audio)], c.audio[:len(a.audio)])


def test_no_sea_background_is_added(tx):
    sent = tx.send("MEET AT DAWN", KEY, 3)
    assert np.abs(sent.audio[:int(0.49 * sent.fs)]).max() == 0.0
    assert np.mean(sent.audio == 0.0) > 0.05                              # true digital silence between the sounds
    assert np.abs(sent.audio).max() < 1.0


@pytest.mark.localdata
def test_type_without_real_shapes_keeps_its_vae_shapes(book, small_bank, monkeypatch):
    lib = fake_library(codebook.load(path=book, check=False), small_bank, empty_type=2)
    tx = sender.Sender(real_shape_config(), codebook_path=book, check_model=False, rhythm_bank=small_bank, library=lib)
    calls = []

    def stub(idx, tau, rng):
        calls.append(idx.copy())
        return [tx.templates[int(i)] for i in idx], np.zeros(len(idx), np.int64), np.zeros(len(idx), bool)

    monkeypatch.setattr(tx, "_shapes", stub)
    sent = tx.send("A" * 60, KEY, 3)
    twos = [d for d in sent.data if d.type_index == 2]
    assert twos and all(d.contour is tx.templates[2] for d in twos)
    assert len(calls) == 1 and set(calls[0].tolist()) == {2}
    assert sent.n_real_shapes == len(sent.data) - len(twos)


@pytest.mark.localdata
def test_default_sender_keeps_vae_shapes_with_real_voices_and_clicks(book, small_bank, lib, monkeypatch):
    tx = sender.Sender(codebook_path=book, check_model=False, rhythm_bank=small_bank, library=lib)
    monkeypatch.setattr(tx, "_shapes", lambda idx, tau, rng: ([tx.templates[int(i)] for i in idx], np.zeros(len(idx), np.int64),
                                                              np.zeros(len(idx), bool)))
    sent = tx.send("MEET AT DAWN", KEY, 3)
    assert sent.n_real_shapes == 0 and sent.n_clicks > 0
    assert all(d.contour is tx.templates[d.type_index] for d in sent.data)


def test_data_whistles_never_fall_below_the_reference_level(cfg):
    r = cfg["realism"]
    lo, hi = r["level_range_db"]
    levels = [realism.data_level_db(v, cfg) for v in np.linspace(lo, hi, 21)]
    assert min(levels) == pytest.approx(r["median_level_db"]) and max(levels) == pytest.approx(hi)
    assert np.all(np.diff(levels) > 0)                                    # louder animals stay louder


def test_upgraded_message_reads_back_exactly(tx, book, small_bank):
    rx = receiver.Receiver(codebook_path=book, check_model=False, rhythm_bank=small_bank)
    got = rx.decode_tracks(tracks_of(tx.send("MEET AT DAWN", KEY, 11), small_bank, 5.5), KEY)
    assert got.ok and got.text == "MEET AT DAWN"


# ---------------------------------------------------------------------------------------------- cluster assignment and the built library
def test_every_point_goes_to_its_likeliest_cluster():
    means = np.array([[0.0, 0.0], [10.0, 0.0], [0.0, 10.0]])
    cov = np.tile(np.eye(2), (3, 1, 1))
    points = means[[2, 0, 1, 1]] + 0.1
    got = realism.assign_components(points, np.full(3, 1 / 3), means, cov, "cpu", batch=2)
    assert got.tolist() == [2, 0, 1, 1]


@pytest.fixture(scope="module")
def real_library():
    from wcode.config import default_config

    cfg = default_config()
    if not (realism.out_dir(cfg) / "library.npz").exists():
        pytest.skip("the realism library is not built on this machine")
    return realism.load(cfg), cfg


def test_built_shapes_read_as_their_own_type(real_library):
    lib, cfg = real_library
    cb = codebook.load(cfg, check=False)
    templates = [t.contour for t in cb.all_types]
    assert sum(len(s) > 0 for s in lib.shapes) >= 16
    for i, shapes in enumerate(lib.shapes):
        if shapes:
            best, ambiguous = classify.decide(classify.distances(shapes, templates, cfg), cfg["classify"]["ambiguity_ratio"])
            assert set(best.tolist()) == {i} and not ambiguous.any()


def test_built_clicks_are_in_time_order_and_short(real_library):
    lib, _ = real_library
    assert np.all(np.diff(lib.click_t) >= 0) and lib.click_wave.shape[1] == 192 and len(lib.click_t) > 1000
    assert lib.steady.mean() > 0.3 and lib.env_db.shape[1] == realism.ENV_POINTS


def test_library_for_another_codebook_is_refused(real_library):
    _, cfg = real_library
    with pytest.raises(realism.RealismError):
        realism.load(cfg, "0" * 64)


# ---------------------------------------------------------------------------------------------- real wobble (WC-R3)
def toy_wobble(scale: float = 1.0) -> realism.Wobble:
    """Four 'real' wobbles of 20, 30, 50 and 80 frames."""
    rng = np.random.default_rng(1)
    res = tuple((40.0 * rng.standard_normal(n)).astype(np.float32) for n in (20, 30, 50, 80))
    return realism.Wobble(res, np.array([len(r) for r in res]), scale, (0.8, 1.25), {})


def test_wobble_keeps_length_and_mid_range_and_repeats():
    c = Contour(np.linspace(-500, 500, 48), HOP)
    w = toy_wobble()
    a, b = w.apply(c, np.random.default_rng(5)), w.apply(c, np.random.default_rng(5))
    assert a.n_frames == 48 and a.hop_s == HOP and np.array_equal(a.offset_hz, b.offset_hz)
    assert a.offset_hz.max() + a.offset_hz.min() == pytest.approx(0.0, abs=1e-6)
    assert not np.allclose(a.offset_hz, c.offset_hz)


def test_wobble_comes_from_a_real_whistle_of_similar_length():
    w = toy_wobble()
    got = w.apply(Contour(np.zeros(48), HOP), np.random.default_rng(0)).offset_hz
    r = np.interp(np.linspace(0, 1, 48), np.linspace(0, 1, 50), w.residuals[2])   # 50 frames: the only one in 38.4-60
    assert np.allclose(got, r - 0.5 * (r.max() + r.min()))


def test_zero_wobble_only_centres_the_shape():
    c = Contour(np.linspace(-300, 500, 40), HOP)
    assert np.allclose(toy_wobble(0.0).apply(c, np.random.default_rng(0)).offset_hz, c.offset_hz - 100.0)


@pytest.mark.localdata
def test_sender_checks_its_shapes_after_the_wobble_and_still_reads_back(book, small_bank, lib):
    plain = sender.Sender(codebook_path=book, check_model=False, rhythm_bank=small_bank, library=lib)
    assert plain.wobble is None                                   # a test codebook never loads the wobble from disk
    tx = sender.Sender(codebook_path=book, check_model=False, rhythm_bank=small_bank, library=lib, wobble=toy_wobble())
    varied, checked = set(), []
    vary, accepted = tx._vary, tx.accepted

    def spy_vary(c, rng):
        out = vary(c, rng)
        varied.add(id(out))
        return out

    def spy_accepted(c, gap, t):
        checked.append(c is None or id(c) in varied)
        return accepted(c, gap, t)

    tx._vary, tx.accepted = spy_vary, spy_accepted
    sent = tx.send("MEET AT DAWN", KEY, 11)
    assert checked and all(checked)                               # every shape the self-check saw had its wobble
    assert all(d.contour is not tx.templates[d.type_index] for d in sent.data if d.type_index < 16)
    rx = receiver.Receiver(codebook_path=book, check_model=False, rhythm_bank=small_bank)
    got = rx.decode_tracks(tracks_of(sent, small_bank, 5.5), KEY)
    assert got.ok and got.text == "MEET AT DAWN"


def test_wobble_settings_are_checked(cfg):
    from wcode.config import ConfigError, validate

    for key, bad in (("wobble_scale", -0.1), ("wobble_length_ratio", [1.2, 1.25])):
        c = copy.deepcopy(cfg)
        c["realism"][key] = bad
        with pytest.raises(ConfigError):
            validate(c, check_library=False)
