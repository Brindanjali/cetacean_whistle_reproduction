"""The web API: upload -> job -> result files, generation, examples, file serving (incl. HTTP Range for the videos)."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from test_infer import RUN, make_engine, synthetic_recording  # noqa: E402  (tests/ is on sys.path under pytest)
from whistlepipe.server import create_app


def wait(client, jid, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = client.get(f"/api/jobs/{jid}").json()
        if j["state"] in ("done", "error"):
            return j
        time.sleep(0.1)
    raise TimeoutError(jid)


@pytest.fixture()
def web(tmp_path):
    d = tmp_path / "web"
    (d / "data" / "ex").mkdir(parents=True)
    (d / "index.html").write_text("<!doctype html><title>t</title>", encoding="utf-8")
    (d / "clip.bin").write_bytes(bytes(range(256)) * 40)
    synthetic_recording(d / "data" / "ex" / "one.flac", fs=96000)
    (d / "data" / "examples.json").write_text(json.dumps({"examples": [{"id": "one", "audio": "data/ex/one.flac"}]}))
    return d


def client_for(tmp_path, web, **model):
    eng = make_engine(tmp_path, **model)
    eng.icfg["output"]["out_dir"] = str(tmp_path / "jobs")
    return TestClient(create_app(eng, web_dir=web, keep_jobs=3))


def test_status_and_page(tmp_path, web):
    c = client_for(tmp_path, web)
    s = c.get("/api/status").json()
    assert s["model"]["ready"]["recreate"] is False and s["examples"] == 1 and len(s["conditions"]) == 13
    assert c.get("/").status_code == 200 and "<title>t</title>" in c.get("/").text
    r = c.get("/clip.bin", headers={"Range": "bytes=10-19"})          # videos need byte ranges to seek
    assert r.status_code == 206 and r.content == bytes(range(10, 20))
    # the page's code is re-checked on every load (an edited lab.js shows after a plain reload); media keeps default caching
    assert c.get("/").headers.get("cache-control") == "no-cache" and c.get("/index.html").headers.get("cache-control") == "no-cache"
    assert "cache-control" not in c.get("/clip.bin").headers


def test_upload_to_results_without_model(tmp_path, web):
    c = client_for(tmp_path, web)
    p = synthetic_recording(tmp_path / "up.wav", fs=48000)
    with open(p, "rb") as f:
        jid = c.post("/api/analyze", files={"file": ("my recording.wav", f, "audio/wav")}, data={"seed": "3"}).json()["job"]
    j = wait(c, jid)
    assert j["state"] == "done", j
    res = c.get(j["result"]).json()
    assert res["input"]["name"] == "my recording.wav" and len(res["whistles"]) == 4
    w = res["whistles"][0]
    for name in (w["input"]["png"], w["input"]["sound"]["wav"], w["recording"]["wav"], res["overview"]["png"]):
        r = c.get(f"/api/results/{jid}/{name}")
        assert r.status_code == 200 and len(r.content) > 100
    z = c.get(f"/api/results/{jid}.zip")
    assert z.status_code == 200 and z.headers["content-type"] == "application/zip"
    assert c.post("/api/generate", json={"n": 2}).status_code == 409         # no model: refused up front


def test_upload_errors(tmp_path, web):
    c = client_for(tmp_path, web)
    assert c.post("/api/analyze", files={"file": ("x.txt", b"hello")}).status_code == 400
    jid = c.post("/api/analyze", files={"file": ("x.wav", b"not audio")}).json()["job"]
    j = wait(c, jid)
    assert j["state"] == "error" and "readable" in j["error"]
    assert c.get("/api/results/../../etc/passwd").status_code == 404
    assert c.get(f"/api/results/{jid}/..%2Fresult.json").status_code == 404
    assert c.get("/api/jobs/nope").status_code == 404


def test_example_and_generation_with_random_model(tmp_path, web):
    c = client_for(tmp_path, web, gmm=True, comp_feats=True)
    assert c.get("/api/status").json()["model"]["ready"]["generate"]
    j = wait(c, c.post("/api/analyze-example", json={"example": "one", "n_samples": 2}).json()["job"])
    res = c.get(j["result"]).json()
    assert res["samples_method"] == "gmm" and all(len(w["samples"]) == 2 for w in res["whistles"])
    g = wait(c, c.post("/api/generate", json={"n": 3, "seed": 2}).json()["job"])
    gr = c.get(g["result"]).json()
    assert gr["kind"] == "generation" and gr["n"] == 3
    bad = wait(c, c.post("/api/generate", json={"n": 2, "condition": 1}).json()["job"])
    assert bad["state"] == "error" and bad["error"]
    assert c.post("/api/analyze-example", json={"example": "zzz"}).status_code == 404


def test_reload_picks_up_dropped_in_files(tmp_path, web):
    c = client_for(tmp_path, web)
    assert c.get("/api/status").json()["model"]["ready"]["recreate"] is False
    from test_infer import write_random_model

    write_random_model(tmp_path / "runs", gmm=False)
    r = c.post("/api/reload-model")                                    # off by default: anyone on the page could call it
    assert r.status_code == 403 and "allow_reload" in r.json()["detail"]
    c.app.state.engine.icfg["server"]["allow_reload"] = True
    st = c.post("/api/reload-model").json()
    assert st["ready"]["recreate"] is True and st["run_id"] == RUN


def test_limits_for_a_public_page(tmp_path, web):
    """BUG-3: n_samples is clamped on every route; BUG-4: request sizes, the queue, and uploads deleted after their job."""
    eng = make_engine(tmp_path, gmm=True)
    eng.icfg["output"]["out_dir"] = str(tmp_path / "jobs")
    eng.icfg["output"]["n_samples"] = 1                                # so the cap is 2
    c = TestClient(create_app(eng, web_dir=web, keep_jobs=5))
    for asked, got in ((1000, 2), (-5, 0)):
        j = wait(c, c.post("/api/analyze-example", json={"example": "one", "n_samples": asked}).json()["job"])
        res = c.get(j["result"]).json()
        assert res["n_samples"] == got and all(len(w.get("samples", [])) == got for w in res["whistles"])
    p = synthetic_recording(tmp_path / "up.wav", fs=48000, dur=1.0)
    with open(p, "rb") as f:
        jid = c.post("/api/analyze", files={"file": ("up.wav", f)}, data={"n_samples": "99"}).json()["job"]
    assert wait(c, jid)["state"] == "done" and c.get(f"/api/results/{jid}/result.json").json()["n_samples"] == 2
    assert not list((tmp_path / "jobs" / jid).glob("input.*"))         # the upload is gone once its job has ended
    r = c.post("/api/generate", json={"n": 2, "pad": "x" * 70_000})     # over max_request_kb
    assert r.status_code == 413 and "larger than" in r.json()["detail"]
    n_jobs = len(list((tmp_path / "jobs").iterdir()))
    c.app.state.jobs.max_queued = 0                                    # as if the queue were full
    for r in (c.post("/api/generate", json={"n": 2}), c.post("/api/analyze-example", json={"example": "one"}),
              c.post("/api/analyze", files={"file": ("up.wav", p.read_bytes())})):
        assert r.status_code == 503 and "busy" in r.json()["detail"]
    assert len(list((tmp_path / "jobs").iterdir())) == n_jobs           # nothing stored for a refused request


def test_old_job_folders_are_pruned(tmp_path, web):
    c = client_for(tmp_path, web)
    p = synthetic_recording(tmp_path / "s.wav", fs=48000, dur=1.0)
    ids = []
    for _ in range(5):
        with open(p, "rb") as f:
            ids.append(c.post("/api/analyze", files={"file": ("s.wav", f)}).json()["job"])
        wait(c, ids[-1])
    left = sorted(d.name for d in (tmp_path / "jobs").iterdir())
    assert len(left) <= 4 and ids[-1] in left and ids[0] not in left


def test_requests_choose_the_model(tmp_path, web):
    from test_infer import make_two_model_engine

    eng = make_two_model_engine(tmp_path)
    eng.icfg["output"]["out_dir"] = str(tmp_path / "jobs")
    c = TestClient(create_app(eng, web_dir=web, keep_jobs=5))
    s = c.get("/api/status").json()
    assert s["default_model"] == "first" and [m["id"] for m in s["models"]] == ["first", "second"]
    j = wait(c, c.post("/api/analyze-example", json={"example": "one", "n_samples": 1, "model": "second"}).json()["job"])
    res = c.get(j["result"]).json()
    assert res["model"]["id"] == "second" and res["samples_method"] == "encoder_posterior"
    p = synthetic_recording(tmp_path / "up.wav", fs=48000, dur=1.0)
    with open(p, "rb") as f:
        up = wait(c, c.post("/api/analyze", files={"file": ("up.wav", f)}, data={"model": "second"}).json()["job"])
    assert c.get(up["result"]).json()["model"]["id"] == "second"
    assert c.post("/api/generate", json={"n": 2, "model": "second"}).status_code == 409    # no GMM: refused up front
    g = wait(c, c.post("/api/generate", json={"n": 2, "model": "first"}).json()["job"])
    assert c.get(g["result"]).json()["model"]["id"] == "first"
    n_jobs = len(list((tmp_path / "jobs").iterdir()))
    for r in (c.post("/api/generate", json={"n": 2, "model": "third"}),
              c.post("/api/analyze-example", json={"example": "one", "model": "third"}),
              c.post("/api/analyze", files={"file": ("up.wav", b"x")}, data={"model": "third"})):
        assert r.status_code == 400 and "no model 'third'" in r.json()["detail"]
    assert len(list((tmp_path / "jobs").iterdir())) == n_jobs                # nothing stored for a refused request
