# Silbido at three detection thresholds

Silbido 3.0, classic graph search, Silbido's default settings except the peak threshold (`energy_thresh`). DCLDE 2011: Li et al. 2023 test set, 2011 answer key, species average of 3 species-pooled scores, detections >= 150 ms. No-whistle: false alarms per minute on 146 beaked and sperm whale minutes, benchmark rule (5-24 kHz, >= 150 ms), 95 % range over encounters. The 10 dB DCLDE scores are the 5 Nov run (re-scored here unchanged; the 13 Nov repeat gives the same scores). Made by `mod_detector_5_24/tools/silbido_thresholds.py`.

## DCLDE 2011: 5-24 kHz, no 30 % rule (main scoring)

| Method | Precision | Recall | F1 | False alarms (DCLDE) | No-whistle false alarms per minute |
|---|---|---|---|---|---|
| ours, 5-24 kHz (paper) | 56.3 | 86.9 | 67.1 | 1538 | 0.90 (0.54 to 1.30) |
| Silbido, 8 dB | 59.5 | 80.5 | 67.4 | 1080 | 30.35 (21.21 to 39.01) |
| Silbido, 10 dB (default) | 76.4 | 72.9 | 74.6 | 447 | 4.90 (3.14 to 6.81) |
| Silbido, 12 dB | 79.3 | 57.0 | 66.1 | 361 | 0.78 (0.42 to 1.19) |

## DCLDE 2011: 5-24 kHz, with 30 % rule

| Method | Precision | Recall | F1 | False alarms (DCLDE) | No-whistle false alarms per minute |
|---|---|---|---|---|---|
| ours, 5-24 kHz (paper) | 47.1 | 85.2 | 59.9 | 1824 | 0.90 (0.54 to 1.30) |
| Silbido, 8 dB | 48.0 | 78.1 | 58.7 | 1412 | 30.35 (21.21 to 39.01) |
| Silbido, 10 dB (default) | 64.5 | 70.0 | 67.1 | 664 | 4.90 (3.14 to 6.81) |
| Silbido, 12 dB | 64.7 | 52.2 | 57.4 | 554 | 0.78 (0.42 to 1.19) |

## DCLDE 2011: all frequencies, no 30 % rule

| Method | Precision | Recall | F1 | False alarms (DCLDE) | No-whistle false alarms per minute |
|---|---|---|---|---|---|
| ours, 5-24 kHz (paper) | 57.6 | 76.6 | 63.8 | 1538 | 0.90 (0.54 to 1.30) |
| Silbido, 8 dB | 53.4 | 79.9 | 62.5 | 1745 | 30.35 (21.21 to 39.01) |
| Silbido, 10 dB (default) | 71.4 | 72.4 | 71.6 | 667 | 4.90 (3.14 to 6.81) |
| Silbido, 12 dB | 73.4 | 56.3 | 63.3 | 576 | 0.78 (0.42 to 1.19) |

## DCLDE 2011: all frequencies, with 30 % rule

| Method | Precision | Recall | F1 | False alarms (DCLDE) | No-whistle false alarms per minute |
|---|---|---|---|---|---|
| ours, 5-24 kHz (paper) | 48.5 | 74.5 | 57.3 | 1824 | 0.90 (0.54 to 1.30) |
| Silbido, 8 dB | 44.0 | 77.6 | 55.1 | 2106 | 30.35 (21.21 to 39.01) |
| Silbido, 10 dB (default) | 61.3 | 69.8 | 65.1 | 904 | 4.90 (3.14 to 6.81) |
| Silbido, 12 dB | 61.0 | 51.9 | 55.7 | 786 | 0.78 (0.42 to 1.19) |
