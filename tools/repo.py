"""Repository checks and chores, in one command. Standard library only (ruff and pytest are called when installed).

    python tools/repo.py check [lint|config|secrets|links|checksums|tests ...] [--quick]
        every check in turn, with a summary; exit code 1 if any failed. --quick: everything except the test suites.
        The Definition of Done (project/WORKFLOW.md) asks for a clean `check` before every commit.

    python tools/repo.py secrets [--staged | --history]
        look for keys, tokens and private keys: in all files git would commit (default), in the staged files only (the
        pre-commit hook), or in every past commit

    python tools/repo.py links
        every relative link in the Markdown files points at a file that git holds

    python tools/repo.py checksums verify [--strict] [--raw]
    python tools/repo.py checksums make
        model and data files against project/checksums/models.sha256. A file that is not on this machine is reported as
        absent, not as a failure, unless --strict. --raw also checks the raw recordings against metadata/manifest_all.csv
        (about 110 GB: long). `make` rewrites the manifest from the files present; run it only when a model is added
        on purpose, and log it (project/MODELS.md)

    python tools/repo.py lock
        write constraints.txt: the exact version of every package the project uses, as installed here

    python tools/repo.py health [URL] [--every SECONDS] [--log FILE]
        ask the web server's /healthz whether it can serve messages (default http://127.0.0.1:8000). Appends one line
        per check to the log (default runs/health.log). Exit code 1 when it is down (single check)

    python tools/repo.py release-check VERSION
        everything a release needs (project/RELEASES.md): matching version, changelog section, clean tree, unused tag,
        and a clean `check`

    python tools/repo.py ci-report [RUN]
        the latest CI run on GitHub (or run RUN): each job's result, the failed step and its annotations (failing tests,
        lint findings, audit warnings). Reads GitHub's public API; no sign-in needed

    python tools/repo.py audit-report REPORT.json
        used by CI: turns pip-audit's JSON report into warnings on the run and a summary table
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from importlib import metadata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_MANIFEST = ROOT / "project" / "checksums" / "models.sha256"
RAW_MANIFEST = ROOT / "metadata" / "manifest_all.csv"

# Files whose checksums are kept (`checksums make`). Tracked ones are verified in CI too; the rest only where they exist.
MODEL_GLOBS = [
    "models/detector/*/checkpoint.pt",
    "mod_detector_5_24/models/detector/*/checkpoint.pt",
    "models/vaegmm/*/checkpoints/final.pt",
    "models/vaegmm/*/checkpoints/last.pt",
    "models/vaegmm/*/latents_mu.npy",
    "models/vaegmm/*/gmm_*/gmm.npz",
    "models/vaegmm/*/gmm_*/component_features.npy",
    "whistlecode/outputs/codebook/codebook.npz",
    "whistlecode/outputs/bank/bank.npz",
    "preprocessed/dataset_info.json",
    "preprocessed/encounter_*/images.csv",
]

SECRET_PATTERNS = {
    "private key": r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP |ENCRYPTED )?PRIVATE KEY-----",
    "GitHub token": r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})",
    "Tailscale key": r"\btskey-[a-z]+-[A-Za-z0-9]{6,}-[A-Za-z0-9]{10,}",
    "AWS access key": r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b",
    "Google API key": r"\bAIza[0-9A-Za-z_\-]{35}\b",
    "Slack token": r"\bxox[abprs]-[A-Za-z0-9-]{10,}",
    "AI service key": r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_\-]{32,}",
    "Hugging Face token": r"\bhf_[A-Za-z0-9]{34,}",
    "assigned secret": r"(?i)\b(?:password|passwd|secret|api_?key|auth_?key|access_?token)\s*[:=]\s*['\"][^'\"\s]{12,}['\"]",
}
SECRET_FILE = re.compile(r"(^|/)(\.env|id_rsa|id_ecdsa|id_ed25519|[^/]+\.(?:pem|key|p12|pfx))$")
SECRET_FILE_OK = re.compile(r"(^|/)\.env\.example$")
MAX_SCAN_BYTES = 5 * 1024 * 1024

LINK = re.compile(r"!?\[[^\]]*\]\((<[^>]+>|[^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE = re.compile(r"`[^`]*`")


# ---------------------------------------------------------------------------------------------- helpers
def git(*args: str, check: bool = True) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=check).stdout


def committable_files() -> list[str]:
    """Tracked files plus new files that .gitignore lets through, as git would commit them."""
    names = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\0")
    return sorted({n for n in names if n and (ROOT / n).is_file()})


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 22):
            h.update(chunk)
    return h.hexdigest()


def say(ok: bool | None, text: str) -> None:
    tag = {True: "PASS", False: "FAIL", None: "SKIP"}[ok]
    print(f"  [{tag}] {text}")


# ---------------------------------------------------------------------------------------------- secrets
def scan_text(name: str, text: str) -> list[str]:
    found = []
    for label, pat in SECRET_PATTERNS.items():
        for m in re.finditer(pat, text):
            line = text.count("\n", 0, m.start()) + 1
            found.append(f"{name}:{line}: {label}")
    return found


def secrets(mode: str = "all") -> bool:
    """mode: all (files git would commit), staged (the index, for the pre-commit hook) or history (every commit)."""
    found: list[str] = []
    if mode == "history":
        log = git("log", "-p", "--all", "--no-color", "--format=commit %H")
        commit = "?"
        for i, line in enumerate(log.splitlines()):
            if line.startswith("commit "):
                commit = line[7:19]
            elif line.startswith("+") and not line.startswith("+++"):
                found += [f"commit {commit} (log line {i + 1}): {h.split(': ', 1)[1]}" for h in scan_text("", line[1:])]
        files = []
    elif mode == "staged":
        files = [n for n in git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split("\0") if n]
    else:
        files = committable_files()
    for name in files:
        if SECRET_FILE.search(name) and not SECRET_FILE_OK.search(name):
            found.append(f"{name}: a key or environment file must not be committed")
            continue
        data = (subprocess.run(["git", "show", f":{name}"], cwd=ROOT, capture_output=True).stdout if mode == "staged"
                else (ROOT / name).read_bytes()[:MAX_SCAN_BYTES])
        if b"\0" in data[:8192]:
            continue                                     # binary
        found += scan_text(name, data.decode("utf-8", errors="replace"))
    for f in found:
        print(f"    {f}")
    say(not found, f"secrets ({mode}): {len(found)} finding(s)" + ("" if found else f" in {len(files)} file(s)" if files else ""))
    return not found


# ---------------------------------------------------------------------------------------------- links
HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
HTML_ANCHOR = re.compile(r"<a\s+(?:id|name)=\"([^\"]+)\"", re.I)


def anchors(path: Path) -> set[str]:
    """The #fragments GitHub gives a Markdown file's headings (lower case, punctuation dropped, spaces to hyphens,
    -1, -2 ... for repeats), plus explicit <a id="..."> anchors."""
    found, seen, in_fence = set(), {}, False
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        found.update(HTML_ANCHOR.findall(line))
        m = HEADING.match(line)
        if m:
            text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", m.group(2))          # [text](link) -> text
            slug = re.sub(r"[^\w\- ]", "", text.lower()).replace(" ", "-")
            n = seen.get(slug, 0)
            seen[slug] = n + 1
            found.add(slug if n == 0 else f"{slug}-{n}")
    return found


def links() -> bool:
    tracked = set(committable_files())
    tracked_dirs = {str(Path(n).parent.as_posix()) for n in tracked}
    for d in list(tracked_dirs):
        while d not in ("", "."):
            d = str(Path(d).parent.as_posix())
            tracked_dirs.add(d)
    bad, n_links, n_files, cache = [], 0, 0, {}
    for name in sorted(n for n in tracked if n.endswith(".md")):
        n_files += 1
        in_fence = False
        for no, line in enumerate((ROOT / name).read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for m in LINK.finditer(INLINE_CODE.sub("", line)):
                target = m.group(1).strip("<>")
                if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
                    continue                             # web address or mailto
                n_links += 1
                path, _, frag = urllib.parse.unquote(target.split("?", 1)[0]).partition("#")
                if not path:                             # a heading in the same file
                    rel = name
                else:
                    resolved = (ROOT / name).parent / path
                    try:
                        rel = resolved.resolve().relative_to(ROOT).as_posix()
                    except ValueError:
                        bad.append(f"{name}:{no}: {target} (outside the repository)")
                        continue
                    if rel not in tracked and rel.rstrip("/") not in tracked_dirs:
                        why = "not in git" if resolved.exists() else "missing"
                        bad.append(f"{name}:{no}: {target} ({why})")
                        continue
                if frag and rel.endswith(".md"):
                    if rel not in cache:
                        cache[rel] = anchors(ROOT / rel)
                    if frag.lower() not in cache[rel]:
                        bad.append(f"{name}:{no}: {target} (no heading #{frag} in {rel})")
    for b in bad:
        print(f"    {b}")
    say(not bad, f"links: {n_links} relative link(s) and anchor(s) in {n_files} Markdown file(s), {len(bad)} broken")
    return not bad


# ---------------------------------------------------------------------------------------------- checksums
def read_manifest(path: Path) -> list[tuple[str, str]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            digest, name = line.split(maxsplit=1)
            rows.append((digest, name.strip().lstrip("*")))
    return rows


def checksums_make() -> bool:
    files = sorted({p for g in MODEL_GLOBS for p in ROOT.glob(g) if p.is_file()})
    old = dict((n, d) for d, n in read_manifest(MODEL_MANIFEST)) if MODEL_MANIFEST.exists() else {}
    keep = {n: d for n, d in old.items() if not (ROOT / n).exists()}     # absent here, so keep the recorded value
    rows = {p.relative_to(ROOT).as_posix(): sha256(p) for p in files} | keep
    MODEL_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    head = ["# SHA-256 of every model, mixture, codebook and dataset index file (project/MODELS.md, project/DATA.md).",
            "# Verify: python tools/repo.py checksums verify    Rewrite (only when a model is added on purpose): ... make",
            f"# Written {dt.date.today().isoformat()} from the files on the project laptop."]
    MODEL_MANIFEST.write_text("\n".join(head + [f"{d}  {n}" for n, d in sorted(rows.items())]) + "\n", encoding="utf-8")
    changed = [n for n in rows if old.get(n) not in (None, rows[n])]
    for n in changed:
        print(f"    changed: {n}")
    say(True, f"checksums make: {len(rows)} file(s) recorded in {MODEL_MANIFEST.relative_to(ROOT).as_posix()}"
        + (f", {len(changed)} changed" if changed else ""))
    return True


def checksums_verify(strict: bool = False, raw: bool = False) -> bool:
    if not MODEL_MANIFEST.exists():
        say(False, f"checksums: {MODEL_MANIFEST.relative_to(ROOT).as_posix()} is missing (run: checksums make)")
        return False
    good, absent, bad = 0, [], []
    for digest, name in read_manifest(MODEL_MANIFEST):
        p = ROOT / name
        if not p.exists():
            absent.append(name)
        elif sha256(p) == digest:
            good += 1
        else:
            bad.append(name)
    for b in bad:
        print(f"    MISMATCH: {b}")
    if strict:
        for a in absent:
            print(f"    absent: {a}")
    ok = not bad and (not strict or not absent)
    say(ok, f"checksums: {good} match, {len(bad)} differ, {len(absent)} not on this machine")
    if raw:
        ok = raw_verify() and ok
    return ok


def raw_verify() -> bool:
    rows = list(csv.DictReader(open(RAW_MANIFEST, encoding="utf-8")))
    present = [r for r in rows if (ROOT / r["relative_path"]).exists()]
    bad = []
    for i, r in enumerate(present, 1):
        if sha256(ROOT / r["relative_path"]) != r["sha256"]:
            bad.append(r["relative_path"])
        if i % 25 == 0 or i == len(present):
            print(f"    raw audio: {i} / {len(present)} checked", flush=True)
    for b in bad:
        print(f"    MISMATCH: {b}")
    say(not bad, f"raw audio: {len(present) - len(bad)} of {len(present)} present file(s) match "
        f"(manifest lists {len(rows)})")
    return not bad


# ---------------------------------------------------------------------------------------------- lint, config, tests
def lint() -> bool:
    ruff = shutil.which("ruff")
    if not ruff:
        say(None, "lint: ruff is not installed (pip install ruff==0.3.5)")
        return True
    r = subprocess.run([ruff, "check", "."], cwd=ROOT)
    say(r.returncode == 0, "lint: ruff check")
    return r.returncode == 0


def config() -> bool:
    """Every TOML file parses, and each project loader accepts its file (they refuse a changed [paper] section)."""
    sys.path[:0] = [str(ROOT / "src"), str(ROOT / "whistlecode")]
    problems = []
    for p in sorted(ROOT.glob("configs/*.toml")) + [ROOT / "whistlecode" / "config.toml", ROOT / "pyproject.toml"]:
        try:
            tomllib.loads(p.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as e:
            problems.append(f"{p.relative_to(ROOT).as_posix()}: {e}")
    try:
        from whistlepipe.config import load_detector_config, load_pipeline_config
        from whistlepipe.vaegmm.config import load_vaegmm_config
        from wcode.config import default_config
        for load in (load_pipeline_config, load_detector_config, load_vaegmm_config, default_config):
            load()
        from whistlepipe.infer import load_inference_config        # imports torch
        load_inference_config()
    except Exception as e:  # noqa: BLE001  (reported, not raised)
        problems.append(f"{type(e).__name__}: {e}")
    for p in problems:
        print(f"    {p}")
    say(not problems, "config: every TOML parses and every loader accepts its file")
    return not problems


def tests() -> bool:
    ok = True
    for label, args in (("whistle-model suite", []), ("message-system suite", ["whistlecode/tests"])):
        r = subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", *args], cwd=ROOT)
        say(r.returncode == 0, f"tests: {label}")
        ok = ok and r.returncode == 0
    return ok


CHECKS = {"lint": lint, "config": config, "secrets": secrets, "links": links, "checksums": checksums_verify, "tests": tests}


def check(names: list[str], quick: bool = False) -> bool:
    names = names or [n for n in CHECKS if not (quick and n == "tests")]
    results = {}
    for n in names:
        print(f"\n== {n}")
        results[n] = CHECKS[n]()
    print("\nSummary: " + "  ".join(f"{n} {'ok' if v else 'FAILED'}" for n, v in results.items()))
    return all(results.values())


# ---------------------------------------------------------------------------------------------- lock
def requirement_names(path: Path) -> list[str]:
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line and not line.startswith("-"):
            names.append(re.split(r"[\s<>=!~;\[]", line, maxsplit=1)[0])
    return names


def lock() -> bool:
    """constraints.txt from the installed packages: the direct requirements and everything they pull in."""
    direct = (requirement_names(ROOT / "requirements.txt") + requirement_names(ROOT / "whistlecode" / "requirements.txt")
              + ["ruff"])
    seen: dict[str, str] = {}
    todo = list(direct)
    while todo:
        name = todo.pop()
        key = re.sub(r"[-_.]+", "-", name).lower()
        if key in seen:
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            if name in direct:                           # a dependency's own missing extras (old-Python backports) are fine
                print(f"    not installed: {name}")
            continue
        seen[key] = dist.version
        for req in dist.requires or []:
            if "extra ==" in req:
                continue
            todo.append(re.split(r"[\s<>=!~;\[(]", req, maxsplit=1)[0])
    out = ROOT / "constraints.txt"
    lines = ["# Exact versions of every package the project uses, as installed on the project laptop. Written by",
             "# `python tools/repo.py lock`; never edit by hand. Use with: pip install -r requirements.txt -c constraints.txt",
             "# Local build labels (+cu130) are dropped, so the CPU and CUDA builds of the same version both satisfy a pin.",
             f"# Python {sys.version.split()[0]}, {sys.platform}, {dt.date.today().isoformat()}."]
    lines += [f"{k}=={v.split('+', 1)[0]}" for k, v in sorted(seen.items())]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    say(True, f"lock: {len(seen)} package(s) written to constraints.txt")
    return True


# ---------------------------------------------------------------------------------------------- health
def health(url: str, every: float | None, log: Path) -> bool:
    url = url.rstrip("/") + "/healthz"
    log.parent.mkdir(parents=True, exist_ok=True)
    while True:
        t0 = time.monotonic()
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                code, body = r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            code, body = e.code, json.loads(e.read() or b"{}")
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
            code, body = 0, {"status": "unreachable", "problem": str(e)}
        ms = round((time.monotonic() - t0) * 1000)
        up = code == 200
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = (f"{stamp}  {'UP  ' if up else 'DOWN'}  {code or '---'}  {ms:>5} ms  {body.get('status', '?')}"
                f"  v{body.get('version', '?')}" + (f"  {body['problem']}" if body.get("problem") else ""))
        print(line, flush=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write(f"{line}  {url}\n")
        if not every:
            return up
        time.sleep(every)


# ---------------------------------------------------------------------------------------------- CI helpers
def audit_report(path: Path) -> bool:
    """pip-audit's JSON report as warnings: GitHub annotations and a step summary in CI, a table elsewhere.
    False only when there is no readable report (the audit itself failed)."""
    import os
    gha = os.environ.get("GITHUB_ACTIONS") == "true"
    try:
        deps = json.loads(path.read_text(encoding="utf-8"))["dependencies"]
    except (OSError, ValueError, KeyError) as e:
        print(f"::error title=pip-audit::no readable report ({e})" if gha else f"  [FAIL] audit: no readable report ({e})")
        return False
    merged: dict[tuple, dict] = {}                       # a package pinned in both files is listed twice; so is an advisory
    for d in deps:
        m = merged.setdefault((d["name"].lower(), d.get("version")), {**d, "vulns": []})
        seen = {v["id"] for v in m["vulns"]}
        m["vulns"] += [v for v in d.get("vulns") or [] if v["id"] not in seen and not seen.add(v["id"])]
    deps = list(merged.values())
    vulnerable = [d for d in deps if d.get("vulns")]
    skipped = [d for d in deps if d.get("skip_reason")]
    try:
        from packaging.version import Version as order       # installed with pip-audit
    except ImportError:
        order = str
    rows = []
    for d in vulnerable:
        fixes = sorted({f for v in d["vulns"] for f in v.get("fix_versions") or []}, key=order)
        fix = fixes[-1] if fixes else "no fix yet"
        ids = ", ".join(v["id"] for v in d["vulns"][:4]) + (" ..." if len(d["vulns"]) > 4 else "")
        rows.append((d["name"], d["version"], len(d["vulns"]), fix, ids))
        if gha:
            print(f"::warning title=pip-audit: {d['name']} {d['version']}::{len(d['vulns'])} known vulnerabilities ({ids}); fixed in {fix}")
        else:
            print(f"    {d['name']}=={d['version']}: {len(d['vulns'])} advisories, fixed in {fix} ({ids})")
    for d in skipped:
        print(f"::notice title=pip-audit skipped {d['name']}::{d['skip_reason']}" if gha else f"    skipped {d['name']}: {d['skip_reason']}")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(f"### Dependency audit\n\n{len(vulnerable)} of {len(deps)} pinned packages have known vulnerabilities.\n\n")
            if rows:
                f.write("| Package | Version | Advisories | Fixed in | IDs |\n|---|---|---|---|---|\n")
                f.writelines(f"| {n} | {v} | {k} | {fx} | {i} |\n" for n, v, k, fx, i in rows)
    if not gha:
        say(not vulnerable, f"audit: {len(vulnerable)} of {len(deps)} pinned package(s) with known vulnerabilities")
    return True


def ci_report(run_id: str | None = None) -> bool:
    """The latest CI run on GitHub (or RUN): each job's result and its annotations. Public data, no sign-in needed."""
    remote = git("remote", "get-url", "origin").strip()
    m = re.search(r"github\.com[:/]([^/]+/[^/.]+)", remote)
    if not m:
        say(False, f"ci-report: origin is not a GitHub repository ({remote})")
        return False
    api = f"https://api.github.com/repos/{m.group(1)}"

    def get(url: str):
        req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "repo-tools"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)

    run = get(f"{api}/actions/runs/{run_id}") if run_id else get(f"{api}/actions/runs?per_page=1")["workflow_runs"][0]
    print(f"Run {run['id']} ({run['head_branch']} {run['head_sha'][:7]}, {run['created_at']}): {run['status']} / {run['conclusion']}")
    print(f"  {run['html_url']}")
    for job in get(f"{api}/actions/runs/{run['id']}/jobs")["jobs"]:
        failed = [s["name"] for s in job["steps"] if s["conclusion"] == "failure"]
        print(f"\n  [{(job['conclusion'] or job['status']).upper()}] {job['name']}" + (f"  (failed step: {', '.join(failed)})" if failed else ""))
        for a in get(f"{api}/check-runs/{job['id']}/annotations"):
            if "Node.js" in (a.get("message") or ""):
                continue                                 # GitHub's own runner notices
            where = f"{a['path']}:{a['start_line']}" if a.get("path") not in (None, ".github") else ""
            print(f"      {a['annotation_level']}: {where} {(a.get('title') or '')} {(a.get('message') or '').strip()[:300]}".rstrip())
    return run["conclusion"] == "success"


# ---------------------------------------------------------------------------------------------- release
def release_check(version: str) -> bool:
    version = version.lstrip("v")
    problems = []
    declared = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    if declared != version:
        problems.append(f"pyproject.toml says {declared}, not {version}")
    if not re.search(rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}", (ROOT / "CHANGELOG.md").read_text(encoding="utf-8"), re.M):
        problems.append(f"CHANGELOG.md has no '## [{version}] - YYYY-MM-DD' section")
    if git("status", "--porcelain").strip():
        problems.append("the working tree has uncommitted changes")
    if git("tag", "--list", f"v{version}").strip():
        problems.append(f"tag v{version} already exists")
    for p in problems:
        print(f"    {p}")
    say(not problems, f"release v{version}: version, changelog, clean tree, unused tag")
    ok = not problems and check([])
    if ok:
        print(f"\nReady. Tag and push (you run these):\n  git tag -a v{version} -m \"v{version}\"\n  git push origin v{version}")
    return ok


# ---------------------------------------------------------------------------------------------- command line
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python tools/repo.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="run the checks")
    c.add_argument("names", nargs="*", choices=[[], *CHECKS], metavar="CHECK", help=" | ".join(CHECKS))
    c.add_argument("--quick", action="store_true", help="skip the test suites")
    s = sub.add_parser("secrets", help="look for keys and tokens")
    g = s.add_mutually_exclusive_group()
    g.add_argument("--staged", action="store_true")
    g.add_argument("--history", action="store_true")
    sub.add_parser("links", help="check relative Markdown links")
    k = sub.add_parser("checksums", help="verify or rewrite project/checksums/models.sha256")
    k.add_argument("action", choices=["verify", "make"])
    k.add_argument("--strict", action="store_true", help="absent files fail too")
    k.add_argument("--raw", action="store_true", help="also verify the raw recordings (long)")
    sub.add_parser("lock", help="write constraints.txt from the installed packages")
    h = sub.add_parser("health", help="ask the web server whether it is up")
    h.add_argument("url", nargs="?", default="http://127.0.0.1:8000")
    h.add_argument("--every", type=float, help="repeat every SECONDS")
    h.add_argument("--log", type=Path, default=ROOT / "runs" / "health.log")
    r = sub.add_parser("release-check", help="check that VERSION can be released")
    r.add_argument("version")
    au = sub.add_parser("audit-report", help="turn a pip-audit JSON report into warnings (CI)")
    au.add_argument("report", type=Path)
    cr = sub.add_parser("ci-report", help="the latest CI run on GitHub: jobs and annotations")
    cr.add_argument("run", nargs="?", help="a run id (default: the latest run)")
    a = ap.parse_args(argv)

    if a.cmd == "check":
        ok = check(a.names, a.quick)
    elif a.cmd == "secrets":
        ok = secrets("staged" if a.staged else "history" if a.history else "all")
    elif a.cmd == "links":
        ok = links()
    elif a.cmd == "checksums":
        ok = checksums_make() if a.action == "make" else checksums_verify(a.strict, a.raw)
    elif a.cmd == "lock":
        ok = lock()
    elif a.cmd == "health":
        ok = health(a.url, a.every, a.log)
    elif a.cmd == "audit-report":
        ok = audit_report(a.report)
    elif a.cmd == "ci-report":
        ok = ci_report(a.run)
    else:
        ok = release_check(a.version)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
