"""Receiver.read_slots: each shape is compared with only the part of a track where that shape would sound."""
import numpy as np
import pytest

from wcode import detect, format2, layout, receiver
from wcode.contour import Contour

HOP = 1024 / 192000
BANDS = (6000.0, 8000.0, 10000.0, 12000.0)


def shape(start, stop, ms):
    return Contour(np.linspace(start, stop, int(round(ms / 1000 / HOP))), HOP)


TEMPLATES = [shape(-500, 500, 150), shape(500, -500, 150), shape(-500, 500, 300), shape(0, 0.001, 200)]


@pytest.fixture
def rx(cfg):
    r = receiver.Receiver.__new__(receiver.Receiver)
    r.cfg, r.templates = cfg, TEMPLATES
    return r


def slot(at_s=1.0):
    return layout.Slot(0, layout.PAYLOAD, at_s, BANDS, 0)


def whistle(template, band, at_s=1.0, before_hz=None, before_ms=0.0, after_hz=None, after_ms=0.0):
    """A track of the sent whistle, with extra frames the detector joined on before or after it."""
    fc = BANDS[band]
    head = np.full(int(round(before_ms / 1000 / HOP)), fc if before_hz is None else before_hz, dtype=np.float64)
    tail = np.full(int(round(after_ms / 1000 / HOP)), fc if after_hz is None else after_hz, dtype=np.float64)
    freq = np.concatenate([head, fc + TEMPLATES[template].offset_hz, tail])
    return detect.Track(at_s - len(head) * HOP, freq, HOP)


def read(rx, tracks):
    return rx.read_slots(receiver.TrackSet(tracks), [slot()], 0.0)


@pytest.mark.parametrize("template", range(4))
@pytest.mark.parametrize("band", range(4))
def test_a_clean_track_gives_shape_and_pitch(rx, template, band):
    got = read(rx, [whistle(template, band)])
    assert got.symbols[0] == (template << 2) | band
    assert got.n_missed == 0 and got.n_doubtful == 0


def test_sound_joined_before_the_whistle_is_ignored(rx):
    got = read(rx, [whistle(1, 2, before_hz=9400.0, before_ms=40.0)])
    assert got.symbols[0] == (1 << 2) | 2


def test_a_track_that_starts_long_before_the_slot_is_still_read(rx):
    got = read(rx, [whistle(0, 1, before_hz=8400.0, before_ms=120.0)])
    assert got.symbols[0] == (0 << 2) | 1


def test_a_far_away_joined_sound_does_not_change_the_pitch(rx):
    got = read(rx, [whistle(0, 1, before_hz=11500.0, before_ms=100.0)])      # the whole track's centre is near another band
    assert got.symbols[0] == (0 << 2) | 1


def test_a_short_tail_after_the_whistle_is_ignored(rx):
    got = read(rx, [whistle(1, 0, after_hz=5600.0, after_ms=12.0)])
    assert got.symbols[0] == (1 << 2) | 0


def test_a_long_whistle_is_not_read_as_a_short_shape_with_the_same_start(rx):
    """The first half of template 2 rises more slowly than template 0, and its length must decide."""
    got = read(rx, [whistle(2, 3)])
    assert got.symbols[0] == (2 << 2) | 3


def test_a_track_cut_short_is_still_read(rx):
    t = whistle(2, 1)
    cut = detect.Track(t.start_s, t.freq_hz[:int(0.8 * len(t.freq_hz))], HOP)
    assert read(rx, [cut]).symbols[0] == (2 << 2) | 1


def test_nothing_near_the_slot_is_lost(rx):
    assert read(rx, []).n_missed == 1
    far_in_time = whistle(0, 0, at_s=3.0)
    far_in_pitch = detect.Track(1.0, np.full(30, 15000.0), HOP)
    got = read(rx, [far_in_time, far_in_pitch])
    assert got.symbols[0] == format2.ERASED and got.n_missed == 1


def test_a_track_that_ends_before_the_slot_is_not_read(rx):
    got = read(rx, [whistle(0, 0, at_s=0.8)])
    assert got.symbols[0] == format2.ERASED


def test_the_track_that_fits_a_shape_best_is_chosen(rx):
    stranger = detect.Track(1.02, BANDS[2] + 300.0 * np.sin(np.linspace(0, 12, 28)), HOP)
    got = read(rx, [stranger, whistle(1, 2)])
    assert got.symbols[0] == (1 << 2) | 2


def test_an_ambiguous_track_is_marked_doubtful(rx):
    rx.templates = TEMPLATES[:2]                          # a rising and a falling shape; the flat track is equally far from both
    between = 0.5 * (TEMPLATES[0].offset_hz + TEMPLATES[1].offset_hz)
    got = read(rx, [detect.Track(1.0, BANDS[1] + between, HOP)])
    assert got.symbols[0] == format2.ERASED and got.n_doubtful == 1 and got.n_missed == 0
