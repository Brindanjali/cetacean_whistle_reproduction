"""WhistleCode on the project page: 05 · Encode and 06 · Decode (web/message.js).

    python whistlecode/whistlecode.py serve          ->  http://127.0.0.1:8000
    python whistlecode/whistlecode.py serve --lan    ->  https://<this computer's address>:8000, for other computers too

Another computer can record a played message with its microphone (06 · Decode, Record). Browsers allow the microphone only on
https pages or on localhost, so --lan serves https with a certificate this computer makes for itself (tls_files). The other
browser warns once that nobody vouches for it; after "Advanced, Proceed" the page works as usual.

The page, Try it and its API come from the reproduction's own app (src/whistlepipe/server.py), mounted unchanged at /. These
routes sit in front of it:

    GET  /api/wc/status                          ready, model and codebook, limits, the 17 whistle shapes
    POST /api/wc/frame       {text, key, nonce}  every encoding step and every data whistle; instant, no audio
    POST /api/wc/send        {text, key, nonce}  -> job: the WAV the sender plays, its picture and the sender's record
    POST /api/wc/sea         {job, snr_db, encounter, seed}  -> job: that WAV inside real ocean noise
    POST /api/wc/decode      multipart (file, key)           -> job: the message, read from the audio and the key alone
    POST /api/wc/decode-job  {job, file, key}    a WAV this server made ("sent" or "heard"), copied into the decode job first
    POST /api/wc/check       {send, decode}      the decoder's reading of each whistle against the sender's record
    GET  /api/wc/jobs/{id}                       state, stage, error, result URL
    GET  /api/wc/files/{id}/{name}               result.json, PNG and WAV files of a job
    GET  /healthz                                for monitoring: 200 while messages can be served ("ok", or "starting"
                                                 while the models load), 503 when they cannot ("down"); with the version

What keeps the demonstration honest:

- A decode job reads only its own input file and the key it is given. It never opens another job's folder.
- The key and the message text are never written to disk. The sender's record holds the whistle symbols, which the key scrambles.
- Comparing a reading with the sender's record is a separate step (/check), run after decoding.

Jobs run one at a time on one worker thread and write whistlecode/outputs/web/<id>/; the newest web.keep_jobs folders are kept.
"""
from __future__ import annotations

import datetime
import hashlib
import ipaddress
import json
import queue
import re
import secrets
import shutil
import socket
import threading
import time
import traceback
from fractions import Fraction
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from . import bank, channel, codebook, format2, layout, receiver, schedule, sender
from .config import PROJECT_ROOT, default_config, project_version
from .framing import FramingError

JOB_ID = re.compile(r"^wc_\d{8}T\d{6}Z_[0-9a-f]{6}$")
FILE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
PARTS = {layout.PREAMBLE: "start", layout.HEADER: "header", layout.PAYLOAD: "message"}
SHAPE_POINTS = 24


class InputError(ValueError):
    """A problem with what the visitor sent; shown to them as it is."""


# ---------------------------------------------------------------------------------------------- audio for the page
def picture(x: np.ndarray, fs: float, path: Path, cfg: dict) -> dict:
    """An 8-bit grey-level spectrogram (loud = 255, top row = highest pitch). The page colours it with the palette of Try it."""
    w = cfg["web"]
    f_lo, f_hi = float(w["picture_hz"][0]), min(float(w["picture_hz"][1]), fs / 2)
    x = np.asarray(x, dtype=np.float32)
    dur = len(x) / fs
    cps = min(float(w["picture_cols_per_s"]), 30000.0 / max(dur, 1e-6))
    n_cols = max(1, int(dur * cps))
    nfft = 1 << int(round(np.log2(fs * 0.0107)))                  # about 10.7 ms: 1,024 points at 96 kHz
    win = np.hanning(nfft).astype(np.float32)
    rows = int(w["picture_rows"])
    pos = np.linspace(f_hi, f_lo, rows) / (fs / nfft)             # fractional FFT bin of each row
    j0 = np.clip(np.floor(pos).astype(np.int64), 0, nfft // 2 - 1)
    a = (pos - j0).astype(np.float32)
    starts = np.round(np.arange(n_cols) * fs / cps).astype(np.int64)
    xp = np.pad(x, (nfft // 2, nfft // 2))
    out = np.empty((rows, n_cols), dtype=np.float32)
    for c0 in range(0, n_cols, 2048):
        idx = starts[c0:c0 + 2048]
        idx = np.minimum(idx, len(xp) - nfft)
        p = np.abs(np.fft.rfft(xp[idx[:, None] + np.arange(nfft)[None, :]] * win, axis=1)) ** 2
        out[:, c0:c0 + len(idx)] = (p[:, j0] * (1 - a) + p[:, j0 + 1] * a).T
    level = 10 * np.log10(out + 1e-20)
    hi = float(np.percentile(level, 99.95))
    lo = max(hi - float(w["picture_range_db"]), float(np.median(level)) + float(w["picture_floor_db"]))   # the sea's own hiss stays pale
    img = np.clip((level - lo) / max(hi - lo, 1e-6), 0, 1)
    from PIL import Image

    Image.fromarray((img * 255).round().astype(np.uint8), mode="L").save(path)
    return {"png": path.name, "t1_s": round(dur, 4), "cols": n_cols, "cols_per_s": round(cps, 4), "rows": rows,
            "f_lo": f_lo, "f_hi": f_hi}


def play_copy(x: np.ndarray, fs: float, path: Path, cfg: dict) -> str:
    """The copy the page plays: 16-bit at web.play_fs_hz, scaled to web.play_peak."""
    from scipy.signal import resample_poly

    w = cfg["web"]
    target = int(w["play_fs_hz"])
    y = np.asarray(x, dtype=np.float64)
    if int(round(fs)) != target:
        r = Fraction(target, int(round(fs))).limit_denominator(1000)
        y = resample_poly(y, r.numerator, r.denominator)
    peak = float(np.abs(y).max()) if len(y) else 0.0
    if peak > 0:
        y *= float(w["play_peak"]) / peak
    sf.write(str(path), y.astype(np.float32), target, subtype="PCM_16")
    return path.name


def read_audio(path: Path, cfg: dict) -> tuple[np.ndarray, int]:
    """A recording as mono float32 (its first channel), checked against the page's limits."""
    w = cfg["web"]
    try:
        info = sf.info(str(path))
    except RuntimeError as e:
        raise InputError("this file could not be read as audio (use WAV, FLAC or OGG)") from e
    if info.samplerate < int(w["min_rate_hz"]):
        raise InputError(f"the recording is sampled at {info.samplerate} Hz; at least {int(w['min_rate_hz'])} Hz is needed, "
                         "because the whistles reach 14.5 kHz")
    if info.duration > float(w["max_seconds"]):
        raise InputError(f"the recording is {info.duration:.0f} s long; the decoder takes up to {float(w['max_seconds']):.0f} s")
    x, fs = sf.read(str(path), dtype="float32", always_2d=True)
    if not len(x):
        raise InputError("the recording is empty")
    return x[:, 0], int(fs)


# ---------------------------------------------------------------------------------------------- the engine
class Engine:
    """The rhythm bank, pitch pool and codebook (loaded at once: /frame needs them), and the sender and receiver (loaded once,
    in the background, the first time they are needed). If the files are missing, the error is kept and shown on the page."""

    def __init__(self, cfg: dict | None = None, book: codebook.Codebook | None = None, rhythm_bank: bank.Bank | None = None,
                 make_sender=None, make_receiver=None):
        self.cfg = cfg or default_config()
        self.error: str | None = None
        self.cb, self.bank, self.pool, self.codebook_sha256 = book, rhythm_bank, None, None
        try:
            if self.cb is None:
                self.cb = codebook.load(self.cfg)       # refuses a codebook built from other model files
                self.codebook_sha256 = hashlib.sha256((codebook.out_dir(self.cfg) / "codebook.npz").read_bytes()).hexdigest()
            if self.bank is None:
                self.bank = bank.load(self.cfg)
            self.pool = schedule.pitch_pool(self.cfg)
        except Exception as e:  # noqa: BLE001  (the page is still served, and says what is missing)
            self.error = f"{type(e).__name__}: {e}"
        self._make_sender = make_sender or (lambda: sender.Sender(self.cfg, rhythm_bank=self.bank))
        self._make_receiver = make_receiver or (lambda: receiver.Receiver(self.cfg, rhythm_bank=self.bank))
        self._sender = self._receiver = None
        self._lock = threading.Lock()
        self.warm_error: str | None = None

    @property
    def sender(self) -> sender.Sender:
        with self._lock:
            if self._sender is None:
                self._sender = self._make_sender()
            return self._sender

    @property
    def receiver(self) -> receiver.Receiver:
        with self._lock:
            if self._receiver is None:
                self._receiver = self._make_receiver()
                _ = self._receiver.detector            # the detector network loads on first use; load it now
            return self._receiver

    @property
    def warm(self) -> bool:
        return self._sender is not None and self._receiver is not None

    def warm_up(self) -> None:
        try:
            _ = self.sender, self.receiver
        except Exception as e:  # noqa: BLE001
            self.warm_error = f"{type(e).__name__}: {e}"

    # ------------------------------------------------------------------------------------------ status
    def shapes(self) -> list[dict]:
        """The 16 shapes and the signature (index 16): length and SHAPE_POINTS centred pitch offsets, for the page's chips."""
        out = []
        for i, t in enumerate(self.cb.all_types):
            f = np.asarray(t.contour.offset_hz, dtype=np.float64)
            u = np.interp(np.linspace(0, len(f) - 1, SHAPE_POINTS), np.arange(len(f)), f)
            out.append({"i": i, "ms": round(len(f) * t.contour.hop_s * 1000, 1), "f": [round(float(v), 1) for v in u]})
        return out

    def status(self) -> dict:
        w = self.cfg["web"]
        limits = {"max_chars": int(w["max_chars"]), "max_key_chars": int(w["max_key_chars"]), "max_upload_mb": int(w["max_upload_mb"]),
                  "max_seconds": float(w["max_seconds"]), "min_rate_hz": int(w["min_rate_hz"]), "formats": list(w["formats"])}
        base = {"limits": limits, "snr_choices_db": list(w["snr_choices_db"]), "noise_choices": list(w["noise_choices"]),
                "alphabet": self.cfg["format2"]["alphabet"]}
        if self.error:
            return {**base, "ready": False, "loading": False, "message": self.error}
        model = self.cb.info.get("model", {})
        return {**base, "ready": self.warm_error is None, "loading": not self.warm and self.warm_error is None,
                "message": self.warm_error or "", "shapes": self.shapes(),
                "model": {"checkpoint": model.get("checkpoint"), "sha256": (model.get("checkpoint_sha256") or "")[:12]},
                "codebook_sha256": (self.codebook_sha256 or "")[:12]}

    # ------------------------------------------------------------------------------------------ checks
    def check_text(self, text: str) -> None:
        w = self.cfg["web"]
        if not text:
            raise InputError("write a message first")
        if len(text) > int(w["max_chars"]):
            raise InputError(f"the message is {len(text)} characters; the page sends up to {int(w['max_chars'])}")
        try:
            format2.split_message(text, self.cfg)           # the byte limit of raw messages
        except FramingError as e:
            raise InputError(str(e)) from e

    def check_key(self, key: str) -> None:
        w = self.cfg["web"]
        if not key:
            raise InputError("the key is empty")
        if len(key) > int(w["max_key_chars"]):
            raise InputError(f"the key is {len(key)} characters; up to {int(w['max_key_chars'])} are allowed")

    def require(self) -> None:
        if self.error:
            raise InputError(f"WhistleCode is not ready: {self.error}")

    # ------------------------------------------------------------------------------------------ /frame
    def frame_info(self, text: str, key: str, nonce: int) -> dict:
        """Every step of encoding, and every data whistle in the order it is played. No audio is made."""
        self.require()
        self.check_text(text)
        self.check_key(key)
        try:
            ex = format2.explain(text, key, nonce, self.cfg)
        except (FramingError, ValueError) as e:
            raise InputError(str(e)) from e
        fr, cb_bits = ex.frame, ex.char_bits
        head, pay = layout.frame_layout(fr, key, self.bank, self.pool, self.cfg)
        n_msg = len(ex.message_bits)
        if fr.mode == format2.COMPACT:
            letters = [{"c": c, "bits": format(self.cfg["format2"]["alphabet"].index(c), "05b")} for c in text]
        else:
            letters = [{"c": chr(b) if 32 <= b < 127 else f"{b:02X}", "bits": format(b, "08b")} for b in text.encode("utf-8")]

        def payload_note(k: int | None) -> dict:
            if k is None:
                return {"role": "spare"}
            lo, hi = 6 * k, 6 * k + 6
            d = {"role": "data", "bits": [lo, hi]}
            if lo < n_msg:
                d["chars"] = [lo // cb_bits, (min(hi, n_msg) - 1) // cb_bits]
            if hi > n_msg and lo < n_msg + format2.CRC_BITS:
                d["crc"] = True
            return d

        header_notes = ["mode and length", "length and nonce", "nonce"]
        whistles = []
        lead = float(self.cfg["transmit"]["lead_in_s"])
        templates = self.cb.all_types
        n_pre = int(self.cfg["framing"]["n_preamble"])
        symbols = [-1] * n_pre + fr.symbols.tolist()
        notes = ([{"role": "start"}] * n_pre
                 + [{"role": "header", "about": header_notes[i]} if i < len(header_notes) else {"role": "header-spare"}
                    for i in range(len(fr.header_symbols))]
                 + [payload_note(k) for _, _, k in ex.payload_source])
        for s, y, note in zip(head.slots + pay.slots, symbols, notes):
            shape = 16 if y < 0 else y >> 2
            whistles.append({"i": s.index, "part": PARTS[s.part], "symbol": y, "shape": shape, "band": 0 if y < 0 else y & 3,
                             "t": round(lead + s.start_s, 4), **note})
        ends = [lead + s.start_s + len(templates[w["shape"]].contour.offset_hz) * templates[w["shape"]].contour.hop_s
                for s, w in zip(head.slots + pay.slots, whistles)]
        duration = max(lead + pay.end_s, max(ends)) + float(self.cfg["transmit"]["tail_s"])
        return {"mode": "compact" if fr.mode == format2.COMPACT else "raw", "unit": "characters" if fr.mode == format2.COMPACT else "bytes",
                "length": fr.length, "nonce": fr.nonce, "char_bits": cb_bits, "letters": letters, "message_bits": n_msg,
                "crc": f"{ex.crc:04X}", "crc_bits": format2.CRC_BITS, "pad_bits": ex.pad_bits,
                "plain": ex.plain.tolist(), "scrambled": ex.scrambled.tolist(), "blocks": [list(b) for b in ex.blocks],
                "parity": sum(p for _, p in ex.blocks),
                "header": {"data": int(self.cfg["format2"]["header_data_symbols"]), "parity": int(self.cfg["format2"]["header_parity"])},
                "n_start": n_pre, "n_header": len(fr.header_symbols), "n_payload": len(fr.payload_symbols),
                "n_cover": len(head.covers) + len(pay.covers), "duration_s": round(duration, 1), "whistles": whistles}

    # ------------------------------------------------------------------------------------------ jobs
    def run_send(self, text: str, key: str, nonce: int, out: Path, progress) -> dict:
        self.require()
        progress("drawing the whistles")
        tx = self.sender.send(text, key, nonce)
        progress("writing the sound")
        sender.write_wav(out / "sent.wav", tx)
        play = play_copy(tx.audio, tx.fs, out / "sent_play.wav", self.cfg)
        progress("drawing the picture")
        pic = picture(tx.audio, tx.fs, out / "sent.png", self.cfg)
        whistles = []
        for d in tx.data:
            f = d.fc_hz + np.asarray(d.contour.offset_hz)
            t0 = tx.lead_in_s + d.slot.start_s
            whistles.append({"i": d.slot.index, "part": PARTS[d.slot.part], "symbol": d.symbol, "shape": d.type_index, "band": d.band,
                             "t0": round(t0, 4), "t1": round(t0 + d.contour.n_frames * d.contour.hop_s, 4),
                             "f0": round(float(f.min()), 1), "f1": round(float(f.max()), 1)})
        return {"kind": "send", "duration_s": round(tx.duration_s, 3), "fs": tx.fs, "nonce": tx.frame.nonce,
                "mode": "compact" if tx.frame.mode == format2.COMPACT else "raw", "length": tx.frame.length,
                "n_data": len(tx.data), "n_cover": tx.n_cover, "n_cover_moved": tx.n_cover_moved, "n_clicks": tx.n_clicks,
                "n_real_shapes": tx.n_real_shapes, "codebook_sha256": tx.codebook_sha256[:12], "whistles": whistles,
                "picture": pic, "audio": {"play": play, "file": "sent.wav"}}

    def run_sea(self, send_dir: Path, send_id: str, snr_db: float, encounter: int, seed: int, out: Path, progress) -> dict:
        self.require()
        progress("mixing it into the sea")
        x, fs = sf.read(str(send_dir / "sent.wav"), dtype="float32", always_2d=True)
        rx = channel.through_channel(x[:, 0], fs, snr_db, self.pool, encounter, seed, self.cfg)
        sf.write(str(out / "heard.wav"), rx.audio, rx.fs, subtype="FLOAT", format="WAV")
        play = play_copy(rx.audio, rx.fs, out / "heard_play.wav", self.cfg)
        progress("drawing the picture")
        pic = picture(rx.audio, rx.fs, out / "heard.png", self.cfg)
        return {"kind": "sea", "from": send_id, "snr_db": snr_db, "encounter": rx.encounter, "seed": seed,
                "offset_s": round(rx.offset_s, 6), "duration_s": round(len(rx.audio) / rx.fs, 3), "noise_files": rx.noise_files,
                "picture": pic, "audio": {"play": play, "file": "heard.wav"}}

    def run_decode(self, path: Path, key: str, source: str, out: Path, progress) -> dict:
        """The message in one recording, from that recording and the key alone."""
        self.require()
        progress("reading the recording")
        x, fs = read_audio(path, self.cfg)
        progress("listening for whistles")
        rx = self.receiver
        tracks = rx.tracks(x, fs)
        progress("following the key")
        r = rx.decode_tracks(tracks, key)
        progress("drawing the picture")
        pic = picture(x, fs, out / "recording.png", self.cfg)
        play = play_copy(x, fs, out / "recording_play.wav", self.cfg)
        templates = self.cb.all_types
        slots = []
        if r.offset_s is not None:
            readings = []
            hdr_slots = [s for s in r.header_slots if s.part == layout.HEADER]
            for group, part in ((hdr_slots, r.header), (list(r.payload_slots), r.body)):
                if part is not None:
                    readings += [(s, int(part.symbols[j]), bool(part.missed[j])) for j, s in enumerate(group)]
            by_index = {s.index: (y, m) for s, y, m in readings}
            for s in [*r.header_slots, *r.payload_slots]:
                t0 = r.offset_s + s.start_s
                cands = [round(float(f), 1) for f in s.candidates_hz]
                d = {"i": s.index, "part": PARTS[s.part], "t0": round(t0, 4), "candidates": cands}
                if s.part == layout.PREAMBLE:
                    d.update(state="start", shape=16, band=0, fc=cands[0])
                elif s.index not in by_index:
                    d.update(state="unread")
                else:
                    y, missed = by_index[s.index]
                    if y >= 0:
                        d.update(state="read", symbol=y, shape=y >> 2, band=y & 3, fc=cands[y & 3])
                    else:
                        d.update(state="missed" if missed else "doubtful")
                if "shape" in d:
                    c = templates[d["shape"]].contour
                    f = d["fc"] + np.asarray(c.offset_hz)
                    d.update(t1=round(t0 + len(f) * c.hop_s, 4), f0=round(float(f.min()), 1), f1=round(float(f.max()), 1))
                else:
                    d.update(t1=round(t0 + 0.2, 4), f0=round(min(cands) - 400, 1), f1=round(max(cands) + 400, 1))
                slots.append(d)

        def counts(part) -> dict | None:
            if part is None:
                return None
            n = len(part.symbols)
            return {"n": n, "read": n - part.n_missed - part.n_doubtful, "missed": part.n_missed, "doubtful": part.n_doubtful}

        spare = None
        if r.mode is not None and r.length is not None:
            spare = {"header": int(self.cfg["format2"]["header_parity"]),
                     "payload": sum(p for _, p in format2.blocks(format2.data_symbols(r.mode, r.length), self.cfg))}
        elif r.header is not None:
            spare = {"header": int(self.cfg["format2"]["header_parity"]), "payload": None}
        return {"kind": "decode", "source": source, "duration_s": round(len(x) / fs, 3), "fs": fs,
                "ok": r.ok, "stage": r.stage, "detail": r.detail, "text": r.text if r.ok else None,
                "hex": r.payload.hex() if r.ok and r.text is None else None,
                "mode": None if r.mode is None else ("compact" if r.mode == format2.COMPACT else "raw"),
                "nonce": r.nonce, "length": r.length, "n_tracks": r.n_tracks,
                "offset_s": None if r.offset_s is None else round(r.offset_s, 4), "sync_votes": round(r.sync_votes, 1),
                "attempts": r.attempts, "header": counts(r.header), "payload": counts(r.body),
                "repair": {"wrong": r.n_repaired_wrong, "lost": r.n_repaired_lost, "spare": spare},
                "slots": slots, "picture": pic, "audio": {"play": play}}


def check(send: dict, decode: dict) -> dict:
    """The decoder's reading of each whistle against the sender's record (both result.json files)."""
    if decode.get("nonce") is None or not decode.get("slots"):
        return {"comparable": False, "why": "the decoder found no message header to compare"}
    if decode["nonce"] != send["nonce"] or decode.get("length") not in (None, send["length"]):
        return {"comparable": False, "why": "the decoder read the header of a different message"}
    sent = {w["i"]: w["symbol"] for w in send["whistles"] if w["part"] != "start"}
    out, tally = [], {"right": 0, "wrong": 0, "lost": 0}
    for s in decode["slots"]:
        if s["part"] == "start" or s["i"] not in sent or s["state"] == "unread":
            continue
        read = s.get("symbol")
        verdict = "lost" if read is None else ("right" if read == sent[s["i"]] else "wrong")
        tally[verdict] += 1
        out.append({"i": s["i"], "verdict": verdict, "sent": sent[s["i"]], "read": read})
    return {"comparable": True, "whistles": out, "counts": tally, "repaired": bool(decode.get("ok"))}


# ---------------------------------------------------------------------------------------------- jobs
def new_job_id() -> str:
    return "wc_" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "_" + secrets.token_hex(3)


class Jobs:
    def __init__(self, root: Path, keep: int):
        self.root, self.keep = root, keep
        self.root.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, dict] = {}
        self.q: queue.Queue = queue.Queue()
        threading.Thread(target=self._work, daemon=True, name="whistlecode-worker").start()

    def new(self) -> tuple[str, Path]:
        jid = new_job_id()
        while (self.root / jid).exists():
            jid = new_job_id()
        d = self.root / jid
        d.mkdir(parents=True)
        return jid, d

    def submit(self, jid: str, kind: str, fn) -> dict:
        self.jobs[jid] = {"id": jid, "kind": kind, "state": "queued", "stage": None, "error": None, "result": None}
        self.q.put((jid, fn))
        self._prune()
        return {"job": jid, "position": self.q.qsize()}

    def _work(self):
        while True:
            jid, fn = self.q.get()
            job = self.jobs[jid]
            job["state"] = "running"

            def progress(stage):
                job["stage"] = stage  # noqa: B023 -- runs during this job only

            d = self.root / jid
            try:
                result = fn(progress)
                (d / "result.json").write_text(json.dumps(result, indent=1), encoding="utf-8")
                job.update(state="done", result=f"/api/wc/files/{jid}/result.json")
            except (InputError, FramingError) as e:
                job.update(state="error", error=str(e))
            except Exception as e:  # noqa: BLE001  (shown as an internal error; the traceback goes to the job folder)
                (d / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
                job.update(state="error", error=f"internal error ({type(e).__name__}); see whistlecode/outputs/web/{jid}/error.txt")

    def _prune(self):
        dirs = sorted(p for p in self.root.iterdir() if p.is_dir() and JOB_ID.match(p.name))     # names start with the time
        for p in dirs[:-self.keep] if len(dirs) > self.keep else []:
            if self.jobs.get(p.name, {}).get("state") not in ("queued", "running"):
                shutil.rmtree(p, ignore_errors=True)
                self.jobs.pop(p.name, None)

    def folder(self, jid: str) -> Path:
        d = self.root / jid
        if not JOB_ID.match(jid) or not d.is_dir():
            raise KeyError(jid)
        return d


# ---------------------------------------------------------------------------------------------- requests
class FrameRequest(BaseModel):
    text: str
    key: str
    nonce: int


class SeaRequest(BaseModel):
    job: str
    snr_db: float = 15.0
    encounter: int = 276
    seed: int = 0


class DecodeJobRequest(BaseModel):
    job: str
    file: str               # "sent" or "heard"
    key: str


class CheckRequest(BaseModel):
    send: str
    decode: str


# ---------------------------------------------------------------------------------------------- the app
def create_app(engine: Engine | None = None, page=None, warm: bool = True):
    """The WhistleCode routes; `page` (an ASGI app, normally the reproduction's own) is mounted behind them at /."""
    engine = engine or Engine()
    w = engine.cfg["web"]
    jobs = Jobs(PROJECT_ROOT / w["out_dir"], int(w["keep_jobs"]))

    def folder(jid: str) -> Path:
        try:
            return jobs.folder(jid)
        except KeyError:
            raise HTTPException(404, "unknown job") from None

    def result_of(jid: str, kind: str) -> dict:
        p = folder(jid) / "result.json"
        if not p.exists():
            raise HTTPException(409, "that job has not finished")
        r = json.loads(p.read_text(encoding="utf-8"))
        if r.get("kind") != kind:
            raise HTTPException(400, f"that job is not a {kind} job")
        return r

    def nonce_ok(n: int) -> int:
        if not 0 <= n <= 255:
            raise InputError("the nonce must be 0-255")
        return n

    api = APIRouter(prefix="/api/wc")

    @api.get("/status")
    def status():
        return {**engine.status(), "queue": jobs.q.qsize()}

    @api.post("/frame")
    def frame(req: FrameRequest):
        return engine.frame_info(req.text, req.key, nonce_ok(req.nonce))

    @api.post("/send")
    def send(req: FrameRequest):
        engine.require()
        engine.check_text(req.text)
        engine.check_key(req.key)
        text, key, nonce = req.text, req.key, nonce_ok(req.nonce)
        jid, d = jobs.new()
        return jobs.submit(jid, "send", lambda progress: engine.run_send(text, key, nonce, d, progress))

    @api.post("/sea")
    def sea(req: SeaRequest):
        engine.require()
        result_of(req.job, "send")
        if req.snr_db not in [float(v) for v in w["snr_choices_db"]]:
            raise InputError(f"choose a signal level of {', '.join(f'{v:g}' for v in w['snr_choices_db'])} dB")
        if req.encounter not in [int(v) for v in w["noise_choices"]]:
            raise InputError(f"choose the noise of encounter {' or '.join(str(v) for v in w['noise_choices'])}")
        src, src_id = folder(req.job), req.job
        jid, d = jobs.new()
        seed = int(req.seed) & 0x7FFFFFFF
        return jobs.submit(jid, "sea", lambda progress: engine.run_sea(src, src_id, req.snr_db, req.encounter, seed, d, progress))

    @api.post("/decode")
    async def decode(file: UploadFile = File(...), key: str = Form(...)):
        engine.require()
        engine.check_key(key)
        name = Path(file.filename or "recording").name[:120]
        ext = Path(name).suffix.lower()
        if ext not in w["formats"]:
            raise InputError(f"{name}: use a {', '.join(w['formats'])} file")
        limit = int(w["max_upload_mb"]) * 1024 * 1024
        jid, d = jobs.new()
        dst, size = d / f"input{ext}", 0
        with open(dst, "wb") as f:
            while chunk := await file.read(1 << 20):
                size += len(chunk)
                if size > limit:
                    f.close()
                    shutil.rmtree(d, ignore_errors=True)
                    raise HTTPException(413, f"{name}: larger than {int(w['max_upload_mb'])} MB")
                f.write(chunk)
        return jobs.submit(jid, "decode", lambda progress: engine.run_decode(dst, key, name, d, progress))

    @api.post("/decode-job")
    def decode_job(req: DecodeJobRequest):
        engine.require()
        engine.check_key(req.key)
        kind, name = {"sent": ("send", "sent.wav"), "heard": ("sea", "heard.wav")}.get(req.file, (None, None))
        if kind is None:
            raise InputError("file must be 'sent' or 'heard'")
        result_of(req.job, kind)
        jid, d = jobs.new()
        dst = d / "input.wav"
        shutil.copyfile(folder(req.job) / name, dst)        # the decoder works on its own copy, and nothing else of that job
        key = req.key
        return jobs.submit(jid, "decode", lambda progress: engine.run_decode(dst, key, name, d, progress))

    @api.post("/check")
    def check_route(req: CheckRequest):
        return check(result_of(req.send, "send"), result_of(req.decode, "decode"))

    @api.get("/jobs/{jid}")
    def job(jid: str):
        j = jobs.jobs.get(jid)
        if j is None:
            raise HTTPException(404, "unknown job")
        return dict(j)

    @api.get("/files/{jid}/{name}")
    def file_route(jid: str, name: str):
        d = folder(jid)
        if not FILE_NAME.match(name) or name.startswith("input.") or not (d / name).is_file():
            raise HTTPException(404, "no such file")
        return FileResponse(d / name)

    app = FastAPI(title="WhistleCode", docs_url=None, redoc_url=None, openapi_url=None)
    started, version = time.monotonic(), project_version()

    @app.exception_handler(InputError)
    async def input_error(_, e: InputError):
        return JSONResponse({"detail": str(e)}, status_code=400)

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        """Docker's healthcheck and `python tools/repo.py health` (project/RELEASES.md, Monitoring) read this."""
        problem = engine.error or engine.warm_error
        body = {"status": "down" if problem else ("ok" if engine.warm else "starting"), "version": version,
                "uptime_s": round(time.monotonic() - started), "queue": jobs.q.qsize()}
        if problem:
            body["problem"] = problem
        return JSONResponse(body, status_code=503 if problem else 200)

    app.include_router(api)
    app.state.engine, app.state.jobs = engine, jobs
    if page is not None:
        app.mount("/", page)
    if warm and engine.error is None:
        threading.Thread(target=engine.warm_up, daemon=True, name="whistlecode-warm-up").start()
    return app


# ---------------------------------------------------------------------------------------------- serving to other computers
def lan_addresses() -> list[str]:
    """This computer's IPv4 addresses on its networks (no packet is sent)."""
    found = set()
    try:
        found.update(socket.gethostbyname_ex(socket.gethostname())[2])
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))            # chooses the outgoing interface; a UDP connect sends nothing
            found.add(s.getsockname()[0])
    except OSError:
        pass
    return sorted(a for a in found if not a.startswith("127."))


def tls_files(names: list[str], cfg: dict | None = None) -> tuple[Path, Path]:
    """(certificate, key) for https on these addresses and names, plus localhost. Made once and kept in web.tls_dir; made
    again when it no longer covers an address (a new network) or is about to expire. Self-signed, so browsers warn once."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    cfg = cfg or default_config()
    d = PROJECT_ROOT / cfg["web"]["tls_dir"]
    cert_p, key_p = d / "cert.pem", d / "key.pem"
    want = set(names) | {"127.0.0.1", "localhost"}
    now = datetime.datetime.now(datetime.timezone.utc)
    if cert_p.exists() and key_p.exists():
        c = x509.load_pem_x509_certificate(cert_p.read_bytes())
        san = c.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        have = {str(v) for v in san.get_values_for_type(x509.IPAddress)} | set(san.get_values_for_type(x509.DNSName))
        if want <= have and c.not_valid_after_utc > now + datetime.timedelta(days=7):
            return cert_p, key_p
    key = ec.generate_private_key(ec.SECP256R1())
    alt = []
    for n in sorted(want):
        try:
            alt.append(x509.IPAddress(ipaddress.ip_address(n)))
        except ValueError:
            alt.append(x509.DNSName(n))
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "WhistleCode on this computer")])
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=int(cfg["web"]["tls_days"])))
            .add_extension(x509.SubjectAlternativeName(alt), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(key, hashes.SHA256()))
    d.mkdir(parents=True, exist_ok=True)
    key_p.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    cert_p.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert_p, key_p


def serve(host: str | None = None, port: int | None = None, device: str | None = None, lan: bool = False) -> None:
    """The project page with Try it (the reproduction's app, unchanged) and the WhistleCode routes, on one port.
    lan=True: on every network of this computer, over https, so another computer can open the page and record with its
    microphone."""
    import uvicorn
    from whistlepipe.infer import Engine as PageEngine
    from whistlepipe.server import create_app as page_app

    page_engine = PageEngine(device=device)
    s = page_engine.icfg["server"]
    host, port = host or ("0.0.0.0" if lan else s["host"]), int(port or s["port"])
    engine = Engine()
    tls, addresses = {}, []
    if lan:
        addresses = lan_addresses()
        cert, key = tls_files(addresses, engine.cfg)
        tls = {"ssl_certfile": str(cert), "ssl_keyfile": str(key)}
    print(f"Try it  : {page_engine.model.status['message']}")
    print(f"messages: {'ready' if engine.error is None else engine.error}")
    if lan:
        print(f"serving web/, Try it and WhistleCode over https on port {port}  (Ctrl+C to stop)")
        print(f"  this computer   : https://localhost:{port}")
        for a in addresses:
            print(f"  other computers : https://{a}:{port}")
        print("  The browser warns once that the certificate is not trusted: it is this computer's own. Choose Advanced, then")
        print("  Proceed. If Windows asks whether Python may use the network, allow it for private networks only.")
        print("  Anyone on this network can open the page while it runs.")
    else:
        print(f"serving web/, Try it and WhistleCode on http://{host}:{port}  (Ctrl+C to stop)")
    uvicorn.run(create_app(engine, page_app(page_engine)), host=host, port=port, log_level="warning", **tls)
