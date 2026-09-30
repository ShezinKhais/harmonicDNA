"""Tests for the HTML report (no audio files needed).

The report's whole claim is that it keeps the four outcomes of the scoring
matrix apart, so these assert on the encoding rather than on the prose.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from harmonicdna.aligner import align, AlignmentResult
from harmonicdna.visualiser import (
    alignment_to_text, chord_timeline, render_html_comparison,
)


SEQ_A = ["Dmin", "Cmaj", "Gmaj", "Amin", "Fmaj", "Emin"]
SEQ_B = ["D#maj", "Cmaj", "Gmaj", "Cmaj", "Fmin", "Bmin"]


@pytest.fixture
def report():
    result = align(SEQ_A, SEQ_B)
    return render_html_comparison("a.wav", SEQ_A, "b.wav", SEQ_B, result)


class TestReport:
    def test_is_self_contained(self, report):
        # the file has to open with no network, so nothing may be fetched
        assert "http://" not in report and "https://" not in report
        assert "<script" not in report

    def test_states_are_named_not_just_coloured(self, report):
        for state in ("identical", "related", "mismatch", "gap"):
            assert state in report

    def test_relationships_are_named(self, report):
        # this fixture aligns Amin against Cmaj and Fmaj against Fmin
        assert "relative" in report and "parallel" in report

    def test_figures_are_present(self, report):
        assert "Smith-Waterman" in report
        assert "tabular-nums" in report

    def test_both_progressions_appear_in_full(self, report):
        for chord in SEQ_A + SEQ_B:
            assert chord in report

    def test_names_are_escaped(self):
        result = align(SEQ_A, SEQ_B)
        html   = render_html_comparison("<b>a</b>.wav", SEQ_A, "b.wav", SEQ_B, result)
        assert "<b>a</b>.wav" not in html
        assert "&lt;b&gt;a&lt;/b&gt;.wav" in html

    def test_empty_alignment_says_so(self):
        seq_a, seq_b = ["Cmaj", "Gmaj"], ["F#min", "Bmin"]
        result = align(seq_a, seq_b)
        html   = render_html_comparison("a.wav", seq_a, "b.wav", seq_b, result)
        assert "No local alignment scored above zero" in html
        # the progressions still get shown, so the reader can see what was searched
        assert "F#min" in html

    def test_writes_the_file(self, tmp_path):
        out    = tmp_path / "report.html"
        result = align(SEQ_A, SEQ_B)
        render_html_comparison("a.wav", SEQ_A, "b.wav", SEQ_B, result,
                               output_path=str(out))
        assert out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


class TestTerminalOutput:
    """The text path is what the CLI prints, and it stays as it was."""

    def test_alignment_to_text_has_both_sequences(self):
        result = align(SEQ_A, SEQ_B)
        text   = alignment_to_text(result)
        assert "Seq A:" in text and "Seq B:" in text

    def test_chord_timeline_handles_nothing_detected(self):
        assert chord_timeline([]) == "(no chords detected)"
