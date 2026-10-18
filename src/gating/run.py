"""One gate run: its runs over the stems, each under its shared hold of
the heavy commands' lock, the instructions each retires, and the
comparison of their outputs and counts with the accepted ones."""

import os
import re
import shutil
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Iterable, Sequence
from enum import Enum
from pathlib import Path

from cli.common import WALL_LIMIT_ENV
from controlled_markdown import mctx
from engine import checkout, rwlock
from engine.duration import FOOTER_RE
from gating.commands import (
    COMMANDS,
    DOCUMENTS,
    EXTS,
    SOLVERS,
    WITNESSES,
    GateCommand,
    dropped_stems,
    frozen_witness,
    keys_of,
)
from gating.deps import GATE_SCRIPT, TRACE, lines_of, pruning_lines, ranges
from gating.lines import Line, LineKind, same, slow
from gating.records import (
    AcceptedCount,
    RunSequence,
    Tracing,
    count_file,
    keep_counts,
    no_counts,
    read_counts,
    standing,
)
import instructions
from handbook.paths import DOCUMENTS_ENV

COUNT_EXT = ".instructions"
"""The extension of the file in `new/` holding a judged run's count of
instructions."""
RUN_COUNTS = "instructions.json"
"""The file under `<out-dir>/gate/` that holds the count of each judged
run, in the form of `records.COUNT_FILE`."""

TIME_LIMIT = 560
KILL_AFTER = 5
TIMEOUT_RC = 124
"""The exit code of a command stopped at `TIME_LIMIT`, as `timeout` gives."""

_ELAPSED_RE = re.compile(r" \([0-9.]+s\) ---$", re.M)
_LIMIT_RE = re.compile(r"^(time limit [0-9]+s; elapsed )[0-9]+s$", re.M)
_DROPPED = "runner and lib:"
OUT_MARK = "<out>/gate/"


class Label(Enum):
    """The label of a run's line in `times.txt`."""

    JUDGED = "pass1"
    DROPPED = "dropped"
    PREFIX = "prefix"


class Role(Enum):
    """What a run of a command on a stem is for."""

    JUDGED = Label.JUDGED
    """Its outputs and its count of instructions are judged."""
    DROPPED = Label.DROPPED
    """It runs, traced, on a stem of `STEMS` the command drops."""
    PREFIX = Label.PREFIX
    """It runs only for the cache state that the judged commands after it
    on the stem start from."""


type Sequenced = list[tuple[GateCommand, Role]]


def sequence(stem: str, cmds: Sequence[GateCommand], keys: set[str],
             dropped: set[str]) -> Sequenced:
    """The runs on `stem` of `cmds`, in their order, each with its role: a
    command whose key is in `keys` is judged, and one whose key is in
    `dropped` runs on a stem it drops. Each other command that runs on
    `stem` before the last judged one runs for the cache state."""
    judged = [i for i, c in enumerate(cmds) if c.key(stem) in keys]
    last = judged[-1] if judged else -1
    out: Sequenced = []
    for i, c in enumerate(cmds):
        key = c.key(stem)
        if key in keys:
            out.append((c, Role.JUDGED))
        elif key in dropped:
            out.append((c, Role.DROPPED))
        elif i < last and stem in c.stems:
            out.append((c, Role.PREFIX))
    return out


def each(stems: Iterable[str], run: Callable[[str], None]) -> None:
    errors: list[BaseException] = []

    def one(stem: str) -> None:
        try:
            run(stem)
        except BaseException as e:
            errors.append(e)
            raise

    threads = [threading.Thread(target=one, args=(s,)) for s in stems]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        raise RuntimeError(f"{len(errors)} stem sequences failed") from errors[0]


def _ended(pid: int, deadline: float) -> bool:
    """Whether the child `pid` ends by the monotonic time `deadline`; it
    stays unreaped."""
    delay = 0.0005
    while not instructions.exited(pid, block=False):
        if time.monotonic() >= deadline:
            return False
        time.sleep(delay)
        delay = min(delay * 2, 0.05)
    return True


def measured(argv: list[str], env: dict[str, str], counted: Path) -> tuple[int, bytes, int | None]:
    """`argv` run in the checkout's root with `env`, stopped at
    `TIME_LIMIT`; its exit code, or `TIMEOUT_RC` where it was stopped, its
    output and error output, and the instructions it retired: its own count
    plus the one its Python process writes to `counted`, as
    `instructions` gives, or None where it was stopped."""
    counted.unlink(missing_ok=True)
    proc = subprocess.Popen(argv, cwd=checkout.ROOT,
                            env={**env, instructions.COUNT_ENV: str(counted)},
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    stdout = proc.stdout
    if stdout is None:
        raise RuntimeError(f"the run of {argv} has no output pipe")
    chunks: list[bytes] = []
    reader = threading.Thread(target=lambda: chunks.append(stdout.read()))
    reader.start()
    stopped = not _ended(proc.pid, time.monotonic() + TIME_LIMIT)
    if stopped:
        os.kill(proc.pid, signal.SIGTERM)
        if not _ended(proc.pid, time.monotonic() + KILL_AFTER):
            os.kill(proc.pid, signal.SIGKILL)
            instructions.exited(proc.pid, block=True)
    own = instructions.retired(proc.pid)
    _, status, _ = os.wait4(proc.pid, 0)
    proc.returncode = os.waitstatus_to_exitcode(status)
    reader.join()
    stdout.close()
    if stopped:
        return TIMEOUT_RC, b"".join(chunks), None
    if not counted.exists():
        raise RuntimeError(f"the run of {argv} ended, and its Python process wrote no count "
                           f"of instructions to {counted}")
    return proc.returncode, b"".join(chunks), own + int(counted.read_text())


class Gate:
    """One gate run into `out/gate/`."""

    def __init__(self, out: Path, accepted: Path, traced: bool, covers: bool) -> None:
        self.dir = out.resolve() / "gate"
        self.new = self.dir / "new"
        self.wit = self.dir / "wit" / "cur"
        self.dropped = self.dir / "dropped"
        """The outputs, coverage data and dependencies of the runs on the
        stems of `STEMS` the commands drop."""
        self.prefix = self.dir / "prefix"
        """The outputs of the runs for the cache state alone."""
        self.documents = self.dir / "documents"
        """The copy of `DOCUMENTS` the context commands render."""
        self.accepted = accepted
        self.traced = traced
        """Whether each command that is not run for the cache state runs
        under `trace`."""
        self.tracing = Tracing.TRACED if traced else Tracing.UNTRACED
        self.covers = covers
        """Whether each command also runs on the stems of `STEMS` it drops,
        as `--coverage` gives."""
        self.counts = read_counts(count_file(accepted))[self.tracing]
        self.run_counts: dict[str, AcceptedCount] = {}
        """The count of each judged run, with the sequence it ran after."""
        self.shown = f"{checkout.shown(self.dir)}/"
        self.log_lock = threading.Lock()

    def traced_dirs(self, role: Role) -> tuple[Path, Path]:
        """The directories of the dependencies and of the coverage data of
        the traced runs of `role`."""
        base = self.dropped if role is Role.DROPPED else self.dir
        return base / "deps", base / "cov"

    def deps_of(self, role: Role, key: str) -> Path:
        return self.traced_dirs(role)[0] / f"{key}.json"

    def env(self, cache: Path, hold: rwlock.Hold) -> dict[str, str]:
        return {**os.environ,
                rwlock.HOLD_ENV: hold,
                checkout.CACHE_ENV: str(cache),
                checkout.SOLVER_FILES_ENV: str(SOLVERS),
                checkout.WITNESSES_ENV: str(WITNESSES),
                DOCUMENTS_ENV: str(self.documents),
                WALL_LIMIT_ENV: str(TIME_LIMIT)}

    def normalize(self, raw: str) -> str:
        """`raw` with the lines naming the runner and lib dropped, the out
        directory written as `OUT_MARK`, whether absolute or from the
        checkout's root, and the times and the duration footer
        dropped."""
        lines = [ln for ln in raw.splitlines(keepends=True) if _DROPPED not in ln]
        text = FOOTER_RE.sub("", _ELAPSED_RE.sub(" ---", self.marked("".join(lines))))
        return _LIMIT_RE.sub(r"\1Ns", text)

    def marked(self, text: str) -> str:
        return text.replace(f"{self.dir}/", OUT_MARK).replace(self.shown, OUT_MARK)

    def witness_file(self, stem: str) -> Path:
        return self.wit / f"{stem}.wit.json"

    def arguments(self, cmd: GateCommand, stem: str) -> tuple[str, ...]:
        """The script and arguments of `cmd` on `stem`, as a `RunSequence`
        records them: each absolute path as a command's output prints it,
        after `normalize`."""
        def recorded(arg: str) -> str:
            path = Path(arg)
            return self.marked(str(checkout.shown(path))) if path.is_absolute() else arg
        return (cmd.script, *map(recorded, cmd.argv(stem, self.witness_file(stem))))

    def run_one(self, cmd: GateCommand, stem: str, role: Role, cache: Path
                ) -> int | None:
        """`cmd` on `stem` under its own shared hold of the heavy commands'
        lock, its normalized output, witness file and exit code written to
        the directory of its role; the instructions it retired, as
        `measured` gives them."""
        wf = self.witness_file(stem)
        if cmd.takes_witness_file:
            shutil.copyfile(frozen_witness(stem), wf)
        key = cmd.key(stem)
        script = [str(checkout.scripts() / cmd.script), *cmd.argv(stem, wf)]
        if self.traced and role is not Role.PREFIX:
            script = [str(checkout.ROOT / GATE_SCRIPT), TRACE, str(self.deps_of(role, key)),
                      str(self.traced_dirs(role)[1] / f".coverage.{key}"), *script]
        argv = ["uv", "run", "--project", str(checkout.ROOT), "python", *script]
        base = self.directory(role) / key
        with rwlock.taken(rwlock.Hold.SHARED) as hold:
            rc, raw, count = measured(argv, self.env(cache, hold), Path(f"{base}.counted"))
        Path(f"{base}.raw").write_bytes(raw)
        Path(f"{base}.txt").write_text(self.normalize(raw.decode()))
        if "wit.json" in cmd.exts:
            shutil.copyfile(wf, f"{base}.wit.json")
        Path(f"{base}.rc").write_text(f"{rc}\n")
        with self.log_lock, open(self.dir / "times.txt", "a") as fh:
            fh.write(f"{cmd.name} {stem} {role.value.value} rc={rc} instructions={count}\n")
        return count

    def directory(self, role: Role) -> Path:
        match role:
            case Role.JUDGED:
                return self.new
            case Role.DROPPED:
                return self.dropped
            case Role.PREFIX:
                return self.prefix

    def compare(self, cmd: GateCommand, stem: str, count: int | None,
                after: RunSequence) -> list[Line]:
        """The judged run's lines: a `DIFF` line per output file that
        differs from the accepted one, and, where it was not stopped at
        `TIME_LIMIT` and so has its count `count`, which ran after `after`,
        a `SLOW` line where that count grew past the accepted one, as
        `scripts/gate.py --help` gives each."""
        key = cmd.key(stem)
        lines = [Line(LineKind.DIFF, cmd.name, stem, ext) for ext in cmd.exts
                 if not same(self.accepted / f"{key}.{ext}", self.new / f"{key}.{ext}")]
        if count is None:
            return lines
        Path(self.new / f"{key}{COUNT_EXT}").write_text(f"{count}\n")
        self.run_counts[key] = AcceptedCount(count, after)
        accepted = standing(self.counts, key, after)
        grown = None if accepted is None else slow(cmd.name, stem, count, accepted)
        return lines if grown is None else [*lines, grown]

    def stem_runs(self, stem: str, runs: Sequenced, lines: list[Line]) -> None:
        """The runs `runs` on `stem`, in order, the lines of the judged ones
        added to `lines`."""
        for i, (cmd, role) in enumerate(runs):
            count = self.run_one(cmd, stem, role, self.cache(stem))
            if role is Role.JUDGED:
                after = tuple((c.key(stem), self.arguments(c, stem)) for c, _ in runs[:i])
                lines += self.compare(cmd, stem, count, after)

    def cache(self, stem: str) -> Path:
        return self.dir / "cache" / stem

    def dropped_keys(self, cmd: GateCommand, keys: set[str]) -> list[str]:
        """The keys of the runs of `cmd` on the stems of `STEMS` it drops,
        where the run covers them and `keys` holds the command's key on
        each of its own stems."""
        if not self.covers or not keys_of([cmd]) <= keys:
            return []
        return [cmd.key(s) for s in dropped_stems(cmd)]

    def coverage_lines(self, cmds: Sequence[GateCommand], keys: set[str]) -> list[str]:
        """The `coverage:` line of each command of `cmds` that ran on the
        stems of `STEMS` it drops, after one naming the stems of its traced
        runs that wrote no dependencies, then one naming the commands that ran on
        only part of their own stems and so got none."""
        if not self.covers:
            return []
        pruning = pruning_lines()
        out: list[str] = []
        for c in cmds:
            dropped = self.dropped_keys(c, keys)
            if not dropped:
                continue
            own_deps = {s: self.deps_of(Role.JUDGED, c.key(s)) for s in c.stems}
            dropped_deps = {s: self.deps_of(Role.DROPPED, c.key(s)) for s in dropped_stems(c)}
            no_data = [s for s, d in (*own_deps.items(), *dropped_deps.items())
                       if not d.exists()]
            if no_data:
                out.append(mctx("coverage: {cmd}: its runs on {stems} wrote no dependencies, "
                                "and count as covering no line").format(
                    cmd=c.name, stems=", ".join(no_data)))
            own = lines_of(own_deps.values())
            every = lines_of(dropped_deps.values())
            gaps = {p: rest for p in sorted(every)
                    if (rest := every[p] - own.get(p, frozenset()) - pruning.get(p, frozenset()))}
            if not gaps:
                out.append(mctx("coverage: {cmd}: its runs on its own stems cover every line "
                                "its runs on all of STEMS cover, the run cache's "
                                "pruning lines left out").format(cmd=c.name))
                continue
            out.append(mctx("coverage: {cmd}: its runs on all of STEMS cover these lines, "
                            "and its runs on its own stems do not: {lines}").format(
                cmd=c.name, lines="; ".join(
                    f"{p} {', '.join(str(a) if a == b else f'{a}-{b}' for a, b in ranges(ns))}"
                    for p, ns in gaps.items())))
        partial = [c.name for c in cmds if dropped_stems(c)
                   and keys_of([c]) & keys and not keys_of([c]) <= keys]
        if partial:
            out.append(mctx("coverage: {cmds}: no coverage line, since not every one of "
                            "their own stems ran").format(cmds=", ".join(partial)))
        return out

    def run(self, cmds: Sequence[GateCommand], keys: set[str]) -> list[Line]:
        """The runs of `cmds` on their stems, each stem's lines written to its
        log, and the count of each judged run to `RUN_COUNTS`; the lines,
        the stems in order. The runs are those `scripts/gate.py --help`
        gives, in its order."""
        for d in (self.new, self.wit, *self.traced_dirs(Role.JUDGED)):
            d.mkdir(parents=True, exist_ok=True)
        dropped = {k for c in cmds for k in self.dropped_keys(c, keys)}
        if dropped:
            for d in self.traced_dirs(Role.DROPPED):
                d.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(self.documents, ignore_errors=True)
        shutil.copytree(DOCUMENTS, self.documents)
        stems = sorted({s for c in cmds for s in (*c.stems, *dropped_stems(c))
                        if c.key(s) in keys | dropped})
        runs = {s: sequence(s, list(COMMANDS.values()), keys, dropped) for s in stems}
        if any(r is Role.PREFIX for s in stems for _, r in runs[s]):
            self.prefix.mkdir(parents=True, exist_ok=True)
        lines: dict[str, list[Line]] = {s: [] for s in stems}
        for s in stems:
            shutil.rmtree(self.cache(s), ignore_errors=True)
            self.cache(s).mkdir(parents=True)
        try:
            each(stems, lambda s: self.stem_runs(s, runs[s], lines[s]))
        finally:
            for s in stems:
                (self.dir / f"log-{s}.txt").write_text("".join(f"{ln}\n" for ln in lines[s]))
                shutil.rmtree(self.cache(s), ignore_errors=True)
        counts = no_counts()
        counts[self.tracing] = self.run_counts
        keep_counts(self.dir / RUN_COUNTS, counts)
        out = [ln for s in stems for ln in lines[s]]
        (self.dir / "log.txt").write_text("")
        self.log(out)
        return out

    def log(self, lines: Iterable[object]) -> None:
        """`lines` added to the run's log, one per line."""
        with open(self.dir / "log.txt", "a") as fh:
            fh.write("".join(f"{ln}\n" for ln in lines))
