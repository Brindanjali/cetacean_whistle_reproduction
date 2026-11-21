# WhistleCode: threat model and claims

Written 2026-11-21, as the first step of presenting the project as covert biomimetic communication rather than a reproduction. It fixes three things before any further work: whom WhistleCode is meant to fool, what it does and does not protect, and what may be claimed today. The protocol and pass marks for the next round of work are frozen beside it in [`PLAN.md`](PLAN.md) section 8.7.

Rows in this document are never edited to fit a later result. New results are added as a new dated column or revision (section 8).

**Working title** `[DECISION]`: *WhistleCode: covert biomimetic underwater messaging with a learned generative model of false killer whale whistles.*

## 1. What is protected

The base paper states the goal of biomimetic communication: signals that are picked up by an outsider should be "misidentified as biological emissions and subsequently ignored" (Park *et al.* 2026, §I-A). WhistleCode adopts that goal.

| Asset | Priority | Protected by |
|---|---|---|
| The fact that a message is being sent | Primary | Sounding like false killer whales: learned whistle shapes, real rhythm, cover whistles, recorded voices and clicks |
| The exact text the receiver accepts | Primary | Reed-Solomon repair and a CRC-16 check before any text is released |
| The content of the message | Secondary, weak | Keyed scrambling only; not encryption (section 5) |

## 2. Parties and assumptions

- **Sender:** one sound source that plays a WAV holding only whistles and clicks. The sea supplies the background.
- **Receiver:** one hydrophone. It holds the shared key, agreed out of band, plus the same codebook, rhythm bank and configuration, all pinned by hash.
- **Adversary:** knows everything about the system except the key. This repository is public, so the design, codebook, configuration and rhythm-bank source recordings (NOAA DCLDE 2022) must be assumed known.

Covertness also rests on conditions WhistleCode cannot test in simulation, stated here as assumptions:

- false killer whales plausibly occur where and when the message is sent; whistles of an absent species are themselves a giveaway;
- the source level and spectrum are plausible for an animal at the distance the adversary assumes;
- the sender does not stay in one place for longer than a group of animals would.

## 3. Adversaries

| Id | Adversary | Capabilities | What would give a message away | How WhistleCode is tested against it | Status (campaign v1) |
|---|---|---|---|---|---|
| A1 | Human analyst | Listens to recordings and looks at spectrograms; no special training on WhistleCode | Whistles that sound artificial, repetitive or out of place | Listening test (second round, mark L) | Not tested |
| A2 | Automated monitoring pipeline | Whistle detectors and species classifiers run over long recordings; flags unusual sounds | Coded whistles not detected or not classified as false killer whale, or scored as anomalies | The reproduction's detector picks the whistles up (it is the receiver); likelihood under the species model was planned (PLAN 8.5) but not yet reported | Partly tested |
| A3 | Steganalyst | Has recordings of the species, including the public DCLDE 2022 data; knows WhistleCode's design; trains classifiers on whistle shapes and timing | Shape statistics (E7); timing (E9); real whistle timing and cover contours matched against the public recordings the bank came from | E7 and E9; matching against public recordings not tested | Rhythm alone passes; rhythm in noise and shapes fail |
| A4 | Array listener | Several hydrophones; localises sources | Every whistle comes from one point, which a group of animals does not do | Not tested | Stated limitation |
| A5 | Channel-stability interceptor (added 2026-11-21 from R1) | One hydrophone; compares the propagation channel between consecutive calls (IEEE IoT J. 2024, 10.1109/jiot.2024.3399742) | A fixed source gives a far more stable channel from call to call than moving, turning animals | Not tested; the simulated sea gives every whistle of a message the same channel, so the simulation cannot show this weakness | Stated limitation |

Out of scope: an adversary who holds the key; active attacks such as jamming, or replaying and injecting recorded messages.

## 4. Covertness levels

| Level | Meaning | Targeted? |
|---|---|---|
| L1 | The transmission is not noticed at all | No: the whistles are meant to be heard, like the animals' own |
| **L2** | **The transmission is heard but taken for false killer whales** | **Yes, against A1, A2 and A3** |
| L3 | The transmission is suspected, but the message cannot be read | Not claimed (section 5) |

## 5. Security properties

| Property | Provided? | Detail |
|---|---|---|
| Integrity against channel errors | Yes | Reed-Solomon over GF(64) with erasures, then CRC-16/CCITT-FALSE on the payload. No wrong text was accepted in 3,700 decoded recordings (campaign v1) |
| Rejection of non-messages | Yes | No message was reported in 3,700 wrong-key reads or 500 keyed reads of noise without a message |
| Confidentiality | **Not claimed** | The payload is XORed with a SHA-256 counter-mode stream from the key and an 8-bit random nonce. The nonce repeats with a 50 % chance within about 19 messages under one key, and a repeat reveals the XOR of two messages. The key is any string, hashed once without stretching, so a recording can be tested against guessed keys offline at decoding speed (median 0.08 s per message on the laptop); weak keys fall quickly |
| Authentication | No | Anyone with the key can forge a message. Without it, a forgery passes the header and CRC checks only by chance |
| Replay protection | No | A recorded message decodes again when it is played again |
| Unlinkability | No | The opening stretch (start signal and header) is chosen by the key alone, so it repeats in every message under that key |
| Source anonymity | No | One source (A4) |

## 6. Claims

State on 2026-11-21: campaign v1 ([`paper/RESULTS.md`](paper/RESULTS.md)), model Nyx (epoch 101), simulation with real ocean recordings. Rates are exact messages; message sets as in [`paper/TEST_PROTOCOL.md`](paper/TEST_PROTOCOL.md).

| # | Claim | Evidence (v1) | Status |
|---|---|---|---|
| C1 | Exact delivery on a clean channel | 200 / 200 | Supported |
| C2 | Exact delivery in real sea noise at moderate SNR | Encounter 214: 98-100 % from 10 dB. Encounter 276: 94 % at 12.5 dB, 100 % from 15 dB | Supported (simulated channel) |
| C3 | At least 95 % exact at 10 dB in held-out sea noise | 84.5 % (97 % for messages under 60 data whistles) | Not supported |
| C4 | Never accepts a false message | 0 in 7,900 tries | Supported (simulated channel) |
| C5 | The timing passes as real whistling (A3, stream on its own) | Rhythm AUC 0.440 (mark 0.60) | Supported |
| C6 | The timing passes as real whistling inside real sea noise | Rhythm AUC 0.684 | Not supported |
| C7 | The whistle shapes pass as real (A3) | Shape AUC 0.944 (mark 0.75; two real encounters score 0.696) | Not supported |
| C8 | It survives the sea channel (echoes and Doppler) | Random sea 4 / 20 / 40 % at 5 / 10 / 20 dB; closing speed ±2 m/s 14-22 % at 15 dB | Not supported (no drift correction yet) |
| C9 | It is more noise-robust than an artificial chirp alphabet | About 10 dB less SNR for the same success | Supported, with a caveat: both were read by the whistle receiver; a matched-filter modem is the fair reference (second round) |
| C10 | It works over a physical acoustic link | — | Not tested |
| C11 | It passes human listeners (A1) | — | Not tested |
| C12 | Throughput | Median 1.08-1.38 bit/s (sweep set, compact text, binary) | Measured |
| C13 | Message confidentiality | — | Not claimed |

**What may be said today**, in one sentence: in simulation with real ocean recordings, WhistleCode delivers exact text at 15 dB and above, never accepted a false message, and its timing passes as real false killer whale whistling; a trained classifier can still tell its whistle shapes from real ones, and it has not been tested over a real acoustic link.

## 7. Scope and ethics

- **No playback near animals.** All testing is simulation plus an in-air test between two computers. Whistles are social signals, and playing synthetic ones in the sea near wild animals could change their behaviour and would need permits.
- **Dual use.** Covert underwater communication is a defence technique; the base paper was funded by Korea's Agency for Defense Development. This project uses public data, publishes its method and results, and claims no operational capability.
- **Listening test.** Volunteers only, anonymous, with no personal data stored.
- **Data.** Public NOAA DCLDE 2022 recordings.

## 8. Revisions

- **2026-11-21:** first version, with the claims of campaign v1. After campaign v2, its results are added as a new column in section 6; the v1 column stays.
- **2026-11-21, after R1 ([`RELATED_WORK.md`](RELATED_WORK.md)):** adversary A5 added, a single-hydrophone interceptor that uses the stability of the propagation channel, from the published literature. No claim changed.
