# WhistleCode plan: hiding messages in whistles

Status: plan written 2026-11-17 and revised twice the same day (section 14). P0 (keys, framing, Reed-Solomon, tests, the `frame` and `roundtrip` commands) and P1 (the codebook, with the pieces of P2-P4 it needs: whistle synthesis, noise and SNR, the detector wrapper and classifier A) were built on 2026-11-18. P1 changed some plan values after measuring them; section 14 lists the changes.

This enhancement replaces WhistleFlow. The `whistleflow/` folder stays as it is but will not be implemented. WhistleFlow's no-images rule does not apply here, because this enhancement reuses the reproduction's spectrogram detector and VAE.

How to read this document:

- `[DECISION]` marks a choice made here because nothing fixes it. It is the same tag the reproduction's configs use. Every one is listed again in section 13 with its default.
- Thresholds in section 8.6 are frozen before the final test runs, so a result cannot move its own goalpost.
- "The reproduction" means `src/whistlepipe`, `configs/`, `models/`, `preprocessed/` and the encounter audio folders. WhistleCode only imports from them and never edits them.
- "Message encoder" is the transmitter and "message decoder" is the receiver. The VAE has its own encoder and decoder, which appear inside them: the VAE decoder makes the whistles, and the VAE encoder is one way to read them back.

## 1. The idea

A text message is turned into a sequence of synthetic false killer whale whistles. The sequence is sent through an underwater channel, and a receiver turns the whistles back into the exact text.

The whistles must sound like the species, not like a modem. This is biomimetic covert underwater communication. The whistle types come from the VAE-GMM V1 trained in the reproduction, so the trained model becomes the modem's alphabet.

## 2. Overview

```
MESSAGE ENCODER (transmitter)
"MEET AT DAWN" -> bytes -> + CRC-16 -> scramble with key + nonce -> Reed-Solomon -> 4-bit symbols
  -> whistle type from a 16-type codebook -> VAE decoder -> contour -> FM tone + envelope + harmonic
  -> each whistle placed at a key-chosen time and centre frequency, after a 3-whistle preamble -> WAV

CHANNEL ("sending")
WAV -> multipath echoes -> absorption -> Doppler -> + real ocean noise from encounters 214 / 276
       (real whistles included) at a set SNR

MESSAGE DECODER (receiver)
WAV -> whistlepipe detector + tracker -> find preamble -> header (length, nonce) -> expected slots
  -> pick the whistle in each slot -> classify its contour -> symbol, or "erased"
  -> Reed-Solomon (fixes errors and erasures) -> unscramble -> CRC check -> "MEET AT DAWN"
```

## 3. The model it depends on, and the order of work

WhistleCode uses the V1 model files:

- the VAE checkpoint `models/vaegmm/V1_L64_b1e-4_critic_E191/checkpoints/final.pt`;
- the GMM `gmm_K3000/gmm.npz` fitted on that checkpoint's latents.

WhistleCode always reads `final.pt`, never `last.pt`, because `final.pt` only changes once a training run is completely finished. The code does not depend on which model it uses. Everything built from the model (the codebook, the tuned thresholds and the results) is tied to these exact files.

### 3.1 K stays at 3,000

The codebook needs 17 whistle types. The epoch-101 fit already has 203 components holding at least 65 whistles each, enough for a full-rank 64-dimensional covariance. A larger K would only make components smaller and closer together, because the median component already holds 10 whistles and 220 hold fewer than 2. Distinct types come from selection (section 5), not from K. A smaller K is not needed either, unless the section 5 filter finds fewer than 17 candidates.

### 3.2 Development model and final model

`[DECISION]` WhistleCode is built in two stages:

- **Development model, epoch 101:** the current `final.pt`, a byte copy of the epoch-101 `last.pt` (SHA-256 `fcb1a2e6...`), with the current `gmm_K3000/gmm.npz`. P1-P4 are built and debugged on it.
- **Final model, epoch 150:** the `final.pt` of the resumed run (section 3.3), with a GMM refitted on its latents. The full evaluation (P5-P7) runs on it, once.

| Carries over from the development model | Redone on the final model (section 3.4) |
|---|---|
| All the code: framing, error correction, transmitter, channel, receiver, both classifiers, evaluation scripts, tests | The codebook, the tuned thresholds, every result |

Rules for the development model:

- **Smoke tests only:** E1 and the E2 smoke subset (section 8.3). The overnight sweeps, the freezing of settings and the encounter-276 runs wait for the final model, so the 11-23 hours of detector time (section 8.4) are spent once.
- **No keeper demo recordings.** The final codebook will have different whistle types, so message WAVs made with the development codebook will not decode afterwards.

If training is not resumed after all, the development model is the final model: skip sections 3.3 and 3.4 and go straight to P5.

### 3.3 Training resume to epoch 150 (phase M)

The resume of the remaining 49 epochs happens in the reproduction, not in `whistlecode/`.

1. **Resume on Colab** from the Drive run folder `G:\My Drive\whistle_vaegmm_E191\runs\V1_L64_b1e-4_critic_E191`, with the same configuration (`BATCH = 5772`) and the code bundle already on Drive. This takes about 1.75 A100 hours at the measured 128 s per epoch. What a check on 2026-11-17 found:
   - The Drive `last.pt` is byte-identical to the local one.
   - The Drive checkpoints folder has **no** `final.pt`, and the Drive `train_info.json` still says "running". So the resumed run writes a proper epoch-150 `final.pt` and closes `train_info.json` itself.
   - The `final.pt` trap exists only in the local folder. `train_vae` writes `final.pt` only if it does not exist yet, and `post_training/finalize_run.py` made a local one from epoch 101. Never resume from the local folder without renaming that file first.
   - The resume checks only that the run spec matches. The partial epoch-102 log line at the end of the Drive log is harmless, because only epoch summaries are read.
2. **Copy** the new `final.pt`, `last.pt` and `train_info.json` from Drive to the local run folder, replacing the epoch-101 files.
3. **On the laptop,** with the reproduction's own commands:
   - encode the latents again;
   - refit the GMM at K = 3,000, before anything rebuilds the codebook;
   - recompute the component features;
   - redo Table 1, Table 3, Fig. 12 and Figs. 7-10. Table 6 does not change, because the architecture is the same.

   The epoch-101 results stay in git history. The epoch-101 backups in the Drive run folder (`eval`, `figures`, `gmm_K3000*`) become out of date at this point.

### 3.4 The swap in WhistleCode (phase S)

After phase M:

1. Rebuild the codebook (section 5): about 30-45 minutes, including the confusion pass.
2. Rerun E1 to confirm the system still works end to end.
3. Run P5-P7 on the final model. P5 includes the tuning on encounter 214: classifier choice, erasure thresholds, slot windows and tau. Classifier B's margin depends directly on the GMM, so none of the development-model values are kept.

### 3.5 Pinning

`[DECISION]` The chain of files is checked by hash:

- `build-codebook` checks that the GMM was fitted on latents of this `final.pt`. `latents_mu.json` records the checkpoint's SHA-256, and `gmm.json` records the latents' SHA-256.
- `codebook.json` then records the SHA-256 of `final.pt` and `gmm.npz`.
- Every other WhistleCode command refuses to run if either file has changed since the codebook was built.

This makes the swap safe. Once the new `final.pt` arrives, nothing runs until the codebook is rebuilt, and the in-between state (new VAE, old GMM) is caught as well.

P0 and P3 contain no model, so they do not depend on any of this.

## 4. Message encoder (transmitter)

### 4.1 The shared key and the nonce

Sender and receiver share a key string. Every message also carries a random 1-byte nonce in its header `[DECISION]`. Without a nonce, every message under the same key would repeat the same rhythm and reuse the same scrambler stream.

| Stream | Seeded from | Used for |
|---|---|---|
| header scrambler, preamble and header timing and pitch | SHA-256(key) | the first 15 whistles |
| payload scrambler | SHA-256(key, nonce) | XOR mask for the payload bytes |
| payload timing | SHA-256(key, nonce) | start-to-start interval of every payload whistle |
| payload pitch | SHA-256(key, nonce) | centre frequency of every payload whistle |
| variation | SHA-256(key, nonce) | the random latent offset of every whistle (the receiver never needs this one) |

`[DECISION]` How the streams are derived (as built in P0, `wcode/keys.py`):

- Every stream has its own SHA-256 seed, taken over length-prefixed parts: the domain string `whistlecode/v1`, the part (header or payload), the stream name, the key and, for the payload, the nonce. The streams are therefore independent, and adding a stream later never shifts an existing one.
- The scrambler bytes come from SHA-256 in counter mode, so they never depend on the NumPy version.
- Timing, pitch and variation draws come from NumPy PCG64 generators seeded with the stream's digest.

The scrambler makes the bytes look random, so the whistle sequence never repeats unnaturally, even for a message like "AAAA". It is not encryption, just a shared secret.

The preamble and header still share one rhythm per key, about 11 s. Section 12 lists this as a remaining limitation.

### 4.2 Frame

| Part | Content | Whistles |
|---|---|---|
| Preamble | 3 repeats of the reserved signature whistle | 3 |
| Header | payload length L (1 byte) and nonce (1 byte), scrambled with the key-only stream, protected by Reed-Solomon RS(6, 2): 4 parity bytes, correcting 2 wrong or 4 erased bytes | 12 |
| Payload | L message bytes + CRC-16, scrambled with the key-and-nonce stream, then Reed-Solomon with `nsym = max(8, ceil(k / 2))` parity bytes, where k = L + 2 | 2 x (k + nsym) |

- Text is encoded as UTF-8. `[DECISION]` The longest payload is 140 bytes, so the payload always fits one Reed-Solomon codeword (n <= 213 <= 255) and needs no interleaver. The shortest is 1 byte; an empty message is refused.
- `[DECISION]` The CRC is CRC-16/CCITT-FALSE (polynomial 0x1021, initial value 0xFFFF, no reflection, no final XOR; check value 0x29B1 for "123456789"). It catches the rare case where Reed-Solomon "corrects" to a wrong codeword.
- Each byte becomes two 4-bit symbols, high nibble first. Each symbol is one whistle.
- Reed-Solomon with `nsym` parity bytes fixes any mix of e wrong bytes and f erased bytes with 2e + f <= nsym. An erased whistle (a missed or ambiguous one) costs half as much as a wrong one, which is why the receiver marks doubtful whistles as erased instead of guessing.

### 4.3 Schedule from the key

- `[DECISION]` Start-to-start intervals are drawn uniformly from 0.55-0.95 s. The codebook's whistles last 100-450 ms (section 5), so consecutive whistles never overlap.
- `[DECISION]` Each whistle's centre frequency is drawn from the centre frequencies of the encounter-191 training whistles (`preprocessed/encounter_191/images.csv`, the same source `infer.training_centre_frequencies` reads), restricted to 5-12 kHz. Because every codebook type spans at most 5 kHz (+/- 2.5 kHz around its centre), every whistle stays within 2.5-14.5 kHz whatever symbol it carries.
- Timing and pitch do not depend on the symbols. The receiver re-creates both from the key and the nonce, so it knows when each whistle comes and roughly at what pitch. This works like frequency hopping and lets it ignore real animals whistling at other times or pitches.

### 4.4 Making one whistle

For symbol s in slot i:

1. Sample a latent from the type's GMM component: z = mu_s + tau * L_s * eps, where L_s is the Cholesky factor of the component covariance and eps comes from the variation stream. `[DECISION]` tau = 0.5 to start; the final value is chosen by measurement (E5). This variation is only meaningful because every codebook component holds at least 32 whistles (section 5), so its covariance has at least 31 directions of real variation rather than the ridge alone. With tau > 0, repeated symbols never sound identical.
2. Decode z with the VAE decoder to a 128 x 128 image, then take its contour with `sonify.image_contour` (threshold 0.05).
3. Synthesise a phase-continuous FM tone at fc_i + contour offset. Add:
   - the amplitude envelope of the synthetic generator (Tukey window with a slow amplitude ripple), ported from `src/whistlepipe/synth/whistles.py`. `[DECISION]` The Tukey taper is drawn from 0.15-0.3 instead of the generator's 0.15-0.6, so the fade-in lasts at most 68 ms and the detector does not find the start late.
   - `[DECISION]` a 2nd harmonic at -12 dB.

   `[DECISION]` The sample rate is 96 kHz and the output is a float32 WAV.
4. **Self-check:** the transmitter classifies the whistle's own contour (from step 2, without running the detector) with classifier A. If the contour is ambiguous or classified wrongly, it draws a new eps, up to 20 times, and otherwise falls back to the type's mean (tau = 0).
5. Place the whistle at its slot start time t_i.

### 4.5 Worked example

"HI" is 2 bytes. With 2 CRC bytes k = 4 and nsym = 8, so the payload is 12 bytes = 24 whistles. With the 12 header and 3 preamble whistles that makes 39 whistles, about 29 s at a mean interval of 0.75 s.

A 20-character sentence: k = 22, nsym = 11, so 33 bytes = 66 whistles, plus 15, giving 81 whistles, about a minute. That is about 2.5-3 bits per second of payload, normal for covert communication that imitates animals. E4 measures a faster option.

## 5. The whistle alphabet (codebook)

Built from the model in use (section 3.2): first on the development model, then rebuilt on the final model. K = 3,000.

1. **Eligible components.** `[DECISION]` Only components holding at least 32 whistles (N_k >= 32). Smaller components have covariances stuck at the ridge, so the variation in section 4.4 would do nothing and a shape-stability check would pass trivially. The epoch-101 fit has 539 such components. (The first version required 65 whistles; on epoch 101 that left only 20 components after the shape filter, too few to choose 17 from. At 32 the covariance still has at least 31 directions of real variation.)
2. **Filter.** Decode each eligible component's mean and 32 samples, extract the contours, and `[DECISION]` keep a component when:
   - its mean decode gives one clean contour, with no gaps longer than 3 columns;
   - its duration is 100-450 ms (the mean decodes are short, median 128 ms, and 100 ms whistles were detected at 10 dB);
   - its frequency span is 300 Hz to 5 kHz;
   - its samples stay close to its mean (median DTW distance below the median over all eligible components).
3. **One confusion pass.** Send every remaining candidate 50 times through the channel at 10 dB SNR on encounter-214 noise (even-index files). Classify each received whistle against all candidates with classifier A, which gives one confusion table. `[DECISION]` Candidates detected in less than 80 % of their sends are dropped. (The first version used 5 dB, where the detector found almost no whistles in the readiness probe.)
4. **Select 16 + 1.** Pick 17 types greedily so that the worst confusion between any two chosen types is as low as possible, breaking ties by the larger DTW distance. The candidate least confused with the other 16 becomes the signature whistle (preamble only), and the other 16 carry symbols 0-15.
5. **Verify.** Send each of the 17 types 200 times under the same conditions. If any pair is confused more than 2 % of the time, replace the worse type of that pair with the next candidate and verify again.
6. **Outputs:**
   - `codebook.npz`: component ids, mean latents, Cholesky factors, template contours, symbol mapping;
   - `codebook.json`: lineage (model hashes, settings, the confusion table);
   - a gallery: each type's contour plot and WAV.

The same procedure builds the M = 8, 32 and 64 codebooks for E4. If fewer than 65 candidates survive the filter, E4 stops at the largest M available.

**Fallback.** If fewer than 17 candidates survive, because the decodes are too blurry, the types come from medoids of real contours in `preprocessed/encounter_191` instead. The rest of the plan is unchanged, except that the VAE is not used at transmit time and tau has no meaning.

## 6. The channel ("sending")

The channel acts on the signal in this order: multipath, absorption, Doppler, then noise. The noise is added last because it was recorded at the hydrophone and has already been through the sea.

| Effect | How |
|---|---|
| Multipath | Image method: direct, surface (reflection -0.9), bottom (0.4) and surface-bottom paths. `[DECISION]` Water depth 50-1,000 m, source depth 5-30 m, receiver depth 5-50 m, range 0.2 / 0.5 / 1 / 2 km. Amplitude falls as 1/path length; delays are applied as fractional delays. |
| Absorption | Thorp's frequency-dependent loss over each path's length. |
| Doppler | Time-scaling by 1/(1 + v/c) with c = 1,500 m/s, v drawn from +/- 3 m/s. |
| Noise | Real channel-0 audio, resampled 500 to 96 kHz (polyphase 24/125) and high-passed at 2 kHz with the reproduction's 4th-order zero-phase Butterworth. **Encounter 214** for tuning, **encounter 276** for the final test. Encounter 191 is never used as noise, because the VAE trained on it. The noise contains real whistles, a realistic source of interference. Each file is tagged "quiet" or "busy" by its old-detector whistle count (from `preprocessed/`), as metadata for breakdowns. |
| SNR | Narrowband, as in the synthetic generator. Each whistle's direct path is scaled so that its level in its own 93.75 Hz bin is the target SNR above the median noise level in that bin; the echoes keep their relative gains. Swept from -5 to +25 dB in 2.5 dB steps. |
| Air test (optional) | Play the WAV through the laptop speaker and record it with the laptop microphone, as a real demonstration. |

`[DECISION]` The "clean" condition (E1) is never digital silence. It uses faint white noise at 40 dB SNR. In pure silence the detector's local noise floor drops to about -240 dB, so the faint spread of energy around a whistle would look strong. The detector never saw that in training, and the tracker drops frames where more than 30 % of the band is active.

Messages longer than one noise file use consecutive files of the same encounter (files follow each other with no gaps).

## 7. Message decoder (receiver)

1. **Detect.** Run the reproduction's S1-S7 chain (`whistlepipe.infer.preprocess`, with ridgenet-v2c and its tracker) on the received WAV. This gives every whistle track with its start time, frame-by-frame frequency contour and centre frequency.
   - `[DECISION]` Long recordings are processed in 60 s blocks with a 2 s overlap, and duplicate tracks in the overlaps are merged.
   - Every trial's tracks are cached. Tuning the classifiers, erasure thresholds and slot windows reuses them and never reruns the detector.
2. **Synchronise.**
   - Every track that classifies as the signature whistle is a candidate preamble start.
   - For each candidate, check whether the other two preamble slots (from the key's timing) also hold signature-like tracks.
   - Accept the best candidate with at least 2 of 3. This fixes the time origin t0.
3. **Header.** Match and classify the 12 header slots (steps 4 and 5) and decode RS(6, 2). This gives the length and the nonce, and from the nonce the payload's slot times and pitches. If the header fails, the message is lost.
4. **Slot matching.** For each expected slot, take a track that:
   - starts between 60 ms before and 150 ms after the expected time `[DECISION]` (late starts are the common error, and the next whistle starts at least 550 ms later, so the windows never overlap);
   - has its centre within +/- 1.5 kHz of the expected pitch `[DECISION]`.

   If several qualify, take the one with the closest start; ties go to the longer track. An empty slot is marked **erased**. A running linear fit of observed against expected start times, over confident matches only, corrects clock drift from Doppler.
5. **Classify.** Two classifiers are built. The one with the lower symbol error on encounter-214 noise becomes the default; both are reported.
   - **A, DTW templates:** DTW distance between the track's contour and each template contour, plus a duration term. Measured on encounter-214 noise at 10 dB (17 types x 40 sends) during P1:
     - `[DECISION]` The track's offsets are measured from the centre frequency the key gives for its slot, not from the track's own mid-range. The detector trims faint ends (median 21 ms shorter at 10 dB), which shifts a re-centred track; correct calls rose from 59 % to 79 %.
     - `[DECISION]` The duration term is asymmetric: 0.5 Hz per ms when the track is shorter than the template, 2 Hz per ms when it is longer.
     - `[DECISION]` Erased when best distance / second-best > 0.85.
     - Together these lowered the repair budget used per whistle (2e + f) from 0.29 to 0.21 at 10 dB.
   - **B, VAE encoder + GMM:** build the track's S8 image, encode it with the VAE encoder, and score it under the 16 chosen GMM components. The S8 image is a clean re-rendering of the detected contour, not the noisy spectrogram, so B sees exactly the information A sees and differs only in how it measures distance. It is kept as the reproduction-native comparison. Because the component covariances are narrow, its posteriors sit near 0 or 1 and cannot flag doubt. `[DECISION]` B therefore erases a call when the log-likelihood gap between the best and second-best component is below 10 nats (starting value).

   Both erasure thresholds are tuned on encounter 214.
6. **Repair and check.** Decode the payload with Reed-Solomon, passing the erased positions, then unscramble. Check the CRC. Only a passing CRC releases the text.
7. **Report:** the text (or "failed"), whistles detected, slots matched, erasures, bytes corrected, CRC result, and the time and frequency of every slot.

## 8. Evaluation

Every test message is generated, so the true text is known. No listening labels are needed.

### 8.1 Test messages

`[DECISION]`

- **Sweep set:** 50 messages per test point, random payloads of 8-32 bytes (about a minute of audio each).
- **Full set:** 200 messages, 150 random-byte payloads of 4-64 bytes and 50 English sentences. Used only for E1 and the frozen final run.

Each trial uses a new random key, a new nonce and a new channel draw.

### 8.2 Reliability measures

- Sync success rate and header success rate.
- Symbol error rate (among whistles not erased) and erasure rate.
- Byte error rate before Reed-Solomon.
- **Message success rate:** exact text and CRC passed.
- **False accepts:** CRC passed but the text is wrong. Must be 0.
- Throughput: payload bits per second of airtime.
- **No-message test:** run the receiver on 50 minutes of noise-only audio from encounter 276 with random keys. Any accepted message is a false alarm. Must be 0.

### 8.3 Experiments

| ID | What varies | Noise | Messages |
|---|---|---|---|
| E1 | Clean (40 dB white noise, no channel effects) | white | full set |
| E2 | SNR -5 to +25 dB (13 points), quiet vs busy files | 214, then 276 | sweep set |
| E3 | Multipath range (4) x SNR 5, 10, 20 dB; Doppler drawn per trial | 214, then 276 | sweep set |
| E4 | Codebook size M = 8 / 16 / 32 / 64 x 5 SNRs (0-20 dB): speed vs reliability | 214 | sweep set |
| E5 | Variation tau = 0 / 0.25 / 0.5 / 1 x 5 SNRs: naturalness vs reliability | 214 | sweep set |
| E6 | Classifier A vs B, on the cached E2 tracks | 214, then 276 | (reuses E2) |
| E7 | Covertness (8.5), on the coded whistles detected in E2 | 276 | (reuses E2) |
| E8 | Baseline modem (8.5), 13 SNRs | 214, then 276 | sweep set |
| Final | Frozen settings, SNR 10 dB, no multipath | 276 | full set |

All of the table above runs on the final model. Defaults (M, tau, classifier, erasure thresholds, slot windows) are chosen on encounter 214, written into `config.toml` and frozen. Only then do the encounter-276 runs start.

On the development model only two smoke tests run `[DECISION]`:

- E1;
- the **E2 smoke subset:** SNR 5, 10 and 20 dB, 10 sweep-set messages each, on quiet encounter-214 files.

Together they take under an hour of detector time.

Possible later upgrades, each measured before adoption:

- larger M (E4);
- 1-2 extra bits per whistle from the centre-frequency band;
- overlapping whistles.

### 8.4 Computing budget

The detector (S2-S9) takes about 5-10 s per minute of audio on the laptop: 0.6-1.5 s per 8 s clip in the two saved runs in `runs/infer/`.

| Work | Audio | Detector time |
|---|---|---|
| P1 confusion pass (<= 203 candidates x 50) | about 2 h | 10-20 min |
| P1 verification (17 x 200) | about 45 min | 4-7 min |
| E4 codebook verifications (8 + 32 + 64 types x 200) | about 4.3 h | 20-45 min |
| E1 (200 messages) | about 5 h | 25-50 min |
| E2 (13 x 2 x 50, two encounters) | about 43 h | 3.5-7 h |
| E3 (12 x 50, two encounters) | about 20 h | 1.7-3.3 h |
| E4 and E5 (20 x 50 each, one encounter) | about 33 h | 2.8-5.6 h |
| E8 (13 x 50, two encounters) | about 22 h | 1.8-3.6 h |
| Final run + no-message test | about 6 h | 0.5-1 h |
| **Total** | | **about 11-23 h**, run unattended (overnight) |

E6 and E7 reuse the E2 tracks and cost no detector time. The budget is for the final model. The development-model smoke tests and the P1 runs on the development model add about 1.5 hours.

### 8.5 Covertness and the baseline

Covertness asks whether the coded whistles can be told apart from real ones. Each measure compares coded whistles, as detected by the receiver in E2, with real whistles from encounter 276. Two real references are used:

- **all** real whistles;
- **in-range** real whistles: those within the codebook's limits (duration 100-450 ms, span 0.3-5 kHz, centre 5-12 kHz).

Against all whistles a classifier can win from the limits alone. The in-range comparison isolates whether the shapes themselves look real.

- **Feature distance:** Wasserstein-1 distance for each of the reproduction's 7 contour features (L, f_min, f_max, df, f_start, f_end, f_c).
- **Likelihood:** mean GMM log-likelihood of the VAE-encoded latents, coded vs real.
- **Discriminator:** a classifier (scikit-learn gradient boosting) trained to tell coded from real on the per-whistle features. 5-fold cross-validated ROC AUC: 0.5 means indistinguishable, 1.0 means obvious.
- **Not measured:** sequence-level cues. The coded stream is one steady whistler that never overlaps itself, while the recordings are choruses. Per-whistle tests cannot see this; the write-up states it as a limitation.

**Baseline modem:** identical framing, key, nonce, schedule and receiver, but each symbol is a 300 ms constant tone at one of 16 frequencies between 5 and 12 kHz (16-FSK), classified by its mean frequency. It should be at least as reliable and clearly artificial. Comparing it with WhistleCode shows the price paid for sounding natural.

### 8.6 Pass marks `[DECISION]`, frozen before the encounter-276 runs

| Test | Pass mark |
|---|---|
| E1 clean | 100 % of the 200 messages exact |
| Final run: encounter 276, SNR 10 dB, no multipath | >= 95 % of messages exact |
| False accepts and no-message false alarms | 0 |
| E7 discriminator AUC against in-range real whistles (chosen tau) | <= 0.75 |

A failed mark is reported as failed, with the measured value; it is never rewritten as a pass.

## 9. Phases

| Phase | Model | Work | Done when |
|---|---|---|---|
| P0 | none | Folder, `config.toml`, key and nonce streams, framing (UTF-8, CRC, scrambler, header), Reed-Solomon, unit tests | Bytes -> symbols -> bytes round trip passes, including with erasures and errors up to the RS limit |
| P1 | development | Codebook: eligibility, filter, confusion pass, selection, verification, gallery, hash pinning | `codebook.npz` + gallery |
| P2 | development | Transmitter: schedule, preamble, header, synthesis, self-check, `send` command | A message becomes a WAV |
| P3 | none | Channel: multipath, absorption, Doppler, noise at SNR, `channel` command | A WAV goes through any channel setting |
| P4 | development | Receiver: detect with track cache, sync, header, slots, both classifiers, Reed-Solomon, CRC, `receive` command; E1 and the E2 smoke subset | **E1 passes: working send -> channel -> receive demo** |
| M | (reproduction) | Training resume to epoch 150 on Colab, then on the laptop re-encode, refit the GMM at K = 3,000, recompute the component features and redo the reproduction's evaluations (section 3.3) | New `final.pt` and `gmm.npz` in place; the reproduction's tables and figures redone |
| S | final | Swap: rebuild the codebook, rerun E1 (section 3.4) | Codebook pinned to the epoch-150 files; E1 passes |
| P5 | final | Sweeps E2-E6, tune on 214, freeze, encounter-276 runs | Reliability curves and tables |
| P6 | final | Covertness E7, baseline E8, no-message test | Covertness table |
| P7 | final | README, figures, results; optional air test; optional "send a message" panel on the project web page | Write-up |

Order:

- P0-P4 can be built now, on the development model.
- M can run at any time, in parallel, because it touches only the reproduction.
- S needs both P4 and M.
- P5-P7 come after S.
- If training is not resumed, skip M and S.

Effort:

- **P0-P4:** about 1.5 days of work.
- **M:** about 1.75 A100 hours on Colab, then under an hour on the laptop.
- **S:** about 1-1.5 hours, mostly unattended.
- **P5-P7:** about 1.5 days of work, plus 11-23 hours of unattended detector time (section 8.4).

No model is trained in WhistleCode itself; the only fitted model is the covertness discriminator, which takes seconds.

P0-P4 is the part to have first: it is a complete, demonstrable system. P5-P7 measure and explain it.

## 10. Folder layout and commands

```
whistlecode/
  PLAN.md            this document
  README.md          what it is, how to run it, results (P7)
  config.toml        every parameter with its tag
  whistlecode.py     command-line entry point (adds src/ to sys.path, like whistle.py)
  wcode/
    keys.py          key and nonce -> random streams
    framing.py       text <-> bytes, CRC, scrambler, header, symbols
    fec.py           Reed-Solomon wrapper with erasures
    codebook.py      build, check, pin and load the codebook
    synth.py         contour -> audio (envelope and harmonic ported from the synthetic generator)
    schedule.py      slot times and pitches from the key and nonce
    transmitter.py   message -> WAV
    channel.py       multipath, absorption, Doppler, noise, SNR
    classify.py      classifiers A (DTW) and B (VAE encoder + GMM)
    receiver.py      WAV -> message, with the track cache
    baseline.py      16-FSK modem
    evaluate.py      experiments E1-E8 and the final run
  tests/
  outputs/           gitignored (codebook gallery, WAVs, track cache, results)
```

| Command | Does |
|---|---|
| `build-codebook` | Section 5 |
| `send "TEXT" --key K --out msg.wav` | Message -> WAV |
| `channel msg.wav --noise 276 --snr 10 [--range 1 --doppler 1.5] --out rx.wav` | Sends the WAV through the simulated channel |
| `receive rx.wav --key K` | WAV -> message and report |
| `evaluate E2` (etc.) | Runs one experiment |

## 11. Reuse, boundaries and requirements

**Imported from the reproduction (read-only):**

- `whistlepipe.audio`;
- `whistlepipe.infer.preprocess` (S1-S7, ridgenet-v2c and the tracker);
- `whistlepipe.sonify.image_contour`;
- the VAE model, `GaussianMixtureEM` and `vaegmm.features`.

**Ported (copied, with an equivalence test against the original):** the envelope part of `src/whistlepipe/synth/whistles.py`. The only intended difference is the narrower taper range (section 4.4).

**Never edited by WhistleCode:** `src/`, `configs/`, `models/`, `preprocessed/`, the encounter audio folders, `web/` (until the optional P7 panel, and only with your go-ahead), `whistleflow/`. Phase M changes `models/` through the reproduction's own commands, not through WhistleCode.

**Model files needed:** the V1 `final.pt` and `gmm_K3000/gmm.npz`, matching the hashes in `codebook.json`. `gmm.npz` is about 100 MB and is not in git, so any other machine needs it copied over.

**Installs (each needs your approval first):**

- `reedsolo`, a small pure-Python Reed-Solomon library. If it is declined, P0 includes writing a Reed-Solomon codec by hand.
- `sounddevice`, only for the optional air test.

**Data:** only the three local encounters (191 for the codebook and centre frequencies, 214 and 276 for noise). No downloads.

## 12. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| The model changes after the codebook is built (training resume) | The codebook no longer matches the decoder and encoder | Planned: phase S rebuilds the codebook on the final model; hash pinning (section 3.5) refuses a mismatched model and catches a new VAE with an old GMM |
| Heavy runs done on the development model | 11-23 hours of detector time spent twice | Development model limited to smoke tests (section 3.2) |
| Decodes are blurry (epoch-101 Table 1 PSNR 32.8 dB vs the paper's 44.5) | Some components give broken contours | Eligibility and filter (section 5); fallback to real-contour medoids |
| Real whistles land in a slot | Wrong symbols | Key-based time and pitch windows, Reed-Solomon, erasure on ambiguity; measured separately on busy files |
| Preamble or header missed | Whole message lost | 3 signature whistles, 2 of 3 enough; header can lose 4 of 6 bytes; sync and header rates reported on their own |
| Detector finds a start late or splits a whistle at low SNR | Wrong or missing symbol | Shorter fade-in, asymmetric slot window, closest-start then longest-track rule, erasure on ambiguity |
| Detector time | Long evaluation runs | Sweep set of 50 short messages, track cache, unattended overnight runs (section 8.4) |
| Low speed (about 2.5-3 bit/s) | Long airtime | Inherent to the approach; E4 and the centre-frequency bits are the measured upgrade path |
| Doppler drift over long messages | Slots slide out of their windows | Running drift correction from confident matches |
| Preamble and header rhythm repeats per key | 15 whistles with the same timing in every message under one key | Accepted; a new key changes it. Stated as a limitation |
| Sequence-level giveaway (one steady whistler, no overlaps) | Covertness weaker than per-whistle scores suggest | Stated as a limitation (section 8.5) |

**Ethics:** this project is simulation only (plus the optional air test). Playing synthetic whistles near wild animals would need permits; the README will say so.

## 13. Parameters

All `[DECISION]` unless stated.

| Parameter | Default | Set in |
|---|---|---|
| GMM components K | 3,000 (unchanged) | 3.1 |
| Model file read | `final.pt`, never `last.pt` | 3 |
| Development model | epoch 101 (`final.pt` SHA-256 `fcb1a2e6...`), smoke tests only | 3.2 |
| Final model | epoch 150 from the resumed run, GMM refitted | 3.3, 3.4 |
| Model pinning | checkpoint -> latents -> GMM chain checked by `build-codebook`; SHA-256 of `final.pt` and `gmm.npz` in `codebook.json` | 3.5 |
| Key -> streams | one SHA-256 seed per stream over domain `whistlecode/v1`, part, stream name, key (and the nonce for the payload); scrambler bytes from SHA-256 in counter mode; other draws from NumPy PCG64 | 4.1 |
| Nonce | 1 random byte per message, in the header | 4.1 |
| Max payload | 140 bytes | 4.2 |
| Min payload | 1 byte (an empty message is refused) | 4.2 |
| CRC | CRC-16/CCITT-FALSE | 4.2 |
| Erased byte fill | 0, written into erased positions before decoding (the decoder ignores it) | 4.2 |
| Payload parity | max(8, ceil(k / 2)) bytes | 4.2 |
| Header code | RS(6, 2): length + nonce | 4.2 |
| Bits per whistle | 4 (M = 16), high nibble first | 4.2, E4 |
| Preamble | 3 signature whistles, 2 of 3 to sync | 4.2, 7 |
| Interval (start to start) | uniform 0.55-0.95 s | 4.3 |
| Centre frequency | encounter-191 distribution, 5-12 kHz | 4.3 |
| Variation tau | 0.5 (set by E5) | 4.4 |
| Envelope taper | Tukey 0.15-0.3 | 4.4 |
| Harmonic | 2nd at -12 dB | 4.4 |
| Self-check | classifier A on the contour, 20 redraws, then tau = 0 | 4.4 |
| Sample rate | 96 kHz, float32 WAV | 4.4 |
| Codebook eligibility | N_k >= 32 | 5 |
| Codebook duration | 100-450 ms | 5 |
| Codebook span | 300 Hz - 5 kHz | 5 |
| Confusion pass | 50 sends per candidate, 10 dB, 214 noise (even-index files); drop candidates detected < 80 % | 5 |
| Verification | 200 sends per type, <= 2 % confusion per pair | 5 |
| Channel order | multipath, absorption, Doppler, then noise | 6 |
| SNR definition | narrowband, per 93.75 Hz bin, on the direct path | 6 |
| Clean condition | 40 dB SNR white noise, never digital silence | 6 |
| Noise for tuning / test | encounter 214 / 276 | 6 |
| Receiver blocks | 60 s with 2 s overlap | 7 |
| Slot time window | -60 ms to +150 ms around the expected start | 7 |
| Slot pitch window | +/- 1.5 kHz | 7 |
| Classifier A input | track offsets from the slot's expected centre frequency | 7 |
| Classifier A duration term | 0.5 Hz/ms if the track is shorter, 2 Hz/ms if longer | 7 |
| Erasure, classifier A | distance ratio > 0.85 (re-tuned on 214 in P5) | 7 |
| Erasure, classifier B | log-likelihood gap < 10 nats (tuned on 214) | 7 |
| Sweep set | 50 messages of 8-32 bytes per point | 8.1 |
| E2 smoke subset (development model) | SNR 5, 10, 20 dB x 10 messages, quiet 214 files | 8.3 |
| Full set | 150 random (4-64 bytes) + 50 sentences | 8.1 |
| No-message test | 50 min of encounter-276 noise | 8.2 |
| Covertness references | all and in-range real whistles of encounter 276 | 8.5 |
| Pass marks | section 8.6 | 8.6 |

## 14. Revision history

- **2026-11-17, first version.**
- **2026-11-17, after review:**
  - Added the model dependency, the K = 3,000 decision, the training-resume steps with the `final.pt` trap, and hash pinning (section 3, phase M).
  - Codebook components must hold at least 65 whistles. The 10-round swap test became one confusion pass plus a verification.
  - Classifier B is described as seeing the same contour as A, and erases on a log-likelihood gap instead of a posterior.
  - Slot window -60/+150 ms; envelope taper 0.15-0.3.
  - The clean test uses a 40 dB noise floor, not silence.
  - Per-message nonce (header RS(6, 2), 12 whistles).
  - Channel order fixed: noise is added last.
  - The self-check classifies the contour directly.
  - Sweep set of 50 short messages, track cache and a computing budget (section 8.4).
  - Covertness also against in-range real whistles; the sequence-level limitation is stated.
  - No-message test added.
- **2026-11-17, build now, swap later:**
  - WhistleCode is built on the epoch-101 model as a development model, with smoke tests only.
  - The epoch-150 model becomes the final model: new phase S rebuilds the codebook, then P5-P7 run once on it.
  - Recorded the Drive check: no `final.pt` on Drive, so the Colab resume is clean, and the trap is local only.
  - WhistleCode reads `final.pt`, never `last.pt`.
  - `build-codebook` checks the checkpoint -> latents -> GMM chain.
  - Sections 3.2-3.5 were rewritten and the phase table reordered.
- **2026-11-18, after the P0 review:**
  - Section 4.1 now describes the key derivation as built: per-stream SHA-256 seeds and counter-mode scrambler bytes, not one NumPy seed.
  - The CRC variant is named exactly: CRC-16/CCITT-FALSE.
  - The 1-byte minimum payload and the erased-byte fill are listed in section 13.
- **2026-11-18, P1 built (measured changes):**
  - Codebook eligibility lowered from N_k >= 65 to N_k >= 32, and the minimum duration from 150 to 100 ms: with the first values only 20 components passed the shape filter on epoch 101.
  - Confusion pass and verification at 10 dB instead of 5 dB (the detector misses almost every whistle at 0-5 dB); candidates detected < 80 % are dropped.
  - Classifier A measures a track from its slot's known centre frequency, uses an asymmetric duration term, and erases above a distance ratio of 0.85.
  - P1 needed parts of later phases, built now: whistle synthesis (P2), real noise and narrowband SNR (P3), the detector wrapper and slot matching (P4), classifier A (P4).
