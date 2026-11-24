"""Web demo server: the page (web/) plus the inference API.     python whistle.py serve  ->  http://127.0.0.1:8000

    GET  /api/status                    model files present/loaded (models: every model on offer), limits, Table 3 conditions
    POST /api/reload-model              re-read the trained files (after dropping them into place); off unless
                                        configs/inference.toml [server] allow_reload = true (403 otherwise)
    POST /api/analyze                   multipart upload (file, channel, n_samples, seed, model) -> {"job": id}
    POST /api/analyze-example           {"example": id, "seed": 0, "model": null}  (web/data/examples.json) -> {"job": id}
    POST /api/generate                  {"n": 8, "seed": 0, "condition": null, "fc_hz": null, "model": null} -> {"job": id}
    GET  /api/jobs/{id}                 state, stage, progress, error, result URL
    GET  /api/results/{id}/{file}       result.json, PNG, WAV of a finished job
    GET  /api/results/{id}.zip          everything of a job in one file (neither route serves its input or error.txt)
    GET  /                              the page itself (web/, with HTTP Range for the videos)

``model`` is an id from configs/inference.toml [[models]] (null or absent: the first, the default); an unknown id is a 400.
Jobs run one at a time on a single worker thread (the GPU holds the models). Each job writes runs/infer/<id>/;
the newest ``keep_jobs`` job folders are kept. A job that fails inside the code saves its traceback as error.txt in its
folder, for whoever runs the server; it is never served. Binds to 127.0.0.1 by default (configs/inference.toml [server]).

Limits, because the page may be open to the internet ([server], [input]; project/AUDIT_2026-11-23.md): a request body is
refused (413) as it arrives once it passes the upload size (/api/analyze) or max_request_kb (every other route); at most
max_uploads_at_once uploads arrive at a time and max_queued jobs wait (503 beyond either); n_samples is clamped to
0-2 x output.n_samples; an upload's input file is deleted when its job ends (it is never served back).
"""
from __future__ import annotations

import io
import json
import queue
import re
import shutil
import threading
import traceback
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .audio import InputError
from .config import PROJECT_ROOT
from .guard import JobFolders, RequestLimit
from .infer import Engine, new_job_id, resolve

JOB_ID = re.compile(r"^(gen_)?\d{8}T\d{6}Z_[0-9a-f]{6}$")
FILE_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
WEB_DIR = PROJECT_ROOT / "web"


def private(name: str) -> bool:
    """A job's files that are never served: the upload (deleted when its job ends) and the traceback (BUG-7)."""
    return name.startswith("input.") or name == "error.txt"


class GenerateRequest(BaseModel):
    n: int = 8
    seed: int = 0
    condition: int | None = None
    fc_hz: float | None = None
    model: str | None = None


class ExampleRequest(BaseModel):
    example: str
    seed: int = 0
    n_samples: int | None = None
    model: str | None = None


class Jobs:
    def __init__(self, engine: Engine, out_root: Path, keep_jobs: int = 200, max_queued: int = 6):
        self.engine, self.out_root, self.max_queued = engine, out_root, max_queued
        self.folders = JobFolders(out_root, keep_jobs, JOB_ID)     # pruned oldest first (BUG-13)
        self.jobs: dict[str, dict] = {}
        self.q: queue.Queue = queue.Queue()
        threading.Thread(target=self._work, daemon=True, name="inference-worker").start()

    def room(self) -> None:
        """Refuse a new job (503) while max_queued jobs are already waiting; call it before storing anything."""
        if self.q.qsize() >= self.max_queued:
            raise HTTPException(503, f"the server is busy: {self.q.qsize()} jobs are waiting; try again in a minute")

    def folder(self, kind: str) -> tuple[str, Path]:
        jid = ("gen_" if kind == "generate" else "") + new_job_id()
        return jid, self.folders.make(jid)

    def submit(self, jid: str, kind: str, fn) -> dict:
        self.jobs[jid] = {"id": jid, "kind": kind, "state": "queued", "stage": None, "frac": None, "error": None}
        self.q.put((jid, fn))
        self._prune()
        return {"job": jid, "position": self.q.qsize()}

    def _work(self):
        while True:
            jid, fn = self.q.get()
            job = self.jobs[jid]
            job["state"] = "running"

            def progress(stage, frac=None):
                job["stage"], job["frac"] = stage, frac  # noqa: B023 -- runs during this job only

            try:
                with self.engine.lock:
                    fn(progress)
                job.update(state="done", result=f"/api/results/{jid}/result.json")
            except InputError as e:
                job.update(state="error", error=str(e))
            except Exception as e:  # noqa: BLE001  (shown as an internal error; the traceback goes to the job folder)
                (self.out_root / jid / "error.txt").write_text(traceback.format_exc(), encoding="utf-8")
                job.update(state="error", error=f"internal error ({type(e).__name__}); the details are saved on the server")
            finally:
                for p in (self.out_root / jid).glob("input.*"):     # the upload is never served back: free its space now
                    p.unlink(missing_ok=True)

    def _prune(self):
        for jid in self.folders.prune(lambda j: self.jobs.get(j, {}).get("state")):
            self.jobs.pop(jid, None)


def create_app(engine: Engine | None = None, web_dir: Path = WEB_DIR, keep_jobs: int = 200) -> FastAPI:
    engine = engine or Engine()
    icfg = engine.icfg
    srv = icfg["server"]
    out_root = resolve(icfg["output"]["out_dir"])
    out_root.mkdir(parents=True, exist_ok=True)
    jobs = Jobs(engine, out_root, keep_jobs, int(srv.get("max_queued", 6)))
    app = FastAPI(title="Whistle VAE-GMM", docs_url="/api/docs", openapi_url="/api/openapi.json")
    app.state.engine, app.state.jobs = engine, jobs
    upload_limit = int(icfg["input"]["max_upload_mb"]) * 1024 * 1024
    app.add_middleware(RequestLimit, uploads={"/api/analyze": upload_limit + 64 * 1024},     # + the multipart envelope
                       max_body=int(srv.get("max_request_kb", 64)) * 1024, max_uploads=int(srv.get("max_uploads_at_once", 2)),
                       prefix="/api/")

    def n_samples_ok(n: int | None) -> int | None:
        """New whistles per detected whistle: 0 to twice the default (BUG-3), or None for the default."""
        return None if n is None else max(0, min(int(icfg["output"]["n_samples"]) * 2, int(n)))

    @app.middleware("http")
    async def revalidate_page_code(request, call_next):
        """The page's own code (HTML, JS, CSS) is checked with the server on every load (a 304 when unchanged). Without a
        Cache-Control header the browser may reuse an old copy for hours, and Chrome's ordinary reload re-checks only the
        page itself, so an updated lab.js or styles.css would not show. Media and results keep the default caching."""
        response = await call_next(request)
        p = request.url.path
        if (p.endswith((".html", ".js", ".css")) or p.endswith("/")) and not p.startswith("/api/"):
            response.headers.setdefault("Cache-Control", "no-cache")
        return response

    def examples() -> dict:
        p = web_dir / "data" / "examples.json"
        return {e["id"]: e for e in json.loads(p.read_text(encoding="utf-8"))["examples"]} if p.exists() else {}

    @app.get("/api/status")
    def status():
        return {**engine.status(), "queue": jobs.q.qsize(), "examples": len(examples())}

    @app.post("/api/reload-model")
    def reload_model():
        if not bool(icfg["server"].get("allow_reload", False)):
            raise HTTPException(403, "reloading is switched off on this server (configs/inference.toml [server] allow_reload); "
                                     "restart it to pick up new model files")
        return engine.reload_model()

    @app.post("/api/analyze")
    async def analyze(file: UploadFile = File(...), channel: int | None = Form(None), n_samples: int | None = Form(None),
                      seed: int = Form(0), model: str | None = Form(None)):
        engine.get_model(model)                     # an unknown model is refused before the upload is stored
        name = Path(file.filename or "upload").name[:120]
        ext = Path(name).suffix.lower()
        if ext not in icfg["input"]["formats"]:
            raise HTTPException(400, f"{name}: unsupported file type (use {', '.join(icfg['input']['formats'])})")
        jobs.room()
        limit = int(icfg["input"]["max_upload_mb"]) * 1024 * 1024
        jid, d = jobs.folder("analyze")
        dst, size = d / f"input{ext}", 0
        with open(dst, "wb") as f:
            while chunk := await file.read(1 << 20):
                size += len(chunk)
                if size > limit:
                    f.close()
                    shutil.rmtree(d, ignore_errors=True)
                    raise HTTPException(413, f"{name}: larger than {icfg['input']['max_upload_mb']} MB")
                f.write(chunk)
        ns = n_samples_ok(n_samples)
        return jobs.submit(jid, "analyze", lambda progress: engine.analyze(dst, d, channel, ns, seed, name, progress, model))

    @app.post("/api/analyze-example")
    def analyze_example(req: ExampleRequest):
        ex = examples().get(req.example)
        if ex is None:
            raise HTTPException(404, f"no example {req.example!r}")
        engine.get_model(req.model)
        jobs.room()
        src, ns = web_dir / ex["audio"], n_samples_ok(req.n_samples)
        jid, d = jobs.folder("analyze")
        return jobs.submit(jid, "analyze", lambda progress: engine.analyze(src, d, None, ns, req.seed,
                                                                           Path(ex["audio"]).name, progress, req.model))

    @app.post("/api/generate")
    def generate(req: GenerateRequest):
        st = engine.get_model(req.model).status
        if not st["ready"]["generate"]:
            raise HTTPException(409, st["message"])
        jobs.room()
        jid, d = jobs.folder("generate")
        return jobs.submit(jid, "generate", lambda progress: engine.generate(d, req.n, req.seed, req.condition, req.fc_hz, progress,
                                                                             req.model))

    @app.get("/api/jobs/{jid}")
    def job(jid: str):
        j = jobs.jobs.get(jid)
        if j is None:
            raise HTTPException(404, "unknown job")
        return {k: v for k, v in j.items()}

    def job_dir(jid: str) -> Path:
        d = out_root / jid
        if not JOB_ID.match(jid) or not d.is_dir():
            raise HTTPException(404, "unknown job")
        return d

    @app.get("/api/results/{jid}.zip")
    def results_zip(jid: str):
        d = job_dir(jid)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(d.iterdir()):
                if p.is_file() and not private(p.name):
                    z.write(p, f"{jid}/{p.name}")
        return Response(buf.getvalue(), media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{jid}.zip"'})

    @app.get("/api/results/{jid}/{name}")
    def result_file(jid: str, name: str):
        d = job_dir(jid)
        if not FILE_NAME.match(name) or private(name) or not (d / name).is_file():
            raise HTTPException(404, "no such file")
        return FileResponse(d / name)

    @app.exception_handler(InputError)
    async def input_error(_, e: InputError):
        return JSONResponse({"detail": str(e)}, status_code=400)

    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return app


def serve(host: str | None = None, port: int | None = None, device: str | None = None) -> None:
    import uvicorn

    engine = Engine(device=device)
    s = engine.icfg["server"]
    host, port = host or s["host"], int(port or s["port"])
    for m in engine.models.values():
        print(f"model {m.status['id']} ({m.status['name']}): {m.status['message']}")
    print(f"serving web/ and the API on http://{host}:{port}  (Ctrl+C to stop)")
    uvicorn.run(create_app(engine), host=host, port=port, log_level="warning")
