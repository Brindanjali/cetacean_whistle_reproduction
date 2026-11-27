# Releases, deployment and monitoring

How a version is named and released, how the page is put online, and how we know it is up. Index of all systems: [README.md](README.md).

## Versions

One version for the whole repository, in [`pyproject.toml`](../pyproject.toml) (`[project] version`). The web server reports it at `/healthz`.

**Numbering** (`MAJOR.MINOR.PATCH`, as in [Semantic Versioning](https://semver.org)):

- **PATCH** (0.9.**1**): fixes only. No result, setting or interface changes.
- **MINOR** (0.**10**.0): new features, experiments or documents; old results still hold.
- **MAJOR** (**1**.0.0): a milestone you hand in, or a change that invalidates earlier results (new model, new data split).

`src/whistlepipe/__version__` ("1.0.0") is the preprocessing pipeline's own version, written into every dataset record. It is not the release version and changes only when the pipeline's output would change.

**Plan**

| Version | When | What |
|---|---|---|
| 0.9.0 | 2026-11-21 | First versioned release: the reproduction, WhistleCode campaign v1 and R0-R2, the page, and the engineering systems |
| 0.10.0 | 2026-11-22 | Apache 2.0 licence; CI fixes and `ci-report`; eight vulnerable packages upgraded (also in the server image) |
| 1.0.0 | 2026-11-27 | Code freeze, moved forward from 2026-11-29 for the project expo on 2026-11-28: the retold page (WEB-5, WEB-6), the epoch-150 paper evaluation (REP-1) and WC-R3's real wobble |

## Release procedure

1. **Changelog.** Move the `[Unreleased]` lines in [`CHANGELOG.md`](../CHANGELOG.md) under a new heading `## [X.Y.Z] - YYYY-MM-DD`, and add the comparison link at the bottom.
2. **Version.** Set `version = "X.Y.Z"` in `pyproject.toml`.
3. **Work log.** Log the release under today's date.
4. **Owner commits:** `git add CHANGELOG.md pyproject.toml WORKLOG.md`, then `git commit -m "Release vX.Y.Z"`.
5. **Check.** `python tools/repo.py release-check X.Y.Z` checks the version, the changelog section, a clean tree and an unused tag, then runs every check. It prints the tag commands.
6. **Owner tags and pushes:** `git tag -a vX.Y.Z -m "vX.Y.Z"`, `git push origin main`, `git push origin vX.Y.Z`. CI runs on the tag.
7. **GitHub release** (optional): on GitHub, Releases → "Draft a new release" → the tag, with the changelog section as the text.
8. **Deploy** if the page changed ([Deployment](#deployment)).

A released tag is never moved or deleted. A mistake gets a new PATCH release.

## Deployment

The page runs in Docker on the project laptop and reaches the internet through Tailscale Funnel. How to set it up: [`deploy/README.md`](../deploy/README.md).

**Checklist** (every deployment):

1. `python tools/repo.py check` passes on the commit being deployed.
2. The models in place match the registry: `python tools/repo.py checksums verify` (Try it needs both GMMs, Encode and Decode need the codebook and rhythm bank).
3. Restart or rebuild:
   - code or model files only: `docker compose -f deploy/docker-compose.yml restart app`;
   - `Dockerfile`, `requirements-serve.txt` or `constraints.txt` changed: `docker compose -f deploy/docker-compose.yml up -d --build`.
4. Wait until `docker compose -f deploy/docker-compose.yml ps` shows the app as `healthy` (up to 3 minutes while the models load).
5. `python tools/repo.py health https://whistle.<tailnet>.ts.net` returns UP with the expected version.
6. Open the page: the film plays, Try it analyses an example, Encode sends "HI" and Decode reads it back.
7. Update [What is live](#what-is-live) and log the deployment.

**Rollback:** `git checkout vX.Y.Z` (the last good release), then step 3. Model files are never overwritten (see [MODELS.md](MODELS.md)), so the old commit finds its own files.

### What is live

| Field | Value |
|---|---|
| Address | `https://whistle.<tailnet>.ts.net` (Tailscale Funnel, project laptop) and http://localhost:8000 |
| Version | Whatever is checked out: the container mounts the working tree read-only. Since 2026-11-27 (about 12:00): `main` at `ac7dbbf` and then the v1.0.0 release commit (version number 1.0.0 after the next restart), with WC-R3's sender (real wobble, D-032). Before that, from 2026-11-27: `main` at `9f91c3b` (version number 0.10.0), with the film's scene redrawn and Try it back on the page as 08 after Decode (WEB-6, D-027, D-028); from 2026-11-26 the branch `web-scene-v2` was checked out here, so its uncommitted work was live while it was being made. Before that, from 2026-11-26: `main` at `f5b794e` (version number 0.10.0), with the retold page (WEB-5: the film drawn from real records in WebGL, Encode and Decode after it, Try it on `model.html`); first live from the branch `web-retelling` at `e983ad4` the same day, untagged (D-025). It becomes v1.0.0 at the freeze. Before: `1613c18` (2026-11-24), v0.10.0 plus the security fixes BUG-2 to BUG-7 and BUG-13 |
| Models | Try it: Nyx (epoch 101) and Delphi (epoch 150). Encode/Decode: Nyx, codebook `cd322a02` |
| Access | Anyone with the address ("AllowFunnel": true) |
| Uptime | Only while the laptop is on, awake and running Docker Desktop |

## Monitoring

| Signal | How to read it |
|---|---|
| `GET /healthz` | 200 `ok` (ready), 200 `starting` (models loading), 503 `down` with the problem. Also gives the version, uptime and job queue |
| Docker healthcheck | `docker compose -f deploy/docker-compose.yml ps` shows `healthy` / `unhealthy` (checked every 60 s, after a 3-minute start) |
| Uptime log | `python tools/repo.py health URL --every 300` checks every 5 minutes and appends to `runs/health.log` (not in git) |
| Server logs | `docker compose -f deploy/docker-compose.yml logs --tail 200 app` |
| Job errors | `/api/wc/jobs/<id>` and `whistlecode/outputs/web/<id>/` keep each failed job's error |

**Watch it in the background** (Windows, from the repository root; the owner runs this once, and it checks every 5 minutes while signed in):

```
schtasks /Create /SC MINUTE /MO 5 /TN "whistle-health" /TR "cmd /c cd /d D:\ALL\cetacean_whistle_reproduction && python tools\repo.py health"
```

Remove it with `schtasks /Delete /TN "whistle-health" /F`. A DOWN line that lasts more than one check while the laptop is on is an incident ([INCIDENTS.md](INCIDENTS.md)).
