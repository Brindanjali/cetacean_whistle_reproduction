# False-alarm sorting guide

Each picture (`pictures/FA001.png`, ...) shows one **false alarm**: a detection that matched no whistle in the experts'
answer key. Your job: say what is really under the red line. You do not know which detector made it (that is on
purpose; the answer key is in `do_not_open_until_done/`, open it only when the whole sheet is filled).

## The picture
- Time runs left to right (seconds in the recording), pitch bottom to top (kHz). Dark = loud.
- **Top panel:** the plain picture. Judge the sound here first, without hints.
- **Bottom panel:** the same picture with lines:
  - **red** = the detection to judge;
  - **green** = whistles the experts marked that count in the score;
  - **yellow dashed** = whistles the experts marked that do not count (too short, too faint, or outside 5-24 kHz);
  - **blue dashed** = the same detector's other detections nearby;
  - grey dotted lines at 5 and 24 kHz = the band that is scored.

## Categories (write the letter in the `category` column)
| Letter | Category | What it looks like |
|---|---|---|
| **W** | Unmarked real whistle | A clear, thin, smooth line that rises, falls or curves, like the marked (green or yellow) whistles nearby, but nothing is marked on it. Not our fault: the answer key missed it |
| **H** | Harmonic, piece or echo of a marked whistle | The red line has the same shape as a marked whistle, but at about 2x or 3x its pitch (harmonic), or it covers part of a marked whistle but sits a little off it, or it is a fainter copy just after it (echo) |
| **T** | Tonal noise | A flat or very regular line that does not look like an animal: a long constant-pitch tone (engine, equipment), or the same short beep repeated at regular intervals (echosounder) |
| **C** | Clicks or burst pulses | Thin vertical stripes (each one a click); many clicks close together can form a ladder or a smeared band, and the red line follows that band |
| **N** | Other noise | Nothing line-like under the red line: random speckle, a smudge, rumble |
| **?** | Can't tell | Use it when you honestly cannot decide; don't force a choice |

If two fit, pick the one that best explains **the red line itself**, and note the other in `notes`.

## The other columns
- `sure`: **y** if you are confident, **n** if it is a guess.
- `notes`: anything useful, e.g. "harmonic of the green whistle at 1.2 s", "clicks everywhere".

## Tips
- About 20-40 seconds per picture is enough; don't overthink. Do it in one or two sittings so your judgement stays the same.
- Look at the top panel first, then use the bottom one to find exactly where the red line is.
- Open `sheet.csv` in Google Sheets (or Excel), fill it in, and save it as CSV again with the same columns.
- The paper will say that one person sorted the pictures, so just be consistent.
