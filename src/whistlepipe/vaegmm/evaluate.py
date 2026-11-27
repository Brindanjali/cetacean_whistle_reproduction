"""Evaluation orchestration for a trained VAE run (specification §3.5-3.7). Every command reads a finished run under
models/vaegmm/<run_id>/ and writes JSON / PNG under that run (eval/, gmm_K<k>/, figures/). Nothing is overwritten
silently: existing outputs make the command stop unless ``force`` is given (GMM fits are never overwritten).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import torch

from ..detector.ridgenet import resolve_device, set_deterministic, sha256_file
from ..storage import software_versions
from . import fid as fidmod
from .conditional import acceptance_ratios, component_features, conditional_sample, weights_eq8, weights_eq10
from .config import main_k, resolve
from .data import training_images
from .features import FEATURES, contour_features, contour_vectors, satisfies
from .gmm import GaussianMixtureEM
from .losses import kl_std_normal, recon_sse
from .metrics import clustering_scores, frechet_distance, frechet_from_samples, precision_recall, psnr_from_mse, ssim, wasserstein1_sorted
from .models import n_params, table6_flops
from .train import encode_means, load_trained_vae


def _run(cfg, run_id: str) -> Path:
    d = resolve(cfg["paths"]["runs_dir"]) / run_id
    if not (d / "checkpoints" / "final.pt").exists():
        raise FileNotFoundError(f"{d} has no checkpoints/final.pt (training not finished)")
    return d


def _write(path: Path, obj: dict, force: bool = False) -> Path:
    if path.exists() and not force:
        raise FileExistsError(f"{path} exists (use --force to recompute)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=float), encoding="utf-8")
    print("wrote", path, flush=True)
    return path


def _ctx(cfg):
    set_deterministic()
    dev = resolve_device(cfg["train"]["device"])
    return dev, training_images(cfg)


def _image_batches(images, batch: int = 512):
    for i in range(0, len(images), batch):
        yield torch.from_numpy(images.gather(np.arange(i, min(i + batch, len(images)))))[:, None]


# ---------------------------------------------------------------- latents + GMM
def encode(cfg, run_id: str) -> Path:
    d = _run(cfg, run_id)
    out = d / "latents_mu.npy"
    if out.exists():
        return out
    dev, images = _ctx(cfg)
    vae, _ = load_trained_vae(d, dev)
    mu = encode_means(vae, images, dev)
    np.save(out, mu)
    (d / "latents_mu.json").write_text(json.dumps({"checkpoint_sha256": sha256_file(d / "checkpoints" / "final.pt"),
                                                   "n": int(len(mu)), "dim": int(mu.shape[1]), "rotation": "none"}, indent=2), encoding="utf-8")
    return out


def gmm_dir(cfg, run_id: str, K: int, tag: str = "") -> Path:
    return resolve(cfg["paths"]["runs_dir"]) / run_id / f"gmm_K{K}{('_' + tag) if tag else ''}"


def fit_gmm(cfg, run_id: str, K: int, reg_rel: float | None = None, seed: int | None = None, tag: str = "") -> Path:
    gd = gmm_dir(cfg, run_id, K, tag)
    if (gd / "gmm.npz").exists():
        raise FileExistsError(f"{gd / 'gmm.npz'} exists; GMM fits are never overwritten (use --tag)")
    gd.mkdir(parents=True, exist_ok=True)
    set_deterministic()      # encode() sets it only when it encodes; without it two GPU fits from the same seed differ
    mu = np.load(encode(cfg, run_id))
    dev = resolve_device(cfg["train"]["device"])
    p, dg = cfg["paper"], cfg["decisions"]["gmm"]
    g = GaussianMixtureEM(K, reg_rel if reg_rel is not None else dg["reg_covar_rel"], p["em_max_iter"], p["em_tol"],
                          dg["empty_nk"], seed if seed is not None else cfg["decisions"]["train"]["seed"], dev,
                          dg["point_chunk"], dg["component_chunk"])
    t0 = time.time()
    g.fit(mu, log_path=gd / "fit_log.jsonl")
    g.save(gd / "gmm.npz", {"run_id": run_id, "latents_sha256": sha256_file(resolve(cfg["paths"]["runs_dir"]) / run_id / "latents_mu.npy"),
                            "fit_wall_s": round(time.time() - t0, 1), "diagnostics": g.diagnostics(len(mu)), "software": software_versions()})
    return gd


def load_gmm(cfg, run_id: str, K: int, tag: str = "") -> GaussianMixtureEM:
    dg = cfg["decisions"]["gmm"]
    return GaussianMixtureEM.load(gmm_dir(cfg, run_id, K, tag) / "gmm.npz", resolve_device(cfg["train"]["device"]),
                                  point_chunk=dg["point_chunk"], component_chunk=dg["component_chunk"], verbose=False)


# ---------------------------------------------------------------- Table 1
@torch.no_grad()
def eval_recon(cfg, run_id: str, force: bool = False) -> Path:
    d = _run(cfg, run_id)
    dev, images = _ctx(cfg)
    vae, spec = load_trained_vae(d, dev)
    sse = ss = kl = 0.0
    n = 0
    for x in _image_batches(images):
        x = x.to(dev)
        mu, logvar = vae.encoder(x)
        xr = vae.decoder(mu)                                   # [DECISION] z = mu
        sse += float(recon_sse(xr, x).double().sum())
        ss += float(ssim(xr, x).double().sum())
        kl += float(kl_std_normal(mu, logvar).double().sum())
        n += len(x)
    mse = sse / n
    return _write(d / "eval" / "table1_recon.json", {
        "run_id": run_id, "latent_dim": spec["latent_dim"], "beta": spec["beta"], "n_images": n,
        "MSE_per_image_sse": mse, "PSNR_dB": psnr_from_mse(mse), "SSIM": ss / n, "KL_latent": kl / n,
        "convention": "MSE = mean per-image sum of squared errors; PSNR = 10 log10(16384/MSE); z = mu; unrotated training images"}, force)


# ---------------------------------------------------------------- Table 2 / 4 / 5 image metrics
class Moments:
    def __init__(self, d: int):
        self.n, self.s1, self.s2 = 0, np.zeros(d), np.zeros((d, d))

    def add(self, f: np.ndarray):
        f = f.astype(np.float64)
        self.n += len(f)
        self.s1 += f.sum(0)
        self.s2 += f.T @ f

    def stats(self):
        mu = self.s1 / self.n
        return mu, (self.s2 - self.n * np.outer(mu, mu)) / (self.n - 1)


def _feature_pass(batches, n: int, nets: dict, thr: float, dev, vgg_prefix: Path):
    """One pass: Inception moments (raw + binarised) and VGG fc2 features (raw + binarised), the latter written to
    on-disk .npy memmaps ``<vgg_prefix>_{raw,bin}.npy`` (2 x 2.9 GB for 180k images; too large for RAM)."""
    mom = {"raw": Moments(2048), "bin": Moments(2048)}
    vgg = {v: np.lib.format.open_memmap(f"{vgg_prefix}_{v}.npy", mode="w+", dtype=np.float32, shape=(n, 4096)) for v in ("raw", "bin")}
    i = 0
    with torch.no_grad():
        for b in batches:
            b = b.to(dev)
            for var, bz in (("raw", None), ("bin", thr)):
                xin = fidmod.preprocess(b, bz)
                mom[var].add(nets["inception"](xin).double().cpu().numpy())
                vgg[var][i:i + len(b)] = nets["vgg16"](xin).float().cpu().numpy()
            i += len(b)
    if i != n:
        raise RuntimeError(f"feature pass saw {i} images, expected {n}")
    for v in vgg.values():
        v.flush()
    return mom


def _nets(cfg, dev):
    root = resolve("models/eval_weights")
    for name in fidmod.WEIGHT_URLS:
        if not fidmod.weight_path(root, name).exists():
            raise FileNotFoundError(f"{fidmod.weight_path(root, name)} missing: feature-network weights are downloaded only after "
                                    "approval (python whistle.py fetch-eval-weights)")
    return {"inception": fidmod.InceptionPool(fidmod.weight_path(root, "inception_v3")).to(dev),
            "vgg16": fidmod.VGGfc2(fidmod.weight_path(root, "vgg16")).to(dev)}


def _real_features(cfg, images, nets, dev) -> dict:
    cache = resolve(cfg["paths"]["runs_dir"]) / "_eval_cache"
    key = images.cache_key()
    f = cache / f"real_{key}_inception_stats.npz"
    if not f.exists():
        cache.mkdir(parents=True, exist_ok=True)
        mom = _feature_pass(_image_batches(images, int(cfg["decisions"]["eval"]["feature_batch"])), len(images), nets,
                            cfg["paper"]["fid1_threshold"], dev,
                            cache / f"real_{key}_vgg")
        np.savez(f, **{f"mu_{k}": m.stats()[0] for k, m in mom.items()}, **{f"cov_{k}": m.stats()[1] for k, m in mom.items()})
    st = dict(np.load(f))
    for v in ("raw", "bin"):
        st[f"vgg_{v}"] = np.load(cache / f"real_{key}_vgg_{v}.npy", mmap_mode="r")
    return st


def generated_batches(decoder, source: str, n: int, seed: int, dev, gmm=None, latent_dim: int = 64, ldm=None, batch: int = 256):
    """Image batches from: 'gmm' (C ~ Cat(pi), z ~ N(mu_C, Sigma_C)), 'prior' (z ~ N(0, I)), or 'ldm' (diffusion latents)."""
    g = torch.Generator(device=dev)
    g.manual_seed(seed)
    done = 0
    with torch.no_grad():
        while done < n:
            b = min(batch, n - done)
            if source == "gmm":
                z, _ = gmm.sample(b, g)
            elif source == "prior":
                z = torch.randn(b, latent_dim, generator=g, device=dev)
            elif source == "ldm":
                model, sched, scale, ldm_sample = ldm
                z = ldm_sample(model, sched, b, g, dev).view(b, -1) * scale
            else:
                raise ValueError(source)
            yield decoder(z).cpu()
            done += b


def eval_generation(cfg, run_id: str, source: str = "gmm", K: int | None = None, tag: str = "", ldm_run: str | None = None,
                    force: bool = False) -> Path:
    """FID1 (binarised at 0.1), FID2 (raw), precision / recall / F1 [47] (raw = primary, binarised also reported)."""
    d = _run(cfg, run_id)
    dev, images = _ctx(cfg)
    vae, spec = load_trained_vae(d, dev)
    nets = _nets(cfg, dev)
    real = _real_features(cfg, images, nets, dev)
    n = len(images)
    gmm = load_gmm(cfg, run_id, K or main_k(cfg), tag) if source == "gmm" else None
    ldm = None
    if source == "ldm":
        from .ldm import LinearSchedule, UNet, ldm_sample
        st = torch.load(resolve(cfg["paths"]["runs_dir"]) / ldm_run / "final.pt", map_location=dev, weights_only=False)
        model = UNet().to(dev)
        model.load_state_dict(st["model"])
        model.eval()
        ldm = (model, LinearSchedule(st["T"], cfg["paper"]["ldm_beta_min"], cfg["paper"]["ldm_beta_max"], dev), st["scale"], ldm_sample)
    seed = int(cfg["decisions"]["train"]["seed"]) + 1
    name = f"gen_{source}" + (f"_K{K}" if source == "gmm" else "") + (f"_{tag}" if tag else "") + (f"_{ldm_run}" if ldm_run else "")
    if (d / "eval" / f"{name}.json").exists() and not force:
        raise FileExistsError(f"{d / 'eval' / (name + '.json')} exists (use --force to recompute)")
    (d / "eval").mkdir(exist_ok=True)
    prefix = d / "eval" / f"_vgg_{name}"
    fb = int(cfg["decisions"]["eval"]["feature_batch"])
    mom = _feature_pass(generated_batches(vae.decoder, source, n, seed, dev, gmm, spec["latent_dim"], ldm, batch=fb), n, nets,
                        cfg["paper"]["fid1_threshold"], dev, prefix)
    res = {"run_id": run_id, "source": source, "K": K, "gmm_tag": tag, "ldm_run": ldm_run, "n_real": n, "n_generated": n,
           "generation_seed": seed, "feature_batch": fb, "checkpoint_sha256": sha256_file(d / "checkpoints" / "final.pt"),
           "weights_sha256": {k: sha256_file(fidmod.weight_path(resolve("models/eval_weights"), k)) for k in fidmod.WEIGHT_URLS},
           "software": software_versions()}
    for var, metric in (("bin", "FID1"), ("raw", "FID2")):         # not `name`: that is the output file's name
        mu, cov = mom[var].stats()
        res[metric] = frechet_distance(real[f"mu_{var}"], real[f"cov_{var}"], mu, cov)
    for var in ("raw", "bin"):
        fake = np.load(f"{prefix}_{var}.npy", mmap_mode="r")
        res[f"PR_{var}"] = precision_recall(real[f"vgg_{var}"], fake, cfg["decisions"]["eval"]["pr_k"], str(dev))
        del fake
        Path(f"{prefix}_{var}.npy").unlink()
    res["primary_PR"] = "PR_raw"
    return _write(d / "eval" / f"{name}.json", res, force)


# ---------------------------------------------------------------- Fig. 11
def eval_clustering(cfg, run_id: str, Ks: list[int], force: bool = False) -> Path:
    d = _run(cfg, run_id)
    set_deterministic()
    mu = np.load(encode(cfg, run_id))
    dev = resolve_device(cfg["train"]["device"])
    rows = []
    for K in Ks:
        lab, _ = load_gmm(cfg, run_id, K).predict(mu)
        r = {"K": K, **clustering_scores(mu, lab, str(dev))}
        print(json.dumps(r), flush=True)
        rows.append(r)
    return _write(d / "eval" / "fig11_clustering.json", {"run_id": run_id, "space": "encoder means (unrotated), Euclidean",
                                                          "labels": "MAP (eq. 12)", "rows": rows}, force)


# ---------------------------------------------------------------- component analysis, Table 3, Fig. 12
def analyze_components(cfg, run_id: str, K: int | None = None) -> Path:
    K = K or main_k(cfg)
    out = gmm_dir(cfg, run_id, K) / "component_features.npy"
    if out.exists():
        return out
    d = _run(cfg, run_id)
    set_deterministic()
    dev = resolve_device(cfg["train"]["device"])
    vae, _ = load_trained_vae(d, dev)
    gmm = load_gmm(cfg, run_id, K)
    g = torch.Generator(device=dev)
    seed = int(cfg["decisions"]["train"]["seed"]) + 2
    g.manual_seed(seed)
    batch = int(cfg["decisions"]["eval"]["sample_batch"])
    t0 = time.time()
    cf = component_features(vae.decoder, gmm, cfg["paper"]["component_samples"], g, cfg["paper"]["contour_threshold"],
                            batch=batch, progress=True)
    np.save(out, cf)
    gd = gmm_dir(cfg, run_id, K)
    valid = np.isfinite(cf).all(-1)
    out.with_suffix(".json").write_text(json.dumps({
        "shape": list(cf.shape), "features": list(FEATURES), "n_per_component": int(cf.shape[1]), "seed": seed, "batch": batch,
        "threshold": float(cfg["paper"]["contour_threshold"]), "frac_samples_with_contour": float(valid.mean()),
        "gmm_npz_sha256": sha256_file(gd / "gmm.npz"), "checkpoint_sha256": sha256_file(d / "checkpoints" / "final.pt"),
        "device": str(dev), "wall_s": round(time.time() - t0, 1), "software": software_versions()}, indent=2), encoding="utf-8")
    return out


def real_features(cfg, images, dev) -> np.ndarray:
    cache = resolve(cfg["paths"]["runs_dir"]) / "_eval_cache"
    f = cache / f"real_whistle_features_{images.cache_key()}.npy"
    if not f.exists():
        cache.mkdir(parents=True, exist_ok=True)
        out = [contour_features(b.to(dev), cfg["paper"]["contour_threshold"])[0].cpu().numpy() for b in _image_batches(images, 2048)]
        np.save(f, np.concatenate(out))
    return np.load(f)


def eval_conditional(cfg, run_id: str, K: int | None = None, force: bool = False) -> Path:
    K = K or main_k(cfg)
    d = _run(cfg, run_id)
    dev, images = _ctx(cfg)
    vae, _ = load_trained_vae(d, dev)
    gmm = load_gmm(cfg, run_id, K)
    cf = np.load(analyze_components(cfg, run_id, K))
    rf = real_features(cfg, images, dev)
    pi = gmm.weights_.cpu().numpy()
    fx = cfg["decisions"]["features"]
    g = torch.Generator(device=dev)
    g.manual_seed(int(cfg["decisions"]["train"]["seed"]) + 3)
    rows, gen_sets, real_sets = [], {}, {}
    for c in cfg["paper"]["table3_conditions"]:
        X = rf[satisfies(rf, c["feature"], c["lo"], c["hi"])]
        a = acceptance_ratios(cf, c["feature"], c["lo"], c["hi"])
        member = a > 0
        row = {"no": c["no"], "feature": c["feature"], "c1": c["lo"], "c2": c["hi"], "N": int(len(X)),
               "n_components_in_subset": int(member.sum())}
        unit = fx["ms_per_sample"] if c["feature"] == "L" else fx["hz_per_bin"]
        j = FEATURES.index(c["feature"])
        for wname, w in (("eq10", weights_eq10(pi, a, member)), ("eq8", weights_eq8(pi, member))):
            s = conditional_sample(vae.decoder, gmm, w, c["feature"], c["lo"], c["hi"], len(X), g, cfg["paper"]["contour_threshold"],
                                   batch=int(cfg["decisions"]["eval"]["sample_batch"]))
            Y = s["features"]
            if wname == cfg["decisions"]["conditional"]["weights_primary"]:
                gen_sets[c["no"]] = Y
            pr = precision_recall(X, Y, cfg["decisions"]["eval"]["pr_k"], str(dev))
            row[wname] = {"W1": wasserstein1_sorted(X[:, j], Y[:, j]) * unit, "W1_unit": "ms" if c["feature"] == "L" else "Hz",
                          "FFD": frechet_from_samples(X, Y), "recall": pr["recall"], "precision": pr["precision"], "f1": pr["f1"],
                          "acceptance_rate": s["acceptance_rate"], "draws": s["draws"]}
        real_sets[c["no"]] = X
        print(json.dumps(row), flush=True)
        rows.append(row)
    nos = [c["no"] for c in cfg["paper"]["table3_conditions"]]
    Z = [[float(np.log(frechet_from_samples(real_sets[i], gen_sets[jn]))) for jn in nos] for i in nos]
    return _write(d / "eval" / f"table3_fig12_K{K}.json", {
        "run_id": run_id, "K": K, "weights_primary": cfg["decisions"]["conditional"]["weights_primary"],
        "features": list(FEATURES), "rows": rows,
        "fig12_lnFFD": {"rows_real_condition": nos, "cols_generated_condition": nos, "Z": Z}}, force)


# ---------------------------------------------------------------- Table 6
def eval_cost(cfg, run_id: str, K: int | None = None, force: bool = False) -> Path:
    K = K or main_k(cfg)
    d = _run(cfg, run_id)
    dev = resolve_device(cfg["train"]["device"])
    vae, spec = load_trained_vae(d, dev)
    gmm = load_gmm(cfg, run_id, K)
    from .models import Decoder
    res = {"run_id": run_id, "decoder_params": n_params(vae.decoder),
           "decoder_table6_flops": table6_flops(Decoder(spec["latent_dim"]), (spec["latent_dim"],)), "device": str(dev),
           "gpu_name": torch.cuda.get_device_name(dev) if dev.type == "cuda" else None,
           "torch_flags": {"cudnn_benchmark": torch.backends.cudnn.benchmark, "cudnn_deterministic": torch.backends.cudnn.deterministic,
                           "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
                           "matmul_tf32": torch.backends.cuda.matmul.allow_tf32},
           "software": software_versions(),
           "protocol": "250 trials, first 50 excluded, 0.5 s between trials; per-image latency = batch time / B"}
    g = torch.Generator(device=dev)
    g.manual_seed(0)
    for B in (1, 16, 32):
        for what in ("decoder_only", "gmm_sampling_plus_decoder"):
            z0, _ = gmm.sample(B, g)
            ts = []
            for _trial in range(250):
                time.sleep(0.5)
                if dev.type == "cuda":
                    torch.cuda.synchronize()
                t0 = time.perf_counter()
                with torch.no_grad():
                    z = gmm.sample(B, g)[0] if what != "decoder_only" else z0
                    vae.decoder(z)
                if dev.type == "cuda":
                    torch.cuda.synchronize()
                ts.append(time.perf_counter() - t0)
            m = float(np.mean(ts[50:]))
            res[f"B{B}_{what}_batch_s"] = m
            res[f"B{B}_{what}_per_image_s"] = m / B
    return _write(d / "eval" / "table6_cost.json", res, force)


# ---------------------------------------------------------------- Figs. 7-10
def make_figures(cfg, run_id: str, K: int | None = None) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    K = K or main_k(cfg)
    d = _run(cfg, run_id)
    out = d / "figures"
    out.mkdir(exist_ok=True)
    dev, images = _ctx(cfg)
    vae, _ = load_trained_vae(d, dev)
    gmm = load_gmm(cfg, run_id, K)
    thr = cfg["paper"]["contour_threshold"]
    g = torch.Generator(device=dev)
    g.manual_seed(7)
    rows = np.arange(128)
    with torch.no_grad():
        # Fig. 7: unconditional samples with component index
        z, comp = gmm.sample(25, g)
        x = vae.decoder(z).cpu().numpy()[:, 0]
        fig, axs = plt.subplots(5, 5, figsize=(10, 10))
        for a, im, k in zip(axs.flat, x, comp.cpu().numpy()):
            a.imshow(im, cmap="viridis", vmin=0, vmax=1)
            a.set_title(f"k = {k}", fontsize=8)
            a.axis("off")
        fig.savefig(out / "fig7_unconditional.png", dpi=90)
        plt.close(fig)
        # Fig. 8: 4 most probable components: 20 overlaid contours + 7 histograms from 500 samples
        cf_path = gmm_dir(cfg, run_id, K) / "component_features.npy"
        cf = np.load(cf_path) if cf_path.exists() else None
        top = np.argsort(-gmm.weights_.cpu().numpy())[:4]
        fig, axs = plt.subplots(4, 8, figsize=(22, 11))
        for r, k in enumerate(top):
            zz, _ = gmm.sample(20, g, components=np.full(20, k))
            v = contour_vectors(vae.decoder(zz), thr).cpu().numpy()
            for vi in v:
                axs[r, 0].plot(rows + 1, vi, lw=0.8)
            axs[r, 0].set(xlim=(0, 128), ylim=(0, 128), title=f"component {k}", xlabel="time step", ylabel="bin")
            for j, f in enumerate(FEATURES):
                if cf is not None:
                    axs[r, j + 1].hist(cf[k, :, j][np.isfinite(cf[k, :, j])], bins=20)
                axs[r, j + 1].set_title(f, fontsize=8)
        fig.tight_layout()
        fig.savefig(out / "fig8_components.png", dpi=80)
        plt.close(fig)
        # Fig. 9: conditional generation, Table 3 condition 2 (75 <= L <= 80), eq. 10 weights, 100 accepted samples
        if cf is not None:
            c = cfg["paper"]["table3_conditions"][1]
            a = acceptance_ratios(cf, c["feature"], c["lo"], c["hi"])
            w = weights_eq10(gmm.weights_.cpu().numpy(), a, a > 0)
            s9 = conditional_sample(vae.decoder, gmm, w, c["feature"], c["lo"], c["hi"], 100, g, thr,
                                    batch=int(cfg["decisions"]["eval"]["sample_batch"]), keep_images=100)
            fig, axs = plt.subplots(1, 2, figsize=(13, 5))
            for vi in contour_vectors(torch.from_numpy(s9["images"]).to(dev), thr).cpu().numpy():
                act = np.nonzero(np.isfinite(vi))[0]
                seg = vi[act[0]:act[-1] + 1]
                axs[0].plot(np.arange(1, len(seg) + 1), seg, lw=0.6)      # start-aligned, as in the paper's Fig. 9
            for xv in (c["lo"], c["hi"]):
                axs[0].axvline(xv, ls=":", c="k")
            axs[0].set(xlim=(0, 128), ylim=(0, 128), xlabel="time step", ylabel="bin", title=f"{c['lo']} <= L <= {c['hi']}")
            axs[1].hist(s9["features"][:, 0], bins=np.arange(c["lo"], c["hi"] + 2) - 0.5)
            axs[1].set_title("L (samples)")
            fig.savefig(out / "fig9_conditional_L75_80.png", dpi=80)
            plt.close(fig)
        # Fig. 10: MAP component of 3 real images + 100 contours sampled from it
        mu = np.load(encode(cfg, run_id))
        pick = np.random.default_rng(10).choice(len(images), 3, replace=False)
        lab, _ = gmm.predict(mu[pick])
        fig, axs = plt.subplots(3, 2, figsize=(9, 13))
        real_v = contour_vectors(torch.from_numpy(images.gather(pick)).to(dev), thr).cpu().numpy()
        for r, (i, k) in enumerate(zip(pick, lab)):
            axs[r, 0].imshow(images.gather(np.array([i]))[0], cmap="viridis", vmin=0, vmax=1)
            zz, _ = gmm.sample(100, g, components=np.full(100, k))
            for vi in contour_vectors(vae.decoder(zz), thr).cpu().numpy():
                axs[r, 1].plot(rows + 1, vi, color="tab:blue", lw=0.5)
            axs[r, 1].plot(rows + 1, real_v[r], color="red", lw=1.5)
            axs[r, 1].set(xlim=(0, 128), ylim=(0, 128), title=f"k^ = {k}")
        fig.savefig(out / "fig10_map.png", dpi=80)
        plt.close(fig)
    # Fig. 12: ln FFD between real whistles of condition i (rows) and generated whistles of condition j (columns)
    t3 = d / "eval" / f"table3_fig12_K{K}.json"
    if t3.exists():
        z = json.loads(t3.read_text(encoding="utf-8"))["fig12_lnFFD"]
        Z, nos = np.array(z["Z"]), z["rows_real_condition"]
        fig, ax = plt.subplots(figsize=(8, 7))
        im = ax.imshow(Z, cmap="gray", vmin=min(-3.0, float(Z.min())), vmax=max(8.0, float(Z.max())))
        for i in range(len(nos)):
            for j in range(len(nos)):
                v = Z[i, j]
                ax.text(j, i, f"{v:.2g}" if abs(v) < 1 else f"{v:.1f}", ha="center", va="center", fontsize=7,
                        color="white" if v < 0.5 * (im.norm.vmin + im.norm.vmax) else "black")
        ax.set_xticks(range(len(nos)), nos)
        ax.set_yticks(range(len(nos)), nos)
        ax.xaxis.tick_top()
        ax.xaxis.set_label_position("top")
        ax.set(xlabel="Condition index (generated data)", ylabel="Condition index (real data)")
        fig.colorbar(im, ax=ax, fraction=0.046)
        fig.savefig(out / "fig12_lnFFD.png", dpi=90)
        plt.close(fig)
    print("figures in", out, flush=True)
    return out


# ---------------------------------------------------------------- Figs. 13-14 (Appendix C)
# [DECISION] read from the paper's Figs. 9, 13 and 14: length and start-frequency contours are drawn from time step 1,
# end-frequency contours end at time step 128, the others stay where they are in the image.
APPENDIX_ALIGN = {"L": "start", "f_start": "start", "f_end": "end"}
FEATURE_TITLES = {"L": "Length", "f_end": "End frequency", "f_start": "Start frequency", "df": "Bandwidth",
                  "f_min": "Min. frequency", "f_max": "Max. frequency"}


def align_contour(v: np.ndarray, align: str | None, width: int = 128) -> tuple[np.ndarray, np.ndarray]:
    """Time steps (1-based) and bins of one contour vector's active span, moved to start at 1 ("start"), to end at
    ``width`` ("end"), or left in place (None). Gaps inside the span stay NaN."""
    act = np.nonzero(np.isfinite(v))[0]
    seg = v[act[0]:act[-1] + 1]
    first = {"start": 1, "end": width - len(seg) + 1}.get(align, act[0] + 1)
    return np.arange(first, first + len(seg)), seg


def make_appendix_figures(cfg, run_id: str, K: int | None = None, force: bool = False) -> Path:
    """Figs. 13-14: for each Appendix C condition, 100 accepted samples (eq. 10 weights) overlaid with the condition's
    bounds dotted, and a histogram of the conditioned feature. Writes figures/fig13_conditional.png,
    fig14_conditional.png and eval/fig13_14_conditional.json."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    K = K or main_k(cfg)
    d = _run(cfg, run_id)
    paths = {13: d / "figures" / "fig13_conditional.png", 14: d / "figures" / "fig14_conditional.png"}
    record_path = d / "eval" / "fig13_14_conditional.json"
    if not force and any(p.exists() for p in [*paths.values(), record_path]):
        raise FileExistsError(f"Figs. 13-14 exist under {d} (use --force to redraw)")
    set_deterministic()
    dev = resolve_device(cfg["train"]["device"])
    vae, _ = load_trained_vae(d, dev)
    gmm = load_gmm(cfg, run_id, K)
    cf = np.load(analyze_components(cfg, run_id, K))
    pi = gmm.weights_.cpu().numpy()
    thr = cfg["paper"]["contour_threshold"]
    seed = int(cfg["decisions"]["train"]["seed"]) + 13                     # [DECISION] its own stream
    g = torch.Generator(device=dev)
    g.manual_seed(seed)
    n = 100                                                                 # App. C: 100 generated whistles each
    rec = {"run_id": run_id, "K": K, "weights": "eq10", "n_per_condition": n, "seed": seed, "threshold": thr,
           "align": APPENDIX_ALIGN, "checkpoint_sha256": sha256_file(d / "checkpoints" / "final.pt"), "panels": []}
    paths[13].parent.mkdir(exist_ok=True)
    for fig_no, path in paths.items():
        conds = [c for c in cfg["paper"]["fig13_14_conditions"] if c["fig"] == fig_no]
        fig, axs = plt.subplots(len(conds), 2, figsize=(12, 4.2 * len(conds)), gridspec_kw={"width_ratios": [2.4, 1]})
        for (ax_c, ax_h), c in zip(axs, conds):
            f, lo, hi = c["feature"], c["lo"], c["hi"]
            a = acceptance_ratios(cf, f, lo, hi)
            s = conditional_sample(vae.decoder, gmm, weights_eq10(pi, a, a > 0), f, lo, hi, n, g, thr,
                                   batch=int(cfg["decisions"]["eval"]["sample_batch"]), keep_images=n)
            with torch.no_grad():
                vs = contour_vectors(torch.from_numpy(s["images"]).to(dev), thr).cpu().numpy()
            for v in vs:
                ax_c.plot(*align_contour(v, APPENDIX_ALIGN.get(f)), lw=0.6)
            if f == "L":
                for b in (lo, hi):
                    ax_c.axvline(b, ls=":", c="k")
            elif f != "df":                                                 # [DECISION] a bandwidth is not a level
                for b in (lo, hi):
                    ax_c.axhline(b, ls=":", c="k")
            ax_c.set(xlim=(0, 128), ylim=(0, 128), xlabel="Time (time step)", ylabel="Frequency (bin)",
                     title=f"({c['panel']}) {FEATURE_TITLES[f]}: {lo}-{hi} {'samples' if f == 'L' else 'bins'}")
            vals = s["features"][:, FEATURES.index(f)]
            ax_h.hist(vals, bins=np.arange(lo, hi + 2) - 0.5)
            ax_h.set(title=FEATURE_TITLES[f], xlabel="samples" if f == "L" else "Bin index")
            rec["panels"].append({"fig": fig_no, "panel": c["panel"], "feature": f, "lo": lo, "hi": hi,
                                  "n_components_in_subset": int((a > 0).sum()), "acceptance_rate": s["acceptance_rate"],
                                  "draws": s["draws"], "feature_min": float(vals.min()), "feature_max": float(vals.max()),
                                  "feature_median": float(np.median(vals))})
            print(json.dumps(rec["panels"][-1]), flush=True)
        fig.suptitle(f"Fig. {fig_no}: conditional whistle generation ({run_id}, K = {K})", fontsize=10)
        fig.tight_layout()
        fig.savefig(path, dpi=80)
        plt.close(fig)
        print("wrote", path, flush=True)
    return _write(record_path, rec, force)


# ---------------------------------------------------------------- LDM baseline training
def train_ldm(cfg, vae_run_id: str, T: int, run_id: str, resume: bool = False) -> Path:
    from .ldm import LinearSchedule, UNet, latents_to_grid, ldm_loss
    out = resolve(cfg["paths"]["runs_dir"]) / run_id
    if out.exists() and not resume:
        raise FileExistsError(f"{out} exists")
    out.mkdir(parents=True, exist_ok=True)
    set_deterministic()
    dev = resolve_device(cfg["train"]["device"])
    p = cfg["paper"]
    mu = np.load(encode(cfg, vae_run_id))
    scale = float(mu.std())
    zg = latents_to_grid(mu, scale)
    seed = int(cfg["decisions"]["train"]["seed"])
    torch.manual_seed(seed)
    model = UNet().to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=p["ldm_lr"])
    sched = LinearSchedule(T, p["ldm_beta_min"], p["ldm_beta_max"], dev)
    start = 1
    if resume and (out / "last.pt").exists():
        st = torch.load(out / "last.pt", map_location=dev, weights_only=False)
        model.load_state_dict(st["model"])
        opt.load_state_dict(st["opt"])
        start = st["epoch"] + 1
    for epoch in range(start, p["ldm_epochs"] + 1):
        perm = np.random.default_rng([seed, epoch]).permutation(len(zg))
        g = torch.Generator(device=dev)
        g.manual_seed(seed * 1000 + epoch)
        tot, t0 = 0.0, time.time()
        for i in range(0, len(perm), p["ldm_batch"]):
            loss = ldm_loss(model, sched, zg[perm[i:i + p["ldm_batch"]]].to(dev), g)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            tot += float(loss.detach()) * min(p["ldm_batch"], len(perm) - i)
        rec = {"epoch": epoch, "loss": tot / len(perm), "epoch_s": round(time.time() - t0, 1)}
        print(json.dumps(rec), flush=True)
        with open(out / "train_log.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "epoch": epoch, "T": T, "scale": scale,
                    "vae_run": vae_run_id}, out / "last.pt")
    if not (out / "final.pt").exists():
        import shutil
        shutil.copyfile(out / "last.pt", out / "final.pt")
    (out / "train_info.json").write_text(json.dumps({"T": T, "vae_run": vae_run_id, "scale": scale, "params": n_params(model),
                                                     "paper_params": "2.9M (Table 6)", "software": software_versions()}, indent=2), encoding="utf-8")
    return out
