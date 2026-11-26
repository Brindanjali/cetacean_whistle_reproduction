"""Encode and Decode on the project page (wcode/web.py)."""
import json
import time

import numpy as np
import pytest
import soundfile as sf
from PIL import Image

from wcode import codebook, format2, web

KEY = "reef42"


# ---------------------------------------------------------------------------------------------- encoding, step by step
@pytest.mark.parametrize("text", ["HI", "MEET AT DAWN", "meet at dawn", "Grüße!", "A" * 140])
def test_explain_gives_the_frame_encode_gives(cfg, text):
    ex = format2.explain(text, KEY, 77, cfg)
    fr = format2.encode(text, KEY, 77, cfg)
    assert np.array_equal(ex.frame.symbols, fr.symbols)
    # every data symbol is played exactly once, and every other payload whistle is parity
    data = [k for _, _, k in ex.payload_source if k is not None]
    assert sorted(data) == list(range(len(ex.plain)))
    assert len(ex.payload_source) - len(data) == sum(p for _, p in ex.blocks)
    assert len(ex.payload_source) == len(fr.payload_symbols)
    # the plain symbols hold the message bits, the CRC and the padding
    bits = format2.to_bits(ex.plain, 6)
    assert np.array_equal(bits[:len(ex.message_bits)], ex.message_bits)
    assert int(format2.from_bits(bits[len(ex.message_bits):len(ex.message_bits) + 16], 16)[0]) == ex.crc
    assert not bits[len(bits) - ex.pad_bits:].any()


# ---------------------------------------------------------------------------------------------- audio for the page
def test_picture_puts_a_tone_where_it_belongs(cfg, tmp_path):
    fs = 96000
    x = np.zeros(2 * fs, dtype=np.float32)
    t = np.arange(fs // 2) / fs
    x[fs // 2:fs] = 0.1 * np.sin(2 * np.pi * 8000 * t)
    info = web.picture(x, fs, tmp_path / "p.png", cfg)
    img = np.asarray(Image.open(tmp_path / "p.png"))
    w = cfg["web"]
    assert img.shape == (int(w["picture_rows"]), 200) and info["cols"] == 200 and info["cols_per_s"] == 100
    row = (w["picture_hz"][1] - 8000) / (w["picture_hz"][1] - w["picture_hz"][0]) * (img.shape[0] - 1)
    assert abs(int(np.argmax(img[:, 75])) - row) <= 1.5                 # top row = highest pitch
    assert img[:, 75].max() == 255 and img[:, 150].max() == 0          # the silence stays pale


def test_long_recordings_get_fewer_columns(cfg, tmp_path):
    info = web.picture(np.zeros(400 * 8000, dtype=np.float32), 8000, tmp_path / "p.png", {**cfg, "web": {**cfg["web"], "picture_hz": [100.0, 3000.0]}})
    assert info["cols"] <= 30000 and info["f_hi"] == 3000.0


def test_play_copy_is_16_bit_48_khz_at_the_set_peak(cfg, tmp_path):
    x = 0.01 * np.sin(np.linspace(0, 2000, 96000)).astype(np.float32)
    web.play_copy(x, 96000, tmp_path / "p.wav", cfg)
    info = sf.info(str(tmp_path / "p.wav"))
    y, fs = sf.read(str(tmp_path / "p.wav"))
    assert fs == 48000 and info.subtype == "PCM_16" and len(y) == 48000
    assert abs(np.abs(y).max() - cfg["web"]["play_peak"]) < 0.01


def test_read_audio_refuses_what_the_decoder_cannot_use(cfg, tmp_path):
    sf.write(str(tmp_path / "low.wav"), np.zeros(16000, dtype=np.float32), 16000)
    with pytest.raises(web.InputError, match="at least"):
        web.read_audio(tmp_path / "low.wav", cfg)
    sf.write(str(tmp_path / "long.wav"), np.zeros(48000 * 3, dtype=np.float32), 48000)
    with pytest.raises(web.InputError, match="up to 2 s"):
        web.read_audio(tmp_path / "long.wav", {**cfg, "web": {**cfg["web"], "max_seconds": 2.0}})
    (tmp_path / "text.wav").write_text("not audio")
    with pytest.raises(web.InputError, match="could not be read"):
        web.read_audio(tmp_path / "text.wav", cfg)
    sf.write(str(tmp_path / "st.wav"), np.stack([np.full(48000, 0.5), np.zeros(48000)], axis=1).astype(np.float32), 48000)
    x, fs = web.read_audio(tmp_path / "st.wav", cfg)
    assert fs == 48000 and x.ndim == 1 and x.min() == 0.5 and x.dtype == np.float32      # the first channel
    # BUG-2: a small compressed file must not decode to gigabytes, so rates and channel counts are capped
    with pytest.raises(web.InputError, match="2 channels; the decoder takes up to 1"):
        web.read_audio(tmp_path / "st.wav", {**cfg, "web": {**cfg["web"], "max_channels": 1}})
    sf.write(str(tmp_path / "fast.flac"), np.zeros((4000, 8), dtype=np.int16), 384000)
    with pytest.raises(web.InputError, match="up to 192000 Hz"):
        web.read_audio(tmp_path / "fast.flac", cfg)


def test_a_full_queue_refuses_new_jobs(tmp_path):
    from fastapi import HTTPException

    jobs = web.Jobs(tmp_path / "jobs", keep=5, max_queued=0)
    with pytest.raises(HTTPException) as e:
        jobs.room()
    assert e.value.status_code == 503 and "busy" in e.value.detail
    web.Jobs(tmp_path / "jobs2", keep=5, max_queued=1).room()             # room left: no error


# ---------------------------------------------------------------------------------------------- digital silence
def test_quiet_floor_adds_noise_only_to_digital_silence(cfg):
    from wcode import channel

    fs, a = 96000, 0.05
    tone = np.zeros(4 * fs, dtype=np.float32)
    tone[fs:2 * fs] = a * np.sin(2 * np.pi * 8000 * np.arange(fs) / fs)
    floored = channel.quiet_floor(tone, fs, cfg)
    assert np.array_equal(floored[fs:2 * fs] != 0, np.ones(fs, bool)) and np.all(floored[:fs] != 0)
    noise = floored[2 * fs:].astype(np.float64)
    levels = channel.bin_levels(noise, fs, cfg["channel"]["snr_bin_hz"])
    snr = 20 * np.log10(a / channel.amplitude_for_snr(0.0, 8000.0, levels, fs, cfg))
    assert abs(snr - cfg["receiver"]["silence_floor_snr_db"]) < 1.5
    assert np.array_equal(channel.quiet_floor(tone, fs, cfg), floored)            # the same file, the same noise
    noisy = tone + np.float32(1e-6)
    assert channel.quiet_floor(noisy, fs, cfg) is not None and np.array_equal(channel.quiet_floor(noisy, fs, cfg), noisy)


# ---------------------------------------------------------------------------------------------- serving other computers
def test_tls_certificate_covers_the_addresses_and_is_kept(cfg, tmp_path):
    from cryptography import x509

    cfg = {**cfg, "web": {**cfg["web"], "tls_dir": str(tmp_path / "tls")}}
    cert, key = web.tls_files(["192.168.1.20"], cfg)
    c = x509.load_pem_x509_certificate(cert.read_bytes())
    san = c.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert {str(v) for v in san.get_values_for_type(x509.IPAddress)} == {"192.168.1.20", "127.0.0.1"}
    assert san.get_values_for_type(x509.DNSName) == ["localhost"] and key.exists()
    first = cert.read_bytes()
    assert web.tls_files(["192.168.1.20"], cfg)[0].read_bytes() == first          # the same network: kept
    assert web.tls_files(["10.0.0.5"], cfg)[0].read_bytes() != first              # a new network: made again
    assert all(not a.startswith("127.") for a in web.lan_addresses())


# ---------------------------------------------------------------------------------------------- the check
def test_check_sorts_each_whistle_into_right_wrong_or_lost():
    send = {"nonce": 7, "length": 2, "whistles": [{"i": 0, "part": "start", "symbol": -1}, {"i": 1, "part": "header", "symbol": 10},
                                                  {"i": 2, "part": "message", "symbol": 20}, {"i": 3, "part": "message", "symbol": 30}]}
    slots = [{"i": 0, "part": "start", "state": "start"}, {"i": 1, "part": "header", "state": "read", "symbol": 10},
             {"i": 2, "part": "message", "state": "read", "symbol": 21}, {"i": 3, "part": "message", "state": "missed"}]
    c = web.check(send, {"nonce": 7, "length": 2, "ok": True, "slots": slots})
    assert c["comparable"] and c["repaired"] and c["counts"] == {"right": 1, "wrong": 1, "lost": 1}
    assert [w["verdict"] for w in c["whistles"]] == ["right", "wrong", "lost"]
    assert not web.check(send, {"nonce": 8, "length": 2, "slots": slots})["comparable"]
    assert not web.check(send, {"nonce": None, "slots": []})["comparable"]


# ---------------------------------------------------------------------------------------------- /healthz (monitoring)
class _StubEngine:
    """Only what create_app and /healthz touch, so these run without the model files (CI)."""

    def __init__(self, cfg, error=None, warm_error=None, warm=True):
        self.cfg, self.error, self.warm_error, self.warm = cfg, error, warm_error, warm


@pytest.mark.parametrize("kw, code, state", [
    ({}, 200, "ok"),
    ({"warm": False}, 200, "starting"),
    ({"error": "FileNotFoundError: codebook.npz"}, 503, "down"),
    ({"warm_error": "RuntimeError: detector"}, 503, "down"),
])
def test_healthz_reports_whether_messages_can_be_served(cfg, tmp_path, kw, code, state):
    from fastapi.testclient import TestClient

    from wcode.config import project_version

    cfg["web"]["out_dir"] = str(tmp_path / "web")
    with TestClient(web.create_app(_StubEngine(cfg, **kw), warm=False)) as c:
        r = c.get("/healthz")
    body = r.json()
    assert r.status_code == code and body["status"] == state and body["queue"] == 0
    assert body["version"] == project_version() != "unknown"
    assert ("problem" in body) == (code == 503)


def test_oversized_requests_are_refused_before_any_route(cfg, tmp_path):
    """BUG-4: bodies over max_request_kb (JSON) or max_upload_mb (/decode) never reach a route or the disk."""
    from fastapi.testclient import TestClient

    cfg["web"]["out_dir"] = str(tmp_path / "web")
    cfg["web"]["max_upload_mb"] = 1
    with TestClient(web.create_app(_StubEngine(cfg), warm=False)) as c:
        r = c.post("/api/wc/frame", json={"text": "x" * 70_000, "key": "k", "nonce": 1})
        assert r.status_code == 413 and "larger than 64 kB" in r.json()["detail"]
        r = c.post("/api/wc/decode", data={"key": "k"}, files={"file": ("big.wav", bytes(2 << 20), "audio/wav")})
        assert r.status_code == 413 and "larger than 1 MB" in r.json()["detail"]
    assert not any((tmp_path / "web").iterdir())                          # no job folder was made


def test_decoded_text_stays_off_disk_and_tracebacks_stay_on_the_server(cfg, tmp_path):
    """BUG-6: a decode job's message is kept in memory, never in result.json; BUG-7: no route serves error.txt."""
    from fastapi.testclient import TestClient

    out = tmp_path / "web"
    cfg["web"]["out_dir"], cfg["web"]["keep_jobs"] = str(out), 2
    with TestClient(web.create_app(_StubEngine(cfg), warm=False)) as c:
        jobs = c.app.state.jobs

        def run(fn) -> str:
            jid, _ = jobs.new()
            jobs.submit(jid, "decode", fn)
            t0 = time.time()
            while jobs.jobs[jid]["state"] not in ("done", "error"):
                assert time.time() - t0 < 10
                time.sleep(0.02)
            return jid

        ok = run(lambda progress: {"kind": "decode", "ok": True, "text": "MEET AT DAWN", "hex": None})
        on_disk = (out / ok / "result.json").read_text(encoding="utf-8")
        assert "MEET" not in on_disk and json.loads(on_disk)["text"] is None
        r = c.get(f"/api/wc/files/{ok}/result.json")
        assert r.json()["text"] == "MEET AT DAWN" and r.headers["cache-control"] == "no-store"
        assert "MEET" not in c.get(f"/api/wc/jobs/{ok}").text
        raw = run(lambda progress: {"kind": "decode", "ok": True, "text": None, "hex": "c3a9ff"})
        assert "c3a9ff" not in (out / raw / "result.json").read_text(encoding="utf-8")
        assert c.get(f"/api/wc/files/{raw}/result.json").json()["hex"] == "c3a9ff"

        def broken(progress):
            raise RuntimeError("a detail for the owner")

        bad = run(broken)
        j = c.get(f"/api/wc/jobs/{bad}").json()
        assert j["state"] == "error" and "RuntimeError" in j["error"] and "error.txt" not in j["error"]
        assert "a detail for the owner" in (out / bad / "error.txt").read_text(encoding="utf-8")
        assert c.get(f"/api/wc/files/{bad}/error.txt").status_code == 404
        # keep_jobs = 2: the oldest job has gone, and its message with it (all three ids may share one second: BUG-13)
        assert {d.name for d in out.iterdir()} == {raw, bad} and set(jobs.held) == {raw}
        assert c.get(f"/api/wc/files/{ok}/result.json").status_code == 404


# ---------------------------------------------------------------------------------------------- the routes, on the real model
@pytest.fixture(scope="module")
def client(tmp_path_factory):
    from fastapi.testclient import TestClient

    from wcode.config import default_config

    cfg = default_config()
    if not (codebook.out_dir(cfg) / "codebook.npz").exists():
        pytest.skip("no codebook built on this machine")
    cfg["web"]["out_dir"] = str(tmp_path_factory.mktemp("web"))
    engine = web.Engine(cfg)
    assert engine.error is None, engine.error
    with TestClient(web.create_app(engine, warm=False)) as c:
        yield c


def finish(client, started, timeout=180.0) -> dict:
    assert started.status_code == 200, started.text
    jid = started.json()["job"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = client.get(f"/api/wc/jobs/{jid}").json()
        if j["state"] in ("done", "error"):
            assert j["state"] == "done", j["error"]
            return {"id": jid, **client.get(j["result"]).json()}
        time.sleep(0.2)
    raise AssertionError("job did not finish")


def test_status_lists_the_shapes_and_limits(client):
    s = client.get("/api/wc/status").json()
    assert s["ready"] and len(s["shapes"]) == 17 and len(s["shapes"][0]["f"]) == web.SHAPE_POINTS
    assert s["limits"]["max_chars"] == 60 and s["noise_choices"][0] == 276


def test_frame_shows_every_step_and_whistle(client, cfg):
    r = client.post("/api/wc/frame", json={"text": "MEET AT DAWN", "key": KEY, "nonce": 77}).json()
    fr = format2.encode("MEET AT DAWN", KEY, 77, cfg)
    assert (r["mode"], r["length"], r["message_bits"], r["n_start"], r["n_header"]) == ("compact", 12, 60, 3, 7)
    assert r["n_payload"] == len(fr.payload_symbols) == len(r["whistles"]) - 10
    assert [w["symbol"] for w in r["whistles"][3:]] == fr.symbols.tolist()
    assert [w["role"] for w in r["whistles"][:4]] == ["start", "start", "start", "header"]
    assert {w["role"] for w in r["whistles"][10:]} == {"data", "spare"}
    assert r["whistles"][10]["chars"][0] == 0 and 30 < r["duration_s"] < 400
    assert client.post("/api/wc/frame", json={"text": "meet", "key": KEY, "nonce": 77}).json()["mode"] == "raw"


@pytest.mark.parametrize("body, words", [({"text": "", "key": KEY, "nonce": 1}, "write a message"),
                                         ({"text": "A" * 61, "key": KEY, "nonce": 1}, "up to 60"),
                                         ({"text": "HI", "key": "", "nonce": 1}, "key is empty"),
                                         ({"text": "HI", "key": KEY, "nonce": 300}, "0-255"),
                                         ({"text": "\U0001F40B" * 40, "key": KEY, "nonce": 1}, "bytes")])
def test_frame_refuses_bad_input_in_plain_words(client, body, words):
    r = client.post("/api/wc/frame", json=body)
    assert r.status_code == 400 and words in r.json()["detail"]


def test_send_sea_decode_check(client):
    """Text -> the sender's WAV -> ocean noise -> an upload that names no job -> the exact text, and the check afterwards."""
    sent = finish(client, client.post("/api/wc/send", json={"text": "MEET AT DAWN", "key": KEY, "nonce": 77}))
    assert sent["n_data"] == len(sent["whistles"]) and sent["nonce"] == 77
    raw = (client.app.state.jobs.root / sent["id"] / "result.json").read_text(encoding="utf-8")
    assert KEY not in raw and "MEET" not in raw                                  # neither the key nor the text on disk
    for name in ("sent.png", "sent_play.wav", "sent.wav"):
        assert client.get(f"/api/wc/files/{sent['id']}/{name}").status_code == 200

    heard = finish(client, client.post("/api/wc/sea", json={"job": sent["id"], "snr_db": 20, "encounter": 214, "seed": 3}))
    assert heard["from"] == sent["id"] and heard["duration_s"] > sent["duration_s"]
    wav = client.get(f"/api/wc/files/{heard['id']}/heard.wav").content

    got = finish(client, client.post("/api/wc/decode", data={"key": KEY}, files={"file": ("heard.wav", wav, "audio/wav")}))
    assert got["ok"] and got["text"] == "MEET AT DAWN" and got["nonce"] == 77 and got["length"] == 12
    assert got["header"]["n"] == 7 and got["payload"]["n"] == sent["n_data"] - 10
    assert {s["state"] for s in got["slots"][:3]} == {"start"} and len(got["slots"]) == sent["n_data"]
    assert got["repair"]["spare"] == {"header": 4, "payload": 8}
    raw = (client.app.state.jobs.root / got["id"] / "result.json").read_text(encoding="utf-8")
    assert KEY not in raw and "MEET" not in raw                                  # the decoded text is held in memory only

    c = client.post("/api/wc/check", json={"send": sent["id"], "decode": got["id"]}).json()
    assert c["comparable"] and sum(c["counts"].values()) == sent["n_data"] - 3 and c["counts"]["right"] >= 20

    wrong = finish(client, client.post("/api/wc/decode-job", json={"job": sent["id"], "file": "sent", "key": "tide-37"}))
    assert not wrong["ok"] and wrong["text"] is None
    assert not client.post("/api/wc/check", json={"send": sent["id"], "decode": wrong["id"]}).json().get("counts", {}).get("right")


def test_files_and_jobs_are_guarded(client):
    assert client.get("/api/wc/jobs/nope").status_code == 404
    assert client.get("/api/wc/files/wc_20260101T000000Z_abcdef/result.json").status_code == 404
    assert client.get("/api/wc/files/..%2F..%2Fconfig.toml/x").status_code == 404
    assert client.post("/api/wc/sea", json={"job": "nope"}).status_code == 404
    sent = finish(client, client.post("/api/wc/send", json={"text": "HI", "key": KEY, "nonce": 1}))
    assert client.post("/api/wc/sea", json={"job": sent["id"], "snr_db": 12}).status_code == 400
    assert client.post("/api/wc/decode-job", json={"job": sent["id"], "file": "heard", "key": KEY}).status_code == 400
    r = client.post("/api/wc/decode", data={"key": KEY}, files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 400 and "file" in r.json()["detail"]
    dec = finish(client, client.post("/api/wc/decode-job", json={"job": sent["id"], "file": "sent", "key": KEY}))
    assert dec["ok"] and dec["text"] == "HI"
    assert client.get(f"/api/wc/files/{dec['id']}/input.wav").status_code == 404     # the upload itself is not served back
    assert not (client.app.state.jobs.root / dec["id"] / "input.wav").exists()      # ... and is deleted once its job has ended
    for name in ("recording.png", "recording_play.wav", "result.json"):
        assert client.get(f"/api/wc/files/{dec['id']}/{name}").status_code == 200
    assert json.loads((client.app.state.jobs.root / dec["id"] / "result.json").read_text(encoding="utf-8"))["source"] == "sent.wav"
