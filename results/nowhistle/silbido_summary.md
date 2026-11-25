# No-whistle test: Silbido next to our detectors

False alarms per minute on 2017 beaked whale and sperm whale recordings (no whistling species logged within 15 min; the same 146 files for every method). Range: 95 % bootstrap over encounters (seed 2026). Silbido 3.0, classic graph search, run 13 Nov 2026 with `run_silbido_nowhistle.m` on channel 0 resampled to 192 kHz. Made by `mod_detector_5_24/tools/nowhistle_silbido.py`.

## Benchmark rule (5-24 kHz, >= 150 ms)

| Method | Beaked whales | Sperm whales | Both |
|---|---|---|---|
| ours, 5-24 kHz (paper) | 1.02 (0.47 to 1.73); 73 | 0.78 (0.34 to 1.23); 58 | 0.90 (0.54 to 1.30); 131 |
| ours, 2-24 kHz | 0.81 (0.47 to 1.22); 58 | 0.59 (0.29 to 0.89); 44 | 0.70 (0.47 to 0.94); 102 |
| Silbido, default (10 dB) | 5.21 (2.81 to 8.18); 373 | 4.59 (2.06 to 7.20); 340 | 4.90 (3.14 to 6.81); 713 |
| Silbido, 8 dB (more sensitive) | 31.12 (20.25 to 40.95); 2226 | 29.61 (14.26 to 43.30); 2191 | 30.35 (21.21 to 39.01); 4417 |
| Silbido, 12 dB (less sensitive) | 0.67 (0.24 to 1.28); 48 | 0.89 (0.34 to 1.48); 66 | 0.78 (0.42 to 1.19); 114 |

## All tracks the detector outputs

| Method | Beaked whales | Sperm whales | Both |
|---|---|---|---|
| ours, 5-24 kHz (paper) | 4.98 (3.14 to 7.18); 356 | 3.96 (1.82 to 5.99); 293 | 4.46 (3.03 to 5.93); 649 |
| ours, 2-24 kHz | 8.86 (6.20 to 11.84); 634 | 6.39 (3.37 to 9.35); 473 | 7.61 (5.57 to 9.68); 1107 |
| Silbido, default (10 dB) | 5.45 (2.87 to 8.74); 390 | 4.68 (2.16 to 7.24); 346 | 5.06 (3.24 to 7.06); 736 |
| Silbido, 8 dB (more sensitive) | 33.57 (22.48 to 44.02); 2401 | 31.01 (15.76 to 44.74); 2295 | 32.27 (22.94 to 41.10); 4696 |
| Silbido, 12 dB (less sensitive) | 0.78 (0.28 to 1.46); 56 | 0.97 (0.38 to 1.59); 72 | 0.88 (0.48 to 1.32); 128 |

## Paired differences, benchmark rule (per minute; ours minus Silbido default)

| Comparison | Beaked whales | Sperm whales | Both |
|---|---|---|---|
| ours, 5-24 kHz (paper) minus Silbido | -4.19 (-6.58 to -2.15) | -3.81 (-6.21 to -1.65) | -4.00 (-5.63 to -2.50) |
| ours, 2-24 kHz minus Silbido | -4.40 (-7.03 to -2.20) | -4.00 (-6.38 to -1.76) | -4.20 (-5.93 to -2.61) |

Cells: per minute (95 % range); number of detections. A range that does not include 0 means a clear difference.
