"""Limits that keep a server open to the internet up (project/AUDIT_2026-11-23.md, BUG-2 and BUG-4). Used by the page's own
server (server.py) and by WhistleCode's (whistlecode/wcode/web.py).

- read_channel: one channel of an audio file, read in blocks and never past a set number of frames. Reading every channel of
  the whole file at once let a 1.7 MB FLAC (8 channels, 655 kHz, 300 s of silence) decode to 6.3 GB.
- RequestLimit: an ASGI middleware that refuses a request body larger than its route allows while it arrives, before it is
  stored. Starlette writes a multipart upload to a temporary file before the route can look at its size, so a size check in
  the route alone comes too late. It also refuses an upload while `max_uploads` others are still arriving.
"""
from __future__ import annotations

import json
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
