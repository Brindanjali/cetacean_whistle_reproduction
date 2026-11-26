# Webpage — Falsetto

One page, `index.html`: a scroll-driven film about whistles, then **Encode** (hide a message in whistles), **Decode**
(read it back with the key) and **Try it**, the whistle model on its own (Nyx or Delphi): upload a recording, see every
whistle found, hear the model's recreation and new whistles of the same type, or generate without a recording. Desktop
only, by design. (`model.html`, Try it's own page during WEB-5, now leads to `#try`.)

Status: retold as Falsetto ([`PLAN.md`](PLAN.md), WEB-5, done 2026-11-26, in v1.0.0). The film's data comes from real
records (`film/`, `export-film`); the research section is one WebGL 2 scene drawn only from `film/`
(Listen → Learn → Speak → Hide → Hear); Encode and Decode follow the film; Try it follows them (back on the page since
2026-11-26); the footer states the limits.

## Run it

With the inference API (from the project root):

```
python whistle.py serve
```

Then open http://127.0.0.1:8000 in Chrome or Edge on a desktop (Try it: http://127.0.0.1:8000/#try). The film
alone (no API) still runs with `python web/serve.py` (http://localhost:5178); Try it then shows only the pre-rendered
examples, and Encode and Decode say how to start their server.

Both servers answer HTTP Range requests, which the browser needs to seek inside the video files. Python's built-in
`http.server` does not, so the return shot would start from the wrong frame.

## Encode and Decode (WhistleCode)

Right after the film (the tide brings in Encode), two places hide a text message in whistles and read it back:

- **04 · Encode:** type a message and a key. Six stations show each step with the real values (letters to bits, checksum, key
  scramble, spare whistles, whistles, real rhythm) and one tile per whistle. "Hide it" makes the sound the sender plays, and
  "Through the sea" mixes it into a real sea recording.
- **05 · Decode:** drop in a recording (or use one made above) and type the key. The decoder gets only the audio and the key.
  For a file made above, the page afterwards checks each whistle against the sender's record and says so. **Record** listens
  with the microphone instead: press it, play the message near the computer, press Stop, and the recording goes straight to
  the decoder (with the key already typed, it reads it at once). The microphone's sound is kept as it is: no echo cancelling,
  noise suppression or automatic gain.

They need the WhistleCode server, which also serves everything else, Try it included:

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

It prints an address such as `https://192.168.1.20:8000` for the other computer. Its browser warns once that the
certificate is not trusted (the server's computer made it for itself and keeps it in `whistlecode/outputs/web_tls/`):
choose Advanced, then Proceed. Windows may ask whether Python may use the network; allow private networks only. While it runs,
anyone on the network can open the page.

Then: write the message in Encode on one computer, press Hide it and play the sound (or its downloaded WAV) aloud; on the
other computer type the same key in Decode, press Record, and press Stop when the sound has finished. The air between two
laptops is a new channel for the decoder (room echoes, speaker and microphone limits) and has not been measured yet.

### On the internet: Docker and Tailscale Funnel

`deploy/` runs the same server in Docker and gives it a fixed https address, `https://whistle.<tailnet>.ts.net`, while
the computer running it is on. It is free and needs no card. Steps in `deploy/README.md`; in short:

```
docker compose -f deploy/docker-compose.yml up -d --build
```

## The model files

Nothing in `web/` changes after training. The server reads the files from where the training commands write them:
`models/vaegmm/V1_L64_b1e-4_critic_E191/checkpoints/last.pt` (`train-vae --experiment V1`, written every epoch; the page
says so while it is a mid-training checkpoint) and
`.../gmm_K3000/gmm.npz` (`fit-gmm --experiment V1`), optionally `.../gmm_K3000/component_features.npy`
(`vae-eval components`) for the Table 3 conditions. `python whistle.py model-status` checks them; a running server
picks them up on restart (or `POST /api/reload-model`, once `[server] allow_reload = true` in `configs/inference.toml`;
it is off because anyone who can open the page could call it). Re-run `python whistle.py export-web` afterwards so the
pre-rendered examples include the model's output too.

### Choosing the model

Try it can offer several trained models side by side. They are listed in `configs/inference.toml` under `[[models]]`
(the first is the default); each entry is `[model]` with its own keys replaced. Today:

| id | shown as | checkpoint | can do |
|---|---|---|---|
| `model1` | Nyx | epoch 101 of 150, `V1_L64_b1e-4_critic_E191/checkpoints/last.pt` (= `[model]`) | recreate, families, imagine, kinds |
| `model2` | Delphi | epoch 150 of 150, `V1_L64_b1e-4_critic_E191_epoch150/checkpoints/final.pt` | recreate, families, imagine, kinds |

To rename one, change its `name` (keep the `id`) and restart the server. Each model has its own mixture, fitted on its own
latents: Delphi's was made with `python whistle.py fit-gmm --experiment V1_L64_b1e-4_critic_E191_epoch150` and
`python whistle.py vae-eval components --experiment V1_L64_b1e-4_critic_E191_epoch150` (checked with
`python post_training/gmm_check.py --run-id V1_L64_b1e-4_critic_E191_epoch150`). A model without its mixture still
recreates; the page then shows families and Imagine as off. `python whistle.py model-status --all` checks every model.

On the page, a single segmented control under the heading ("Model") chooses the model (click, or the arrow keys). Each option
shows the model's name, its epoch, and a hairline for how far through its planned training it got; a glass thumb glides to
the chosen one. A small twin sits beside the Imagine panel's heading. Every request carries the chosen model (`model` in
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
17 Mbit/s, and Tailscale Funnel (`deploy/`) gave about 1-1.6 Mbit/s per connection (measured 2026-11-20). Visitors on
the server's own computer or local network keep the 4K files; `?video=4k` or `?video=web` in the address overrides the
choice. Make the
copies from the 4K clips, from `web/` (about 3.4 MB and 0.9 MB, under 0.9 Mbit/s):

```
ffmpeg -i media4k/whale.mp4 -an -vf "scale=1280:720:flags=lanczos,format=yuv420p" -c:v libx264 -preset slow -profile:v high -crf 26 -maxrate 900k -bufsize 1800k -g 30 -keyint_min 30 -sc_threshold 0 -movflags +faststart mediaweb/whale.mp4
ffmpeg -i media4k/dolphins.mp4 -an -vf "scale=1280:720:flags=lanczos,format=yuv420p" -c:v libx264 -preset slow -profile:v high -crf 26 -maxrate 900k -bufsize 1800k -g 30 -keyint_min 30 -sc_threshold 0 -movflags +faststart mediaweb/dolphins.mp4
```

Without them, an internet visitor's page falls back to the 4K files. Without the clips the page still runs and shows the posters
(`media4k/*.jpg`, in git). `web/data/` (examples) is generated by `export-web`.

## The film's data (`film/`)

The film draws only from real records, exported once so it runs without a server (`web/PLAN.md`, P1):

```
python whistlecode/whistlecode.py export-film
```

It writes `film/film.json` (provenance, then one block per beat: one encounter-191 training image, the codebook's 16
shapes, one real send of "MEET AT DAWN" under the public key `reef-42`, and that send decoded in encounter-214 sea noise
at 10 dB), `film/learn.bin` (all 63,490 latents on three principal axes, with their mixture components) and
`film/hear_it.wav` (one data whistle cut from the send). Nothing is picked by hand: the noise seed is the first whose
decode is exact. These files are small (about 600 KB) and in git; `whistlecode/tests/test_wc_film.py` checks them, and
fails if the model or codebook changed since the export. Settings: `whistlecode/config.toml` `[film]`.

## What's where

- `index.html`: the four movements (Ocean, Listen, Research, Return), their copy, then the lab: Encode, Decode, Try it
- `model.html`: a redirect to Try it (`#try`), its own page during WEB-5
- `shots.js`: the edit: shot windows, depth curve, text and visualisation timings (all in scroll position)
- `app.js`: the film controller: playback, cross-fades, the text layer, "Hear it" (plays `film/hear_it.wav`); drives the
  research scene and parks the film (videos paused, layer hidden) while the lab covers the screen
- `water.js`: the water below the film: the tide the film ends under, and the sea (one WebGL shader)
- `scene.js`: the research section as one WebGL 2 scene on `#gl`, labels and letters on `#sig` (Listen → Learn → Speak →
  Hide → Hear, one continuous camera), drawn only from `film/`; without WebGL 2 the words stand over still water
- `gl.js`: the scene's small WebGL 2 helpers (programs, matrices, fine lines with mitred joins, thick lines as instanced
  quads, a GPU timer); no library
- `styles.css`: all styling; `serve.py`: the film-only server with HTTP Range support
- `lab.js`: Try it (`#try`): model selector, upload, job progress, overview with clickable whistle boxes, per-whistle cards, generation;
  "Slow ×2" and the pitch shift re-synthesise the contour in the browser with sonify.py's rules
- `message.js`: Encode and Decode (WhistleCode): stations, whistle tiles, close-up spectrograms, playback
- `media4k/`, `fonts/`: local assets (see `CREDITS.md`); `data/`: exported examples for Try it; `film/`: the film's data

## Playback notes

On Windows the browser decodes video on the same GPU thread that draws the page, so decoder work for a clip that is off
screen costs frames on screen. `app.js` therefore prerolls every later clip while the opening frame holds still (at
most 1.5 s, typically about 0.35 s), folds the depth shade into the planes' opacity instead of drawing a full-screen
layer, and hides the plot canvas and the text veil whenever they are empty. Measured on a test laptop with integrated
graphics (AMD Radeon 610M, 2560×1600 display at 240 Hz), these changes removed every frame stall during a fast scroll
from the top and through the whole film: the 95th-percentile frame time fell from 16.6–20.9 ms to 4.3 ms.
