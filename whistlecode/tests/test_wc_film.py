"""The page film's data (wcode/film.py, web/PLAN.md WEB-5)."""
import base64
import hashlib
import json

import numpy as np
import pytest

from wcode import film
from wcode.config import PROJECT_ROOT

FILM = PROJECT_ROOT / "web" / "film"


# ---------------------------------------------------------------------------------------------- helpers
def test_pca3_is_sorted_orthonormal_and_sign_stable():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(500, 8)) * np.array([5, 3, 2, 1, 1, 1, 1, 1])
    xyz, axes, share = film.pca3(x)
    assert xyz.shape == (500, 3) and axes.shape == (3, 8)
    assert share[0] > share[1] > share[2] and share.sum() < 1
    assert np.allclose(axes @ axes.T, np.eye(3), atol=1e-9)
    _, flipped, _ = film.pca3(-x)                  # same spread, mirrored data: the axes keep their signs
    assert np.allclose(flipped, axes)


def test_points_pack_and_unpack():
    xyz = np.array([[1.0, -2.0, 0.5], [-4.0, 0.0, 3.0]])
    buf, scale = film.pack_points(xyz, np.array([7, 2999]))
    assert len(buf) == 2 * film.POINT.itemsize == 16
    q, k = film.unpack_points(buf)
    assert k.tolist() == [7, 2999] and np.abs(q).max() == 32767
    assert np.allclose(q / scale, xyz, atol=1 / scale)


def test_component_numbers_must_fit_in_16_bits():
    with pytest.raises(film.FilmError):
        film.pack_points(np.zeros((1, 3)), np.array([70000]))


def test_the_first_exact_seed_is_taken_and_the_skipped_are_recorded():
    seed, result, skipped = film.first_exact(lambda s: (s == 2, f"r{s}", "exact" if s == 2 else "failed"), 5)
    assert seed == 2 and result == "r2" and [k["seed"] for k in skipped] == [0, 1]
    with pytest.raises(film.FilmError):
        film.first_exact(lambda s: (False, None, "failed"), 3)


def test_hear_it_is_the_first_message_whistle_heard_alone():
    s = [{"kind": "data", "part": "header", "t0": 0.0, "t1": 0.2},
         {"kind": "data", "part": "message", "t0": 1.0, "t1": 1.2},
         {"kind": "cover", "t0": 1.21, "t1": 1.5},
         {"kind": "data", "part": "message", "t0": 2.0, "t1": 2.2},
         {"kind": "click", "t0": 2.4, "t1": 2.41}]
    assert film.alone(s, 0.05) == 3
    assert film.alone(s, 0.25) is None


def test_thin_keeps_both_ends():
    assert film.thin([0, 100, 200], 5) == [0, 50, 100, 150, 200]
    assert film.thin([7], 3) == [7, 7, 7]


# ---------------------------------------------------------------------------------------------- the exported files (in git)
@pytest.fixture(scope="module")
def exported():
    p = FILM / "film.json"
    if not p.exists():
        pytest.skip("web/film/ has not been exported yet")
    return json.loads(p.read_text(encoding="utf-8"))


def test_the_exported_film_hangs_together(exported):
    assert exported["format"] == film.FORMAT
    learn = exported["learn"]
    assert (FILM / learn["file"]).stat().st_size == learn["n"] * learn["bytes_per_point"]
    assert len(exported["speak"]["shapes"]) == 17 and len(learn["codebook_components"]) == 17
    hide = exported["hide"]
    kinds = [s["kind"] for s in hide["sounds"]]
    assert (kinds.count("data"), kinds.count("cover"), kinds.count("click")) == (hide["n_data"], hide["n_cover"], hide["n_clicks"])
    assert [s["t0"] for s in hide["sounds"]] == sorted(s["t0"] for s in hide["sounds"])
    assert sum(bool(s.get("hear_it")) for s in hide["sounds"]) == 1
    assert (FILM / hide["hear_it_file"]).exists()
    assert exported["hear"]["text"] == hide["text"] == exported["provenance"]["example"]["text"]
    listen = exported["listen"]
    assert len(base64.b64decode(listen["levels_b64"])) == listen["rows"] * listen["cols"]
    assert listen["component"] in learn["codebook_components"]


@pytest.mark.localdata
def test_the_exported_film_matches_the_current_model_and_codebook(exported, cfg):
    from wcode import codebook, model

    npz = codebook.out_dir(cfg) / "codebook.npz"
    if not npz.exists():
        pytest.skip("the codebook is not on this machine")
    prov, now = exported["provenance"], model.check_lineage(cfg)
    for k in ("checkpoint_sha256", "latents_sha256", "gmm_sha256"):
        assert prov["model"][k] == now[k], f"web/film is stale ({k}); run: python whistlecode/whistlecode.py export-film"
    assert prov["codebook_sha256"] == hashlib.sha256(npz.read_bytes()).hexdigest(), \
        "web/film is stale (the codebook changed); run: python whistlecode/whistlecode.py export-film"
