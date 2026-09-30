"""Desktop window for HarmonicDNA.

Everything ``compare`` and ``chords`` do on the command line, in one window:
pick two tracks, watch the pipeline run, and read the alignment as coloured
chords rather than as a line of text.

Built on tkinter, which ships with Python, so the window costs the project no
dependency it did not already have.

Two rules shape the code. Decoding audio and matching 24 templates against
every frame takes seconds, so the pipeline runs on a worker thread and reports
each stage back through a queue that the Tk event loop polls; run inline it
freezes the window for the whole analysis. And the score is never shown alone:
a high score with low identity means the songs are harmonically parallel
rather than the same passage, and the window says so, because the number by
itself invites exactly the wrong reading.
"""

from __future__ import annotations

import ctypes
import queue
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, ttk

from harmonicdna.aligner import GAP, align
from harmonicdna.chord_detector import chords_to_sequence, detect_chords
from harmonicdna.chromagram import compute_chromagram
from harmonicdna.scoring import self_align_score, similarity_score

BG = "#0b0c0e"
PANEL = "#111318"
PANEL2 = "#16181c"
GRID = "#1a1a1a"
BORDER = "#262a30"
SOFT = "#22262c"
TEXT = "#e8e9ea"
DIM = "#9aa0a8"
FAINT = "#6f757e"
MUTED = "#4a4f57"
MAJ = "#4f8ef7"
MIN = "#f7a54f"
BAD = "#f85149"

FONT = "Segoe UI"
MONO = "Consolas"

AUDIO_TYPES = [("Audio", "*.mp3 *.wav *.flac *.ogg *.m4a *.aiff"), ("All files", "*.*")]

_DWMWA_DARK = 20
_DWMWA_DARK_OLD = 19
_DWMWA_BORDER_COLOR = 34
_DWMWA_CAPTION_COLOR = 35
_DWMWA_TEXT_COLOR = 36


def _colorref(hex_colour: str) -> int:
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return (b << 16) | (g << 8) | r


def _blend_titlebar(window: tk.Tk) -> None:
    """Ask Windows to paint the caption to match the window.

    Tk owns the client area but not the title bar, which Windows paints in the
    system light theme by default: a white caption above a near-black window
    reads as two applications stacked. Best-effort everywhere else.
    """
    if sys.platform != "win32":
        return
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        dwm = ctypes.windll.dwmapi

        def _set(attr: int, value: int) -> bool:
            v = ctypes.c_int(value)
            return dwm.DwmSetWindowAttribute(
                hwnd, attr, ctypes.byref(v), ctypes.sizeof(v)) == 0

        if not _set(_DWMWA_DARK, 1):
            _set(_DWMWA_DARK_OLD, 1)
        _set(_DWMWA_CAPTION_COLOR, _colorref(PANEL2))
        _set(_DWMWA_TEXT_COLOR, _colorref(DIM))
        _set(_DWMWA_BORDER_COLOR, _colorref(PANEL2))
    except (AttributeError, OSError):
        pass


def chord_colour(label: str) -> str:
    """Blue for major, orange for minor, grey for anything unparseable.

    The same split visualiser.py uses, so the window and the saved HTML colour
    a given chord identically.
    """
    if label.endswith("maj"):
        return MAJ
    if label.endswith("min"):
        return MIN
    return MUTED


# The substitution table, spelled out for the legend. Kept beside the aligner's
# constants rather than duplicating their values as literals in the UI.
from harmonicdna.aligner import FIFTH, PARALLEL, RELATIVE, SAME, UNRELATED  # noqa: E402

_LEGEND = [
    ("same chord", SAME, TEXT),
    ("parallel major/minor", PARALLEL, TEXT),
    ("relative major/minor", RELATIVE, TEXT),
    ("fifth (same quality)", FIFTH, TEXT),
    ("unrelated", UNRELATED, DIM),
    ("gap", GAP, DIM),
]

_STAGES = ["Beat-synchronous chroma", "Template matching",
           "Smoothing and dedup", "Smith-Waterman fill"]


@dataclass
class Source:
    """One of the two tracks, and whatever is known about it so far."""
    path: Path | None = None
    labels: list | None = None
    seq: list[str] | None = None

    @property
    def name(self) -> str:
        return self.path.name if self.path else "No file selected"


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.queue: queue.Queue = queue.Queue()
        self.busy = False
        self.a = Source()
        self.b = Source()
        self.mode = "compare"

        root.title("HarmonicDNA")
        root.configure(bg=BG)
        root.geometry("1060x820")
        root.minsize(900, 680)
        _blend_titlebar(root)

        self.min_conf = tk.DoubleVar(value=0.5)
        self.gap = tk.DoubleVar(value=GAP)

        self._build()
        self.root.after(80, self._pump)

    # ---------- chrome ----------

    def _build(self) -> None:
        head = tk.Frame(self.root, bg=PANEL2, height=44)
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Label(head, text="HarmonicDNA", bg=PANEL2, fg=TEXT,
                 font=(FONT, 12, "bold")).pack(side="left", padx=16)
        self.tabs = {}
        for name, label in (("compare", "Compare"), ("chords", "Chords")):
            b = tk.Label(head, text=label, bg=PANEL2, fg=FAINT, font=(MONO, 10), cursor="hand2")
            b.pack(side="left", padx=10)
            b.bind("<Button-1>", lambda _e, n=name: self._switch(n))
            self.tabs[name] = b
        self.head_note = tk.Label(head, text="", bg=PANEL2, fg=FAINT, font=(MONO, 9))
        self.head_note.pack(side="right", padx=16)

        self.body = tk.Frame(self.root, bg=BG)
        self.body.pack(fill="both", expand=True, padx=20, pady=16)

        self._build_sources()
        self._build_controls()

        # The lower half swaps between three things: a prompt, the running
        # pipeline, and the result. They are separate frames rather than one
        # frame being rewritten, so a slow render never shows a half-cleared UI.
        self.stage = tk.Frame(self.body, bg=BG)
        self.stage.pack(fill="both", expand=True, pady=(16, 0))
        self._show_idle()
        self._switch("compare")

    def _build_sources(self) -> None:
        self.sources = tk.Frame(self.body, bg=BG)
        self.sources.pack(fill="x")
        self.sources.columnconfigure(0, weight=1, uniform="s")
        self.sources.columnconfigure(1, weight=1, uniform="s")
        self.cards = {}
        for col, (key, tag, colour) in enumerate((("a", "SEQ A", MAJ), ("b", "SEQ B", MIN))):
            card = tk.Frame(self.sources, bg=PANEL, highlightthickness=1,
                            highlightbackground=BORDER, highlightcolor=BORDER)
            card.grid(row=0, column=col, sticky="nsew", padx=(0, 10) if col == 0 else (10, 0))
            tk.Label(card, text=tag, bg=PANEL, fg=colour, font=(MONO, 9, "bold"),
                     anchor="w").pack(fill="x", padx=16, pady=(12, 0))
            drop = tk.Label(card, text="click to choose audio\nmp3  wav  flac  ogg",
                            bg=PANEL2, fg=FAINT, font=(MONO, 9), height=3, cursor="hand2")
            drop.pack(fill="x", padx=16, pady=8)
            drop.bind("<Button-1>", lambda _e, k=key: self._pick(k))
            name = tk.Label(card, text="No file selected", bg=PANEL, fg=FAINT,
                            font=(FONT, 10, "bold"), anchor="w")
            name.pack(fill="x", padx=16)
            meta = tk.Label(card, text="anything librosa can decode", bg=PANEL, fg=MUTED,
                            font=(MONO, 8), anchor="w")
            meta.pack(fill="x", padx=16, pady=(2, 14))
            self.cards[key] = {"drop": drop, "name": name, "meta": meta}

    def _build_controls(self) -> None:
        bar = tk.Frame(self.body, bg=PANEL, highlightthickness=1,
                       highlightbackground=BORDER, highlightcolor=BORDER)
        bar.pack(fill="x", pady=(14, 0))
        self.slider_conf = self._slider(bar, "min-confidence", self.min_conf, 0.1, 0.9, 0.05)
        self.slider_gap = self._slider(bar, "gap penalty", self.gap, -2.0, 0.0, 0.1)
        self.go = tk.Button(bar, text="Align sequences", command=self._start, relief="flat",
                            bd=0, cursor="hand2", font=(FONT, 10, "bold"), bg=MAJ,
                            fg="#08121f", activebackground="#7fadfa",
                            activeforeground="#08121f", padx=20, pady=8)
        self.go.pack(side="right", padx=16, pady=12)

    def _slider(self, parent, label, var, lo, hi, step):
        """A thin track with a round handle, drawn rather than themed.

        tk.Scale paints its handle in the widget's own background colour, so on
        a dark panel the handle is invisible and the control looks like a bare
        groove. Drawing it on a canvas is both fixable and closer to the design.
        """
        box = tk.Frame(parent, bg=PANEL, width=214)
        box.pack(side="left", padx=16, pady=12)
        top = tk.Frame(box, bg=PANEL, width=214)
        top.pack(fill="x")
        tk.Label(top, text=label, bg=PANEL, fg=DIM, font=(MONO, 9)).pack(side="left")
        val = tk.Label(top, text=f"{var.get():.2f}", bg=PANEL, fg=TEXT, font=(MONO, 9))
        val.pack(side="right")

        w, h, m = 214, 20, 7
        cv = tk.Canvas(box, width=w, height=h, bg=PANEL, highlightthickness=0)
        cv.pack(pady=(6, 0))

        def draw() -> None:
            cv.delete("all")
            frac = (var.get() - lo) / (hi - lo) if hi > lo else 0.0
            x = m + frac * (w - 2 * m)
            y = h / 2
            cv.create_line(m, y, w - m, y, fill=SOFT, width=3, capstyle="round")
            cv.create_line(m, y, x, y, fill=MAJ, width=3, capstyle="round")
            cv.create_oval(x - 5.5, y - 5.5, x + 5.5, y + 5.5, fill=MAJ, width=0)
            val.configure(text=f"{var.get():.2f}")

        def set_from(event) -> None:
            if self.busy:
                return
            frac = min(1.0, max(0.0, (event.x - m) / (w - 2 * m)))
            # Snap to the same grid the CLI options use, so a value read off
            # this window can be typed at the command line unchanged.
            var.set(round((lo + frac * (hi - lo)) / step) * step)
            draw()

        cv.bind("<Button-1>", set_from)
        cv.bind("<B1-Motion>", set_from)
        draw()
        return box

    # ---------- modes ----------

    def _switch(self, mode: str) -> None:
        if self.busy:
            return
        self.mode = mode
        for name, widget in self.tabs.items():
            widget.configure(fg=TEXT if name == mode else FAINT)
        # Comparing needs two tracks; reading chords off one needs only the first.
        if mode == "chords":
            self.sources.columnconfigure(1, weight=0)
            self.cards["b"]["drop"].master.grid_remove()
            self.go.configure(text="Detect chords")
        else:
            self.sources.columnconfigure(1, weight=1)
            self.cards["b"]["drop"].master.grid()
            self.go.configure(text="Align sequences")
        self._show_idle()

    def _clear_stage(self) -> None:
        for child in self.stage.winfo_children():
            child.destroy()

    def _show_idle(self) -> None:
        self._clear_stage()
        card = tk.Frame(self.stage, bg=PANEL, highlightthickness=1,
                        highlightbackground=BORDER, highlightcolor=BORDER)
        card.pack(fill="both", expand=True)
        msg = ("Choose two tracks, then align.\n"
               "The alignment is local: only the passages that match have to."
               if self.mode == "compare" else
               "Choose one track to read its chord sequence.")
        tk.Label(card, text=msg, bg=PANEL, fg=FAINT, font=(MONO, 10),
                 justify="left", anchor="nw").pack(fill="both", expand=True, padx=20, pady=18)

    # ---------- picking ----------

    def _pick(self, key: str) -> None:
        if self.busy:
            return
        chosen = filedialog.askopenfilename(title="Choose an audio file", filetypes=AUDIO_TYPES)
        if not chosen:
            return
        src = self.a if key == "a" else self.b
        src.path = Path(chosen)
        src.labels = src.seq = None
        card = self.cards[key]
        card["name"].configure(text=src.path.name, fg=TEXT)
        size = src.path.stat().st_size / (1024 * 1024)
        card["meta"].configure(text=f"{size:.1f} MB · not yet analysed", fg=FAINT)
        card["drop"].configure(text="click to replace", fg=MUTED)

    # ---------- running ----------

    def _start(self) -> None:
        if self.busy:
            return
        need_b = self.mode == "compare"
        if not self.a.path or (need_b and not self.b.path):
            self._error("Choose " + ("two tracks" if need_b else "a track") + " first.")
            return
        self.busy = True
        self.go.configure(state="disabled", bg=SOFT, fg=DIM)
        self._show_running()
        threading.Thread(target=self._work, daemon=True).start()

    def _show_running(self) -> None:
        self._clear_stage()
        card = tk.Frame(self.stage, bg=PANEL, highlightthickness=1,
                        highlightbackground=BORDER, highlightcolor=BORDER)
        card.pack(fill="both", expand=True)
        tk.Label(card, text="RUNNING THE PIPELINE", bg=PANEL, fg=DIM,
                 font=(MONO, 8, "bold"), anchor="w").pack(fill="x", padx=20, pady=(16, 10))
        self.stage_rows = []
        for name in _STAGES:
            row = tk.Frame(card, bg=PANEL)
            row.pack(fill="x", padx=20, pady=4)
            dot = tk.Label(row, text="○", bg=PANEL, fg=MUTED, font=(MONO, 11))
            dot.pack(side="left")
            lbl = tk.Label(row, text=name, bg=PANEL, fg=FAINT, font=(FONT, 10))
            lbl.pack(side="left", padx=8)
            note = tk.Label(row, text="waiting", bg=PANEL, fg=MUTED, font=(MONO, 9))
            note.pack(side="left", padx=8)
            self.stage_rows.append((dot, lbl, note))

    def _work(self) -> None:
        """Runs off the Tk thread; progress and results go back on the queue."""
        try:
            conf = float(self.min_conf.get())
            self.queue.put(("stage", (0, "running", "decoding audio")))
            chroma_a = compute_chromagram(str(self.a.path))
            self.queue.put(("stage", (0, "done", f"{chroma_a.shape[1]} frames")))

            self.queue.put(("stage", (1, "running", "24 templates")))
            labels_a = detect_chords(chroma_a, min_confidence=conf)
            self.queue.put(("stage", (1, "done", f"{len(labels_a)} frames kept")))

            self.queue.put(("stage", (2, "running", "collapsing repeats")))
            seq_a = chords_to_sequence(labels_a)
            self.a.labels, self.a.seq = labels_a, seq_a
            self.queue.put(("stage", (2, "done", f"{len(seq_a)} chords")))

            if self.mode == "chords":
                if not seq_a:
                    self.queue.put(("nochords", self.a.path.name))
                    return
                self.queue.put(("stage", (3, "done", "not needed")))
                self.queue.put(("chords", None))
                return

            chroma_b = compute_chromagram(str(self.b.path))
            labels_b = detect_chords(chroma_b, min_confidence=conf)
            seq_b = chords_to_sequence(labels_b)
            self.b.labels, self.b.seq = labels_b, seq_b

            if not seq_a or not seq_b:
                empty = self.a.path.name if not seq_a else self.b.path.name
                self.queue.put(("nochords", empty))
                return

            self.queue.put(("stage", (3, "running", f"{len(seq_a)}x{len(seq_b)} cells")))
            result = align(seq_a, seq_b, gap=float(self.gap.get()))
            longer = seq_a if len(seq_a) >= len(seq_b) else seq_b
            score = similarity_score(result, self_align_score(longer))
            self.queue.put(("stage", (3, "done", f"score {result.score:.1f}")))
            self.queue.put(("result", (result, score)))
        except ImportError as e:
            self.queue.put(("error", f"Audio decoding needs librosa, which is not installed "
                                     f"({e}). pip install -r requirements.txt"))
        except (OSError, ValueError) as e:
            self.queue.put(("error", f"Could not read the audio: {e}"))

    def _pump(self) -> None:
        try:
            while True:
                kind, payload = self.queue.get_nowait()
                if kind == "stage":
                    self._mark_stage(*payload)
                elif kind == "result":
                    self._finish(); self._show_result(*payload)
                elif kind == "chords":
                    self._finish(); self._show_chords()
                elif kind == "nochords":
                    self._finish(); self._show_nochords(payload)
                elif kind == "error":
                    self._finish(); self._error(payload)
        except queue.Empty:
            pass
        self.root.after(80, self._pump)

    def _mark_stage(self, i: int, state: str, note: str) -> None:
        if not getattr(self, "stage_rows", None) or i >= len(self.stage_rows):
            return
        dot, lbl, n = self.stage_rows[i]
        dot.configure(text="●" if state == "done" else "◐",
                      fg=MAJ if state == "done" else MIN)
        lbl.configure(fg=TEXT)
        n.configure(text=note, fg=FAINT)

    def _finish(self) -> None:
        self.busy = False
        self.go.configure(state="normal", bg=MAJ, fg="#08121f")

    # ---------- results ----------

    def _error(self, message: str) -> None:
        self._clear_stage()
        card = tk.Frame(self.stage, bg=PANEL, highlightthickness=1,
                        highlightbackground=BAD, highlightcolor=BAD)
        card.pack(fill="both", expand=True)
        tk.Label(card, text=message, bg=PANEL, fg=TEXT, font=(FONT, 11), wraplength=760,
                 justify="left", anchor="nw").pack(fill="both", expand=True, padx=20, pady=18)

    def _show_nochords(self, name: str) -> None:
        self._clear_stage()
        card = tk.Frame(self.stage, bg=PANEL, highlightthickness=1,
                        highlightbackground=BORDER, highlightcolor=BORDER)
        card.pack(fill="both", expand=True)
        tk.Label(card, text="NO CHORDS", bg=PANEL, fg=BAD, font=(MONO, 8, "bold"),
                 anchor="w").pack(fill="x", padx=20, pady=(16, 6))
        tk.Label(card, text=f"Could not extract a chord sequence from {name}.",
                 bg=PANEL, fg=TEXT, font=(FONT, 11), anchor="w").pack(fill="x", padx=20)
        tk.Label(card, text=f"Nothing cleared min-confidence {self.min_conf.get():.2f}. "
                            f"Lower the threshold and run again.",
                 bg=PANEL, fg=FAINT, font=(MONO, 9), anchor="w",
                 wraplength=740, justify="left").pack(fill="x", padx=20, pady=(6, 16))

    def _show_chords(self) -> None:
        self._clear_stage()
        card = tk.Frame(self.stage, bg=PANEL, highlightthickness=1,
                        highlightbackground=BORDER, highlightcolor=BORDER)
        card.pack(fill="both", expand=True)
        labels, seq = self.a.labels, self.a.seq
        tk.Label(card, text=f"{self.a.name} · {len(labels)} frames, {len(seq)} chords",
                 bg=PANEL, fg=DIM, font=(MONO, 9), anchor="w").pack(fill="x", padx=20, pady=(16, 10))

        tk.Label(card, text="TIMELINE", bg=PANEL, fg=DIM, font=(MONO, 8, "bold"),
                 anchor="w").pack(fill="x", padx=20)
        cv = tk.Canvas(card, bg=GRID, height=70, highlightthickness=0)
        cv.pack(fill="x", padx=20, pady=(6, 4))
        card.update_idletasks()
        self._draw_timeline(cv, labels)
        cv.bind("<Configure>", lambda _e, c=cv, l=labels: self._draw_timeline(c, l))
        tk.Label(card, text="bar height = template match confidence", bg=PANEL, fg=MUTED,
                 font=(MONO, 8), anchor="w").pack(fill="x", padx=20)

        tk.Label(card, text="SEQUENCE AFTER DEDUP", bg=PANEL, fg=DIM, font=(MONO, 8, "bold"),
                 anchor="w").pack(fill="x", padx=20, pady=(16, 6))
        wrap = tk.Frame(card, bg=PANEL)
        wrap.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        for i, name in enumerate(seq[:60]):
            tk.Label(wrap, text=name, bg=chord_colour(name), fg="#08121f",
                     font=(MONO, 9, "bold"), padx=7, pady=3).grid(
                row=i // 12, column=i % 12, padx=2, pady=2, sticky="w")

    def _draw_timeline(self, cv: tk.Canvas, labels: list) -> None:
        cv.delete("all")
        if not labels:
            return
        w = max(cv.winfo_width(), 200)
        h = cv.winfo_height() or 70
        step = w / len(labels)
        for i, lab in enumerate(labels):
            bh = max(3, lab.confidence * (h - 8))
            cv.create_rectangle(i * step, h - bh, (i + 1) * step - 0.5, h,
                                fill=chord_colour(lab.name), width=0)

    def _show_result(self, result, score) -> None:
        self._clear_stage()
        outer = tk.Frame(self.stage, bg=BG)
        outer.pack(fill="both", expand=True)

        # -- left: the verdict and the numbers behind it
        side = tk.Frame(outer, bg=PANEL, width=250, highlightthickness=1,
                        highlightbackground=BORDER, highlightcolor=BORDER)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="SIMILARITY", bg=PANEL, fg=DIM, font=(MONO, 8, "bold"),
                 anchor="w").pack(fill="x", padx=18, pady=(16, 2))
        tk.Label(side, text=f"{score.normalised:.0%}", bg=PANEL, fg=MAJ,
                 font=(FONT, 34, "bold"), anchor="w").pack(fill="x", padx=16)
        tk.Label(side, text=score.verdict, bg=PANEL, fg=TEXT, font=(FONT, 11),
                 anchor="w").pack(fill="x", padx=18, pady=(0, 10))
        span = len(result.seq_a_aligned)
        gaps = sum(1 for x in result.seq_a_aligned + result.seq_b_aligned if x == "-")
        for label, value in (("identity", f"{score.identity:.0%}"),
                             ("raw SW score", f"{result.score:.1f}"),
                             ("aligned span", f"{span} pos"),
                             ("gaps", str(gaps)),
                             ("start_a / start_b", f"{result.start_a} / {result.start_b}")):
            row = tk.Frame(side, bg=PANEL)
            row.pack(fill="x", padx=18, pady=3)
            tk.Label(row, text=label, bg=PANEL, fg=DIM, font=(MONO, 9)).pack(side="left")
            tk.Label(row, text=value, bg=PANEL, fg=TEXT, font=(MONO, 10)).pack(side="right")

        # The reading that the percentage alone does not give you.
        parallel = score.identity < 0.5 and score.normalised >= 0.5
        note = ("Carried by related chords, not shared ones: the same shape "
                "in a different key."
                if parallel else
                "High identity: the same passage, not a harmonically "
                "parallel one.")
        tk.Label(side, text=("PARALLEL, NOT IDENTICAL" if parallel else "SAME PASSAGE"),
                 bg=PANEL, fg=MIN if parallel else MAJ, font=(MONO, 8, "bold"),
                 anchor="w").pack(fill="x", padx=18, pady=(14, 4))
        tk.Label(side, text=note, bg=PANEL, fg=FAINT, font=(MONO, 8), wraplength=206,
                 justify="left", anchor="nw").pack(fill="x", padx=18, pady=(0, 14))

        # -- right: the alignment itself
        main = tk.Frame(outer, bg=PANEL, highlightthickness=1,
                        highlightbackground=BORDER, highlightcolor=BORDER)
        main.pack(side="left", fill="both", expand=True, padx=(14, 0))
        tk.Label(main, text="LOCAL ALIGNMENT", bg=PANEL, fg=DIM, font=(MONO, 8, "bold"),
                 anchor="w").pack(fill="x", padx=18, pady=(16, 8))
        cv = tk.Canvas(main, bg=GRID, height=96, highlightthickness=0)
        # tk.Scrollbar takes the native Windows look and ignores the colours
        # given to it; ttk's clam theme is the one that can actually be styled.
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("HD.Horizontal.TScrollbar", background=SOFT, troughcolor=GRID,
                        bordercolor=GRID, arrowcolor=FAINT, darkcolor=SOFT,
                        lightcolor=SOFT, relief="flat")
        style.map("HD.Horizontal.TScrollbar", background=[("active", MAJ)])
        bar = ttk.Scrollbar(main, orient="horizontal", command=cv.xview,
                            style="HD.Horizontal.TScrollbar")
        cv.configure(xscrollcommand=bar.set)
        cv.pack(fill="x", padx=18)
        bar.pack(fill="x", padx=18, pady=(3, 0))
        # Dragging the alignment is more natural than reaching for the bar.
        cv.bind("<Button-1>", lambda e: cv.scan_mark(e.x, e.y))
        cv.bind("<B1-Motion>", lambda e: cv.scan_dragto(e.x, e.y, gain=1))
        cv.bind("<MouseWheel>", lambda e: cv.xview_scroll(-e.delta // 120, "units"))
        self._draw_alignment(cv, result)

        legend = tk.Frame(main, bg=PANEL)
        legend.pack(fill="x", padx=18, pady=(14, 0))
        tk.Label(legend, text="WHY EACH COLUMN SCORED", bg=PANEL, fg=DIM,
                 font=(MONO, 8, "bold"), anchor="w").pack(fill="x", pady=(0, 6))
        for text, value, colour in _LEGEND:
            row = tk.Frame(legend, bg=PANEL)
            row.pack(fill="x")
            tk.Label(row, text=text, bg=PANEL, fg=colour, font=(MONO, 9)).pack(side="left")
            tk.Label(row, text=f"{value:+.1f}", bg=PANEL, fg=colour,
                     font=(MONO, 9)).pack(side="right")
        tk.Label(main, text="local, not global: the rest of each track is free to differ",
                 bg=PANEL, fg=MUTED, font=(MONO, 8), anchor="w").pack(
            fill="x", padx=18, pady=(10, 16))

    def _draw_alignment(self, cv: tk.Canvas, result) -> None:
        """Two rows of chord cells with the match glyph between them.

        The rows sit close enough that a column reads as one unit: the glyph
        belongs to the pair above and below it, not to either row alone.
        """
        cell_w, cell_h, pad = 62, 26, 5
        y_a, y_b = 8, 8 + cell_h + 22
        a, b = result.seq_a_aligned, result.seq_b_aligned
        for i, (ca, cb) in enumerate(zip(a, b)):
            x = 8 + i * (cell_w + pad)
            for y, label in ((y_a, ca), (y_b, cb)):
                gap = label == "-"
                cv.create_rectangle(x, y, x + cell_w, y + cell_h,
                                    fill=GRID if gap else chord_colour(label),
                                    outline=MUTED if gap else "", dash=(2, 2) if gap else ())
                cv.create_text(x + cell_w / 2, y + cell_h / 2, text=label,
                               fill=MUTED if gap else "#08121f", font=(MONO, 9, "bold"))
            # The glyph says how the pair scored: identical, related, or a gap.
            if ca == "-" or cb == "-":
                glyph, colour = "–", DIM
            elif ca == cb:
                glyph, colour = "|", DIM
            else:
                glyph, colour = "≈", MIN
            cv.create_text(x + cell_w / 2, y_a + cell_h + 11, text=glyph,
                           fill=colour, font=(MONO, 10))
        cv.configure(scrollregion=(0, 0, 16 + len(a) * (cell_w + pad), y_b + cell_h + 8))


def run() -> int:
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0
