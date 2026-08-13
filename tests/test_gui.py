"""The window renders what the aligner actually produced.

Most of these need a display, so they skip where there is none rather than
failing: CI runs headless, and a GUI that cannot open there is expected, not
broken. The colour rule and the parallel/identical reading are pure functions
and are tested unconditionally.
"""

import pytest

from harmonicdna.aligner import GAP, align
from harmonicdna.scoring import self_align_score, similarity_score

tk = pytest.importorskip("tkinter")
from harmonicdna import gui  # noqa: E402


@pytest.fixture
def root():
    try:
        r = tk.Tk()
    except tk.TclError as e:            # no display
        pytest.skip(f"no display available: {e}")
    r.withdraw()
    yield r
    r.destroy()


class TestChordColour:
    """Blue major, orange minor - the split visualiser.py already uses."""

    @pytest.mark.parametrize("label", ["Cmaj", "F#maj", "Bmaj"])
    def test_major_is_the_major_colour(self, label):
        assert gui.chord_colour(label) == gui.MAJ

    @pytest.mark.parametrize("label", ["Amin", "D#min", "Bmin"])
    def test_minor_is_the_minor_colour(self, label):
        assert gui.chord_colour(label) == gui.MIN

    @pytest.mark.parametrize("label", ["-", "N", "X"])
    def test_anything_unparseable_is_muted(self, label):
        # A gap and a "no chord" marker are not chords and must not read as one.
        assert gui.chord_colour(label) == gui.MUTED


class TestLegendMatchesTheAligner:
    def test_the_legend_quotes_the_substitution_table(self):
        """A legend with its own copy of the numbers would drift from the code."""
        from harmonicdna import aligner
        values = {label: value for label, value, _ in gui._LEGEND}
        assert values["same chord"] == aligner.SAME
        assert values["parallel major/minor"] == aligner.PARALLEL
        assert values["relative major/minor"] == aligner.RELATIVE
        assert values["fifth (same quality)"] == aligner.FIFTH
        assert values["unrelated"] == aligner.UNRELATED
        assert values["gap"] == aligner.GAP


class TestResultView:
    def _aligned(self, a, b):
        result = align(a, b)
        return result, similarity_score(result, self_align_score(max(a, b, key=len)))

    def test_a_result_renders(self, root):
        app = gui.App(root)
        result, score = self._aligned(
            ["Cmaj", "Amin", "Fmaj", "Gmaj"], ["Cmaj", "Amin", "Dmin", "Gmaj"])
        app._show_result(result, score)
        root.update_idletasks()
        assert app.stage.winfo_children()

    def test_the_same_passage_and_parallel_readings_differ(self, root):
        """A high score with low identity must not read as 'the same passage'."""
        app = gui.App(root)

        same = ["Cmaj", "Amin", "Fmaj", "Gmaj", "Cmaj"]
        r1, s1 = self._aligned(same, same)
        app._show_result(r1, s1)
        root.update_idletasks()
        assert "SAME PASSAGE" in self._labels(app)

        # Transposed: every chord related, none shared.
        r2, s2 = self._aligned(same, ["Emaj", "C#min", "Amaj", "Bmaj", "Emaj"])
        if s2.identity < 0.5 and s2.normalised >= 0.5:
            app._show_result(r2, s2)
            root.update_idletasks()
            assert "PARALLEL, NOT IDENTICAL" in self._labels(app)

    def test_the_gap_count_matches_the_alignment(self, root):
        app = gui.App(root)
        result, score = self._aligned(
            ["Cmaj", "Amin", "Fmaj", "Gmaj", "Cmaj", "Fmaj"],
            ["Cmaj", "Amin", "Fmaj", "Emin", "Gmaj", "Cmaj", "Fmaj"])
        app._show_result(result, score)
        root.update_idletasks()
        expected = sum(1 for x in result.seq_a_aligned + result.seq_b_aligned if x == "-")
        assert str(expected) in self._labels(app)

    def _labels(self, app):
        out = []

        def walk(w):
            for c in w.winfo_children():
                try:
                    out.append(str(c.cget("text")))
                except tk.TclError:
                    pass
                walk(c)
        walk(app.stage)
        return out


class TestModes:
    def test_chords_mode_hides_the_second_source(self, root):
        # grid_info, not winfo_ismapped: the root is withdrawn for the tests,
        # which makes every descendant report unmapped whatever its geometry
        # says. grid_remove clears grid_info and grid() restores it, so this
        # reads the state the code actually sets.
        app = gui.App(root)
        card_b = app.cards["b"]["drop"].master
        app._switch("chords")
        root.update_idletasks()
        assert card_b.grid_info() == {}
        app._switch("compare")
        root.update_idletasks()
        assert card_b.grid_info() != {}
        assert app.go.cget("text") == "Align sequences"

    def test_aligning_without_files_reports_rather_than_crashes(self, root):
        app = gui.App(root)
        app._start()
        root.update_idletasks()
        assert not app.busy


class TestSliders:
    def test_the_defaults_match_the_cli(self, root):
        """A value read off this window can be typed at the CLI unchanged."""
        app = gui.App(root)
        assert app.min_conf.get() == pytest.approx(0.5)   # cli --min-confidence
        assert app.gap.get() == pytest.approx(GAP)        # aligner.GAP
