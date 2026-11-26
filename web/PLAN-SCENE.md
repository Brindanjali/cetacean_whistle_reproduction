# The film's 3D scene redrawn (WEB-6)

**Status:** approved by the owner 2026-11-26 (D-026). **Revised 2026-11-26 (D-027):** the owner rejected the first style frame (deep dark water, glow, a translucent sheet) as childish and unprofessional, and asked for the page's own blue water and a minimal, sophisticated drawing. This file now describes that direction; the first one is kept in "Progress". Work on the branch `web-scene-v2`; `main` stays ready to freeze as v1.0.0. The second style frame (S1, Listen) was approved the same day. **Done 2026-11-27:** Listen redrawn, Learn and Speak made bolder, Hide and Hear and the camera left as WEB-5 (owner), checks passed; the owner commits and merges it (YOU-15).

`[DECISION]` marks a choice this plan makes. The main ones are recorded as [D-026](../project/DECISIONS.md#d-026) and [D-027](../project/DECISIONS.md#d-027).

## Why

The owner judged the WEB-5 scene (`web/scene.js`) odd and unprofessional. Seen in the browser on 2026-11-26:

- **A wire fence, scribbles and scratches.** The Listen landscape is a wireframe of 53 rows and every fifth column; the Speak lattice is 64 small strokes crowded together; the Hide river is strokes scattered on a diagonal.
- **Jagged lines.** The Listen contour has 27 points, joined by straight segments.
- **Labels like a chart's:** monospace with a dark outline, and arrows ("pitch ↑"). One of them says more than the record: "loudness", although the training image is the contour resynthesised at constant strength and drawn as an image, so its height is the drawing's level, not the animal's loudness.
- **A camera that jerks at each beat boundary:** straight blends between fixed poses.

## Direction: fine lines over the page's own water

`[DECISION]` (D-027) The scene stays on the page's blue water, as in WEB-5: the canvas is transparent over the dolphins' last frame. It is drawn like a precise instrument drawing:

- **Fine lines and points only:** 1 px white hairlines and small dots. No glow, no bloom, no fills, no particles, no translucent sheets.
- **One accent:** amber for the whistle the film follows, from Listen to Speak, and for the key's whistles in Hear. Coral only for the one misread whistle.
- **Depth by fading:** lines and dots grow fainter with distance, into the water.
- **Few elements, each from a record**, and every one of them earns its place.
- **Motion:** lines draw themselves; hairlines rise one after another; one camera, moving smoothly. Every frame is a pure function of the scroll position; nothing moves while the page is still.
- **Labels:** the page's mono, upper case and widely spaced, with a soft shadow like the header's. Numbers with their units. Never over the words.

## How it is drawn

Hand-written WebGL 2 in `web/gl.js`, as in WEB-5 (D-025): no library. Every line and point smooths its own edge in its shader, so the context has no multisampling (`antialias: false`; with it, the bolder Learn cloud cost 7 ms a frame on the Radeon 610M). Lines are strips with mitred joins and per-point opacity (`Lines`), drawn over the water rather than added to it. No off-screen buffers or post-processing, so no quality steps are needed: Listen costs about 0.1 ms of GPU time per frame on the Radeon 610M at 2560 × 1600.

## Beat by beat

| Beat | New |
|---|---|
| 01 Listen | The training image's pixel grid as a floor of fine dots (one per 2 × 2 pixels; time across, pitch into the distance). The contour traces itself on that floor; then, at every frame of the image, a hairline rises to the image's level there, one after another along time, and the contour rides their tops as one amber line. The camera comes round from low on the side, then tips over: the hairlines become points and the amber line lies on its trace: the whistle's shape. Labels: time (0.37 s) and pitch (2.6–7.4 kHz), then "its shape" |
| 02 Learn | *Revised 2026-11-26 (owner): Learn and Speak keep their WEB-5 design and are only made bolder; see "Progress". The plan first written for them:* The amber line shrinks into its own point, marked by a small amber dot and a thin ring. Around it, all 63,490 whistles appear as fine white points, one colour, fainter with distance; the camera turns slowly round them |
| 03 Speak | The codebook's 16 families brighten within the cloud and the rest dim. Each family's mean shape draws itself out of its family and settles in a 16 × 4 grid over a dot floor like Listen's (shape across, pitch up), evenly spaced and the same size. The followed shape is amber; "Hear it" moves a small amber dot along it |
| 04 Hide | A dotted time axis running into the distance. Every sound of the send is a fine stroke at its pitch and time; clicks are short hairlines on the axis. Data and cover whistles are drawn alike. The camera travels low along it |
| 05 Hear | The key's whistles turn amber and lift a little; the rest fade into the water. The misread whistle shows in coral, then turns amber when it is repaired. The message whistles draw in towards the letters, which appear in the page's serif |

**Stays:** every shape, time and point from `web/film/` (no new export), the words, the scroll timings, the fallbacks (no WebGL, a lost context, reduced motion), desktop only. Smoothing (the contour's spline, the five-frame average of the hairlines' heights) is display only and says so in the code.

## Graphics chip

The owner's laptop has an AMD Radeon 610M (built in) and an NVIDIA GeForce RTX 5060 Laptop GPU, and the owner wants the scene on the RTX 5060. A page cannot choose the chip. Measured 2026-11-26: Chrome on Windows gives WebGL the Radeon 610M for every `powerPreference` (default, low-power, high-performance). Launched with `--force_high_performance_gpu`, it gives the RTX 5060. So the chip is the browser's, set per app in Windows (Settings → System → Display → Graphics) or the NVIDIA Control Panel. The scene still asks for `high-performance`, which browsers on other systems honour. `[DECISION]` Screenshots and timings are taken on the RTX 5060 (Chrome with that flag), and the Radeon 610M is checked too.

## Steps

| Step | Work | Done when |
|---|---|---|
| S1 | Style frame: the drawing (`gl.js`) and the Listen beat | The owner approves screenshots taken on the RTX 5060 |
| S2 | Learn and Speak, made bolder (owner, 2026-11-26: no new design) | Screenshots of each |
| S3 | Hide and Hear: *dropped 2026-11-27, the owner chose to leave them as in WEB-5* | – |
| S4 | Camera path, transitions, labels: *left out 2026-11-27; the camera keeps its WEB-5 moves apart from Listen's opening* | – |
| S5 | Checks (below) | All pass, with proof |
| S6 | Records: `WORKLOG.md`, D-026 and D-027, this file, `CHANGELOG.md`, `docs/ARCHITECTURE.md` | – |

## Checks

- **Speed:** GPU time per frame from the browser's timer query (`EXT_disjoint_timer_query_webgl2`), at 2560 × 1600, through the whole film, on the RTX 5060 and the Radeon 610M: 95th percentile at or under 6 ms.
- **Fallbacks:** WebGL off, a forced lost context, reduced motion.
- **Browsers:** Chrome and Edge on desktop.
- **Repository:** `python tools/repo.py check`; the Definition of Done in `project/WORKFLOW.md`.

## Timing

`[DECISION]` If S5 passes by 28 Nov, the branch merges and ships in v1.0.0 (29 Nov). Otherwise v1.0.0 ships the WEB-5 scene and this follows as v1.1.0.

## Progress

Dated lines, newest last. Details are in `WORKLOG.md`.

- **2026-11-26, started** on the branch `web-scene-v2`.
- **2026-11-26, S1 (style frame) built; waiting for the owner's approval.**
  - **Drawing (`web/gl.js`):** `Frame` (a half-float scene buffer with 4× multisampling; a six-level bloom, 13-tap down and tent up; Khronos PBR Neutral tone mapping; the water drawn behind; vignette; grain), `Ribbons` (mitred strips with per-point width and light, depth of field, fog), quality steps (`full`, `balanced`, `light`; a discrete chip starts at `full`), and a GPU timer (`EXT_disjoint_timer_query_webgl2`).
  - **Listen (`web/scene.js`):** the image is a thin ridge on a zero floor (90 % of the crop's pixels are 0 or 1 of 255), so it is drawn as a translucent sheet of light over a dark glass floor, in three passes of one mesh (floor, sheet, reflection), 4 × 4 vertices per pixel. Display only: a blur of 1.2 pixels along time and 0.5 across pitch (the contour falls between pixel rows, so the crest's level alternates frame to frame and read as teeth), bicubic interpolation, crest scaled to full height. The contour is a Catmull-Rom ribbon in amber on the crest, with light running along it as it draws. Labels: no outlines or arrows; time and pitch with their real spans (0.37 s; 2.6–7.4 kHz). The camera now cranes in from a three-quarter view before it tips over.
  - **Water:** a gradient from near black to deep blue, light from above in slanted shafts, 1,400 drifting particles with depth of field. Learn to Hear still draw as in WEB-5, now over this water.
  - **Graphics chip:** Chrome on Windows ignores `powerPreference` (all three values gave the Radeon 610M); with `--force_high_performance_gpu` it gives the RTX 5060.
  - **GPU time per frame**, headless Chrome at 2560 × 1600 (1707 × 1067 at 150 %), the browser's timer query, 60-150 frames per position:
    - RTX 5060, `full` (4× multisampling, scene at full resolution): median 0.6-1.0 ms in every beat. Some runs read 3.4-3.7 ms for the same frame: the laptop's power state, not the scene (repeat runs of one position give either).
    - Radeon 610M, `balanced`: median 9.0-9.6 ms, over the 6 ms target. `light`: 6.8-7.5 ms. `light` with the canvas at one pixel per point: 2.8 ms median, 95th percentile 4.2-4.6 ms. So for S5: on a built-in chip, the `light` step also halves the canvas resolution.
- **2026-11-26, first style frame rejected; direction revised (D-027).** The owner found the deep-water look childish and unprofessional and the translucent sheet useless, and asked for the page's own theme and a minimal, sophisticated drawing. `Frame`, the bloom, the tone mapping, the drawn water, the particles, the quality steps and the sheet are removed; `gl.js` and `scene.js` are rebuilt from the WEB-5 versions.
- **2026-11-26, S1 rebuilt (second style frame); waiting for the owner's approval.**
  - **Drawing (`web/gl.js`):** the WEB-5 helpers, plus `Lines` (fine lines drawn over the water, mitred, opacity per point, fading with distance), `GpuTimer`, the browser's anti-aliasing, and `powerPreference: 'high-performance'`.
  - **Listen (`web/scene.js`):** a floor of 972 dots (one per 2 × 2 pixels of the crop, fading over its outer fifth); the contour's trace; 27 hairlines, one per frame, as tall as the image's level there (the highest within a row of the contour, averaged over five frames); the amber line along their tops (Catmull-Rom, 6 samples a frame). The "loudness" label is gone (see "Why"); time 0.37 s and pitch 2.6–7.4 kHz label the floor. The Learn hand-over is a small amber dot with a thin ring instead of a glow. Learn to Hear draw as in WEB-5.
  - **GPU time per frame**, headless Chrome at 2560 × 1600, 90 frames per position: Listen 0.05 ms median on the RTX 5060 and 0.1 ms on the Radeon 610M. The WEB-5 Learn cloud costs 3.6 ms on the Radeon now that the browser anti-aliases (0.1 ms on the RTX); S2 redraws it.
- **2026-11-26, S1 approved** by the owner. Also at the owner's request, outside this plan: Try it is back on the page as 08, after Decode (D-028).
- **2026-11-26, S2 done: Learn and Speak made bolder.** The owner asked for no new design here, only more boldness: Listen and Learn were already minimal. Changes in `web/scene.js`:
  - **Learn:** the 63,490 points are crisp round points drawn over the water instead of soft glows added together, larger (2.4 px before perspective, from 2.3) and stronger (opacity 0.5, from 0.24), fading with distance. Where they crowd, the colour holds instead of burning white. The followed whistle keeps its amber dot and ring until Speak begins.
  - **Speak:** the 64 strokes are solid fine lines with mitred joins (`Lines`), 2.6 px (from 1.3, with a faint wide glow pass), the followed one 3.6 px in amber (from 2.4). The cloud dims to 15 % behind the lattice as it forms, so the lattice stands clear. "Hear it" follows the shape with an amber dot and ring instead of a glow. The labels lose their arrows ("16 shapes", "4 pitches").
  - **Multisampling off** (`web/gl.js`): every line and point smooths its own edge, so it changed nothing on screen but cost the Radeon 610M 7 ms a frame in Learn.
  - **GPU time per frame** at 2560 × 1600, headless Chrome, 90 frames: Radeon 610M Listen 0.12 ms, Learn 2.1 ms median (95th percentile 5.6), Speak 1.3-2.4 ms; RTX 5060 at most 0.8 ms.
- **2026-11-27, S3 and S4 dropped.** The owner chose to leave Hide and Hear as in WEB-5. `[DECISION]` S4 goes with them: the owner asked for small changes only, and a new camera path would change how every beat moves. The camera keeps its WEB-5 moves, apart from Listen's opening (it comes round from low on the side before tipping over). Left: S5 (checks) and S6 (records).
- **2026-11-27, S5 checks.** Headless Chrome and Edge on the RTX 5060 (`--force_high_performance_gpu`) at 2560 × 1600, against `whistlecode serve`, with every console error and warning caught from the first script:
  - **The whole page in Chrome:** the film from the opening to the return, then Try it: no errors, no warnings; Try it offers Nyx and Delphi; Encode is ready.
  - **WebGL off** (`--disable-3d-apis`): no scene; the words stand alone (Listen at 2.07, Speak at 2.555); only the expected warning.
  - **Lost context** (`WEBGL_lose_context`): the words stand alone, then the scene rebuilds on restore (`lost` false, `ready` true) and draws Speak correctly.
  - **Reduced motion** (emulated media): Listen shows its settled picture; no errors.
  - **Edge:** the RTX 5060; Listen, Learn and Speak draw as in Chrome; Try it offers both models; no errors.
  - **Review of the diff:** one real fault, fixed: the new label style sets a label in capitals, which turned Hear's key into "REEF-42"; the key is now the label's detail and keeps its case. Also the scene's header comment brought up to date and an unused class removed. Hide's and Hear's labels now use the new label style (capitals, a soft shadow instead of an outline); their drawing is unchanged.
  - **Numbers:** Listen's two labels (0.37 s; 2.6–7.4 kHz) are traced in `project/TRACEABILITY.md`.

