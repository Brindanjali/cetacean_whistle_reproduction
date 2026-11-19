"""The rhythm bank (PLAN.md section 4.6): the real whistles of encounters 191 and 214, with their times, lengths and contours.

A message is played on top of a stretch of this bank, so its timing is a copy of real timing. The bank marks

- active stretches: runs of 44 s windows holding at least 10 whistles;
- start points: whistles that follow a real silence of at least 1 s, where a message may begin;
- whistles that can carry data: 100-450 ms long, with no other whistle starting from 60 ms before to 150 ms after.

Sender and receiver must hold the same bank. It is built from preprocessed/ once, cached in outputs/bank (gitignored) and
pinned by the SHA-256 in config.toml.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .config import PROJECT_ROOT, WhistleCodeError, default_config

ENCOUNTER_GAP_S = 3600.0            # the encounters are laid end to end on one time axis, this far apart


class BankError(WhistleCodeError):
    pass


@dataclass(frozen=True)
class Bank:
    on: np.ndarray                  # start of each whistle (s), increasing
    off: np.ndarray                 # end of each whistle (s)
    first: np.ndarray               # whistle i's contour is freq[first[i]:first[i + 1]]
    freq: np.ndarray                # absolute frequency per frame (Hz)
    run: np.ndarray                 # which active stretch the whistle belongs to
    eligible: np.ndarray            # can carry data
    silence_after: np.ndarray       # silence between the end of everything so far and the next whistle (s)
    starts: np.ndarray              # whistles that follow a real silence
    hop_s: float
    sha256: str

    def __len__(self) -> int:
        return len(self.on)

    def contour_hz(self, i: int) -> np.ndarray:
        return self.freq[self.first[i]:self.first[i + 1]].astype(np.float64)


def _file_time(stem: str) -> float:
    """Recording start from a file name such as 1705_20171009_231401_141 (UTC, so every machine gets the same bank)."""
    p = stem.split("_")
    t = datetime.strptime(p[1] + p[2], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc).timestamp()
    return t + int(p[3]) / 1000


def _digest(arrays: dict) -> str:
    h = hashlib.sha256()
    for name in sorted(arrays):
        a = np.asarray(arrays[name])
        if a.dtype.kind == "f" and a.dtype.itemsize == 8:
            a = np.round(a * 1e6).astype(np.int64)      # microseconds: independent of rounding in the last float bits
        h.update(name.encode("ascii"))
        h.update(str(a.shape).encode("ascii"))
        h.update(a.tobytes())
    return h.hexdigest()


def _one_encounter(encounter: int, c: dict) -> dict:
    z = np.load(PROJECT_ROOT / "preprocessed" / f"encounter_{int(encounter)}" / "contours.npz")
    hop = float(z["frame_s"])
    times = {s: _file_time(s) for s in np.unique(z["source_file"]).tolist()}
    t = np.array([times[s] for s in z["source_file"].tolist()]) + z["start_s"].astype(np.float64)
    order = np.argsort(t, kind="stable")
    on = t[order] - t[order[0]]
    n_frames = z["n_frames"][order].astype(np.int64)
    off = on + n_frames * hop
    offsets, freq = z["offsets"], z["freq_hz"]
    contours = [freq[offsets[i]:offsets[i + 1]] for i in order]

    reach = np.maximum.accumulate(off)
    silence = np.append(on[1:] - reach[:-1], np.inf)
    after_silence = np.insert(silence[:-1] >= float(c["min_silence_s"]), 0, True)

    lo, hi = c["data_length_s"]
    near = np.searchsorted(on, on + float(c["slot_late_s"]), "right") - np.searchsorted(on, on - float(c["slot_early_s"]), "left")
    eligible = (off - on >= float(lo)) & (off - on <= float(hi)) & (near == 1)

    win = float(c["window_s"])
    w = np.floor(on / win).astype(np.int64)
    counts = np.bincount(w)
    active = np.where((counts >= int(c["min_whistles"])) & ((np.arange(len(counts)) + 1) * win <= on[-1]))[0]
    run_of = np.full(len(counts), -1, dtype=np.int64)
    run_of[active] = np.cumsum(np.insert(np.diff(active) != 1, 0, True)) - 1
    run = run_of[w]
    keep = run >= 0
    return {"on": on[keep], "off": off[keep], "contours": [contours[i] for i in np.where(keep)[0]], "run": run[keep],
            "eligible": eligible[keep], "silence": silence[keep], "start": after_silence[keep], "hop": hop, "t0": float(t[order[0]])}


def build(cfg: dict | None = None) -> Bank:
    """Build the bank from preprocessed/ (a few seconds)."""
    cfg = cfg or default_config()
    c = cfg["bank"]
    parts, shift, run_shift = [], 0.0, 0
    for e in c["encounters"]:
        p = _one_encounter(int(e), c)
        p["on"] = p["on"] + shift
        p["off"] = p["off"] + shift
        p["run"] = p["run"] + run_shift
        shift = float(p["off"].max()) + ENCOUNTER_GAP_S
        run_shift = int(p["run"].max()) + 1
        parts.append(p)
    hops = {p["hop"] for p in parts}
    if len(hops) != 1:
        raise BankError(f"the encounters use different frame steps: {sorted(hops)}")
    contours = [f for p in parts for f in p["contours"]]
    arrays = {"on": np.concatenate([p["on"] for p in parts]), "off": np.concatenate([p["off"] for p in parts]),
              "first": np.cumsum([0] + [len(f) for f in contours], dtype=np.int64),
              "freq": np.concatenate(contours).astype(np.float32), "run": np.concatenate([p["run"] for p in parts]),
              "eligible": np.concatenate([p["eligible"] for p in parts]),
              "silence_after": np.concatenate([p["silence"] for p in parts]),
              "starts": np.where(np.concatenate([p["start"] for p in parts]))[0].astype(np.int64),
              "hop_s": np.array(hops.pop())}
    return _bank(arrays)


def time_base(cfg: dict | None = None) -> dict[int, tuple[float, float]]:
    """For each encounter: (recording time of its first whistle, where that whistle sits on the bank's time axis)."""
    cfg = cfg or default_config()
    out, shift = {}, 0.0
    for e in cfg["bank"]["encounters"]:
        p = _one_encounter(int(e), cfg["bank"])
        out[int(e)] = (float(p["t0"]), shift)
        shift = float(p["off"].max()) + shift + ENCOUNTER_GAP_S
    return out


def _bank(arrays: dict) -> Bank:
    a = dict(arrays)
    hop = float(a.pop("hop_s"))
    return Bank(hop_s=hop, sha256=_digest({**a, "hop_s": np.array(hop)}), **a)


def out_dir(cfg: dict | None = None) -> Path:
    return PROJECT_ROOT / (cfg or default_config())["bank"]["out_dir"]


def save(path: Path, b: Bank) -> None:
    path.mkdir(parents=True, exist_ok=True)
    np.savez(path / "bank.npz", on=b.on, off=b.off, first=b.first, freq=b.freq, run=b.run, eligible=b.eligible,
             silence_after=b.silence_after, starts=b.starts, hop_s=np.array(b.hop_s))
    (path / "bank.json").write_text(json.dumps({"sha256": b.sha256, "whistles": len(b), "can_carry_data": int(b.eligible.sum()),
                                                "start_points": len(b.starts), "active_stretches": int(b.run.max()) + 1}, indent=1),
                                    encoding="utf-8")


def load(cfg: dict | None = None) -> Bank:
    """The bank, built on first use, and refused if it is not the one config.toml pins."""
    cfg = cfg or default_config()
    path = out_dir(cfg) / "bank.npz"
    if path.exists():
        with np.load(path) as z:
            b = _bank({k: z[k] for k in z.files})
    else:
        b = build(cfg)
        save(path.parent, b)
    pin = str(cfg["bank"]["sha256"])
    if pin and pin != b.sha256:
        raise BankError(f"the rhythm bank is {b.sha256[:12]}... but config.toml pins {pin[:12]}...; "
                        "sender and receiver must use the same bank")
    return b
