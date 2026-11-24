"""The server image installs every package at its locked version (deploy/; project/AUDIT_2026-11-23.md, BUG-9)."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def pins(path: Path) -> dict[str, str]:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if "==" in line:
            name, version = line.split("==", 1)
            out[re.sub(r"[-_.]+", "-", name).lower()] = version.strip()
    return out


def test_the_server_pins_agree_with_the_lock():
    lock, serve = pins(ROOT / "constraints.txt"), pins(ROOT / "deploy" / "requirements-serve.txt")
    assert serve and {name: lock.get(name) for name in serve} == serve


def test_the_image_installs_with_the_lock():
    df = (ROOT / "deploy" / "Dockerfile").read_text(encoding="utf-8")
    assert set(re.findall(r"torch==([0-9.]+)", df)) == {pins(ROOT / "constraints.txt")["torch"]}
    assert "--no-deps --index-url" in df and "-c /tmp/constraints.txt" in df and "pip check" in df
    assert re.search(r"^RUN pip install pip==[0-9.]+$", df, re.M)           # not the base image's own pip
    # the build context is the repository: the ignore file lets in exactly what the Dockerfile copies
    copied = {p for line in df.splitlines() if line.startswith("COPY ") for p in line.split()[1:-1]}
    let_in = {line[1:] for line in (ROOT / "deploy" / "Dockerfile.dockerignore").read_text(encoding="utf-8").splitlines()
              if line.startswith("!")}
    assert copied == let_in == {"deploy/requirements-serve.txt", "constraints.txt"}
