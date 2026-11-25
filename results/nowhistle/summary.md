# No-whistle test: false alarms per minute

Both detectors on 2017 beaked whale and sperm whale recordings (no whistling species logged within 15 min; files in `nowhistle_files.csv`). Every detection counts as a false alarm. Range: 95 % bootstrap over encounters (seed 2026). Code commit 25214ab.

| Detector | Rule | Beaked whales | Sperm whales |
|---|---|---|---|
| ridgenet-5-24 | benchmark rule (5-24 kHz, >= 150 ms) | 1.02 /min (0.47 to 1.73); 73 in 71.5 min, 13 encounters | 0.78 /min (0.34 to 1.23); 58 in 74.0 min, 8 encounters |
| ridgenet-5-24 | all tracks the detector outputs | 4.98 /min (3.19 to 7.20); 356 in 71.5 min, 13 encounters | 3.96 /min (1.82 to 5.97); 293 in 74.0 min, 8 encounters |
| ridgenet-v2c | benchmark rule (5-24 kHz, >= 150 ms) | 0.81 /min (0.48 to 1.22); 58 in 71.5 min, 13 encounters | 0.59 /min (0.29 to 0.89); 44 in 74.0 min, 8 encounters |
| ridgenet-v2c | all tracks the detector outputs | 8.86 /min (6.18 to 11.90); 634 in 71.5 min, 13 encounters | 6.39 /min (3.40 to 9.39); 473 in 74.0 min, 8 encounters |
