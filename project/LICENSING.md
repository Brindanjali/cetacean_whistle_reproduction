# Licensing

What licence covers each part of the repository, and every third-party work it uses. Index of all systems: [README.md](README.md).

## This project's code

**Apache License 2.0** ([`LICENSE`](../LICENSE), the unmodified text from apache.org, SHA-256 `cfc7749b…3d30`), chosen 2026-11-22 ([D-022](DECISIONS.md#d-022)).

- **What it allows:** anyone may use, change and redistribute the code, also commercially, if they keep the licence and the [`NOTICE`](../NOTICE) file and mark the files they changed.
- **Patents:** every contributor grants a patent licence for their contributions, and loses it if they sue over patents in the work. This matters for a new communication scheme such as WhistleCode.
- **Compatibility:** every dependency below is permissive (BSD, MIT, Apache-2.0, PSF, public domain), so there is no conflict.
- **Scope:** the code and documents written here. `NOTICE` lists the third-party material it does not cover (below).
- **Copyright line:** "The Falsetto contributors" (temporary name, D-024) in `NOTICE`, which covers the teammates who contributed. The owner may put their own name there instead.

## Third-party material in the repository

| What | Where | Licence | Obligation |
|---|---|---|---|
| The base paper (Park *et al.*, IEEE Access 2026) | `resources/VAE-GMM Cetacean Whistles.pdf` | CC BY-NC-ND 4.0 (stated on its first page) | keep unmodified, credit the authors, no commercial use |
| NOAA DCLDE detection table and dataset description | `metadata/DCLDE2020_DetectionData.xlsx`, `metadata/Dataset_DCLDE_Oahu.pdf` | NOAA material; U.S. federal works are generally public domain in the U.S. | credit NOAA; confirm the terms before reuse beyond this project (OPS-6) |
| Page footage (Pixabay, Pexels) | `web/media4k/`, `web/mediaweb/` (not in git), posters in git | Pixabay Content License, Pexels License | no resale or redistribution as stock; details in [`web/CREDITS.md`](../web/CREDITS.md) |
| Page fonts | `web/fonts/` | SIL Open Font License 1.1 ([`web/CREDITS.md`](../web/CREDITS.md)) | keep the licence with the fonts; don't sell them alone |

## Third-party material used but not redistributed

| What | Where it is used | Terms |
|---|---|---|
| NOAA DCLDE 2022 recordings (HICEAS 2017, R/V *Lasker*) | raw audio, local only | public data; credit NOAA when used |
| DCLDE 2011 benchmark recordings | the detector paper (`mod_detector_5_24/`) | public benchmark; credit the DCLDE 2011 organisers |
| Elsevier paper "Whistle extraction" | `docs/private/` (never in git) | copyright; personal reading copy only |
| Reference [32] text of unknown licence | `resources/reference_32_mca_cfar.md` (gitignored) | not redistributed |
| Inception-V3 and VGG-16 weights | not downloaded ([D-006](DECISIONS.md#d-006)) | — |

## Python dependencies

From the installed packages' own metadata (2026-11-21). All are permissive.

| Package | Licence | Package | Licence |
|---|---|---|---|
| numpy | BSD-3-Clause (with 0BSD, MIT, Zlib, CC0 parts) | fastapi | MIT |
| scipy | BSD-3-Clause | uvicorn | BSD-3-Clause |
| soundfile | BSD-3-Clause | python-multipart | Apache-2.0 |
| torch | BSD-3-Clause with Apache-2.0 parts | pydantic | MIT |
| torchvision | BSD-3-Clause | pytest | MIT |
| matplotlib | Matplotlib licence (PSF-based) | httpx | BSD-3-Clause |
| pillow | MIT-CMU | reedsolo | Public domain (Unlicense / MIT-0) |
| pandas | BSD-3-Clause | ruff | MIT |
| scikit-learn | BSD-3-Clause | cryptography (`serve --lan` only) | Apache-2.0 or BSD-3-Clause |

Container images: `python:3.11-slim-bookworm` (PSF and Debian licences), `tailscale/tailscale` (BSD-3-Clause).

**Rule:** a new dependency is added to this table in the same change (Definition of Done). A copyleft licence (GPL, AGPL) needs the owner's decision first.

## Citing

[`CITATION.cff`](../CITATION.cff) makes GitHub show "Cite this repository". It points first at the base paper, which anyone using this work should cite.
