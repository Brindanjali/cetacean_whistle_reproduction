# WhistleCode: related work and novelty

Second-round step R1, written 2026-11-21. It places WhistleCode among published biomimetic covert underwater communication schemes, states what appears new and what does not, and lists what this changes for the rest of the second round ([`PLAN.md`](PLAN.md) section 8.7). The threat model and current claims are in [`THREAT_MODEL.md`](THREAT_MODEL.md).

**How the literature was found.**

- **Starting set:** the base paper's references [1]-[11] (biomimetic communication) and [18]-[20] (generated whistles).
- **Search:** OpenAlex for works that cite the closest of these, and keyword searches for biomimetic, bionic and covert underwater acoustic communication from 2024 on (searched 2026-11-21).
- **Screening:** 63 recent records matched by title and were screened.
- **Depth of reading:** four papers were read in full: Ahn *et al.* 2020, WhistleGAN, Bilal *et al.* 2026, and the base paper. About 30 more were read at abstract level, and several are paywalled.

Numbers below are as the authors report them. Their SNR and error definitions differ from WhistleCode's (section 3), so the comparison is indicative, not a ranking.

## 1. The field in four families

| Family | Idea | Typical evidence | Main weakness |
|---|---|---|---|
| **A. Modify a whistle-like carrier** | Bits ride inside each whistle: chirp keying along the contour, carrier-frequency or phase changes, spread spectrum, cepstrum watermarks, learned symbol pulses | Bit error rate (BER) vs SNR; lake and sea trials up to several km; 20-300 bit/s | The modification itself can be detected; covertness and reliability pull against each other |
| **B. Send real recorded whistles as symbols** | Whole real whistles, or time/frequency-shifted copies, stand for symbol values | BER; ocean trials; correlation-based "degree of mimic" (DoM), listening scores | A small recorded set repeats, and repetition is a pattern an adversary can learn (the base paper's own critique) |
| **C. Generate new whistles** | A generative model makes fresh whistles: GANs, a masked-autoencoder GAN, a conditional GAN, flow matching, VAE-GMM, HMM synthesis, parametric models | Mostly generation quality (FID, SSIM, listening scores); communication tested only in simulation, if at all | The generator is rarely built into a working message system |
| **D. The adversary's side** | Covertness scores and recognisers that tell mimicked signals from real animals | Classifier accuracy or AUC; one interceptor uses the stability of the propagation channel | Mostly aimed at family A signals |

Click-based schemes (sperm whale and dolphin clicks) reach kbit/s rates but are a different signal class. Two of them are precedents for WhistleCode's design, though: [8] inserts real recorded clicks as camouflage among coded ones, and [9] imitates overlapping calls of several individuals.

## 2. Comparison

| Work | Carrier | How bits are carried | Rate | Reliability (as reported) | Physical test | Covertness evidence |
|---|---|---|---|---|---|---|
| Lee *et al.* 2020 [6] | Real dolphin whistle contours | The same contour sent at shifted time-frequency positions | — | BER better than a cross-correlation receiver | Ocean | Correlation coefficient, higher than chirp and CV-CFM schemes |
| Ahn *et al.* 2021 [7] | Real dolphin whistles | Time-frequency shift keying with derived orthogonality conditions | — | Zero BER at -6 dB | Lake and ocean | DoM up 35 % (two-step assessment for long signals) |
| Ahn *et al.* 2020 [11] (read in full) | 704 real white-sided dolphin whistles (Watkins database) | k-means groups as symbols (32 subgroups, 3 bits per whistle); a random whistle of the group is sent; a link matrix between consecutive whistles; deep-learning receiver | — | BER 0.002 over 15,000 bits; conventional detectors 0.36-0.37 | Ocean, West Sea of Korea | Every real whistle is used, so DoM is held at its maximum; not otherwise scored |
| Kim *et al.* 2023 (Electronics 12:3999) | Overlapping dolphin "group" whistles | Time-frequency shift keying with continuously varying carrier frequency | Higher than single-whistle schemes | Better BER than conventional covert schemes | Ocean | Listening test (MOS) against real group whistles |
| WhistleGAN, Kim *et al.* 2024 [20] (read in full) | 239 real whistles, augmented to 10,000, into a DCGAN with mel filter banks | Generated whistles used as carriers for existing schemes (CV-CFM, OFDM, HOWM) | 50 bit/s, rate-1/3 turbo code | Same BER as real whistles | None: simulation with three channel responses from Korean seas | MOS 4.3, the same as real whistles (31 listeners) |
| Bilal *et al.* 2026, *Sci. Rep.* (read in full) | **False killer whale**: 58-60 real whistles (Watkins database) | Cepstrum-domain watermark inside a real whistle | 55.5 bit/s | No errors above 4 dB after equalisation | None: a Bellhop-simulated 1 km channel | Correlation; a CNN trained on whistles against noise classed 928 of 950 coded whistles as whistles |
| JASA 2026 (10.1121/10.0044123) | **False killer whale**: pulses extracted from real whistles | Autoencoder-learned symbol waveforms with envelope-driven durations | 250 bit/s | BER 0.0245 at 1.5 km | Sea | ECSM3 score and higher-order cumulants |
| UComms 2026, neural contour steganography | Real dolphin whistle contours | A learned, bounded perturbation of the contour, trained against a discriminator | 5- or 8-bit payloads per whistle | Matches rule-based contour schemes | None: simulated acoustic pipeline | Significantly harder for a learned classifier to detect than rule-based schemes |
| IEEE IoT J. 2025 (10.1109/jiot.2025.3570985) | Dolphin whistles | Phase modulation with joint equalisation | 300 bit/s | BER below 1e-3 at 9 km | Sea | — |
| MVDL 2026, DPDS | Bottlenose dolphin whistles | **Timing:** the delay between consecutive whistles (4 bits per delay) | — | Error-free at -25 dB | None: AWGN simulation | Argued from the carrier |
| **WhistleCode v1** | **False killer whale**: VAE-GMM trained on 63,490 whistles (public DCLDE 2022 data) | A fresh sample of one of 16 mixture components, at one of 4 key-chosen pitches (6 bits per data whistle), placed at real whistle times among cover whistles | **1.1-1.4 bit/s** | Exact text in 100 % of messages from 15 dB narrowband (about -6 dB in-band, section 3) in held-out real sea noise; 0 false messages in 7,900 tries | None: simulation with real ocean recordings | A discriminator trained on real vs coded whistles: shape AUC 0.944 (two real encounters: 0.696); rhythm AUC 0.440 |

## 3. Making the numbers comparable

- **SNR.** WhistleCode quotes a narrowband SNR: the whistle against the noise in its own 93.75 Hz bin. Most papers quote the in-band SNR, which compares the signal power with all the noise in the band it uses. A whistle occupies about one bin at a time, so over WhistleCode's 2.5-14.5 kHz band the in-band SNR is roughly 10 log10(12,000 / 93.75) ≈ 21 dB lower, on the approximate assumption that the noise is flat across the band. WhistleCode's "100 % from 15 dB" is therefore near -6 dB in-band, which is the regime Ahn *et al.* 2021 report. This is an estimate; campaign v2 measures both.
- **Errors.** Most papers report BER, sometimes after a code. WhistleCode reports exact messages after Reed-Solomon and CRC, plus lost and wrong whistles before repair. Campaign v2 also reports the whistle (symbol) error rate against SNR.
- **Rate.** WhistleCode carries data on whole whistles at the animals' own pace. A median message plays about 1.4 whistles per second, a third of them data whistles at 6 bits each. That gives about 2.8 bit/s of coded symbols and about 1.2 bit/s of text after framing and repair. Family A schemes reach 20-300 bit/s because they hide bits inside every whistle's waveform.
- **Adversary strength.** Correlation, MOS and ECSM3 score how alike two sounds are, and a classifier trained on whistles against noise asks only whether a sound is a whistle. WhistleCode's E7 trains a classifier on real against coded whistles. That is a much stronger test: the base paper argues that such learned detectors are exactly the risk, and family D builds them.

## 4. What appears new, and what does not

**Appears new**, as far as the papers read show:

1. **A complete message system whose alphabet is the components of an explicit density model.** This is the generative version of Ahn *et al.* 2020's "a group of whistles is a symbol": every data whistle is a fresh sample, never a replayed or modified recording. The nearest works stop short of that:
   - WhistleGAN feeds generated whistles into existing modulation schemes, tested in simulation.
   - The 2025 conditional GAN and 2026 flow-matching papers report generation quality only.
   - The base paper builds the generator only.
2. **Covertness at the level of the stream, not only the single whistle.** Real whistle timing is borrowed from recordings, about two in three whistles are cover, and the whistles carry recorded voices, virtual animals and clicks. A rhythm discriminator (E9) tests the result. [8] and [9] have analogous ideas for clicks and mixed calls, but no paper read reports a timing-level detector for whistle schemes.
3. **Evaluation against a trained real-vs-coded discriminator, calibrated by two real encounters** (0.696) and run on a held-out encounter. The 2026 neural contour steganography paper also uses a learned classifier. The calibration and the held-out encounter appear to be new.
4. **Message-level reliability.** WhistleCode reports exact delivery, wrong text accepted, wrong-key and empty-recording tries (0 false messages in 7,900), not BER alone.
5. **Openness.** Public data, released code, and pass marks frozen before testing. Prior work mostly uses 58-704 whistles from the Watkins database or private recordings.

**Not new:** imitating false killer whales (two 2026 papers do); a deep-learning receiver (Ahn *et al.* 2020); cover or camouflage signals ([8]); MOS-style listening tests; using generated whistles for communication (WhistleGAN).

**Behind the field:**

- **Rate:** one to two orders of magnitude below family A.
- **No physical test,** where several schemes have lake or sea trials of up to 9 km.
- **Shape covertness fails** (0.944).
- **A known interception attack applies.** An IEEE IoT Journal 2024 paper (10.1109/jiot.2024.3399742) separates mimicked from real calls on one hydrophone, by the stability of the propagation channel from a fixed source; WhistleCode, like every single-projector scheme, is exposed to it.

## 5. Draft novelty statement

> Biomimetic covert schemes either modify whistle-like carriers or replay recorded whistles, and the generative models proposed for this purpose have so far been judged on generation quality. WhistleCode is, to our knowledge, the first complete messaging system whose symbols are freshly sampled components of an explicit density model of one species' whistles (a VAE with a Gaussian-mixture prior trained on public recordings). It hides the data whistles among cover whistles at real whistle timing, and it is evaluated against trained discriminators of whistle shape and stream rhythm, calibrated by the difference between two real encounters, with reliability measured as exact delivery and false-message rates. It trades rate for naturalness: about 1.2 bit/s against 20-300 bit/s for schemes that modify each whistle.

Check this statement again before submission against the papers read only at abstract level (section 7).

## 6. Consequences for the second round

- **Threat model:** add the single-hydrophone channel-stability interceptor as adversary A5 (done in `THREAT_MODEL.md`, revision 2026-11-21).
- **Campaign v2 additions** (reported, no pass mark; recorded in PLAN 8.7):
  - SNR in in-band terms beside narrowband;
  - whistle (symbol) error rate against SNR;
  - the share of coded whistles accepted by a whistle-against-noise classifier, the weaker test used by Bilal *et al.* 2026, for direct comparison;
  - the ECSM3 score, if its definition can be obtained. It is apparently the IEEE JOE 2025 covertness evaluation (10.1109/joe.2024.3508036), judging by the title; not yet confirmed.
- **R3 (shape covertness):** compare with the neural contour steganography approach of training the sender against a discriminator. This is a direction to note, not to adopt, since VAE shapes are the decided voice.
- **Write-up:** present WhistleCode as the low-rate, high-naturalness design point, and compare it in prose with Ahn *et al.* 2020 (groups as symbols) and WhistleGAN (generated carriers).

## 7. Still to read in full (paywalled; needs library access)

- JASA 2026, false killer whale autoencoder waveforms (10.1121/10.0044123);
- UComms 2026, neural contour steganography (10.1109/ucomms71328.2026.11726055);
- IEEE JOE 2025, covertness evaluation and ECSM3 (10.1109/joe.2024.3508036);
- IEEE JOE 2025, research trends and maturity (10.1109/joe.2025.3553982);
- *Applied Ocean Research* 2026, classifier for biomimetic covert signals (10.1016/j.apor.2026.105355);
- IEEE IoT J. 2024, interception by channel stability (10.1109/jiot.2024.3399742);
- Liu *et al.* 2017 [10] (10.1016/j.apacoust.2017.01.018);
- Kim *et al.* 2023 (10.3390/electronics12193999).

## 8. Sources

Base paper references, numbered as there: [1] Du *et al.* 2024 (10.1109/nnice61279.2024.10499166); [2] Li *et al.* 2024 (10.1016/j.apacoust.2024.109907); [3] Li *et al.* 2023 (10.1016/j.apacoust.2023.109691); [4] Wang *et al.* 2022 (10.1016/j.apacoust.2022.108665); [5] ElMoslimany *et al.* 2016 (10.1002/wcm.2676); [6] Lee *et al.* 2020 (10.35848/1347-4065/ab87f0); [7] Ahn *et al.* 2021 (10.3390/s21062184); [8] Jiang *et al.* 2021 (10.1016/j.apacoust.2020.107660); [9] Li *et al.* 2021 (10.1016/j.apacoust.2021.108279); [10] Liu *et al.* 2017 (10.1016/j.apacoust.2017.01.018); [11] Ahn *et al.* 2020 (10.3390/s20216166); [18] Zhang *et al.* 2022 (10.1016/j.jnlest.2022.100171); [19] Wang *et al.* 2023 (10.3390/jmse11051086); [20] Kim *et al.* 2024 (10.3390/electronics13050964).

Found by search: Bilal *et al.* 2026 (10.1038/s41598-025-34297-5); JASA 2026 (10.1121/10.0044123); neural contour steganography 2026 (10.1109/ucomms71328.2026.11726055); Kim *et al.* 2023 (10.3390/electronics12193999); IEEE IoT J. 2025 (10.1109/jiot.2025.3570985); DPDS 2026 (10.1117/12.3121279); conditional GAN 2025 (10.1109/icufn65838.2025.11170017); flow matching 2026 (10.1109/icufn69619.2026.11628714); IEEE JOE 2025 covertness evaluation (10.1109/joe.2024.3508036); IEEE JOE 2025 trends (10.1109/joe.2025.3553982); *Applied Ocean Research* 2026 classifier (10.1016/j.apor.2026.105355); IEEE IoT J. 2024 interception (10.1109/jiot.2024.3399742).
