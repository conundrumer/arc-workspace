"""Invoke the `souffle` binary on a built program, and build what it links."""

import hashlib
import json
import os
import random
import re
import shlex
import signal
import subprocess
import tempfile
import time
import zlib
from collections import defaultdict
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from controlled_markdown import mctx
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

# Souffle's report when a rule takes a record pattern to a Box a functor
# returned: it names the pattern's variable and asserts instead of erroring.
_PATTERN_ON_FUNCTOR_RE = re.compile(r"variable not grounded: (\w+) at \S+ \[(\d+):")

# Functor calls a rule's body holds after Souffle inlines the lib relations,
# from which the run reports the rule.
EXPRESSION_REPORT_MIN = 100

EXITED = mctx("souffle exited {code}:")
"""The line that heads what Souffle wrote when it failed."""

# A profile's `source-locator`: the file, then the span it covers.
LOCATOR_RE = re.compile(r"^(?P<file>.*) \[(?P<line>\d+):\d+-\d+:\d+\]$")

# Where a profile keeps its per-rule records, under one relation.
RULE_BUCKETS = ("non-recursive-rule", "recursive-rule")

# The CPU seconds one Souffle run of one grid gets.
CPU_LIMIT_SECONDS = 5

# The profiled rerun has to reach the end, so it runs under a raised limit.
# A pair that overruns the budget lands well inside this multiple of it, and
# a pair that does not is past reporting anyway.
PROFILE_CPU_FACTOR = 10


# One file per Souffle run, named by the hash of everything the run reads.
CACHE_DIR = REPO_ROOT / ".scratch" / "cache" / "souffle"

# What the stored runs may take on disk. A write now and then removes the
# least recently used runs past it, at most once per interval across every
# runner process, which the marker file's mtime records.
CACHE_CAP_BYTES = 20 << 30
CACHE_PRUNE_EVERY = 200
CACHE_PRUNE_INTERVAL_SECONDS = 300
CACHE_PRUNE_MARKER = ".pruned"
CACHE_ZLIB_LEVEL = 6

# A temp file older than this lost its writer to a kill before the rename.
CACHE_STALE_TEMP_SECONDS = 3600

# A preprocessor include, as Souffle's preprocessor resolves it: relative to
# the directory of the file that holds it.
INCLUDE_RE = re.compile(r'^\s*#include\s+"([^"]+)"', re.M)

# The flags every run passes ahead of its own. `-L` loads the functor library
# `build_functors` compiled, which lib.dl's relations call into.
BASE_FLAGS = ["-w", "-L", str(PROGRAMS_DIR), "-lfunctors"]


def _preprocessor_flags() -> list[str]:
    """The preprocessor Souffle calls, named by its full path. Souffle's own
    default is `gcc -x c -E`, and on macOS `gcc` is an xcrun shim that
    looks up clang on each call. Empty where xcrun is absent, which leaves
    Souffle's default."""
    try:
        clang = subprocess.run(["xcrun", "-f", "clang"], capture_output=True,
                               text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return []
    if not clang or not os.access(clang, os.X_OK):
        return []
    return [f"--preprocessor={shlex.quote(clang)} -x c -E"]


# Passed on every run and kept out of the cache key: the preprocessor's
# output is the same whichever path names it.
PREPROCESSOR_FLAGS = _preprocessor_flags()


@dataclass(frozen=True)
class _Ran:
    """What the runner takes from one Souffle run."""
    returncode: int
    stdout: str
    stderr: str


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
    it (lib.dl's relations call its functors), so a failure here is fatal.
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


@lru_cache(maxsize=1)
def _souffle_version() -> str:
    try:
        return subprocess.run(["souffle", "--version"], capture_output=True,
                              text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _included(text: str, base: Path, seen: set[Path], digest) -> None:
    """Feed `digest` each file `text` includes, and each file those include,
    once per file."""
    for name in INCLUDE_RE.findall(text):
        path = Path(os.path.normpath(base / name))
        if path in seen:
            continue
        seen.add(path)
        digest.update(f"\0include {path}\0".encode())
        try:
            body = path.read_text()
        except OSError:
            digest.update(b"missing")
            continue
        digest.update(body.encode())
        _included(body, path.parent, seen, digest)


def _cache_key(built: str, flags: list[str], stdin_text: str) -> str | None:
    """The hash of everything one run reads: the program, each file it
    includes, the functor library's source, the facts on stdin or in a `-F`
    directory, the flags, and the Souffle version. None for a run that writes
    a file of its own (`-p`), which a stored result cannot stand for."""
    if "-p" in flags:
        return None
    digest = hashlib.sha256()
    digest.update(_souffle_version().encode())
    digest.update(b"\0program\0" + built.encode())
    _included(built, SOLVERS_DIR, set(), digest)
    digest.update(b"\0functors\0" + FUNCTORS_SRC.read_bytes())
    digest.update(b"\0stdin\0" + stdin_text.encode())
    args = iter([*BASE_FLAGS, *flags])
    for arg in args:
        digest.update(b"\0flag\0" + arg.encode())
        if arg == "-F":
            # The fact directory is a fresh temp dir per run: its files count,
            # and its name does not.
            facts = Path(next(args))
            for f in sorted(facts.iterdir()):
                digest.update(f"\0fact {f.name}\0".encode() + f.read_bytes())
    return digest.hexdigest()


def _cache_read(key: str) -> _Ran | None:
    path = CACHE_DIR / f"{key}.json.z"
    try:
        ran = _Ran(**json.loads(zlib.decompress(path.read_bytes())))
        os.utime(path)
        return ran
    except (OSError, ValueError, TypeError, zlib.error):
        return None


def _cache_prune() -> None:
    """Remove the least recently used runs until the rest fit the cap, and
    the temp files a killed writer left. Skipped when a prune ran within the
    interval; two processes that prune at once only repeat each other."""
    marker = CACHE_DIR / CACHE_PRUNE_MARKER
    now = time.time()
    try:
        if now - marker.stat().st_mtime < CACHE_PRUNE_INTERVAL_SECONDS:
            return
    except FileNotFoundError:
        pass
    marker.touch()
    entries = []
    with os.scandir(CACHE_DIR) as scan:
        for entry in scan:
            try:
                st = entry.stat()
            except OSError:
                continue
            if entry.name.startswith(".tmp"):
                if now - st.st_mtime > CACHE_STALE_TEMP_SECONDS:
                    Path(entry.path).unlink(missing_ok=True)
            elif entry.name.endswith(".json.z"):
                entries.append((st.st_mtime, st.st_size, entry.path))
    total = sum(size for _, size, _ in entries)
    for _, size, path in sorted(entries):
        if total <= CACHE_CAP_BYTES:
            break
        Path(path).unlink(missing_ok=True)
        total -= size


def _cache_write(key: str, ran: _Ran) -> None:
    """Store `ran` under `key`. Several runner processes write at once, so the
    file is written under a temp name and renamed into place."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=CACHE_DIR, prefix=".tmp", suffix=".json.z", delete=False,
        ) as tf:
            tf.write(zlib.compress(json.dumps(asdict(ran)).encode(),
                                   CACHE_ZLIB_LEVEL))
        os.replace(tf.name, CACHE_DIR / f"{key}.json.z")
        if random.randrange(CACHE_PRUNE_EVERY) == 0:
            _cache_prune()
    except OSError:
        pass


def _cached_run(
    built: str, flags: list[str], stdin_text: str,
    invoke: Callable[[Path], _Ran], cpu_limit: int | None = None,
) -> _Ran:
    """`invoke` on `built` as a temp source, or the stored result of the same
    run. A run Souffle ended with a return code is stored, a failure among
    them. A run the CPU limit ended is stored under that limit, and raises
    the same `_CpuLimit` again: `ulimit -t` counts the run's own CPU
    seconds, so the load on the machine has no part in it. A run another
    signal or a timeout ended is not stored, since the load had a part in
    it."""
    key = _cache_key(built, flags, stdin_text)
    limited = None if key is None or cpu_limit is None else f"{key}-cpu{cpu_limit}"
    if key is not None and (hit := _cache_read(key)) is not None:
        return hit
    if limited is not None and (hit := _cache_read(limited)) is not None:
        raise _CpuLimit(hit.stderr)
    with _temp_source(built) as run_path:
        try:
            ran = invoke(run_path)
        except _CpuLimit as e:
            if limited is not None:
                _cache_write(limited, _Ran(-signal.SIGXCPU, "", str(e)))
            raise
    if key is not None and ran.returncode >= 0:
        _cache_write(key, ran)
    return ran


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
    cpu_limit: int = CPU_LIMIT_SECONDS, solver_path: Path | None = None,
) -> str:
    """Write built source to a tempfile and run Souffle on it.

    `solver_path` is the solver file `built` was assembled from. A caller
    that passes it asks for the profiled rerun a CPU-limit failure reports
    from, and the rule that rerun names is placed in that file. A caller
    that leaves it out — a search running many variants of one source —
    pays nothing for a run it drops anyway.
    """
    flags = extra_args or []
    try:
        ran = _cached_run(
            built, ["-D-", *flags], stdin_text,
            lambda run_path: _souffle(run_path, stdin_text, flags, cpu_limit),
            cpu_limit)
    except _CpuLimit as e:
        if solver_path is None:
            raise RuntimeError(str(e)) from None
        note = _slowest_rule_note(
            built, stdin_text, extra_args, cpu_limit, solver_path)
        raise RuntimeError(f"{e}\n{note}") from None
    return _stdout(ran)


def _explained(stderr: str) -> str:
    """Souffle's stderr, led by a plain statement of the one failure it
    reports as an assertion: a record pattern over a Box a functor returned.
    A Box a lib relation returns is read by a lib relation; a rule that has to
    take it apart binds it through a relation first."""
    m = _PATTERN_ON_FUNCTOR_RE.search(stderr)
    if m and "Assertion failed" in stderr:
        said = mctx(
            "a record pattern binds `{var}` (line {line}) from a Box a "
            "functor returned, which Souffle leaves ungrounded; read the Box "
            "through a lib relation, or derive it in a relation and take it "
            "apart there").format(var=m.group(1), line=m.group(2))
        return f"{said}\n{stderr}"
    return stderr


def expression_report(built: str) -> str | None:
    """One line naming the rule whose body holds the most functor calls
    after Souffle inlines the lib relations, when that count reaches
    EXPRESSION_REPORT_MIN. The count measures what one candidate tuple costs
    to evaluate; the line goes in the review, and says nothing about how the
    solver should read. None when the count is under the threshold or the
    program does not compile."""
    try:
        result = _cached_run(
            built, ["--show=transformed-datalog"], "",
            lambda run_path: _plain(["--show=transformed-datalog"], run_path))
    except subprocess.TimeoutExpired:
        return None
    if result.returncode != 0:
        return None
    largest: tuple[str, int] | None = None
    for rule in re.split(r"\.\s*\n", result.stdout):
        if ":-" not in rule:
            continue
        head = rule.split(":-", 1)[0].strip().split("(", 1)[0]
        calls = rule.count("@")
        if largest is None or calls > largest[1]:
            largest = (head, calls)
    if largest is None or largest[1] < EXPRESSION_REPORT_MIN:
        return None
    return mctx("expression size: {head}, {calls} functor calls after "
                "inlining").format(head=largest[0], calls=largest[1])


def compile_check(built: str) -> str | None:
    """Souffle's complaint about `built`, or None when it compiles.

    `-g -` runs the parse and the semantic analyses and writes the generated
    C++ instead of evaluating, so a source-level error surfaces once, before
    any grid runs. A run that does not land in the timeout answers None: the
    check is an early report, and the pair runs still say what they hit.
    """
    try:
        result = _cached_run(
            built, ["-g", "-"], "",
            lambda run_path: _plain(["-g", "-"], run_path))
    except subprocess.TimeoutExpired:
        return None
    if result.returncode == 0:
        return None
    m = FIRST_ERROR_RE.search(result.stderr)
    detail = result.stderr[m.start():] if m else _explained(result.stderr)
    return EXITED.format(code=result.returncode) + f"\n{detail}"


def _plain(flags: list[str], dl_path: Path) -> _Ran:
    """A Souffle run that evaluates nothing, under a wall timeout alone."""
    result = subprocess.run(
        ["souffle", *flags, *BASE_FLAGS, *PREPROCESSOR_FLAGS, str(dl_path)],
        input="", capture_output=True, text=True, timeout=60,
    )
    return _Ran(result.returncode, result.stdout, result.stderr)


def _stdout(ran: _Ran) -> str:
    """The run's stdout, or the failure Souffle reported, raised."""
    if ran.returncode != 0:
        raise RuntimeError(
            EXITED.format(code=ran.returncode) + f"\n{_explained(ran.stderr)}")
    return ran.stdout


def _souffle(
    dl_path: Path, stdin_text: str, extra_args: list[str] | None = None,
    cpu_limit: int = CPU_LIMIT_SECONDS,
) -> _Ran:
    # Two bounds on runaway souffle (some rule shapes can hang the evaluator
    # and exhaust system memory). The kernel CPU-time limit (`ulimit -t`, via
    # a sh wrapper — preexec_fn is unsafe under threads) counts only souffle's
    # own burn, so system load and EDR spawn stalls can't fake a failure. The
    # wall timeout backstops hangs that block without spinning; it stays low
    # so inefficient solvers surface. The default budgets one grid; a run fed
    # every example at once (determination) passes a limit scaled to what it carries.
    cmd = ["souffle", "-D-", *BASE_FLAGS, *PREPROCESSOR_FLAGS,
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
            mctx("souffle exceeded the {seconds}s CPU limit on {name}").format(
                seconds=cpu_limit, name=dl_path.name))
    return _Ran(result.returncode, result.stdout, result.stderr)


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
                _stdout(_souffle(run_path, stdin_text,
                                 [*(extra_args or []), "-p", str(profile_path)],
                                 PROFILE_CPU_FACTOR * cpu_limit))
                slowest = slowest_rule(json.loads(profile_path.read_text()))
                if slowest is None:
                    return mctx("no clause named: the profile holds none")
                path, line, secs, tuples = slowest
                site = _rule_site(path, line, run_path, solver_path)
        except (RuntimeError, OSError, ValueError, KeyError, TypeError,
                subprocess.SubprocessError):
            return mctx("no clause named: the rerun under a {seconds}s CPU "
                        "limit gave no profile").format(
                seconds=PROFILE_CPU_FACTOR * cpu_limit)
    return mctx("slowest clause: {site}, {secs:.1f}s CPU, {tuples} tuples").format(
        site=site, secs=secs, tuples=tuples)


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
