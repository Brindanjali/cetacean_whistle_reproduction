"""Classifier A (PLAN.md section 7 step 5): DTW between a whistle's contour and each template contour, plus a
duration term; a call is erased when it is ambiguous.

distance(q, t) = DTW(q, t) / max(len q, len t)                 mean |offset difference| in Hz along the path
               + duration_weight_short_hz_per_ms x (ms the query is shorter than the template)
               + duration_weight_long_hz_per_ms  x (ms the query is longer than the template)

Templates are centred on their mid-range. A detected track's offsets are measured from the centre frequency the key
gives for its slot (Track.contour(fc)), because the transmitter puts the type's mid-range exactly there; re-centring
the track instead would shift it whenever the detector trims a faint end.

DTW uses steps (1,0), (0,1), (1,1) with unit weights and a Sakoe-Chiba band around the length-scaled diagonal of
half-width max(dtw_band_min, dtw_band_frac x the longer length). The implementation runs many pairs at once in
NumPy (one Python loop over the cells of the longest pair), so thousands of whistles against hundreds of
templates take seconds rather than hours.
"""
from __future__ import annotations

import numpy as np

from .config import default_config
from .contour import Contour


def _pad(seqs) -> tuple[np.ndarray, np.ndarray]:
    lens = np.array([len(s) for s in seqs], dtype=np.int64)
    out = np.full((len(seqs), int(lens.max()) if len(seqs) else 0), np.nan)
    for i, s in enumerate(seqs):
        out[i, :len(s)] = s
    return out, lens


def dtw_pairs(a: np.ndarray, la: np.ndarray, b: np.ndarray, lb: np.ndarray, band_frac: float, band_min: int) -> np.ndarray:
    """Banded DTW cost / max(len) for pairs: a (P, ma) with lengths la, b (P, mb) with lengths lb (NaN padded)."""
    P = len(la)
    if P == 0:
        return np.zeros(0)
    ma, mb = int(la.max()), int(lb.max())
    a, b = a[:, :ma], b[:, :mb]
    half = np.maximum(band_min, np.ceil(band_frac * np.maximum(la, lb)))
    slope = (lb - 1) / np.maximum(la - 1, 1)
    jj = np.arange(mb)
    inf = np.inf
    prev = np.full((P, mb), inf)
    res = np.full(P, inf)
    for i in range(ma):
        cost = np.abs(a[:, i:i + 1] - b)
        cost[np.isnan(cost)] = inf
        cost[np.abs(jj[None, :] - (i * slope)[:, None]) > half[:, None]] = inf
        cur = np.empty_like(prev)
        cur[:, 0] = cost[:, 0] + (prev[:, 0] if i else 0.0)
        for j in range(1, mb):
            best = cur[:, j - 1] if i == 0 else np.minimum(np.minimum(prev[:, j], cur[:, j - 1]), prev[:, j - 1])
            cur[:, j] = cost[:, j] + best
        done = la - 1 == i
        if done.any():
            res[done] = cur[done, lb[done] - 1]
        prev = cur
    return res / np.maximum(la, lb)


def dtw_matrix(queries, templates, band_frac: float, band_min: int, max_pairs: int = 60_000) -> np.ndarray:
    """(Q, T) banded DTW between every query and every template (sequences of Hz offsets)."""
    Q, T = len(queries), len(templates)
    out = np.zeros((Q, T))
    if Q == 0 or T == 0:
        return out
    tb, lt = _pad(templates)
    step = max(1, max_pairs // T)
    order = np.argsort([len(q) for q in queries], kind="stable")     # similar lengths together: the loop runs to the longest
    for q0 in range(0, Q, step):
        sel = order[q0:q0 + step]
        qa, lq = _pad([queries[i] for i in sel])
        b = len(lq)
        out[sel] = dtw_pairs(np.repeat(qa, T, axis=0), np.repeat(lq, T), np.tile(tb, (b, 1)), np.tile(lt, b),
                             band_frac, band_min).reshape(b, T)
    return out


def distances(queries: list[Contour], templates: list[Contour], cfg: dict | None = None) -> np.ndarray:
    """(Q, T) classifier-A distances."""
    c = (cfg or default_config())["classify"]
    d = dtw_matrix([q.offset_hz for q in queries], [t.offset_hz for t in templates],
                   float(c["dtw_band_frac"]), int(c["dtw_band_min"]))
    if len(queries) and len(templates):
        diff = np.array([q.duration_ms for q in queries])[:, None] - np.array([t.duration_ms for t in templates])[None, :]
        d = d + float(c["duration_weight_short_hz_per_ms"]) * np.maximum(0.0, -diff) \
              + float(c["duration_weight_long_hz_per_ms"]) * np.maximum(0.0, diff)
    return d


def decide(dist: np.ndarray, ambiguity_ratio: float) -> tuple[np.ndarray, np.ndarray]:
    """Rows of distances -> (column of the best template, ambiguous?). Ambiguous: best / second-best > ratio."""
    dist = np.atleast_2d(dist)
    order = np.argsort(dist, axis=1)
    best = order[:, 0]
    if dist.shape[1] < 2:
        return best, np.zeros(len(best), dtype=bool)
    r = np.arange(len(dist))
    d1, d2 = dist[r, best], dist[r, order[:, 1]]
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = np.where(d2 > 0, d1 / d2, 1.0)
    return best, ratio > ambiguity_ratio
