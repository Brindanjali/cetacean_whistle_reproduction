# Security

This repository is **public**, and the project page can be **open to the internet** (Tailscale Funnel). This page covers the secrets the project uses, what the page exposes, and how to report a problem. Index of all engineering systems: [`project/README.md`](../project/README.md).

## Reporting a problem

Use GitHub's private vulnerability reporting on this repository (Security → "Report a vulnerability") if it is enabled, or contact the owner through their GitHub profile. Please don't open a public issue for a security problem.

WhistleCode is a research prototype. Its message encryption is **not** claimed to be confidential ([`whistlecode/THREAT_MODEL.md`](../whistlecode/THREAT_MODEL.md) section 5); weak keys can be guessed offline. Don't use it to protect anything real.

## Secrets

| Secret | Where it lives | Never |
|---|---|---|
| Tailscale auth key (optional, one-off) | `deploy/.env` (gitignored); delete it once the machine is signed in | in git, in a log line, in a screenshot |
| Tailscale machine sign-in | Docker volume `whistle_tailscale-state` | copied anywhere |
| `serve --lan` certificate and private key | `whistlecode/outputs/web_tls/` (gitignored), made on the laptop | in git |
| Message keys typed into Encode and Decode | memory only: the server never writes them to disk (`whistlecode/wcode/web.py`) | logged |
| GitHub, Google and Colab accounts | the owner's password manager | in any file in this repository |

**Checks**

- **Pre-commit hook:** refuses a commit whose staged files contain a private key, a known token format (GitHub, Tailscale, AWS, Google, Slack, Hugging Face, AI services), a secret assigned in code, or a key or `.env` file (`python tools/repo.py secrets --staged`).
- **CI:** the same scan over every file and every past commit, on every push.
- **State on 2026-11-21:** 0 findings in 374 files and in the full history.

**If a secret reaches git:** revoke it at its provider first (that is what makes it harmless), then remove it from the files. A public commit stays readable in forks and caches, so removing it from history is not enough on its own. Record an incident ([`project/INCIDENTS.md`](../project/INCIDENTS.md)).

## What the public page exposes

| Exposure | Control |
|---|---|
| Anyone with the address can use the page | `"AllowFunnel": false` in `deploy/tailscale/serve.json` limits it to the owner's own devices |
| Uploads (Try it, Decode) | size limit (200 MB), allowed formats only, one job at a time, files written only to the job's own folder |
| Job files | job IDs and file names must match fixed patterns; a decode job can read only its own input; input files are never served back |
| Text and keys | length limits; keys and message text are never written to disk |
| Server process | runs as a non-root user; the repository is mounted read-only, except `whistlecode/outputs/` and `runs/` |
| Errors | input errors return a short message; no stack trace reaches the browser |
| No login | intended for a demonstration; share the address only with the people who need it |

## Dependencies

- The server image pins every package (`deploy/requirements-serve.txt`), and `constraints.txt` pins everything else.
- CI's dependency audit (`pip-audit`) reports known vulnerabilities in both, on every push, as warnings on the run (`python tools/repo.py ci-report` lists them). It does not block; read it before every release and deployment.
- **State on 2026-11-22:** none of the 57 pins has a known advisory (OSV). The same morning eight had: anyio, certifi, cryptography, filelock, fsspec, pillow, pytest and setuptools; all were upgraded to fixed versions (OPS-7). The page exposed little of it: its uploads are audio files, which pillow never decodes. The running server picks up pillow 13 when its image is rebuilt (`project/RELEASES.md`, Deployment).
- A vulnerable package is upgraded like any other change: rewrite the lock, run the checks, log it, and redeploy.

## Data and privacy

The recordings are of animals and hold no personal data. The listening test (WC-R4) is anonymous and stores no personal data. Unpublished drafts and copyrighted papers are kept in `docs/private/`, which is never committed.
