"""The scoring matrix is filled from a lookup table rather than a per-cell call.

score_fn is now invoked once per distinct label pair instead of once per cell,
so these tests pin that the matrix, the alignment and any caller-supplied
scoring function still behave exactly as they did.
"""

import random

import numpy as np
import pytest

from harmonicdna.aligner import align, chord_similarity, GAP, _score_lookup

_NAMES = [root + qual
          for root in ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
          for qual in ["maj", "min"]] + ["N"]


def _reference_matrix(seq_a, seq_b, gap=GAP, score_fn=chord_similarity):
    """The original cell-by-cell fill, kept here as the oracle."""
    n, m = len(seq_a), len(seq_b)
    H = np.zeros((n + 1, m + 1))
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            s = score_fn(seq_a[i - 1], seq_b[j - 1])
            H[i, j] = max(0, H[i - 1, j - 1] + s,
                          H[i - 1, j] + gap, H[i, j - 1] + gap)
    return H


class TestScoreLookup:
    def test_lookup_reproduces_score_fn_for_every_pair(self):
        seq_a = ["Cmaj", "Amin", "Fmaj", "Cmaj"]
        seq_b = ["Cmin", "Gmaj", "Amin"]
        table, rows, cols = _score_lookup(seq_a, seq_b, chord_similarity)
        for i, label_a in enumerate(seq_a):
            for j, label_b in enumerate(seq_b):
                assert table[rows[i], cols[j]] == chord_similarity(label_a, label_b)

    def test_table_is_vocabulary_sized_not_cell_sized(self):
        seq_a = ["Cmaj"] * 50
        seq_b = ["Amin"] * 40
        table, _, _ = _score_lookup(seq_a, seq_b, chord_similarity)
        assert table.shape == (1, 1)

    def test_unparseable_labels_are_handled(self):
        table, rows, cols = _score_lookup(["N", "Cmaj"], ["N"], chord_similarity)
        assert table[rows[0], cols[0]] == chord_similarity("N", "N")
        assert table[rows[1], cols[0]] == chord_similarity("Cmaj", "N")


class TestMatrixEquivalence:
    @pytest.mark.parametrize("seed", range(25))
    def test_matches_the_cell_by_cell_fill(self, seed):
        rng = random.Random(seed)
        seq_a = [rng.choice(_NAMES) for _ in range(rng.randint(0, 20))]
        seq_b = [rng.choice(_NAMES) for _ in range(rng.randint(0, 20))]
        if not seq_a or not seq_b:
            assert align(seq_a, seq_b).score == 0.0
            return
        expected = _reference_matrix(seq_a, seq_b)
        assert align(seq_a, seq_b).score == pytest.approx(float(expected.max()))

    def test_empty_sequences_score_zero(self):
        assert align([], ["Cmaj"]).score == 0.0
        assert align(["Cmaj"], []).score == 0.0
        assert align([], []).score == 0.0


class TestCustomScoreFn:
    def test_a_caller_supplied_score_fn_is_still_honoured(self):
        def exact_only(a, b):
            return 3.0 if a == b else -2.0

        seq = ["Cmaj", "Gmaj", "Amin"]
        result = align(seq, seq, score_fn=exact_only)
        assert result.score == pytest.approx(9.0)
        assert result.identity == 1.0

    def test_filling_the_matrix_no_longer_scales_with_cell_count(self):
        calls = []

        def counting(a, b):
            calls.append((a, b))
            return chord_similarity(a, b)

        seq_a = ["Cmaj"] * 30
        seq_b = ["Amin"] * 20
        align(seq_a, seq_b, score_fn=counting)

        # 600 cells over a single distinct label pair. The fill scores that pair
        # once; the remaining calls come from the traceback, which walks the
        # alignment and so is bounded by its length, not by the cell count.
        assert len(set(calls)) == 1
        assert len(calls) <= len(seq_a) + len(seq_b)
