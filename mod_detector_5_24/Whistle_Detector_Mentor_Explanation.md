# Whistle Detector: Explained from the Beginning

Prepared for mentor review. First written 5 November 2026; **status updated 12 November 2026** (sections 1, 8, 10, 11,
12, 14 and 15: results reproduced, statistics, false-alarm analysis, no-whistle test results, preprint plan).

## Contents
1. [Summary](#1-summary)
2. [The problem](#2-the-problem)
3. [What the detector does](#3-what-the-detector-does)
4. [Technologies used and where they come from](#4-technologies-used-and-where-they-come-from)
5. [The two detector configurations](#5-the-two-detector-configurations)
6. [Training data](#6-training-data)
7. [How training works](#7-how-training-works)
8. [Testing data](#8-testing-data)
9. [How testing works](#9-how-testing-works)
10. [Machines used](#10-machines-used)
11. [Results](#11-results)
12. [Limitations](#12-limitations)
13. [Justification of our choices](#13-justification-of-our-choices)
14. [Next steps](#14-next-steps)
15. [Possible mentor questions and answers](#15-possible-mentor-questions-and-answers)
16. [References](#16-references)

---

## 1. Summary
- **The need:** we are reproducing a published paper on dolphin and whale whistles (Park et al., VAE-GMM). It relies on a whistle detector that was not available to us, so we built our own.
- **The detector:** a very small neural network (14,209 parameters) followed by a tracker. It was trained only on synthetic whistles mixed into real ocean noise, with no human labels.
- **Two configurations:** the **2–24 kHz detector** built the dataset for the VAE-GMM reproduction. The **5–24 kHz detector** is the same method, retrained so it could be tested on a public benchmark.
- **Real-data result (5–24 kHz detector):**

| 12 expert-labelled recordings, 5–24 kHz | Precision | Recall | F1 |
|---|---|---|---|
| Silbido (the standard older method) | **76.4** | 72.9 | **74.6** |
| Our 5–24 kHz detector | 56.3 | **86.9** | 67.1 |

- **What this means:** our detector finds more whistles, but raises more false alarms, so Silbido scores higher overall.
- **How sure we are (new):** with only 12 recordings, the F1 gap of 7.5 points is **not statistically significant**
  (95 % range −18.0 to +5.9, p = 0.18). Our **higher recall is significant** (+14.0, p = 0.014), and so is Silbido's
  **higher precision** (+20.2, p = 0.042).
- **What the false alarms are (new):** in a blind check of 147 sampled false alarms, about **a quarter of ours look like
  real whistles the experts didn't mark**, and a fifth are pieces or copies of marked whistles. Silbido's are mostly
  noise and clicks.
- **Reproducible (new):** all committed scores were reproduced exactly on a fresh Colab machine.
- **Decision (new):** the preprint (version 1) goes out with these results as they stand; improving precision is version 2.
- **Biggest gap:** the **2–24 kHz detector has never been scored on labelled real recordings**, so its real-world accuracy is unknown.

---

## 2. The problem
Dolphins and whales make whistles, and researchers record them underwater with hydrophones (underwater microphones). Recordings are far too long to go through by hand, so software has to find the whistles.

The paper we are reproducing (Park et al.) needs whistles cut out of recordings before it can train its VAE-GMM generative model. Its detector and tracker were not available to us, so we needed a replacement.

**A spectrogram** is a picture of sound, with time across and pitch going up. A whistle looks like a thin bright curved line. The detector's job is to find those lines and report each whistle as a list of times and pitches.

**Terms used in this document:**

| Term | Meaning |
|---|---|
| **Precision** | Of everything the detector reported, how much was real |
| **Recall** | Of the real whistles, how many it found |
| **F1** | One score combining precision and recall |
| **SNR** | Signal-to-noise ratio: how far a sound stands above the background, in dB |
| **Harmonic** | A fainter copy of a whistle at a multiple of its pitch |
| **Answer key** | Whistles marked by human experts, used to score a detector |

---

## 3. What the detector does
```text
Recording
   |  1. Pick one hydrophone channel (where a recording has several)
   |  2. Resample the audio to 192 kHz
   |  3. Remove sound below 2 kHz
   |  4. Make a spectrogram (93.75 Hz by 5.33 ms per cell)
   v
RidgeNet (our small neural network)
   |  Gives every point in the band a confidence from 0 to 1: "is this part of a whistle?"
   v
Tracker
   |  Finds peaks, links them over time into lines, and rejects poor tracks
   v
List of whistles (times and pitches)
```

**RidgeNet** is our own design. Its name comes from the thin "ridge" a whistle makes on a spectrogram. A convolutional network slides small filters over the picture, so it learns from local shapes. It has a stem, 6 convolution blocks and an output layer, with 14,209 learned values. It doesn't shrink the picture, so each output lines up with one spectrogram point. Each output sees about 208 ms by 1.8 kHz around it: long enough to follow a thin line, and narrow enough to tell it from a brief click.

**The tracker** is rule-based, with no learning:
1. In each time slice, it keeps confidence peaks above a threshold.
2. It predicts where each whistle goes next, and assigns peaks to whistles.
3. It can bridge gaps up to about 64 ms, which also helps at crossings.
4. It rejects tracks that are too short, mostly interpolated, low-confidence, too steep, duplicates or pulse-train patterns. It can also remove harmonics.

---

## 4. Technologies used and where they come from

| Technology | What it does here | Origin |
|---|---|---|
| **Spectrogram (short-time Fourier transform)** | Turns audio into a picture of pitch over time | Standard signal processing |
| **Hamming window** | Reduces artefacts when cutting audio into short slices | Named after Richard Hamming |
| **Butterworth filter** | Removes sound below 2 kHz | Stephen Butterworth, 1930 |
| **Convolutional neural network** | Learns the shape of whistles | LeCun and colleagues, 1989 onward |
| **Dilated convolution** | Lets the network see far with few parameters | Yu & Koltun, 2016 |
| **Residual connection** | Makes the network easier to train | He et al., 2016 |
| **Batch normalisation** | Keeps training stable | Ioffe & Szegedy, 2015 |
| **Binary cross-entropy and Dice loss** | Measure how wrong the network is; Dice helps because whistles cover few pixels | Standard loss; Dice's measure is from 1945 |
| **AdamW and one-cycle learning rate** | Update the network and control its learning speed | Loshchilov & Hutter, 2019; Smith, 2018 |
| **Hungarian algorithm** | Optimally assigns peaks to whistles in the tracker | Kuhn, 1955 |
| **PyTorch** | Software used to build and train the network | Open-source library, started at Meta (then Facebook) |
| **Training on synthetic whistles** | Avoids needing human labels | Idea inspired by Li et al., 2020; no numbers copied |
| **Silbido** | The baseline detector we compare against | Roch et al., 2011 (MATLAB and Java) |
| **MATLAB** | Needed only to run Silbido | MathWorks |

**RidgeNet, the tracker, the training generator and our scoring code were written for this project.** Our scorer follows Silbido's published scoring code and Li et al.'s stated rules.

---

## 5. The two detector configurations
Both use the same network design, training method and tracker code. They differ in the pitch band they analyse and the data they trained with.

| | **2–24 kHz detector** | **5–24 kHz detector** |
|---|---|---|
| **Purpose** | Build the whistle dataset for the VAE-GMM reproduction | Be tested on the DCLDE 2011 benchmark |
| **Synthetic whistle range** | 2.3–23.7 kHz | 5.3–23.7 kHz |
| **Confidence threshold** | 0.5 | 0.4 |
| **Harmonics** | Removed | Kept for the benchmark |
| **Used on** | Real 2017 false killer whale recordings | Real DCLDE 2011 recordings |
| **Real-data accuracy known?** | **No** | Yes, on other species |

### Why these two bands?
**Why 2 kHz:** Park et al.'s method filters out sound below 2 kHz, so the detector starts there.

**Why 24 kHz:** this was **our decision**. The paper gives no upper limit for the detector, so we chose 24 kHz to cover the range shown in its Figure 3. The audio itself reaches 96 kHz, so this isn't a limit of the data.

**Why a second version from 5 kHz:** the DCLDE 2011 experts only marked whistles from 5 to 50 kHz. A detector working down to 2 kHz could find real whistles below 5 kHz, and they would wrongly count as false alarms.

**Why not 5–50 kHz:** we kept the change as small as possible, so the 5–24 kHz detector stays the same method as the 2–24 kHz one. The cost is that it can't detect anything above 24 kHz. A 5–50 kHz version is a possible next step.

**The numbers don't transfer.** The real-data scores below belong to the 5–24 kHz detector. They are supporting evidence for the method, not the accuracy of the 2–24 kHz detector.

---

## 6. Training data

### Why synthetic whistles?
No whistle-by-whistle labels exist for our recordings, so we generate training data where the correct answer is known exactly.

### Where the background noise comes from
Both detectors use real ocean noise from the same source.

- **Dataset:** DCLDE 2022, from NOAA's 2017 Hawaiian Islands survey (HICEAS), recorded aboard the R/V Reuben Lasker. It is freely available from NOAA's public cloud storage.
- **Format:** towed hydrophone array, 6 channels, 500 kHz, in 60-second files.
- **Source files:** 56 files from false killer whale encounter 191, split into **24 training, 16 validation and 16 test** files. The splits share no files, and none of these files are used in our dataset validation sets.
- **Window selection:** the code cuts 3-second candidate windows and keeps the ones with the least whistle-like content, using a classical rule. It uses no detector and no human labels.

| Windows kept (5–24 kHz detector) | Train | Validation | Test |
|---|---|---|---|
| Kept | 180 | 44 | 116 |
| Maximum possible | 480 | 192 | 192 |

Encounter 191 is rich in whistles, so clean windows are scarce. The 2–24 kHz detector used the same files, but its windows were selected in its own band, so its window sets differ.

### What is added to the noise
Everything is generated by our code, with these settings:

| Element | Settings |
|---|---|
| **Number of whistles** | 0–5 per window |
| **Length** | 0.1–1.0 s |
| **Loudness (SNR)** | −2 to 24 dB |
| **Pitch range** | Inside each detector's band |
| **Shapes** | Flat, rising, falling, arched, valley and wavy; some with ripple |
| **Arrangements** | Random (60%), crossing (20%), parallel (20%) |
| **Harmonics** | Added to many whistles |
| **Distractors** | Synthetic click trains and sweeps, like dolphin clicks or echosounders |

### Avoiding a known training problem
Selected noise can still contain faint real whistles. If the network is taught that these are "not whistle", it learns the wrong lesson. So a classical rule marks probable real whistles in the training noise, and **those points are ignored during training** (about 2% of points).

---

## 7. How training works
1. Take a real noise window and add synthetic whistles and clicks.
2. Turn it into a spectrogram, using the same code as on real recordings.
3. Express each point as its height above the local noise level.
4. Build the correct-answer map from the known whistle shapes.
5. Show the network a 1.37-second patch, measure its error, and adjust its parameters.

| Setting | Value |
|---|---|
| Training steps | 6,000 |
| Batch size | 16 (96,000 samples in total) |
| Optimiser | AdamW, learning rate 0.003 with one-cycle schedule |
| Loss | Weighted binary cross-entropy plus Dice |
| Saved model | The step with the best synthetic validation score |

| | 2–24 kHz detector | 5–24 kHz detector |
|---|---|---|
| **Machine** | RTX 5060 laptop GPU | Google Colab, free Tesla T4 GPU |
| **Training time** | About 65 min | About 1 h 41 min |
| **Best synthetic validation score (node F1)** | 0.695 at step 1,500 | 0.559 at step 2,000 |

The two validation scores come from different validation sets, so they can't be compared. The confidence threshold was then chosen on synthetic validation data only, never on real test data.

---

## 8. Testing data

### Test 1: synthetic data
Generated the same way as training data, on the separate 16 test noise files. The correct answers are known exactly. This measures recall, not real-world accuracy.

### Test 2: real recordings (5–24 kHz detector only)
- **Dataset:** DCLDE 2011 (Roch et al.), a public benchmark from NOAA's public cloud storage. It contains recordings with whistles marked by human analysts.
- **Which recordings:** the test set used by Li et al. (2023), the closest published work.
- **Size:** 12 recordings, 43.2 minutes, 6,011 marked whistles.
- **Species (3 recordings each):** bottlenose dolphin, long-beaked common dolphin, melon-headed whale and spinner dolphin.
- **Format:** mono, 192 kHz.
- **How it was obtained:** a Colab script downloaded each file into Google Drive and verified its size and checksum.

**Our detector never saw any of this data during training.** It involves different species, locations and recording equipment from its training noise.

### Baseline: Silbido
- Silbido is the standard rule-based whistle detector. It finds points about 10 dB above the noise, connects them with a graph search, and keeps whistles of at least 150 ms. It needs no training.
- A colleague ran the original Silbido 3.0, classic graph search with default settings, on the same 12 recordings.

### Test 3: recordings with no whistles (done for our detectors, 11–12 Nov)
- **Idea:** run the detectors on recordings of species that click but don't whistle. Every detection is then a false
  alarm, so we can measure **false alarms per minute** without needing an answer key.
- **Recordings:** 2017 survey (the DCLDE 2022 data), chosen before running anything: 21 single-species encounters with
  no dolphins or other whistling species logged within 15 minutes. That's 13 beaked whale encounters (Cuvier's and
  Blainville's, 60 min) and 8 sperm whale encounters (250 min). List: `mod_detector_5_24/nowhistle_encounters.csv`.
- **Files used:** every 1-minute file overlapping a beaked whale encounter (72 files), and 10 files spread evenly
  through each sperm whale encounter (74 files): **146 minutes** in all, fixed in advance with their checksums
  (`mod_detector_5_24/nowhistle_files.csv`). Ten minutes per sperm whale encounter is enough because results differ
  mainly between encounters, and all 8 encounters are still used.
- **How:** both of our detectors ran on Colab (benchmark settings for the 5–24 kHz one, dataset settings for the
  2–24 kHz one; code commit `25214ab`), counted per minute; Silbido later, when the colleague with MATLAB is available,
  on the same files (run 13 Nov, see below). Ten detections per detector per group were checked by eye, blind, since distant dolphins could
  occasionally be audible. Results: `results/nowhistle/` (`summary.md`, `counts.md`).
- **Result, benchmark rule (5–24 kHz, at least 150 ms), 95 % range over encounters:**

  | Detector | Beaked whales (71.5 min) | Sperm whales (74.0 min) | Both |
  |---|---|---|---|
  | 5–24 kHz (paper) | 1.02 per min (0.47–1.73) | 0.78 per min (0.34–1.23) | 0.90 per min (131 in 145.5 min) |
  | 2–24 kHz | 0.81 per min (0.48–1.22) | 0.59 per min (0.29–0.89) | 0.70 per min (102) |

  Counting every track the detector outputs, the rates are 4.98 and 3.96 per minute (5–24 kHz) and 8.86 and 6.39
  (2–24 kHz): most raw tracks are short or below 5 kHz, and the benchmark rule removes them (80 % and 91 %).
- **Compared with DCLDE 2011**, under the same rule: our detector made 35.6 false alarms per minute there (1,538 in
  43.2 min; Silbido 10.3), about 40 times more than here. So most of its false alarms happen when dolphins are
  whistling (pieces, harmonics and unannotated whistles, as in 11.7), not on clicks or empty ocean.
- **What the false alarms are** (40 pictures, sorted blind): 5–24 kHz: 10 other noise, 8 clicks, 2 possible whistles
  (both beaked whale files, both marked unsure); 2–24 kHz: 16 other noise, 3 clicks, 1 tonal noise. So almost none are
  hidden whistles, and the rates above are real false alarms. The same click event, picked once for each detector,
  was given the same letter both times.
- **Silbido on the same files** (Silbido 3.0, default settings, the same audio: channel 0 at 192 kHz; run 13 Nov
  2026; `results/nowhistle/silbido_summary.md`): **4.90 false alarms per minute** under the benchmark rule (beaked
  5.21, sperm 4.59), against 0.90 for ours. Paired difference, ours minus Silbido: −4.00 per minute (95 % range
  −5.63 to −2.50), so ours makes clearly fewer false alarms when no whistles are present. Silbido at 12 dB (less
  sensitive) makes 0.78 per minute, about as few as ours; at 8 dB, 30.4. The same Silbido run repeated the 5 Nov DCLDE
  2011 result exactly (F1 74.6). Silbido's no-whistle detections, checked by eye the same way
  (20 pictures, blind, mixed with 10 earlier pictures of ours shown again; `results/silbido_pictures/counts.md`):
  15 other noise, 5 clicks (all in sperm whale files), no whistles, so its rate is also made of real false alarms.
  The 10 repeated pictures got the same category 7 times out of 10 (the 3 changes were all "clicks" becoming "other
  noise") and the same whistle-or-not answer 10 times out of 10: the line between clicks and noise is soft, the
  whistle judgement is stable.
- **Silbido's threshold** (fixed in advance at 8 and 12 dB besides the default 10; main scoring;
  `results/silbido_thresholds/silbido_thresholds.md`):

  | Silbido threshold | DCLDE P / R / F1 | No-whistle false alarms per minute |
  |---|---|---|
  | 8 dB | 59.5 / 80.5 / 67.4 | 30.4 |
  | 10 dB (default) | 76.4 / 72.9 / 74.6 | 4.9 |
  | 12 dB | 79.3 / 57.0 / 66.1 | 0.8 |
  | ours, for comparison | 56.3 / 86.9 / 67.1 | 0.9 |

  No Silbido setting has both our recall and our quietness on no-whistle recordings: made as quiet as ours (12 dB),
  it finds 57 % of the whistles instead of 87 %. Silbido's default is its best F1 on DCLDE.
- **Bursty:** false alarms cluster in a few minutes and encounters (the busiest 10 files hold a third of the 5–24 kHz
  tracks; some encounters average 0.2 tracks per file, others 17), hence the wide ranges.
- **Caveat:** same survey and equipment as our training noise (different encounters), so not a fully independent test.

### What was not tested
The 2–24 kHz detector has no labelled real-data test. Our search found no public whistle-level labels for the 2017 recordings; the dataset only labels encounter times and species.

---

## 9. How testing works
Our Python scorer follows Silbido's scoring code and Li et al.'s rules. It was checked first: the answer key scored against itself gets about 100, and copies with the pitch shifted or the length cut are rejected as expected.

**A marked whistle counts only if:**
- it lasts at least 150 ms;
- it is above 10 dB over at least a third of its length;
- it lies entirely inside 5–24 kHz (our band limit).

This leaves **1,516 of the 6,011 whistles**.

**A detection matches a whistle if:**
- its average pitch difference is at most 350 Hz;
- it covers more than 30% of the whistle (optional; see below).

**Other rules:**
- Detections that match only uncounted whistles count neither for nor against.
- Results are calculated per species, then averaged.
- Detections mostly outside 5–24 kHz are dropped, so Silbido isn't penalised for searching higher.

### Settings used for our detector on this test
- **Harmonics kept**, because the DCLDE experts mark them as whistles.
- **150 ms minimum detection length**, because that's Silbido's default. Without it, our tracker keeps tracks from about 64 ms.

### The 30% rule
Li et al.'s paper says a detection must cover more than 30% of the marked whistle. Silbido's scoring code has no such rule, and our results match their published Silbido scores much better without it. So we report both, and recommend "no 30% rule" as the main score.

---

## 10. Machines used

| Task | Machine | Software |
|---|---|---|
| Train 2–24 kHz detector | NVIDIA RTX 5060 laptop GPU, Windows | Python 3.11, PyTorch 2.14 |
| Build VAE-GMM whistle dataset (1,415 files, about 72 min) | Same laptop GPU | Same |
| Train 5–24 kHz detector | Google Colab free tier, Tesla T4 GPU, Linux | Python 3.13, PyTorch 2.11 |
| Run 5–24 kHz detector on 12 recordings (about 4 min, including reading files) | Google Colab CPU | Same |
| Run Silbido on 12 recordings (about 90 s) | A colleague's Apple Silicon Mac, MATLAB R2024b | Silbido 3.0 |
| Scoring | Google Colab CPU | Python |
| Reproducing all scores, and making the false-alarm pictures (Nov 8) | Google Colab CPU | Python |
| Statistics, counting the sorted false alarms | Windows PC | Python |
| Writing and small tests | Windows PC, no GPU | Python |

Run times aren't a fair speed comparison, because the two detectors ran on different machines. Most of our data and results are stored in Google Drive.

---

## 11. Results

### 11.1 Synthetic test
| Loudness (SNR) | 2–24 kHz detector recall | 5–24 kHz detector recall |
|---|---|---|
| −5 to 5 dB | 0.051 | 0.086 |
| 5 to 10 dB | 0.647 | 0.632 |
| 10 to 15 dB | 0.905 | 0.885 |
| 15 to 40 dB | 0.966 | 0.980 |
| **Overall** | **0.729** | **0.629** |

- The two perform about the same at each loudness.
- The overall gap comes from the test mix: 66% of the 5–24 kHz test whistles are below 10 dB, against 43% for the 2–24 kHz test.
- Rescored on the other test's mix, the 5–24 kHz detector also gets 0.729.
- The test sets differ, so this isn't a paired comparison.
- Neither detector produced false tracks on clean synthetic negatives.

### 11.2 Real recordings: 5–24 kHz detector against Silbido
**Overall, 5–24 kHz:**

| Scoring | Method | Precision | Recall | F1 | Pitch error | Coverage | Fragmentation |
|---|---|---|---|---|---|---|---|
| **No 30% rule** (recommended) | Silbido | **76.4** | 72.9 | **74.6** | 100 Hz | 80.7% | **1.25** |
| | Our 5–24 kHz detector | 56.3 | **86.9** | 67.1 | **94 Hz** | **86.6%** | 1.30 |
| **With 30% rule** | Silbido | **64.5** | 70.0 | **67.1** | 100 Hz | 80.6% | **1.11** |
| | Our 5–24 kHz detector | 47.1 | **85.2** | 59.9 | **93 Hz** | **85.5%** | 1.14 |

**By species, no 30% rule:**

| Species | Silbido P / R / F1 | Our 5–24 kHz detector P / R / F1 | Higher F1 |
|---|---|---|---|
| Bottlenose | 89.6 / 82.9 / 86.1 | 65.3 / 86.4 / 74.4 | Silbido |
| Common | 58.4 / 51.3 / 54.6 | 45.0 / 87.0 / 59.3 | **Ours** |
| Melon-headed | 71.3 / 72.8 / 72.0 | 38.5 / 87.6 / 53.5 | Silbido |
| Spinner | 86.4 / 84.8 / 85.6 | 76.2 / 86.7 / 81.1 | Silbido |

**By recording, no 30% rule:**

| Recording | Counted / marked | Silbido P / R / F1 | Our 5–24 kHz detector P / R / F1 |
|---|---|---|---|
| Bottlenose `Qx-Tt-SCI0608` | 56 / 152 | 74.4 / 85.7 / **79.7** | 35.0 / 85.7 / 49.7 |
| Bottlenose `...205305` | 99 / 539 | 97.1 / 83.8 / **90.0** | 86.4 / 81.8 / 84.1 |
| Bottlenose `...205730` | 103 / 336 | 93.9 / 80.6 / 86.7 | 89.1 / 91.3 / **90.2** |
| Common `Qx-Dc-CC0411` | 287 / 759 | 26.4 / 21.3 / 23.5 | 35.4 / 81.2 / **49.3** |
| Common `QX-Dc-FLIP0610` | 219 / 533 | 93.2 / 89.5 / **91.3** | 65.3 / 94.1 / 77.1 |
| Common `Qx-Dc-SC03` | 9 / 135 | 90.9 / 77.8 / **83.8** | 57.1 / 100 / 72.7 |
| Melon `...032342` | 54 / 202 | 34.1 / 70.4 / 46.0 | 62.5 / 94.4 / **75.2** |
| Melon `...204327_4` | 153 / 601 | 94.0 / 75.2 / **83.5** | 71.2 / 83.7 / 76.9 |
| Melon `...023000` | 76 / 1,067 | 89.4 / 69.7 / **78.4** | 18.0 / 90.8 / 30.1 |
| Spinner `...224737` | 237 / 734 | 91.6 / 86.5 / **89.0** | 77.0 / 92.4 / 84.0 |
| Spinner `...213127_4` | 112 / 553 | 76.1 / 85.7 / **80.6** | 68.2 / 77.7 / 72.6 |
| Spinner `...232000` | 111 / 400 | 88.6 / 80.2 / 84.2 | 84.6 / 83.8 / 84.2 |

F1 wins: Silbido 8, our detector 3, tie 1 (the "tie", `...232000`, is 84.18 for Silbido against 84.17 for ours, so
strictly Silbido 9, ours 3). Our detector has higher recall on 9 recordings (1 tie), and Silbido has higher precision on 10.

**Our 5–24 kHz detector under other settings:**

| Setting | Precision | Recall | F1 |
|---|---|---|---|
| Main settings, with 30% rule | 47.1 | 85.2 | 59.9 |
| No 150 ms minimum, with 30% rule | 25.6 | 93.3 | 39.3 |
| Revised 2025 answer key, with 30% rule | 47.9 | 85.2 | 60.5 |
| Harmonics removed, with 30% rule | 46.5 | 79.2 | 57.9 |
| No 30% rule | 56.3 | 86.9 | 67.1 |
| All frequencies, with 30% rule | 48.5 | 74.5 | 57.3 |
| All frequencies, no 30% rule | 57.6 | 76.6 | 63.8 |

### 11.3 Is our Silbido run trustworthy?
| Silbido, all frequencies, no 30% rule | Precision | Recall | F1 | Pitch error | Coverage | Fragmentation |
|---|---|---|---|---|---|---|
| Our run | 71.4 | 72.4 | 71.6 | 101 Hz | 80.5% | 1.23 |
| Li et al. (2023) | 81.13 | 72.28 | 75.95 | 101 Hz | 81.05% | 1.23 |

Recall, pitch error, coverage and fragmentation match closely, which suggests our setup is sound. **Precision is the unexplained gap**:

| Silbido species precision | Our run | Li et al. |
|---|---|---|
| Bottlenose | 89.2 | 92.3 |
| Spinner | 87.3 | 90.1 |
| Common | 53.0 | 75.4 |
| Melon-headed | 55.9 | about 66.7 (calculated from their averages) |

### 11.4 Published results, for context only
These cover 5–50 kHz with Li et al.'s setup, so they aren't directly comparable with our 5–24 kHz scores.

| Method (Li et al. 2023) | Precision | Recall | F1 |
|---|---|---|---|
| Their best CNN | 88.78 | 85.78 | 87.20 |
| SMC-PHD (a tracking method) | 76.55 | 92.45 | 83.40 |
| Silbido graph search | 81.13 | 72.28 | 75.95 |

### 11.5 Reproducibility check (8 November 2026)
A Colab cell (`colab_verify_scores.py`) re-scored the committed detections on a fresh machine, reading Google Drive
only. All 12 recordings and both answer keys had the right size and checksum; the detection files were byte-identical
to the committed ones; the scorer self-test gave the expected result; and **all 11 committed score files were
reproduced exactly, field by field.**

### 11.6 How sure are we? Statistics across the 12 recordings
Computed from the per-recording counts in the score files (`tools/dclde2011_stats.py`, results in
`results/dclde2011_stats/`). **Ranges:** bootstrap 95 % ranges, redrawing 3 recordings per species 10,000 times; the
same draws are used for both methods, so the range of the difference is paired. Only 3 recordings per species, so the
ranges are approximate. **p:** paired Wilcoxon test on per-recording values.

| 5–24 kHz, no 30 % rule | Ours | Silbido | Ours − Silbido | p |
|---|---|---|---|---|
| Precision | 56.3 (46.8 to 72.0) | 76.4 (62.3 to 91.3) | **−20.2 (−32.3 to −3.0)** | **0.042** |
| Recall | 86.9 (83.6 to 90.9) | 72.9 (64.8 to 83.1) | **+14.0 (+4.3 to +22.1)** | **0.014** |
| F1 | 67.1 (58.4 to 78.6) | 74.6 (63.1 to 86.4) | −7.5 (−18.0 to +5.9) | 0.18 |

- **F1:** the range of the difference crosses zero, so on this test set **neither method is clearly better overall**.
- **Recall** is clearly higher for ours, and **precision** clearly higher for Silbido.
- With the 30 % rule the pattern is the same (F1 −7.2, range −16.9 to +5.8, p = 0.38).
- When all frequencies count, our recall advantage shrinks to +4.1 (−6.8 to +13.2) and is no longer clear, as expected,
  since our detector can't see above 24 kHz.

### 11.7 What are the false alarms? (blind check, 10 November 2026)
**Method:** on the 4 weakest recordings (`...023000`, `Qx-Tt-SCI0608`, `Qx-Dc-CC0411`, `...032342`), up to 20 false
alarms per method per recording were drawn at random (fixed seed), 147 in all (ours 80, Silbido 67). Each was drawn as a
spectrogram picture with the answer key overlaid. Pictures were shuffled and numbered, so the person sorting them didn't
know which detector made each one. One person sorted them into categories (`false_alarm_guide.md`).

| Category | Ours (80) | Silbido (67) |
|---|---|---|
| Unmarked real whistle | **24 %** | 6 % |
| Harmonic, piece or echo of a marked whistle | **21 %** | 16 % |
| Tonal noise (engine, echosounder) | 2 % | 0 % |
| Clicks or burst pulses | 10 % | 19 % |
| Other noise | 34 % | **52 %** |
| Can't tell | 9 % | 6 % |

- **Almost half of our sampled false alarms are whistle-related:** real whistles the experts didn't mark, or real
  whistles traced imperfectly (broken up, a copy higher up, or switching at a crossing).
- **Silbido's false alarms are mostly noise and clicks.**
- **Our 18 % recording (`...023000`):** 15 of the 20 sampled false alarms were unmarked whistles or pieces of whistles.
  It is a very busy recording, and the answer key seems to miss much of it.
- **Echosounders and engines are almost never the cause** (2 %).
- **Limits:** one person sorted; only 84 of 147 were marked "sure"; the sample is up to 20 per method per recording,
  not proportional to all false alarms (ours 1,538, Silbido 447), so the shares describe the sample. **The official
  scores are not changed by this check.**

Files: `results/false_alarms/` (sheet, key, `counts.md`).

---

## 12. Limitations
| Limitation | Why it matters |
|---|---|
| **2–24 kHz detector has no real-data accuracy score** | It built the VAE-GMM dataset, so its real precision and recall on false killer whales are unknown |
| **Low precision of the 5–24 kHz detector** | It's the main weakness against Silbido (significant, p = 0.042). The blind check (11.7) suggests part of it is unmarked whistles, and part is the tracker breaking up real whistles; the rest is noise and clicks. Not fixed in version 1 |
| **`...023000` recording** | Precision of 18%; the blind check found mostly unmarked whistles and pieces of whistles in the sample |
| **`Qx-Tt-SCI0608` and `Qx-Dc-CC0411`** | Low precision for our detector; in the sample, mostly "other noise" and pieces of whistles, and hardly any echosounder (tonal) sounds |
| **Silbido weak on `Qx-Dc-CC0411` and `...032342`** | In the sample, Silbido's false alarms there were mostly "other noise" |
| **False-alarm categories** | One person sorted 147 pictures, about half marked "sure"; the shares describe a sample, not all false alarms |
| **Precision gap with Li et al.** | Unexplained in two species |
| **24 kHz upper limit** | 344 of 1,860 otherwise-counted whistles (18%) aren't entirely in band |
| **Settings chosen after seeing results** | Harmonics and the 150 ms minimum |
| **Small test set** | 12 recordings; only 9 whistles count in `Qx-Dc-SC03`. The statistics (11.6) show the F1 gap can't be called significant with this few recordings |
| **Imperfect answer key** | Annotators skipped many short whistles, so some "false alarms" may be real |
| **Training noise from one encounter** | All 56 noise files come from encounter 191, and clean windows there were scarce |
| **Synthetic whistles** | Their shapes are generated by rules, so they may not fully match real whistles |
| **Different training and test species** | Good for testing generalisation, but false killer whale performance isn't measured directly |
| **One fixed channel** | The first hydrophone was chosen arbitrarily on 2017 recordings |

---

## 13. Justification of our choices
| Choice | Justification |
|---|---|
| **Build our own detector** | The original wasn't available |
| **Synthetic training data** | No whistle-level labels exist for these recordings, and the correct answers are known exactly |
| **Real noise as background** | It's closer to real conditions than simulated noise |
| **Small network** | Whistles are simple thin lines, and a small model is fast and needs less data |
| **Dilated convolutions, no shrinking** | They see long thin shapes while keeping every output aligned with the spectrogram |
| **DCLDE 2011 benchmark** | It's public, expert-labelled, and used by the closest published work |
| **Li et al.'s 12 recordings** | They allow comparison with published work |
| **Silbido as baseline** | It's the established method, needs no training, and we can run the original |
| **Separate 5–24 kHz training** | It matches the benchmark's lower limit without changing the method |
| **Harmonics kept on benchmark** | The experts mark them as whistles. The VAE-GMM dataset removes them because it needs main whistles |
| **150 ms minimum** | It's Silbido's own default; we didn't use 200 ms, even though it scored slightly better on one recording |
| **Reporting both 30% versions** | The paper's text and its published scores appear to disagree |
| **Dropping detections outside 5–24 kHz** | Otherwise Silbido would be penalised for looking beyond our band |

---

## 14. Next steps
**Decided (10 November 2026):** the preprint (version 1) is posted with the current results; improving precision is
version 2.

### Preprint version 1: status
| Step | Status |
|---|---|
| Save results, code and scripts in the repository | **Done** (`whistle-detector` repository) |
| Reproduce all scores on a fresh machine | **Done**, exact match (11.5) |
| Statistics: ranges and significance tests | **Done** (11.6) |
| False-alarm pictures and blind sorting | **Done** (11.7) |
| No-whistle test (beaked and sperm whales) | **Done** (Test 3): 0.9 false alarms per minute for the 5–24 kHz detector, 4.9 for Silbido at default settings |
| Freeze and tag the version used in the paper | To do |
| Figures and tables | To do |
| Write the 2–4 page paper | To do |
| Licence, public repository, posting | To do; needs the team's agreement |

### Version 2 and other possible improvements, depending on your advice
1. **Run the 2–24 kHz detector on the DCLDE 2011 recordings.** Scoring within 5–24 kHz would give real-data evidence for the configuration behind the dataset, on other species.
2. **Tune for better precision (version 2),** using annotated DCLDE recordings outside the 12 test files. The blind
   check points first at the tracker (joining whistle pieces, crossings, harmonics), then at noise and clicks (more of
   them in the synthetic training data).
3. **Train a 5–50 kHz version,** for a direct comparison with published numbers.
4. **Check about 200 2017 detections by hand,** which gives a real precision estimate without labelling everything.
5. **Hand-label a small set of 2017 recordings,** or leave this as future work in the detector paper. Precision and recall on false killer whales need this.
6. **Contact other researchers:** ask Marie Roch's group about the 30% rule, and Pina Gruden's group about whistle-level labels.
7. **Add Silbido's deep-learning version** as a further comparison.

---

## 15. Possible mentor questions and answers

### The basics
**Q: Why did you build a detector at all?**
A: The paper we're reproducing depends on a whistle detector and tracker we couldn't obtain. Without one, we can't build its dataset.

**Q: Is your detector the same as the paper's?**
A: No. It's a replacement of our own design. We don't claim it matches theirs.

**Q: What's new about it?**
A: It's very small, trains with no human whistle labels, and uses real ocean noise, while ignoring probable real whistles in that noise during training. Li et al. have also worked on detectors trained without human labels, so novelty has to be claimed carefully.

**Q: Why two bands?**
A: 2–24 kHz serves the reproduction. 5–24 kHz exists because the benchmark's answer key starts at 5 kHz.

**Q: Why stop at 24 kHz?**
A: It was our decision, made to cover the paper's Figure 3. The cost is that we miss anything above it, and 18% of otherwise-counted benchmark whistles aren't entirely inside the band.

### Training
**Q: Where did the training data come from?**
A: Real ocean noise from 56 files of NOAA's 2017 false killer whale encounter 191, with synthetic whistles and clicks added by our code.

**Q: Isn't training on synthetic whistles risky?**
A: Yes. If the shapes don't match reality, performance can suffer. That's why we tested on real recordings. It finds most real whistles, but precision suggests it may not separate them well from other sounds.

**Q: Could real whistles in the training noise harm it?**
A: Yes. We screen windows with a classical rule and ignore probable real whistles during training. This reduces the problem, but can't guarantee it's gone.

**Q: Did any test data leak into training?**
A: DCLDE 2011 audio wasn't used in training or threshold selection. However, keeping harmonics and the 150 ms minimum were chosen after seeing test results, and we state this openly.

### Testing and results
**Q: How accurate is the detector on real data?**
A: The 5–24 kHz detector reaches precision 56.3, recall 86.9 and F1 67.1 on 12 labelled recordings. **The 2–24 kHz detector's accuracy on real data is unknown.**

**Q: Is it better than Silbido?**
A: Not overall. Silbido is ahead on F1 (74.6 vs 67.1), but on 12 recordings that gap is not statistically significant (p = 0.18). Silbido is significantly better on precision; ours is significantly better on recall, and also better on pitch error and coverage.

**Q: How does it compare with the best published method?**
A: Li et al.'s best model reports F1 87.2, well above ours, but over 5–50 kHz. They also trained on data from the same corpus, while ours never saw it.

**Q: Why is precision low?**
A: We checked 80 of our false alarms by eye, blind. About a quarter look like real whistles the experts didn't mark, a fifth are real whistles traced imperfectly, and about 45 % are noise or clicks. Echosounders were almost never the cause. So part of the low precision comes from the answer key, and part is real weakness (mainly the tracker, then noise).

**Q: Why is one recording only 18% precise?**
A: In our sample from that recording, 15 of 20 false alarms were unmarked whistles or pieces of whistles. It's a very busy recording, and the answer key seems to miss much of the whistling.

**Q: Can you correct your score using that check?**
A: No. The official scores stay as they are. The check explains them; it was one person on a sample, so it can't be used to recalculate precision.

**Q: Did you change the rules to improve your result?**
A: We report all versions. Without the 150 ms minimum, F1 falls to 39.3, and this is reported too. Dropping the 30% rule helps both methods about equally, and Silbido stays ahead.

**Q: What is the 30% rule, and why two scores?**
A: Li et al. state that a detection must cover more than 30% of a whistle. Silbido's scoring code has no such rule, and our Silbido results match theirs much better without it. Without a clear answer, we report both.

**Q: Can I trust your Silbido results?**
A: Mostly. Recall, pitch error, coverage and fragmentation match Li et al.'s closely. Precision is lower in common dolphins and melon-headed whales, and that gap is unexplained.

**Q: Why not compare directly with Li et al.'s model?**
A: We found no released code for their 2023 model, so we can only quote their numbers.

**Q: Are 12 recordings enough?**
A: They're the benchmark's established test set, but it's a small sample. Our statistics show recall and precision differences are clear, while the F1 difference can't be called significant.

**Q: What about recordings with no whistles at all?**
A: That's the no-whistle test (Test 3): beaked and sperm whale encounters from the 2017 survey, chosen in advance, with no dolphins logged nearby. The 5–24 kHz detector made about 0.9 false alarms per minute there, against 35.6 per minute in the DCLDE dolphin recordings, and the checked pictures were mostly faint noise and clicks. Silbido, on the same files, made 4.9 per minute.

### The 2–24 kHz detector and the dataset
**Q: Is the VAE-GMM dataset reliable, then?**
A: We can't fully say yet. Its detector has passed synthetic tests, engineering checks and visual inspection, but it has no real-data accuracy score. This is the most important open question.

**Q: Can you use the 5–24 kHz scores for it?**
A: Only as supporting evidence for the method. They come from different training noise windows, a different threshold, different settings and other species.

**Q: Why not test the 2–24 kHz detector on DCLDE too?**
A: We haven't yet, and it's a sensible next step. It would need scoring within 5–24 kHz. It still wouldn't measure accuracy on false killer whales.

**Q: Why not label automatically?**
A: Code-made labels only measure agreement with another program. A person has to decide what's true. Code can still speed that person up.

**Q: How much hand-labelling would it take?**
A: About 8 one-minute files, one per encounter. This is a rough plan, and could take a few hours per file. A cheaper option is labelling 3–4 files for recall and checking sampled detections on 4 more for precision.

**Q: Can it stay as future work?**
A: We propose that for the detector paper, provided the limit is stated clearly. The VAE-GMM paper needs your advice, because its dataset depends on this detector.

### Practical
**Q: Can someone reproduce this?**
A: Yes. The data is public, the code records settings and file checksums, and the code and results are in the repository. All scores were reproduced exactly on a fresh Colab machine. We haven't chosen a licence yet.

**Q: Why use several machines?**
A: Training the 5–24 kHz detector used free Colab because no GPU was available at the time. Silbido needs MATLAB, which a colleague has.

**Q: What decisions do you need from me?**
A:
1. ~~Publish as it stands, or improve precision first?~~ Decided: preprint as it stands; precision in version 2.
2. Which score should be the main result (with or without the 30 % rule)?
3. Can hand-labelling stay as future work, for each paper?
4. Which journal or conference should we target?
5. Should we contact the other research groups?
6. Authorship and acknowledgements (code authors, the colleague who ran Silbido).

---

## 16. References
- Park et al. VAE-GMM cetacean whistle paper, *IEEE Access*.
- Roch et al. (2011). Automated extraction of odontocete whistle contours. *J. Acoust. Soc. Am.* 130(4), 2212–2223.
- Li et al. (2020). Learning deep models from synthetic data for extracting dolphin whistle contours. *IJCNN*.
- Li et al. (2023). Using deep learning to track time × frequency whistle contours of toothed whales without human-annotated training data. *J. Acoust. Soc. Am.* 154(1), 502–517. doi:10.1121/10.0020274.
- DCLDE 2011 Conference Data. doi:10.25921/wsnc-js16.
- DCLDE 2022 dataset, NOAA HICEAS 2017 towed-array recordings.
- Yu & Koltun (2016). Multi-scale context aggregation by dilated convolutions. *ICLR*.
- He et al. (2016). Deep residual learning for image recognition. *CVPR*.
- Ioffe & Szegedy (2015). Batch normalization. *ICML*.
- Loshchilov & Hutter (2019). Decoupled weight decay regularization. *ICLR*.
- Kuhn (1955). The Hungarian method for the assignment problem. *Naval Research Logistics Quarterly*.
