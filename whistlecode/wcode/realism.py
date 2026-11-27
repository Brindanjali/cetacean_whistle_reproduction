"""Real material for the sender (built once by `build-realism`, gitignored in outputs/realism).

- shapes: for each codebook type, real whistles of that type's GMM cluster that classifier A clearly reads as that type;
- voices: the loudness pattern and 2nd and 3rd harmonics of clean recorded whistles;
- clicks: 2 ms cuts of clean clicks in regular trains, with their real times on the rhythm bank's time axis;
- wobble (wobble.npz, built beside it by `build-wobble`): the fine frequency wander of real whistles, each one's contour minus
  its cubic fit. The VAE's decodes lack it (WC-R3, EXP-021), so each drawn data shape gets one, stretched to its length.

Everything between two clicks stays silent, so no sea background enters the transmitted file. The receiver never needs this
library: it reads the same 16 shapes as before.
"""
from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import signal

from . import bank
from .config import PROJECT_ROOT, WhistleCodeError, default_config
from .contour import Contour, centred

FS = 96000
HOP = 512                       # STFT step at 96 kHz: 5.33 ms, the detector's frame step
NFFT = 1024
BIN_HZ = FS / NFFT
ENV_POINTS, HARMONIC_POINTS = 64, 16
CLICK_BEFORE, CLICK_AFTER = 58, 134     # samples kept around a click's peak: 2 ms in all
CLICK_FADE = 24
MAX_CLICKS_PER_FILE = 2000


class RealismError(WhistleCodeError):
    pass


@dataclass(frozen=True)
class Library:
    shapes: list                # per type (16 symbols, then the signature): real contours, possibly empty
    env_db: np.ndarray          # (V, ENV_POINTS) loudness pattern, 0 dB = the whistle's median level
    h2_db: np.ndarray           # (V, HARMONIC_POINTS) 2nd harmonic relative to the fundamental
    h3_db: np.ndarray           # (V, HARMONIC_POINTS) 3rd harmonic relative to the fundamental
    steady: np.ndarray          # (V,) voices that data whistles may use
    click_t: np.ndarray         # (C,) time on the rhythm bank's axis, increasing
    click_wave: np.ndarray      # (C, 192) recorded waveform
    click_gain: float           # recorded amplitude -> WAV amplitude
    info: dict


def out_dir(cfg: dict | None = None) -> Path:
    return PROJECT_ROOT / (cfg or default_config())["realism"]["out_dir"]


# ---------------------------------------------------------------------------------------------- real shapes
def assign_components(latents: np.ndarray, weights: np.ndarray, means: np.ndarray, covariances: np.ndarray, dev, batch: int = 256) -> np.ndarray:
    """The most likely GMM component of every latent."""
    import torch

    mu = torch.from_numpy(means).to(dev)
    chol = torch.linalg.cholesky(torch.from_numpy(covariances).to(dev))
    inv = torch.linalg.solve_triangular(chol, torch.eye(chol.shape[-1], dtype=chol.dtype, device=dev)[None], upper=False)
    constant = torch.log(torch.from_numpy(weights).to(dev)) - torch.log(torch.diagonal(chol, dim1=-2, dim2=-1)).sum(dim=1)
    z = torch.from_numpy(np.asarray(latents, dtype=np.float64)).to(dev)
    out = []
    for i in range(0, len(z), batch):
        d = z[i:i + batch, None, :] - mu[None, :, :]
        maha = torch.cat([torch.einsum("kij,bkj->bki", inv[k:k + 500], d[:, k:k + 500]).pow(2).sum(dim=2)
                          for k in range(0, len(mu), 500)], dim=1)
        out.append((constant[None] - 0.5 * maha).argmax(dim=1).cpu().numpy())
    return np.concatenate(out)


def build_shapes(cfg: dict, log) -> tuple[list, dict]:
    """Real whistles of each type's cluster that classifier A clearly reads as that type."""
    from . import classify, codebook, model

    r, cb_cfg = cfg["realism"], cfg["codebook"]
    cb = codebook.load(cfg)
    gmm = model.load_gmm(cfg)
    files = model.model_files(cfg)
    log("assigning every training whistle to its GMM cluster")
    assigned = assign_components(np.load(files.latents), gmm.weights, gmm.means, gmm.covariances, model.device(cfg))
    z = np.load(PROJECT_ROOT / "preprocessed" / f"encounter_{int(cfg['synth']['fc_source_encounter'])}" / "contours.npz")
    image_index, offsets, freq, observed = z["image_index"], z["offsets"], z["freq_hz"], z["observed_fraction"]
    hop = float(z["frame_s"])
    of_image = {int(im): i for i, im in enumerate(image_index.tolist()) if im >= 0}
    templates = [t.contour for t in cb.all_types]
    ratio_max = float(r["shape_margin"])
    d_lo, d_hi = cb_cfg["duration_ms"]
    s_lo, s_hi = cb_cfg["span_hz"]
    out, counts = [], []
    for type_index, t in enumerate(cb.all_types):
        members = []
        for im in np.where(assigned == t.component)[0].tolist():
            i = of_image.get(int(im))
            if i is None or observed[i] < float(r["min_observed_fraction"]):
                continue
            c = Contour(centred(freq[offsets[i]:offsets[i + 1]].astype(np.float64)), hop)
            if d_lo <= c.duration_ms <= d_hi and s_lo <= c.span_hz <= s_hi:
                members.append(c)
        kept = []
        if members:
            dist = classify.distances(members, templates, cfg)
            best, _ = classify.decide(dist, 1.0)
            closest = np.sort(dist, axis=1)
            margin = closest[:, 0] / np.maximum(closest[:, 1], 1e-9)
            kept = [c for c, b, m in zip(members, best, margin) if int(b) == type_index and m < ratio_max]
        out.append(kept if len(kept) >= int(r["min_members"]) else [])
        counts.append({"type": type_index, "component": t.component, "cluster_members": int((assigned == t.component).sum()),
                       "usable": len(members), "kept": len(out[-1])})
        log(f"  type {type_index:2d}: {counts[-1]['cluster_members']:3d} whistles in the cluster, {len(members):3d} usable, {len(out[-1]):3d} kept")
    return out, {"types": counts}


# ---------------------------------------------------------------------------------------------- reading one recording
def _read_96k(path: Path) -> np.ndarray:
    parts = []
    with sf.SoundFile(str(path)) as f:
        fs = f.samplerate
        for block in f.blocks(blocksize=4_000_000, dtype="int16", always_2d=True):
            parts.append(block[:, 0].copy())
    if fs != 500000:
        raise RealismError(f"{path.name} is sampled at {fs} Hz, expected 500 kHz")
    return signal.resample_poly(np.concatenate(parts).astype(np.float64) / 32768, 24, 125)


def _resampled(values: np.ndarray, n: int) -> np.ndarray:
    return np.interp(np.linspace(0, 1, n), np.linspace(0, 1, len(values)), values)


def _voices_of(y: np.ndarray, tracks: list, s: dict) -> list:
    """Voices of the clean whistles of one recording. tracks: (start_s, frequency per frame) of every whistle in the file."""
    _, _, z = signal.stft(y.astype(np.float32), FS, window="hann", nperseg=NFFT, noverlap=NFFT - HOP, boundary=None, padded=False)
    mag = np.abs(z) * 2                                     # the amplitude of a steady tone
    floor = np.maximum(np.median(mag, axis=1), 1e-12)
    n_bins, n_frames = mag.shape
    ranges = [(t, t + len(f) * HOP / FS, float(np.mean(f))) for t, f in tracks]
    out = []
    for me, (start, f) in enumerate(tracks):
        if len(f) < 19 or float(np.max(f)) > s["voice_max_hz"]:
            continue
        frames = np.round(start * FS / HOP + np.arange(len(f))).astype(np.int64)
        if frames[0] < 0 or frames[-1] >= n_frames:
            continue
        a, b, fm = ranges[me]
        clash = any(i != me and t0 < b and t1 > a and any(abs(j * other - k * fm) < 400.0 for j in (1, 2, 3) for k in (1, 2, 3))
                    for i, (t0, t1, other) in enumerate(ranges))
        if clash:
            continue
        amps, levels = [], []
        for k in (1, 2, 3):
            centre = np.clip(np.round(k * f / BIN_HZ).astype(np.int64), 1, n_bins - 2)
            amps.append(np.max([mag[centre + d, frames] for d in (-1, 0, 1)], axis=0))
            levels.append(floor[centre])
        snr_db = 20 * np.log10(np.maximum(amps[0] / levels[0], 1e-9))
        if np.median(snr_db) < s["voice_min_snr_db"] or np.mean(snr_db >= s["voice_frame_snr_db"]) < 0.9:
            continue
        smooth = lambda v: np.convolve(np.pad(v, 1, mode="edge"), np.ones(3) / 3, "valid")
        a1 = np.maximum(smooth(amps[0]), 1e-12)
        median = float(np.median(a1))
        env = np.clip(20 * np.log10(a1 / median), -30.0, 12.0)
        harmonics = []
        for k in (1, 2):
            h = 20 * np.log10(np.maximum(smooth(amps[k]), 1e-12) / a1)
            harmonics.append(_resampled(np.clip(np.where(amps[k] >= 2 * levels[k], h, -40.0), -40.0, 0.0), HARMONIC_POINTS))
        if float(np.median(harmonics[0])) > s["max_h2_db"]:
            continue
        inner = env[int(0.1 * len(env)):max(int(0.9 * len(env)), int(0.1 * len(env)) + 1)]
        out.append((_resampled(env, ENV_POINTS), harmonics[0], harmonics[1], bool(inner.min() >= s["steady_floor_db"]), median))
    return out


def _clicks_of(y: np.ndarray, s: dict) -> tuple[np.ndarray, np.ndarray]:
    """Clean clicks of one recording that belong to a regular train: (peak times in s, waveforms)."""
    x = signal.sosfiltfilt(signal.butter(4, 5000.0, "highpass", fs=FS, output="sos"), y)
    n = len(x) // 4
    env = np.abs(x[:n * 4]).reshape(n, 4).max(axis=1)
    med = float(np.median(env))
    mad = float(np.median(np.abs(env - med))) * 1.4826
    peaks, _ = signal.find_peaks(env, height=med + 15 * mad, distance=48)
    times, waves = [], []
    fade = 0.5 - 0.5 * np.cos(np.pi * (np.arange(CLICK_FADE) + 0.5) / CLICK_FADE)
    need = 10 ** (float(s["click_min_snr_db"]) / 20)
    for q in peaks.tolist():
        p = q * 4 + int(np.argmax(np.abs(x[q * 4:q * 4 + 4])))
        if p < 480 or p + 624 > len(x):
            continue
        cut = x[p - CLICK_BEFORE:p + CLICK_AFTER].astype(np.float32)
        peak = float(np.abs(x[p]))
        around = np.concatenate([x[p - 480:p - 96], x[p + 240:p + 624]])
        sigma = float(np.median(np.abs(around))) / 0.6745
        rms = float(np.sqrt(np.mean(cut.astype(np.float64) ** 2)))
        if peak < need * sigma or peak < float(s["click_min_crest"]) * rms:
            continue
        cut[:CLICK_FADE] *= fade
        cut[-CLICK_FADE:] *= fade[::-1]
        times.append(p / FS)
        waves.append(cut)
    if len(times) < int(s["click_train_min"]):
        return np.zeros(0), np.zeros((0, CLICK_BEFORE + CLICK_AFTER), np.float32)
    t = np.array(times)
    ici = np.diff(t)
    lo, hi = s["click_ici_s"]
    good = (ici >= float(lo)) & (ici <= float(hi))
    ratio = float(s["click_ici_ratio"])
    keep = np.zeros(len(t), bool)
    i = 0
    while i < len(ici):
        if not good[i]:
            i += 1
            continue
        j = i
        while j + 1 < len(ici) and good[j + 1] and 1 / ratio < ici[j + 1] / ici[j] < ratio:
            j += 1
        if j - i + 2 >= int(s["click_train_min"]):
            keep[i:j + 2] = True
        i = j + 1
    w = np.stack(waves)[keep]
    t = t[keep]
    if len(t) > MAX_CLICKS_PER_FILE:
        strongest = np.sort(np.argsort(np.abs(w).max(axis=1))[-MAX_CLICKS_PER_FILE:])
        t, w = t[strongest], w[strongest]
    return t, w


def _process_recording(job: tuple) -> dict:
    """One recording: its clean voices and clicks (runs in a worker process)."""
    path, time_offset, tracks, s = job
    y = signal.sosfiltfilt(signal.butter(4, 2000.0, "highpass", fs=FS, output="sos"), _read_96k(Path(path)))
    voices = _voices_of(y, tracks, s)
    t, waves = _clicks_of(y, s)
    return {"voices": voices, "click_t": t + time_offset, "click_wave": waves, "name": Path(path).name}


# ---------------------------------------------------------------------------------------------- the library
def _jobs(cfg: dict) -> list:
    s = dict(cfg["realism"])
    base = bank.time_base(cfg)
    jobs = []
    for e in cfg["bank"]["encounters"]:
        z = np.load(PROJECT_ROOT / "preprocessed" / f"encounter_{int(e)}" / "contours.npz")
        offsets, freq, starts, sources = z["offsets"], z["freq_hz"], z["start_s"], z["source_file"]
        observed = z["observed_fraction"]
        by_file: dict[str, list] = {}
        for i, stem in enumerate(sources.tolist()):
            if observed[i] >= float(s["min_observed_fraction"]):
                by_file.setdefault(stem, []).append((float(starts[i]), freq[offsets[i]:offsets[i + 1]].astype(np.float64)))
        t0, shift = base[int(e)]
        for path in sorted((PROJECT_ROOT / f"encounter_{int(e)}_audio").glob("*.flac")):
            jobs.append((str(path), bank._file_time(path.stem) - t0 + shift, by_file.get(path.stem, []), s))
    return jobs


def build(cfg: dict | None = None, log=print) -> dict:
    """Build the library from the raw recordings and the VAE-GMM files (a few minutes)."""
    from . import codebook

    cfg = cfg or default_config()
    t_all = time.perf_counter()
    r = cfg["realism"]
    shapes, shape_info = build_shapes(cfg, log)
    jobs = _jobs(cfg)
    log(f"reading {len(jobs)} recordings with {r['workers']} workers")
    voices, click_t, click_wave = [], [], []
    with ProcessPoolExecutor(max_workers=int(r["workers"])) as pool:
        for n, got in enumerate(pool.map(_process_recording, jobs, chunksize=4), 1):
            voices += got["voices"]
            click_t.append(got["click_t"])
            click_wave.append(got["click_wave"])
            if n % 50 == 0 or n == len(jobs):
                log(f"  {n}/{len(jobs)} recordings: {len(voices)} clean voices, {sum(len(t) for t in click_t)} clicks "
                    f"[{(time.perf_counter() - t_all) / 60:.1f} min]")
    if not voices:
        raise RealismError("no clean voices were found in the recordings")
    rng = np.random.default_rng(int(cfg["codebook"]["seed"]))
    order = rng.permutation(len(voices))[:int(r["max_voices"])]
    chosen = [voices[int(i)] for i in order]
    recorded = float(np.median([v[4] for v in voices]))
    wav_level = float(cfg["sender"]["data_amplitude"]) * 10 ** (float(r["median_level_db"]) / 20)
    t = np.concatenate(click_t)
    w = np.concatenate(click_wave)
    by_time = np.argsort(t, kind="stable")
    path = out_dir(cfg)
    path.mkdir(parents=True, exist_ok=True)
    lens = np.array([len(c) for per_type in shapes for c in [x.offset_hz for x in per_type]], dtype=np.int64)
    np.savez(path / "library.npz",
             shape_type=np.array([i for i, per_type in enumerate(shapes) for _ in per_type], dtype=np.int64),
             shape_first=np.cumsum(np.r_[0, lens], dtype=np.int64),
             shape_hz=np.concatenate([c.offset_hz for per_type in shapes for c in per_type]) if len(lens) else np.zeros(0),
             hop_s=np.array(next((c.hop_s for per_type in shapes for c in per_type), 0.0)),
             env_db=np.stack([v[0] for v in chosen]).astype(np.float32), h2_db=np.stack([v[1] for v in chosen]).astype(np.float32),
             h3_db=np.stack([v[2] for v in chosen]).astype(np.float32), steady=np.array([v[3] for v in chosen]),
             click_t=t[by_time], click_wave=w[by_time], click_gain=np.array(wav_level / recorded))
    info = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "codebook_sha256": hashlib.sha256((codebook.out_dir(cfg) / "codebook.npz").read_bytes()).hexdigest(),
            "shapes": shape_info, "n_shapes": int(len(lens)), "n_clean_voices": len(voices), "n_voices": len(chosen),
            "n_steady_voices": int(sum(v[3] for v in chosen)), "n_clicks": int(len(t)), "recordings": len(jobs),
            "click_gain": wav_level / recorded, "minutes": round((time.perf_counter() - t_all) / 60, 1)}
    (path / "library.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    log(f"written to {path}: {info['n_shapes']} real shapes, {info['n_voices']} voices ({info['n_steady_voices']} steady), "
        f"{info['n_clicks']} clicks [{info['minutes']} min]")
    build_wobble(cfg, log)
    return info


def load(cfg: dict | None = None, codebook_sha256: str | None = None) -> Library:
    """The library, refused if it was built for another codebook."""
    cfg = cfg or default_config()
    path = out_dir(cfg)
    if not (path / "library.npz").exists():
        raise RealismError(f"no realism library in {path}; run: python whistlecode/whistlecode.py build-realism")
    info = json.loads((path / "library.json").read_text(encoding="utf-8"))
    if codebook_sha256 is not None and info["codebook_sha256"] != codebook_sha256:
        raise RealismError("the realism library was built for another codebook; run build-realism again")
    z = np.load(path / "library.npz")
    first, hz, kinds, hop = z["shape_first"], z["shape_hz"], z["shape_type"], float(z["hop_s"])
    shapes: list = [[] for _ in range(int(cfg["codebook"]["n_types"]) + 1)]
    for i, kind in enumerate(kinds.tolist()):
        shapes[kind].append(Contour(hz[first[i]:first[i + 1]], hop))
    return Library(shapes, z["env_db"], z["h2_db"], z["h3_db"], z["steady"], z["click_t"], z["click_wave"], float(z["click_gain"]), info)


# ---------------------------------------------------------------------------------------------- real wobble (WC-R3)
@dataclass(frozen=True)
class Wobble:
    residuals: tuple            # per real whistle: its contour minus its cubic fit, Hz per frame
    lengths: np.ndarray         # frames of each
    scale: float
    length_ratio: tuple         # a residual is used for shapes between its length / hi and its length / lo
    info: dict

    def apply(self, c: Contour, rng: np.random.Generator) -> Contour:
        """The shape plus the wobble of a real whistle of similar length, stretched to the shape's length."""
        n = c.n_frames
        lo, hi = self.length_ratio
        ok = np.flatnonzero((self.lengths >= lo * n) & (self.lengths <= hi * n))
        r = self.residuals[int(ok[rng.integers(len(ok))])] if len(ok) else self.residuals[int(np.argmin(np.abs(self.lengths - n)))]
        r = np.interp(np.linspace(0.0, 1.0, n), np.linspace(0.0, 1.0, len(r)), r)
        return Contour(centred(c.offset_hz + self.scale * r), c.hop_s)


def _wobble_limits(cfg: dict, hop_s: float) -> tuple[int, int]:
    """Frames of the codebook's shortest and longest whistle."""
    lo, hi = (float(v) / 1000 for v in cfg["codebook"]["duration_ms"])
    return int(np.ceil(lo / hop_s - 1e-9)), int(np.floor(hi / hop_s + 1e-9))


def build_wobble(cfg: dict | None = None, log=print) -> dict:
    """Contour minus cubic fit of every well-observed encounter-191 whistle in the codebook's ranges (a few seconds)."""
    cfg = cfg or default_config()
    r = cfg["realism"]
    src = PROJECT_ROOT / "preprocessed" / f"encounter_{int(r['wobble_encounter'])}" / "contours.npz"
    if not src.exists():
        raise RealismError(f"no {src.relative_to(PROJECT_ROOT).as_posix()}; it is made with the dataset (python whistle.py build-dataset)")
    z = np.load(src)
    n_frames, observed, offsets, freq = z["n_frames"], z["observed_fraction"], z["offsets"], z["freq_hz"]   # read each once
    f_lo, f_hi = _wobble_limits(cfg, float(z["frame_s"]))
    s_lo, s_hi = (float(v) for v in cfg["codebook"]["span_hz"])
    c_lo, c_hi = (float(v) for v in cfg["synth"]["fc_range_hz"])
    out = []
    for i, n in enumerate(n_frames):
        if not f_lo <= n <= f_hi or observed[i] < float(r["min_observed_fraction"]):
            continue
        f = freq[offsets[i]:offsets[i + 1]].astype(np.float64)
        span, centre = float(f.max() - f.min()), 0.5 * float(f.max() + f.min())
        if not (s_lo <= span <= s_hi and c_lo <= centre <= c_hi):
            continue
        x = np.arange(n) / n
        out.append((f - np.polyval(np.polyfit(x, f, 3), x)).astype(np.float32))
    if not out:
        raise RealismError("no real whistle passed the wobble filters")
    path = out_dir(cfg)
    path.mkdir(parents=True, exist_ok=True)
    np.savez(path / "wobble.npz", r=np.concatenate(out), offsets=np.r_[0, np.cumsum([len(v) for v in out])].astype(np.int64))
    info = {"created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": src.relative_to(PROJECT_ROOT).as_posix(),
            "source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(), "n_whistles": len(out), "frames": [f_lo, f_hi],
            "span_hz": [s_lo, s_hi], "centre_hz": [c_lo, c_hi], "min_observed_fraction": float(r["min_observed_fraction"]),
            "median_wobble_hz": round(float(np.median([v.std() for v in out])), 1),
            "sha256": hashlib.sha256((path / "wobble.npz").read_bytes()).hexdigest()}
    (path / "wobble.json").write_text(json.dumps(info, indent=1), encoding="utf-8")
    log(f"wobble of {len(out)} real whistles written to {path / 'wobble.npz'} (median {info['median_wobble_hz']} Hz)")
    return info


def load_wobble(cfg: dict | None = None) -> Wobble:
    cfg = cfg or default_config()
    path = out_dir(cfg)
    if not (path / "wobble.npz").exists():
        raise RealismError(f"no wobble library in {path}; run: python whistlecode/whistlecode.py build-wobble "
                           "(or set [realism] wobble_scale = 0 for campaign v1's sender)")
    z = np.load(path / "wobble.npz")
    r, offsets = z["r"], z["offsets"]
    res = tuple(r[offsets[i]:offsets[i + 1]] for i in range(len(offsets) - 1))
    info = json.loads((path / "wobble.json").read_text(encoding="utf-8"))
    lo, hi = (float(v) for v in cfg["realism"]["wobble_length_ratio"])
    return Wobble(res, np.array([len(v) for v in res]), float(cfg["realism"]["wobble_scale"]), (lo, hi), info)


# ---------------------------------------------------------------------------------------------- at transmit time
@dataclass(frozen=True)
class Performer:
    level_db: float             # above data_amplitude
    tone_db: float              # extra loss per harmonic


def group_of_animals(n_whistles: int, rng: np.random.Generator, cfg: dict) -> list:
    """Who sings each whistle, in time order. Data and cover whistles are drawn from the same group, so the same loudness range."""
    r = cfg["realism"]
    lo, hi = (float(v) for v in r["level_range_db"])
    k = int(r["n_animals"])
    levels = rng.permutation(lo + (hi - lo) * (np.arange(k) + 0.5) / k)
    tones = rng.uniform(*r["tone_range_db"], k)
    stay, jitter = float(r["animal_stay"]), float(r["level_jitter_db"])
    who = int(rng.integers(k))
    out = []
    for _ in range(n_whistles):
        if rng.random() >= stay:
            who = int(rng.integers(k))
        out.append(Performer(float(np.clip(levels[who] + rng.normal(0.0, jitter), lo, hi)), float(tones[who])))
    return out


def data_level_db(level_db: float, cfg: dict) -> float:
    """An animal's level for a data whistle: the same order of loudness, squeezed so that it never falls below the channel's
    reference level (the quietest data whistles were being lost in heavy noise)."""
    r = cfg["realism"]
    lo, hi = (float(v) for v in r["level_range_db"])
    floor = float(r["median_level_db"])
    return floor + (float(level_db) - lo) * (hi - floor) / (hi - lo)


def clicks_for(lib: Library, segments, busy_on: np.ndarray, busy_off: np.ndarray, guard_s: float) -> list:
    """(time in the frame, click index) of the recorded clicks of the walked bank stretches, except those near a data whistle."""
    out = []
    for start, end, shift in segments:
        a, b = np.searchsorted(lib.click_t, [start, end])
        for i in range(int(a), int(b)):
            t = float(lib.click_t[i]) + shift
            j = int(np.searchsorted(busy_on, t + guard_s))
            if j > 0 and t - guard_s < busy_off[j - 1]:
                continue
            out.append((t, i))
    return out
