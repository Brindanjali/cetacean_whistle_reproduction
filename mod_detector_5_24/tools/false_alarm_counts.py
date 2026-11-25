"""Count the sorted false alarms (step 3): which kinds of false alarm does each detector make?

    python mod_detector_5_24/tools/false_alarm_counts.py --sheet PATH/sheet.csv --key PATH/key.csv [--out DIR]
                                                         [--test dclde2011|nowhistle]

sheet.csv: filled in by hand (id, category, sure, notes), see mod_detector_5_24/false_alarm_guide.md. An empty 'sure'
           is accepted only on '?' (can't tell) rows and counted as n.
key.csv:   from colab_false_alarm_clips.py (do_not_open_until_done/key.csv): which detector and recording each id is.
Writes <out>/counts.md and counts.json (default results/false_alarms/). Only counts what was sorted: the shares describe
the sampled false alarms (up to 20 per detector per recording), not every false alarm.
--test nowhistle: the same counts for colab_nowhistle_test.py's pictures (its key.csv has the same columns); only the
title and wording change (10 per detector per group, from detections that pass the benchmark rule).
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CATS = {"W": "unmarked real whistle", "H": "harmonic, piece or echo", "T": "tonal noise", "C": "clicks or burst pulses",
        "N": "other noise", "?": "can't tell"}


def table(rows, group_key):
    groups = sorted({group_key(r) for r in rows})
    lines = ["| | " + " | ".join(groups) + " |", "|---|" + "---|" * len(groups)]
    out = {}
    for g in groups:
        sel = [r for r in rows if group_key(r) == g]
        c = Counter(r["category"] for r in sel)
        out[g] = {"n": len(sel), "counts": {k: c.get(k, 0) for k in CATS},
                  "n_sure": sum(r["sure"] == "y" for r in sel)}
    for k, name in CATS.items():
        lines.append(f"| {k} {name} | " + " | ".join(
            f"{out[g]['counts'][k]} ({100 * out[g]['counts'][k] / out[g]['n']:.0f} %)" for g in groups) + " |")
    lines.append("| total (sure) | " + " | ".join(f"{out[g]['n']} ({out[g]['n_sure']})" for g in groups) + " |")
    return lines, out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", required=True, type=Path)
    ap.add_argument("--key", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "results" / "false_alarms")
    ap.add_argument("--test", choices=("dclde2011", "nowhistle"), default="dclde2011")
    ap.add_argument("--earlier-sheet", type=Path, help="for keys with a repeat_of column: the sheet those ids come from")
    a = ap.parse_args()
    with open(a.sheet, newline="", encoding="utf-8-sig") as fh:
        sheet = {r["id"].strip(): r for r in csv.DictReader(fh)}
    with open(a.key, newline="", encoding="utf-8-sig") as fh:
        key = {r["id"]: r for r in csv.DictReader(fh)}
    if set(sheet) != set(key):
        raise SystemExit(f"sheet and key ids differ: only in sheet {sorted(set(sheet) - set(key))}, "
                         f"only in key {sorted(set(key) - set(sheet))}")
    rows, problems = [], []
    for i in sorted(key):
        cat = sheet[i]["category"].strip().upper()
        sure = sheet[i]["sure"].strip().lower()
        if cat == "?" and sure == "":
            sure = "n"   # "can't tell" already means not sure; an empty 'sure' there counts as n
        if cat not in CATS:
            problems.append(f"{i}: category '{sheet[i]['category']}' (use one of {' '.join(CATS)})")
        if sure not in ("y", "n"):
            problems.append(f"{i}: sure '{sheet[i]['sure']}' (use y or n)")
        rows.append({**key[i], "category": cat, "sure": sure, "notes": sheet[i]["notes"]})
    if problems:
        raise SystemExit("fix these rows in the sheet first:\n  " + "\n  ".join(problems))
    if a.test == "nowhistle":
        CATS["W"] = "real whistle (unlogged whistler)"
        head = ["# False-alarm categories (no-whistle test, benchmark rule)", "",
                f"{len(rows)} sampled detections from beaked and sperm whale recordings with no whistling species logged "
                "(10 per detector per group, from detections that pass the benchmark rule: 5-24 kHz, >= 150 ms), sorted "
                "blind by one person (detector and species hidden). Shares describe the sample, not all detections. "
                "Made by `mod_detector_5_24/tools/false_alarm_counts.py --test nowhistle`."]
        if any(r.get("repeat_of") for r in rows):
            head[-1] = head[-1].replace("sorted blind", "sorted blind on a later day")
    else:
        head = ["# False-alarm categories (DCLDE 2011, main scoring)", "",
                f"{len(rows)} sampled false alarms, sorted blind by one person (method hidden). Shares describe the sample "
                "(up to 20 per detector per recording), not all false alarms. Made by "
                "`mod_detector_5_24/tools/false_alarm_counts.py`."]
    repeats = [r for r in rows if r.get("repeat_of")]
    if repeats:   # colab_silbido_pictures.py: some pictures are earlier ones shown again
        head.append(f"Of these, {len(repeats)} are pictures sorted earlier, shown again under new ids (method "
                    "'... (repeat)'); see the consistency section at the end.")
    md = head + ["", "## By detector", ""]
    lines, by_method = table(rows, lambda r: r["method"])
    md += lines + ["", "## By detector and recording", ""]
    lines, by_rec = table(rows, lambda r: f"{r['method']}: {r['recording'][:24]}")
    md += lines + [""]
    consistency = None
    if repeats:
        if a.earlier_sheet is None:
            raise SystemExit("this key has repeated pictures: give the earlier sheet with --earlier-sheet")
        with open(a.earlier_sheet, newline="", encoding="utf-8-sig") as fh:
            earlier = {r["id"].strip(): r for r in csv.DictReader(fh)}
        pairs = [(r["id"], r["repeat_of"], earlier[r["repeat_of"]]["category"].strip().upper(),
                  earlier[r["repeat_of"]]["sure"].strip().lower(), r["category"], r["sure"]) for r in repeats]
        same = sum(p[2] == p[4] for p in pairs)
        same_w = sum((p[2] == "W") == (p[4] == "W") for p in pairs)
        md += ["## Consistency: the same pictures sorted twice", "",
               f"Same category both times: **{same} of {len(pairs)}**; same answer to 'real whistle or not' (W or "
               f"not W): **{same_w} of {len(pairs)}**.", "", "| New id | Earlier id | Earlier (sure) | Now (sure) |",
               "|---|---|---|---|"]
        md += [f"| {p[0]} | {p[1]} | {p[2]} ({p[3]}) | {p[4]} ({p[5]}) |" for p in pairs] + [""]
        consistency = {"same_category": same, "same_whistle_or_not": same_w, "n": len(pairs),
                       "pairs": [dict(zip(("id", "repeat_of", "earlier", "earlier_sure", "now", "now_sure"), p))
                                 for p in pairs]}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "counts.md").write_text("\n".join(md), encoding="utf-8")
    out = {"categories": CATS, "by_method": by_method, "by_method_and_recording": by_rec}
    if consistency is not None:
        out["consistency"] = consistency
    (a.out / "counts.json").write_text(json.dumps(out, indent=2))
    print("\n".join(md))
    print(f"saved {a.out / 'counts.md'} and {a.out / 'counts.json'}")


if __name__ == "__main__":
    main()
