# Self-hosting: Docker + Tailscale Funnel

Serves the whole project page (the film, Encode, Decode and Try it) from your own computer in Docker, and puts
it on the internet at a fixed https address, `https://whistle.<your tailnet>.ts.net`. Free, with no card: Tailscale's
Personal plan is free for non-commercial use. Because the address is https, Record (the microphone) works on other
computers too. The steps are written for Windows with Docker Desktop, where they were tested.

**The address works only while your computer is on, awake and running Docker Desktop.** When it is off, visitors get a
connection error; the site comes back by itself when Docker Desktop starts again (both containers restart
automatically).

## What runs

| Container | Image | Job |
|---|---|---|
| `tailscale` | `tailscale/tailscale:v1.104.4` | joins your tailnet as the machine `whistle`, gets its https certificate, forwards port 443 to the app, and with Funnel opens it to the internet |
| `app` | `whistle-app:cpu` (or `:gpu`), built from `Dockerfile` | `python whistlecode/whistlecode.py serve` on port 8000, inside the `tailscale` container's network |

The image holds only Python and the packages in `requirements-serve.txt`, each of them and everything they pull in at its
version in the lock file, `constraints.txt` (the build reads only these two files of the repository:
`Dockerfile.dockerignore`). The repository is mounted read-only at
`/app`, so the container uses exactly the code, models (`models/`), page (`web/`) and sea recordings
(`encounter_214_audio/`, `encounter_276_audio/` and the noise cache) that are on disk. It writes only to
`whistlecode/outputs/` (WhistleCode jobs and new noise-cache files) and `runs/` (Try it jobs), as the local server does.

## Once: before the first start

1. **Docker Desktop**: start it and wait until it says the engine is running. To have the site come back after a
   restart, turn on Settings → General → "Start Docker Desktop when you sign in to your computer".
2. **Tailscale account**: sign in at https://login.tailscale.com with Google, GitHub or Microsoft. This creates your
   tailnet. You do not need the Tailscale app on your computer: the container is its own Tailscale machine.
3. **HTTPS certificates**: admin console → DNS → make sure MagicDNS is on, then press "Enable HTTPS". Funnel needs both.
4. **Funnel permission**: admin console → Access controls. New tailnets already have this in the policy file; add it if
   it is missing:

   ```json
   "nodeAttrs": [{ "target": ["autogroup:member"], "attr": ["funnel"] }]
   ```

## Start

From the repository root (the first build downloads about 1 GB: the Python image, CPU PyTorch and the packages):

```
docker compose -f deploy/docker-compose.yml up -d --build
```

The first time, the `tailscale` container waits for you to sign it in. Follow its log live and open the link as soon as
it appears: **each link works for about a minute**. Then the container gives up (`context deadline exceeded`), Docker
restarts it and it prints a new link. Approve the machine on the page the link opens, then press Ctrl+C to stop
following the log (the container keeps running):

```
docker compose -f deploy/docker-compose.yml logs -f tailscale
```

With no hurry at all: put a one-off auth key in `deploy/.env` instead (admin console → Settings → Keys → Generate auth
key; see `.env.example`), run `up -d` again, and delete the key from `.env` once the machine is signed in. Then, in the
admin console → Machines → `whistle` →
⋯ → **Disable key expiry**, or the machine signs out after 180 days.

Check that the app is ready (it prints `Try it : ...` and `messages: ready` once the models are loaded):

```
docker compose -f deploy/docker-compose.yml logs -f app
```

- On your computer: http://localhost:8000
- Everyone else: `https://whistle.<your tailnet>.ts.net`; the exact name is on the Machines page. The first visit can
  take up to a minute while the certificate is issued, and a new Funnel name can take a few minutes to be found.

## Speed over Funnel

Funnel carried about 1-1.6 Mbit/s per connection when measured on 2026-11-20, on a line with about 32 Mbit/s of upload,
so the limit was Tailscale's relay, not the internet line. The 4K film clips need 17-30 Mbit/s, so internet visitors
get the 720p copies in `web/mediaweb/` (under 0.9 Mbit/s), and the server's own computer keeps the 4K files. Without the copies the page falls
back to the 4K files, which do not play at that speed (visitors see the posters); `web/README.md` ("Video and example
files") has the two commands that make them. Uploads in Try it and Decode cross the same relay and may be as slow (not
measured).

## Use the NVIDIA GPU (optional)

The CPU image is small and works everywhere; Try it and Decode are faster on the GPU. Docker Desktop passes an NVIDIA
GPU through WSL 2 with the normal Windows driver. The CUDA build of PyTorch adds several GB to the download:

```
docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.gpu.yml up -d --build
```

Use the same two `-f` options for the other commands while you run the GPU version.

## Everyday commands

| What | Command |
|---|---|
| stop (the address stops working) | `docker compose -f deploy/docker-compose.yml down` |
| start again | `docker compose -f deploy/docker-compose.yml up -d` |
| new model files or code (restart the app only) | `docker compose -f deploy/docker-compose.yml restart app` |
| a changed `requirements-serve.txt`, `constraints.txt` or `Dockerfile` | `docker compose -f deploy/docker-compose.yml up -d --build` |
| sign the machine out of Tailscale for good | `docker compose -f deploy/docker-compose.yml down -v` (deletes the saved sign-in) |

Port 8000 on your computer is taken while the containers run. To run `python whistlecode/whistlecode.py serve` at the same
time, set `LOCAL_PORT=8001` in `deploy/.env`.

## Who can open it

With `"AllowFunnel": true` in `tailscale/serve.json`, **anyone who has the address can use the page**. The server has no
login, takes uploads up to 200 MB and runs one job at a time (it refuses oversized requests and new jobs when six are
waiting; limits in `.github/SECURITY.md`), so share the address only with the people you want. To
keep the page to your own devices (those signed in to your tailnet), set `"AllowFunnel"` to `false`. The container
applies the change by itself; if not, run `docker compose -f deploy/docker-compose.yml restart tailscale`.

The key and the message typed into Encode and Decode travel over https and are never written to disk; a decoded message is
kept in memory until its job is pruned or the server restarts (see `whistlecode/wcode/web.py`).
