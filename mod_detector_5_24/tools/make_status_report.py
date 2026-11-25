"""Build the whistle detector status report as a PDF (for the project mentor)."""
import sys
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, ListFlowable, ListItem, PageTemplate, Paragraph,
                                Spacer, Table, TableStyle)

OUT = sys.argv[1]
F = "C:/Windows/Fonts/"
pdfmetrics.registerFont(TTFont("Body", F + "calibri.ttf"))
pdfmetrics.registerFont(TTFont("Body-Bold", F + "calibrib.ttf"))
pdfmetrics.registerFont(TTFont("Head", F + "georgia.ttf"))
pdfmetrics.registerFont(TTFont("Head-Bold", F + "georgiab.ttf"))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body", boldItalic="Body-Bold")

INK = colors.HexColor("#17262b")
MUTED = colors.HexColor("#52666d")
ACCENT = colors.HexColor("#0b5c68")
LINE = colors.HexColor("#c6d3d6")
BAND = colors.HexColor("#eef3f4")
WIN = colors.HexColor("#dcecee")

body = ParagraphStyle("body", fontName="Body", fontSize=10.5, leading=14.5, textColor=INK, spaceAfter=6)
small = ParagraphStyle("small", parent=body, fontSize=9, leading=12, textColor=MUTED, spaceAfter=6)
title = ParagraphStyle("title", fontName="Head-Bold", fontSize=24, leading=29, textColor=INK, spaceAfter=4)
subtitle = ParagraphStyle("subtitle", parent=body, fontSize=12, leading=16, textColor=MUTED, spaceAfter=14)
h1 = ParagraphStyle("h1", fontName="Head-Bold", fontSize=14.5, leading=18, textColor=ACCENT, spaceBefore=15, spaceAfter=7, keepWithNext=1)
h2 = ParagraphStyle("h2", fontName="Body-Bold", fontSize=11.5, leading=15, textColor=INK, spaceBefore=9, spaceAfter=4, keepWithNext=1)
cell = ParagraphStyle("cell", fontName="Body", fontSize=9.3, leading=11.8, textColor=INK)
cellc = ParagraphStyle("cellc", parent=cell, alignment=TA_CENTER)
hdr = ParagraphStyle("hdr", fontName="Body-Bold", fontSize=9.3, leading=11.8, textColor=colors.white)
hdrc = ParagraphStyle("hdrc", parent=hdr, alignment=TA_CENTER)
W = A4[0] - 4.2 * cm


def P(t, s=body):
    return Paragraph(t, s)


def bullets(items, numbered=False, start=1):
    kw = dict(bulletType="1", start=start, bulletFontName="Body", bulletFontSize=10) if numbered else dict(bulletType="bullet", start="•", bulletFontSize=9)
    return ListFlowable([ListItem(P(i, ParagraphStyle("li", parent=body, spaceAfter=3)), leftIndent=15) for i in items], leftIndent=15, **kw)


def table(rows, widths, center_from=1, wins=(), extra=(), header_rows=1):
    data = []
    for r, row in enumerate(rows):
        out = []
        for c, v in enumerate(row):
            if r < header_rows:
                out.append(P(v, hdrc if c >= center_from else hdr))
            else:
                out.append(P(v, cellc if c >= center_from else cell))
        data.append(out)
    total = sum(widths)
    t = Table(data, colWidths=[w / total * W for w in widths], repeatRows=header_rows)
    st = [("BACKGROUND", (0, 0), (-1, header_rows - 1), ACCENT), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 3.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.6),
          ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
          ("LINEBELOW", (0, header_rows), (-1, -1), 0.4, LINE), ("LINEBELOW", (0, -1), (-1, -1), 0.8, MUTED)]
    for r in range(header_rows, len(rows)):
        if (r - header_rows) % 2:
            st.append(("BACKGROUND", (0, r), (-1, r), BAND))
    for (r, c) in wins:
        st.append(("BACKGROUND", (c, r), (c, r), WIN))
    st.extend(extra)
    t.setStyle(TableStyle(st))
    return t


def gap(h=8):
    return Spacer(1, h)


s = []
s += [P("Whistle Detector Project", title), P("Status report for mentor review &nbsp;|&nbsp; Parjanya &nbsp;|&nbsp; 5 November 2026", subtitle)]

# ---------------------------------------------------------------- summary
s += [P("1. Summary", h1),
      P("We built a small whistle detector because the detector used in the paper we are reproducing (Park et al., VAE-GMM) was not available. "
        "We tested a 5–24 kHz version on 12 expert-labelled real recordings from DCLDE 2011 and compared it with Silbido, the standard older method, under the same rules.")]
s.append(table([
    ["12 recordings, 5–24 kHz, recommended scoring", "Precision", "Recall", "F1"],
    ["Silbido", "<b>76.4</b>", "72.9", "<b>74.6</b>"],
    ["Our detector (RidgeNet + tracker)", "56.3", "<b>86.9</b>", "67.1"]], [6, 1.2, 1.2, 1.2], wins=[(1, 1), (2, 2), (1, 3)]))
s += [gap(), bullets([
    "<b>Main finding:</b> our detector finds more whistles, but raises more false alarms, so Silbido scores higher overall.",
    "<b>Fair claim:</b> a very small network (14,209 parameters), trained only on synthetic whistles and never on DCLDE data, has higher recall than Silbido and follows whistles more closely. Precision is its clear limitation.",
    "<b>Main gap:</b> the 2–24 kHz version used for the VAE-GMM dataset has never been scored on labelled real recordings.",
    "<b>Guidance needed:</b> whether to publish now or improve precision first, which score to use as the main result, and whether hand-labelling can stay as future work. Questions are in Section 15.",
])]

# ---------------------------------------------------------------- why
s += [P("2. Why this work was done", h1), bullets([
    "The main project reproduces Park et al.'s VAE-GMM whistle paper.",
    "That paper relies on a detector and tracker we could not obtain, so we built replacements.",
    "We decided to write a short paper (2–4 pages) about the detector.",
    "A paper needs real-data evidence and a fair comparison, which is what most of this work produced.",
], numbered=True)]

s += [P("3. Terms used", h1), table([
    ["Term", "Meaning"],
    ["Spectrogram", "A picture of sound, with time across and pitch going up. A whistle looks like a thin bright curved line."],
    ["Detection", "A whistle reported by a program."],
    ["Answer key", "Whistles marked by human experts."],
    ["Precision", "Of everything the program reported, how much was real."],
    ["Recall", "Of the real whistles, how many the program found."],
    ["F1", "One score combining precision and recall."],
    ["Pitch error", "How far a detection is from the marked pitch, in Hz. Lower is better."],
    ["Coverage", "How much of each found whistle was covered. Higher is better."],
    ["Fragmentation", "How many pieces one whistle is split into. 1.0 is ideal."],
    ["Benchmark / baseline", "The benchmark is the test itself. The baseline is the established method compared against."],
], [1.5, 6], center_from=9)]

# ---------------------------------------------------------------- detector
s += [P("4. How our detector works", h1), table([
    ["Stage", "What it does"],
    ["S1", "Picks one channel from the recording."],
    ["S2", "Resamples 500 kHz audio to 192 kHz."],
    ["S3", "Removes sound below 2 kHz."],
    ["S4", "Makes the spectrogram (93.75 Hz by 5.33 ms per cell)."],
    ["S5", "<b>RidgeNet</b>, a small neural network, marks whistle-like points (14,209 parameters)."],
    ["S6", "<b>Tracker</b>, which links points into whistles and rejects short, weak, duplicate and harmonic tracks."],
], [1, 8], center_from=9), gap(),
    P("<b>Training:</b> synthetic whistles are mixed into real ocean background noise, with no human labels. The noise comes from 56 recordings of encounter 191 (24 train, 16 validation, 16 test). "
      "Parts of the noise that probably contain real whistles are ignored during training (the background-label fix).")]

s += [P("5. Datasets", h1), table([
    ["Dataset", "Contents", "Used for", "Labels"],
    ["DCLDE 2022 (2017 Hawaiian survey)", "60 s files, 500 kHz, 6 channels; 8 false killer whale encounters", "VAE-GMM dataset and training noise", "Encounter times and species only, no individual whistles"],
    ["DCLDE 2011", "192 kHz mono; Li et al. (2023) test set of 12 recordings, 43.2 min, 6,011 marked whistles", "Real-data benchmark", "Individual whistles, marked 5–50 kHz"],
], [2.2, 3.4, 2, 2.6], center_from=9), gap(),
    P("The 12 recordings cover 4 species with 3 recordings each: bottlenose dolphin, long-beaked common dolphin, melon-headed whale and spinner dolphin. "
      "No public whistle-level labels were found for the 2017 recordings.")]

s += [P("6. Two versions of the detector", h1), table([
    ["", "v2c", "ridgenet-5-24"],
    ["Band", "2–24 kHz", "5–24 kHz"],
    ["Purpose", "VAE-GMM dataset", "DCLDE 2011 benchmark"],
    ["Threshold", "0.5", "0.4 (calibrated on synthetic validation data)"],
    ["Trained on", "RTX 5060 laptop GPU, about 65 min", "Free Colab T4, about 1 h 41 min"],
    ["Best validation node F1", "0.695", "0.559 (different validation set, not comparable)"],
], [2, 3, 4]), gap(), bullets([
    "<b>Why 2 kHz:</b> the paper's filter setting.",
    "<b>Why 24 kHz:</b> our decision, because the paper gives no upper limit. It covers the range shown in the paper's Figure 3.",
    "<b>Why 5 kHz in the second version:</b> DCLDE's answer key marks nothing below 5 kHz, so detections down there would wrongly count as false alarms.",
])]

# ---------------------------------------------------------------- synthetic
s += [P("7. Results on synthetic whistles", h1),
      P("These tests use fake whistles at known positions. They measure recall, not real-world accuracy. Improving the original detector (v1 to v2c, paired test) raised recall from 0.704 to 0.729, and at 5–10 dB from 0.519 to 0.647 (McNemar p = 0.044)."),
      table([
          ["Loudness (SNR)", "v2c", "ridgenet-5-24"],
          ["−5 to 5 dB", "0.051", "0.086"], ["5 to 10 dB", "0.647", "0.632"],
          ["10 to 15 dB", "0.905", "0.885"], ["15 to 40 dB", "0.966", "0.980"],
          ["<b>Overall</b>", "<b>0.729</b>", "<b>0.629</b>"]], [3, 2, 2]), gap(),
      P("The two are nearly equal at each loudness. The overall gap comes from the test mix: 66% of the 5–24 kHz test whistles are below 10 dB, against 43% for v2c. Rescored on v2c's mix, the new model also gets 0.729. The test sets differ, so this is not a paired comparison."),
      P("<b>Other v2c checks on unlabelled real data:</b> engineering checks and visual inspection passed. Inspection did find one artefact, a burst of near-identical short tracks, which led to a tracker fix. "
        "On 8 real files, v2c finds 99.4–99.8% of the same whistles at lower sample rates. That shows consistency, not accuracy.")]

# ---------------------------------------------------------------- scoring
s += [P("8. How real-data scoring works", h1),
      P("Silbido's scoring was rebuilt in Python (<font name='Body-Bold'>dclde2011.py</font>) with Li et al.'s rules and checked: the answer key scored against itself gets about 100, and damaged copies are rejected."),
      P("A marked whistle counts only if", h2), bullets([
          "it lasts at least 150 ms;", "it is above 10 dB over at least a third of its length;",
          "it is entirely inside 5–24 kHz (our band limit)."]),
      gap(4),
      P("That leaves <b>1,516 of 6,011</b> whistles. Counting all frequencies gives 1,860; Li et al. expected 1,935, so ours is about 4% lower."),
      P("A detection matches a whistle if", h2), bullets([
          "its average pitch difference is at most 350 Hz;", "it covers more than 30% of the whistle (the optional 30% rule; see Section 11)."]),
      P("Other rules", h2), bullets([
          "Detections matching only uncounted whistles count neither for nor against.",
          "Results are calculated per species, then averaged.",
          "In 5–24 kHz scoring, detections mostly outside the band are dropped, so Silbido is not penalised for searching higher."]),
      P("Benchmark settings for our detector", h2), bullets([
          "<b>Harmonics kept</b>, because DCLDE marks them as whistles.",
          "<b>150 ms minimum detection length</b>, because that is Silbido's default.",
          "Both were chosen after seeing test results, so the paper must say so and report other settings too."])]

s += [P("9. The Silbido baseline", h1),
      P("Silbido (Roch et al. 2011) finds points 10 dB above the noise, connects them with a graph search, and keeps whistles of at least 150 ms. "
        "A colleague ran the original Silbido 3.0, classic graph search with default settings, in MATLAB R2024b on a Mac. Processing took about 90 seconds for all 12 recordings and found 2,546 whistles. "
        "Running it again gave identical results on the recordings compared.")]

# ---------------------------------------------------------------- comparison
s += [P("10. Final comparison (12 recordings)", h1), P("Overall, 5–24 kHz", h2), table([
    ["Rule", "Method", "Precision", "Recall", "F1", "Pitch error", "Coverage", "Fragm."],
    ["No 30% rule (recommended main)", "Silbido", "<b>76.4</b>", "72.9", "<b>74.6</b>", "100 Hz", "80.7%", "<b>1.25</b>"],
    ["", "Our detector", "56.3", "<b>86.9</b>", "67.1", "<b>94 Hz</b>", "<b>86.6%</b>", "1.30"],
    ["With 30% rule", "Silbido", "<b>64.5</b>", "70.0", "<b>67.1</b>", "100 Hz", "80.6%", "<b>1.11</b>"],
    ["", "Our detector", "47.1", "<b>85.2</b>", "59.9", "<b>93 Hz</b>", "<b>85.5%</b>", "1.14"],
], [2.6, 1.7, 1.1, 1, 0.9, 1.1, 1.1, 0.9], center_from=2, extra=[("SPAN", (0, 1), (0, 2)), ("SPAN", (0, 3), (0, 4))],
    wins=[(1, 2), (1, 4), (1, 7), (2, 3), (2, 5), (2, 6), (3, 2), (3, 4), (3, 7), (4, 3), (4, 5), (4, 6)])]

species = lambda rows: table(rows, [2.4, 1, 1, 1, 1, 1, 1], extra=[("SPAN", (1, 0), (3, 0)), ("SPAN", (4, 0), (6, 0))], header_rows=2)
s += [P("By species, no 30% rule", h2), species([
    ["Species", "Silbido", "", "", "Our detector", "", ""], ["", "P", "R", "F1", "P", "R", "F1"],
    ["Bottlenose", "89.6", "82.9", "<b>86.1</b>", "65.3", "86.4", "74.4"],
    ["Common", "58.4", "51.3", "54.6", "45.0", "87.0", "<b>59.3</b>"],
    ["Melon-headed", "71.3", "72.8", "<b>72.0</b>", "38.5", "87.6", "53.5"],
    ["Spinner", "86.4", "84.8", "<b>85.6</b>", "76.2", "86.7", "81.1"],
    ["<b>Average</b>", "<b>76.4</b>", "<b>72.9</b>", "<b>74.6</b>", "<b>56.3</b>", "<b>86.9</b>", "<b>67.1</b>"]])]
s += [P("By species, with 30% rule", h2), species([
    ["Species", "Silbido", "", "", "Our detector", "", ""], ["", "P", "R", "F1", "P", "R", "F1"],
    ["Bottlenose", "71.2", "77.5", "<b>74.2</b>", "53.6", "83.3", "65.2"],
    ["Common", "50.7", "49.9", "50.3", "39.6", "86.2", "<b>54.2</b>"],
    ["Melon-headed", "66.1", "71.0", "<b>68.5</b>", "34.8", "87.3", "49.8"],
    ["Spinner", "70.1", "81.7", "<b>75.5</b>", "60.5", "83.9", "70.3"],
    ["<b>Average</b>", "<b>64.5</b>", "<b>70.0</b>", "<b>67.1</b>", "<b>47.1</b>", "<b>85.2</b>", "<b>59.9</b>"]])]

rec = [
    ["Bottlenose <font color='#52666d'>Qx-Tt-SCI0608</font>", "56 / 152", "74.4", "85.7", "<b>79.7</b>", "35.0", "85.7", "49.7"],
    ["Bottlenose <font color='#52666d'>...205305</font>", "99 / 539", "97.1", "83.8", "<b>90.0</b>", "86.4", "81.8", "84.1"],
    ["Bottlenose <font color='#52666d'>...205730</font>", "103 / 336", "93.9", "80.6", "86.7", "89.1", "91.3", "<b>90.2</b>"],
    ["Common <font color='#52666d'>Qx-Dc-CC0411</font>", "287 / 759", "26.4", "21.3", "23.5", "35.4", "81.2", "<b>49.3</b>"],
    ["Common <font color='#52666d'>QX-Dc-FLIP0610</font>", "219 / 533", "93.2", "89.5", "<b>91.3</b>", "65.3", "94.1", "77.1"],
    ["Common <font color='#52666d'>Qx-Dc-SC03</font>", "9 / 135", "90.9", "77.8", "<b>83.8</b>", "57.1", "100", "72.7"],
    ["Melon <font color='#52666d'>...032342</font>", "54 / 202", "34.1", "70.4", "46.0", "62.5", "94.4", "<b>75.2</b>"],
    ["Melon <font color='#52666d'>...204327_4</font>", "153 / 601", "94.0", "75.2", "<b>83.5</b>", "71.2", "83.7", "76.9"],
    ["Melon <font color='#52666d'>...023000</font>", "76 / 1,067", "89.4", "69.7", "<b>78.4</b>", "18.0", "90.8", "30.1"],
    ["Spinner <font color='#52666d'>...224737</font>", "237 / 734", "91.6", "86.5", "<b>89.0</b>", "77.0", "92.4", "84.0"],
    ["Spinner <font color='#52666d'>...213127_4</font>", "112 / 553", "76.1", "85.7", "<b>80.6</b>", "68.2", "77.7", "72.6"],
    ["Spinner <font color='#52666d'>...232000</font>", "111 / 400", "88.6", "80.2", "84.2", "84.6", "83.8", "84.2"],
]
s += [P("By recording, no 30% rule, 5–24 kHz", h2), table(
    [["Recording", "Counted / marked", "Silbido", "", "", "Our detector", "", ""], ["", "", "P", "R", "F1", "P", "R", "F1"]] + rec,
    [3.5, 1.5, .8, .8, .8, .8, .8, .8], extra=[("SPAN", (2, 0), (4, 0)), ("SPAN", (5, 0), (7, 0)), ("SPAN", (1, 0), (1, 1)), ("SPAN", (0, 0), (0, 1))], header_rows=2), gap(),
    P("F1 wins: Silbido 8, our detector 3, tie 1. Our detector has higher recall on 9 recordings (1 tie), and Silbido has higher precision on 10.")]

s.append(KeepTogether([P("Our detector under other settings", h2), table([
    ["Setting", "Precision", "Recall", "F1"],
    ["Main settings, with 30% rule", "47.1", "85.2", "59.9"],
    ["No 150 ms minimum, with 30% rule", "25.6", "93.3", "39.3"],
    ["2025 revised answer key, with 30% rule", "47.9", "85.2", "60.5"],
    ["Harmonics removed, with 30% rule", "46.5", "79.2", "57.9"],
    ["No 30% rule", "56.3", "86.9", "67.1"],
    ["All frequencies, with 30% rule", "48.5", "74.5", "57.3"],
    ["All frequencies, no 30% rule", "57.6", "76.6", "63.8"]], [5, 1, 1, 1])]))
s.append(KeepTogether([P("Silbido over all frequencies", h2), table([
    ["Rule", "Precision", "Recall", "F1"], ["With 30% rule", "61.3", "69.8", "65.1"], ["No 30% rule", "71.4", "72.4", "71.6"]], [5, 1, 1, 1])]))
s.append(KeepTogether([P("Published numbers from Li et al. (2023), 5–50 kHz, context only", h2), table([
    ["Method", "Precision", "Recall", "F1"], ["Their best CNN", "88.78", "85.78", "87.20"],
    ["SMC-PHD (a tracking method)", "76.55", "92.45", "83.40"], ["Silbido graph search", "81.13", "72.28", "75.95"]], [5, 1, 1, 1])]))

# ---------------------------------------------------------------- check
s += [P("11. Checking our Silbido run against Li et al.", h1), table([
    ["Silbido, all frequencies, no 30% rule", "Precision", "Recall", "F1", "Pitch error", "Coverage", "Fragm."],
    ["Our run", "71.4", "72.4", "71.6", "101 Hz", "80.5%", "1.23"], ["Li et al.", "81.13", "72.28", "75.95", "101 Hz", "81.05%", "1.23"]],
    [3.3, 1, 1, 1, 1.1, 1.1, 1]), gap(), table([
        ["Species precision", "Our run", "Li et al."], ["Bottlenose", "89.2", "92.3"], ["Spinner", "87.3", "90.1"],
        ["Common", "53.0", "75.4"], ["Melon-headed", "55.9", "about 66.7 (calculated from their averages)"]], [2.5, 1.2, 4]), gap(), bullets([
            "Everything matches closely except precision in two species, so the run and scorer look correct.",
            "With the 30% rule on, fragmentation is 1.10, far from their 1.23. Their published scores therefore do not seem to apply the rule the way their text describes. Silbido's scoring code has no such rule.",
            "The precision gap in common dolphins and melon-headed whales is unexplained and must be disclosed.",
        ])]

s += [P("12. Corrections made during the work", h1), bullets([
    "<b>Test set size:</b> an earlier run used 9 recordings because Li et al.'s Table III lists some files twice. Their real set is 12, confirmed from their durations and whistle totals. All 12 are now used.",
    "<b>Earlier tie:</b> on 9 recordings, F1 was 66.5 against 65.2 with the 30% rule. The 12-recording result replaces it.",
    "<b>30% rule:</b> first treated as settled, it is now reported both ways because of the evidence in Section 11.",
    "<b>Band rule:</b> detections mostly outside 5–24 kHz are now dropped. Our detector's scores did not change.",
])]

# ---------------------------------------------------------------- gaps
s += [P("13. Known gaps and limitations", h1), table([
    ["Gap", "Why it matters", "Status"],
    ["v2c (2–24 kHz) has no real-data accuracy score", "It built the VAE-GMM dataset, and DCLDE numbers cannot be transferred to it", "Proposed as future work; needs mentor decision"],
    ["Low precision", "The main weakness against Silbido", "Cause not investigated"],
    ["...023000 precision of 18%", "One recording drags melon-headed down", "Cause unknown; about 400 false alarms"],
    ["Qx-Tt-SCI0608 and Qx-Dc-CC0411 weak", "Low precision for our detector", "Echosounders may explain CC0411; unconfirmed"],
    ["Silbido weak on CC0411 and ...032342", "Low recall on CC0411 and low precision on both shape the comparison", "Cause unknown"],
    ["Precision gap with Li et al.", "Common and melon-headed do not match their Silbido numbers", "Unexplained; must be disclosed"],
    ["24 kHz upper limit", "344 of 1,860 otherwise-counted whistles (18%) are not entirely in band", "A 5–50 kHz version could address this"],
    ["Small test set", "12 recordings; only 9 whistles count in Qx-Dc-SC03", "No significance test yet"],
    ["Settings chosen after seeing results", "Harmonics and the 150 ms minimum", "State openly; report other settings"],
    ["Answer key is imperfect", "Annotators skipped many short whistles, so some false alarms may be real", "Not measured"],
    ["Different test conditions", "Li et al.'s best result is over 5–50 kHz", "Context only"],
], [3, 4, 3], center_from=9)]

s += [P("14. What is done and what is left", h1), P("Done", h2), bullets([
    "Detector versions built and trained; synthetic tests complete.", "Scoring tool built and checked.",
    "Silbido run on all 12 recordings; full comparison and check against Li et al. complete."]),
    P("Needed for the detector paper", h2), bullets([
        "Copy the score files from Google Drive into the project.",
        "Commit the current code, Silbido script and results, then update the pull request.",
        "Plot spectrograms of false alarms on our 3 weak recordings and Silbido's 2 weakest.",
        "Run a no-whistle test: measure false alarms during beaked whale and sperm whale encounters, excluding mixed-species groups.",
        "Add a significance test or confidence ranges across recordings.",
        "Make figures and write the 2–4 page paper."], numbered=True),
    P("Depends on mentor advice", h2), bullets([
        "Tuning for better precision, using annotated DCLDE recordings outside the 12 test files.",
        "Training a 5–50 kHz version.",
        "Checking a sample of about 200 detections from 2017 recordings by hand, for a real precision estimate.",
        "Hand-labelling 2017 recordings now instead of later.",
        "Asking Marie Roch's group how the 30% rule was applied.",
        "Emailing Pina Gruden's group about any whistle-level labels for the 2017 data.",
        "Adding Silbido's deep-learning version as a further comparison."])]

# ---------------------------------------------------------------- questions
q = [("Paper goal", [
        "Is this result worth publishing as it stands (higher recall, but lower precision and F1 than Silbido), or should we improve the detector first?",
        "Where should we submit, and what evidence will that venue expect?",
        "Does this framing work: a very small detector trained only on synthetic whistles finds more whistles on unseen species, with precision as the limitation?"]),
     ("Scoring", [
        "Which should be the main score: no 30% rule (matches Li et al.'s published Silbido numbers) or with it (matches their text)? Should we report both?",
        "Should we contact Marie Roch's group about the rule and the remaining precision gap?",
        "Are we comfortable with harmonics kept and the 150 ms minimum, given they were chosen after seeing results?",
        "What statistical test should we use with only 12 recordings?"]),
     ("Improving the detector", [
        "Should we tune for precision on separate DCLDE recordings, then re-test once?",
        "Is a 5–50 kHz version worth training, so we can compare directly with published results?",
        "How should we treat problem recordings such as ...023000? The proposal is to keep them in the results and explain them."]),
     ("2017 data and the VAE-GMM paper", [
        "Is hand-labelling acceptable as future work in the detector paper?",
        "Does the VAE-GMM paper need a real accuracy score for the 2–24 kHz detector before submission?",
        "If so, is a small labelled set enough? Who can label, and who can check the labels?",
        "Should we email the survey researchers about existing labels, and who should send it?",
        "Would a no-whistle false-alarm test plus a small checked sample be enough evidence for now?"]),
     ("Practical", [
        "Should the methods section or acknowledgements mention the colleague who ran Silbido?",
        "Who should be listed as authors, and in what order?",
        "What is the realistic deadline?"])]
s.append(P("15. Questions for guidance", h1))
n = 1
for name, items in q:
    s.append(KeepTogether([P(name, h2), bullets(items, numbered=True, start=n)]))
    n += len(items)

s += [gap(10), P("References: Park et al., VAE-GMM whistle paper, IEEE Access. Roch et al. (2011), J. Acoust. Soc. Am. 130(4), 2212–2223. Li et al. (2023), J. Acoust. Soc. Am. 154(1), 502–517, doi:10.1121/10.0020274. "
                 "DCLDE 2011 data: doi:10.25921/wsnc-js16. Abbreviations in tables: P precision, R recall, Fragm. fragmentation.", small)]


def footer(c, d):
    c.saveState()
    c.setFont("Body", 8.5)
    c.setFillColor(MUTED)
    c.drawString(2.1 * cm, 1.15 * cm, "Whistle Detector Project: status report, 5 November 2026")
    c.drawRightString(A4[0] - 2.1 * cm, 1.15 * cm, f"Page {d.page}")
    c.restoreState()


doc = BaseDocTemplate(OUT, pagesize=A4, leftMargin=2.1 * cm, rightMargin=2.1 * cm, topMargin=1.9 * cm, bottomMargin=1.9 * cm,
                      title="Whistle Detector Project: status report", author="Parjanya")
doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)], onPage=footer)])
doc.build(s)
print("built", OUT)
