# WhistleCode: related work and novelty

Second-round step R1, written 2026-11-21 and revised the same day after a review (section 9). It places WhistleCode among published biomimetic covert underwater communication schemes, states what appears new and what does not, and lists what this changes for the rest of the second round ([`PLAN.md`](PLAN.md) section 8.7). The threat model and current claims are in [`THREAT_MODEL.md`](THREAT_MODEL.md).

**How the literature was found.**

- **Starting set:** the base paper's references [1]-[11] (biomimetic communication) and [18]-[20] (generated whistles).
- **First search:** OpenAlex, for works citing the closest of these (from mid-2023) and for keyword matches on biomimetic, bionic and covert underwater acoustic communication from 2024 on. 63 records matched by title.
- **Second search** (review, same day): the same keywords over 2012-2023 gave 146 records, of which 31 relevant titles were missing from the first search.
- **Depth of reading:** four papers were read in full: Ahn *et al.* 2020, WhistleGAN, Bilal *et al.* 2026, and the base paper. About 40 more were read at abstract level, and several have no abstract in the index or are paywalled (section 7).
- **Not covered:** only one English-language index was searched. The field has a large Chinese-language literature (for example *Acta Physica Sinica*), and IEEE Xplore, Google Scholar and CNKI were not searched.

Numbers below are as the authors report them. Their SNR and error definitions differ from WhistleCode's and are mostly unread (section 3), so the comparison is indicative, not a ranking.

## 1. The field

| Family | Idea | Typical evidence | Main weakness |
|---|---|---|---|
| **A. Modify a whistle-like carrier by rule** | Bits ride inside each call: chirp keying along the contour, carrier-frequency or phase changes, spread spectrum, cepstrum watermarks | BER vs SNR; lake and sea trials up to 9 km; 50-300 bit/s | The modification itself can be detected; covertness and reliability pull against each other |
| **B. Send real recorded calls as symbols** | Whole real whistles or clicks, time/frequency-shifted copies, or frames assembled from original call trains stand for symbol values; the timing between calls can carry bits too | BER; lake and ocean trials since 2013; correlation-based "degree of mimic" (DoM), listening scores | A small recorded set repeats, and repetition is a pattern an adversary can learn (the base paper's own critique) |
| **C. Synthesise or generate new calls** | Parametric models fitted to real calls, HMM synthesis, and generative networks: GANs, a masked-autoencoder GAN, a conditional GAN, flow matching, VAE-GMM | Similarity to real calls (correlation, FID, SSIM, listening scores); communication tested only in simulation, if at all | The generator is rarely built into a working message system |
| **D. Learn the embedding** | A network is trained to put bits into a carrier and read them back, usually against a discriminator: learned contour perturbations, GAN encoder-decoders, autoencoder-learned symbol pulses | BER, sometimes sea trials; a learned classifier or covertness score | Each call is still a modified carrier |
| **E. The adversary's side** | Covertness scores; recognisers that tell mimicked signals from real animals; interceptors that use the channel's stability or the transmitter's distortion | Classifier accuracy or AUC; field experiments | Mostly aimed at families A and B |

**History.**

- **2013, the first lake trial** (Liu, Qiao and Ismail): dolphin whistles synchronise, and the time between dolphin clicks carries 37 bit/s.
- **Since then:**
  - a review of the field (*Physical Communication* 2018);
  - frames built from original whale call pulses, presented as steganography (IEEE Communications Magazine 2018);
  - a frame design from killer whale calls (IEEE Access 2020);
  - [8], which inserts real recorded clicks as camouflage among coded ones;
  - [9], which imitates overlapping calls of several individuals.
- **Security layers** have been proposed separately: a hash-tree scheme against replayed, forged and altered messages (FITEE 2021).

## 2. Comparison

"Read" says whether the paper was read in full or only its abstract.

| Work | Read | Carrier | How bits are carried | Rate | Reliability (as reported) | Physical test | Covertness evidence |
|---|---|---|---|---|---|---|---|
| Liu, Qiao and Ismail 2013, JASA-EL | abstract | Dolphin whistles (sync) and clicks (data) | **Timing:** the interval between clicks | 37 bit/s | BER below 1e-4 | Lake | — |
| Lee *et al.* 2020 [6] | abstract | Real dolphin whistle contours | The same contour sent at shifted time-frequency positions | — | BER better than a cross-correlation receiver | Ocean | Correlation coefficient, higher than chirp and CV-CFM schemes |
| Ahn *et al.* 2021 [7] | abstract | Real dolphin whistles | Time-frequency shift keying with derived orthogonality conditions | — | Zero BER at -6 dB (SNR definition not read) | Lake and ocean | DoM up 35 % (two-step assessment for long signals) |
| Ahn *et al.* 2020 [11] | full | 704 real white-sided dolphin whistles (Watkins database) | k-means groups as symbols (32 subgroups, 3 bits per whistle); a random whistle of the group is sent; a link matrix between consecutive whistles; deep-learning receiver | Not stated | BER 0.002 over 15,000 bits; conventional detectors 0.36-0.37 | Ocean, West Sea of Korea | Every real whistle is used, so DoM is held at its maximum; not otherwise scored |
| Kim *et al.* 2023 | abstract | Overlapping dolphin "group" whistles | Time-frequency shift keying with continuously varying carrier frequency | Higher than single-whistle schemes | Better BER than conventional covert schemes | Ocean | Listening test (MOS) against real group whistles |
| Synthesis of cetacean tonal sounds, IEEE Access 2020 | abstract | 13 cetacean tonal sounds | Parametric synthesis whose parameters can be set for detection and communication | — | — | Experiments (kind not stated) | Pearson correlation above 0.97 with the real sounds |
| WhistleGAN, Kim *et al.* 2024 [20] | full | 239 real whistles, augmented to 10,000, into a DCGAN with mel filter banks | Generated whistles used as carriers for existing schemes (CV-CFM, OFDM, HOWM) | 50 bit/s, rate-1/3 turbo code | Same BER as real whistles | None: simulation with three channel responses from Korean seas | MOS 4.3, the same as real whistles (31 listeners) |
| Bilal *et al.* 2026, *Sci. Rep.* | full | **False killer whale**: 58-60 real whistles (Watkins database) | Cepstrum-domain watermark inside a real whistle | 55.5 bit/s | No errors above 4 dB after equalisation | None: a Bellhop-simulated 1 km channel | Correlation; a CNN trained on whistles against noise classed 928 of 950 coded whistles as whistles |
| IEEE IoT J. 2025 | abstract | Dolphin whistles | Phase modulation with joint equalisation | 300 bit/s | BER below 1e-3 at 9 km | Sea | — |
| IEEE Trans. Green Comm. 2026 | abstract | Marine mammal calls (a low-frequency wavelet component) | A GAN encoder, decoder and discriminator embed and read the bits | 20 bit/s | Decoding errors below 2.1e-4 at 15 dB | Not stated in the abstract | Discriminator in training |
| JASA 2026 | abstract | **False killer whale**: pulses extracted from real whistles | Autoencoder-learned symbol waveforms with envelope-driven durations | 250 bit/s | BER 0.0245 at 1.5 km | Sea | ECSM3 score and higher-order cumulants |
| UComms 2026, neural contour steganography | abstract | Real dolphin whistle contours | A learned, bounded perturbation of the contour, trained against a discriminator | 5- or 8-bit payloads per whistle | Matches rule-based contour schemes | None: simulated acoustic pipeline | Significantly harder for a learned classifier to detect than rule-based schemes |
| MVDL 2026, DPDS | abstract | Bottlenose dolphin whistles | **Timing:** the delay between consecutive whistles (4 bits per delay) | — | Error-free at -25 dB | None: AWGN simulation | Argued from the carrier |
| **WhistleCode v1** | — | **False killer whale**: VAE-GMM trained on 63,490 whistles (public DCLDE 2022 data) | A fresh sample of one of 16 mixture components, at one of 4 key-chosen pitches (6 bits per data whistle), placed at real whistle times among cover whistles | **1.1-1.4 bit/s** | Exact text in 100 % of messages from 15 dB narrowband, about -10 dB in-band (section 3), in held-out real sea noise; 0 false messages in 7,900 tries | None: simulation with real ocean recordings | A discriminator trained on real vs coded whistles: shape AUC 0.944 (two real encounters: 0.696); rhythm AUC 0.440 |

## 3. Making the numbers comparable

- **SNR.**
  - **WhistleCode's measure is narrowband:** the quietest data whistle, as a tone in its own 93.75 Hz bin, against the *median* noise magnitude in that bin.
  - **Most papers quote an in-band SNR:** the signal power against the *mean* power of all the noise in the band it uses.
  - **The measured gap** ([`experiments/snr_inband.py`](experiments/snr_inband.py): 12 noise files per encounter, the sender's pitch pool, the 2.5-14.5 kHz band) is:

    | Noise | Median gap | Range across files |
    |---|---|---|
    | Encounter 214 | 22.3 dB | 20.6-33.4 dB |
    | Encounter 276 | 25.3 dB | 23.0-43.2 dB |

  - **Why it exceeds the flat-noise estimate of 21 dB:** the median of a noise magnitude sits about 1.6 dB below its mean power, and clicks and real whistles in the recordings raise the mean power but hardly the median bin level. That is also why a few files are 10-20 dB further off.
  - **In-band terms for WhistleCode:** "100 % from 15 dB" in encounter-276 noise is about -10 dB in-band, and "at least 98 % from 10 dB" in encounter-214 noise is about -12 dB in-band, both for the median file.
  - **No placing against other papers yet.** Most papers' SNR definitions were not read, so WhistleCode's figures cannot yet be placed against theirs (for example Ahn *et al.* 2021's -6 dB). Campaign v2 reports both measures per trial.
- **Errors.** Most papers report BER, sometimes after a code. WhistleCode reports exact messages after Reed-Solomon and CRC, plus lost and wrong whistles before repair. Campaign v2 also reports the whistle (symbol) error rate against SNR.
- **Rate.**
  - **WhistleCode:** it carries data on whole whistles at the animals' own pace. A median message plays about 1.4 whistles per second, and about a third of them carry data, header included. That gives about 2.8 bit/s of coded symbols and about 1.2 bit/s of text after framing and repair. The figures for this share differ between documents. Of the rhythm bank's 73,791 whistles, 19,432 (26 %) can carry data, and `TEST_PROTOCOL.md` says about one in four played whistles carries data. In the campaign's median compact-text message, though, 66 of 198 played whistles (a third) were data whistles, header included. To be reconciled in R7.
  - **Its natural peers** are the schemes that send whole calls as symbols (family B), but most of them do not state a rate in the text read. Ahn *et al.* 2020 send 3 bits per whistle.
  - **Faster schemes:** those that embed bits inside each call (families A and D) reach 20-300 bit/s, and the 2013 click-timing trial reached 37 bit/s.
- **Adversary strength.**
  - **What most scores test:** correlation, MOS and ECSM3 score how alike two sounds are, and a classifier trained on whistles against noise asks only whether a sound is a whistle.
  - **What WhistleCode's E7 tests:** it trains a classifier on real against coded whistles, which is a much stronger test. The base paper argues that learned detectors are exactly the risk, and family E builds them.
  - **Physical-layer attacks:** none of these scores tests them. One is a fixed source's unusually stable channel (IEEE IoT J. 2024); the other is the distortion an electro-acoustic projector adds to animal sounds (*Sci. Rep.* 2023, two field experiments).

## 4. What appears new, and what does not

**Appears new**, as far as the papers read show:

1. **Symbols that are components of an explicit density model, with every data whistle a fresh sample from its component.** This is the generative counterpart of Ahn *et al.* 2020's "a group of real whistles is a symbol". It differs from the other routes:
   - **Parametric synthesis** (IEEE Access 2020) fits hand-designed signal models to real calls.
   - **Learned embeddings** (IEEE Trans. Green Comm. 2026; neural contour steganography; the JASA 2026 autoencoder pulses) train a network to put bits into a carrier.
   - **WhistleGAN** feeds generated whistles into existing modulation schemes.
   - **Generation-only work** (the conditional GAN of 2025, flow matching in 2026, and the base paper) stops at the generator.

   The unread *Ocean Engineering* 2026 generative framework (section 7) is the main risk to this claim.
2. **Covertness tested at the level of the stream.** Real whistle timing is borrowed from recordings, and the data whistles sit among cover whistles with recorded voices, virtual animals and clicks. A rhythm discriminator (E9) tests the result. Frames built from original calls ([8]; 2018; 2020) are a precedent for the design, but no paper read reports a timing-level detector.
3. **A trained real-vs-coded discriminator, calibrated by two real encounters** (0.696) and run on a held-out encounter. Learned classifiers appear in other work too (neural contour steganography; the *Applied Ocean Research* 2026 recogniser tested on unseen modulation conditions). The calibration against real-vs-real appears to be new.
4. **Message-level reliability:** exact delivery, wrong text accepted, and wrong-key and empty-recording tries (0 false messages in 7,900), not BER alone.
5. **Openness:** public data, released code, and pass marks frozen before testing. Prior work mostly uses 58-704 whistles from the Watkins database or private recordings.

**Not new:**

- imitating false killer whales (two 2026 papers do);
- a deep-learning receiver (Ahn *et al.* 2020);
- cover or camouflage calls, and frames built from original calls ([8]; 2018; 2020);
- the steganography framing (2018);
- synthesising calls for communication (2020), and networks that carry bits (2026);
- MOS-style listening tests;
- security layers against replay and forgery (2021).

**Behind the field:**

- **Rate:** one to two orders of magnitude below families A and D, and below the 2013 click-timing trial.
- **No physical test,** where several schemes have lake or sea trials of up to 9 km.
- **Shape covertness fails** (0.944).
- **Two published physical-layer attacks apply to every single-projector scheme, WhistleCode included.** One uses channel stability (IEEE IoT J. 2024). The other uses projector distortion (*Sci. Rep.* 2023), which WhistleCode has never been tested against, because no test plays it through a projector.

## 5. Draft novelty statement

> Biomimetic covert schemes modify whistle-like carriers, replay or rearrange recorded calls, synthesise calls from parametric models, or train networks to embed bits in a carrier. WhistleCode takes a different route: its symbols are the mixture components of an explicit density model of one species' whistles (a VAE with a Gaussian-mixture prior trained on public recordings), and every data whistle is a fresh sample from its component. To our knowledge, it is the first complete messaging system built this way. It hides the data whistles among cover whistles at real whistle timing and is evaluated against trained discriminators of whistle shape and stream rhythm, calibrated by the difference between two real encounters, with reliability measured as exact delivery and false-message rates. It trades rate for naturalness: about 1.2 bit/s, against 20-300 bit/s for schemes that embed bits inside each call.

Check this statement again before submission against section 7, above all the *Ocean Engineering* 2026 generative framework, and after the searches the "Not covered" item at the top asks for.

## 6. Consequences for the second round

- **Threat model** (`THREAT_MODEL.md`, revisions of 2026-11-21):
  - adversary A5, the channel-stability interceptor;
  - adversary A6, the projector-distortion detector;
  - the published hash-tree scheme, named as a remedy for the missing replay and forgery protection (not built).
- **Campaign v2 additions** (reported, no pass mark; defined in PLAN 8.7):
  - in-band SNR per trial;
  - the whistle (symbol) error rate;
  - the share of coded whistles a whistle-against-noise classifier accepts, which is the weaker test of Bilal *et al.* 2026;
  - the ECSM3 score, if its definition can be obtained. It is apparently the IEEE JOE 2025 covertness evaluation, judging by its title; not yet confirmed.
- **R5 (in-air test):** it measures delivery only. A laptop speaker adds its own distortion, so its recordings must not be read as evidence of covertness.
- **R3 (shape covertness):** note the learned-embedding approach of training the sender against a discriminator, as a direction only, since VAE shapes are the decided voice.
- **Literature, still open:** search IEEE Xplore, Google Scholar and CNKI, and follow the reference lists of the 2018 review and the IEEE JOE 2025 trends review.
- **Write-up:** present WhistleCode as the low-rate, high-naturalness design point. Compare it in prose with Ahn *et al.* 2020 (groups as symbols), WhistleGAN (generated carriers) and the learned embeddings.

## 7. Still to read in full

**Open access, can be read next:**

- *Sci. Rep.* 2023, projector distortion makes biomimicking discoverable (10.1038/s41598-023-29413-2);
- IEEE Access 2020, synthesis of cetacean tonal sounds (10.1109/access.2020.3004282);
- IEEE Access 2020, camouflage frame from killer whale calls (10.1109/access.2020.2970746);
- Kim *et al.* 2023 (10.3390/electronics12193999).

**No abstract in the index**, which makes these the most likely to overlap unseen:

- *Ocean Engineering* 2026, receiver-guided generative semantic communication framework (10.1016/j.oceaneng.2026.127837);
- *Applied Acoustics* 2026, stochastic jitter waveform codebook (10.1016/j.apacoust.2026.111450);
- *Applied Acoustics* 2025, PCHIP-based whistle generation (10.1016/j.apacoust.2025.110673);
- *Physical Communication* 2026, segment-wise frequency perturbation (10.1016/j.phycom.2026.103163);
- *Applied Acoustics* 2026, whale whistle and phase-reduced PSK (10.1016/j.apacoust.2026.111331);
- *Signal Processing* 2024, masking technique (10.1016/j.sigpro.2024.109632);
- *Physical Communication* 2018, review (10.1016/j.phycom.2018.07.007).

**Paywalled** (needs library access):

- JASA 2026, false killer whale autoencoder waveforms (10.1121/10.0044123);
- UComms 2026, neural contour steganography (10.1109/ucomms71328.2026.11726055);
- IEEE Trans. Green Comm. 2026 (10.1109/tgcn.2026.3693088);
- IEEE JOE 2025, covertness evaluation and ECSM3 (10.1109/joe.2024.3508036);
- IEEE JOE 2025, research trends and maturity (10.1109/joe.2025.3553982);
- *Applied Ocean Research* 2026, classifier for biomimetic covert signals (10.1016/j.apor.2026.105355);
- IEEE IoT J. 2024, interception by channel stability (10.1109/jiot.2024.3399742);
- IEEE Communications Magazine 2018, bio-inspired steganography (10.1109/mcom.2018.1601228);
- Liu *et al.* 2017 [10] (10.1016/j.apacoust.2017.01.018).

## 8. Sources

**Base paper references, numbered as there:** [1] Du *et al.* 2024 (10.1109/nnice61279.2024.10499166); [2] Li *et al.* 2024 (10.1016/j.apacoust.2024.109907); [3] Li *et al.* 2023 (10.1016/j.apacoust.2023.109691); [4] Wang *et al.* 2022 (10.1016/j.apacoust.2022.108665); [5] ElMoslimany *et al.* 2016 (10.1002/wcm.2676); [6] Lee *et al.* 2020 (10.35848/1347-4065/ab87f0); [7] Ahn *et al.* 2021 (10.3390/s21062184); [8] Jiang *et al.* 2021 (10.1016/j.apacoust.2020.107660); [9] Li *et al.* 2021 (10.1016/j.apacoust.2021.108279); [10] Liu *et al.* 2017 (10.1016/j.apacoust.2017.01.018); [11] Ahn *et al.* 2020 (10.3390/s20216166); [18] Zhang *et al.* 2022 (10.1016/j.jnlest.2022.100171); [19] Wang *et al.* 2023 (10.3390/jmse11051086); [20] Kim *et al.* 2024 (10.3390/electronics13050964).

**Found by search, 2024 on:** Bilal *et al.* 2026 (10.1038/s41598-025-34297-5); JASA 2026 (10.1121/10.0044123); neural contour steganography 2026 (10.1109/ucomms71328.2026.11726055); IEEE Trans. Green Comm. 2026 (10.1109/tgcn.2026.3693088); IEEE IoT J. 2025 (10.1109/jiot.2025.3570985); DPDS 2026 (10.1117/12.3121279); conditional GAN 2025 (10.1109/icufn65838.2025.11170017); flow matching 2026 (10.1109/icufn69619.2026.11628714); IEEE JOE 2025 covertness evaluation (10.1109/joe.2024.3508036); IEEE JOE 2025 trends (10.1109/joe.2025.3553982); *Applied Ocean Research* 2026 classifier (10.1016/j.apor.2026.105355); IEEE IoT J. 2024 interception (10.1109/jiot.2024.3399742).

**Found by search, 2012-2023:** Liu, Qiao and Ismail 2013 (10.1121/1.4795219); *Physical Communication* 2018 review (10.1016/j.phycom.2018.07.007); IEEE Communications Magazine 2018 (10.1109/mcom.2018.1601228); IEEE Access 2020 synthesis (10.1109/access.2020.3004282); IEEE Access 2020 camouflage frame (10.1109/access.2020.2970746); FITEE 2021 hash-tree security (10.1631/fitee.2000043); *Sci. Rep.* 2023 projector distortion (10.1038/s41598-023-29413-2); Kim *et al.* 2023 (10.3390/electronics12193999).

## 9. Revisions

- **2026-11-21:** first version.
- **2026-11-21, after review:**
  - **SNR gap:** measured on real noise (22.3 and 25.3 dB median, not the flat-noise 21 dB), so WhistleCode's 15 dB is about -10 dB in-band; the comparison with Ahn *et al.* 2021 is withdrawn.
  - **Second search:** 2012-2023, adding the 2013 trial, the 2018 review and steganography paper, the 2020 synthesis and frame papers, the 2021 security scheme and the 2023 projector-distortion attack.
  - **New family:** D, learned embeddings, including the previously uncited IEEE Trans. Green Comm. 2026 paper behind the "20 bit/s".
  - **Novelty statement narrowed:** to components of an explicit density model, sampled fresh.
  - **Clarifications:** rate peers (family B) and the data-whistle share.
  - **Reading list:** extended with the papers that have no abstract.
