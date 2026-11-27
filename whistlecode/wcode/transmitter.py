"""Message -> WAV (PLAN.md section 4).

For every slot of the frame:

1. the whistle type: the signature for the preamble, the symbol's type for the header and payload;
2. a new shape of that type: z = mean + tau x L x eps, decoded by the VAE and turned into a contour;
3. the self-check: the shape is kept only if it stays in the codebook's duration, span and gap limits and classifier A
   clearly recognises it as its own type. Otherwise a new eps is drawn, and after self_check_redraws failures the
   type's mean shape is used;
4. the audio: an FM tone at the slot's centre frequency, with envelope and 2nd harmonic, placed at the slot's start.

All the randomness comes from the key and nonce, so the same message, key and nonce always give the same audio.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from . import classify, codebook, contour, framing, keys, model, repro, schedule, synth
from .config import default_config

SIGNATURE = 16          # index of the signature whistle in Codebook.all_types


@dataclass(frozen=True)
class SentWhistle:
    slot: schedule.Slot
    type_index: int             # 0-15 = symbol, 16 = signature
    contour: contour.Contour
    redraws: int                # latents rejected by the self-check before this shape
    fell_back: bool             # True: every draw was rejected, so this is the type's mean shape


@dataclass(frozen=True)
class Transmission:
    audio: np.ndarray           # float32, mono
    fs: int
    frame: framing.Frame
    whistles: list[SentWhistle]
    lead_in_s: float            # the frame starts this long into the audio
    tau: float
    gain: float                 # amplitude of each whistle's fundamental in `audio`
    codebook_sha256: str

    @property
    def duration_s(self) -> float:
        return len(self.audio) / self.fs

    @property
    def n_fell_back(self) -> int:
        return sum(w.fell_back for w in self.whistles)

    @property
    def n_redrawn(self) -> int:
        return sum(w.redraws > 0 for w in self.whistles)

    def manifest(self) -> dict:
        """What was sent, for debugging and evaluation. It holds neither the key nor the message text."""
        return {"fs_hz": self.fs, "duration_s": round(self.duration_s, 4), "lead_in_s": self.lead_in_s, "tau": self.tau,
                "gain": self.gain, "nonce": self.frame.nonce, "payload_bytes": self.frame.length,
                "codebook_sha256": self.codebook_sha256, "n_whistles": len(self.whistles),
                "n_redrawn": self.n_redrawn, "n_fell_back": self.n_fell_back,
                "whistles": [{"index": w.slot.index, "part": w.slot.part, "start_s": round(w.slot.start_s, 6),
                              "fc_hz": round(w.slot.fc_hz, 2), "type": "signature" if w.type_index == SIGNATURE else w.type_index,
                              "duration_ms": round(w.contour.duration_ms, 2), "redraws": w.redraws, "fell_back": w.fell_back}
                             for w in self.whistles]}


class Transmitter:
    """Loads the codebook once (the VAE only when a whistle needs a new shape) and sends any number of messages."""

    def __init__(self, cfg: dict | None = None, codebook_path: str | Path | None = None, check_model: bool = True):
        self.cfg = cfg or default_config()
        path = Path(codebook_path) if codebook_path else codebook.out_dir(self.cfg)
        self.cb = codebook.load(self.cfg, path, check=check_model)
        self.codebook_sha256 = hashlib.sha256((path / "codebook.npz").read_bytes()).hexdigest()
        self.types = self.cb.all_types
        self.templates = [t.contour for t in self.types]
        self.means = np.stack([t.mean for t in self.types])
        self.chols = np.stack([t.chol for t in self.types])
        self.pool = schedule.pitch_pool(self.cfg)
        self.pcfg = repro.load_pipeline_config()
        self._vae = None

    @property
    def vae(self):
        if self._vae is None:
            self._vae = model.load_vae(self.cfg)
        return self._vae

    def accepted(self, c: contour.Contour | None, gap: int, type_index: int) -> bool:
        """The self-check for one decoded shape."""
        cb = self.cfg["codebook"]
        if c is None or gap > int(cb["max_gap_cols"]):
            return False
        d_lo, d_hi = cb["duration_ms"]
        s_lo, s_hi = cb["span_hz"]
        if not (d_lo <= c.duration_ms <= d_hi and s_lo <= c.span_hz <= s_hi):
            return False
        best, ambiguous = classify.decide(classify.distances([c], self.templates, self.cfg),
                                          float(self.cfg["classify"]["ambiguity_ratio"]))
        return int(best[0]) == type_index and not bool(ambiguous[0])

    def _shapes(self, idx: np.ndarray, tau: float, rng: np.random.Generator):
        """One shape per slot: (contours, rejected draws per slot, fell back to the mean per slot)."""
        n = len(idx)
        shapes = [self.templates[int(i)] for i in idx]
        redraws = np.zeros(n, dtype=np.int64)
        if tau == 0:
            return shapes, redraws, np.zeros(n, dtype=bool)
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
                c = self._vary(c, rng) if c is not None else None
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
            shapes[p] = self._vary(shapes[p], rng)
        return shapes, redraws, fell

    def _vary(self, c: contour.Contour, rng: np.random.Generator) -> contour.Contour:
        """A drawn shape as played; the format v2 sender adds real wobble here (sender.py). Checked before it is used."""
        return c

    def send(self, message: bytes | str, key: str, nonce: int | None = None, tau: float | None = None) -> Transmission:
        cfg = self.cfg
        tau = float(cfg["transmit"]["tau"] if tau is None else tau)
        if tau < 0:
            raise ValueError("tau must be >= 0")
        fr = framing.encode(message, key, nonce, cfg)
        slots = schedule.frame_slots(key, fr.nonce, fr.length, cfg, self.pool)
        idx = np.concatenate([np.full(fr.n_preamble, SIGNATURE), fr.symbols]).astype(np.int64)
        rng = keys.stream(keys.PAYLOAD, "variation", key, fr.nonce, cfg)
        shapes, redraws, fell = self._shapes(idx, tau, rng)

        fs = int(cfg["synth"]["fs_hz"])
        lead, tail = float(cfg["transmit"]["lead_in_s"]), float(cfg["transmit"]["tail_s"])
        end_s = max(s.start_s + c.n_frames * c.hop_s for s, c in zip(slots, shapes))
        x = np.zeros(int(np.ceil((lead + end_s + tail) * fs)))
        for slot, c in zip(slots, shapes):
            w = synth.whistle(c, slot.fc_hz, rng, cfg, fs)
            s0 = int(round((lead + slot.start_s) * fs))
            x[s0:s0 + len(w)] += w
        gain = 10 ** (float(cfg["transmit"]["peak_dbfs"]) / 20) / float(np.abs(x).max())
        whistles = [SentWhistle(s, int(i), c, int(r), bool(f)) for s, i, c, r, f in zip(slots, idx, shapes, redraws, fell)]
        return Transmission((x * gain).astype(np.float32), fs, fr, whistles, lead, tau, gain, self.codebook_sha256)


def write_wav(path: str | Path, tx: Transmission, manifest: bool = False, overwrite: bool = False) -> Path:
    """Write the float32 WAV, and with manifest=True a .json beside it (no key, no message text)."""
    path = Path(path)
    if path.suffix.lower() != ".wav":
        raise ValueError(f"the output must be a .wav file, got {path.name}")
    if path.exists() and not overwrite:
        raise ValueError(f"{path} already exists; use another name or --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), tx.audio, tx.fs, subtype="FLOAT", format="WAV")
    if manifest:
        path.with_suffix(".json").write_text(json.dumps(tx.manifest(), indent=1), encoding="utf-8")
    return path
