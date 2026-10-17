"""One gate run: its passes over the stems, the holds of the heavy
commands' lock they take, the comparison of their outputs and times, and
the writing of its times and outputs as accepted."""

import contextlib
import os
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Callable, Iterable, Iterator, Sequence
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
    Named,
    dropped_stems,
    frozen_witness,
    keys_of,
)
from gating.cpu import CpuSample, OutsideCpu
from gating.deps import GATE_SCRIPT, TRACE, lines_of, pruning_lines, ranges
from gating.lines import TIME_KINDS, Line, LineKind, same
from gating.records import (
    AcceptedTime,
    RunSequence,
    keep_loaded,
    keep_times,
    loaded_file,
    read_times,
    times_file,
)
from handbook.paths import DOCUMENTS_ENV

TIME_EXT = ".time"
"""The extension of the file in `new/` holding a cold run's time."""

TIME_LIMIT = 560
KILL_AFTER = 5
TIMEOUT_RC = 124
"""The exit code of a command stopped at `TIME_LIMIT`, as `timeout` gives."""

SLOW_FACTOR = 1.25
SLOW_MARGIN = 1.0

_ELAPSED_RE = re.compile(r" \([0-9.]+s\) ---$", re.M)
_LIMIT_RE = re.compile(r"^(time limit [0-9]+s; elapsed )[0-9]+s$", re.M)
_DROPPED = "runner and lib:"
OUT_MARK = "<out>/gate/"


class Label(Enum):
    """The label of a run's line in `times.txt`."""

    JUDGED = "pass1"
    WARM = "pass2"
    DROPPED = "dropped"
    PREFIX = "prefix"


class Role(Enum):
    """What a cold run of a command on a stem is for."""

    JUDGED = Label.JUDGED
    """Its outputs, and in a timed run its time, are judged, and in a timed
    run it runs in the warm pass too."""
    DROPPED = Label.DROPPED
    """It runs, traced, on a stem of `STEMS` the command drops."""
    PREFIX = Label.PREFIX
    """It runs only for the cache state that the judged commands after it
    on the stem start from."""


type Sequenced = list[tuple[GateCommand, Role]]


def sequence(stem: str, cmds: Sequence[GateCommand], keys: set[str], dropped: set[str],
             prefixed: bool) -> Sequenced:
    """The cold runs on `stem` of `cmds`, in their order, each with its
    role: a command whose key is in `keys` is judged, and one whose key is
    in `dropped` runs on a stem it drops. Where `prefixed`, each other
    command that runs on `stem` before the last judged one runs for the
    cache state."""
    judged = [i for i, c in enumerate(cmds) if c.key(stem) in keys]
    last = judged[-1] if prefixed and judged else -1
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


class Skipped(Exception):
    """A timed run whose hold was not free at once, and which ran no
    command; its text is the line that says so."""


class Gate:
    """One gate run into `out/gate/`."""

    def __init__(self, out: Path, accepted: Path, timed: bool, traced: bool,
                 covers: bool, tries: bool = False, prefixed: bool = False) -> None:
        self.dir = out.resolve() / "gate"
        self.new = self.dir / "new"
        self.warm = self.new / "warm"
        self.wit = self.dir / "wit" / "cur"
        self.dropped = self.dir / "dropped"
        """The outputs, coverage data and dependencies of the runs on the
        stems of `STEMS` the commands drop."""
        self.prefix = self.dir / "prefix"
        """The outputs of the runs for the cache state alone."""
        self.documents = self.dir / "documents"
        """The copy of `DOCUMENTS` the context commands render."""
        self.accepted = accepted
        self.timed = timed
        """Whether the run makes the warm pass and judges the cold times;
        `--outputs-only` clears it."""
        self.traced = traced
        """Whether each cold command runs under `trace`."""
        self.covers = covers
        """Whether each command also runs on the stems of `STEMS` it drops,
        as `--coverage` gives."""
        self.prefixed = timed or prefixed
        """Whether each command before the last judged one on a stem runs,
        untraced, for the cache state, in the order of `COMMANDS`."""
        self.tries = tries
        """Whether the cold pass takes its hold only where it is free at
        once (`rwlock.tried`), as `--since-timed` gives."""
        self.times_file = times_file(accepted)
        self.times = read_times(self.times_file)
        self.cold_times: dict[str, AcceptedTime] = {}
        """The time of each judged cold run, with the sequence it ran
        after."""
        self.loaded_file = loaded_file(accepted)
        self.shown = f"{checkout.shown(self.dir)}/"
        self.log_lock = threading.Lock()
        self.notice = rwlock.Notice()
        """The run's wait line for the shared holds of its commands."""

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

    @contextlib.contextmanager
    def held(self, under: rwlock.Hold | None) -> Iterator[rwlock.Hold]:
        """The hold one command runs under: `under`, the hold of its pass,
        or else the heavy commands' lock held shared for the command
        alone."""
        if under is not None:
            yield under
            return
        with rwlock.taken(rwlock.Hold.SHARED, self.notice) as hold:
            yield hold

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

    def run_one(self, cmd: GateCommand, stem: str, role: Role, cold: bool, cache: Path,
                under: rwlock.Hold | None) -> tuple[int, float, OutsideCpu | None]:
        """`cmd` on `stem` under the hold `held` gives, its normalized
        output, witness file and exit code written to the directory of its
        pass or its role; the exit code, the wall time, and, where it runs
        under an exclusive hold, the outside CPU over its run."""
        wf = self.witness_file(stem)
        if cmd.takes_witness_file:
            shutil.copyfile(frozen_witness(stem), wf)
        key = cmd.key(stem)
        script = [str(checkout.scripts() / cmd.script), *cmd.argv(stem, wf)]
        if self.traced and cold and role is not Role.PREFIX:
            script = [str(checkout.ROOT / GATE_SCRIPT), TRACE, str(self.deps_of(role, key)),
                      str(self.traced_dirs(role)[1] / f".coverage.{key}"), *script]
        argv = ["uv", "run", "--project", str(checkout.ROOT), "python", *script]
        base = self.directory(role, cold) / key
        with self.held(under) as hold:
            sample = CpuSample.now() if hold is rwlock.Hold.EXCLUSIVE else None
            start = time.time()
            proc = subprocess.Popen(argv, cwd=checkout.ROOT, env=self.env(cache, hold),
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            try:
                raw, _ = proc.communicate(timeout=TIME_LIMIT)
                rc = proc.returncode
            except subprocess.TimeoutExpired:
                proc.terminate()
                try:
                    raw, _ = proc.communicate(timeout=KILL_AFTER)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    raw, _ = proc.communicate()
                rc = TIMEOUT_RC
            wall = round(time.time() - start, 1)
            outside = None if sample is None else sample.outside(CpuSample.now())
        Path(f"{base}.raw").write_bytes(raw)
        Path(f"{base}.txt").write_text(self.normalize(raw.decode()))
        if "wit.json" in cmd.exts:
            shutil.copyfile(wf, f"{base}.wit.json")
        Path(f"{base}.rc").write_text(f"{rc}\n")
        label = role.value if cold else Label.WARM
        with self.log_lock, open(self.dir / "times.txt", "a") as fh:
            fh.write(f"{cmd.name} {stem} {label.value} rc={rc} wall={wall}s\n")
        return rc, wall, outside

    def directory(self, role: Role, cold: bool) -> Path:
        match role:
            case Role.JUDGED:
                return self.new if cold else self.warm
            case Role.DROPPED:
                return self.dropped
            case Role.PREFIX:
                return self.prefix

    def compare(self, cmd: GateCommand, stem: str, wall: float, after: RunSequence,
                outside: OutsideCpu | None) -> list[Line]:
        """The cold run's lines: a `DIFF` line per output file that differs
        from the accepted one, and in a timed run a `SLOW`, `LOADED` or
        `NOTIME` line for its time, which ran after `after`, as
        `scripts/gate.py --help` gives each."""
        key = cmd.key(stem)
        lines = [Line(LineKind.DIFF, cmd.name, stem, ext) for ext in cmd.exts
                 if not same(self.accepted / f"{key}.{ext}", self.new / f"{key}.{ext}")]
        if not self.timed:
            return lines
        if outside is None:
            raise ValueError(f"the cold run of {key} in a timed run has no outside CPU")
        Path(self.new / f"{key}{TIME_EXT}").write_text(f"{wall}\n")
        self.cold_times[key] = AcceptedTime(wall, after)
        accepted = self.standing(key, after)
        if accepted is None:
            other = ", accepted after another sequence" if key in self.times else ""
            lines.append(Line(LineKind.NOTIME, cmd.name, stem, f"time={wall}s{other}"))
        elif wall > SLOW_FACTOR * accepted + SLOW_MARGIN:
            kind = LineKind.LOADED if outside.cores > 1 else LineKind.SLOW
            lines.append(Line(kind, cmd.name, stem,
                              f"time={wall}s accepted={accepted}s {outside}"))
        return lines

    def standing(self, key: str, after: RunSequence) -> float | None:
        accepted = self.times.get(key)
        return accepted.seconds if accepted is not None and accepted.after == after else None

    def compare_warm(self, cmd: GateCommand, stem: str) -> list[Line]:
        """The warm run's lines: a `DIFF` line ending in `warm` per output
        file that differs from the cold run's."""
        key = cmd.key(stem)
        return [Line(LineKind.DIFF, cmd.name, stem, f"{ext} warm") for ext in cmd.exts
                if not same(self.new / f"{key}.{ext}", self.warm / f"{key}.{ext}")]

    def cold(self, stem: str, runs: Sequenced, under: rwlock.Hold | None,
             lines: list[Line]) -> None:
        """The cold pass of `runs` on `stem`, under the hold `held` gives,
        the lines of its judged runs added to `lines`."""
        for i, (cmd, role) in enumerate(runs):
            _, wall, outside = self.run_one(cmd, stem, role, True, self.cache(stem), under)
            if role is Role.JUDGED:
                after = tuple((c.key(stem), self.arguments(c, stem)) for c, _ in runs[:i])
                lines += self.compare(cmd, stem, wall, after, outside)

    def warm_pass(self, stem: str, runs: Sequenced, lines: list[Line]) -> None:
        """The warm pass of the judged runs of `runs` on `stem`, each under
        its own shared hold, their lines added to `lines`."""
        for cmd, role in runs:
            if role is Role.JUDGED:
                self.run_one(cmd, stem, role, False, self.cache(stem), None)
                lines += self.compare_warm(cmd, stem)

    def cache(self, stem: str) -> Path:
        return self.dir / "cache" / stem

    @contextlib.contextmanager
    def cold_hold(self, runs: bool) -> Iterator[rwlock.Hold | None]:
        """The hold the cold commands run under, or None where each takes
        its own. Where the process started under a hold, `rwlock.taken`
        gives that hold. Under `tries`, a hold that is not free at once is
        a `Skipped`."""
        if not (self.timed and runs):
            yield None
            return
        if self.tries:
            with rwlock.tried() as tried:
                if tried is None:
                    raise Skipped(rwlock.SKIP.format(
                        path=rwlock.lock_dir() / rwlock.LOCK_FILE))
                yield tried
            return
        with rwlock.taken(rwlock.Hold.EXCLUSIVE, rwlock.Notice()) as hold:
            yield hold

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
                                "its runs on all of STEMS cover").format(cmd=c.name))
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
        """The cold pass of `cmds` on their stems, and in a timed run the
        warm pass after it, each stem's lines written to its log; the
        lines, the stems in order. The commands of a timed run are those
        `scripts/gate.py --help` gives, in its order."""
        for d in (self.new, self.warm, self.wit, *self.traced_dirs(Role.JUDGED)):
            d.mkdir(parents=True, exist_ok=True)
        dropped = {k for c in cmds for k in self.dropped_keys(c, keys)}
        if dropped:
            for d in self.traced_dirs(Role.DROPPED):
                d.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(self.documents, ignore_errors=True)
        shutil.copytree(DOCUMENTS, self.documents)
        stems = sorted({s for c in cmds for s in (*c.stems, *dropped_stems(c))
                        if c.key(s) in keys | dropped})
        order = list(COMMANDS.values()) if self.prefixed else cmds
        runs = {s: sequence(s, order, keys, dropped, prefixed=self.prefixed) for s in stems}
        if any(r is Role.PREFIX for s in stems for _, r in runs[s]):
            self.prefix.mkdir(parents=True, exist_ok=True)
        lines: dict[str, list[Line]] = {s: [] for s in stems}
        for s in stems:
            shutil.rmtree(self.cache(s), ignore_errors=True)
            self.cache(s).mkdir(parents=True)
        try:
            with self.cold_hold(bool(stems)) as hold:
                if hold is None:
                    each(stems, lambda s: self.cold(s, runs[s], None, lines[s]))
                else:
                    for s in stems:
                        self.cold(s, runs[s], hold, lines[s])
                    judged = {c.key(s) for s in stems for c, r in runs[s] if r is Role.JUDGED}
                    keep_loaded(self.loaded_file, judged,
                                {Named(ln.cmd).key(ln.stem) for s in stems for ln in lines[s]
                                 if ln.kind is LineKind.LOADED})
            if self.timed:
                each(stems, lambda s: self.warm_pass(s, runs[s], lines[s]))
        finally:
            for s in stems:
                (self.dir / f"log-{s}.txt").write_text("".join(f"{ln}\n" for ln in lines[s]))
                shutil.rmtree(self.cache(s), ignore_errors=True)
        out = [ln for s in stems for ln in lines[s]]
        (self.dir / "log.txt").write_text("")
        self.log(out)
        return out

    def log(self, lines: Iterable[object]) -> None:
        """`lines` added to the run's log, one per line."""
        with open(self.dir / "log.txt", "a") as fh:
            fh.write("".join(f"{ln}\n" for ln in lines))

    def kinds(self) -> tuple[LineKind, ...]:
        """The kinds of line the run makes, which the last line counts."""
        return tuple(k for k in LineKind if self.timed or k not in TIME_KINDS)

    def accept(self, replace: bool) -> tuple[int, int]:
        """Each cold time and each output written as accepted where
        `--accept` writes it, as `scripts/gate.py --help` gives; the counts of
        times and outputs written."""
        times = {key: t for key, t in self.cold_times.items()
                 if _writes(replace, self.standing(key, t.after) is not None)}
        keep_times(self.times_file, {**self.times, **times})
        written = 0
        for p in sorted(p for ext in EXTS for p in self.new.glob(f"*.{ext}")):
            dest = self.accepted / p.name
            if _writes(replace, dest.exists()):
                shutil.copyfile(p, dest)
                written += 1
        return len(times), written


def _writes(replace: bool, stands: bool) -> bool:
    return replace or not stands
