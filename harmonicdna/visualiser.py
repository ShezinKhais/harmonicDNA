"""Visualise chord sequences and alignment results."""

from __future__ import annotations

from harmonicdna.aligner import AlignmentResult
from harmonicdna.chord_detector import ChordLabel


_CHORD_COLORS = {
    "maj": "#4f8ef7",
    "min": "#f7a54f",
}


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


def render_html_comparison(
    name_a: str, seq_a: list[str],
    name_b: str, seq_b: list[str],
    result: AlignmentResult,
    output_path: str = None,
) -> str:
    """HTML page showing two chord sequences and their alignment."""
    def _seq_html(seq):
        parts = []
        for chord in seq:
            kind  = "min" if chord.endswith("min") else "maj"
            color = _CHORD_COLORS[kind]
            parts.append(
                f'<span style="background:{color};color:#000;'
                f'padding:2px 6px;border-radius:4px;margin:2px;'
                f'display:inline-block;font-size:.85rem">{chord}</span>'
            )
        return " ".join(parts)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>HarmonicDNA Comparison</title>
<style>body{{background:#111;color:#eee;font-family:monospace;padding:2rem}}
pre{{background:#1a1a1a;padding:1rem;border-radius:8px}}</style></head><body>
<h1>HarmonicDNA - Chord Alignment</h1>
<h2>{name_a}</h2><p>{_seq_html(seq_a)}</p>
<h2>{name_b}</h2><p>{_seq_html(seq_b)}</p>
<h2>Alignment</h2><pre>{alignment_to_text(result)}</pre>
</body></html>"""

    if output_path:
        from pathlib import Path
        Path(output_path).write_text(html, encoding="utf-8")
    return html
