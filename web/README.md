# Webpage — Learning the shape of a whistle

A scroll-driven film about how false killer whale whistles become data, followed by "Try it": upload a recording, see
every whistle found, hear the model's recreation and new whistles of the same type, or generate without a recording.
Desktop only, by design.

Status: the film's research section (Listen → Learn → Imagine) is a hand-made illustration and is labelled as such.
"Try it" runs the real pipeline; its model panels fill in once the trained files exist (see below).

## Run it

With the inference API (from the project root):

```
python whistle.py serve
```

Then open http://127.0.0.1:8000 in Chrome or Edge on a desktop. The film alone (no API) still runs with
`python web/serve.py` (http://localhost:5178); "Try it" then shows only the pre-rendered examples.

Both servers answer HTTP Range requests, which the browser needs to seek inside the video files. Python's built-in
`http.server` does not, so the return shot would start from the wrong frame.

## Encode and Decode (WhistleCode)

Below "Imagine new voices", two more places hide a text message in whistles and read it back:

- **05 · Encode:** type a message and a key. Six stations show each step with the real values (letters to bits, checksum, key
  scramble, spare whistles, whistles, real rhythm) and one tile per whistle. "Hide it" makes the sound the sender plays, and
  "Through the sea" mixes it into a real sea recording.
- **06 · Decode:** drop in a recording (or use one made above) and type the key. The decoder gets only the audio and the key.
  For a file made above, the page afterwards checks each whistle against the sender's record and says so. **Record** listens
  with the microphone instead: press it, play the message near the computer, press Stop, and the recording goes straight to
  the decoder (with the key already typed, it reads it at once). The microphone's sound is kept as it is: no echo cancelling,
  noise suppression or automatic gain.

They need the WhistleCode server, which also serves everything else on the page, Try it included:

```
python whistlecode/whistlecode.py serve
```

With `python whistle.py serve` or `python web/serve.py` the two places say how to start it and stay still. The routes are in
`whistlecode/wcode/web.py`; the page code is `message.js`.

### Two computers: play on one, record on the other

Browsers allow the microphone only on https pages or on the computer that runs the server, so serve the network over https:

```
python whistlecode/whistlecode.py serve --lan
```

It prints an address such as `https://192.168.18.39:8000` for the other computer. Its browser warns once that the
certificate is not trusted (this computer made it for itself and keeps it in `whistlecode/outputs/web_tls/`): choose
Advanced, then Proceed. Windows may ask whether Python may use the network; allow private networks only. While it runs,
anyone on the network can open the page.

Then: write the message in Encode on one computer, press Hide it and play the sound (or its downloaded WAV) aloud; on the
other computer type the same key in Decode, press Record, and press Stop when the sound has finished. The air between two
laptops is a new channel for the decoder (room echoes, speaker and microphone limits) and has not been measured yet.

### On the internet: Docker and Tailscale Funnel

`deploy/` runs the same server in Docker and gives it a fixed https address, `https://whistle.<tailnet>.ts.net`, while
this computer is on. It is free and needs no card. Steps in `deploy/README.md`; in short:

```
docker compose -f deploy/docker-compose.yml up -d --build
```

## The model files

Nothing in `web/` changes after training. The server reads the files from where the training commands write them:
`models/vaegmm/V1_L64_b1e-4_critic_E191/checkpoints/last.pt` (`train-vae --experiment V1`, written every epoch; the page
says so while it is a mid-training checkpoint) and
`.../gmm_K3000/gmm.npz` (`fit-gmm --experiment V1`), optionally `.../gmm_K3000/component_features.npy`
(`vae-eval components`) for the Table 3 conditions. `python whistle.py model-status` checks them; a running server
picks them up on restart or `POST /api/reload-model`. Re-run `python whistle.py export-web` afterwards so the
pre-rendered examples include the model's output too.

### Choosing the model

Try it can offer several trained models side by side. They are listed in `configs/inference.toml` under `[[models]]`
(the first is the default); each entry is `[model]` with its own keys replaced. Today:

| id | shown as | checkpoint | can do |
|---|---|---|---|
| `model1` | Model 1 | epoch 101 of 150, `V1_L64_b1e-4_critic_E191/checkpoints/last.pt` (= `[model]`) | recreate, families, imagine, kinds |
| `model2` | Model 2 | epoch 150 of 150, `V1_L64_b1e-4_critic_E191_epoch150/checkpoints/final.pt` | recreate (its GMM is not fitted yet) |

To rename one, change its `name` (keep the `id`) and restart the server. Model 2 gains whistle families and "Imagine" once
its own mixture exists: `python whistle.py fit-gmm --experiment V1_L64_b1e-4_critic_E191_epoch150`, then
`python whistle.py vae-eval components --experiment V1_L64_b1e-4_critic_E191_epoch150`, then a restart.
`python whistle.py model-status --all` checks every model.

On the page, "The listener" under the heading chooses the model (click, or the arrow keys); a small twin sits in the
Imagine panel. Each option draws the training run its checkpoint came from (reconstruction loss per epoch, one epoch axis
for all), so a model stopped early ends part-way along. Every request carries the chosen model (`model` in
`/api/analyze`, `/api/analyze-example` and `/api/generate`; an unknown one is refused with 400), each result names the model
that made it, and a recording on screen can be heard again by the other model with one click. The choice is remembered
in the visitor's browser. With one model, or without the server, the selector does not appear.

## Video and example files

The two 4K clips (`media4k/whale.mp4`, `media4k/dolphins.mp4`, about 100 MB) are not in git. Download the 4K
originals from the links in `CREDITS.md` (Pixabay 244188, a 60 fps clip, and Pexels 5743314) and encode them from
`web/` with these commands, which give the settings recorded there:

```
ffmpeg -i whale_4k60.mp4 -an -filter_complex "[0:v]scale=3840:2160,setpts=2*PTS,fps=30,split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0,format=yuv420p[v]" -map "[v]" -c:v libx264 -profile:v high -crf 18 -g 30 -keyint_min 30 -sc_threshold 0 -movflags +faststart media4k/whale.mp4
ffmpeg -i dolphins_4k.mp4 -an -vf "scale=3840:2160,format=yuv420p" -c:v libx264 -profile:v high -crf 18 -g 30 -keyint_min 30 -sc_threshold 0 -movflags +faststart media4k/dolphins.mp4
```

The first plays the 60 fps clip at half speed (every frame real) and appends it reversed, so it loops without a seam;
`reverse` holds the clip in memory (several GB at 4K).

Visitors over the internet get 720p copies in `mediaweb/` instead (`app.js`, `VIDEO`): the 4K whale needs about
17 Mbit/s, and Tailscale Funnel (`deploy/`) gave about 1-1.6 Mbit/s per connection (measured 2026-11-20). This computer
and its local network keep the 4K files; `?video=4k` or `?video=web` in the address overrides the choice. Make the
copies from the 4K clips, from `web/` (about 3.4 MB and 0.9 MB, under 0.9 Mbit/s):

```
ffmpeg -i media4k/whale.mp4 -an -vf "scale=1280:720:flags=lanczos,format=yuv420p" -c:v libx264 -preset slow -profile:v high -crf 26 -maxrate 900k -bufsize 1800k -g 30 -keyint_min 30 -sc_threshold 0 -movflags +faststart mediaweb/whale.mp4
ffmpeg -i media4k/dolphins.mp4 -an -vf "scale=1280:720:flags=lanczos,format=yuv420p" -c:v libx264 -preset slow -profile:v high -crf 26 -maxrate 900k -bufsize 1800k -g 30 -keyint_min 30 -sc_threshold 0 -movflags +faststart mediaweb/dolphins.mp4
```

Without them, an internet visitor's page falls back to the 4K files. Without the clips the page still runs and shows the posters
(`media4k/*.jpg`, in git). `web/data/` (examples) is generated by `export-web`.

## What's where

- `index.html`: the four movements (Ocean, Listen, Research, Return), their copy, and the "Try it" section
- `shots.js`: the edit: shot windows, depth curve, text and visualisation timings (all in scroll position)
- `app.js`: the film controller: playback, cross-fades, the text layer, the "Hear it" tone; drives the research scene
  and parks the film (videos paused, layer hidden) while "Try it" covers the screen
- `scene.js`: the research section's 3D scene on the `#sig` canvas (Listen → Learn → Imagine, one continuous camera;
  hand-made, not model output)
- `styles.css`: all styling; `serve.py`: the film-only server with HTTP Range support
- `lab.js`: "Try it": model selector, upload, job progress, overview with clickable whistle boxes, per-whistle cards, generation;
  "Slow ×2" and the pitch shift re-synthesise the contour in the browser with sonify.py's rules
- `audio-engine.js`: the illustrative whistle contours and tone of the film (not the model)
- `message.js`: 05 · Encode and 06 · Decode (WhistleCode): stations, whistle tiles, close-up spectrograms, playback
- `media4k/`, `fonts/`: local assets (see `CREDITS.md`); `data/`: exported examples

## Playback notes

On Windows the browser decodes video on the same GPU thread that draws the page, so decoder work for a clip that is off
screen costs frames on screen. `app.js` therefore prerolls every later clip while the opening frame holds still (at
most 1.5 s, typically about 0.35 s), folds the depth shade into the planes' opacity instead of drawing a full-screen
layer, and hides the plot canvas and the text veil whenever they are empty. On a 2560×1600, 240 Hz display driven by a
Radeon 610M this removed every frame stall measured during a fast scroll from the top (95th-percentile frame time
16.6–20.9 ms → 4.3 ms) and through the whole film.
