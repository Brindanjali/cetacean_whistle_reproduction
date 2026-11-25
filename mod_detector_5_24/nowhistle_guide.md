# No-whistle test: picture sorting guide

These pictures come from recordings of **beaked whales and sperm whales**, which click but don't whistle, with no
dolphins logged nearby. So each red line is a detection where we expect **no whistle**. Your job: say what is really
under the red line. You don't know which detector made it, or which species was recorded (on purpose; the answer is in
`do_not_open_until_done/`, open it only when the sheet is filled).

## The picture
- Time runs left to right (seconds in the 1-minute file), pitch bottom to top (kHz). Dark = loud.
- **Top panel:** the plain picture. Judge the sound here first.
- **Bottom panel:** the same, with **red** = the detection to judge, **blue dashed** = the same detector's other
  detections nearby, grey dotted lines at 5 and 24 kHz. There is no answer key here, so there are no green lines.

## Categories (write the letter in the `category` column)
| Letter | Category | What it looks like |
|---|---|---|
| **W** | Real whistle | A clear, thin, smooth line that rises, falls or curves, like a dolphin whistle. It means a whistling animal was audible after all; note it, it's useful to know |
| **T** | Tonal noise | A flat or very regular line that doesn't look like an animal: a long constant tone (engine, equipment) or the same short beep repeated regularly (echosounder) |
| **C** | Clicks or burst pulses | Thin vertical stripes (clicks); many clicks close together can form a ladder or smeared band, and the red line follows it |
| **N** | Other noise | Nothing line-like under the red line: speckle, a smudge, rumble |
| **?** | Can't tell | When you honestly cannot decide |

(H is not used here: there are no marked whistles to be a piece of. A piece of a real whistle counts as **W**.)

## The other columns
- `sure`: **y** if you are confident, **n** if it is a guess (you may leave it empty for **?**).
- `notes`: anything useful, e.g. "clicks everywhere", "looks like a faint dolphin whistle".

## Tips
- 20-40 seconds per picture is enough; do them in one sitting if you can, so your judgement stays the same.
- Open `sheet.csv` in Google Sheets, fill it in, then File, Download, CSV.
