# WhistleFlow

WhistleFlow extends the Park et al. reproduction. It learns false killer whale whistles directly from the audio recordings, with no images at any step, and generates new whistles as audio. Everything for this enhancement lives in this folder.

## The idea

1. **Audio → vectors.** Learn an "acoustic alphabet" from the raw recordings without labels: a time-ordered sequence of vectors that can be turned back into the same audio.
2. **Find whistles in the vectors.** A detector that works directly on the vector sequences and marks each whistle's start and end, including overlapping whistles.
3. **Whistle units.** Each detected whistle becomes a sequence of units, so similar-sounding whistles get similar sequences. Each keeps its context: time, encounter, what else was sounding.
4. **Learn the structure.** Within a whistle (contour, duration, harmonics, envelope) first. Between whistles (order, gaps, overlaps) later.
5. **Generate new whistle vectors.** New sequences that are plausible for the species and not copies. Optionally steered by length, frequency range or encounter.
6. **Vectors → audio.** Turn the generated vectors back into sound.
7. **Evaluate without images.** Rebuild fidelity, detector precision and recall, realism, novelty and diversity, all on held-out files and one held-out encounter. The VAE-GMM V1 is the baseline.

No model in WhistleFlow reads a spectrogram image. The reproduction's spectrogram detector (`ridgenet-v2c`) can serve only as an outside benchmark for the new detector.

## Boundaries

- **Reads, never writes:** the encounter audio folders, `metadata/` and `preprocessed/` are read-only inputs.
- **Untouched:** the reproduction (`src/whistlepipe`, `configs/pipeline.toml`, `resources/`, `colab/`, `web/`, `tests/`) is never modified by WhistleFlow work.
- **Self-contained:** WhistleFlow code, configuration, tests, documents and outputs all stay inside `whistleflow/`.

## Status

- The idea is finalised.
- No technologies have been chosen yet.
- Nothing has been built.
