"""Invoke the `souffle` binary on a built program, and build what it links."""

import json
import re
import signal
import subprocess
import tempfile
import time
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from dl.paths import (
    FUNCTORS_LIB,
    FUNCTORS_SRC,
    PROGRAMS_DIR,
    REPO_ROOT,
    SOLVERS_DIR,
)
from dl.source import macro_line_map

# The tempfile `_temp_source` hands Souffle, as it appears in Souffle's own
# messages and in the CPU-limit message. Every run names a fresh one, so a
# reader comparing two errors has to put the solver back in its place.
TEMP_NAME_RE = re.compile(r"\.tmp\w+\.dl")

# Souffle reports the determination-mode relations as unfed whenever it reads a
# solve-mode program, so the first error is what a compile failure is about.
FIRST_ERROR_RE = re.compile(r"^Error:", re.M)

# A profile's `source-locator`: the file, then the span it covers.
LOCATOR_RE = re.compile(r"^(?P<file>.*) \[(?P<line>\d+):\d+-\d+:\d+\]$")

# Where a profile keeps its per-rule records, under one relation.
RULE_BUCKETS = ("non-recursive-rule", "recursive-rule")

# The profiled rerun has to reach the end, so it runs under a raised limit.
# A pair that overruns the budget lands well inside this multiple of it, and
# a pair that does not is past reporting anyway.
PROFILE_CPU_FACTOR = 10


class _CpuLimit(RuntimeError):
    """Souffle burned the CPU budget. Caught inside this module: what
    escapes it is a RuntimeError, as every other Souffle failure is."""


# A temp source older than this has no live run: a run that lost its process
# to a kill left it behind.
STALE_TEMP_SECONDS = 3600


def sweep_temp_sources(now: float | None = None) -> int:
    """Remove the temp sources no run owns, and return how many went.

    A run removes its own temp source when it ends, but a killed process
    removes nothing, so the files it held stay under `programs/solvers/`.
    """
    now = time.time() if now is None else now
    gone = 0
    for path in SOLVERS_DIR.glob(".tmp*.dl"):
        try:
            if now - path.stat().st_mtime > STALE_TEMP_SECONDS:
                path.unlink()
                gone += 1
        except OSError:
            continue
    return gone


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
    cpu_limit: int = 5, solver_path: Path | None = None,
) -> str:
    """Write built source to a tempfile and run Souffle on it.

    `solver_path` is the solver file `built` was assembled from. A caller
    that passes it asks for the profiled rerun a CPU-limit failure reports
    from, and the rule that rerun names is placed in that file. A caller
    that leaves it out — a search running many variants of one source —
    pays nothing for a run it drops anyway.
    """
    with _temp_source(built) as run_path:
        try:
            return _souffle(run_path, stdin_text, extra_args, cpu_limit)
        except _CpuLimit as e:
            if solver_path is None:
                raise RuntimeError(str(e)) from None
            note = _slowest_rule_note(
                built, stdin_text, extra_args, cpu_limit, solver_path)
            raise RuntimeError(f"{e}\n{note}") from None


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
    # every example at once (determination) passes a limit scaled to what it carries.
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
        raise _CpuLimit(
            f"souffle exceeded the {cpu_limit}s CPU limit on {dl_path.name}")
    if result.returncode != 0:
        raise RuntimeError(f"souffle exited {result.returncode}:\n{result.stderr}")
    return result.stdout


def _rule_records(relation: dict) -> Iterator[dict]:
    """The per-rule records under one relation. A recursive rule holds one
    record per iteration, so a bucket's values can nest."""
    for bucket in RULE_BUCKETS:
        pending = list(relation.get(bucket, {}).values())
        while pending:
            item = pending.pop()
            if not isinstance(item, dict):
                continue
            if "runtime" in item:
                yield item
            else:
                pending.extend(item.values())


def slowest_rule(profile: dict) -> tuple[str, int, float, int] | None:
    """The costliest rule of a Souffle profile as (file, line, seconds,
    tuples), or None when the profile names none.

    Rule text is what the evaluator runs, after inlining, so a rule stands
    for the place it was written at. Two records at one place — a rule run
    per iteration, or facts sharing a line — count as that place's one
    total. Runtimes are microseconds.
    """
    seconds: dict[tuple[str, int], float] = defaultdict(float)
    tuples: dict[tuple[str, int], int] = defaultdict(int)
    program = profile.get("root", {}).get("program", {})
    for relation in program.get("relation", {}).values():
        for record in _rule_records(relation):
            m = LOCATOR_RE.match(record.get("source-locator", ""))
            if m is None:
                continue
            site = (m["file"], int(m["line"]))
            runtime = record["runtime"]
            seconds[site] += (runtime["end"] - runtime["start"]) / 1e6
            tuples[site] += record.get("num-tuples", 0)
    if not seconds:
        return None
    site, secs = max(seconds.items(), key=lambda kv: kv[1])
    return site[0], site[1], secs, tuples[site]


def _rule_site(path: str, line: int, run_path: Path, solver_path: Path) -> str:
    """`file:line` a reader can open. A locator in the built tempfile points
    into macro-expanded source, so the line maps back to the solver's own
    file. Every other locator is a file the solver includes, lib.dl above
    all, and stands as it is."""
    if path != str(run_path):
        p = Path(path)
        rel = p.relative_to(REPO_ROOT) if p.is_relative_to(REPO_ROOT) else p
        return f"{rel}:{line}"
    line_map = macro_line_map(solver_path.read_text())
    if line <= len(line_map):
        line = line_map[line - 1]
    return f"{solver_path.name}:{line}"


def _slowest_rule_note(
    built: str, stdin_text: str, extra_args: list[str] | None,
    cpu_limit: int, solver_path: Path,
) -> str:
    """One line naming the rule that burned the most CPU.

    A profile only covers a run that reached the end, so the pair runs a
    second time, under a raised limit, with `-p`. That rerun can overrun the
    raised limit too, and Souffle can write a profile that names no rule;
    either way the note says so, and the message above it still stands.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        profile_path = Path(tmp_dir) / "profile.json"
        try:
            with _temp_source(built) as run_path:
                _souffle(run_path, stdin_text,
                         [*(extra_args or []), "-p", str(profile_path)],
                         PROFILE_CPU_FACTOR * cpu_limit)
                slowest = slowest_rule(json.loads(profile_path.read_text()))
                if slowest is None:
                    return "no rule named: the profile holds none"
                path, line, secs, tuples = slowest
                site = _rule_site(path, line, run_path, solver_path)
        except (RuntimeError, OSError, ValueError, KeyError, TypeError,
                subprocess.SubprocessError):
            return (f"no rule named: the rerun under a "
                    f"{PROFILE_CPU_FACTOR * cpu_limit}s CPU limit gave no "
                    "profile")
    return f"slowest rule: {site}, {secs:.1f}s CPU, {tuples} tuples"


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
