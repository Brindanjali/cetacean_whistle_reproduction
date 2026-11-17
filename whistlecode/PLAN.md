# WhistleCode plan: hiding messages in whistles

Status: plan written 2026-11-17. Nothing is built.

This enhancement replaces WhistleFlow. The `whistleflow/` folder stays as it is but will not be implemented. WhistleFlow's no-images rule does not apply here, because this enhancement reuses the reproduction's spectrogram detector and VAE.

How to read this document:

- `[DECISION]` marks a choice made here because nothing fixes it. It is the same tag the reproduction's configs use. Every one is listed again in section 12 with its default.
- Thresholds in section 7.5 are frozen before the final test runs, so a result cannot move its own goalpost.
- "The reproduction" means `src/whistlepipe`, `configs/`, `models/`, `preprocessed/` and the encounter audio folders. WhistleCode only imports from them and never edits them.
- "Message encoder" is the transmitter and "message decoder" is the receiver. The VAE has its own encoder and decoder, which appear inside them: the VAE decoder makes the whistles, and the VAE encoder is one way to read them back.

## 1. The idea

A text message is turned into a sequence of synthetic false killer whale whistles. The sequence is sent through an underwater channel, and a receiver turns the whistles back into the exact text.

The whistles must sound like the species, not like a modem. This is biomimetic covert underwater communication. The whistle types come from the VAE-GMM V1 trained in the reproduction, so the trained model becomes the modem's alphabet.

## 2. Overview

```
MESSAGE ENCODER (transmitter)
"MEET AT DAWN" -> bytes -> + CRC-16 -> scramble with key -> Reed-Solomon -> 4-bit symbols
  -> whistle type from a 16-type codebook -> VAE decoder -> contour -> FM tone + envelope + harmonic
  -> each whistle placed at a key-chosen time and centre frequency, after a 3-whistle preamble -> WAV

CHANNEL ("sending")
WAV + real ocean noise from encounters 214 / 276 (real whistles included) at a set SNR
    + multipath echoes + absorption + Doppler

MESSAGE DECODER (receiver)
WAV -> whistlepipe detector + tracker -> find preamble -> expected slots from the key
  -> pick the whistle in each slot -> classify its contour -> symbol, or "erased"
  -> Reed-Solomon (fixes errors and erasures) -> unscramble -> CRC check -> "MEET AT DAWN"
```

## 3. Message encoder (transmitter)

### 3.1 The shared key

Sender and receiver share a key string. `[DECISION]` The SHA-256 of the key seeds a NumPy `SeedSequence`, which spawns four independent streams:

| Stream | Used for |
|---|---|
| scrambler | XOR mask for the header and payload bytes |
| timing | start-to-start interval of every whistle |
| pitch | centre frequency of every whistle |
| variation | the random latent offset of every whistle (the receiver never needs this one) |

The scrambler makes the bytes look random, so the whistle sequence never repeats unnaturally, even for a message like "AAAA". It is not encryption, just a shared secret.

### 3.2 Frame

| Part | Content | Whistles |
|---|---|---|
| Preamble | 3 repeats of the reserved signature whistle | 3 |
| Header | payload length L (1 byte), scrambled, protected by Reed-Solomon RS(5, 1): 4 parity bytes, correcting 2 wrong or 4 erased bytes | 10 |
| Payload | L message bytes + CRC-16, scrambled, then Reed-Solomon with `nsym = max(8, ceil(k / 2))` parity bytes, where k = L + 2 | 2 x (k + nsym) |

- Text is encoded as UTF-8. `[DECISION]` The longest payload is 140 bytes, so the payload always fits one Reed-Solomon codeword (n <= 213 <= 255) and needs no interleaver.
- `[DECISION]` The CRC is CRC-16/CCITT. It catches the rare case where Reed-Solomon "corrects" to a wrong codeword.
- Each byte becomes two 4-bit symbols, high nibble first. Each symbol is one whistle.
- Reed-Solomon with `nsym` parity bytes fixes any mix of e wrong bytes and f erased bytes with 2e + f <= nsym. An erased whistle (a missed or ambiguous one) costs half as much as a wrong one, which is why the receiver marks doubtful whistles as erased instead of guessing.

### 3.3 Schedule from the key

- `[DECISION]` Start-to-start intervals are drawn uniformly from 0.55-0.95 s. The codebook's whistles last 150-450 ms (section 4), so consecutive whistles never overlap.
- `[DECISION]` Each whistle's centre frequency is drawn from the centre frequencies of the encounter-191 training whistles (`preprocessed/encounter_191/images.csv`, the same source `infer.training_centre_frequencies` reads), restricted to 5-12 kHz. Because every codebook type spans at most 5 kHz (+/- 2.5 kHz around its centre), every whistle stays within 2.5-14.5 kHz whatever symbol it carries.
- Timing and pitch do not depend on the symbols. The receiver re-creates both from the key, so it knows when each whistle comes and roughly at what pitch. This works like frequency hopping and lets it ignore real animals whistling at other times or pitches.

### 3.4 Making one whistle

For symbol s in slot i:

1. Sample a latent from the type's GMM component: z = mu_s + tau * L_s * eps, where L_s is the Cholesky factor of the component covariance and eps comes from the variation stream. `[DECISION]` tau = 0.5 to start; the final value is chosen by measurement (section 7.3). With tau > 0, repeated symbols never sound identical.
2. Decode z with the VAE decoder to a 128 x 128 image, then take its contour with `sonify.image_contour` (threshold 0.05).
3. Synthesise a phase-continuous FM tone at fc_i + contour offset. Add:
   - the amplitude envelope of the synthetic generator (Tukey window with a slow amplitude ripple), ported from `src/whistlepipe/synth/whistles.py`;
   - `[DECISION]` a 2nd harmonic at -12 dB.

   `[DECISION]` The sample rate is 96 kHz and the output is a float32 WAV.
4. **Self-check:** the transmitter classifies its own clean whistle with the receiver's classifier. If the whistle is ambiguous or classified wrongly, it draws a new eps, up to 20 times, and otherwise falls back to the type's mean (tau = 0).
5. Place the whistle at its slot start time t_i.

### 3.5 Worked example

"HI" is 2 bytes. With 2 CRC bytes k = 4 and nsym = 8, so the payload is 12 bytes = 24 whistles. With the 10 header and 3 preamble whistles that makes 37 whistles, about 28 s at a mean interval of 0.75 s.

A 20-character sentence: k = 22, nsym = 11, so 33 bytes = 66 whistles, plus 13, giving 79 whistles, about a minute. That is roughly 3 bits per second of payload, normal for covert communication that imitates animals. Section 7.3 measures the faster options.

## 4. The whistle alphabet (codebook)

Built once, from the V1 model (`models/vaegmm/V1_L64_b1e-4_critic_E191/checkpoints/final.pt` and `gmm_K3000/gmm.npz`).

1. **Candidates.** Decode the mean of each of the 3,000 components and extract its contour. Also decode 32 samples per component to measure how stable its shape is.
2. **Filter.** `[DECISION]` Keep a component when:
   - its mean decode gives one clean contour, with no gaps longer than 3 columns;
   - its duration is 150-450 ms;
   - its frequency span is 300 Hz to 5 kHz;
   - its samples stay close to its mean (median DTW distance below the 50th percentile of all components);
   - its weight pi_k is above the median, because common types sound natural.
3. **Select 16 + 1.** Compute DTW distances between the candidate contours and pick 17 by greedy max-min selection, starting from the heaviest component. The most distinctive of the 17 becomes the signature whistle (preamble only) and the other 16 carry symbols 0-15.
4. **Confusion test.** Send each type 200 times through the channel at 5 dB SNR on encounter-214 noise and classify it. Swap out the type with the most confusions for the next-best candidate, and repeat until no pair is confused more than 2 % of the time, or for 10 rounds.
5. **Outputs:**
   - `codebook.npz`: component ids, mean latents, Cholesky factors, template contours, symbol mapping;
   - `codebook.json`: lineage (model hashes, settings);
   - a gallery: each type's contour plot and WAV.

**Fallback.** If fewer than 17 candidates pass the filter, because the V1 decodes are too blurry, the types come from medoids of real contours in `preprocessed/encounter_191` instead. The rest of the plan is unchanged, except that the VAE is not used at transmit time.

## 5. The channel ("sending")

| Effect | How |
|---|---|
| Noise | Real channel-0 audio, resampled 500 to 96 kHz (polyphase 24/125) and high-passed at 2 kHz with the reproduction's 4th-order zero-phase Butterworth. **Encounter 214** for tuning, **encounter 276** for the final test. Encounter 191 is never used as noise, because the VAE trained on it. The noise contains real whistles, a realistic source of interference. Each file is tagged "quiet" or "busy" by its old-detector whistle count (from `preprocessed/`), as metadata for breakdowns. |
| SNR | Narrowband, as in the synthetic generator: each whistle is scaled so that its level in its own 93.75 Hz bin is the target SNR above the median noise level in that bin. Swept from -5 to +25 dB in 2.5 dB steps. |
| Multipath | Image method: direct, surface (reflection -0.9), bottom (0.4) and surface-bottom paths. `[DECISION]` Water depth 50-1,000 m, source depth 5-30 m, receiver depth 5-50 m, range 0.2 / 0.5 / 1 / 2 km. Amplitude falls as 1/path length; delays are applied as fractional delays. |
| Absorption | Thorp's frequency-dependent loss over each path's length. |
| Doppler | Time-scaling by 1/(1 + v/c) with c = 1,500 m/s, v drawn from +/- 3 m/s. |
| Air test (optional) | Play the WAV through the laptop speaker and record it with the laptop microphone, as a real demonstration. |

Messages longer than one noise file use consecutive files of the same encounter (files follow each other with no gaps).

## 6. Message decoder (receiver)

1. **Detect.** Run the reproduction's S1-S7 chain (`whistlepipe.infer.preprocess`, with ridgenet-v2c and its tracker) on the received WAV. This gives every whistle track with its start time, frame-by-frame frequency contour and centre frequency. `[DECISION]` Long recordings are processed in 60 s blocks with a 2 s overlap, and duplicate tracks in the overlaps are merged.
2. **Synchronise.**
   - Every track that classifies as the signature whistle is a candidate preamble start.
   - For each candidate, check whether the other two preamble slots (from the key's timing) also hold signature-like tracks.
   - Accept the best candidate with at least 2 of 3. This fixes the time origin t0.
3. **Slot matching.** For each expected slot, take the track that starts within +/- 80 ms of the expected time `[DECISION]` and whose centre lies within +/- 1.5 kHz of the expected pitch `[DECISION]`.
   - If several qualify, take the one with the closest start; ties go to the longer track.
   - An empty slot is marked **erased**.
   - A running linear fit of observed against expected start times, over confident matches only, corrects clock drift from Doppler.
4. **Classify.** Two classifiers are built. The one with the lower symbol error on encounter-214 noise becomes the default; both are reported.
   - **A, DTW templates:** DTW distance between the track's contour (relative to its own centre) and each of the 16 template contours, plus a duration-difference term.
   - **B, VAE encoder + GMM:** build the track's S8 image, encode it with the VAE encoder, and take the GMM posterior restricted to the 16 chosen components.

   In both, `[DECISION]` a call is marked erased when it is ambiguous: for A, best distance / second-best > 0.8; for B, top posterior < 0.6. Both values are tuned on encounter 214.
5. **Repair and check.**
   - Decode the header. If it fails, the message is lost.
   - Decode the payload with Reed-Solomon, passing the erased positions, then unscramble.
   - Check the CRC. Only a passing CRC releases the text.
6. **Report:** the text (or "failed"), whistles detected, slots matched, erasures, bytes corrected, CRC result, and the time and frequency of every slot.

## 7. Evaluation

Every test message is generated, so the true text is known. No listening labels are needed.

### 7.1 Test messages

`[DECISION]` 200 messages: 150 random-byte payloads of 4-64 bytes and 50 English sentences. Each trial uses a new random key and a new channel draw.

### 7.2 Reliability measures

- Sync success rate.
- Symbol error rate (among whistles not erased) and erasure rate.
- Byte error rate before Reed-Solomon.
- **Message success rate:** exact text and CRC passed.
- **False accepts:** CRC passed but the text is wrong. Must be 0.
- Throughput: payload bits per second of airtime.
- **No-message test:** run the receiver on noise-only files with random keys. Any accepted message is a false alarm. Must be 0.

### 7.3 Experiments

| ID | What varies | Noise |
|---|---|---|
| E1 | Clean loopback (no noise, no channel) | none |
| E2 | SNR -5 to +25 dB, quiet vs busy files | 214, then 276 |
| E3 | Multipath range and Doppler, at SNR 5, 10 and 20 dB | 214, then 276 |
| E4 | Codebook size M = 8 / 16 / 32 / 64: speed vs reliability | 214 |
| E5 | Variation tau = 0 / 0.25 / 0.5 / 1: naturalness vs reliability | 214 |
| E6 | Classifier A vs B | 214, then 276 |
| E7 | Covertness (7.4) | 276 |
| E8 | Baseline modem (7.4) | 214, then 276 |

Defaults (M, tau, classifier, erasure thresholds, slot tolerances) are chosen on encounter 214, written into `config.toml` and frozen. Only then does the encounter-276 test run.

Possible later upgrades, each measured before adoption:

- larger M (E4);
- 1-2 extra bits per whistle from the centre frequency band;
- overlapping whistles.

### 7.4 Covertness and the baseline

Covertness asks whether the coded whistles can be told apart from real ones. Each measure compares coded whistles, as detected by the receiver, with real whistles from encounter 276.

- **Feature distance:** Wasserstein-1 distance for each of the reproduction's 7 contour features (L, f_min, f_max, df, f_start, f_end, f_c).
- **Likelihood:** mean GMM log-likelihood of the VAE-encoded latents, coded vs real.
- **Discriminator:** a classifier (scikit-learn gradient boosting) trained to tell coded from real on the per-whistle features. 5-fold cross-validated ROC AUC: 0.5 means indistinguishable, 1.0 means obvious.

**Baseline modem:** identical framing, key, schedule and receiver, but each symbol is a 300 ms constant tone at one of 16 frequencies between 5 and 12 kHz (16-FSK), classified by its mean frequency. It should be at least as reliable and clearly artificial. Comparing it with WhistleCode shows the price paid for sounding natural.

### 7.5 Pass marks `[DECISION]`, frozen before the encounter-276 test

| Test | Pass mark |
|---|---|
| E1 clean loopback | 100 % of the 200 messages exact |
| E2 encounter 276, SNR 10 dB, no multipath | >= 95 % of messages exact |
| False accepts and no-message false alarms | 0 |
| E7 discriminator AUC (chosen tau) | <= 0.75 |

A failed mark is reported as failed, with the measured value; it is never rewritten as a pass.

## 8. Phases

| Phase | Work | Done when |
|---|---|---|
| P0 | Folder, `config.toml`, key streams, framing (UTF-8, CRC, scrambler, header), Reed-Solomon, unit tests | Bytes -> symbols -> bytes round trip passes, including with erasures and errors up to the RS limit |
| P1 | Codebook: candidates, filter, selection, confusion test, gallery | `codebook.npz` + gallery |
| P2 | Transmitter: schedule, preamble, synthesis, self-check, `send` command | A message becomes a WAV |
| P3 | Channel: noise at SNR, multipath, absorption, Doppler, `channel` command | A WAV goes through any channel setting |
| P4 | Receiver: detect, sync, slots, classifier A, Reed-Solomon, CRC, `receive` command | **E1 passes: working send -> channel -> receive demo** |
| P5 | Classifier B, sweeps E2-E6, tune on 214, freeze, test on 276 | Reliability curves and tables |
| P6 | Covertness E7 and baseline E8 | Covertness table |
| P7 | README, figures, results; optional air test; optional "send a message" panel on the project web page | Write-up |

Effort: about 1.5 days of work for P0-P4 and 1-1.5 days for P5-P7. Everything runs on the laptop (RTX 5060, 8 GB). No Colab units and no model training are needed; the only fitted model is the covertness discriminator, which takes seconds.

P0-P4 is the part to have first: it is a complete, demonstrable system. P5-P7 measure and explain it.

## 9. Folder layout and commands

```
whistlecode/
  PLAN.md            this document
  README.md          what it is, how to run it, results (P7)
  config.toml        every parameter with its tag
  whistlecode.py     command-line entry point (adds src/ to sys.path, like whistle.py)
  wcode/
    keys.py          key -> random streams
    framing.py       text <-> bytes, CRC, scrambler, header, symbols
    fec.py           Reed-Solomon wrapper with erasures
    codebook.py      build, check and load the codebook
    synth.py         contour -> audio (envelope and harmonic ported from the synthetic generator)
    schedule.py      slot times and pitches from the key
    transmitter.py   message -> WAV
    channel.py       noise, SNR, multipath, absorption, Doppler
    classify.py      classifiers A (DTW) and B (VAE encoder + GMM)
    receiver.py      WAV -> message
    baseline.py      16-FSK modem
    evaluate.py      experiments E1-E8
  tests/
  outputs/           gitignored (codebook gallery, WAVs, results)
```

| Command | Does |
|---|---|
| `build-codebook` | Section 4 |
| `send "TEXT" --key K --out msg.wav` | Message -> WAV |
| `channel msg.wav --noise 276 --snr 10 [--range 1 --doppler 1.5] --out rx.wav` | Sends the WAV through the simulated channel |
| `receive rx.wav --key K` | WAV -> message and report |
| `evaluate E2` (etc.) | Runs one experiment |

## 10. Reuse, boundaries and requirements

**Imported from the reproduction (read-only):**

- `whistlepipe.audio`;
- `whistlepipe.infer.preprocess` (S1-S7, ridgenet-v2c and the tracker);
- `whistlepipe.sonify.image_contour`;
- the VAE model, `GaussianMixtureEM` and `vaegmm.features`.

**Ported (copied, with an equivalence test against the original):** the envelope part of `src/whistlepipe/synth/whistles.py`.

**Never edited:** `src/`, `configs/`, `models/`, `preprocessed/`, the encounter audio folders, `web/` (until the optional P7 panel, and only with your go-ahead), `whistleflow/`.

**Model files needed:** the V1 `final.pt` and `gmm_K3000/gmm.npz`. `gmm.npz` is about 100 MB and is not in git, so any other machine needs it copied over.

**Installs (each needs your approval first):**

- `reedsolo`, a small pure-Python Reed-Solomon library. If it is declined, P0 includes writing a Reed-Solomon codec by hand.
- `sounddevice`, only for the optional air test.

**Data:** only the three local encounters (191 for the codebook and centre frequencies, 214 and 276 for noise). No downloads.

## 11. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| V1 decodes are blurry (Table 1 PSNR 32.8 dB vs the paper's 44.5) | Some components give broken contours | The section 4 filter; fallback to real-contour medoids |
| Real whistles land in a slot | Wrong symbols | Key-based time and pitch windows, Reed-Solomon, erasure on ambiguity; measured separately on busy files |
| Preamble missed | Whole message lost | 3 signature whistles, 2 of 3 enough; sync rate reported on its own |
| Detector splits a whistle into two tracks at low SNR | Wrong or missing symbol | Slot matching prefers the closest start, then the longer track; ambiguous calls are erased |
| Low speed (about 3 bit/s) | Long airtime | Inherent to the approach; E4 and the frequency-band bits are the measured upgrade path |
| Doppler drift over long messages | Slots slide out of their windows | Running drift correction from confident matches |

**Ethics:** this project is simulation only (plus the optional air test). Playing synthetic whistles near wild animals would need permits; the README will say so.

## 12. Parameters

All `[DECISION]` unless stated.

| Parameter | Default | Set in |
|---|---|---|
| Key -> streams | SHA-256 -> NumPy `SeedSequence`, 4 streams | 3.1 |
| Max payload | 140 bytes | 3.2 |
| CRC | CRC-16/CCITT | 3.2 |
| Payload parity | max(8, ceil(k / 2)) bytes | 3.2 |
| Header code | RS(5, 1) | 3.2 |
| Bits per whistle | 4 (M = 16), high nibble first | 3.2, E4 |
| Preamble | 3 signature whistles, 2 of 3 to sync | 3.2, 6 |
| Interval (start to start) | uniform 0.55-0.95 s | 3.3 |
| Centre frequency | encounter-191 distribution, 5-12 kHz | 3.3 |
| Variation tau | 0.5 (set by E5) | 3.4 |
| Self-check redraws | 20, then tau = 0 | 3.4 |
| Harmonic | 2nd at -12 dB | 3.4 |
| Sample rate | 96 kHz, float32 WAV | 3.4 |
| Codebook duration | 150-450 ms | 4 |
| Codebook span | 300 Hz - 5 kHz | 4 |
| Confusion test | 200 sends per type, 5 dB, 214 noise, <= 2 % per pair | 4 |
| Noise for tuning / test | encounter 214 / 276 | 5 |
| SNR definition | narrowband, per 93.75 Hz bin | 5 |
| Receiver blocks | 60 s with 2 s overlap | 6 |
| Slot time window | +/- 80 ms | 6 |
| Slot pitch window | +/- 1.5 kHz | 6 |
| Erasure rule | A: distance ratio > 0.8; B: posterior < 0.6 (tuned on 214) | 6 |
| Test messages | 150 random (4-64 bytes) + 50 sentences | 7.1 |
| Pass marks | section 7.5 | 7.5 |
