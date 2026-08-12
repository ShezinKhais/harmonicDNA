"""Smith-Waterman local alignment for chord sequences."""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass


# 12 pitch classes, matching chord_detector's template naming
_PITCH_CLASSES = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]
_PC_INDEX      = {name: i for i, name in enumerate(_PITCH_CLASSES)}

# Substitution scores. Chord labels are not symbols to be matched literally:
# two chords can be a semitone apart on paper and closely related in function,
# so scoring only exact equality throws away most of the musical signal.
SAME      =  2.0   # Cmaj / Cmaj
PARALLEL  =  1.0   # Cmaj / Cmin       same root, opposite quality
RELATIVE  =  0.5   # Cmaj / Amin       share a key signature
FIFTH     =  0.3   # Cmaj / Gmaj, Fmaj dominant or subdominant
UNRELATED = -1.0
GAP       = -0.5

# Scores like 0.3 have no exact binary representation, so sums of them drift by
# a few ulps. The traceback below compares a cell against the three moves that
# could have produced it, and an exact == would occasionally miss the real one
# and take a wrong branch, so those comparisons run against a tolerance.
_EPS = 1e-9


def parse_chord(label: str) -> tuple[int, str] | None:
    """'C#min' -> (1, 'min'). None if the label is not a known triad."""
    for quality in ("maj", "min"):
        if label.endswith(quality):
            root = label[:-len(quality)]
            if root in _PC_INDEX:
                return _PC_INDEX[root], quality
    return None


def chord_similarity(a: str, b: str) -> float:
    """
    Score one chord against another by harmonic relationship.

    Anything unparseable (a "no chord" marker, say) only ever scores as
    identical or unrelated, since there is no root to reason about.
    """
    if a == b:
        return SAME

    pa, pb = parse_chord(a), parse_chord(b)
    if pa is None or pb is None:
        return UNRELATED

    root_a, qual_a = pa
    root_b, qual_b = pb

    # same root, opposite quality: C major against C minor
    if root_a == root_b:
        return PARALLEL

    if qual_a != qual_b:
        # relative major/minor: the minor sits 9 semitones above its major
        major, minor = ((root_a, root_b) if qual_a == "maj" else (root_b, root_a))
        return RELATIVE if (major + 9) % 12 == minor else UNRELATED

    # same quality, a fifth apart in either direction
    return FIFTH if (root_b - root_a) % 12 in (5, 7) else UNRELATED


@dataclass
class AlignmentResult:
    score: float
    seq_a_aligned: list[str]
    seq_b_aligned: list[str]
    start_a: int
    start_b: int
    identity: float   # fraction of aligned positions that match


def _score_lookup(seq_a: list[str], seq_b: list[str], score_fn):
    """Return (table, rows, cols) giving the score for any position pair.

    The score for seq_a[i] against seq_b[j] is table[rows[i], cols[j]].

    A song reduces to at most the 24 triads plus whatever unparseable markers
    the detector emitted, so the number of distinct label pairs is tiny next to
    the number of cell pairs. Scoring each distinct pair once turns a per-cell
    call that reparses two chord names into a lookup. The table stays at
    vocabulary size rather than being expanded to one entry per cell, which
    would cost as much memory again as the scoring matrix itself.
    """
    index_a = {label: i for i, label in enumerate(dict.fromkeys(seq_a))}
    index_b = {label: j for j, label in enumerate(dict.fromkeys(seq_b))}

    table = np.empty((len(index_a), len(index_b)))
    for label_a, i in index_a.items():
        for label_b, j in index_b.items():
            table[i, j] = score_fn(label_a, label_b)

    rows = [index_a[label] for label in seq_a]
    cols = np.fromiter((index_b[label] for label in seq_b),
                       dtype=np.intp, count=len(seq_b))
    return table, rows, cols


def align(
    seq_a: list[str],
    seq_b: list[str],
    gap: float = GAP,
    score_fn = chord_similarity,
) -> AlignmentResult:
    """Smith-Waterman local alignment of two chord sequences."""
    n, m = len(seq_a), len(seq_b)
    H    = np.zeros((n + 1, m + 1))
    if n and m:
        table, rows, cols = _score_lookup(seq_a, seq_b, score_fn)

        # The recurrence is serial in both axes, so the fill stays a loop. It
        # runs over Python lists rather than indexing H cell by cell: element
        # access on a numpy array costs far more than plain float arithmetic,
        # and this loop runs len(a) * len(b) times. The arithmetic is identical,
        # so the matrix and the traceback below are unchanged.
        prev = [0.0] * (m + 1)
        for i in range(1, n + 1):
            scores = table[rows[i - 1]].take(cols).tolist()
            cur    = [0.0] * (m + 1)
            left   = 0.0
            for j in range(1, m + 1):
                best = prev[j - 1] + scores[j - 1]
                up   = prev[j] + gap
                if up > best:
                    best = up
                lf = left + gap
                if lf > best:
                    best = lf
                if best < 0.0:
                    best = 0.0
                cur[j] = best
                left   = best
            H[i] = cur
            prev = cur

    # find best score position
    best_score = float(H.max())
    if best_score <= 0:
        return AlignmentResult(
            score=0.0, seq_a_aligned=[], seq_b_aligned=[],
            start_a=0, start_b=0, identity=0.0
        )

    idx      = np.unravel_index(np.argmax(H), H.shape)
    i, j     = int(idx[0]), int(idx[1])

    # traceback
    aligned_a, aligned_b = [], []
    while i > 0 and j > 0 and H[i, j] > 0:
        s = score_fn(seq_a[i - 1], seq_b[j - 1])
        if abs(H[i, j] - (H[i - 1, j - 1] + s)) < _EPS:
            aligned_a.append(seq_a[i - 1])
            aligned_b.append(seq_b[j - 1])
            i -= 1; j -= 1
        elif abs(H[i, j] - (H[i - 1, j] + gap)) < _EPS:
            aligned_a.append(seq_a[i - 1])
            aligned_b.append("-")
            i -= 1
        else:
            aligned_a.append("-")
            aligned_b.append(seq_b[j - 1])
            j -= 1

    aligned_a.reverse(); aligned_b.reverse()
    matches   = sum(a == b for a, b in zip(aligned_a, aligned_b))
    length    = max(len(aligned_a), 1)

    return AlignmentResult(
        score         = best_score,
        seq_a_aligned = aligned_a,
        seq_b_aligned = aligned_b,
        start_a       = i,
        start_b       = j,
        identity      = round(matches / length, 3),
    )
