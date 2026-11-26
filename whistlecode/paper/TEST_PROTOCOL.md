# WhistleCode test protocol (for the paper's Methods section)

This is how the results in `RESULTS.md` were produced. The plan behind it is `../PLAN.md`, section 8. Scripts:
`experiments/paper_eval.py` (reliability), `experiments/paper_covert.py` (covertness) and `experiments/paper_analysis.py`
(ablations, tables, figures).

## 1. System under test

The system tested is exactly the one deployed on the project web page, with nothing re-tuned for the tests.

| Part | As tested |
|---|---|
| Model | VAE-GMM V1 (L = 64, beta = 1e-4, critic), epoch 101, trained on encounter 191; GMM K = 3,000 fitted on its latents. Epoch 101 is the final model: the resume to epoch 150 was not completed (PLAN.md section 3.2). *(Corrected 2026-11-26, WC-R7: the resume did complete epoch 150 on 2026-11-20, as a second model (Delphi, D-007). Epoch 101 stays the final model, and every test here used it; WhistleCode has not been tested on epoch 150.)* |
| Alphabet | 16 GMM components chosen for low mutual confusion (each holds at least 32 training whistles), plus 1 signature component for the start signal. Mean decodes last 101-416 ms. |
| Symbol | 6 bits per data whistle: 4 bits choose the shape, 2 bits choose one of four key-dependent pitches (quantiles of the real centre-frequency pool, at least 1,054 Hz apart). |
| Frame | 3 signature whistles; a 7-whistle header (mode, length, nonce) protected by RS(7, 3) over GF(64); payload of compact 5-bit text or raw bytes, plus CRC-16/CCITT-FALSE, scrambled with the key and nonce, protected by Reed-Solomon over GF(64) with max(8, ceil(k / 2)) parity symbols per block of at most 63 symbols. |
| Timing | Borrowed real rhythm: a message is laid over a stretch of a bank of 73,791 real whistles from encounters 191 and 214 (19,432 can carry data). Every bank whistle is played at its real time; about one in four can carry data, the rest are cover whistles re-synthesised from their real contours. The sender uses every eligible whistle its spacing rules allow, so in a played message about a third carry data, header included: the median compact-text message played 66 data whistles among 198 (RESULTS.md section 6). *(Corrected 2026-11-26, WC-R7: this row said "about one in four carries data", which is the bank's share, not a message's.)* |
| Sound | Each whistle takes the loudness pattern and 2nd and 3rd harmonics of one of 3,383 clean recorded whistles, belongs to one of 6 virtual animals, and recorded clicks (53,729 available) are played at their recorded times. Latent variation tau = 0.5 around each component mean, with a self-check that the shape still reads as its type. The file is silent between sounds: the sea supplies the background. |
| Receiver | The reproduction's detector (ridgenet-v2c) and tracker; frame search by voting on the key's known whistle times and pitches; each slot read by comparing each of the 16 shapes with the part of the track where that shape would sound (banded DTW plus a length term); doubtful whistles erased (distance ratio > 0.85); Reed-Solomon errors-and-erasures decoding with a soft retry; CRC check before any text is released. The receiver knows only the key. |

## 2. Data

- **Noise:** channel 0 of the raw 500 kHz recordings, resampled to 96 kHz and high-passed at 2 kHz. **Encounter 214** (124 one-minute files) is the tuning noise; **encounter 276** (120 files) is the test noise. Encounter 191 is never used as noise because the VAE was trained on it. The recordings contain real false killer whale whistles and clicks, so real animals interfere with the message.
- **Real whistle references (covertness):** whistles detected by the same detector in encounter-276 recordings (no part of the sender uses encounter 276) and, as the reference two real encounters score, encounter 214.
- **History of encounter 276:** it was used twice before this campaign, for checks only (the 2026-11-19 sea test and normal-conditions check). No setting was tuned on it.

## 3. Test messages

Generated from seed 20261120, which was never used during development. Every message has its own random key and nonce.

| Set | Contents | Used by |
|---|---|---|
| Sweep set | 50 sentences in capitals of 8-32 characters (compact 5-bit text) | SNR sweeps, baseline, sea, tau |
| Full set | 150 random binary payloads of 4-64 bytes (raw mode) and 50 sentences in capitals of 10-60 characters | E1 (clean) and the final run |

The same sweep-set messages are sent at every test point, so differences between points come from the condition, not the messages.

## 4. Channel

- **SNR:** narrowband, per 93.75 Hz bin: the level of a data whistle in its own bin above the median noise level in that bin, at the median pitch of the pool. The whole message is played with one gain, as a real source would be. SNR refers to the quietest level a data whistle can have; WhistleCode's data whistles sit 0-5 dB above it (the virtual animals' loudness range), the baseline's 2.5 dB above it, the same median.
- **Sea model (E3):** image method with four paths (direct, surface -0.9, bottom 0.4, surface-bottom), each falling as 1 / length and losing Thorp absorption over its own length; Doppler as one time-scaling of the whole recording by 1 + v / c (c = 1,500 m/s). Random sea per message: range 0.2 / 0.5 / 1 / 2 km, water depth 50-1,000 m (log-uniform), source depth 5-30 m, receiver depth 5-50 m, closing speed -3 to +3 m/s. Each message keeps its own sea in every condition. Noise is added last.
- **Clean condition (E1):** the sent file goes straight to the receiver, which adds faint white noise 40 dB below the loud whistles because the detector misses whistles in digital silence.

## 5. Experiments

| Id | Condition | Messages | Trials |
|---|---|---|---|
| E1 `clean` | no channel | full set | 200 |
| Final `final` | encounter 276, 10 dB | full set | 200 |
| E2 `snr214`, `snr276` | -5 to 25 dB in 2.5 dB steps, encounter 214 and 276 | sweep set | 2 x 650 |
| E8 `baseline` | chirp modem, -5 to 25 dB, encounter 276 | sweep set | 650 |
| E3 `range` | echoes and absorption at 0.2, 0.5, 1, 2 km, at 5, 10, 20 dB, no Doppler | sweep set | 600 |
| E3 `doppler` | Doppler alone, -3 to +3 m/s (9 speeds), 15 dB | sweep set | 450 |
| E3 `sea` | random sea, 5, 10, 20 dB | sweep set | 150 |
| E5 `tau` | tau = 0.25, 0.75, 1.0 at 10 dB, encounter 214 (0.5 = E2) | sweep set | 150 |
| `empty` | 50 one-minute stretches of encounter-276 noise without a message, 10 random keys each | - | 500 tries |
| E7 | covertness of whistle shapes (section 7) | 24 messages of 60 characters per sender | 7 senders |
| E9 | covertness of rhythm (section 7) | saved tracks of E1, E2 and the final run | - |
| Ablations | receiver variations on the saved E2 tracks | sweep set | 6 x 1,300 |

**Baseline modem (E8):** the same frame, key, rhythm bank, cover whistles, pitches and receiver, with the 16 whale shapes replaced by 16 straight-line chirps of 200 ms whose sweeps are spaced evenly from -1.5 to +1.5 kHz, and a 300 ms up-down chirp as the signature. No recorded voices and no latent variation. It shows what sounding like a whale costs and buys.

## 6. Reliability measures

Per trial, from the receiver given only the key:

- **Exact:** the CRC passed and the payload equals the sent one, byte for byte. This is the message success rate.
- **Wrong text accepted:** the CRC passed but the payload differs. Must be 0.
- **Where a failed message failed:** frame (none of the receiver's 8 frame candidates lies within 150 ms of the true start),
  else header or payload (the frame was found but that part could not be repaired, or its CRC failed).
- **Oracle sync:** the frame read at the true start, which separates synchronisation failures from whistle errors.
- **Whistles lost / wrong:** every data whistle read at the true start; lost = no track found (missed) or erased as doubtful; wrong = a symbol that is not the sent one (split into shape and pitch).
- **Wrong key:** every recording is also read with a wrong key. Any message reported is a false message.
- **Throughput:** information bits (5 per compact character, 8 per byte) per second of the sent file, including its 0.5 s lead-in and tail.
- **Cost:** wall-clock time of sending, detection and decoding on the laptop (RTX 5060 Laptop GPU).

## 7. Covertness measures

- **Whistle shapes (E7):** gradient boosting (scikit-learn HistGradientBoosting, depth 4, 200 iterations) trained to tell coded data whistles from real encounter-276 whistles on 14 features (duration, span, centre, mean slope, slope changes, contour roughness, net rise, curve-fit error, three loudness features, 2nd and 3rd harmonic levels, 2nd-harmonic change). Coded whistles are sent through encounter-214 noise at 15 and 20 dB and picked up by the same detector. Both sides are restricted to 100-450 ms, centre 5-12 kHz and span 0.3-5 kHz, balanced within signal-to-noise bands, and split by recording or message (5 splits). Score: ROC AUC (0.5 = indistinguishable). Also the Wasserstein-1 distance of the reproduction's 7 contour features (L, f_min, f_max, df, f_start, f_end, f_c).
- **Rhythm (E9):** 44 s windows of detected tracks, 11 timing features (rate, median gap, gap variation, burstiness, local variation, gap percentiles, longest silence, busy fraction, overlap, clumping). Trained on real encounter-214 windows against coded windows of half the messages, tested on real encounter-276 windows against coded windows of the other half, then swapped. A positive control replays format v1's steady 0.55-0.95 s gaps.

## 8. Statistics and pass marks

Rates carry 95 % Wilson score intervals. A count of zero out of n carries the one-sided 95 % upper bound 1 - 0.05^(1/n).

Pass marks were set in PLAN.md section 8.6 before any of these runs and are reported as measured, never moved:

| Test | Pass mark |
|---|---|
| E1 clean | 100 % of the 200 messages exact |
| Final run (encounter 276, 10 dB) | >= 95 % exact |
| Wrong text accepted, false messages | 0 |
| E7 discriminator AUC, deployed sender | <= 0.75 |
| E9 rhythm AUC against encounter 276 | <= 0.60 |

## 9. What these tests do not cover

- A real acoustic channel: no message has yet been played through a speaker and recorded (in air or water).
- Human listeners: whether people can pick out the coded whistles is not scored.
- A hydrophone array that could show all whistles come from one place, and loudness patterns across a group.
- The sea model leaves out a moving surface, different Doppler per path and sound-speed layers.
- The receiver has no Doppler drift correction, so the Doppler results measure that gap.
- Playing synthetic whistles near wild animals would need permits; everything here is simulation.
