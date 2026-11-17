"""The whistle alphabet (PLAN.md section 5): 16 symbol types and 1 signature whistle, chosen among the GMM components.

Build steps (build()):
  1. eligible components: N_k >= min_nk
  2. decode each one's mean and stability_samples samples; keep one clean contour with duration, span and gap in
     range, whose samples stay close to it (median distance <= the stability_quantile over all eligible components)
  3. one confusion pass: every candidate sent pass_sends times at pass_snr_db in encounter-214 noise (even-index
     files), detected with the reproduction's chain, and classified against all candidates with classifier A
  4. drop candidates detected less than min_detection_rate of the time; pick 17 greedily so that the worst confusion
     between two chosen types stays as low as possible
  5. verify: each chosen type sent verify_sends times in other noise (odd-index files); while a pair is confused more
     than verify_max_pair_confusion, replace the weaker type of that pair (at most verify_rounds times)
  6. the type least confused with the others becomes the signature; the other 16 get symbols 0-15 by component id

Outputs (out_dir, gitignored): codebook.npz, codebook.json (with the model hashes), pass.npz, verify.npz, gallery/.
load() refuses a codebook whose model files have changed since it was built (PLAN.md section 3.5).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

import numpy as np
import soundfile as sf

from . import channel, classify, contour, detect, model, repro, synth
from .config import PROJECT_ROOT, WhistleCodeError, default_config


class CodebookError(WhistleCodeError):
    pass


# ---------------------------------------------------------------------------------------------- the codebook
@dataclass(frozen=True)
class WhistleType:
    component: int
    symbol: int | None          # 0-15; None for the signature whistle
    mean: np.ndarray            # latent mean (D,)
    chol: np.ndarray            # Cholesky factor of the component covariance (D, D)
    contour: contour.Contour    # mean decode, centred
    nk: float


@dataclass(frozen=True)
class Codebook:
    types: list[WhistleType]    # symbol order 0..15
    signature: WhistleType
    info: dict                  # codebook.json

    @property
    def all_types(self) -> list[WhistleType]:
        """The 16 symbol types, then the signature (index 16)."""
        return [*self.types, self.signature]


def out_dir(cfg: dict | None = None, quick: bool = False) -> Path:
    d = PROJECT_ROOT / (cfg or default_config())["codebook"]["out_dir"]
    return d.with_name(d.name + "_quick") if quick else d


def save(path: Path, cb: Codebook) -> None:
    path.mkdir(parents=True, exist_ok=True)
    allt = cb.all_types
    lens = np.array([t.contour.n_frames for t in allt])
    contours = np.full((len(allt), int(lens.max())), np.nan)
    for i, t in enumerate(allt):
        contours[i, :lens[i]] = t.contour.offset_hz
    np.savez(path / "codebook.npz", component=np.array([t.component for t in allt]),
             symbol=np.array([-1 if t.symbol is None else t.symbol for t in allt]),
             mean=np.stack([t.mean for t in allt]), chol=np.stack([t.chol for t in allt]),
             contour=contours, contour_len=lens, hop_s=np.array(allt[0].contour.hop_s), nk=np.array([t.nk for t in allt]))
    (path / "codebook.json").write_text(json.dumps(cb.info, indent=1), encoding="utf-8")


def load(cfg: dict | None = None, path: Path | None = None, check: bool = True) -> Codebook:
    """Read the codebook. With check=True, refuse it unless final.pt and gmm.npz are the files it was built from."""
    cfg = cfg or default_config()
    path = Path(path or out_dir(cfg))
    if not (path / "codebook.npz").exists():
        raise CodebookError(f"no codebook in {path}; run: python whistlecode/whistlecode.py build-codebook")
    info = json.loads((path / "codebook.json").read_text(encoding="utf-8"))
    if check:
        now = model.check_lineage(cfg)
        built = info["model"]
        for k in ("checkpoint_sha256", "gmm_sha256"):
            if now[k] != built[k]:
                raise CodebookError(f"the model changed since the codebook was built ({k}: {built[k][:12]}... -> "
                                    f"{now[k][:12]}...); rebuild it (PLAN.md section 3.4)")
    z = np.load(path / "codebook.npz")
    hop = float(z["hop_s"])
    allt = [WhistleType(int(z["component"][i]), None if int(z["symbol"][i]) < 0 else int(z["symbol"][i]),
                        z["mean"][i], z["chol"][i], contour.Contour(z["contour"][i, :int(z["contour_len"][i])], hop),
                        float(z["nk"][i])) for i in range(len(z["component"]))]
    sig = [t for t in allt if t.symbol is None]
    types = sorted((t for t in allt if t.symbol is not None), key=lambda t: t.symbol)
    if len(sig) != 1 or [t.symbol for t in types] != list(range(len(types))):
        raise CodebookError(f"{path / 'codebook.npz'} is malformed")
    return Codebook(types, sig[0], info)


# ---------------------------------------------------------------------------------------------- selection (pure)
def restricted_stats(dist: np.ndarray, true: np.ndarray, members, ratio: float) -> dict:
    """Classify the rows whose true candidate is in `members` among `members` only (classifier A + ambiguity rule).

    dist: (rows, candidates) distances; true: (rows,) candidate index of each row. Returns the pair confusion matrix
    (rate a<->b over both types' detected sends), per-type accuracy and erasure rates, and totals."""
    m = np.asarray(members, dtype=np.int64)
    pos = {int(c): i for i, c in enumerate(m)}
    rows = np.isin(true, m)
    t = np.array([pos[int(x)] for x in true[rows]], dtype=np.int64)
    n = len(m)
    counts = np.bincount(t, minlength=n).astype(float)
    if rows.sum():
        best, amb = classify.decide(dist[rows][:, m], ratio)
    else:
        best, amb = np.zeros(0, np.int64), np.zeros(0, bool)
    wrong = (best != t) & ~amb
    conf = np.zeros((n, n))
    np.add.at(conf, (t[wrong], best[wrong]), 1.0)
    pair = conf + conf.T
    denom = counts[:, None] + counts[None, :]
    with np.errstate(divide="ignore", invalid="ignore"):
        pair_rate = np.where(denom > 0, pair / denom, 0.0)
    np.fill_diagonal(pair_rate, 0.0)
    correct = np.bincount(t[(best == t) & ~amb], minlength=n)
    erased = np.bincount(t[amb], minlength=n)
    with np.errstate(divide="ignore", invalid="ignore"):
        acc = np.where(counts > 0, correct / counts, 0.0)
        ers = np.where(counts > 0, erased / counts, 0.0)
    total = max(1.0, counts.sum())
    return {"members": m, "pair_rate": pair_rate, "confusions": conf, "worst_pair": float(pair_rate.max()) if n > 1 else 0.0,
            "error_rate": float(wrong.sum() / total), "erasure_rate": float(amb.sum() / total),
            "accuracy": acc, "erasure": ers, "n_detected": counts}


def greedy_select(dist: np.ndarray, true: np.ndarray, allowed, n: int, ratio: float, tdist: np.ndarray,
                  start: list | None = None) -> list[int]:
    """Add candidates one at a time, each time the one giving the lowest (worst pair confusion, error rate +
    half the erasure rate, -distance to the closest chosen template). Without `start`, begin with the candidate
    classified correctly most often among all allowed candidates."""
    allowed = [int(c) for c in allowed]
    chosen = [int(c) for c in (start or [])]
    if not chosen:
        own = restricted_stats(dist, true, allowed, ratio)
        chosen = [allowed[int(np.argmax(own["accuracy"]))]]
    while len(chosen) < n:
        best_key, best_c = None, None
        for c in allowed:
            if c in chosen:
                continue
            st = restricted_stats(dist, true, chosen + [c], ratio)
            key = (round(st["worst_pair"], 6), round(st["error_rate"] + 0.5 * st["erasure_rate"], 6),
                   -float(tdist[c, chosen].min()))
            if best_key is None or key < best_key:
                best_key, best_c = key, c
        if best_c is None:
            raise CodebookError(f"only {len(chosen)} candidates available, {n} needed")
        chosen.append(best_c)
    return chosen


# ---------------------------------------------------------------------------------------------- sending test whistles
class Sender:
    """Places test whistles into real noise, detects them with the reproduction's chain and returns the matched tracks."""

    def __init__(self, cfg: dict, pcfg, detector: detect.Detector, templates: list[contour.Contour], log):
        self.cfg, self.pcfg, self.det, self.templates, self.log = cfg, pcfg, detector, templates, log
        self.fs = float(cfg["synth"]["fs_hz"])
        self.fcs = synth.fc_pool(cfg)
        self._levels: dict[str, np.ndarray] = {}

    def run(self, labels: np.ndarray, files: list[Path], snr_db: float, rng: np.random.Generator, first_file: int = 0):
        """labels: candidate index per send (any order). Returns (labels in sent order, detected mask, contours of the
        detected sends, files used)."""
        sch = self.cfg["schedule"]
        lo, hi = sch["interval_s"]
        order = rng.permutation(np.asarray(labels))
        sent, found, contours_, used = [], [], [], []
        i, f = 0, first_file
        while i < len(order):
            path = files[f % len(files)]
            f += 1
            noise = channel.load_noise(path, self.cfg, self.pcfg)
            if path.name not in self._levels:
                self._levels[path.name] = channel.bin_levels(noise, self.fs, float(self.cfg["channel"]["snr_bin_hz"]))
            levels = self._levels[path.name]
            x = noise.astype(np.float64).copy()
            end = len(x) / self.fs - float(sch["end_margin_s"])
            t = float(sch["start_s"])
            starts, fcs, labs = [], [], []
            while i < len(order):
                c = self.templates[int(order[i])]
                if t + c.n_frames * c.hop_s > end:
                    break
                fc = float(rng.choice(self.fcs))
                w = synth.whistle(c, fc, rng, self.cfg, self.fs)
                a = channel.amplitude_for_snr(snr_db, fc + float(np.mean(c.offset_hz)), levels, self.fs, self.cfg)
                s0 = int(round(t * self.fs))
                x[s0:s0 + len(w)] += a * w
                starts.append(t)
                fcs.append(fc)
                labs.append(int(order[i]))
                i += 1
                t += float(rng.uniform(lo, hi))
            tracks = self.det.tracks(x.astype(np.float32), self.fs)
            for lab, fc, m in zip(labs, fcs, detect.match(tracks, starts, fcs, self.cfg)):
                sent.append(lab)
                found.append(m is not None)
                if m is not None:
                    contours_.append(m.contour(fc))             # offsets from the slot's known fc (classifier A)
            used.append(path.name)
            self.log(f"    segment {len(used):3d}: {path.name}  {len(labs)} whistles, {sum(found[-len(labs):])} found"
                     f"  ({i}/{len(order)})")
        return np.array(sent, dtype=np.int64), np.array(found, dtype=bool), contours_, used


# ---------------------------------------------------------------------------------------------- build
def _stability(vae, gmm: model.GMM, comps: np.ndarray, means: list[contour.Contour], pcfg, cfg, rng,
               ns: int | None = None) -> np.ndarray:
    """Median classifier-A distance between each component's mean contour and the contours of its samples."""
    cb, cl = cfg["codebook"], cfg["classify"]
    ns = int(ns or cb["stability_samples"])
    thr = float(cfg["synth"]["contour_threshold"])
    qa, ta, ok = [], [], []
    for c0 in range(0, len(comps), 64):                 # 64 components at a time: about 130 MB of images
        z = np.concatenate([gmm.means[k] + rng.standard_normal((ns, gmm.means.shape[1])) @ gmm.cholesky(k).T
                            for k in comps[c0:c0 + 64]])
        for j, img in enumerate(model.decode(vae, z, int(cfg["model"]["decode_batch"]))):
            c, _ = contour.from_image(img, pcfg, thr)
            ok.append(c is not None)
            qa.append(c.offset_hz if c is not None else np.zeros(1))
            ta.append(means[c0 + j // ns].offset_hz)
    a, la = classify._pad(qa)
    b, lb = classify._pad(ta)
    d = classify.dtw_pairs(a, la, b, lb, float(cl["dtw_band_frac"]), int(cl["dtw_band_min"]))
    diff_ms = (la - lb) * means[0].hop_s * 1000              # sample minus mean
    d = d + float(cl["duration_weight_short_hz_per_ms"]) * np.maximum(0.0, -diff_ms) \
          + float(cl["duration_weight_long_hz_per_ms"]) * np.maximum(0.0, diff_ms)
    d[~np.array(ok)] = np.inf
    return np.median(d.reshape(len(comps), ns), axis=1)


def _software() -> dict:
    import torch
    return {"numpy": np.__version__, "torch": torch.__version__, "reedsolo": metadata.version("reedsolo"),
            "soundfile": sf.__version__}


def _gallery(path: Path, cb: Codebook, stats: dict, cfg: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    g = path / "gallery"
    g.mkdir(parents=True, exist_ok=True)
    fs = float(cfg["synth"]["fs_hz"])
    fc = float(cfg["codebook"]["gallery_fc_hz"])
    allt = cb.all_types
    fig, axes = plt.subplots(3, 6, figsize=(18, 8), sharey=True)
    for ax, (i, t) in zip(axes.flat, enumerate(allt)):
        name = "signature" if t.symbol is None else f"symbol {t.symbol:x}"
        ms = (np.arange(t.contour.n_frames) + 0.5) * t.contour.hop_s * 1000
        ax.plot(ms, t.contour.offset_hz, lw=2, color="C3" if t.symbol is None else "C0")
        ty = stats["types"][i]
        ax.set_title(f"{name} | comp {t.component} | N_k {t.nk:.0f}\n{t.contour.duration_ms:.0f} ms, "
                     f"det {ty['detection_rate']:.0%}, acc {ty['accuracy']:.0%}", fontsize=8)
        ax.grid(alpha=0.3)
        x = synth.whistle(t.contour, fc, np.random.default_rng(t.component), cfg, fs)
        pad = np.zeros(int(0.1 * fs))
        tag = "signature" if t.symbol is None else f"symbol_{t.symbol:02d}"
        sf.write(g / f"{tag}_comp{t.component}.wav", np.concatenate([pad, 0.5 * x / np.abs(x).max(), pad]), int(fs),
                 subtype="PCM_16")
        f2, a2 = plt.subplots(figsize=(4, 3))
        a2.plot(ms, fc + t.contour.offset_hz, lw=2)
        a2.set_xlabel("ms")
        a2.set_ylabel("Hz")
        a2.set_title(f"{name} (component {t.component}) at {fc:.0f} Hz")
        a2.grid(alpha=0.3)
        f2.tight_layout()
        f2.savefig(g / f"{tag}_comp{t.component}.png", dpi=110)
        plt.close(f2)
    for ax in list(axes.flat)[len(allt):]:
        ax.axis("off")
    for ax in axes[:, 0]:
        ax.set_ylabel("offset from mid-range (Hz)")
    for ax in axes[-1]:
        ax.set_xlabel("ms")
    fig.suptitle("WhistleCode codebook: 16 symbol types and the signature whistle (mean decodes, epoch-specific)")
    fig.tight_layout()
    fig.savefig(path / "codebook_overview.png", dpi=110)
    plt.close(fig)
    m = np.asarray(stats["verify_confusions"], float)
    n_det = np.asarray([t["n_detected"] for t in stats["types"]], float)
    rate = m / np.maximum(n_det[:, None], 1)
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(rate, cmap="magma_r", vmin=0, vmax=max(0.02, float(rate.max())))
    labels = [("sig" if t.symbol is None else f"{t.symbol:x}") for t in allt]
    ax.set_xticks(range(len(allt)), labels)
    ax.set_yticks(range(len(allt)), labels)
    ax.set_xlabel("classified as")
    ax.set_ylabel("sent")
    ax.set_title("Verification: wrong calls per sent type (erasures excluded)")
    fig.colorbar(im)
    fig.tight_layout()
    fig.savefig(path / "verify_confusion.png", dpi=110)
    plt.close(fig)


def build(cfg: dict | None = None, quick: bool = False, log=print) -> dict:
    """Build the codebook (see the module docstring). quick=True: a few sends only, into <out_dir>_quick, for checks."""
    cfg = cfg or default_config()
    cb_cfg = cfg["codebook"]
    t_all = time.perf_counter()
    timings = {}
    path = out_dir(cfg, quick)
    path.mkdir(parents=True, exist_ok=True)
    lines = []

    def say(msg: str) -> None:
        lines.append(msg)
        log(msg)

    pass_sends = 4 if quick else int(cb_cfg["pass_sends"])
    verify_sends = 12 if quick else int(cb_cfg["verify_sends"])
    rounds = 1 if quick else int(cb_cfg["verify_rounds"])
    ratio = float(cfg["classify"]["ambiguity_ratio"])
    rng = np.random.default_rng(int(cb_cfg["seed"]))
    n_needed = int(cb_cfg["n_types"]) + 1

    # 1. model
    t0 = time.perf_counter()
    lineage = model.check_lineage(cfg)
    say(f"model: {lineage['checkpoint']} sha256 {lineage['checkpoint_sha256'][:12]}..., GMM K = {lineage['n_components']}")
    dev = model.device(cfg)
    vae = model.load_vae(cfg, dev)
    gmm = model.load_gmm(cfg)
    pcfg = repro.load_pipeline_config()
    thr = float(cfg["synth"]["contour_threshold"])
    nk = gmm.nk
    eligible = np.where(nk >= float(cb_cfg["min_nk"]))[0]
    say(f"eligible components (N_k >= {cb_cfg['min_nk']}): {len(eligible)} of {len(nk)}")

    # 2. shape filter and stability
    imgs = model.decode(vae, gmm.means[eligible], int(cfg["model"]["decode_batch"]))
    means, gaps, valid = [], [], []
    for img in imgs:
        c, gap = contour.from_image(img, pcfg, thr)
        means.append(c)
        gaps.append(gap)
        valid.append(c is not None)
    valid = np.array(valid)
    comps_v = eligible[valid]
    means_v = [m for m in means if m is not None]
    gaps_v = np.array(gaps)[valid]
    stab = _stability(vae, gmm, comps_v, means_v, pcfg, cfg, rng, ns=4 if quick else None)
    dur = np.array([m.duration_ms for m in means_v])
    span = np.array([m.span_hz for m in means_v])
    d_lo, d_hi = cb_cfg["duration_ms"]
    s_lo, s_hi = cb_cfg["span_hz"]
    f_gap = gaps_v <= int(cb_cfg["max_gap_cols"])
    f_dur = (dur >= d_lo) & (dur <= d_hi)
    f_span = (span >= s_lo) & (span <= s_hi)
    stab_thr = float(np.quantile(stab[np.isfinite(stab)], float(cb_cfg["stability_quantile"])))
    f_stab = stab <= stab_thr
    keep = f_gap & f_dur & f_span & f_stab
    cand_comp = comps_v[keep]
    cand = [m for m, k in zip(means_v, keep) if k]
    counts = {"components": int(len(nk)), "eligible": int(len(eligible)), "mean_contour": int(valid.sum()),
              "gap_ok": int(f_gap.sum()), "duration_ok": int(f_dur.sum()), "span_ok": int(f_span.sum()),
              "stable": int(f_stab.sum()), "stability_threshold": round(stab_thr, 2), "candidates": int(len(cand))}
    say(f"shape filter: {counts}")
    if len(cand) < n_needed:
        raise CodebookError(f"only {len(cand)} candidates pass the shape filter, {n_needed} needed (PLAN.md section 5 fallback)")
    timings["filter"] = round(time.perf_counter() - t0, 1)

    # 3. confusion pass
    t0 = time.perf_counter()
    files = channel.noise_files(int(cb_cfg["noise_encounter"]))
    pass_files, verify_files = files[0::2], files[1::2]
    detector = detect.Detector(cfg, dev)
    sender = Sender(cfg, pcfg, detector, cand, say)
    snr = float(cb_cfg["pass_snr_db"])
    say(f"confusion pass: {len(cand)} candidates x {pass_sends} sends at {snr:g} dB in encounter-{cb_cfg['noise_encounter']} noise")
    labels = np.repeat(np.arange(len(cand)), pass_sends)
    p_sent, p_found, p_contours, p_files = sender.run(labels, pass_files, snr, rng)
    p_true = p_sent[p_found]
    p_dist = classify.distances(p_contours, cand, cfg)
    det_rate = np.bincount(p_sent[p_found], minlength=len(cand)) / np.maximum(np.bincount(p_sent, minlength=len(cand)), 1)
    tdist = classify.distances(cand, cand, cfg)
    np.savez(path / "pass.npz", components=cand_comp, sent=p_sent, found=p_found, dist=p_dist, detection_rate=det_rate,
             template_dist=tdist)
    timings["pass"] = round(time.perf_counter() - t0, 1)
    say(f"pass: {p_found.sum()} of {len(p_sent)} whistles found ({p_found.mean():.1%}), "
        f"median detection rate per candidate {np.median(det_rate):.0%}  [{timings['pass']} s]")

    # 4. selection
    allowed = np.where(det_rate >= float(cb_cfg["min_detection_rate"]))[0]
    say(f"candidates detected >= {cb_cfg['min_detection_rate']:.0%}: {len(allowed)}")
    if len(allowed) < n_needed:
        raise CodebookError(f"only {len(allowed)} candidates are detected often enough, {n_needed} needed")
    chosen = greedy_select(p_dist, p_true, allowed, n_needed, ratio, tdist)
    st = restricted_stats(p_dist, p_true, chosen, ratio)
    say(f"selected 17 (pass data): worst pair {st['worst_pair']:.1%}, errors {st['error_rate']:.1%}, erasures {st['erasure_rate']:.1%}")

    # 5. verification with replacement
    t0 = time.perf_counter()
    v_rows: dict[int, np.ndarray] = {}
    v_sent: dict[int, int] = {}
    v_found: dict[int, int] = {}
    tried: set[int] = set()
    history = []
    next_file = 0
    passed = False
    for rnd in range(rounds + 1):
        need = [c for c in chosen if c not in v_rows]
        if need:
            say(f"verification round {rnd}: sending {len(need)} type(s) x {verify_sends}")
            s, f, cs, used = sender.run(np.repeat(need, verify_sends), verify_files, snr, rng, next_file)
            next_file += len(used)
            d = classify.distances(cs, cand, cfg)
            tr = s[f]
            for c in need:
                v_rows[c] = d[tr == c]
                v_sent[c] = int((s == c).sum())
                v_found[c] = int(((s == c) & f).sum())
        dist_v = np.concatenate([v_rows[c] for c in chosen])
        true_v = np.concatenate([np.full(len(v_rows[c]), c) for c in chosen])
        vs = restricted_stats(dist_v, true_v, chosen, ratio)
        history.append({"round": rnd, "chosen": [int(cand_comp[c]) for c in chosen], "worst_pair": round(vs["worst_pair"], 4),
                        "error_rate": round(vs["error_rate"], 4), "erasure_rate": round(vs["erasure_rate"], 4)})
        say(f"  worst pair {vs['worst_pair']:.1%}, errors {vs['error_rate']:.1%}, erasures {vs['erasure_rate']:.1%}")
        if vs["worst_pair"] <= float(cb_cfg["verify_max_pair_confusion"]):
            passed = True
            break
        if rnd == rounds:
            break
        a, b = np.unravel_index(np.argmax(vs["pair_rate"]), vs["pair_rate"].shape)
        drop = chosen[a] if vs["accuracy"][a] <= vs["accuracy"][b] else chosen[b]
        tried.add(drop)
        rest = [c for c in chosen if c != drop]
        pool = [c for c in allowed if c not in tried and c not in rest]
        if not pool:
            say("  no candidates left to try")
            break
        chosen = greedy_select(p_dist, p_true, pool + rest, n_needed, ratio, tdist, start=rest)
        say(f"  replaced component {int(cand_comp[drop])} by {int(cand_comp[chosen[-1]])}")
    timings["verify"] = round(time.perf_counter() - t0, 1)

    # 6. signature, symbols, outputs
    worst_each = vs["pair_rate"].max(axis=1)
    sig_i = int(np.lexsort((-vs["accuracy"], worst_each))[0])
    sig_c = chosen[sig_i]
    sym_cs = sorted((c for c in chosen if c != sig_c), key=lambda c: int(cand_comp[c]))
    ordered = sym_cs + [sig_c]
    idx = [chosen.index(c) for c in ordered]

    def wtype(c: int, symbol):
        k = int(cand_comp[c])
        return WhistleType(k, symbol, gmm.means[k].copy(), gmm.cholesky(k), cand[c], float(nk[k]))

    type_stats = [{"symbol": (None if c == sig_c else s), "component": int(cand_comp[c]), "nk": round(float(nk[cand_comp[c]]), 1),
                   "duration_ms": round(cand[c].duration_ms, 1), "span_hz": round(cand[c].span_hz, 1),
                   "detection_rate": round(v_found[c] / max(1, v_sent[c]), 4), "accuracy": round(float(vs["accuracy"][i]), 4),
                   "erasure_rate": round(float(vs["erasure"][i]), 4), "n_sent": v_sent[c], "n_detected": int(v_found[c]),
                   "worst_pair": round(float(worst_each[i]), 4)}
                  for s, (c, i) in enumerate(zip(ordered, idx))]
    conf = vs["confusions"][np.ix_(idx, idx)]
    info = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "quick": quick, "model": lineage,
            "settings": {k: cfg[k] for k in ("codebook", "classify", "detect", "synth", "channel", "schedule")},
            "software": _software(), "counts": counts,
            "pass": {"snr_db": snr, "sends_per_candidate": pass_sends, "whistles": int(len(p_sent)),
                     "found": int(p_found.sum()), "files": p_files, "allowed": int(len(allowed))},
            "verification": {"passed": passed, "sends_per_type": verify_sends, "rounds": history,
                             "worst_pair": round(vs["worst_pair"], 4), "error_rate": round(vs["error_rate"], 4),
                             "erasure_rate": round(vs["erasure_rate"], 4), "confusions": conf.astype(int).tolist()},
            "types": type_stats[:-1], "signature": type_stats[-1], "timings_s": timings}
    cb = Codebook([wtype(c, s) for s, c in enumerate(sym_cs)], wtype(sig_c, None), info)
    save(path, cb)
    np.savez(path / "verify.npz", **{f"comp{int(cand_comp[c])}": v_rows[c] for c in v_rows},
             candidate_components=cand_comp)
    _gallery(path, cb, {"types": type_stats, "verify_confusions": conf}, cfg)
    timings["total"] = round(time.perf_counter() - t_all, 1)
    info["timings_s"] = timings
    (path / "codebook.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    say(f"codebook written to {path} (verification {'PASSED' if passed else 'FAILED'}) [{timings['total']} s]")
    (path / "build_log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return info
