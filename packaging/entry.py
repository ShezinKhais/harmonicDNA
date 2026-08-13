"""Entry point for the packaged executable.

The .exe opens the window, because someone who downloaded a binary rather than
the source is not looking for a command line. The subcommands are still
reachable by passing arguments, so the same file serves both:

    HarmonicDNA.exe                     opens the window
    HarmonicDNA.exe chords song.mp3     runs the command line
    HarmonicDNA.exe --help              lists everything

The build is windowed, so it starts with no console attached and Python leaves
sys.stdout as None. print() writes to nothing in that state and does not
complain, which would make every subcommand appear to do nothing at all.
_attach_console reconnects to the terminal that launched the exe first.
"""

import multiprocessing
import sys


def _attach_console() -> None:
    """Reconnect stdout and stderr to the calling terminal, on Windows.

    A windowed build has no console of its own. AttachConsole borrows the one
    the user typed into, when there is one; launched from Explorer there is
    not, the call fails harmlessly, and output stays discarded, which is the
    right outcome for a double-click.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ATTACH_PARENT_PROCESS = -1
        if not ctypes.windll.kernel32.AttachConsole(ATTACH_PARENT_PROCESS):
            return
        for name in ("stdout", "stderr"):
            if getattr(sys, name) is None:
                setattr(sys, name, open("CONOUT$", "w", encoding="utf-8",
                                        errors="replace", buffering=1))
    except (AttributeError, OSError):
        pass


if __name__ == "__main__":
    # numba and joblib, both pulled in by librosa, start worker processes. A
    # frozen build re-executes itself to spawn one, so without this a child
    # would relaunch the whole interface instead of doing its work.
    multiprocessing.freeze_support()

    from harmonicdna.cli import app

    if len(sys.argv) > 1:
        _attach_console()
    else:
        sys.argv.append("gui")
    app()
