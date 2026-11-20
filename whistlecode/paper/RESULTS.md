# WhistleCode: test results for the paper

Generated 2026-11-20 04:26 by `experiments/paper_analysis.py report` from the campaign in `outputs/paper/` (seed 20261120, started 2026-11-19T20:43:15Z).

Frozen: git ea18d032, config.toml 5576d79bcaa1, codebook cd322a0267ea, rhythm bank 27ca3ddeadd2, VAE checkpoint (epoch 101) fcb1a2e69324, GMM d8087ed21f42. Rates: 95 % Wilson intervals in brackets.

Noise: the sent file never contains any sea background (the sea supplies it). Recordings of encounters 214 (tuning) and 276 (test) stand in for the sea only on the receiving side of these simulations. No message has yet been played through a speaker and recorded. Methods: `TEST_PROTOCOL.md`.

## Verdicts against the pass marks (set in PLAN.md section 8.6 before these runs)

| Test | Pass mark | Measured | Verdict |
|---|---|---|---|
| E1 clean channel | 100 % exact | 100.0 % (98.1-100.0) | PASS |
| Final run, encounter 276, 10 dB | >= 95 % exact | 84.5 % (78.8-88.9) | FAIL |
| False messages (wrong text, wrong key, no message) | 0 | 0 in 7900 tries | PASS |
| E7 whistle-shape discriminator, deployed sender | AUC <= 0.75 | 0.944 (two real encounters: 0.696) | FAIL |
| E9 rhythm: WhistleCode stream on its own | AUC <= 0.60 | 0.440 | PASS |
| E9 rhythm: WhistleCode inside encounter-276 noise, 10 dB | AUC <= 0.60 | 0.684 | FAIL |


## 1. Clean channel (E1) and the frozen final run

| Test | Messages | Exact | Binary payloads | Text payloads | Whistles lost / wrong | Failed at (frame / header / payload) | Wrong text accepted | Wrong-key accepts | Pass mark | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| E1 clean, no channel | 200 | 100.0 % (98.1-100.0) | 150/150 | 50/50 | 0.7 % / 0.2 % | 0 / 0 / 0 | 0 | 0 | 100 % exact | PASS |
| Final: encounter 276, 10 dB | 200 | 84.5 % (78.8-88.9) | 125/150 | 44/50 | 8.1 % / 5.1 % | 4 / 3 / 24 | 0 | 0 | >= 95 % exact | FAIL |

Failed at: frame = none of the receiver's 8 frame candidates lay within 150 ms of the true start; header / payload = the frame was found but that part could not be repaired, or its CRC failed.

**Final run by message size** (number of data whistles, header included; preamble excluded):

| Data whistles | Messages | Exact | Binary / text exact | Whistles lost / wrong | Failed at (frame / header / payload) | Exact with the frame start given |
|---|---|---|---|---|---|---|
| 0-59 | 67 | 97.0 % (89.8-99.2) | 45/46 / 20/21 | 7.8 % / 3.5 % | 0 / 0 / 2 | 65/67 |
| 60-79 | 53 | 77.4 % (64.5-86.5) | 21/30 / 20/23 | 7.9 % / 6.0 % | 2 / 1 / 9 | 44/53 |
| 80-99 | 26 | 69.2 % (50.0-83.5) | 14/20 / 4/6 | 9.3 % / 6.5 % | 1 / 1 / 6 | 17/26 |
| 100-119 | 20 | 85.0 % (64.0-94.8) | 17/20 / 0/0 | 8.1 % / 4.0 % | 0 / 1 / 2 | 17/20 |
| >= 120 | 34 | 82.4 % (66.5-91.7) | 28/34 / 0/0 | 7.8 % / 5.1 % | 1 / 0 / 5 | 29/34 |


## 2. Message success against SNR (E2, E8)

The sweep set: 50 compact-text messages of 8-32 characters, the same messages at every point. SNR is narrowband (per 93.75 Hz bin), measured at the quietest level a data whistle can have; WhistleCode's data whistles sit 0-5 dB above it, the baseline's 2.5 dB above it.

| SNR (dB) | WhistleCode, 214 noise | WhistleCode, 276 noise | Chirp baseline, 276 noise | 276: lost / wrong whistles | Baseline: lost / wrong |
|---|---|---|---|---|---|
| -5 | 0.0 % (0.0-7.1) | 0.0 % (0.0-7.1) | 0.0 % (0.0-7.1) | 81.1 / 18.2 % | 97.4 / 2.6 % |
| -2.5 | 0.0 % (0.0-7.1) | 0.0 % (0.0-7.1) | 0.0 % (0.0-7.1) | 75.8 / 21.3 % | 98.2 / 1.7 % |
| 0 | 2.0 % (0.4-10.5) | 0.0 % (0.0-7.1) | 0.0 % (0.0-7.1) | 71.8 / 16.7 % | 94.8 / 3.9 % |
| 2.5 | 0.0 % (0.0-7.1) | 0.0 % (0.0-7.1) | 0.0 % (0.0-7.1) | 52.4 / 15.7 % | 84.4 / 9.1 % |
| 5 | 16.0 % (8.3-28.5) | 14.0 % (7.0-26.2) | 0.0 % (0.0-7.1) | 29.6 / 14.0 % | 67.2 / 15.5 % |
| 7.5 | 94.0 % (83.8-97.9) | 66.0 % (52.2-77.6) | 0.0 % (0.0-7.1) | 16.4 / 8.0 % | 48.8 / 19.0 % |
| 10 | 100.0 % (92.9-100.0) | 76.0 % (62.6-85.7) | 0.0 % (0.0-7.1) | 8.2 / 6.2 % | 36.6 / 16.0 % |
| 12.5 | 98.0 % (89.5-99.6) | 94.0 % (83.8-97.9) | 10.0 % (4.3-21.4) | 5.7 / 4.1 % | 31.9 / 10.7 % |
| 15 | 98.0 % (89.5-99.6) | 100.0 % (92.9-100.0) | 22.0 % (12.8-35.2) | 4.0 / 3.1 % | 27.9 / 7.7 % |
| 17.5 | 100.0 % (92.9-100.0) | 100.0 % (92.9-100.0) | 56.0 % (42.3-68.8) | 3.4 / 2.8 % | 24.8 / 4.5 % |
| 20 | 100.0 % (92.9-100.0) | 100.0 % (92.9-100.0) | 82.0 % (69.2-90.2) | 2.7 / 2.6 % | 21.4 / 2.4 % |
| 22.5 | 100.0 % (92.9-100.0) | 100.0 % (92.9-100.0) | 78.0 % (64.8-87.2) | 2.9 / 2.5 % | 19.8 / 2.3 % |
| 25 | 100.0 % (92.9-100.0) | 100.0 % (92.9-100.0) | 88.0 % (76.2-94.4) | 2.7 / 2.9 % | 17.8 / 1.4 % |


## 3. The simulated sea (E3), encounter-276 noise

**Echoes and absorption** (image method, four paths, Thorp absorption; no Doppler):

| Range (km) | 5 dB | 10 dB | 20 dB | Lost / wrong whistles (all SNRs) |
|---|---|---|---|---|
| no echoes (snr276) | 14.0 % (7.0-26.2) | 76.0 % (62.6-85.7) | 100.0 % (92.9-100.0) |  |
| 0.2 | 14.0 % (7.0-26.2) | 76.0 % (62.6-85.7) | 76.0 % (62.6-85.7) | 14.9 / 9.6 % |
| 0.5 | 12.0 % (5.6-23.8) | 76.0 % (62.6-85.7) | 86.0 % (73.8-93.0) | 15.4 / 9.8 % |
| 1 | 4.0 % (1.1-13.5) | 54.0 % (40.4-67.0) | 80.0 % (67.0-88.8) | 17.6 / 11.1 % |
| 2 | 14.0 % (7.0-26.2) | 48.0 % (34.8-61.5) | 84.0 % (71.5-91.7) | 18.8 / 11.0 % |

**Doppler alone** at 15 dB (one time-scaling per message; positive = closing, heard early):

| Closing speed (m/s) | Exact | Timing drift over a median message (ms) | Lost / wrong whistles |
|---|---|---|---|
| -3 | 2.0 % (0.4-10.5) | 169 | 38.0 / 36.5 % |
| -2 | 14.0 % (7.0-26.2) | 113 | 27.3 / 30.1 % |
| -1 | 60.0 % (46.2-72.4) | 56 | 14.7 / 14.6 % |
| -0.5 | 88.0 % (76.2-94.4) | 28 | 7.3 / 6.3 % |
| +0 | 100.0 % (92.9-100.0) | 0 | 2.6 / 2.8 % |
| +0.5 | 96.0 % (86.5-98.9) | 28 | 6.6 / 4.7 % |
| +1 | 68.0 % (54.2-79.2) | 56 | 16.5 / 11.0 % |
| +2 | 22.0 % (12.8-35.2) | 113 | 32.5 / 22.6 % |
| +3 | 4.0 % (1.1-13.5) | 169 | 40.1 / 32.0 % |

**Random sea** per message (range 0.2-2 km, water 50-1,000 m, closing speed up to 3 m/s; echoes, absorption and Doppler):

| SNR (dB) | Exact | Lost / wrong whistles | Failed at (frame / header / payload) |
|---|---|---|---|
| 5 | 4.0 % (1.1-13.5) | 39.6 / 23.2 % | 5 / 9 / 34 |
| 10 | 20.0 % (11.2-33.0) | 28.8 / 24.6 % | 3 / 2 / 35 |
| 20 | 40.0 % (27.6-53.8) | 23.4 / 23.4 % | 1 / 0 / 29 |


## 4. Latent variation tau (E5), encounter-214 noise, 10 dB

| tau | Exact | Lost / wrong whistles |
|---|---|---|
| 0.25 | 100.0 % (92.9-100.0) | 3.2 / 1.5 % |
| 0.5 (deployed; snr214 at 10 dB) | 100.0 % (92.9-100.0) | 4.3 / 1.7 % |
| 0.75 | 98.0 % (89.5-99.6) | 4.7 / 2.7 % |
| 1 | 98.0 % (89.5-99.6) | 5.7 / 2.5 % |


## 5. False messages

| Check | Tries | False messages | 95 % upper bound on the rate |
|---|---|---|---|
| Recording with a message, receiver holds the right key: wrong text accepted | 3700 | 0 | 0.08 % |
| Recording with a message, wrong key | 3700 | 0 | 0.08 % |
| No message: 50 min of encounter-276 noise, random keys | 500 | 0 | 0.60 % |


## 6. Throughput and computing cost

| Payload | Messages | Median length | Median data whistles | Median whistles played | Median airtime (s) | Median information rate (bit/s) |
|---|---|---|---|---|---|---|
| Compact text | 50 | 41 characters | 66 | 198 | 142 | 1.22 |
| Binary | 150 | 34 bytes | 82 | 236 | 193 | 1.38 |
| Sweep set (text, 8-32 characters) | 50 | 19.5 characters | 39.5 | 109.5 | 84 | 1.08 |

Computing cost on the laptop (NVIDIA GeForce RTX 5060 Laptop GPU; two campaign workers and the covertness test sharing it), median per message: send 0.63 s, detect 1.60 s, decode 0.08 s; detection runs at 1.3 s per minute of audio (1500 messages, 2732 min of audio).

## 7. Covertness (E7, E9)

In-range whistles only (100-450 ms, centre 5-12 kHz, span 0.3-5 kHz); 1978 real encounter-276 whistles. AUC: 0.50 = indistinguishable, 1.00 = always told apart; mean +/- s.d. over 5 splits by recording. Pass mark (E7): AUC <= 0.75 for the deployed sender.

| Whistles compared with real encounter-276 whistles | Whistles | Discriminator AUC | Main clues | W1 L (ms) | W1 df (Hz) | W1 f_start (Hz) | W1 f_end (Hz) | W1 f_c (Hz) |
|---|---|---|---|---|---|---|---|---|
| Real whistles, encounter 214 (reference) | 686 | 0.696 +/- 0.037 | loudness depth, centre, loudness roughness | 3 | 167 | 232 | 252 | 147 |
| WhistleCode as deployed (tau 0.5) | 1861 | 0.944 +/- 0.013 | curve fit error, net rise, span | 41 | 457 | 1141 | 370 | 714 |
| WhistleCode, tau 0.25 | 1826 | 0.943 +/- 0.007 | curve fit error, duration, net rise | 41 | 454 | 1128 | 366 | 700 |
| WhistleCode, tau 0.75 | 1888 | 0.938 +/- 0.009 | curve fit error, net rise, duration | 41 | 454 | 1138 | 382 | 719 |
| WhistleCode, tau 1.0 | 1900 | 0.932 +/- 0.013 | curve fit error, net rise, duration | 42 | 446 | 1131 | 376 | 711 |
| Without the realism library | 1698 | 0.988 +/- 0.002 | 2nd harmonic, 3rd harmonic, 2nd harmonic change | 50 | 490 | 1139 | 375 | 722 |
| Chirp baseline | 1648 | 0.992 +/- 0.003 | 2nd harmonic, 3rd harmonic, slope changes | 80 | 310 | 981 | 418 | 683 |

| 44 s windows | Coded windows (test) | Real windows (train 214 / test 276) | Rhythm AUC | Pass mark (E9) |
|---|---|---|---|---|
| WhistleCode stream on its own | 760 | 126 / 158 | 0.440 | PASS (<= 0.60) |
| WhistleCode inside encounter-276 noise, 10 dB | 769 | 126 / 158 | 0.684 | FAIL (<= 0.60) |
| Control: format v1's steady 0.55-0.95 s gaps | 200 | 126 / 158 | 1.000 | - |


## 8. Receiver ablations (saved tracks of E2, no detector re-run)

Each variant decodes the same saved detector tracks with the key only. Ratio = distance to the best shape / distance to the second best; above it a whistle is erased before repair. Soft repair retries a failed block with the most doubtful whistles marked lost, one more at a time, leaving 2 parity symbols unused.

| Receiver | Noise | 5 dB | 7.5 dB | 10 dB | 15 dB | 20 dB | All 13 SNRs | Wrong text |
|---|---|---|---|---|---|---|---|---|
| Receiver as deployed (ratio 0.85, soft repair) | 214 | 8/50 | 47/50 | 50/50 | 49/50 | 50/50 | 404/650 | 0 |
| Receiver as deployed (ratio 0.85, soft repair) | 276 | 7/50 | 33/50 | 38/50 | 50/50 | 50/50 | 375/650 | 0 |
| No soft repair (no retries that mark the most doubtful whistles as lost) | 214 | 6/50 | 43/50 | 50/50 | 49/50 | 49/50 | 397/650 | 0 |
| No soft repair (no retries that mark the most doubtful whistles as lost) | 276 | 4/50 | 30/50 | 37/50 | 47/50 | 49/50 | 361/650 | 0 |
| Stricter doubt rule (ratio 0.75) | 214 | 7/50 | 44/50 | 49/50 | 49/50 | 50/50 | 399/650 | 0 |
| Stricter doubt rule (ratio 0.75) | 276 | 3/50 | 26/50 | 37/50 | 50/50 | 50/50 | 363/650 | 0 |
| Looser doubt rule (ratio 0.95) | 214 | 15/50 | 47/50 | 49/50 | 49/50 | 50/50 | 410/650 | 0 |
| Looser doubt rule (ratio 0.95) | 276 | 11/50 | 33/50 | 39/50 | 50/50 | 50/50 | 380/650 | 0 |
| No up-front doubt rule (ratio 1.0; soft repair still erases the most doubtful in turn) | 214 | 15/50 | 47/50 | 49/50 | 49/50 | 50/50 | 410/650 | 0 |
| No up-front doubt rule (ratio 1.0; soft repair still erases the most doubtful in turn) | 276 | 11/50 | 33/50 | 39/50 | 50/50 | 50/50 | 380/650 | 0 |
| Errors only: every whistle given a symbol, no erasures, no soft repair | 214 | 4/50 | 40/50 | 48/50 | 48/50 | 49/50 | 387/650 | 0 |
| Errors only: every whistle given a symbol, no erasures, no soft repair | 276 | 2/50 | 23/50 | 33/50 | 46/50 | 48/50 | 342/650 | 0 |
| Frame start given (oracle sync) | 214 | 12/50 | 48/50 | 50/50 | 49/50 | 50/50 | 409/650 | 0 |
| Frame start given (oracle sync) | 276 | 8/50 | 34/50 | 38/50 | 50/50 | 50/50 | 377/650 | 0 |

