"""Invoke the `souffle` binary on a built program, and build what it links."""

import re
import signal
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from dl.paths import FUNCTORS_LIB, FUNCTORS_SRC, PROGRAMS_DIR, SOLVERS_DIR

# The tempfile `_temp_source` hands Souffle, as it appears in Souffle's own
# messages and in the CPU-limit message. Every run names a fresh one, so a
# reader comparing two errors has to put the solver back in its place.
TEMP_NAME_RE = re.compile(r"\.tmp\w+\.dl")

# Souffle reports the fit-mode relations as unfed whenever it reads a
# solve-mode program, so the first error is what a compile failure is about.
FIRST_ERROR_RE = re.compile(r"^Error:", re.M)


def build_functors() -> None:
    """Compile lib_functors.cpp to the shared library Souffle loads at runtime.

    Skips when the artifact is newer than the source. Called once before the
    pool spins up — never per-pair, which would race. Solvers can't run without
    it (lib.dl's primitives call its functors), so a failure here is fatal.
    """
    if FUNCTORS_LIB.exists() and FUNCTORS_LIB.stat().st_mtime >= FUNCTORS_SRC.stat().st_mtime:
        return
    souffle_prefix = subprocess.run(
        ["brew", "--prefix", "souffle"], capture_output=True, text=True, check=True
    ).stdout.strip()
    subprocess.run(
        ["clang++", "-std=c++17", "-shared", "-fPIC",
         f"-I{souffle_prefix}/include",
         "-o", str(FUNCTORS_LIB), str(FUNCTORS_SRC)],
        check=True,
    )


@contextmanager
def _temp_source(built: str) -> Iterator[Path]:
    """Built source as a file Souffle can read.

    The file lives next to the originals so `#include "../lib.dl"` resolves.
    The dot prefix keeps it out of the `*.dl` solver glob.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", prefix=".tmp", suffix=".dl", dir=str(SOLVERS_DIR), delete=False
    ) as tf:
        tf.write(built)
        run_path = Path(tf.name)
    try:
        yield run_path
    finally:
        run_path.unlink(missing_ok=True)


def _run_source(
    built: str, stdin_text: str, extra_args: list[str] | None = None,
    cpu_limit: int = 5,
) -> str:
    """Write built source to a tempfile and run Souffle on it."""
    with _temp_source(built) as run_path:
        return _souffle(run_path, stdin_text, extra_args, cpu_limit)


def compile_check(built: str) -> str | None:
    """Souffle's complaint about `built`, or None when it compiles.

    `-g -` runs the parse and the semantic analyses and writes the generated
    C++ instead of evaluating, so a source-level error surfaces once, before
    any grid runs. A run that does not land in the timeout answers None: the
    check is an early report, and the pair runs still say what they hit.
    """
    try:
        with _temp_source(built) as run_path:
            result = subprocess.run(
                ["souffle", "-g", "-", "-w", "-L", str(PROGRAMS_DIR), "-lfunctors",
                 str(run_path)],
                capture_output=True, text=True, timeout=60,
            )
    except subprocess.TimeoutExpired:
        return None
    if result.returncode == 0:
        return None
    m = FIRST_ERROR_RE.search(result.stderr)
    detail = result.stderr[m.start():] if m else result.stderr
    return f"souffle exited {result.returncode}:\n{detail}"


def _souffle(
    dl_path: Path, stdin_text: str, extra_args: list[str] | None = None,
    cpu_limit: int = 5,
) -> str:
    # -L/-lfunctors load the functor shared library build_functors compiled —
    # lib.dl's primitives call into it.
    #
    # Two bounds on runaway souffle (some rule shapes can hang the evaluator
    # and exhaust system memory). The kernel CPU-time limit (`ulimit -t`, via
    # a sh wrapper — preexec_fn is unsafe under threads) counts only souffle's
    # own burn, so system load and EDR spawn stalls can't fake a failure. The
    # wall timeout backstops hangs that block without spinning; it stays low
    # so inefficient solvers surface. The default budgets one grid; a run fed
    # every example at once (fit) passes a limit scaled to what it carries.
    cmd = ["souffle", "-D-", "-w", "-L", str(PROGRAMS_DIR), "-lfunctors",
           *(extra_args or []), str(dl_path)]
    result = subprocess.run(
        ["/bin/sh", "-c", f'ulimit -t {cpu_limit}; exec "$0" "$@"', *cmd],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=2 * cpu_limit,
    )
    if result.returncode == -signal.SIGXCPU:
        raise RuntimeError(
            f"souffle exceeded the {cpu_limit}s CPU limit on {dl_path.name}")
    if result.returncode != 0:
        raise RuntimeError(f"souffle exited {result.returncode}:\n{result.stderr}")
    return result.stdout


def _pool_workers() -> int | None:
    """Cap Souffle-spawning pools at the performance-core count.

    A full sweep queues hundreds of CPU-bound Souffle processes; the default
    pool size (cores + 4) oversubscribes onto efficiency cores and inflates
    wall times.
    """
    try:
        out = subprocess.run(
            ["sysctl", "-n", "hw.perflevel0.logicalcpu"],
            capture_output=True, text=True, check=True,
        )
        return int(out.stdout)
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError):
        return None  # no asymmetric cores to avoid: default sizing
