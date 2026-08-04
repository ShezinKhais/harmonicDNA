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


def align(
    seq_a: list[str],
    seq_b: list[str],
    gap: float = GAP,
    score_fn = chord_similarity,
) -> AlignmentResult:
    """Smith-Waterman local alignment of two chord sequences."""
    n, m = len(seq_a), len(seq_b)
    H    = np.zeros((n + 1, m + 1))

    # fill scoring matrix
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            s = score_fn(seq_a[i - 1], seq_b[j - 1])
            H[i, j] = max(
                0,
                H[i - 1, j - 1] + s,
                H[i - 1, j]     + gap,
                H[i,     j - 1] + gap,
            )

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
