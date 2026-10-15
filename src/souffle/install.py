"""The Souffle install that runs: the `souffle` binary `PATH` gives, its
identity, its header directory, and the preprocessor it calls."""

import os
import shutil
import subprocess
from functools import cache
from pathlib import Path


@cache
def preprocessor_flags() -> tuple[str, ...]:
    """The preprocessor Souffle calls, by its full path, where xcrun finds
    clang; Souffle's default otherwise."""
    try:
        clang = subprocess.run(["xcrun", "-f", "clang"], capture_output=True, text=True,
                               timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ()
    if not clang or not os.access(clang, os.X_OK):
        return ()
    return (f"--preprocessor={clang} -x c -E",)


def souffle_binary() -> Path | None:
    """The `souffle` binary `PATH` gives, with each link resolved; None
    where `PATH` gives none."""
    found = shutil.which("souffle")
    return None if found is None else Path(os.path.realpath(found))


def binary_identity() -> bytes:
    """The `souffle` binary `PATH` gives, by its resolved path,
    modification time and size, which a Homebrew upgrade changes, with no
    Souffle process; a marker of its own where `PATH` gives none."""
    binary = souffle_binary()
    if binary is None:
        return b"\1none"
    st = binary.stat()
    return f"{binary}\0{st.st_mtime_ns}\0{st.st_size}".encode()


def souffle_include() -> Path:
    """The header directory of the Souffle install that runs: `include/`
    beside the `bin/` that holds the `souffle` binary."""
    binary = souffle_binary()
    if binary is None:
        raise RuntimeError("no souffle binary on PATH")
    include = binary.parent.parent / "include"
    if not (include / "souffle" / "SouffleFunctor.h").is_file():
        raise RuntimeError(f"no Souffle headers under {include}")
    return include
