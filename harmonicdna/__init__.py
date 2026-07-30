"""HarmonicDNA - chord fingerprinting and musical similarity via Smith-Waterman."""

from harmonicdna.chord_detector import detect_chords, ChordLabel
from harmonicdna.chromagram import compute_chromagram
from harmonicdna.aligner import align, AlignmentResult
from harmonicdna.scoring import similarity_score

__all__ = [
    "detect_chords", "ChordLabel",
    "compute_chromagram",
    "align", "AlignmentResult",
    "similarity_score",
]
