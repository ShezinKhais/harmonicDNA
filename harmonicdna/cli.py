"""HarmonicDNA CLI - compare two songs by their chord fingerprints."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from harmonicdna.chromagram import compute_chromagram
from harmonicdna.chord_detector import detect_chords, chords_to_sequence
from harmonicdna.aligner import align
from harmonicdna.scoring import similarity_score, self_align_score
from harmonicdna.visualiser import alignment_to_text, chord_timeline, render_html_comparison

# Windows consoles often default to cp1252, which mangles the non-ASCII
# characters in the output; force UTF-8 where the stream supports it.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

app     = typer.Typer(name="harmonicdna", add_completion=False)
console = Console()


@app.command("compare")
def compare_cmd(
    file_a: Path = typer.Argument(..., help="First audio file"),
    file_b: Path = typer.Argument(..., help="Second audio file"),
    html_out: Path = typer.Option(None, "--html", help="Save HTML comparison"),
    min_conf: float = typer.Option(0.5, "--min-confidence"),
):
    """Compare two audio files by chord-sequence alignment."""
    console.print(f"[bold]Analysing:[/bold] {file_a.name}")
    chroma_a = compute_chromagram(str(file_a))
    labels_a = detect_chords(chroma_a, min_confidence=min_conf)
    seq_a    = chords_to_sequence(labels_a)
    console.print(f"  {len(seq_a)} unique chords  {chord_timeline(labels_a)}")

    console.print(f"\n[bold]Analysing:[/bold] {file_b.name}")
    chroma_b = compute_chromagram(str(file_b))
    labels_b = detect_chords(chroma_b, min_confidence=min_conf)
    seq_b    = chords_to_sequence(labels_b)
    console.print(f"  {len(seq_b)} unique chords  {chord_timeline(labels_b)}")

    if not seq_a or not seq_b:
        console.print("[red]Could not extract chord sequences from one or both files.[/red]")
        raise typer.Exit(1)

    console.print("\n[bold]Aligning...[/bold]")
    result      = align(seq_a, seq_b)
    longer_seq  = seq_a if len(seq_a) >= len(seq_b) else seq_b
    max_score   = self_align_score(longer_seq)
    score       = similarity_score(result, max_score)

    panel_text = (
        f"Similarity : [bold]{score.normalised:.0%}[/bold]\n"
        f"Verdict    : [bold]{score.verdict}[/bold]\n"
        f"Identity   : {score.identity:.0%}\n"
        f"Raw SW score: {score.raw_score:.1f}\n\n"
        + alignment_to_text(result)
    )
    console.print(Panel(panel_text, title="Result", border_style="blue"))

    if html_out:
        render_html_comparison(file_a.name, seq_a, file_b.name, seq_b,
                                result, output_path=str(html_out))
        console.print(f"HTML saved -> {html_out}")


@app.command("gui")
def gui_cmd():
    """Open the desktop window: pick tracks, align them, read the result."""
    # Imported here rather than at module scope: tkinter is absent from some
    # Linux python builds, and the rest of the CLI must work without it.
    try:
        from harmonicdna.gui import run
    except ImportError as e:
        console.print(f"[red]The window needs tkinter, which this Python was "
                      f"built without ({e}).[/red]")
        raise typer.Exit(2)
    raise typer.Exit(run())


@app.command("chords")
def chords_cmd(
    file: Path = typer.Argument(..., help="Audio file to analyse"),
    min_conf: float = typer.Option(0.5, "--min-confidence"),
):
    """Detect and print the chord sequence of a single audio file."""
    console.print(f"[bold]Analysing:[/bold] {file.name}")
    chroma = compute_chromagram(str(file))
    labels = detect_chords(chroma, min_confidence=min_conf)
    seq    = chords_to_sequence(labels)
    if not seq:
        console.print("[red]No chords detected above the confidence threshold.[/red]")
        raise typer.Exit(1)
    console.print(f"  {len(labels)} frames, {len(seq)} unique chords")
    console.print(f"  Timeline: {chord_timeline(labels)}")
    console.print(f"  Sequence: {' -> '.join(seq)}")


if __name__ == "__main__":
    app()
