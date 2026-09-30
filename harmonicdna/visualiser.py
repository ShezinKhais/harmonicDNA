"""Visualise chord sequences and alignment results."""

from __future__ import annotations

from collections import Counter
from html import escape

from harmonicdna.aligner import (
    AlignmentResult, chord_relationship,
    FIFTH, GAP, PARALLEL, RELATIVE, SAME, UNRELATED,
)
from harmonicdna.chord_detector import ChordLabel
from harmonicdna.scoring import self_align_score, similarity_score


def alignment_to_text(result: AlignmentResult) -> str:
    """Pretty-print an alignment result like a DNA aligner would."""
    a = " ".join(f"{c:>6}" for c in result.seq_a_aligned)
    b = " ".join(f"{c:>6}" for c in result.seq_b_aligned)
    # match line
    m = " ".join(
        f"{'|':>6}" if x == y else f"{'X':>6}"
        for x, y in zip(result.seq_a_aligned, result.seq_b_aligned)
    )
    lines = [
        f"Score  : {result.score:.1f}",
        f"Identity: {result.identity:.0%}",
        f"",
        f"Seq A: {a}",
        f"       {m}",
        f"Seq B: {b}",
    ]
    return "\n".join(lines)


def chord_timeline(labels: list[ChordLabel], width: int = 60) -> str:
    """ASCII timeline of chord labels, compressed to fit in width chars."""
    if not labels:
        return "(no chords detected)"
    total  = labels[-1].frame + 1
    scale  = width / max(total, 1)
    cells  = ["."] * width
    for lbl in labels:
        pos = min(int(lbl.frame * scale), width - 1)
        # just use first letter of chord name
        cells[pos] = lbl.name[0]
    return "[" + "".join(cells) + "]"


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------

# The substitution table distinguishes four outcomes per aligned column, and
# the report has to keep them apart: collapsing "related" into "mismatch" is
# exactly what makes a relative-minor substitution look like a failure.
_STATES = ("identical", "related", "mismatch", "gap")

_STATE_NOTE = {
    "identical": "the same chord in both progressions",
    "related":   "different chords the matrix treats as harmonically close",
    "mismatch":  "a pair with no relationship the matrix recognises",
    "gap":       "a chord in one progression with nothing opposite it",
}

# Abbreviated in the track because a column is only as wide as a chord symbol;
# the legend spells each one out.
_RELATION_SHORT = {
    "parallel":    "par",
    "relative":    "rel",
    "dominant":    "dom",
    "subdominant": "sub",
}

# Drawn rather than coloured: an unbroken line, a dashed line, a line with a
# break in the middle and no line at all read the same in grey.
_MARKS = {
    "identical": '<svg viewBox="0 0 14 16" width="1em" height="1.15em" aria-hidden="true">'
                 '<line x1="7" y1="0" x2="7" y2="16" stroke="var(--confirm)" stroke-width="2"/></svg>',
    "related":   '<svg viewBox="0 0 14 16" width="1em" height="1.15em" aria-hidden="true">'
                 '<line x1="7" y1="0" x2="7" y2="16" stroke="var(--mark)" stroke-width="2"'
                 ' stroke-dasharray="2 2"/></svg>',
    "mismatch":  '<svg viewBox="0 0 14 16" width="1em" height="1.15em" aria-hidden="true">'
                 '<line x1="7" y1="0" x2="7" y2="4" stroke="var(--challenge)" stroke-width="2"/>'
                 '<line x1="7" y1="12" x2="7" y2="16" stroke="var(--challenge)" stroke-width="2"/></svg>',
    "gap":       '<svg viewBox="0 0 14 16" width="1em" height="1.15em" aria-hidden="true">'
                 '<line x1="1" y1="8" x2="13" y2="8" stroke="var(--quiet)" stroke-width="1"'
                 ' stroke-dasharray="2 2"/></svg>',
}

_CSS = """
:root {
  /* ground */
  --ground:    #EDEFEA;
  --lift:      #F7F8F5;
  --sink:      #E3E6DF;
  /* ink */
  --ink:       #191D1C;
  --ink-mid:   #4E5754;
  --ink-soft:  #7C8683;
  /* structure */
  --rule:      #CFD4CC;
  --rule-firm: #A8B0AC;
  /* the one structural accent */
  --mark:      #1D4E63;
  --mark-soft: #7FA3B2;
  /* semantic data inks */
  --confirm:   #2F6B4F;
  --challenge: #A33B2A;
  --extend:    #8A6A1F;
  --quiet:     #8C9491;

  --measure: 68ch;
  --sans: ui-sans-serif, "Segoe UI Variable Display", "Segoe UI", Inter,
          system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
  --mono: ui-monospace, "Cascadia Code", "SF Mono", "Consolas",
          "Liberation Mono", monospace;
  --col: 52px;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --ground:    #14171A;
    --lift:      #1C2024;
    --sink:      #0F1215;
    --ink:       #E4E8E6;
    --ink-mid:   #A6AEAB;
    --ink-soft:  #7B8582;
    --rule:      #2E343A;
    --rule-firm: #454D53;
    --mark:      #6FB3CE;
    --mark-soft: #3C6478;
    --confirm:   #6FBE93;
    --challenge: #E08472;
    --extend:    #D9B45C;
    --quiet:     #6E7773;
  }
}
:root[data-theme="dark"] {
  --ground:    #14171A;
  --lift:      #1C2024;
  --sink:      #0F1215;
  --ink:       #E4E8E6;
  --ink-mid:   #A6AEAB;
  --ink-soft:  #7B8582;
  --rule:      #2E343A;
  --rule-firm: #454D53;
  --mark:      #6FB3CE;
  --mark-soft: #3C6478;
  --confirm:   #6FBE93;
  --challenge: #E08472;
  --extend:    #D9B45C;
  --quiet:     #6E7773;
}

* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  background: var(--ground);
  color: var(--ink);
  font: 400 15px/1.6 var(--sans);
}
.page { max-width: 1120px; margin: 0 auto; padding: 48px 24px 64px; }
@media (max-width: 640px) { .page { padding: 32px 16px 48px; } }

h1 { font: 600 30px/1.15 var(--sans); letter-spacing: -0.02em; margin: 0 0 8px; }
h2 {
  font: 600 17px/1.3 var(--sans);
  margin: 0 0 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--rule-firm);
}
p { margin: 0 0 12px; max-width: var(--measure); }
.lede { color: var(--ink-mid); }
section { margin-top: 32px; }
.caption {
  font: 500 12px/1.45 var(--sans);
  color: var(--ink-soft);
  max-width: var(--measure);
  margin: 12px 0 0;
}
.label { font: 500 12px/1.3 var(--sans); color: var(--ink-soft); }
.figure {
  font: 550 22px/1.0 var(--sans);
  font-variant-numeric: tabular-nums;
  display: block;
  margin: 6px 0 0;
}
.mono { font-family: var(--mono); }
.num { font-variant-numeric: tabular-nums; }
.sr {
  position: absolute; width: 1px; height: 1px;
  overflow: hidden; clip-path: inset(50%); white-space: nowrap;
}

/* inputs: a 3px ink rule at the leading edge and a plain word, no badges */
.input {
  position: relative;
  border-top: 1px solid var(--rule);
  padding: 12px 0 12px 12px;
  display: flex; flex-wrap: wrap; gap: 4px 12px; align-items: baseline;
}
.inputs .input:last-child { border-bottom: 1px solid var(--rule); }
.input::before {
  content: ""; position: absolute; left: 0; top: 12px; bottom: 12px;
  width: 3px; background: var(--mark);
}
.input .who { font: 500 12px/1.3 var(--sans); color: var(--ink-soft); min-width: 3.5em; }
.input .what { font-family: var(--mono); font-size: 13.5px; word-break: break-all; }
.input .len { font: 400 13.5px/1.45 var(--sans); color: var(--ink-mid); }

.facts {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  border-top: 1px solid var(--rule-firm);
  margin-top: 24px;
}
.fact { padding: 12px 16px 16px 0; border-bottom: 1px solid var(--rule); }
.fact .note { font: 400 12px/1.35 var(--sans); color: var(--ink-soft); margin-top: 6px; }

/* two-track alignment viewer */
.tracks { margin: 0 0 4px; }
.track-key {
  display: flex; gap: 8px; align-items: baseline;
  font-size: 13.5px; padding: 2px 0;
}
.track-key .who { font: 500 12px/1.45 var(--sans); color: var(--mark); min-width: 1.4em; }
.track-key .what { font-family: var(--mono); word-break: break-all; }

.align { display: flex; gap: 4px; align-items: flex-start; margin-top: 16px; }
.keys { flex: 0 0 auto; }
.strip { flex: 1 1 auto; min-width: 0; overflow-x: auto; padding-bottom: 8px; }
.strip:focus-visible { outline: 2px solid var(--mark); outline-offset: 2px; }
.rows { width: max-content; }
.row { display: flex; }
.r-ruler { height: 20px; }
.r-chord { height: 27px; border-top: 1px solid var(--rule); }
.r-bond { height: 34px; }
.cell { flex: 0 0 var(--col); width: var(--col); text-align: center; }
.keycell {
  display: block; width: 1.6em; padding-right: 4px; text-align: right;
  font: 500 12px/26px var(--sans); color: var(--ink-soft);
}
.chord { display: block; font: 400 13.5px/26px var(--mono); }
.chord.is-gap { background: var(--sink); color: var(--quiet); }
.rnum {
  display: block; font: 500 12px/12px var(--sans); color: var(--ink-soft);
  font-variant-numeric: tabular-nums;
}
.tick { display: block; width: 1px; height: 5px; margin: 3px auto 0; background: var(--rule-firm); }
.tick.minor { height: 2px; background: var(--rule); }
.bond { display: block; position: relative; padding-top: 2px; }
.bond svg { display: block; margin: 0 auto; }
.bondword { display: block; font: 500 12px/14px var(--sans); color: var(--mark); }

/* states table: the legend and the tally are the same object */
table { border-collapse: collapse; width: 100%; font-size: 13.5px; line-height: 1.45; }
th {
  font: 500 12px/1.3 var(--sans); color: var(--ink-soft);
  text-align: left; padding: 0 12px 8px 0; border-bottom: 1px solid var(--rule-firm);
  vertical-align: bottom;
}
td { padding: 12px 12px 12px 0; border-bottom: 1px solid var(--rule); vertical-align: top; }
th.gutter, td.gutter { width: 56px; padding-right: 16px; }
th.count, td.count { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
th.score, td.score { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
td.state { white-space: nowrap; }
td.count .unit { display: none; color: var(--ink-soft); }
td .glyph { display: inline-block; vertical-align: -0.15em; }

/* Five columns cannot hold their meaning at phone width, so the row stacks and
   the two figures carry the heading the hidden thead was giving them. */
@media (max-width: 720px) {
  .states thead { display: none; }
  .states, .states tbody { display: block; }
  .states tr {
    display: flex; flex-direction: column; gap: 4px;
    position: relative; padding: 12px 0 12px 72px;
    border-bottom: 1px solid var(--rule);
  }
  .states td { display: block; border: 0; padding: 0; text-align: left; }
  .states td.gutter { position: absolute; left: 0; top: 15px; width: 56px; }
  .states td.state { order: 1; font-weight: 500; }
  .states td.count { order: 2; }
  .states td.means { order: 3; color: var(--ink-mid); }
  .states td.score { order: 4; }
  .states td.count .unit { display: inline; }
  .states td.score::before { content: "table score "; color: var(--ink-soft); }
}

/* where the aligned window falls inside each progression */
.cov { border-top: 1px solid var(--rule); padding: 16px 0; }
.cov:last-child { border-bottom: 1px solid var(--rule); }
.cov-head { display: flex; flex-wrap: wrap; gap: 4px 12px; align-items: baseline; max-width: none; }
.cov-head .who { font: 500 12px/1.45 var(--sans); color: var(--mark); min-width: 1.4em; }
.cov-head .what { font-family: var(--mono); font-size: 13.5px; word-break: break-all; }
.cov-head .span { font-size: 13.5px; color: var(--ink-mid); font-variant-numeric: tabular-nums; }
.axis { position: relative; height: 13px; margin: 12px 0 4px; border-bottom: 1px solid var(--rule-firm); }
.axis .win { position: absolute; bottom: 0; height: 3px; background: var(--mark); }
.axis .end { position: absolute; bottom: 0; width: 1px; height: 9px; background: var(--mark); }
.axis-labels {
  display: flex; justify-content: space-between;
  font: 500 12px/1.3 var(--sans); color: var(--ink-soft);
  font-variant-numeric: tabular-nums;
}
.seq {
  display: flex; flex-wrap: wrap; gap: 2px 3px;
  font-family: var(--mono); font-size: 13.5px; margin-top: 12px;
}
.seq span {
  padding: 1px 4px; color: var(--ink-soft);
  border-bottom: 2px solid transparent;
}
.seq span.in {
  color: var(--ink); background: var(--lift); border-bottom-color: var(--mark);
}
.empty { color: var(--ink-mid); }
"""


def _state_of(a: str, b: str) -> tuple[str, str]:
    """
    Classify one aligned column, and name the relationship where there is one.

    The relationship reads from the first progression to the second, so
    "dominant" means the second song's chord is the dominant of the first's.
    """
    if a == "-" or b == "-":
        return "gap", ""
    relation = chord_relationship(a, b)
    if relation == "identical":
        return "identical", ""
    if relation == "unrelated":
        return "mismatch", ""
    return "related", relation


def _columns(result: AlignmentResult) -> list[dict]:
    """One record per aligned position: the two chords and how they relate."""
    columns = []
    for a, b in zip(result.seq_a_aligned, result.seq_b_aligned):
        state, relation = _state_of(a, b)
        columns.append({"a": a, "b": b, "state": state, "relation": relation})
    return columns


def _window(seq: list[str], start: int, aligned: list[str]) -> tuple[int, int] | None:
    """
    Half-open slice of the full progression that the alignment consumed.

    None where the numbers do not fit the sequence, so the report says it
    cannot place the window rather than drawing a span it invented.
    """
    used = sum(1 for chord in aligned if chord != "-")
    if used == 0 or not seq or start < 0 or start + used > len(seq):
        return None
    return start, start + used


def _track_html(columns: list[dict], name_a: str, name_b: str) -> str:
    """The hero: two position-aligned chord tracks with the states between."""
    ruler, row_a, bonds, row_b = [], [], [], []
    for i, col in enumerate(columns, start=1):
        labelled = i == 1 or i % 5 == 0
        ruler.append(
            '<span class="cell">'
            + (f'<span class="rnum">{i}</span>' if labelled else '<span class="rnum">&nbsp;</span>')
            + f'<span class="tick{"" if labelled else " minor"}"></span></span>'
        )
        for row, chord in ((row_a, col["a"]), (row_b, col["b"])):
            gap = ' is-gap' if chord == "-" else ''
            row.append(f'<span class="cell"><span class="chord{gap}">{escape(chord)}</span></span>')

        state    = col["state"]
        relation = col["relation"]
        word     = _RELATION_SHORT.get(relation, "")
        spoken   = relation or state
        bonds.append(
            f'<span class="cell" title="{escape(spoken)}"><span class="bond">'
            + _MARKS[state]
            + (f'<span class="bondword">{word}</span>' if word else '')
            + f'<span class="sr">{escape(spoken)}</span>'
            + '</span></span>'
        )

    return (
        '<div class="align">'
        '<div class="keys">'
        '<div class="row r-ruler"><span class="keycell"></span></div>'
        '<div class="row r-chord"><span class="keycell">A</span></div>'
        '<div class="row r-bond"><span class="keycell"></span></div>'
        '<div class="row r-chord"><span class="keycell">B</span></div>'
        '</div>'
        '<div class="strip" tabindex="0" role="group"'
        f' aria-label="Alignment of {escape(name_a)} against {escape(name_b)},'
        f' {len(columns)} columns, scrolls sideways">'
        '<div class="rows">'
        f'<div class="row r-ruler">{"".join(ruler)}</div>'
        f'<div class="row r-chord">{"".join(row_a)}</div>'
        f'<div class="row r-bond">{"".join(bonds)}</div>'
        f'<div class="row r-chord">{"".join(row_b)}</div>'
        '</div></div></div>'
    )


def _gutter_svg(count: int, total: int, ink: str) -> str:
    """A tick on the scale every row in this table shares."""
    span = 54.0
    x    = 1.0 + (span - 2.0) * (count / total if total else 0.0)
    return (
        '<svg viewBox="0 0 56 12" width="56" height="12" aria-hidden="true">'
        f'<line x1="1" y1="6" x2="55" y2="6" stroke="var(--rule)" stroke-width="1"/>'
        f'<rect x="{x:.1f}" y="1" width="2" height="10" fill="var({ink})"/>'
        '</svg>'
    )


def _states_html(columns: list[dict]) -> str:
    """Legend and tally in one table: every row names an encoding and counts it."""
    counts    = Counter(col["state"] for col in columns)
    relations = Counter(col["relation"] for col in columns if col["state"] == "related")
    total     = len(columns)

    scores = {
        "identical": f"+{SAME:.1f}",
        "related":   f"+{PARALLEL:.1f} to +{FIFTH:.1f}",
        "mismatch":  f"{UNRELATED:.1f}",
        "gap":       f"{GAP:.1f}",
    }
    inks = {
        "identical": "--confirm",
        "related":   "--mark",
        "mismatch":  "--challenge",
        "gap":       "--quiet",
    }

    rows = []
    for state in _STATES:
        count  = counts.get(state, 0)
        detail = _STATE_NOTE[state]
        if state == "related":
            detail += (
                f", written par for parallel ({PARALLEL:+.1f}), rel for relative"
                f" ({RELATIVE:+.1f}), dom for dominant and sub for subdominant"
                f" ({FIFTH:+.1f})"
            )
            seen = ", ".join(
                f"{name} {relations[name]}"
                for name in ("parallel", "relative", "dominant", "subdominant")
                if relations[name]
            )
            if seen:
                detail += f". Seen here: {seen}"
        rows.append(
            '<tr>'
            f'<td class="gutter">{_gutter_svg(count, total, inks[state])}</td>'
            f'<td class="count">{count}'
            f'<span class="unit"> column{"" if count == 1 else "s"}</span></td>'
            f'<td class="state"><span class="glyph">{_MARKS[state]}</span> {state}</td>'
            f'<td class="means">{detail}.</td>'
            f'<td class="score">{scores[state]}</td>'
            '</tr>'
        )

    return (
        '<table class="states">'
        '<thead><tr>'
        '<th class="gutter">share</th><th class="count">columns</th>'
        '<th>state, as drawn between the tracks</th><th>what it means</th>'
        '<th class="score">table score</th>'
        '</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
        f'<p class="caption">Gutter tick: this state\'s count on a scale running from'
        f' none of the {total} aligned columns at the left to all of them at the right.'
        ' Table score is the value the substitution matrix awards a column of that'
        ' kind, before the gap penalty accumulates.</p>'
    )


def _coverage_html(letter: str, name: str, seq: list[str],
                   window: tuple[int, int] | None) -> str:
    """One progression in full, with the aligned window marked inside it."""
    total = len(seq)
    head  = (
        '<div class="cov"><p class="cov-head">'
        f'<span class="who">{letter}</span>'
        f'<span class="what">{escape(name)}</span>'
    )

    if total == 0:
        return head + '<span class="span">no chords detected</span></p></div>'

    if window is None:
        body = (
            f'<span class="span">{total} chords, no aligned window to place</span></p>'
        )
        chips = "".join(f'<span>{escape(chord)}</span>' for chord in seq)
        return head + body + f'<div class="seq">{chips}</div></div>'

    start, end = window
    covered    = end - start
    left       = 100.0 * start / total
    width      = max(100.0 * covered / total, 1.0)
    body = (
        f'<span class="span">chords {start + 1} to {end} of {total},'
        f' {covered / total:.0%} of the progression</span></p>'
        '<div class="axis">'
        f'<span class="win" style="left:{left:.2f}%;width:{width:.2f}%"></span>'
        f'<span class="end" style="left:{left:.2f}%"></span>'
        f'<span class="end" style="left:calc({left + width:.2f}% - 1px)"></span>'
        '</div>'
        f'<div class="axis-labels"><span>1</span><span>{total}</span></div>'
    )
    chips = "".join(
        f'<span class="{"in" if start <= i < end else ""}">{escape(chord)}</span>'
        for i, chord in enumerate(seq)
    )
    return head + body + f'<div class="seq">{chips}</div></div>'


def render_html_comparison(
    name_a: str, seq_a: list[str],
    name_b: str, seq_b: list[str],
    result: AlignmentResult,
    output_path: str | None = None,
) -> str:
    """HTML report of two chord progressions and the local alignment between them."""
    columns = _columns(result)
    longer  = seq_a if len(seq_a) >= len(seq_b) else seq_b
    score   = similarity_score(result, self_align_score(longer))

    if columns:
        hero = (
            '<div class="tracks">'
            f'<p class="track-key"><span class="who">A</span>'
            f'<span class="what">{escape(name_a)}</span></p>'
            f'<p class="track-key"><span class="who">B</span>'
            f'<span class="what">{escape(name_b)}</span></p>'
            '</div>'
            + _track_html(columns, name_a, name_b)
            + '<p class="caption">Each column is one aligned position. The mark between'
              ' the tracks names the state: an unbroken line is an identical chord, a'
              ' dashed line with the relationship written under it is a harmonically'
              ' related pair, a line broken in the middle is a mismatch, and a faint'
              ' horizontal stub against a hyphen in a recessed cell is a gap. Numbers'
              ' along the top count columns from the start of the alignment, not from'
              ' the start of either song.</p>'
        )
        states = (
            '<section><h2>How the columns scored</h2>'
            + _states_html(columns)
            + '</section>'
        )
    else:
        # A local alignment can genuinely find nothing, and saying so is more
        # useful than an empty track with a legend under it.
        if not seq_a and not seq_b:
            reason = "neither recording yielded a chord to align"
        elif not seq_a or not seq_b:
            reason = f"song {'A' if not seq_a else 'B'} yielded no chords to align"
        else:
            reason = ("every candidate window held enough unrelated pairs to cancel"
                      " its matches, so Smith-Waterman clamped the whole matrix to zero")
        hero = (
            f'<p class="empty">No local alignment scored above zero: {reason}.'
            ' The two progressions are given in full below, with no window marked.</p>'
        )
        states = ""

    facts = (
        '<div class="facts">'
        '<div class="fact"><span class="label">Similarity</span>'
        f'<span class="figure">{score.normalised:.0%}</span>'
        f'<p class="note">Verdict: {score.verdict}. Measured against a perfect'
        f' self-alignment of the longer progression, {len(longer)} chords.</p></div>'
        '<div class="fact"><span class="label">Identity</span>'
        f'<span class="figure">{result.identity:.0%}</span>'
        '<p class="note">Aligned columns holding the same chord in both songs. The rest'
        ' scored on harmonic relationship alone.</p></div>'
        '<div class="fact"><span class="label">Alignment score</span>'
        f'<span class="figure">{result.score:.1f}</span>'
        '<p class="note">Raw Smith-Waterman score at the best cell in the matrix.</p></div>'
        '<div class="fact"><span class="label">Aligned region</span>'
        f'<span class="figure">{len(columns)}</span>'
        '<p class="note">Columns in the highest-scoring local window, gaps'
        ' included.</p></div>'
        '</div>'
    )

    where_note = (
        "Each progression in full, in detection order, with the aligned window"
        " marked. The width of the mark against the width of the line is how much"
        " of that song the local alignment actually accounts for."
        if columns else
        "Each progression in full, in detection order. Nothing aligned, so there is"
        " no window to mark."
    )

    window_a = _window(seq_a, result.start_a, result.seq_a_aligned)
    window_b = _window(seq_b, result.start_b, result.seq_b_aligned)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HarmonicDNA: chord alignment</title>
<style>{_CSS}</style>
</head>
<body>
<div class="page">
<h1>HarmonicDNA chord alignment</h1>
<p class="lede">Smith-Waterman local alignment of the chord progressions detected in
two recordings. What follows is the single highest-scoring pair of windows, so a
strong result means the two songs share a passage, not that they are the same song.</p>

<section>
<h2>Inputs and result</h2>
<div class="inputs">
<div class="input"><span class="who">Song A</span>
<span class="what">{escape(name_a)}</span>
<span class="len num">{len(seq_a)} chords detected</span></div>
<div class="input"><span class="who">Song B</span>
<span class="what">{escape(name_b)}</span>
<span class="len num">{len(seq_b)} chords detected</span></div>
</div>
{facts}
</section>

<section>
<h2>Aligned region</h2>
{hero}
</section>

{states}

<section>
<h2>Where the region falls</h2>
<p>{where_note}</p>
{_coverage_html("A", name_a, seq_a, window_a)}
{_coverage_html("B", name_b, seq_b, window_b)}
</section>
</div>
</body>
</html>"""

    if output_path:
        from pathlib import Path
        Path(output_path).write_text(html, encoding="utf-8")
    return html
