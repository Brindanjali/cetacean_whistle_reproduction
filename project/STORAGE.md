# Backup and storage

Where every kind of file lives, how many copies exist, what can be rebuilt, and how to restore it. What each dataset and model *is*: [DATA.md](DATA.md), [MODELS.md](MODELS.md). Index of all systems: [README.md](README.md).

## Where things are

| What | Size | Primary copy | Second copy | If lost |
|---|---|---|---|---|
| Code, configs, docs, registers, records, figures | ~60 MB | project laptop, `D:\ALL\cetacean_whistle_reproduction` | **GitHub** (`origin`, public), after each push | clone again |
| VAE checkpoints Nyx and Delphi (`final.pt`), detector checkpoints | 13 MB each | laptop (in git) | **GitHub**; Google Drive (`whistle_vaegmm_E191/`, the Colab run) | clone again. **Irreplaceable** otherwise: retraining cannot reproduce them bit for bit |
| GMMs, latents, component features | ~300 MB | laptop (`models/vaegmm/*/gmm_*`, not in git) | none | refit with `fit-gmm`: bit-identical from the same latents |
| Inception-V3 and VGG-16 weights (Table 2) | 662 MB | laptop (`models/eval_weights/`, not in git) | download.pytorch.org | download again: `python whistle.py fetch-eval-weights --approved` (checks each file's SHA-256); checked against [`checksums/models.sha256`](checksums/models.sha256) |
| Real-image feature cache (Table 2) | ~2 GB | laptop (`models/vaegmm/_eval_cache/`, not in git) | none | rebuilt by the next `vae-eval gen` |
| WhistleCode codebook and rhythm bank | 19 MB | laptop (`whistlecode/outputs/codebook/`, `bank/`) | none | rebuild: `build-codebook` (20-40 min), `build-realism` (also writes `realism/wobble.npz`; alone: `build-wobble`, seconds); checked against [`checksums/models.sha256`](checksums/models.sha256) |
| WhistleCode campaign v1 raw records | part of 5.9 GB | laptop (`whistlecode/outputs/paper/`) | summaries in git (`whistlecode/paper/`) | **Irreplaceable**: the frozen campaign cannot be rerun without becoming a new campaign |
| Built dataset | 19 GB | laptop (`preprocessed/`) | none | rebuild from raw audio with `build-dataset` (long; needs all 1,415 files) |
| Raw audio, encounters 191, 214, 276 | 110 GB | laptop (`encounter_*_audio/`) | NOAA's public bucket | download again; verified by `metadata/manifest_all.csv` |
| Course and private documents | ~25 MB | laptop (`docs/course/` in git; `docs/private/` not) | `docs/private/`: none | the detector draft is **irreplaceable** |
| Page videos (4K and 720p) | ~100 MB | laptop (`web/media4k/`, `web/mediaweb/`, not in git) | sources in `web/CREDITS.md` | re-download and re-encode (`web/README.md`) |
| Tailscale sign-in | — | Docker volume `whistle_tailscale-state` | none | sign in again (`deploy/README.md`) |

## What must have a second copy

Three things cannot be rebuilt and have only one copy today:

1. **`whistlecode/outputs/paper/`**: campaign v1's raw records (trial by trial).
2. **`docs/private/Mentor_Review_1.pdf`**: the detector paper draft.
3. **The local-only records of EXP-015, EXP-019 and EXP-020** (until OPS-5 copies their summaries into git).

**Backup (owner, once, then monthly):** copy those three to a second place that is not this laptop: an external drive or a private Google Drive folder. For example, in PowerShell from the repository root, to a drive `E:`:

```
robocopy whistlecode\outputs\paper E:\whistle_backup\paper /MIR
robocopy docs\private E:\whistle_backup\private /MIR
robocopy whistlecode\outputs E:\whistle_backup\outputs_records *.json *.jsonl /S
```

Never put `docs/private/` in a public place: the repository is public.

## Restore check (monthly, and before the freeze)

1. `python tools/repo.py checksums verify`: every model and index file on the laptop matches the registry.
2. Clone the repository into a temporary folder and run `python -m pytest` there: GitHub alone gives a working, tested checkout (CI also proves this on every push).
3. Open one file from the backup drive: the copy is readable.
4. Log the check in `WORKLOG.md`.

## Rules

- **Nothing is overwritten.** Runs, fits, datasets and campaigns get new folders (the lineage rules in the README).
- **Never delete raw audio** that a planned experiment needs (214 and 276 for campaign v2) until that campaign has run.
- **Large files stay out of git** (`.gitignore`): audio, datasets, GMMs, outputs, 4K video. Nothing over 50 MB is committed.
