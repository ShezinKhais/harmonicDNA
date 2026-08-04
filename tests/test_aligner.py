"""Tests for Smith-Waterman chord aligner."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from harmonicdna.aligner import (
    align, AlignmentResult, chord_similarity, parse_chord,
    SAME, PARALLEL, RELATIVE, FIFTH, UNRELATED,
)


class TestParseChord:
    def test_natural_root(self):
        assert parse_chord("Cmaj") == (0, "maj")

    def test_sharp_root(self):
        assert parse_chord("C#min") == (1, "min")

    def test_last_pitch_class(self):
        assert parse_chord("Bmin") == (11, "min")

    @pytest.mark.parametrize("label", ["N", "", "Hmaj", "Cdim", "maj", "C"])
    def test_rejects_non_triads(self, label):
        assert parse_chord(label) is None


class TestChordSimilarity:
    def test_identical(self):
        assert chord_similarity("Cmaj", "Cmaj") == SAME

    def test_parallel_major_minor(self):
        assert chord_similarity("Cmaj", "Cmin") == PARALLEL

    def test_relative_minor(self):
        # A minor is the relative of C major, in either argument order
        assert chord_similarity("Cmaj", "Amin") == RELATIVE
        assert chord_similarity("Amin", "Cmaj") == RELATIVE

    def test_relative_wraps_the_octave(self):
        # E flat major's relative minor is C minor: 3 + 9 = 12 -> 0
        assert chord_similarity("D#maj", "Cmin") == RELATIVE

    def test_dominant_and_subdominant(self):
        assert chord_similarity("Cmaj", "Gmaj") == FIFTH   # dominant, +7
        assert chord_similarity("Cmaj", "Fmaj") == FIFTH   # subdominant, +5

    def test_fifths_need_matching_quality(self):
        # G minor is not the dominant of C major in any useful sense
        assert chord_similarity("Cmaj", "Gmin") == UNRELATED

    def test_unrelated(self):
        assert chord_similarity("Cmaj", "F#min") == UNRELATED

    def test_unparseable_label_is_unrelated(self):
        assert chord_similarity("Cmaj", "N") == UNRELATED

    def test_unparseable_labels_still_match_themselves(self):
        assert chord_similarity("N", "N") == SAME

    def test_symmetric(self):
        chords = ["Cmaj", "Cmin", "Amin", "Gmaj", "Fmaj", "F#min", "D#maj"]
        for a in chords:
            for b in chords:
                assert chord_similarity(a, b) == chord_similarity(b, a)


class TestAlign:
    def test_identical_sequences_high_score(self):
        seq = ["Cmaj", "Gmaj", "Amin", "Fmaj"]
        r   = align(seq, seq)
        assert r.score > 0
        assert r.identity == pytest.approx(1.0)

    def test_empty_sequences(self):
        r = align([], [])
        assert r.score == 0.0
        assert r.seq_a_aligned == []

    def test_no_match_returns_zero(self):
        # Every pairing here is unrelated, so every cell goes negative and
        # Smith-Waterman clamps the whole matrix to zero. Note that harmonic
        # scoring makes "different chord" and "unrelated chord" different
        # things: Gmaj against Emin would score, since they are relatives.
        r = align(["Cmaj", "Gmaj"], ["F#min", "Bmin"])
        assert r.score == 0.0

    def test_related_chords_score_without_matching(self):
        # no chord appears in both sequences, yet the relationships align them
        r = align(["Cmaj", "Gmaj"], ["Amin", "Emin"])
        assert r.score > 0
        assert r.identity == pytest.approx(0.0)

    def test_exact_match_beats_related(self):
        exact   = align(["Cmaj", "Gmaj"], ["Cmaj", "Gmaj"]).score
        related = align(["Cmaj", "Gmaj"], ["Amin", "Emin"]).score
        assert exact > related

    def test_traceback_survives_inexact_scores(self):
        # A run of FIFTH (0.3) accumulates float error, so the traceback has to
        # compare against a tolerance rather than for exact equality.
        a = ["Cmaj", "Gmaj", "Dmaj", "Amaj", "Emaj"]
        b = ["Gmaj", "Dmaj", "Amaj", "Emaj", "Bmaj"]
        r = align(a, b)
        assert r.score > 0
        assert len(r.seq_a_aligned) == len(r.seq_b_aligned)
        assert len(r.seq_a_aligned) >= 4

    def test_partial_match(self):
        a = ["Cmaj", "Gmaj", "Amin", "Fmaj"]
        b = ["Dmin", "Cmaj", "Gmaj", "Emin"]
        r = align(a, b)
        # at least "Cmaj", "Gmaj" should align
        assert r.score > 0
        assert len(r.seq_a_aligned) >= 2

    def test_alignment_lengths_match(self):
        a = ["Cmaj", "Gmaj", "Amin"]
        b = ["Cmaj", "Fmaj", "Amin"]
        r = align(a, b)
        assert len(r.seq_a_aligned) == len(r.seq_b_aligned)

    def test_identity_in_range(self):
        a = ["Cmaj", "Gmaj", "Amin", "Fmaj"]
        b = ["Cmaj", "Gmaj", "Dmin", "Fmaj"]
        r = align(a, b)
        assert 0.0 <= r.identity <= 1.0
