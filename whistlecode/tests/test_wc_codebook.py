"""codebook.py: selection on known confusions, saving and loading, and the model-hash check (PLAN.md section 3.5)."""
import copy

import numpy as np
import pytest

from wcode import codebook, model
from wcode.contour import Contour


def toy_pass():
    """4 candidates, 20 whistles each. Whistles of 0 and 1 often look like each other; 2 and 3 are distinct."""
    rng = np.random.default_rng(0)
    rows, true = [], []
    for c in range(4):
        for _ in range(20):
            d = np.full(4, 100.0) + rng.uniform(0, 5, 4)
            d[c] = 10.0
            if c in (0, 1) and rng.random() < 0.3:
                d[1 - c] = 5.0                             # mistaken for its twin 30 % of the time
            rows.append(d)
            true.append(c)
    return np.array(rows), np.array(true)


def test_restricted_stats():
    dist, true = toy_pass()
    st = codebook.restricted_stats(dist, true, [0, 1, 2], ratio=0.8)
    assert st["pair_rate"][0, 1] > 0.1 and st["pair_rate"][0, 2] == 0.0
    assert st["accuracy"][2] == 1.0 and st["worst_pair"] == st["pair_rate"][0, 1]
    st2 = codebook.restricted_stats(dist, true, [0, 2, 3], ratio=0.8)
    assert st2["worst_pair"] == 0.0                         # without 1, nothing pulls 0 away


def test_greedy_avoids_the_twins():
    dist, true = toy_pass()
    tdist = np.ones((4, 4))
    chosen = codebook.greedy_select(dist, true, [0, 1, 2, 3], 3, 0.8, tdist)
    assert not {0, 1} <= set(chosen) and {2, 3} <= set(chosen)


def fake_codebook(lineage):
    types = [codebook.WhistleType(100 + i, i, np.full(64, float(i)), np.eye(64), Contour(np.linspace(-i, i, 20 + i), 0.005), 50.0)
             for i in range(16)]
    sig = codebook.WhistleType(999, None, np.zeros(64), np.eye(64), Contour(np.zeros(30), 0.005), 70.0)
    return codebook.Codebook(types, sig, {"model": lineage, "quick": False})


@pytest.mark.localdata
def test_save_load_round_trip(tmp_path, cfg):
    lineage = model.check_lineage(cfg)
    cb = fake_codebook(lineage)
    codebook.save(tmp_path, cb)
    got = codebook.load(cfg, tmp_path, check=True)
    assert [t.symbol for t in got.types] == list(range(16)) and got.signature.component == 999
    assert np.array_equal(got.types[5].contour.offset_hz, cb.types[5].contour.offset_hz)
    assert np.array_equal(got.types[3].chol, np.eye(64))


@pytest.mark.localdata
def test_load_refuses_another_model(tmp_path, cfg):
    lineage = copy.deepcopy(model.check_lineage(cfg))
    lineage["checkpoint_sha256"] = "0" * 64                  # as if built before the training resume
    codebook.save(tmp_path, fake_codebook(lineage))
    with pytest.raises(codebook.CodebookError):
        codebook.load(cfg, tmp_path, check=True)


@pytest.mark.localdata
def test_lineage_of_the_current_model(cfg):
    lin = model.check_lineage(cfg)
    assert lin["checkpoint"].endswith("checkpoints/final.pt")
    assert len(lin["checkpoint_sha256"]) == 64 and lin["n_components"] == 3000
