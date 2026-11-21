"""How WhistleCode's narrowband SNR relates to the in-band SNR most published schemes quote (RELATED_WORK.md section 3).

WhistleCode's SNR is narrowband: the peak |STFT| of the quietest data whistle, as a tone in its own 93.75 Hz bin, against the
MEDIAN noise |STFT| in that bin (wcode/channel.py, amplitude_for_snr; through_channel takes the median amplitude over the
sender's pitch pool). The in-band SNR used here instead compares that whistle's power, A^2 / 2, with the MEAN power of all the
noise in WhistleCode's band.

[DECISION] Band 2.5-14.5 kHz: every codebook whistle stays inside it (centre 5-12 kHz, span at most 5 kHz). Band-pass:
8th-order Butterworth, zero-phase (second-order sections). The level window is the channel's own (channel.level_window_s,
60 s from the start of each noise file), and the pitches are the sender's pitch pool, as in through_channel().

For each noise file it prints the offset in dB: narrowband SNR minus in-band SNR. A message at narrowband SNR S therefore sits
at about S - offset in-band. Clicks and real whistles in the recordings raise the mean noise power but hardly the median bin
level, so the offset varies a lot between files.

    python whistlecode/experiments/snr_inband.py [--encounters 214 276] [--files 12]

Results: whistlecode/outputs/snr_inband/results.json (gitignored).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import signal

WC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WC))

from wcode import channel, schedule  # noqa: E402
from wcode.config import PROJECT_ROOT, default_config  # noqa: E402

BAND_HZ = (2500.0, 14500.0)
FILTER_ORDER = 8


def offset_db(x: np.ndarray, fs: int, pitches_hz: np.ndarray, cfg: dict) -> float:
    """Narrowband SNR minus in-band SNR for one noise recording, as through_channel() would set the gain."""
    c = cfg["channel"]
    window = x[:int(float(c["level_window_s"]) * fs)].astype(np.float64)
    levels = channel.bin_levels(window, fs, float(c["snr_bin_hz"]))
    amp = float(np.median([channel.amplitude_for_snr(0.0, float(f), levels, fs, cfg)
                           for f in np.quantile(pitches_hz, np.linspace(0.02, 0.98, 25))]))   # tone at narrowband SNR 0 dB
    sos = signal.butter(FILTER_ORDER, BAND_HZ, btype="bandpass", fs=fs, output="sos")
    noise_power = float(np.mean(signal.sosfiltfilt(sos, window) ** 2))
    return 10 * np.log10(noise_power / (amp ** 2 / 2))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--encounters", type=int, nargs="+", default=[214, 276])
    ap.add_argument("--files", type=int, default=12, help="noise files per encounter, spread evenly over the encounter")
    a = ap.parse_args()
    cfg = default_config()
    fs = int(cfg["synth"]["fs_hz"])
    pool = schedule.pitch_pool(cfg)
    out = {"band_hz": BAND_HZ, "filter_order": FILTER_ORDER, "level_window_s": float(cfg["channel"]["level_window_s"]),
           "pitch_pool_median_hz": float(np.median(pool)), "encounters": {}}
    for enc in a.encounters:
        files = channel.noise_files(enc)
        files = files[::max(1, len(files) // a.files)][:a.files]
        per_file = {p.stem: round(offset_db(channel.load_noise(p, cfg), fs, pool, cfg), 2) for p in files}
        v = np.array(list(per_file.values()))
        out["encounters"][str(enc)] = {"files": len(v), "median_db": round(float(np.median(v)), 1),
                                       "min_db": round(float(v.min()), 1), "max_db": round(float(v.max()), 1),
                                       "per_file_db": per_file}
        print(f"encounter {enc}: narrowband minus in-band SNR, median {np.median(v):.1f} dB over {len(v)} files "
              f"(range {v.min():.1f} to {v.max():.1f} dB)")
    print(f"for reference, flat noise would give {10 * np.log10((BAND_HZ[1] - BAND_HZ[0]) / float(cfg['channel']['snr_bin_hz'])):.1f} dB "
          f"(signal against the noise of one 93.75 Hz bin vs the whole band), before the median-vs-mean difference of about 1.6 dB")
    dest = PROJECT_ROOT / "whistlecode" / "outputs" / "snr_inband"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "results.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("results:", dest / "results.json")


if __name__ == "__main__":
    main()
