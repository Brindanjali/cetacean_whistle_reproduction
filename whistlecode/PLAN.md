# WhistleCode plan: hiding messages in whistles

Status: plan written 2026-11-17 and revised twice the same day (section 14). P0 (keys, framing, Reed-Solomon, tests, the `frame` and `roundtrip` commands) and P1 (the codebook, with the pieces of P2-P4 it needs: whistle synthesis, noise and SNR, the detector wrapper and classifier A) were built on 2026-11-18, followed by P2 (the transmitter and the `send` command). P1 changed some plan values after measuring them; section 14 lists the changes. The idea was finalised on 2026-11-18 (next section), and the complete format v2 pipeline was built the same day: `send`, `channel` and `receive` now use format v2. The `frame` and `roundtrip` commands still show format v1.

This enhancement replaces WhistleFlow. The `whistleflow/` folder stays as it is but will not be implemented. WhistleFlow's no-images rule does not apply here, because this enhancement reuses the reproduction's spectrogram detector and VAE.

How to read this document:

- `[DECISION]` marks a choice made here because nothing fixes it. It is the same tag the reproduction's configs use. Every one is listed again in section 13 with its default.
- Thresholds in section 8.6 are frozen before the final test runs, so a result cannot move its own goalpost.
- "The reproduction" means `src/whistlepipe`, `configs/`, `models/`, `preprocessed/` and the encounter audio folders. WhistleCode only imports from them and never edits them.
- "Message encoder" is the transmitter and "message decoder" is the receiver. The VAE has its own encoder and decoder, which appear inside them: the VAE decoder makes the whistles, and the VAE encoder is one way to read them back.

## Final idea (2026-11-18)

**A text message is hidden in a stretch of real-sounding false killer whale whistling. Some whistles carry the message, the rest are cover, and a receiver holding the shared key turns the audio back into the exact text.** Where this section differs from older text below, this section wins.

```
SEND     text -> compact bits + CRC-16 -> scramble with the key -> Reed-Solomon over 6-bit symbols
              -> each symbol = one whistle: 16 shapes (4 bits) x 4 pitches (2 bits)
              -> placed at real whistle times from the rhythm bank, among cover whistles -> WAV

CHANNEL  WAV + real ocean noise at a set SNR

RECEIVE  WAV -> whistlepipe detector and tracker -> find the 3-whistle start signal -> read the header
              -> read each data slot's pitch and shape -> Reed-Solomon repair -> unscramble -> CRC check -> text
```

| Part | Final decision |
|---|---|
| Text | 5 bits per character for A-Z, space and `. , ? ! -`; raw UTF-8 for anything else |
| Error correction | CRC-16, then Reed-Solomon over GF(64), so one whistle is one code symbol |
| Whistle alphabet | The current 16 shapes from the VAE-GMM, **at their own lengths**, plus 1 signature whistle. Shapes are not stretched |
| Pitch | Four key-chosen candidates per slot, following the real pitch distribution |
| Timing | Real whistle times from a bank of encounters 191 and 214; about 1 played whistle in 4 carries data |
| Key | The shared key and a per-message nonce choose the bank position, pitches and scrambling |
| Decoder | Classifier A: compares each detected whistle with the 16 shapes |

Measured in the final gate run: about 3,200 data whistles per SNR in real encounter-214 noise, on the epoch-101 model. Message success in this table is predicted from the measured whistle error rates. Complete messages were decoded later; see "Pipeline results" below.

| Measure | 10 dB | 15 dB | 20 dB (outside the gate) |
|---|---|---|---|
| Whistles lost / wrong | 15.1 % / 4.5 % | 8.8 % / 3.8 % | 9.4 % / 3.0 % |
| Predicted success, 12 characters (v1 -> final) | 56 % -> 88 % | 92 % -> 97 % | 91 % -> 98 % |
| Predicted success, 20 characters (v1 -> final) | 44 % -> 84 % | 91 % -> 96 % | 90 % -> 98 % |
| Predicted success, 60 characters (v1 -> final) | 35 % -> 79 % | 97 % -> 96 % | 96 % -> 98 % |
| Rhythm detection score on quiet noise (limit 0.60; v1 scores 1.00) | 0.56 | 0.55 | 0.62 |
| Wrong pitch (limit 1 %) | 2.13 % | 1.53 % | 1.19 % |

"MEET AT DAWN" needs 31 data whistles, about 41-51 s.

**By its own rules the gate still FAILED, and this is recorded as measured.** These gaps stay open, to be corrected once the pipeline runs:

- Wrong pitch is above the 1 % limit at 10 and 15 dB.
- At 15 dB a 60-character message is predicted slightly below format v1 (96.2 % against 97.0 %).
- With many real whistles already in the noise, the rhythm score is 0.66-0.67, above the 0.60 limit.
- Whistle shape realism, loudness patterns and a hydrophone array locating one source are not covered by these results.

**Build order: the complete pipeline first, then correct the mistakes it makes.**

1. **Format v2:** compact alphabet, GF(64) code, frame, rhythm bank, slot schedule, transmitter.
2. **Channel:** real noise at a set SNR, and the `channel` command.
3. **Receiver:** start-signal search, header, slot reading, repair, and the `receive` command.
4. **End-to-end run:** text in, audio file, text out; then fix what it gets wrong.

**Left until the pipeline works:** multipath, absorption and Doppler; classifier B; the chirp baseline modem; the full evaluation sweeps; the epoch-150 model swap.

### Pipeline results (2026-11-18)

All four build steps are done. Each trial sent one message with its own key through real encounter-214 noise, and the receiver knew only the key (`experiments/e2e_run.py`, results in `outputs/e2e_final/`). There were 10 messages per cell, on the epoch-101 model.

| Exact messages | 12 characters | 20 characters | 60 characters | All | Whistles lost / wrong |
|---|---|---|---|---|---|
| 10 dB | 8/10 | 7/10 | 6/10 | 21/30 | 18.6 % / 5.3 % |
| 15 dB | 10/10 | 10/10 | 9/10 | 29/30 | 8.4 % / 4.1 % |
| 20 dB | 7/10 | 10/10 | 10/10 | 27/30 | 7.9 % / 4.0 % |

- **Overall:** 77 of 90 messages came back exact. The frame was found in all 90 recordings.
- **False messages:** no wrong text was accepted, and none of the 10 recordings without a message reported one. A separate check on the same recordings found no false message in 300 tries on empty recordings and 270 tries with a wrong key.
- **Two receiver fixes after the first run (73 of 90):** when several tracks fit a slot, the receiver reads the one closest to a codebook shape, and when a repair fails it retries with the most doubtful whistles marked as lost. They were chosen on these same recordings, so 77 of 90 is slightly optimistic, and a gain of 4 messages is within chance at this sample size.
- **Where the errors come from:** they are spread evenly over the 16 shapes, and the slot time and pitch windows are not too tight. Most missed whistles have no detector track near their slot.

Known gaps:

- **Messages take longer than planned.** The median recording for 12 characters is 66-88 s, against the 41-51 s estimated in section 4.6. Sparse bank stretches and the joins between stretches add the time.
- **20 dB is not better than 15 dB** for whistle errors. About 4 % of whistles stay wrong even in light noise.
- **The SNR differs slightly from the gate test.** The channel plays the whole message at one gain, as a real source would, so individual whistles sit above or below the target where the noise spectrum is uneven.
- **Not tested yet:** the epoch-150 model. Multipath, absorption, Doppler and encounter-276 noise were tested on 2026-11-19 (see "Sea channel test").

### Realism upgrade (2026-11-19)

The sender now plays recorded material, and the message format and the receiver are unchanged (`wcode/realism.py`, built once with `build-realism`). No sea background is added: the file is silent between sounds.

- **Real voices:** every whistle takes its loudness pattern and 2nd and 3rd harmonics from one of 3,383 clean recorded whistles.
- **Virtual animals:** six animals per message, each with its own loudness and tone. Cover whistles span 0-10 dB above the base level, and data whistles 5-10 dB, because quieter data whistles were lost in heavy noise.
- **Recorded clicks:** 53,729 clean 2 ms clicks in regular trains, played at the times they were recorded during the same bank stretches, and left out within 12 ms of a data whistle.
- **Real shapes (built, switched off):** `realism.real_shapes = true` gives data whistles the shape of a real whistle of their type. Type 15 has no usable real whistles and would keep its VAE shapes.

Two tests were run on the same 90 messages. The realism score is how well a trained detector separates our data whistles from real encounter-276 whistles (0.50 = it cannot, 1.00 = always). Two real encounters (214 against 276) score 0.751, which is about the lowest to expect.

| Version | Exact messages at 10 / 15 / 20 dB | Total of 90 | Realism score |
|---|---|---|---|
| Before the upgrade | 21 / 29 / 27 | 77 | 0.992 |
| Real shapes, data whistles as quiet as cover whistles | 6 / 23 / 27 | 56 | 0.908 |
| VAE shapes, data whistles as quiet as cover whistles | 15 / 28 / 28 | 71 | not measured |
| **VAE shapes, data whistles kept loud (in use)** | **26 / 28 / 28** | **82** | **0.954** |
| Real shapes, data whistles kept loud | 24 / 25 / 27 | 76 | 0.920 |

- **Choice:** the pass mark, set before the test, was at least 77 of 90. Real shapes missed it by one message, so VAE shapes stay in use. The gap of 6 messages is small at this sample size.
- **Part of the decoding gain is extra loudness.** Data whistles now sit 0-5 dB above the level the SNR refers to, where they used to sit exactly at it.
- **A trained detector still finds our data whistles easily.** The upgrade removed the harmonic clue, and the main clues left are in the whistle shapes (curve fit, net rise, length, span).
- **Not scored:** the clicks, the animal group as a whole, and human listening.

### Sea channel test (2026-11-19)

The channel of section 6 is built (`wcode/sea.py`, `channel --range --doppler`): four image-method paths, Thorp absorption over each path, and one Doppler time-scaling per message. `experiments/sea_run.py` sent the same 90 messages under four conditions in encounter-276 noise, which the receiver was never tuned on. Each message kept one random sea (range 0.2-2 km, water 50-1,000 m, closing speed up to 3 m/s) in every condition. The receiver was not changed. The SNR is the level of the direct path at the hydrophone. Results are in `outputs/sea_run/`.

| Condition | Exact at 10 / 15 / 20 dB | Total of 90 | Whistles lost / wrong |
|---|---|---|---|
| Ocean noise only | 21 / 23 / 21 | 65 | 13.3 % / 7.3 % |
| Echoes and absorption | 12 / 20 / 10 | 42 | 17.6 % / 13.5 % |
| Doppler | 16 / 12 / 11 | 39 | 36.6 % / 9.3 % |
| **Echoes, absorption and Doppler** | **7 / 10 / 6** | **23** | **38.5 % / 13.7 %** |

- **False messages:** no wrong text was accepted in 360 messages, and none of the 10 recordings without a message reported one.
- **Unseen noise costs 17 messages on its own.** The same sender and receiver decoded 82 of 90 in encounter-214 noise. On encounter 276 a stronger signal does not help (13 % of whistles lost at every SNR), so the loss is not explained by the noise level. The cause is not yet known.
- **Doppler fails through timing.** The receiver has no drift correction, so slots slide out of their -60 / +150 ms windows. Messages decoded by total drift: under 30 ms 9/12, 30-60 ms 8/16, 60-150 ms 18/33, over 150 ms 4/29. At 60-150 ms, whistles heard early lost 44.8 % and whistles heard late 13.8 %, as the narrower early window predicts. The pitch shift itself (at most 0.2 %) is small.
- **Echoes make whistles misread.** Wrong whistles nearly double, and range makes little difference (13/24, 11/24, 8/18 and 10/24 from 0.2 to 2 km).
- **Limits of the model:** the sea surface is still, all paths share one Doppler, and sound-speed layers are left out. A real sea is likely to be harder.
- **Encounter 276 has now been seen.** Receiver fixes must be developed on encounter-214 noise, and then checked once on 276.
- **These results predate the slot-reading fix below,** so the sea test must be run again before it is compared with anything newer.

### Normal conditions proved (2026-11-19)

Normal conditions means the sent file plus real ocean noise, with no echoes or movement. The target is the plan's final mark: at least 95 % of messages exact on encounter 276.

**The cause.** About 8 % of whistles were lost or misread even in almost silent audio, so noise was not the root problem. The detector often joins a little of the sound before or after a whistle onto its track. With those frames removed by hand, correct reads rose from 91.2 % to 99.0 % in clean audio and from 88.8 % to 97.5 % in encounter-214 noise.

**The fix** (`Receiver.read_slots`, the sender is unchanged). The key gives the moment each whistle starts, and each shape has its own length. Each of the 16 shapes is now compared with only the part of the track where that shape would sound, and the pitch is read from that part. A track that starts well before the slot can now be read too. The settings were tuned on the 90 encounter-214 tuning messages only.

| Test | Before the fix | After the fix | Whistles lost / wrong after |
|---|---|---|---|
| Almost silent audio, 30 messages | 30 | 30 | 98.0 % read right |
| Encounter-214 noise, the 90 tuning messages | 82 | 87 | 3.6 % / 2.3 % |
| **Encounter-214 noise, 90 fresh messages** | not run | **90** | 2.4 % / 1.1 % |
| **Encounter-276 noise, 90 messages** | 65 | **87** | 5.0 % / 4.0 % |

- **Encounter 276 by noise level:** 29/30 at 10 dB, 28/30 at 15 dB and 30/30 at 20 dB. The mark is met (96.7 %). No message that decoded before now fails.
- **Sample size:** with 90 messages, the true rate on encounter 276 lies between about 91 % and 99 % (95 % confidence).
- **False messages:** no wrong text was accepted in those 180 messages. The 20 recordings without a message reported none, and 360 tries with a wrong key reported none.
- **Not covered:** echoes, absorption and Doppler, and the epoch-150 model. Data whistles still sit 0-5 dB above the level the SNR refers to.

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

This diagram shows format v1, as built through P2. Phase F replaces the 4-bit symbols with the shorter format v2 (section 4.6). The stages stay the same.

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

- **Smoke tests only:** E1 and the E2 smoke subset (section 8.3). The overnight sweeps, the freezing of settings and the encounter-276 runs wait for the final model, so the full evaluation's detector time (section 8.4) is spent once.
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

Sections 4.2 to 4.5 describe format v1, as built through P2. Section 4.6 describes the format that replaces it.

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
- As built (`wcode/schedule.py`): the 15 preamble and header slots come from the key alone, and the payload slots from the key and nonce, starting one drawn interval after the last header slot. Each pitch is an index into the sorted pool of centre frequencies, so sender and receiver must share that pool.

### 4.4 Making one whistle

For each slot i, with the type of its symbol (the signature whistle in the preamble):

1. Sample a latent from the type's GMM component: z = mu_s + tau * L_s * eps, where L_s is the Cholesky factor of the component covariance and eps comes from the variation stream. `[DECISION]` tau = 0.5 to start; the final value is chosen by measurement (E5). This variation is only meaningful because every codebook component holds at least 32 whistles (section 5), so its covariance has at least 31 directions of real variation rather than the ridge alone. With tau > 0, repeated symbols never sound identical.
2. Decode z with the VAE decoder to a 128 x 128 image, then take its contour with `sonify.image_contour` (threshold 0.05).
3. Synthesise a phase-continuous FM tone at fc_i + contour offset. Add:
   - the amplitude envelope of the synthetic generator (Tukey window with a slow amplitude ripple), ported from `src/whistlepipe/synth/whistles.py`. `[DECISION]` The Tukey taper is drawn from 0.15-0.3 instead of the generator's 0.15-0.6, so the fade-in lasts at most 68 ms and the detector does not find the start late.
   - `[DECISION]` a 2nd harmonic at -12 dB.

   `[DECISION]` The sample rate is 96 kHz and the output is a float32 WAV.
4. **Self-check:** the transmitter classifies the whistle's own contour (from step 2, without running the detector) with classifier A, among all 17 types. `[DECISION]` The shape must also stay within the codebook's duration, span and gap limits. If it fails, the transmitter draws a new eps, up to 20 times, and otherwise falls back to the type's mean (tau = 0).
5. Place the whistle at its slot start time t_i. `[DECISION]` The WAV has 0.5 s of silence before the first whistle and after the last, and its peak is -3 dBFS; the channel sets the SNR afterwards.

All the variation, including the envelope, comes from the message's variation stream, so the same message, key and nonce always give the same audio.

### 4.5 Worked example

"HI" is 2 bytes. With 2 CRC bytes k = 4 and nsym = 8, so the payload is 12 bytes = 24 whistles. With the 12 header and 3 preamble whistles that makes 39 whistles, about 29 s at a mean interval of 0.75 s.

A 20-character sentence: k = 22, nsym = 11, so 33 bytes = 66 whistles, plus 15, giving 81 whistles, about a minute. That is about 2.5-3 bits per second of payload, normal for covert communication that imitates animals. Section 4.6 is the faster format.

### 4.6 Compact format v2 (built 2026-11-18)

"MEET AT DAWN" takes 59 whistles and about 44 s in format v1. Only 24 of those whistles carry the text; the other 35 are parity (16), CRC (4), header (12) and preamble (3). Format v2 makes four changes.

**1. Borrowed real rhythm.** A steady stream gives the message away. On 44 s windows of encounters 191, 214 and 276, a classifier trained on two encounters and tested on the third scored as follows (0.50 = guessing, 1.00 = always caught):

| Timing of the whistles | Detection score |
|---|---|
| Steady gaps of 0.55-0.95 s (format v1) | 1.00 |
| Steady gaps of 0.40-0.60 s (the first v2 idea, dropped) | 1.00 |
| Borrowed real rhythm, data whistles with codebook lengths | 0.66 |
| Borrowed real rhythm, cover whistles dropped where they collide | 0.71-0.78 |
| **Borrowed real rhythm with the rules below** | **0.50** |

`[DECISION]` The rules:

- **Rhythm bank:** the times, lengths, pitches and contours of the real whistles of encounters 191 and 214, in 44 s stretches with at least 10 whistles (about 7 hours). Encounter 276 stays out, as the unseen real reference for the final test. Sender and receiver hold the same bank, pinned by its SHA-256.
- **Where a message sits in the bank:** the key alone picks the stretch for the preamble and header. The key and nonce pick the stretch for the payload, which joins the first one at a real silence of at least 1 s.
- **Every whistle of the stretch is played** at its real time and length. Cover whistles are re-synthesised from their real contours (`preprocessed/encounter_*/contours.npz`).
- **A real whistle can carry data** if it lasts 100-450 ms, no other whistle starts from 60 ms before it to 150 ms after it, and the previous data whistle started at least max(0.35 s, its length + 0.1 s) earlier. About 26 % of the played whistles carry data.
- **A data whistle keeps the real whistle's start and its own shape's length.** The receiver reads the slot times from the bank. (Stretching each shape to the real whistle's length was tested and dropped; see the results below.)
- **Collisions:** a cover whistle that overlaps a data whistle within 1 kHz of its pitch, or follows it within 100 ms at that pitch, moves to another pitch and keeps its time and length. About 10 % of cover whistles overlap a data whistle in this way. Dropping them instead raised the detection score to 0.71-0.78.

The 0.50 is expected, because the played timing is a copy of real timing. It shows only that the rhythm is safe. Whistle shape, loudness and the fact that every whistle comes from one place are separate questions (section 8.5).

**2. Pitch carries 2 extra bits.** `[DECISION]` Each data whistle carries 6 bits: 4 in its shape (16 types) and 2 in its pitch.

- The key draws a position u from 0 to 1 for each slot. The four candidate pitches are the quantiles (b + u) / 4 of the real centre-frequency pool, for b = 0 to 3, and the two data bits choose b.
- Scrambled data uses the four values equally, so the pitches keep exactly the distribution of the real whistles.
- Neighbouring candidates are at least 1,054 Hz apart (median 1,177 Hz). The detector placed whistle pitch within about +/- 100 Hz at 10 dB (10th to 90th percentile).
- The receiver takes the candidate nearest the track's mid-range, then classifies the shape from that pitch. A track more than 500 Hz from every candidate is not a match.
- The preamble carries no data, so its pitch comes straight from the key.

**3. Compact alphabet for text.** `[DECISION]` Text made only of the 32 characters A-Z, space and `. , ? ! -` uses 5 bits per character instead of 8. Anything else, including lowercase letters, is sent as raw UTF-8 bytes. Letters are never changed to capitals, because the receiver must return the exact text.

**4. One whistle = one code symbol.** `[DECISION]` Reed-Solomon works on 6-bit symbols (GF(64)) instead of bytes, so one lost whistle costs exactly one symbol. This change was added after calculation: packing 6-bit whistles into the byte code would have weakened the protection. For example, a 60-character message at 6 % lost and 3 % wrong whistles would fall from 95 % to about 85 % success.

| Part | Content | Whistles |
|---|---|---|
| Preamble | 3 signature whistles | 3 |
| Header | mode (1 bit), a spare bit, length (8 bits), nonce (8 bits) = 3 symbols, scrambled with the key-only stream, RS(7, 3) over GF(64): fixes 2 wrong or 4 lost whistles | 7 |
| Payload | data bits + CRC-16 in 6-bit symbols, scrambled with the key-and-nonce stream; parity = max(8, ceil(data symbols / 2)) per block | data + parity |

- `[DECISION]` A code block holds at most 63 symbols. Longer messages use equal blocks, and their symbols are interleaved in time so a burst of losses spreads across them.
- `[DECISION]` The length counts characters in compact mode and bytes in raw mode, from 1 to 140. The CRC also covers the mode and the length.
- reedsolo 1.7.0 supports GF(64): 1,000 of 1,000 random codewords were repaired within the 2e + f limit.

Data whistles and time from the first to the last of them. The v2 times are medians measured with the rules above on the bank's two encounters (191 and 214). Cover whistles play in between, so about four whistles are heard for every data whistle.

| Message | v1 today | v2 data whistles | v2 time |
|---|---|---|---|
| "HI" | 39 whistles, 30 s | 23 | 30-37 s |
| "MEET AT DAWN" (12 characters) | 59 whistles, 44 s | 31 | 41-51 s |
| 20 characters | 81 whistles, 61 s | 40 | 53-67 s |
| 60 characters | 201 whistles, 151 s | 90 | 120-158 s |
| 140 characters | 441 whistles, 331 s | 190 | 257-350 s |

Hiding the rhythm therefore costs the speed that the other changes gain: short messages take about as long as in v1, and long messages about the same or slightly less.

Calculated message success at the same per-whistle error rates, with independent losses:

| Lost / wrong whistles | 12 characters (v1 -> v2) | 20 characters | 60 characters | 140 characters | 140 raw bytes |
|---|---|---|---|---|---|
| 6 % / 3 % | 89 % -> 99 % | 88 % -> 99 % | 95 % -> 99 % | 98 % -> 99 % | 98 % -> 99 % |
| 10 % / 3 % | 75 % -> 98 % | 69 % -> 97 % | 74 % -> 97 % | 82 % -> 98 % | 82 % -> 98 % |
| 12 % / 4 % | 55 % -> 94 % | 43 % -> 92 % | 33 % -> 91 % | 24 % -> 92 % | 24 % -> 88 % |

These figures assume that pitch bits, stretched shapes and cover whistles do not raise the whistle error rates. The gate test below measures that.

**Gate test (F1), before any format code is written.** Play real bank stretches with their cover whistles, and put the current 16 shapes into the data slots, stretched to the real lengths and placed at the four candidate pitches, 200 times per shape, in encounter-214 noise at 10, 15 and 20 dB. Read every detected data whistle twice: once with the true pitch given and once choosing among the four candidates. `[DECISION]` The format is adopted only if all of these hold at 10 and 15 dB:

- the wrong pitch is chosen for at most 1 % of detected data whistles;
- the predicted v2 message success for 12, 20 and 60 characters, using the measured rates, is at least that of v1 measured in the same noise;
- the rhythm of the tracks the detector finds scores at most 0.60 against real whistles.

**If the gate fails:**

- **Pitch bits are unreliable:** format v2 drops pitch bits and GF(64) and keeps the byte code with the borrowed rhythm and the compact alphabet. "MEET AT DAWN" then needs 51 data whistles, about 70-85 s.
- **Stretched shapes cannot be read:** data whistles keep their codebook lengths. The rhythm score then rises to about 0.66, which fails the 0.60 pass mark, and the write-up reports that failure.

**Gate result, 2026-11-18: FAILED** on wrong pitch and on message success; rhythm passed. About 3,200 data whistles per SNR, on the epoch-101 codebook (`experiments/f1_gate.py`). The 20 dB column is not part of the gate.

| Measure | 10 dB | 15 dB | 20 dB |
|---|---|---|---|
| Whistles lost / wrong, format v1 | 11.6 % / 4.1 % | 6.3 % / 2.0 % | 6.7 % / 2.6 % |
| Whistles lost / wrong, v2 with the true pitch given | 21.6 % / 10.3 % | 17.9 % / 5.8 % | 17.4 % / 5.5 % |
| Whistles lost / wrong, v2 choosing among four pitches | 21.4 % / 11.1 % | 17.8 % / 6.3 % | 17.3 % / 5.9 % |
| Wrong pitch (limit 1 %) | 2.52 %, fail | 1.41 %, fail | 1.30 % |
| Predicted success, 12 characters, v1 -> v2 | 56 % -> 35 %, fail | 94 % -> 73 %, fail | 90 % -> 77 % |
| Predicted success, 20 characters, v1 -> v2 | 44 % -> 20 %, fail | 94 % -> 63 %, fail | 89 % -> 68 % |
| Predicted success, 60 characters, v1 -> v2 | 35 % -> 4 %, fail | 98 % -> 45 %, fail | 96 % -> 52 % |
| Rhythm score on quiet noise (limit 0.60) | 0.55, pass | 0.56, pass | 0.61 |
| Rhythm score on all noise (for information) | 0.66 | 0.66 | 0.69 |

What the result means:

- **Pitch bits are not the main problem.** Even with the true pitch given, v2 loses almost three times as many whistles as v1 at 15 dB. The losses come from the stretched shapes, the cover whistles, or both; this test cannot separate them.
- **The byte-code fallback is not applied.** With the measured rates it would be worse than the format tested: 34 % predicted success for 12 characters at 15 dB, against 73 %.
- **Not yet tried:** the codebook was chosen for its original lengths, and the erasure threshold was not tuned for stretched shapes.
- F2 was put on hold after this run. The final gate run below settled the design.

**Follow-up test, 2026-11-18: stretching causes the loss, not the cover whistles.** The same 1,600 data whistles per SNR were played four ways, at real bank times, with the four-pitch format (`experiments/f1b_diagnose.py`). The repair budget is lost + 2 x wrong whistles per data whistle, with the true pitch given; lower is better.

| Condition | Repair budget, 10 dB | Predicted success for 12 / 20 / 60 characters, 10 dB | Repair budget, 15 dB | Predicted success for 12 / 20 / 60 characters, 15 dB |
|---|---|---|---|---|
| Format v1 (reference) | 0.198 | 56 % / 44 % / 35 % | 0.103 | 94 % / 94 % / 98 % |
| Shapes at their own length, no cover whistles | 0.181 | 94 % / 92 % / 91 % | 0.120 | 98 % / 98 % / 98 % |
| Shapes at their own length, with cover whistles | 0.214 | 90 % / 86 % / 82 % | 0.153 | 97 % / 96 % / 96 % |
| Stretched shapes, no cover whistles | 0.406 | 38 % / 24 % / 6 % | 0.292 | 73 % / 63 % / 46 % |
| Stretched shapes, with cover whistles | 0.437 | 30 % / 16 % / 2 % | 0.316 | 66 % / 54 % / 33 % |

- **Cover whistles cost little:** they add about 0.03 to the repair budget.
- **Stretching more than doubles the repair budget.** Whistles stretched by almost nothing (0.75 to 1.25 times) still score 0.28 at 15 dB, against 0.12 at their own length. The likely cause is that the current 16 types are told apart partly by their length, and a stretched whistle no longer has that clue. This explanation is not yet tested.
- **Wrong pitch stays over the 1 % limit in every condition** (1.4 % to 2.7 %), even without stretching or cover whistles. Its cost in message success is small, but the limit still stands.

**Final gate run, 2026-11-18: own-length whistles.** The same test and limits as F1, with data whistles at their own lengths (`experiments/f1_gate.py --own-length`). The results are in the "Final idea" section at the top of this plan.

- **Reliability recovered:** at 15 dB, predicted success for 12 characters is 97 %, against 73 % with stretched shapes.
- **The rhythm still passes after the detector:** 0.56 at 10 dB and 0.55 at 15 dB on quiet noise. The earlier figure of about 0.66 was measured before the detector and did not hold.
- **The gate still fails by its rules:** wrong pitch is 2.13 % at 10 dB and 1.53 % at 15 dB (limit 1 %), and a 60-character message at 15 dB is predicted at 96.2 % against 97.0 % for v1.
- **Decision:** stretching is dropped. No further gate tests are run before the pipeline is built, and the two misses stay open as known gaps.

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

P4 builds the receiver for the format phase F settles. With format v2 (section 4.6), the slots and their lengths come from the rhythm bank, cover whistles are ignored, the header has 7 whistles, slot matching and classification choose among the four candidate pitches, and Reed-Solomon works on 6-bit symbols. The steps below are otherwise unchanged.

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
- **Full set:** 200 messages, 150 random-byte payloads of 4-64 bytes and 50 English sentences in capitals, so that format v2's compact alphabet is tested too. Used only for E1 and the frozen final run.

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
| E4 | Format v1 vs v2 x 5 SNRs (0-20 dB): speed vs reliability | 214 | sweep set |
| E5 | Variation tau = 0 / 0.25 / 0.5 / 1 x 5 SNRs: naturalness vs reliability | 214 | sweep set |
| E6 | Classifier A vs B, on the cached E2 tracks | 214, then 276 | (reuses E2) |
| E7 | Covertness (8.5), on the coded whistles detected in E2 | 276 | (reuses E2) |
| E8 | Baseline modem (8.5), 13 SNRs | 214, then 276 | sweep set |
| E9 | Rhythm test (8.5): 44 s windows of detected tracks, coded streams vs real whistles | 276 | (reuses E2) |
| Final | Frozen settings, SNR 10 dB, no multipath | 276 | full set |

All of the table above runs on the final model. Defaults (tau, classifier, erasure thresholds, slot windows) are chosen on encounter 214, written into `config.toml` and frozen. Only then do the encounter-276 runs start.

On the development model only two smoke tests run `[DECISION]`:

- E1;
- the **E2 smoke subset:** SNR 5, 10 and 20 dB, 10 sweep-set messages each, on quiet encounter-214 files.

Together they take under an hour of detector time.

Possible later upgrade, measured before adoption: overlapping whistles.

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

This table is the original estimate, for format v1 at 5-10 s of detector time per minute of audio. Two things have since made it too high: the detector measured about 2.5 s per minute when the dataset was built, and the borrowed rhythm makes format v2 messages in the sweep set about 1.3 times as long as in v1. The revised estimate for the full evaluation is about 5-8 hours of detector time.

### 8.5 Covertness and the baseline

Covertness asks whether the coded whistles can be told apart from real ones. Each measure compares coded whistles, as detected by the receiver in E2, with real whistles from encounter 276. Two real references are used:

- **all** real whistles;
- **in-range** real whistles: those within the codebook's limits (duration 100-450 ms, span 0.3-5 kHz, centre 5-12 kHz).

Against all whistles a classifier can win from the limits alone. The in-range comparison isolates whether the shapes themselves look real.

- **Feature distance:** Wasserstein-1 distance for each of the reproduction's 7 contour features (L, f_min, f_max, df, f_start, f_end, f_c).
- **Likelihood:** mean GMM log-likelihood of the VAE-encoded latents, coded vs real.
- **Discriminator:** a classifier (scikit-learn gradient boosting) trained to tell coded from real on the per-whistle features. 5-fold cross-validated ROC AUC: 0.5 means indistinguishable, 1.0 means obvious.
- **Rhythm (E9):** a classifier trained to tell coded streams from real whistles using 11 timing features of 44 s windows: rate, spacing, irregularity, burstiness, silences, overlap and clumping. It reads the tracks the detector finds, and encounter 276 is the unseen real reference.
- **Not measured:** loudness patterns, and whether a hydrophone array could show that every whistle comes from one place. The write-up states both as limitations.

**Baseline modem:** identical framing, key, nonce, schedule and receiver, but the 16 whistle shapes are replaced by 16 straight-line chirps of 200 ms with evenly spaced slopes from -1.5 to +1.5 kHz `[DECISION]`. The four pitch candidates stay, because 64 constant tones between 5 and 12 kHz would sit only about 110 Hz apart. The baseline should be at least as reliable and clearly artificial. Comparing it with WhistleCode shows the price paid for sounding natural.

### 8.6 Pass marks `[DECISION]`, frozen before the encounter-276 runs

| Test | Pass mark |
|---|---|
| E1 clean | 100 % of the 200 messages exact |
| Final run: encounter 276, SNR 10 dB, no multipath | >= 95 % of messages exact |
| False accepts and no-message false alarms | 0 |
| E7 discriminator AUC against in-range real whistles (chosen tau) | <= 0.75 |
| E9 rhythm detection score against real whistles of encounter 276 | <= 0.60 |

A failed mark is reported as failed, with the measured value; it is never rewritten as a pass.

## 9. Phases

| Phase | Model | Work | Done when |
|---|---|---|---|
| P0 | none | Folder, `config.toml`, key and nonce streams, framing (UTF-8, CRC, scrambler, header), Reed-Solomon, unit tests | Bytes -> symbols -> bytes round trip passes, including with erasures and errors up to the RS limit |
| P1 | development | Codebook: eligibility, filter, confusion pass, selection, verification, gallery, hash pinning | `codebook.npz` + gallery |
| P2 | development | Transmitter: schedule, preamble, header, synthesis, self-check, `send` command | A message becomes a WAV |
| F | development | Format v2 as finalised at the top of this plan: compact alphabet, GF(64) code, frame, rhythm bank, slot schedule, transmitter and tests. The gate runs are done, and the current codebook is kept | Message round trips pass, including damaged whistles up to the code's limit; `send` writes a v2 WAV with the borrowed rhythm |
| P3 | none | Channel: noise at SNR and the `channel` command first; multipath, absorption and Doppler after the pipeline works | A WAV goes through the noise channel at any SNR |
| P4 | development | Receiver: detect with track cache, sync, header, slots, classifier A, Reed-Solomon, CRC, `receive` command; E1 and the E2 smoke subset. Classifier B follows after the pipeline works | **E1 passes: working send -> channel -> receive demo** |
| M | (reproduction) | Training resume to epoch 150 on Colab, then on the laptop re-encode, refit the GMM at K = 3,000, recompute the component features and redo the reproduction's evaluations (section 3.3) | New `final.pt` and `gmm.npz` in place; the reproduction's tables and figures redone |
| S | final | Swap: rebuild the codebook, rerun E1 (section 3.4) | Codebook pinned to the epoch-150 files; E1 passes |
| P5 | final | Sweeps E2-E6, tune on 214, freeze, encounter-276 runs | Reliability curves and tables |
| P6 | final | Covertness E7, baseline E8, no-message test | Covertness table |
| P7 | final | README, figures, results; optional air test; optional "send a message" panel on the project web page | Write-up |

Order:

- P0-P2 are built. F comes next, once the owner decides to build the final idea, because the receiver (P4) is built around the message format.
- P3 and P4 follow F, on the development model. The aim is one complete working pipeline before any further tuning.
- M can run at any time, in parallel, because it touches only the reproduction.
- S needs both P4 and M.
- P5-P7 come after S.
- If training is not resumed, skip M and S.

Effort:

- **P0-P4:** about 1.5 days of work.
- **F:** about one day of work.
- **M:** about 1.75 A100 hours on Colab, then under an hour on the laptop.
- **S:** about 1-1.5 hours, mostly unattended.
- **P5-P7:** about 1.5 days of work, plus about 5-8 hours of unattended detector time (section 8.4).

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
    rhythm.py        the rhythm bank of real whistle times, lengths and contours (format v2)
    schedule.py      slot times and pitches from the key and nonce
    transmitter.py   message -> WAV
    channel.py       multipath, absorption, Doppler, noise, SNR
    classify.py      classifiers A (DTW) and B (VAE encoder + GMM)
    receiver.py      WAV -> message, with the track cache
    baseline.py      straight-line chirp modem
    evaluate.py      experiments E1-E9 and the final run
  experiments/
    f1_gate.py       gate test F1 for format v2
    f1b_diagnose.py  separates stretched shapes from cover whistles
  tests/
  outputs/           gitignored (codebook gallery, WAVs, track cache, results)
```

| Command | Does |
|---|---|
| `build-codebook` | Section 5 |
| `send "TEXT" --key K --out msg.wav [--nonce N] [--tau T] [--manifest] [--force]` | Message -> WAV. `--manifest` adds a .json of the slots, without the key or the text |
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
| Heavy runs done on the development model | The full evaluation's detector time spent twice | Development model limited to smoke tests (section 3.2) |
| Pitch bits raise whistle errors | Format v2 protects messages less than calculated | Gate test F1 before any format code; fallback to the byte code without pitch bits (section 4.6) |
| Cover whistles confuse the receiver or merge with a data whistle | Lost or wrong symbols | No other whistle may start inside a data slot's window; colliding cover whistles move to another pitch; gate test F1 measures the effect |
| Wrong pitch stays above the 1 % limit (1.53 % at 15 dB) | A few more wrong symbols | Known gap from the final gate run; the error correction absorbs it in the predicted success, and it is corrected after the pipeline works |
| A small code (GF(64)) "repairs" to a wrong result more often | A wrong header or block | A wrong header cannot release text, and the CRC-16 over the mode, length and data rejects a wrong payload; false accepts must stay at 0 (section 8.2) |
| Decodes are blurry (epoch-101 Table 1 PSNR 32.8 dB vs the paper's 44.5) | Some components give broken contours | Eligibility and filter (section 5); fallback to real-contour medoids |
| Real whistles land in a slot | Wrong symbols | Key-based time and pitch windows, Reed-Solomon, erasure on ambiguity; measured separately on busy files |
| Preamble or header missed | Whole message lost | 3 signature whistles, 2 of 3 enough; header can lose 4 of 6 bytes; sync and header rates reported on their own |
| Detector finds a start late or splits a whistle at low SNR | Wrong or missing symbol | Shorter fade-in, asymmetric slot window, closest-start then longest-track rule, erasure on ambiguity |
| Detector time | Long evaluation runs | Sweep set of 50 short messages, track cache, unattended overnight runs (section 8.4) |
| Low speed (about 2.5-3 bit/s) | Long airtime | Accepted: format v2 spends its speed gain on hiding the rhythm, so "MEET AT DAWN" still takes about 41-51 s; E4 measures the real figures |
| Doppler drift over long messages | Slots slide out of their windows | Running drift correction from confident matches |
| Preamble and header rhythm repeats per key | 15 whistles with the same timing in every message under one key | Accepted; a new key changes it. Stated as a limitation |
| The rhythm gives the message away | Anyone listening can suspect a signal | Borrowed real rhythm (section 4.6), checked by the rhythm test E9 with a pass mark |
| The same bank stretch is heard twice, or matched against the public recordings | Repeated timing reveals the method | The key and nonce choose among about 7 hours of stretches; the risk remains and is stated as a limitation |
| Other giveaways: whistle shape, loudness, one source location | Covertness weaker than the rhythm score suggests | E7 tests shapes; loudness and source location are stated as limitations (section 8.5) |

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
| Self-check | classifier A on the contour among all 17 types, plus the codebook's duration, span and gap limits; 20 redraws, then tau = 0 | 4.4 |
| Sample rate | 96 kHz, float32 WAV | 4.4 |
| WAV padding and level | 0.5 s before and after; peak -3 dBFS | 4.4 |
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

Format v2 values (section 4.6). They replace the v1 values above once phase F is built:

| Parameter | Default |
|---|---|
| Rhythm bank | encounters 191 and 214, 44 s stretches with at least 10 whistles; pinned by SHA-256 |
| Bank position | key alone for the preamble and header; key and nonce for the payload, joined at a silence of at least 1 s |
| Data slot | real whistle of 100-450 ms; no other start from -60 to +150 ms; at least max(0.35 s, length + 0.1 s) after the previous data whistle |
| Data whistle | real start time, codebook shape at its own length |
| Cover whistles | real contours at real times; moved in pitch if they collide within 1 kHz or follow within 100 ms |
| Bits per data whistle | 6: 4 from the shape, 2 from the pitch |
| Pitch candidates | quantiles (b + u) / 4 of the real pitch pool, b = 0-3, u from the key |
| Slot pitch window | within 500 Hz of a candidate pitch |
| Compact alphabet | 5 bits: A-Z, space and `. , ? ! -` |
| Error-correcting code | Reed-Solomon over GF(64), one whistle per symbol |
| Header | mode, spare bit, length, nonce; RS(7, 3); 7 whistles |
| Payload parity | max(8, ceil(data symbols / 2)) per block |
| Code block | at most 63 symbols; several blocks are interleaved in time |
| Gate test | at 10 and 15 dB: wrong pitch on at most 1 % of detected data whistles, predicted success at least that of v1, and a rhythm score of at most 0.60 |
| Rhythm pass mark (E9) | detection score <= 0.60 against encounter 276 |
| Baseline modem | 16 straight-line chirps of 200 ms, slopes -1.5 to +1.5 kHz, same four pitch candidates |

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
- **2026-11-18, P2 built:**
  - `wcode/schedule.py`, `wcode/transmitter.py` and the `send` command. The self-check also enforces the codebook's duration, span and gap limits.
  - First measurement on the development model: 8 messages of 12 bytes per setting in encounter-214 noise, read at the known slots (no synchronisation yet). At tau = 0.5, 7 of 8 messages decoded at each of 10, 15 and 20 dB. tau = 0.25 looked similar and tau = 1 was worse at 10 dB (4 of 8). The sample is small; E5 sets the final tau.
- **2026-11-18, compact format v2 planned (section 4.6, phase F):**
  - Shorter gaps (0.40-0.60 s, whistles of 100-300 ms), 2 data bits in the pitch, a 5-bit alphabet for capitals, and Reed-Solomon over 6-bit symbols so one whistle is one code symbol.
  - The 6-bit code was added after calculation showed that packing 6-bit whistles into the byte code would weaken the protection.
  - "MEET AT DAWN": 59 whistles and 44 s become a calculated 31 whistles and 16 s. A gate test must confirm the pitch bits before any format code is written.
  - E4 now compares the two formats instead of larger shape alphabets. The baseline modem uses 16 chirps with the same four pitch candidates.
  - The evaluation's detector time is re-estimated at about 2-4 hours.
- **2026-11-18, borrowed real rhythm replaces the fixed gaps:**
  - A rhythm classifier caught every 44 s coded stream with steady gaps (score 1.00), including the planned 0.40-0.60 s gaps, so those gaps are dropped.
  - Format v2 now plays real whistle timing from a bank of encounters 191 and 214. Data whistles keep the real start and length, and colliding cover whistles move in pitch. Under these rules the rhythm scores 0.50.
  - "MEET AT DAWN" now takes about 41-51 s instead of the 16 s first calculated, because fewer real whistles can carry data.
  - Added the rhythm test E9 with a pass mark of 0.60, extended gate test F1, and re-estimated the evaluation at about 5-8 hours of detector time.
- **2026-11-18, gate test F1 run: FAILED (section 4.6):**
  - Wrong pitch was 2.52 % at 10 dB and 1.41 % at 15 dB (limit 1 %), and predicted message success fell below format v1. The rhythm passed on quiet noise (0.55 and 0.56).
  - Most of the loss remains with the true pitch given, so it comes from stretched shapes, cover whistles, or both. F2 is on hold until they are separated.
- **2026-11-18, follow-up test: stretching is the cause:**
  - Cover whistles add about 0.03 to the repair budget; stretched shapes more than double it (0.120 to 0.292 at 15 dB).
  - The next step is to choose the 16 types again for shape differences at equal length, then repeat gate test F1 with unchanged limits.
- **2026-11-18, idea finalised (owner: no further tests, build the complete pipeline first):**
  - Final gate run with own-length whistles: reliable, and the rhythm passes on quiet noise (0.56 and 0.55). The gate still fails on wrong pitch and on one 60-character case; both stay open as known gaps.
  - Stretching is dropped and the current codebook is kept.
  - The "Final idea" section at the top of this plan is now the design. Multipath, Doppler, classifier B and the baseline modem wait until the pipeline works.
