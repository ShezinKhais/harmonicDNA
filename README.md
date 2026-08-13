# HarmonicDNA

Applies the Smith-Waterman local sequence alignment algorithm - normally used in bioinformatics to find similar regions in DNA strands - to chord progressions extracted from audio files. The result is a similarity score and a visual alignment showing which passages are most harmonically alike.

The idea is that chord sequences, like genetic sequences, can be compared for local similarity rather than requiring a global match. Two songs might share a bridge or chorus even if they are structurally different overall.

---

## How it works

1. Audio is loaded and a beat-synchronous chromagram is extracted using librosa
2. Chroma vectors are matched against 24 chord templates (12 roots x major/minor) via cosine similarity
3. The resulting chord sequence is run through Smith-Waterman alignment against a second song's sequence
4. A scoring matrix rewards same chords, related chords (parallel, relative, subdominant/dominant), and penalises gaps
5. Traceback recovers the highest-scoring local alignment

---

## Usage

```bash
pip install -r requirements.txt

# Open the desktop window
python -m harmonicdna.cli gui

# Compare two audio files
python -m harmonicdna.cli compare song_a.mp3 song_b.mp3

# Show detected chords only
python -m harmonicdna.cli chords song_a.mp3
```

### The window

`gui` opens a desktop window that does everything `compare` and `chords` do:
pick two tracks, watch the pipeline run stage by stage, and read the alignment
as coloured chords rather than as a line of text. It is built on tkinter, which
ships with Python, so it adds no dependency.

The score is never shown on its own. A high similarity with low identity means
the two tracks are harmonically *parallel* rather than the same passage — the
same shape in a different key — and the window says which of the two it is.

### Windows executable

Download `HarmonicDNA-windows.zip` from the
[latest release](https://github.com/ShezinKhais/harmonicDNA/releases/latest),
unzip it anywhere, and run `HarmonicDNA.exe` from inside the folder. No Python,
no dependencies. It opens the window; passing arguments still gets the command
line, so `HarmonicDNA.exe chords song.mp3` works too.

It ships as a folder rather than a lone executable because librosa brings
numba, scipy and several native audio libraries with it. A single-file build
would append all of that to the executable and unpack it into a temporary
directory on every launch.

---

## Scoring matrix

Chord labels are not treated as symbols to be matched literally. Two chords can
look unrelated as strings and be closely related in function, so the aligner
scores each pair by harmonic relationship instead of equality.

| Relationship | Example | Score |
|---|---|---|
| Same chord | Cmaj / Cmaj | +2.0 |
| Parallel major/minor (same root) | Cmaj / Cmin | +1.0 |
| Relative major/minor | Cmaj / Amin | +0.5 |
| Subdominant or dominant | Cmaj / Fmaj, Cmaj / Gmaj | +0.3 |
| Unrelated | Cmaj / F#min | -1.0 |
| Gap penalty | | -0.5 |

The fifth relationship requires both chords to share a quality, so Cmaj scores
against Gmaj but not against Gmin. One consequence worth knowing: two sequences
with no chord in common can still align, because relatedness alone is enough to
carry a local alignment. `identity` reports how much of that alignment was exact
matching, so a high score with a low identity means the passages are harmonically
parallel rather than the same.

---

## Testing

Install the dependencies and run the suite:

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt pytest   # Linux/macOS: .venv/bin/pip
.venv/Scripts/python -m pytest -v
```

Exercise the CLI directly with `python -m harmonicdna.cli --help`.

---

## Project structure

```
harmonicdna/
├── harmonicdna/
│   ├── chromagram.py       # beat-synchronous chroma extraction
│   ├── chord_detector.py   # template matching, smoothing, deduplication
│   ├── scoring.py          # 24x24 chord similarity matrix
│   ├── aligner.py          # Smith-Waterman DP + traceback
│   ├── visualiser.py       # HTML alignment table
│   └── cli.py
└── tests/
    ├── test_aligner.py
    ├── test_scoring.py
    └── test_chord_detector.py
```

---

## Stack

Python 3.10, librosa, NumPy, SciPy, Typer, Rich

Supports MP3, WAV, FLAC and any format librosa can decode.
