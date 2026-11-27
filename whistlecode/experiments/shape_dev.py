"""WC-R3 development (PLAN.md section 8.7): what gives the coded whistle shapes away, and does a sender change fix it?

Encounter 214 only: campaign v2's encounter 276 is never touched here.

- Real side: in-range whistles (E7's limits) detected in 80 encounter-214 recordings spread over the encounter.
- Coded side: the data whistles of fresh messages sent through encounter-214 noise at 15 and 20 dB and picked up by the same
  detector, exactly as E7 does (experiments/paper_covert.py), with each whistle's type and pitch kept.
- Score: E7's classifier, features, signal-to-noise balancing and recording/message splits (realism_score.score). The
  adoption rule compares this AUC between senders: a sender change needs a fall of at least 0.03.
- Prototype fix, `wobble_<scale>`: every data shape, after it is drawn and before the sender's self-check, gets the
  wobble of a real encounter-191 whistle of similar length (19-84 frames, within -20/+25 %): that whistle's contour minus
  its cubic fit, stretched to the shape's length and multiplied by <scale>. Encounter 191 trained the VAE and never serves
  as noise or as the real side here, so no encounter-214 material reaches the coded side through it.
- Diagnosis (reported, no mark): the AUC of each feature group on its own (shape, loudness, harmonics), each feature's own
  AUC and its quartiles on both sides, and how fake each of the 16 types looks (mean held-out classifier score).

    python whistlecode/experiments/shape_dev.py build-delphi      # the epoch-150 voice's codebook and library, own folders
    python whistlecode/experiments/shape_dev.py build-delphi-library   # only the library, for a codebook that failed verification
    python whistlecode/experiments/shape_dev.py real
    python whistlecode/experiments/shape_dev.py coded deployed tau_0 ...
    python whistlecode/experiments/shape_dev.py score deployed tau_0 ...
    python whistlecode/experiments/shape_dev.py messages deployed delphi ...   # the adoption rule's message check
    python whistlecode/experiments/shape_dev.py spread deployed     # WC-R3a: per type, real cluster members against coded

Adoption check (PLAN.md 8.7): 50 sweep-set messages (8-32 characters, as E2) at 10 dB of encounter-214 noise, the same
messages, keys and noise for every variant, each read by the receiver that holds the variant's codebook. A sender change may
cost at most 2 of 50 exact messages against the deployed sender.

Results: whistlecode/outputs/shape_dev/ (gitignored): real_214.pkl, coded_<variant>.pkl, score_<variant>.json.
"""
from __future__ import annotations

import argparse
import copy
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

WC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WC))
sys.path.insert(0, str(WC / "experiments"))

import paper_covert as pc  # noqa: E402
import realism_score as rs  # noqa: E402
import paper_eval as pe  # noqa: E402
from wcode import channel, contour, detect, model, realism, receiver, sender  # noqa: E402
from wcode.config import PROJECT_ROOT, default_config  # noqa: E402

OUT = PROJECT_ROOT / "whistlecode" / "outputs" / "shape_dev"
DEV_SEED = 20261127                 # [DECISION] WC-R3 development only; no other run uses it
ENCOUNTER = 214                     # [PLAN] 8.7: second-round development uses encounter 214 only
REAL_FILES = 80                     # [DECISION] twice E7's 40, for about twice the real whistles and a steadier AUC
# [PLAN] 8.7: the epoch-150 voice (Delphi) gets its codebook in a separate folder; its realism library goes beside it
DELPHI = {"model": {"run_dir": "models/vaegmm/V1_L64_b1e-4_critic_E191_epoch150"},
          "codebook": {"out_dir": "whistlecode/outputs/codebook_epoch150"},
          "realism": {"out_dir": "whistlecode/outputs/realism_epoch150"}}
GROUPS = {"shape": list(range(8)), "loudness": [8, 9, 10], "harmonics": [11, 12, 13]}


# ---------------------------------------------------------------------------------------------- senders under test
def v1_sender(cfg: dict) -> dict:
    """Campaign v1's sender: no real wobble."""
    c = copy.deepcopy(cfg)
    c["realism"]["wobble_scale"] = 0.0
    return c


def delphi_cfg(cfg: dict) -> dict:
    c = copy.deepcopy(cfg)
    for section, values in DELPHI.items():
        c[section].update(values)
    return c


def build_delphi(cfg: dict) -> None:
    """Delphi's codebook (the same build and settings as v1's, EXP-013) and realism library, in folders of their own."""
    from wcode import codebook

    c = delphi_cfg(cfg)
    for k in ("codebook", "realism"):
        if (PROJECT_ROOT / c[k]["out_dir"]).exists():
            raise SystemExit(f"{c[k]['out_dir']} exists; output folders are never reused")
    info = codebook.build(c, log=lambda m: print(m, flush=True))
    if not info["verification"]["passed"]:
        raise SystemExit("Delphi's codebook failed its verification; no realism library is built")
    realism.build(c, log=lambda m: print(m, flush=True))


def build_delphi_library(cfg: dict) -> None:
    """The realism library for Delphi's codebook as built, even if it failed its verification. [DECISION] 2026-11-27: the
    plan reports the Delphi ablation without a mark, so it is measured on the codebook the standard build gives; a codebook
    that failed its verification is never adopted."""
    c = delphi_cfg(cfg)
    if (PROJECT_ROOT / c["realism"]["out_dir"]).exists():
        raise SystemExit(f"{c['realism']['out_dir']} exists; output folders are never reused")
    info = json.loads((PROJECT_ROOT / c["codebook"]["out_dir"] / "codebook.json").read_text(encoding="utf-8"))
    v = info["verification"]
    print(f"Delphi's codebook: verification {'passed' if v['passed'] else 'FAILED'} (worst pair {v.get('worst_pair')})", flush=True)
    realism.build(c, log=lambda m: print(m, flush=True))

RESIDUAL_FRAMES = (19, 84)          # 100-450 ms at 5.333 ms per frame, the codebook's duration limits
RESIDUAL_MIN_OBSERVED = 0.9         # [DECISION] as [realism] min_observed_fraction


def residuals_191() -> list[np.ndarray]:
    """Contour minus cubic fit of every in-range, well-observed encounter-191 track (cached in OUT)."""
    cache = OUT / "residuals_191.npz"
    if cache.exists():
        z = np.load(cache)
        return np.split(z["r"], z["offsets"][1:-1])
    z = np.load(PROJECT_ROOT / "preprocessed" / "encounter_191" / "contours.npz")
    n_frames, observed, offsets, freq = z["n_frames"], z["observed_fraction"], z["offsets"], z["freq_hz"]   # read once
    out = []
    for i, n in enumerate(n_frames):
        if not RESIDUAL_FRAMES[0] <= n <= RESIDUAL_FRAMES[1] or observed[i] < RESIDUAL_MIN_OBSERVED:
            continue
        f = freq[offsets[i]:offsets[i + 1]].astype(np.float64)
        span, centre = float(f.max() - f.min()), 0.5 * float(f.max() + f.min())
        if not (pc.SPAN_HZ[0] <= span <= pc.SPAN_HZ[1] and 5000.0 <= centre <= 12000.0):
            continue
        x = np.arange(n) / n
        out.append((f - np.polyval(np.polyfit(x, f, 3), x)).astype(np.float32))
    OUT.mkdir(parents=True, exist_ok=True)
    np.savez(cache, r=np.concatenate(out), offsets=np.r_[0, np.cumsum([len(r) for r in out])])
    return out


class WobbleSender(sender.Sender):
    """The deployed sender, whose drawn shapes get a real encounter-191 whistle's wobble before the self-check."""

    def __init__(self, cfg: dict, scale: float, base: sender.Sender):
        super().__init__(cfg, rhythm_bank=base.bank, library=base.library)
        self.scale = float(scale)
        self.res = residuals_191()
        self.res_n = np.array([len(r) for r in self.res])

    def proto_wobble(self, c: contour.Contour, rng: np.random.Generator) -> contour.Contour:
        n = c.n_frames
        ok = np.flatnonzero((self.res_n >= 0.8 * n) & (self.res_n <= 1.25 * n))
        r = self.res[int(ok[rng.integers(len(ok))])] if len(ok) else self.res[int(np.argmin(np.abs(self.res_n - n)))]
        r = np.interp(np.linspace(0.0, 1.0, n), np.linspace(0.0, 1.0, len(r)), r)
        return contour.Contour(contour.centred(c.offset_hz + self.scale * r), c.hop_s)

    def _shapes(self, idx: np.ndarray, tau: float, rng: np.random.Generator):
        """transmitter._shapes with the wobble added before the self-check; a fallback mean shape gets one too."""
        n = len(idx)
        shapes = [self.templates[int(i)] for i in idx]
        redraws = np.zeros(n, dtype=np.int64)
        if tau == 0:
            return [self.proto_wobble(c, rng) for c in shapes], redraws, np.zeros(n, dtype=bool)
        tries = 1 + int(self.cfg["transmit"]["self_check_redraws"])
        thr = float(self.cfg["synth"]["contour_threshold"])
        pending = np.arange(n)
        for attempt in range(tries):
            if not len(pending):
                break
            t = idx[pending]
            eps = rng.standard_normal((len(pending), self.means.shape[1]))
            z = self.means[t] + tau * np.einsum("nij,nj->ni", self.chols[t], eps)
            still = []
            for p, ti, img in zip(pending, t, model.decode(self.vae, z, int(self.cfg["model"]["decode_batch"]))):
                c, gap = contour.from_image(img, self.pcfg, thr)
                c = self.proto_wobble(c, rng) if c is not None else None
                if self.accepted(c, gap, int(ti)):
                    shapes[p] = c
                    redraws[p] = attempt
                else:
                    still.append(p)
            pending = np.array(still, dtype=np.int64)
        fell = np.zeros(n, dtype=bool)
        fell[pending] = True
        redraws[pending] = tries
        for p in pending:
            shapes[p] = self.proto_wobble(shapes[p], rng)
        return shapes, redraws, fell


def variants(name: str, cfg: dict, base: sender.Sender | None):
    """(sender, config) of a named variant; `base` is the deployed sender, whose bank and library the variants share."""
    if name == "adopted":                       # the sender as config.toml now sets it (wobble adopted, D-032)
        return sender.Sender(cfg), cfg
    cfg = v1_sender(cfg)                        # every other variant was measured on campaign v1's sender
    base = sender.Sender(cfg, rhythm_bank=base.bank, library=base.library) if base is not None else None
    if name == "deployed":                      # the sender deployed when WC-R3 began (campaign v1's)
        return sender.Sender(cfg), cfg
    if name.startswith("wobble_"):
        return WobbleSender(cfg, float(name[7:]), base), cfg
    if name == "delphi":
        return sender.Sender(delphi_cfg(cfg)), delphi_cfg(cfg)
    if name.startswith("tau_"):
        c = copy.deepcopy(cfg)
        c["transmit"]["tau"] = float(name[4:])
        return sender.Sender(c, rhythm_bank=base.bank, library=base.library), c
    raise SystemExit(f"unknown variant {name!r}")


# ---------------------------------------------------------------------------------------------- collection
def real_rows(det: detect.Detector, cfg: dict, pcfg) -> list[dict]:
    files = channel.noise_files(ENCOUNTER)
    rows = []
    for g, i in enumerate(np.linspace(0, len(files) - 1, REAL_FILES).astype(int).tolist()):
        x = channel.load_noise(files[i], cfg, pcfg)
        mag, floor = rs.spectrum(x)
        for t in det.tracks(x, realism.FS):
            got = rs.features(t, mag, floor)
            if got is not None and pc.in_range(t):
                rows.append({"f": got[0], "snr": got[1], "group": f"{ENCOUNTER}-{g}", "basic": pc.basic7(t),
                             "contour": np.asarray(t.freq_hz, dtype=np.float32)})
    return rows


def coded_rows(name: str, tx: sender.Sender, det: detect.Detector, cfg: dict) -> list[dict]:
    """paper_covert.coded_whistles with DEV_SEED, encounter-214 noise, and each whistle's type, pitch and contour kept."""
    rng = np.random.default_rng([DEV_SEED, 1])
    alphabet = np.array(list(cfg["format2"]["alphabet"]))
    rows = []
    for snr in rs.S["snr_db"]:
        for m in range(int(rs.S["messages_per_snr"])):
            text = "".join(rng.choice(alphabet, int(rs.S["message_chars"])))
            seed = int(rng.integers(2 ** 31))
            sent = tx.send(text, f"r3-{seed}", seed % 256)
            heard = channel.through_channel(sent.audio, sent.fs, snr, tx.pool, ENCOUNTER, seed, cfg, tx.pcfg)
            start = heard.offset_s + sent.lead_in_s
            tracks = det.tracks(heard.audio, heard.fs)
            t0 = np.array([t.start_s for t in tracks])
            fc = np.array([t.centre_hz for t in tracks])
            mag, floor = rs.spectrum(heard.audio)
            for d in sent.data:
                at = start + d.slot.start_s
                ok = np.where((t0 >= at - rs.S["slot_early_s"]) & (t0 <= at + rs.S["slot_late_s"])
                              & (np.abs(fc - d.fc_hz) <= rs.S["pitch_window_hz"]))[0]
                if len(ok):
                    t = tracks[int(ok[np.argmin(np.abs(t0[ok] - at))])]
                    got = rs.features(t, mag, floor)
                    if got is not None and pc.in_range(t):
                        rows.append({"f": got[0], "snr": got[1], "group": f"{name}-{snr:g}-{m}", "basic": pc.basic7(t),
                                     "contour": np.asarray(t.freq_hz, dtype=np.float32), "type": int(d.type_index),
                                     "band": int(d.band), "fc_sent": float(d.fc_hz), "fell_back": bool(d.fell_back)})
    return rows


# ---------------------------------------------------------------------------------------------- scoring
def _matched(a: list[dict], b: list[dict], rng: np.random.Generator) -> tuple[list[dict], np.ndarray]:
    """realism_score.matched, returning the rows themselves (equal numbers of both sides in every SNR band)."""
    edges = np.array(rs.S["snr_bins_db"], dtype=np.float64)
    bins = [np.digitize([r["snr"] for r in side], edges) for side in (a, b)]
    rows, y = [], []
    for k in range(1, len(edges)):
        ia, ib = np.flatnonzero(bins[0] == k), np.flatnonzero(bins[1] == k)
        n = min(len(ia), len(ib))
        if n:
            rows += [a[int(i)] for i in rng.choice(ia, n, replace=False)] + [b[int(i)] for i in rng.choice(ib, n, replace=False)]
            y += [0] * n + [1] * n
    return rows, np.array(y)


def score(real: list[dict], coded: list[dict], cols: list[int], splits: int = 5) -> dict:
    """realism_score.score on the feature columns `cols`; also the held-out classifier score of every coded test whistle."""
    aucs, imp, held = [], np.zeros(len(cols)), []
    for s in range(splits):
        rng = np.random.default_rng(DEV_SEED + s)
        parts = []
        for side in (real, coded):
            groups = sorted({r["group"] for r in side})
            test = set(rng.permutation(groups)[:len(groups) // 2].tolist())
            parts.append(([r for r in side if r["group"] not in test], [r for r in side if r["group"] in test]))
        tr, ytr = _matched(parts[0][0], parts[1][0], rng)
        te, yte = _matched(parts[0][1], parts[1][1], rng)
        Xtr = np.array([[r["f"][j] for j in cols] for r in tr])
        Xte = np.array([[r["f"][j] for j in cols] for r in te])
        m = HistGradientBoostingClassifier(max_depth=4, max_iter=200, learning_rate=0.08, random_state=s).fit(Xtr, ytr)
        p = m.predict_proba(Xte)[:, 1]
        base = roc_auc_score(yte, p)
        aucs.append(float(base))
        held += [(r.get("type", -1), float(q)) for r, q, yy in zip(te, p, yte) if yy == 1]
        for j in range(len(cols)):
            sh = Xte.copy()
            sh[:, j] = rng.permutation(sh[:, j])
            imp[j] += (base - roc_auc_score(yte, m.predict_proba(sh)[:, 1])) / splits
    order = np.argsort(-imp)
    return {"auc": round(float(np.mean(aucs)), 4), "spread": round(float(np.std(aucs)), 4), "splits": [round(a, 4) for a in aucs],
            "clues": [{"feature": rs.FEATURES[cols[int(i)]], "drop": round(float(imp[int(i)]), 4)} for i in order[:5]],
            "held": held}


def diagnose(real: list[dict], coded: list[dict]) -> dict:
    """Each feature on its own: AUC (>0.5 means coded higher) and quartiles on both sides; SNR-balanced, all whistles."""
    rows, y = _matched(real, coded, np.random.default_rng(DEV_SEED))
    X = np.array([r["f"] for r in rows])
    out = {}
    for j, name in enumerate(rs.FEATURES):
        a = float(roc_auc_score(y, X[:, j]))
        q = [np.percentile(X[y == k, j], [25, 50, 75]).round(3).tolist() for k in (0, 1)]
        out[name] = {"auc": round(a, 3), "real_q": q[0], "coded_q": q[1]}
    return out


def by_type(held: list[tuple], coded: list[dict]) -> list[dict]:
    """Per type: whistles, mean held-out score (0.5 = looks real on average), and median span, net rise and fit error."""
    out = []
    for t in sorted({r["type"] for r in coded}):
        rs_t = [r for r in coded if r["type"] == t]
        sc = [q for k, q in held if k == t]
        f = np.array([r["f"] for r in rs_t])
        out.append({"type": t, "whistles": len(rs_t), "held_score": round(float(np.mean(sc)), 3) if sc else None,
                    "duration_ms": round(float(np.median(f[:, 0])), 1), "span_hz": round(float(np.median(f[:, 1])), 1),
                    "net_rise": round(float(np.median(f[:, 6])), 3), "fit_error_hz": round(float(np.median(f[:, 7])), 1)})
    return out


# ---------------------------------------------------------------------------------------------- WC-R3a: spread per type
def _shape_stats(contours: list[np.ndarray], hop_s: float) -> dict:
    dur = np.array([len(f) * hop_s * 1000 for f in contours])
    span = np.array([float(np.ptp(f)) for f in contours])
    fit = []
    for f in contours:
        f = np.asarray(f, dtype=np.float64)
        x = np.arange(len(f)) / len(f)
        fit.append(float(np.std(f - np.polyval(np.polyfit(x, f, 3), x))))
    iqr = lambda v: round(float(np.subtract(*np.percentile(v, [75, 25]))), 1)
    return {"n": len(contours), "duration_iqr_ms": iqr(dur), "span_iqr_hz": iqr(span), "fit_error_median_hz": round(float(np.median(fit)), 1)}


def spread(name: str, tx: sender.Sender) -> list[dict]:
    """Per type: the realism library's real members of its GMM cluster (encounter 191, tracked) against the coded whistles
    of that type as detected here. The library keeps only members classifier A reads clearly, so its spread is a lower bound."""
    coded = _load(OUT / f"coded_{name}.pkl")["rows"]
    hop = realism.HOP / realism.FS                  # detector frames: 5.333 ms
    out = []
    for t, real in enumerate(tx.library.shapes):
        mine = [r["contour"] for r in coded if r["type"] == t]
        if len(real) < 8 or len(mine) < 8:
            continue
        out.append({"type": t, "real": _shape_stats([c.offset_hz for c in real], float(real[0].hop_s)), "coded": _shape_stats(mine, hop)})
    return out


# ---------------------------------------------------------------------------------------------- adoption: messages
CHECK_SNR_DB = 10.0                 # [PLAN] 8.7: exact messages at 10 dB (sweep set) fall by at most 2 of 50


def check_messages() -> list[dict]:
    rng = np.random.default_rng([DEV_SEED, 2])
    return [{"id": f"r{i:02d}", "text": pe.sentence(int(rng.integers(8, 33)), rng), "key": f"r3-{int(rng.integers(2 ** 32)):08x}",
             "nonce": int(rng.integers(256))} for i in range(pe.N_SWEEP)]


def message_check(name: str, tx: sender.Sender, c: dict, det: detect.Detector) -> dict:
    rx = receiver.Receiver(c, rhythm_bank=tx.bank, detector=det)
    rows = []
    for i, m in enumerate(check_messages()):
        seed = int(np.random.SeedSequence([DEV_SEED, 3, i]).generate_state(1)[0])
        sent = tx.send(m["text"], m["key"], int(m["nonce"]))
        heard = channel.through_channel(sent.audio, sent.fs, CHECK_SNR_DB, tx.pool, ENCOUNTER, seed, c, tx.pcfg)
        got = rx.receive(heard.audio, heard.fs, m["key"])
        rows.append({"id": m["id"], "ok": bool(got.ok), "exact": bool(got.ok and got.text == m["text"]),
                     "wrong_text": bool(got.ok and got.text != m["text"]), "stage": got.stage})
    return {"variant": name, "snr_db": CHECK_SNR_DB, "exact": sum(r["exact"] for r in rows), "wrong_text": sum(r["wrong_text"] for r in rows),
            "messages": len(rows), "rows": rows}


# ---------------------------------------------------------------------------------------------- commands
def _save(obj, path: Path) -> None:
    if path.exists():
        raise SystemExit(f"{path} exists; output files are never overwritten (delete it by hand to redo)")
    OUT.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(obj, f)


def _load(path: Path):
    with open(path, "rb") as f:
        return pickle.load(f)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=("build-delphi", "build-delphi-library", "real", "coded", "score", "messages", "spread"))
    ap.add_argument("variants", nargs="*", default=[])
    args = ap.parse_args()
    sys.stdout.reconfigure(errors="replace")
    rs.S["seed"] = DEV_SEED
    cfg = default_config()
    if args.command == "build-delphi":
        build_delphi(cfg)
        return 0
    if args.command == "build-delphi-library":
        build_delphi_library(cfg)
        return 0
    if args.command == "real":
        t = time.perf_counter()
        base = sender.Sender(cfg)
        rows = real_rows(detect.Detector(cfg), cfg, base.pcfg)
        _save({"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "encounter": ENCOUNTER, "files": REAL_FILES,
               "rows": rows}, OUT / "real_214.pkl")
        print(f"{len(rows)} in-range real whistles from {REAL_FILES} encounter-214 recordings [{(time.perf_counter() - t) / 60:.1f} min]")
        return 0
    if args.command == "coded":
        det, base = detect.Detector(cfg), sender.Sender(cfg)
        for name in args.variants:
            t = time.perf_counter()
            tx, c = variants(name, cfg, base)
            rows = coded_rows(name, tx, det, c)
            _save({"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "variant": name, "tau": c["transmit"]["tau"],
                   "codebook_sha256": tx.codebook_sha256, "rows": rows}, OUT / f"coded_{name}.pkl")
            print(f"{name}: {len(rows)} data whistles [{(time.perf_counter() - t) / 60:.1f} min]", flush=True)
        return 0
    if args.command == "spread":
        base = sender.Sender(cfg)
        for name in args.variants:
            tx, _ = variants(name, cfg, base)
            res = spread(name, tx)
            path = OUT / f"spread_{name}.json"
            if path.exists():
                raise SystemExit(f"{path} exists; output files are never overwritten")
            path.write_text(json.dumps(res, indent=1), encoding="utf-8")
            for r in res:
                print(f"type {r['type']:2d}: real n {r['real']['n']:3d} dur IQR {r['real']['duration_iqr_ms']:6.1f} span IQR "
                      f"{r['real']['span_iqr_hz']:6.1f} fit {r['real']['fit_error_median_hz']:5.1f} | coded n {r['coded']['n']:3d} dur IQR "
                      f"{r['coded']['duration_iqr_ms']:6.1f} span IQR {r['coded']['span_iqr_hz']:6.1f} fit {r['coded']['fit_error_median_hz']:5.1f}")
        return 0
    if args.command == "messages":
        det, base = detect.Detector(cfg), sender.Sender(cfg)
        for name in args.variants:
            path = OUT / f"messages_{name}.json"
            if path.exists():
                raise SystemExit(f"{path} exists; output files are never overwritten")
            t = time.perf_counter()
            tx, c = variants(name, cfg, base)
            res = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **message_check(name, tx, c, det)}
            OUT.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(res, indent=1), encoding="utf-8")
            print(f"{name}: {res['exact']}/{res['messages']} exact at {CHECK_SNR_DB:g} dB, wrong text {res['wrong_text']} "
                  f"[{(time.perf_counter() - t) / 60:.1f} min]", flush=True)
        return 0
    real = _load(OUT / "real_214.pkl")["rows"]
    for name in args.variants:
        coded = _load(OUT / f"coded_{name}.pkl")["rows"]
        full = score(real, coded, list(range(len(rs.FEATURES))))
        groups = {g: {k: v for k, v in score(real, coded, cols).items() if k != "held"} for g, cols in GROUPS.items()}
        res = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "variant": name, "real": len(real),
               "coded": len(coded), "auc": full["auc"], "spread": full["spread"], "splits": full["splits"], "clues": full["clues"],
               "groups": groups, "w1": pc.w1([(0, 0, 0, r["basic"]) for r in real], [(0, 0, 0, r["basic"]) for r in coded]),
               "features": diagnose(real, coded), "types": by_type(full["held"], coded)}
        path = OUT / f"score_{name}.json"
        if path.exists():
            raise SystemExit(f"{path} exists; output files are never overwritten")
        path.write_text(json.dumps(res, indent=1), encoding="utf-8")
        print(f"{name}: AUC {res['auc']:.3f} +/- {res['spread']:.3f} ({len(coded)} coded, {len(real)} real); "
              + "; ".join(f"{g} {v['auc']:.3f}" for g, v in groups.items()))
        print("  clues: " + ", ".join(f"{c['feature']} {c['drop']:.3f}" for c in res["clues"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
