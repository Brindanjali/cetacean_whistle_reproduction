# Page retelling plan (WEB-5)

**Status:** approved by the owner 2026-11-26 (D-025). Started 2026-11-26, at the owner's request, on the branch `web-retelling`, so `main` stays ready for the v1.0.0 code freeze (29 Nov 2026). The branch merges after the freeze and ships as v1.1.0 (`project/RELEASES.md`: new features, old results still hold). It carries out the page story of WC-R7 (Listen → Learn → Speak → Hide → Hear) and includes WEB-2 (real model output in the film). Desktop only (D-015); controls stay minimal, with no explanatory panels.

`[DECISION]` marks a choice this plan makes. The main ones are recorded together as [D-025](../project/DECISIONS.md#d-025); the rest stay here.

## Why

The page still tells the whistle model's story, while the project is now Falsetto, the message system (D-024):

- **The message system is at the bottom.** Before Encode, a visitor scrolls through about 9 screens of film and then the whole Try it lab. Encode is the 7th stop in the header.
- **The page names the old project.** The header mark reads "Whistle VAE-GMM", the tab title's subtitle is "learning the shape of a whistle", and the header links walk through the model.
- **The research beats (01 Listen, 02 Learn, 03 Imagine) end with the model.** In Falsetto the model is one step, the sender's voice. The scene is also hand-drawn (WEB-2).
- **Try it gets in the way.** It is a tool for the whistle model. Its model selector suggests a choice the message system does not have (WhistleCode runs on epoch 101 only). Its examples are stale (WEB-1), and most of the public routes belong to it (BUG-2 to BUG-5, WEB-4).
- **The page never states its limits.** It makes the hiding claim, but nowhere says "simulation only" or that a classifier can still tell the coded shapes from real ones. The README does both (D-023, D-024).

What already fits stays: the ocean opening ("Sound never fades… farther than any light can reach" is why underwater messages go by sound), "In the open blue, a name is a whistle" (animals already carry information in whistles), the coda "Now you hear it differently", and the whole visual language.

## The story

One continuous film, then the two tools. The research beats 01-05 are one 3D scene drawn with WebGL ([The 3D scene](#the-3d-scene)); the ocean opening and the return stay as video. The words for each beat are short: a two-line heading and at most two sentences. The gist below is not final copy.

| Beat | Gist of the words | On screen | Real data |
|---|---|---|---|
| Ocean (keep) | The sea is never silent. Could a machine whistle back, and say something only one listener understands? | Whale footage, as now | – |
| Dive (keep) | Light fades; sound carries | Footage, as now | – |
| Listen (keep) | In the open blue, a name is a whistle | Dolphin footage, as now | – |
| **01 · Listen** | A whistle rises out of the sea's hiss; seen from above, it is a line | The sound landscape rises and tips over, as now, but as a mesh built from a real spectrogram patch, with its real contour as the glowing ridge | One encounter-191 training image (0.68 s, ±6 kHz) and its contour |
| **02 · Learn** | 63,490 false killer whale whistles; look-alikes gather into families | The camera orbits a cloud of all 63,490 whistles, one point each, with families as soft colours | All 63,490 latent means of the epoch-101 model, projected to 3D; their GMM components |
| **03 · Speak** | Of 3,000 families, the sender keeps 16 it can say clearly. Each whistle is one of 16 shapes at one of 4 pitches: 6 bits | 16 families pull forward out of the cloud and unfold into ribbons. They settle into a 16 × 4 lattice, shape across and pitch as height: the 64 letters as one object | The 16 codebook components and their mean contours (`codebook.npz`) |
| **04 · Hide** | The message goes out among real whistles, at the moments real animals called | The camera drops onto a river of time running into the distance. Every sound is a small ribbon at its own pitch height, and data whistles, cover whistles and clicks look the same | The sender's record of one real send of the example message |
| **05 · Hear** | Only the key knows where to look. Without it, this is just whales | The key's whistles rise out of the river, fly forward and resolve into the letters of the message | The receiver's output for that send, heard through real sea noise |
| Return (keep, new last line) | Now you hear it differently. Your turn: hide a message | Whale footage returns | – |

The example message is "MEET AT DAWN", the same text Encode starts with, under a fixed key, `reef-42`. `[DECISION]` Encode keeps its random keys.

**Hear it.** The button moves from Imagine to Speak. It plays a real data whistle made by WhistleCode's own synthesiser: the sound a sender actually plays. The note "Illustration · drawn by hand, not by the model" goes. `[DECISION]` If a beat still shows anything drawn by hand, the same note stays on that beat.

## The 3D scene

The research beats (01-05) are one continuous camera move through one 3D scene, as today. As today, every frame is a pure function of the scroll position. What changes is how it is drawn.

- **WebGL instead of a 2D canvas.** Today's `scene.js` projects 3D by hand and draws every point and line one call at a time on a 2D canvas, which is why the cloud would need a cap of about 1,500 points. With WebGL the graphics chip draws all 63,490 points in one call, and fog, additive glow and ribbons with thickness come almost free. On screen, 63,490 means 63,490 points.
- **No library.** `[DECISION]` The scene needs points, ribbons (triangle strips, drawn instanced) and one 128 × 128 landscape mesh, with fog and additive blending. Hand-written WebGL is enough, and the page already has some: the sea behind the lab (`lab.js`, `setupSea`). Three.js would earn its place only if lit, solid models or post-processing were wanted.
- **WebGL 2.** `[DECISION]` The page targets desktop Chrome and Edge only (D-015), which all have it, and it draws instanced shapes without an extension.
- **Layers.** A new `<canvas id="gl">` sits in `.world`, under `#sig`. `#sig` stays a 2D canvas for the labels and the shading behind the text column. Each layer is hidden while empty, as `app.js` does today.
- **Loading.** Shaders are compiled and the buffers uploaded during the preroll, while the opening frame holds still (`app.js`). The first research frame never waits for them.
- **Fallbacks.** `[DECISION]`
  - With reduced motion, the scene draws each beat's final pose, and the beats cross-fade without camera moves.
  - Without WebGL, or after a lost context, the beats show their words over the still water, as today's static fallback does.
  - No pre-rendered stills need to be kept in step with the data.
- **Not used.** `[DECISION]`
  - Computer-made 3D whales: next to real 4K footage they look fake, and every picture in the scene comes from data.
  - Pre-rendered 3D video: scroll drives every frame, and seeking video stutters on an integrated graphics chip, which is why the film never scrubs its clips.

## The page after the film

- **Order:** film → **06 · Encode** (with Through the sea) → **07 · Decode** (with Record) → footer. `[DECISION]` Numbering continues from the film.
- **Header:** the mark reads "Falsetto". The links are Listen · Learn · Speak · Hide · Hear · Encode · Decode. The tab title becomes "Falsetto — messages hidden in whale whistles".
- **Try it moves to its own page,** `web/model.html` ("The whistle model"), linked from the footer. It keeps the Nyx/Delphi selector, since that choice belongs to the model. `[DECISION]` This keeps it for readers of the model's results without putting it in the way of the story. Its routes stay public as today; WEB-4 still applies.
- **Footer:** credits as now (Park et al. as the basis of the whistle model, NOAA recordings, footage), plus one line on the limits: "Tested in simulation only; no message has been played into water. A trained classifier can still tell the coded whistle shapes from real ones." The 0.68 s image note moves to `model.html`.

## Real data for the film: `export-film`

The film must run without a server (`web/serve.py`, a static host), so its data is exported once to `web/film/`. These files are small (under 1 MB in total), so they go in git, unlike `web/data/`. `[DECISION]`

New command: `python whistlecode/whistlecode.py export-film` (code in `whistlecode/wcode/film.py`), writing `web/film/film.json`, `web/film/learn.bin` and a few short WAVs:

- **`listen`:** one training image from encounter 191, as 8-bit levels, with its contour. The image is a member of the codebook component that Speak follows, so the whistle you watch rise is the one that becomes a letter.
- **`learn`:** all 63,490 latent means, projected to 3D by PCA, with each point's GMM component. They go in `learn.bin`: 16-bit positions and a 16-bit component per point, about 0.5 MB, loaded straight into a WebGL buffer. `film.json` holds the PCA basis, the scale, and the 16 codebook components to flag.
- **`speak`:** the 16 codebook contours, the signature contour (`contour`, `contour_len`, `hop_s`) and the 4 pitches of the pool.
- **`hide`:** from one real send of the example message (`run_send`): every sound's start, length and pitch, and its role (data, cover or click). Each data whistle also records its bits and letters (`frame_info`).
- **`hear`:** that send mixed into encounter-214 sea noise at 10 dB (the development noise; 276 stays for campaigns), then decoded: what was detected, which slots the key opened, how many symbols Reed–Solomon repaired, and the text read.
- **`provenance`:** the SHA-256 of the checkpoint, GMM, latents and codebook, the key, the nonce, the noise seed and the export time.

**Choosing the noise seed honestly.** `[DECISION]` The rule is set in advance: the first seed from 0 whose decode is exact. The rule, and the seeds it skipped, go in `provenance`. The film shows one demonstration, and its words claim no success rate.

**Test.** `whistlecode/tests/test_wc_film.py` checks the JSON's shape, and checks that its provenance hashes match `codebook.json` and `project/MODELS.md`. Then a later codebook change (WC-R3) cannot leave the film showing stale shapes unnoticed.

## Changes by file

| File | Change |
|---|---|
| `web/index.html` | Identity strings; header links; five research beats instead of three; the `#gl` canvas; new coda line; the lab starts at Encode; Try it markup leaves; footer limits line |
| `web/shots.js` | `TEXT`, `VIZ` and `STOPS` for five beats. The research section grows from `--s:4` to about `--s:6`, so the whole film is about 11 screens. `[DECISION]` Each beat gets about the length a beat has today |
| `web/scene.js` | Rewritten for WebGL. It reads `film/film.json` and `film/learn.bin`. A real ridge (Listen) and a real cloud (Learn), then new phases: `pick` and `lattice` (Speak), `river` (Hide), `reveal` (Hear). The hand-made `FAMILIES` leave. Same rules as now: one camera, and every frame a pure function of scroll. Labels are still drawn on `#sig` |
| `web/gl.js` | New: the small WebGL helpers (shaders, buffers, ribbons, context loss) |
| `web/app.js` | The lab anchor `#try` becomes `#lab`, and the parking and index logic follow it. It shows and hides `#gl`, prepares the scene during the preroll, and falls back when WebGL is missing. "Hear it" plays the exported WAV |
| `web/audio-engine.js` | Removed, if nothing else uses it once "Hear it" plays a file |
| `web/lab.js` | Split. `setupSea` and `setupTide` (the arrival under the film) move to a new `web/water.js`, loaded by both pages. Try it stays in `lab.js`, loaded only by `model.html` |
| `web/model.html` | New: the Try it markup, a slim header back to the film, the old footer note |
| `web/message.js` | Section numbers; the Encode heading becomes the arrival heading (the tide's text) |
| `web/styles.css` | Styles for the new beats; the arrival heading on Encode |
| `whistlecode/wcode/film.py`, CLI | `export-film`, as above |
| Servers, Docker | No change: both servers serve the whole `web/` folder (`server.py` mounts it with `StaticFiles`, and `whistlecode serve` mounts that app), and Docker mounts the repository read-only |

## Before it starts

1. The v1.0.0 freeze has passed. *(2026-11-26: replaced by working on the branch `web-retelling`, which merges after the freeze.)*
2. **WC-R7, "reconcile the data-whistle share (one in four vs a third)",** is done. The Hide beat draws that share, so it must be settled first. *(Done 2026-11-26: one in four bank whistles can carry data; about a third of a played message does, 33-36 % in `RESULTS.md` section 6.)*
3. Each number the film states has a row in `project/TRACEABILITY.md`: 63,490 whistles, 3,000 families, 16 shapes, 4 pitches, 6 bits. Kept to these few. `[DECISION]`
4. Copy rule from WC-R7a: no "no two whistles alike" or "a brand-new voice every time". The samples are tempered (tau 0.5), and a whistle that fails its self-check falls back to its type's mean shape.

## Phases

| Phase | Work | Size | Done when |
|---|---|---|---|
| P1 | `export-film` and its test; `web/film/` committed | 1 day | The test passes; `film.json` hashes match the codebook |
| P2 | Page structure: identity strings, header, order, `model.html`, `water.js` split, footer, coda. The old scene still runs | 1 day | Both pages work with `whistlecode serve`, `whistle.py serve` and `web/serve.py`; the page can ship at this point |
| P3 | Scene in WebGL: first the renderer and its fallbacks, then the real ridge and cloud, then Speak, Hide and Hear | 4 days | Every beat draws from `film/`; nothing hand-drawn is left without the note |
| P4 | Words for every beat and the footer | ½ day | Every number traced; WC-R7a rules kept |
| P5 | Checks (below) | ½–1 day | All checks pass, with proof (screenshots and bench numbers) |
| P6 | Records, version 1.1.0, Docker rebuild, deployment checklist | ½ day | The live page runs the new version; the owner commits, tags and pushes |

## Checks

- **Speed:** on the test laptop (Radeon 610M, 2560×1600, 240 Hz), use the headless Chrome bench, alternating runs against the current page. Through the whole film, the 95th-percentile frame time stays at or under 6 ms (today 4.3 ms), with no frame over 33 ms. If the scene costs too much, the glow and point size come down first, then the cloud thins to a fixed subset, and the words then say "a sample of".
- **Without WebGL:** with WebGL turned off in the browser, and after a forced context loss (`WEBGL_lose_context`), the film shows its words over still water and nothing else breaks.
- **Without a server:** with `web/serve.py`, the film runs fully, and Encode and Decode say how to start the server.
- **With the servers:** with `whistlecode serve`, and in Docker over Tailscale Funnel (720p video), Encode, Decode, Record and `model.html` work.
- **Reduced motion:** each beat shows a still frame.
- **Browsers:** Chrome and Edge on desktop.
- **Repository:** `python tools/repo.py check` passes; the Definition of Done in `project/WORKFLOW.md`.

## Risks

- **The projected cloud may look like one blob.** A 64-D latent space need not show families in 3 PCA axes. The fallback is a linear projection fitted to separate the 16 codebook components (Fisher discriminant over their members). It is still a view of real data, and the words never say more than that.
- **Speed.** Real data means far more points than today's hand-made scene. WebGL carries them; the fallbacks under "Checks" cover the rest. Measure as in the past: single bench runs are noisy.
- **WebGL on an integrated graphics chip.** Drivers can lose the context, for example when the laptop sleeps or another tab takes the chip. The scene handles the loss: it falls back, and rebuilds when the context is restored. The page's two WebGL canvases (the scene and the sea) are never on screen together.
- **WC-R3 may change the codebook.** Then re-run `export-film`; the provenance test catches a stale export.
- **Honest pictures.** Camera moves and colours are style, but every shape, time and point comes from a record. The Hide strip shows true proportions of data and cover.
- **Length.** About 11 screens against 9 today. If it drags, Dive merges into Ocean.

## Records to update when it ships

`web/README.md` (rewritten for the new page), `web/CREDITS.md`, `docs/ARCHITECTURE.md` (the new page, `film/` and `export-film`), `docs/INDEX.md`, `CHANGELOG.md` `[Unreleased]`, `project/TRACEABILITY.md`, `project/DECISIONS.md` (D-025's status, and a dated note on D-024 that the name now also appears in the header mark and `model.html`), `WORKLOG.md`.

## Not in this plan

- **New footage.** No free false killer whale video was found (2026-11-26). Pexels and Pixabay have none. The clips found (BBC, sold through Getty) are paid. NOAA's public-domain material is low-resolution stills. `[DECISION]` Keep the current footage as atmosphere (`web/CREDITS.md` already says so); the species is right where it matters, in the data the scene draws.
- **Phone layouts** (D-015).
- **Any change to how Encode and Decode work.**

## Progress

Dated lines, newest last. Details are in `WORKLOG.md`.

- **2026-11-26, started** on the branch `web-retelling`; prerequisite 2 done (data-whistle share reconciled).
- **2026-11-26, P1 done.** `export-film` (`whistlecode/wcode/film.py`, settings `[film]` in `whistlecode/config.toml`) wrote `web/film/`: `film.json` 75 KB, `learn.bin` 508 KB, `hear_it.wav` 24 KB. The send had 31 data and 51 cover whistles (38 % data) and 50 clicks, over 53.9 s. Seed 0 decoded "MEET AT DAWN" exactly, with no seed skipped and 1 wrong whistle repaired. The three PCA axes keep 60 % of the latent variance; all 3,000 components have members. The followed whistle is shape 3 (component 440, carrying "M" and the start of "E"), and the Listen image is that component's most typical member. The sender gained a record of each cover whistle as played (`Transmission.covers`, `clicks_s`), which the Hide beat needs. Tests: `whistlecode/tests/test_wc_film.py`, plus one in `test_wc_pipeline.py`.
- **2026-11-26, P2 done.**
  - Changes: the identity strings; header links without Try it; the Falsetto question in the opening; the film's last line leads to Encode; the lab (`#lab`) opens on 04 · Encode, with Encode's heading taking the arrival; the limits line and a link to `model.html` in the footer.
  - New files: `web/model.html` (Try it as it was) and `web/water.js` (the tide and the sea, moved from `lab.js` unchanged).
  - Checked in the browser with `whistlecode serve`:
    - both pages load with no console errors;
    - the tide brings in Encode, which reports ready and frames the default message;
    - the header links Listen and Decode land and mark themselves;
    - `model.html` offers Nyx and Delphi, shows its three examples, and its Imagine made two whistles.
  - Numbering until P3: the film's beats stay 01-03, so Encode and Decode are 04 and 05; they become 06 and 07 with the new beats.
- **2026-11-26, P3 done.** The research section is one WebGL 2 scene, written by hand with no library: `web/gl.js` (programs, matrices, thick lines as instanced quads) and `web/scene.js`, rewritten.
  - **The five beats:** Listen → Learn → Speak → Hide → Hear, drawn only from `film/`. `shots.js` gives the research section 6 screens.
  - **"Hear it"** moved to Speak and plays `film/hear_it.wav`. `audio-engine.js` is removed.
  - **Header links:** Listen · Learn · Speak · Hide · Hear · Encode · Decode. Encode and Decode are now 06 and 07.
  - **Display choices, each with its reason:**
    - **Listen crop:** Listen shows a crop of the 0.68 s × 12 kHz image around its whistle.
    - **Ridge smoothing:** the ridge line takes a five-frame average of the image's crest, because the contour falls between pixel rows. The landscape keeps every pixel.
    - **Cloud scale:** the cloud is scaled by its 98th-percentile radius, not its largest point, so outliers do not squeeze the bulk.
    - **Clicks:** short ticks on the riverbed.
  - **Checked in the in-app browser on this laptop's Radeon 610M:**
    - **Every beat:** a screenshot of each.
    - **Speed:** at 3840 × 2400 device pixels (more than the laptop's screen), the scene alone costs a median 0.8 ms per frame, 1.9 ms at the 95th percentile and 2.4 ms at most, measured with a one-pixel read-back to wait for the GPU. That leaves room within the 6 ms target for the rest of the page, which was not measured here.
    - **Warm-up:** first draws cost up to 13 ms until the shaders were warmed at load; after the warm-up, every first draw is under 5 ms.
    - **Fallbacks:** a forced lost context (the words stand alone, then the scene rebuilds); no WebGL 2 (the constructor refuses, and the words stand alone); reduced motion (settled pictures).
    - **Controls:** "Hear it" plays; the header links land on their beats.
  - **Not checked yet:** whole-page frame times with the pane visible (the pane was hidden, which throttles animation frames), Edge, and Docker over Funnel. Those are P5.
