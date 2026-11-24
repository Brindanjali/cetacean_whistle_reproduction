"""Limits for a server open to the internet (src/whistlepipe/guard.py; project/AUDIT_2026-11-23.md, BUG-2, BUG-4, BUG-13)."""
import asyncio
import re

import numpy as np
import pytest
import soundfile as sf
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from whistlepipe.guard import JobFolders, RequestLimit, TooLong, read_channel


# ---------------------------------------------------------------------------------------------- reading one channel
def test_read_channel_keeps_one_channel_in_blocks(tmp_path):
    x = np.stack([np.full(10_000, 0.1), np.full(10_000, 0.2), np.linspace(-0.5, 0.5, 10_000)], axis=1).astype(np.float32)
    sf.write(str(tmp_path / "three.wav"), x, 48000, subtype="FLOAT")
    y = read_channel(tmp_path / "three.wav", 2, 10_000, block_samples=3 * 777)       # many small blocks
    assert y.dtype == np.float32 and y.shape == (10_000,) and np.array_equal(y, x[:, 2])
    with pytest.raises(TooLong):                          # never reads past the limit, whatever the header says
        read_channel(tmp_path / "three.wav", 0, 9_999)
    with pytest.raises(ValueError, match="channel 3"):
        read_channel(tmp_path / "three.wav", 3, 10_000)


# ---------------------------------------------------------------------------------------------- request sizes
def _app(seen: list):
    app = FastAPI()

    @app.post("/api/small")
    async def small(request: Request):
        body = await request.body()
        seen.append(len(body))
        return {"n": len(body)}

    @app.post("/api/upload")
    async def upload(request: Request):
        body = await request.body()
        seen.append(len(body))
        return {"n": len(body)}

    @app.post("/other")
    async def other(request: Request):
        return {"n": len(await request.body())}

    app.add_middleware(RequestLimit, uploads={"/api/upload": 5000}, max_body=100, max_uploads=1, prefix="/api/")
    return app


def test_bodies_over_their_route_limit_are_refused_before_the_route_runs():
    seen = []
    c = TestClient(_app(seen))
    assert c.post("/api/small", content=b"x" * 100).json() == {"n": 100}
    r = c.post("/api/small", content=b"x" * 101)
    assert r.status_code == 413 and "larger than" in r.json()["detail"]
    assert c.post("/api/upload", content=b"x" * 5000).json() == {"n": 5000}
    assert c.post("/api/upload", content=b"x" * 5001).status_code == 413
    assert c.get("/api/small").status_code == 405                    # GET passes through untouched
    assert c.post("/other", content=b"x" * 1000).json() == {"n": 1000}  # outside the prefix: not limited
    assert seen == [100, 5000]                                       # the refused bodies never reached a route


def _call(app, path: str, chunks: list[bytes], headers=()) -> tuple[int, bytes]:
    """One request straight through the ASGI app, its body in chunks (as a client that sends no Content-Length)."""
    msgs = [{"type": "http.request", "body": b, "more_body": i < len(chunks) - 1} for i, b in enumerate(chunks)]
    out = []

    async def receive():
        return msgs.pop(0) if msgs else {"type": "http.disconnect"}

    async def send(m):
        out.append(m)

    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST", "scheme": "http",
             "path": path, "raw_path": path.encode(), "root_path": "", "query_string": b"", "headers": list(headers),
             "client": ("1.2.3.4", 5), "server": ("test", 80)}
    asyncio.run(app(scope, receive, send))
    start = next(m for m in out if m["type"] == "http.response.start")
    return start["status"], b"".join(m.get("body", b"") for m in out if m["type"] == "http.response.body")


def test_a_body_without_its_length_is_cut_off_once_it_passes_the_limit():
    seen = []
    app = _app(seen)
    status, body = _call(app, "/api/small", [b"x" * 40] * 2)
    assert status == 200 and seen == [80]
    status, body = _call(app, "/api/small", [b"x" * 40] * 50)        # 2 kB arrive, the limit is 100 bytes
    assert status == 413 and b"larger than" in body and seen == [80]


def test_uploads_at_once_are_limited():
    seen = []
    app = _app(seen)
    TestClient(app).post("/api/upload", content=b"x")                # builds the middleware stack
    guard = app.middleware_stack
    while not isinstance(guard, RequestLimit):
        guard = guard.app
    guard.arriving = 1                                               # one upload still arriving
    status, body = _call(app, "/api/upload", [b"x" * 10])
    assert status == 503 and b"other uploads" in body
    status, _ = _call(app, "/api/small", [b"x" * 10])                # ordinary requests are not held up
    assert status == 200
    guard.arriving = 0
    assert _call(app, "/api/upload", [b"x" * 10])[0] == 200 and guard.arriving == 0


# ---------------------------------------------------------------------------------------------- job folders (BUG-13)
ID = re.compile(r"^(gen_)?\d{8}T\d{6}Z_[0-9a-f]{6}$")


def _left(f: JobFolders) -> list[str]:
    return sorted(p.name for p in f.root.iterdir())


def test_job_folders_go_in_the_order_they_were_made(tmp_path):
    """Two ids from the same second differ only in their random suffix: the one made first goes first, whatever its name."""
    f = JobFolders(tmp_path, keep=2, pattern=ID)
    older = tmp_path / "20260101T000000Z_aaaaaa"            # left by an earlier run of the server: goes before this run's
    older.mkdir()
    ids = ["20260102T000000Z_ffffff", "20260102T000000Z_000000", "gen_20260102T000000Z_777777"]
    for jid in ids:
        f.make(jid)
    assert f.prune(lambda j: "done") == [older.name, ids[0]] and _left(f) == sorted(ids[1:])
    assert f.prune(lambda j: "done") == []                  # nothing beyond keep
    (tmp_path / "notes").mkdir()                            # not a job folder: never touched
    assert f.prune(lambda j: "done") == [] and (tmp_path / "notes").is_dir()


def test_job_folders_still_needed_are_kept(tmp_path):
    f = JobFolders(tmp_path, keep=1, pattern=ID)
    arriving, queued, done, newest = (f"20260102T00000{k}Z_abcdef" for k in range(4))
    for jid in (arriving, queued, done, newest):
        f.make(jid)
    state = {queued: "queued", done: "done", newest: "done"}          # `arriving` is not a job yet: its upload is copying
    assert f.prune(state.get) == [done] and _left(f) == [arriving, queued, newest]
    state[queued] = "error"
    f.grace_s = 0                                           # a failed request's leftover folder goes once grace_s has passed
    assert f.prune(state.get) == [arriving, queued] and _left(f) == [newest]
    gone = f.make("20260102T000004Z_abcdef")
    gone.rmdir()                                            # removed by its own request (a refused upload)
    f.prune(state.get)
    assert gone.name not in f.made
    with pytest.raises(FileExistsError):
        f.make(newest)

