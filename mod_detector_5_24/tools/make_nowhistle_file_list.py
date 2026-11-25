"""Build the exact file list for the no-whistle test from the pre-chosen encounters (names and checksums only; no audio).

    python mod_detector_5_24/tools/make_nowhistle_file_list.py

Reads mod_detector_5_24/nowhistle_encounters.csv, lists the matching 1-minute files in NOAA's public bucket
(dclde/2022/dclde_2022_1705/audio/, named 1705_YYYYMMDD_HHMMSS_mmm.flac by start time) and writes
mod_detector_5_24/nowhistle_files.csv.

Rule (fixed before any detection was run, 11 Nov 2026):
  * a file belongs to an encounter if its 60 s overlap the encounter's logged UTC start-end at all;
  * beaked whale encounters: all such files;
  * sperm whale encounters: 10 files spread evenly over the encounter (indices round(linspace(0, n-1, 10))), or all
    files if there are 10 or fewer.
"""
from __future__ import annotations

import csv
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
API = "https://storage.googleapis.com/storage/v1/b/noaa-passive-bioacoustic/o"
PREFIX = "dclde/2022/dclde_2022_1705/audio/"
PER_SPERM = 10


def list_hour(hour: datetime) -> list[dict]:
    q = {"prefix": PREFIX, "matchGlob": f"**1705_{hour:%Y%m%d_%H}*.flac", "fields": "items(name,size,md5Hash),nextPageToken"}
    items, token = [], None
    while True:
        url = API + "?" + urllib.parse.urlencode({**q, **({"pageToken": token} if token else {})})
        with urllib.request.urlopen(url, timeout=60) as r:
            d = json.load(r)
        items += d.get("items", [])
        token = d.get("nextPageToken")
        if not token:
            return items


def start_of(name: str) -> datetime:
    stem = name.rsplit("/", 1)[-1]
    return datetime.strptime(stem[5:20], "%Y%m%d_%H%M%S")


def main() -> None:
    enc = list(csv.DictReader(open(HERE / "nowhistle_encounters.csv", encoding="utf-8")))
    cache: dict[datetime, list[dict]] = {}
    rows = []
    for e in enc:
        t0 = datetime.strptime(e["utc_start"], "%Y-%m-%d %H:%M:%S")
        t1 = datetime.strptime(e["utc_end"], "%Y-%m-%d %H:%M:%S")
        hours, h = [], (t0 - timedelta(minutes=1)).replace(minute=0, second=0)
        while h <= t1:
            hours.append(h)
            h += timedelta(hours=1)
        files = []
        for h in hours:
            if h not in cache:
                cache[h] = list_hour(h)
            files += cache[h]
        files = sorted({f["name"]: f for f in files}.values(), key=lambda f: f["name"])
        files = [f for f in files if start_of(f["name"]) < t1 and start_of(f["name"]) + timedelta(seconds=60) > t0]
        if e["group"] == "sperm whale" and len(files) > PER_SPERM:
            files = [files[i] for i in sorted(set(np.round(np.linspace(0, len(files) - 1, PER_SPERM)).astype(int)))]
        for f in files:
            rows.append({"encounter_id": e["encounter_id"], "group": e["group"], "species": e["species"],
                         "file": f["name"].rsplit("/", 1)[-1], "size_bytes": int(f["size"]), "md5_base64": f["md5Hash"]})
        print(f"  encounter {e['encounter_id']:>3s} {e['group']:12s} {e['duration_min']:>5s} min logged -> {len(files)} files")
    with open(HERE / "nowhistle_files.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for g in ("beaked whale", "sperm whale"):
        sel = [r for r in rows if r["group"] == g]
        print(f"{g}: {len(sel)} files ({sum(r['size_bytes'] for r in sel) / 1e9:.1f} GB)")
    print(f"saved {HERE / 'nowhistle_files.csv'} ({len(rows)} files)")


if __name__ == "__main__":
    main()
