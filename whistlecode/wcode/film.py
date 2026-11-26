"""The page's film data (web/PLAN.md, WEB-5): real records only, exported once to web/film/ so the film runs without a server.

    python whistlecode/whistlecode.py export-film [--device auto]

Files (config.toml [film] out_dir):

  film.json     provenance, then one block per research beat:
    listen        one encounter-191 training image (8-bit levels, base64, row 0 = highest pitch) and the contour it was made from.
                  It is the most typical member (highest responsibility) of the component the "Hear it" whistle was drawn from
    learn         how to read learn.bin (count, scale, each axis's share of the variance), and which components the codebook uses
    speak         the 16 shapes and the signature (centred contours, every frame), and the four pitches of the "Hear it" slot
    hide          every sound of one real send of the example message, in time order: start, header and message whistles (with
                  symbols and the letters they carry), cover whistles as played, and recorded clicks
    hear          that send in real sea noise, decoded from the audio and the key alone, as the page's Decode does it. Times are
                  on the Hide beat's clock (seconds into the sent file); sync_error_ms is where the receiver found the frame,
                  against where it really was
  learn.bin     every latent mean of the model: int16 x, y, z (the first three principal axes, one common scale), then uint16
                component (MAP, the paper's eq. 12), little-endian, 8 bytes per whistle
  hear_it.wav   the "Hear it" data whistle, cut from the sent audio (16-bit at the page's play rate)

Nothing is picked by hand: the noise seed is the first from 0 whose decode is exact (the seeds skipped are recorded), and the
"Hear it" whistle is the first message whistle with no other sound within alone_margin_s of it.
"""
from __future__ import annotations

import base64
import csv
import datetime
import json
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

from . import channel, model, repro, web
from .config import PROJECT_ROOT, WhistleCodeError, default_config, project_version
from .contour import centred

CLICK_S = 0.01          # a recorded click's length, for the "Hear it" rule (they are a few milliseconds)
FORMAT = 1              # film.json layout; the page checks it


class FilmError(WhistleCodeError):
    pass


# ---------------------------------------------------------------------------------------------- pure helpers (tested)
def pca3(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(points on the first three principal axes, the axes (3, D), each axis's share of the total variance).
    Each axis's sign is fixed so that its largest loading is positive: the same data always gives the same picture."""
    x = np.asarray(x, dtype=np.float64)
    xc = x - x.mean(0)
    vals, vecs = np.linalg.eigh(xc.T @ xc / max(len(x) - 1, 1))
    order = np.argsort(vals)[::-1][:3]
    axes = vecs[:, order].T
    axes *= np.sign(axes[np.arange(3), np.abs(axes).argmax(1)])[:, None]
    return xc @ axes.T, axes, vals[order] / vals.sum()


POINT = np.dtype([("x", "<i2"), ("y", "<i2"), ("z", "<i2"), ("k", "<u2")])


def pack_points(xyz: np.ndarray, comp: np.ndarray) -> tuple[bytes, float]:
    """learn.bin and its scale: int16 coordinates = value * scale, one scale for all three axes (proportions kept)."""
    xyz, comp = np.asarray(xyz, dtype=np.float64), np.asarray(comp)
    if comp.min() < 0 or comp.max() > 65535:
        raise FilmError("component numbers must fit in 16 bits")
    scale = 32767.0 / max(float(np.abs(xyz).max()), 1e-12)
    a = np.empty(len(xyz), dtype=POINT)
    q = np.round(xyz * scale).astype(np.int16)
    a["x"], a["y"], a["z"], a["k"] = q[:, 0], q[:, 1], q[:, 2], comp.astype(np.uint16)
    return a.tobytes(), scale


def unpack_points(buf: bytes) -> tuple[np.ndarray, np.ndarray]:
    a = np.frombuffer(buf, dtype=POINT)
    return np.stack([a["x"], a["y"], a["z"]], 1), a["k"].astype(np.int64)


def thin(offsets_hz, n: int) -> list[float]:
    """A contour resampled to n points, in whole Hz."""
    f = np.asarray(offsets_hz, dtype=np.float64)
    if len(f) == 1:
        return [round(float(f[0]))] * n
    return [round(float(v)) for v in np.interp(np.linspace(0, len(f) - 1, n), np.arange(len(f)), f)]


def first_exact(attempt, max_seeds: int) -> tuple[int, object, list]:
    """(seed, its result, the seeds skipped with why) for the first seed from 0 where attempt(seed) -> (exact, result, why)."""
    skipped = []
    for seed in range(max_seeds):
        exact, result, why = attempt(seed)
        if exact:
            return seed, result, skipped
        skipped.append({"seed": seed, "why": why})
    raise FilmError(f"no seed from 0 to {max_seeds - 1} gave an exact decode: {skipped}")


def alone(sounds: list[dict], margin: float) -> int | None:
    """Index of the first message whistle with no other sound within margin seconds of it, or None."""
    for i, s in enumerate(sounds):
        if s["kind"] != "data" or s["part"] != "message":
            continue
        a, b = s["t0"] - margin, s["t1"] + margin
        if not any(j != i and o["t0"] < b and o["t1"] > a for j, o in enumerate(sounds)):
            return i
    return None


# ---------------------------------------------------------------------------------------------- the export
def export(cfg: dict | None = None, out_dir: Path | None = None, device: str | None = None, log=print) -> dict:
    cfg = cfg or default_config()
    f = cfg["film"]
    out = Path(out_dir) if out_dir else PROJECT_ROOT / f["out_dir"]
    text, key, nonce = str(f["text"]), str(f["key"]), int(f["nonce"])
    k_pts = int(f["contour_points"])

    log("loading the codebook, the rhythm bank and the sender")
    engine = web.Engine(cfg)
    engine.require()
    lineage = model.check_lineage(cfg)
    cb, b = engine.cb, engine.bank

    # ------------------------------------------------------------------ hide: one real send
    log(f"sending {text!r} under the film's key")
    info = engine.frame_info(text, key, nonce)
    notes = {w["i"]: w for w in info["whistles"]}
    tx = engine.sender.send(text, key, nonce)
    lead = tx.lead_in_s
    sounds = []
    for d in tx.data:
        t0 = lead + d.slot.start_s
        n = notes[d.slot.index]
        s = {"kind": "data", "part": web.PARTS[d.slot.part], "i": d.slot.index, "t0": round(t0, 4),
             "t1": round(t0 + d.contour.n_frames * d.contour.hop_s, 4), "fc": round(d.fc_hz, 1), "f": thin(d.contour.offset_hz, k_pts),
             "symbol": d.symbol, "shape": d.type_index, "band": d.band}
        s.update({k: n[k] for k in ("role", "about", "bits", "chars", "crc") if k in n})
        sounds.append(s)
    for c in tx.covers:
        fhz = b.contour_hz(c.bank_index)
        t0 = lead + c.start_s
        sounds.append({"kind": "cover", "t0": round(t0, 4), "t1": round(t0 + len(fhz) * b.hop_s, 4), "fc": round(c.fc_hz, 1),
                       "f": thin(centred(fhz), k_pts), "moved": c.state == 1})
    for t in tx.clicks_s:
        sounds.append({"kind": "click", "t0": round(lead + t, 4), "t1": round(lead + t + CLICK_S, 4)})
    sounds.sort(key=lambda s: (s["t0"], s["kind"]))
    n_data = sum(s["kind"] == "data" for s in sounds)
    n_cover = sum(s["kind"] == "cover" for s in sounds)
    if n_cover != tx.n_cover:
        raise FilmError("the sender's cover record does not match its count")

    # ------------------------------------------------------------------ "Hear it": a message whistle heard on its own
    margin = float(f["alone_margin_s"])
    j = alone(sounds, margin)
    is_alone = j is not None
    if j is None:
        j = next(i for i, s in enumerate(sounds) if s["kind"] == "data" and s["part"] == "message")
    heard = sounds[j]
    heard["hear_it"] = True
    a, z = int(max(heard["t0"] - margin, 0) * tx.fs), int(min(heard["t1"] + margin, tx.duration_s) * tx.fs)
    out.mkdir(parents=True, exist_ok=True)
    web.play_copy(tx.audio[a:z], tx.fs, out / "hear_it.wav", cfg)
    followed = next(d for d in tx.data if d.slot.index == heard["i"])
    k_followed = cb.all_types[followed.type_index].component

    # ------------------------------------------------------------------ hear: through the sea, then the page's decoder
    snr, enc = float(f["snr_db"]), int(f["noise_encounter"])
    log(f"into encounter-{enc} sea noise at {snr:g} dB, and decoding")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        def attempt(seed):
            rx = channel.through_channel(tx.audio, tx.fs, snr, engine.pool, enc, seed, cfg)
            path = tmp / f"heard_{seed}.wav"
            sf.write(str(path), rx.audio, rx.fs, subtype="FLOAT", format="WAV")
            d = tmp / f"decode_{seed}"
            d.mkdir()
            r = engine.run_decode(path, key, "heard", d, lambda _stage: None)
            exact = bool(r["ok"]) and r["text"] == text
            why = "exact" if exact else (f"read {r['text']!r}" if r["ok"] else f"failed at {r['stage']}")
            log(f"  seed {seed}: {why}")
            return exact, (rx, r), why

        seed, (rx, r), skipped = first_exact(attempt, int(f["max_seeds"]))

    shift = lead - r["offset_s"]                  # the receiver's clock -> the sent file's clock
    keep = ("i", "part", "state", "symbol", "shape", "band", "fc")
    slots = [{**{k: s[k] for k in keep if k in s}, "t0": round(s["t0"] + shift, 4), "t1": round(s["t1"] + shift, 4)}
             for s in r["slots"]]
    hear = {"snr_db": snr, "encounter": enc, "seed": seed, "skipped": skipped, "text": r["text"], "n_tracks": r["n_tracks"],
            "sync_votes": r["sync_votes"], "attempts": r["attempts"], "header": r["header"], "payload": r["payload"],
            "repair": r["repair"], "sync_error_ms": round(1000 * (r["offset_s"] - (rx.offset_s + lead)), 2), "slots": slots}

    # ------------------------------------------------------------------ learn: every latent, on three axes
    log("projecting the latents and assigning each to its component")
    files = model.model_files(cfg)
    lat = np.load(files.latents).astype(np.float32)
    from whistlepipe.vaegmm.gmm import GaussianMixtureEM

    gmm = GaussianMixtureEM.load(files.gmm, repro.resolve_device(device or cfg["model"]["device"]), verbose=False)
    comp, resp = gmm.predict(lat)
    xyz, axes, share = pca3(lat)
    buf, scale = pack_points(xyz, comp)
    (out / "learn.bin").write_bytes(buf)
    used = [t.component for t in cb.all_types]
    learn = {"n": int(len(lat)), "dim": int(lat.shape[1]), "file": "learn.bin", "bytes_per_point": POINT.itemsize, "scale": scale,
             "share": [round(float(v), 4) for v in share], "n_components": int(gmm.K),
             "n_components_used": int(len(np.unique(comp))), "codebook_components": used,
             "codebook_members": [int((comp == k).sum()) for k in used]}

    # ------------------------------------------------------------------ listen: a real member of the followed component
    tinfo = json.loads((files.run_dir / "train_info.json").read_text(encoding="utf-8"))
    encs = tinfo["dataset"]["encounters"]
    if len(encs) != 1:
        raise FilmError(f"the film expects a model trained on one encounter, not {encs}")
    enc_dir = PROJECT_ROOT / "preprocessed" / encs[0]
    images = np.load(enc_dir / "images.npy", mmap_mode="r")
    if images.shape[0] != len(lat):
        raise FilmError(f"{enc_dir.name}/images.npy has {images.shape[0]} images, the latents {len(lat)}")
    members = np.flatnonzero(comp == k_followed)
    if not len(members):
        raise FilmError(f"no whistle is assigned to component {k_followed}")
    best = int(members[np.argmax(resp[members])])
    with open(enc_dir / "images.csv", newline="", encoding="utf-8") as fh:
        row = next(r for i, r in enumerate(csv.DictReader(fh)) if i == best)
    con = np.load(enc_dir / "contours.npz")
    cid = int(row["contour_id"])
    if int(con["image_index"][cid]) != best:
        raise FilmError(f"contour {cid} does not belong to image {best}")
    fhz = con["freq_hz"][int(con["offsets"][cid]):int(con["offsets"][cid + 1])]
    levels = np.round(np.clip(np.asarray(images[best], dtype=np.float32), 0, 1) * 255).astype(np.uint8)
    listen = {"index": best, "encounter": encs[0], "source_file": row["source_file"], "start_s": float(row["start_s"]),
              "component": k_followed, "responsibility": round(float(resp[best]), 4), "rows": 128, "cols": 128,
              "hz_per_row": 93.75, "zero_row": 63, "s_per_col": float(con["frame_s"]), "col0": int(row["image_col0"]),
              "center_hz": float(row["center_hz"]), "levels_b64": base64.b64encode(levels.tobytes()).decode("ascii"),
              "contour_hz": [round(float(v), 1) for v in fhz]}

    # ------------------------------------------------------------------ speak: the alphabet
    speak = {"hop_s": cb.all_types[0].contour.hop_s,
             "shapes": [{"shape": i, "symbol": t.symbol, "component": t.component, "nk": round(t.nk, 1),
                         "ms": round(t.contour.duration_ms, 1), "f": [round(float(v), 1) for v in t.contour.offset_hz]}
                        for i, t in enumerate(cb.all_types)],
             "pitches_hz": [round(float(v), 1) for v in followed.slot.candidates_hz], "band": followed.band,
             "followed_shape": followed.type_index}

    film = {"format": FORMAT,
            "provenance": {"made_by": "python whistlecode/whistlecode.py export-film (whistlecode/wcode/film.py)",
                           "version": project_version(),
                           "created_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                           "model": lineage, "codebook_sha256": engine.codebook_sha256, "bank_sha256": tx.bank_sha256,
                           "images_sha256": tinfo["dataset"].get("arrays", {}).get(encs[0], {}).get("sha256"),
                           "example": {"text": text, "key": key, "nonce": nonce, "tau": tx.tau},
                           "rules": {"noise_seed": "the first seed from 0 whose decode is exact",
                                     "hear_it": f"the first message whistle with no other sound within {margin:g} s"
                                                + ("" if is_alone else " (none was; the first message whistle instead)")}},
            "listen": listen, "learn": learn, "speak": speak,
            "hide": {"text": text, "letters": info["letters"], "duration_s": round(tx.duration_s, 3), "lead_in_s": lead,
                     "n_data": n_data, "n_cover": n_cover, "n_clicks": len(tx.clicks_s),
                     "data_share": round(n_data / (n_data + n_cover), 4), "hear_it_file": "hear_it.wav", "sounds": sounds},
            "hear": hear}
    (out / "film.json").write_text(json.dumps(film, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return film
