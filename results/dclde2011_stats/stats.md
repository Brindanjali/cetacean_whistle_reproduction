# DCLDE 2011: uncertainty of the comparison (12 recordings, species average)

Values in brackets: bootstrap 95 % range (10000 resamples, 3 recordings per species drawn with replacement, seed 1; approximate, only 3 recordings per species). The difference range is paired (same resamples for both methods). Wilcoxon: paired signed-rank test on per-recording values, two-sided, exact, ties dropped. Made by `mod_detector_5_24/tools/dclde2011_stats.py` from the committed score files.

### 5-24 kHz, no 30 % rule (main)  (`score_gt2011_min150ms_ov0.json`)

| | Ours | Silbido | Ours - Silbido | Recordings ours / Silbido better / tie | Wilcoxon p |
|---|---|---|---|---|---|
| precision | 56.3 (46.8 to 72.2) | 76.4 (62.2 to 91.2) | -20.2 (-32.2 to -2.6) | 2 / 10 / 0 | 0.042 |
| recall | 86.9 (83.6 to 91.0) | 72.9 (64.8 to 83.0) | 14.0 (4.3 to 22.1) | 9 / 2 / 1 | 0.014 |
| f1 | 67.1 (58.3 to 78.8) | 74.6 (63.0 to 86.4) | -7.5 (-18.0 to 5.9) | 3 / 9 / 0 | 0.176 |

### 5-24 kHz, with 30 % rule  (`score_gt2011_min150ms.json`)

| | Ours | Silbido | Ours - Silbido | Recordings ours / Silbido better / tie | Wilcoxon p |
|---|---|---|---|---|---|
| precision | 47.1 (39.2 to 61.1) | 64.5 (52.4 to 76.8) | -17.4 (-27.9 to -1.1) | 3 / 9 / 0 | 0.077 |
| recall | 85.2 (81.0 to 89.8) | 70.0 (62.0 to 80.2) | 15.1 (4.8 to 23.5) | 10 / 2 / 0 | 0.012 |
| f1 | 59.9 (51.7 to 71.1) | 67.1 (56.7 to 77.8) | -7.2 (-17.3 to 6.1) | 4 / 8 / 0 | 0.380 |

### all frequencies, no 30 % rule  (`score_gt2011_min150ms_fullband_ov0.json`)

| | Ours | Silbido | Ours - Silbido | Recordings ours / Silbido better / tie | Wilcoxon p |
|---|---|---|---|---|---|
| precision | 57.6 (48.4 to 73.8) | 71.4 (57.8 to 90.0) | -13.7 (-29.3 to 3.0) | 2 / 10 / 0 | 0.092 |
| recall | 76.6 (71.9 to 81.2) | 72.4 (63.9 to 82.6) | 4.1 (-6.6 to 13.3) | 6 / 6 / 0 | 0.970 |
| f1 | 63.8 (55.1 to 75.1) | 71.6 (59.5 to 85.8) | -7.9 (-20.3 to 5.7) | 3 / 9 / 0 | 0.176 |

### all frequencies, with 30 % rule  (`score_gt2011_min150ms_fullband.json`)

| | Ours | Silbido | Ours - Silbido | Recordings ours / Silbido better / tie | Wilcoxon p |
|---|---|---|---|---|---|
| precision | 48.5 (40.3 to 62.2) | 61.3 (49.6 to 77.4) | -12.7 (-26.6 to 3.1) | 3 / 9 / 0 | 0.129 |
| recall | 74.5 (69.5 to 80.0) | 69.8 (61.3 to 79.9) | 4.8 (-6.5 to 14.6) | 6 / 6 / 0 | 0.910 |
| f1 | 57.3 (49.0 to 68.2) | 65.1 (54.1 to 78.2) | -7.8 (-19.9 to 5.7) | 4 / 8 / 0 | 0.301 |
