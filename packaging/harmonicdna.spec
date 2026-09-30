# PyInstaller build for the Windows executable.
#
# Build with:  pyinstaller packaging/harmonicdna.spec --noconfirm
#
# This is a one-folder build, not a single .exe, and that is a startup-time
# decision. librosa brings numba, scipy, soundfile and their native libraries;
# the tree is a few hundred megabytes. A one-file build appends all of it to
# the executable and unpacks the lot into a temporary directory before the
# first line of application code runs, on every launch. The folder build maps
# the same files straight from disk.
#
# The cost is that the download is a zip containing HarmonicDNA.exe next to its
# libraries, instead of a lone file. That is a worse first impression and a
# better tenth one. codecartographer makes the opposite call because it is
# stdlib-only and weighs about 10 MB.
#
# librosa resolves most of its own submodules lazily through lazy_loader, and
# soundfile and soxr ship native libraries, so none of them can be found by
# walking import statements alone. They are collected explicitly.

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

binaries = (
    collect_dynamic_libs("soundfile")
    + collect_dynamic_libs("soxr")
    + collect_dynamic_libs("llvmlite")
)
datas = (
    collect_data_files("librosa")      # window functions and example metadata
    + collect_data_files("soundfile")  # libsndfile on Windows lives here
    + collect_data_files("soxr")
)

# librosa reaches its submodules through lazy_loader, which imports by name at
# call time. PyInstaller cannot see those, and a missing one fails only when a
# particular code path runs, which is the worst way to find out.
hiddenimports = (
    collect_submodules("librosa")
    + collect_submodules("soundfile")
    + [
        "harmonicdna.gui",
        "sklearn.utils._typedefs",
        "sklearn.neighbors._partition_nodes",
        "scipy.special._cdflib",
        "audioread",
        "lazy_loader",
        "numba.core.typing.builtins",
    ]
)

a = Analysis(
    ["entry.py"],
    pathex=[".."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    # Nothing here is imported by the application. Each arrives as a dependency
    # of a dependency and costs download size and startup scan time.
    excludes=[
        "pytest",
        "matplotlib",
        "PIL",
        "pandas",
        "IPython",
        "notebook",
        "setuptools",
        "pip",
        "pydoc_data",
        "numpy.f2py",
        "numpy.testing",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HarmonicDNA",
    debug=False,
    strip=False,
    upx=False,
    # No console: this opens a window, and a terminal flashing up behind it
    # looks broken. entry.py borrows the calling terminal when it is handed
    # arguments, so the command line still prints.
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="HarmonicDNA",
)
