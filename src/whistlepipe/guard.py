"""Limits that keep a server open to the internet up (project/AUDIT_2026-11-23.md, BUG-2, BUG-4 and BUG-13). Used by the
page's own server (server.py) and by WhistleCode's (whistlecode/wcode/web.py).

- read_channel: one channel of an audio file, read in blocks and never past a set number of frames. Reading every channel of
  the whole file at once let a 1.7 MB FLAC (8 channels, 655 kHz, 300 s of silence) decode to 6.3 GB.
- RequestLimit: an ASGI middleware that refuses a request body larger than its route allows while it arrives, before it is
  stored. Starlette writes a multipart upload to a temporary file before the route can look at its size, so a size check in
  the route alone comes too late. It also refuses an upload while `max_uploads` others are still arriving.
- JobFolders: a server's job folders, made and pruned oldest first. Ordering by name alone let a newer job go first (ids
  made in the same second differ only in their random suffix), and a folder whose upload was still being copied, not yet a
  job, could be deleted by a job submitted meanwhile.
"""
from __future__ import annotations

import json
import re
import shutil
import threading
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from fastapi import HTTPException

BLOCK_SAMPLES = 1 << 22                 # samples per block, over all channels (16 MB of float32)


class TooLong(ValueError):
    """The file holds more frames than allowed (its header may have said otherwise)."""


def read_channel(path: str | Path, channel: int, max_frames: int, block_samples: int = BLOCK_SAMPLES) -> np.ndarray:
    """Channel `channel` of an audio file as float32, at most `max_frames` frames; TooLong if the file holds more.
    Memory: one block of all channels, plus the channel kept."""
    parts, n = [], 0
    with sf.SoundFile(str(path)) as f:
        if not 0 <= channel < f.channels:
            raise ValueError(f"channel {channel} requested, the file has {f.channels}")
        block = max(1, block_samples // f.channels)
        for blk in f.blocks(blocksize=block, dtype="float32", always_2d=True, frames=int(max_frames) + 1):
            parts.append(blk[:, channel].copy())
            n += len(blk)
    if n > max_frames:
        raise TooLong(f"more than {max_frames} frames")
    return np.concatenate(parts) if parts else np.zeros(0, dtype=np.float32)


class RequestLimit:
    """ASGI middleware. For requests with a body (not GET, HEAD, OPTIONS) whose path starts with `prefix`:

    - a route in `uploads` ({path: bytes}) may receive up to its own limit, and at most `max_uploads` such requests may arrive
      at once (503 beyond that);
    - every other route may receive up to `max_body` bytes;
    - a larger body is refused with 413: at once when its Content-Length says so, otherwise as soon as the bytes that arrived
      pass the limit, so nothing larger is ever stored."""

    def __init__(self, app, uploads: dict[str, int], max_body: int, max_uploads: int, prefix: str = "/"):
        self.app, self.uploads, self.max_body, self.max_uploads, self.prefix = app, dict(uploads), int(max_body), int(max_uploads), prefix
        self.arriving = 0                                # uploads in progress (one event loop, so no lock is needed)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            return await self.app(scope, receive, send)
        path, root = scope["path"], scope.get("root_path", "")
        if root and path.startswith(root):
            path = path[len(root):] or "/"
        if not path.startswith(self.prefix):
            return await self.app(scope, receive, send)
        upload = path in self.uploads
        limit = self.uploads[path] if upload else self.max_body
        too_big = f"the request is larger than {_size(limit)}"
        try:
            declared = int(dict(scope["headers"]).get(b"content-length", b"-1"))
        except ValueError:
            declared = -1
        if declared > limit:
            return await _refuse(send, 413, too_big)
        if upload and self.arriving >= self.max_uploads:
            return await _refuse(send, 503, "the server is receiving other uploads; try again in a minute")
        seen, started = 0, False

        async def counted():
            nonlocal seen
            msg = await receive()
            if msg["type"] == "http.request":
                seen += len(msg.get("body", b""))
                if seen > limit:
                    raise HTTPException(413, too_big)    # FastAPI passes an HTTPException from body reading through as it is
            return msg

        async def watched(msg):
            nonlocal started
            started = started or msg["type"] == "http.response.start"
            await send(msg)

        if upload:
            self.arriving += 1
        try:
            await self.app(scope, counted, watched)
        except HTTPException as e:                       # only if no handler inside answered it
            if started or e.status_code != 413:
                raise
            await _refuse(send, 413, too_big)
        finally:
            if upload:
                self.arriving -= 1


def _size(n: int) -> str:
    return f"{n / 2 ** 20:.0f} MB" if n >= 2 ** 20 else f"{n / 1024:.0f} kB"


async def _refuse(send, status: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode("utf-8")
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()),
                            (b"connection", b"close")]})
    await send({"type": "http.response.body", "body": body})


STAMP = re.compile(r"\d{8}T\d{6}Z")      # the UTC time in every job id


class JobFolders:
    """The job folders under `root` whose names match `pattern`; the newest `keep` are kept.

    Oldest first: folders from earlier server runs, by the time in their names, then the folders this server made, in the
    order it made them. A folder this server made that is not a job yet (its upload is still being copied) is kept for
    `grace_s` seconds; after that a failed request's leftover folder is pruned like any other."""

    def __init__(self, root: str | Path, keep: int, pattern: re.Pattern, grace_s: float = 600.0):
        self.root, self.keep, self.pattern, self.grace_s = Path(root), int(keep), pattern, float(grace_s)
        self.root.mkdir(parents=True, exist_ok=True)
        self.made: dict[str, float] = {}            # id -> when this server made it, oldest first
        self.lock = threading.Lock()                # routes make folders and submit jobs on several threads

    def make(self, jid: str) -> Path:
        """Create the folder for job id `jid` (FileExistsError if it exists) and note when it was made."""
        d = self.root / jid
        with self.lock:
            d.mkdir(parents=True)
            self.made[jid] = time.monotonic()
        return d

    def prune(self, state_of) -> list[str]:
        """Delete the oldest folders beyond `keep` and return their ids. `state_of(id)` is the job's state, or None for a
        folder that is not a job; queued and running jobs are kept, and so are folders made in the last grace_s seconds
        that are not jobs yet."""
        gone, now = [], time.monotonic()
        with self.lock:
            dirs = [p for p in self.root.iterdir() if p.is_dir() and self.pattern.match(p.name)]
            for jid in set(self.made) - {p.name for p in dirs}:       # removed by their own request (a refused upload)
                del self.made[jid]
            order = {jid: k for k, jid in enumerate(self.made)}

            def age(p: Path) -> tuple:
                m = STAMP.search(p.name)
                return (p.name in order, order.get(p.name, 0), m.group(0) if m else "", p.name)

            dirs.sort(key=age)
            for p in dirs[:-self.keep] if len(dirs) > self.keep else []:
                state = state_of(p.name)
                if state in ("queued", "running"):
                    continue
                if state is None and now - self.made.get(p.name, -float("inf")) < self.grace_s:
                    continue                                          # its upload is still arriving
                shutil.rmtree(p, ignore_errors=True)
                self.made.pop(p.name, None)
                gone.append(p.name)
        return gone
