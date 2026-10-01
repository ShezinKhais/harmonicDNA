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

# Write the alignment out as a page, and keep only confident chord detections
python -m harmonicdna.cli compare song_a.mp3 song_b.mp3     --html alignment.html --min-confidence 0.6

# Show detected chords only
python -m harmonicdna.cli chords song_a.mp3
```

### The window

`gui` opens a desktop window that does everything `compare` and `chords` do:
pick two tracks, watch the pipeline run stage by stage, and read the alignment
as coloured chords rather than as a line of text. It is built on tkinter, which
ships with Python, so it adds no dependency.

The score is never shown on its own. A high similarity with low identity means
the two tracks are harmonically *parallel* rather than the same passage: the
same shape in a different key, and the window says which of the two it is.

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

## Limitations

The alignment is exact given a chord sequence. Getting the chord sequence out of
audio is the part that is approximate, and everything downstream inherits it.

- **The vocabulary is 24 chords: twelve roots, major or minor.** Anything else,
  a dominant seventh, a sus, a diminished or augmented chord, a slash chord over
  a different bass, is forced onto whichever of the 24 its chroma most resembles.
  Jazz and anything with extended harmony will come back as a plausible-looking
  sequence of triads that is not what is being played.
- **Frames below `--min-confidence` are dropped rather than marked.** The
  sequence closes up over them, so a passage the detector was unsure about
  becomes a shorter sequence rather than a gap, and the alignment is not told
  that anything is missing.
- **Chroma cannot tell a chord from its inversion**, or reliably from a
  neighbouring chord sharing two notes, so Cmaj and Amin are easy to confuse in
  exactly the cases where it matters.
- **Detection is beat-synchronous.** A chord change inside a beat is averaged
  away, and the whole thing rests on librosa's beat tracker agreeing with the
  music, which it does not do on rubato, on heavy swing, or on anything without
  a clear pulse.
- **A high score with low identity is not the same passage.** The scoring matrix
  pays for related chords, so two sequences with no chord in common can still
  align. This is a design choice rather than a defect, but the score cannot be
  read on its own, which is why `identity` is always reported next to it.

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
│   ├── aligner.py          # chord relationship scores, Smith-Waterman DP + traceback
│   ├── scoring.py          # normalised similarity, identity, verdict
│   ├── visualiser.py       # two-track HTML alignment report
│   ├── gui.py              # desktop window
│   └── cli.py
└── tests/
    ├── test_aligner.py
    ├── test_scoring.py
    ├── test_score_lookup.py
    ├── test_chord_detector.py
    ├── test_visualiser.py
    ├── test_gui.py
    └── test_cli.py
```

---

## Stack

Python 3.10, librosa, NumPy, SciPy, Typer, Rich

Supports MP3, WAV, FLAC and any format librosa can decode.
