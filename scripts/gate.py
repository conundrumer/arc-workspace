"""The gate: the gate commands on each gate stem, compared with the accepted
outputs under `tests/gate/accepted/` and the machine's accepted times.

    uv run python scripts/gate.py <out-dir> [cmd ...]
    uv run python scripts/gate.py --outputs-only <out-dir> [cmd ...]
    uv run python scripts/gate.py --accept [--replace] <out-dir> [cmd ...]

The stems run in parallel. On each stem, the commands run in the order
given, which is the order a pass runs them, sharing one run cache from
empty: this is the cold pass. Then the same sequence runs again with every
result cached: this is the warm pass. A `record*` command runs on ac0c5833
alone.

A command's outputs are its output, in `<key>.txt`, the witness file, in
`<key>.wit.json`, but for the `TEXT_ONLY_SUBS`, and its exit code, in
`<key>.rc`, with `<key>` its name and stem joined by `-`. A command stopped
at `TIME_LIMIT` has the exit code `TIMEOUT_RC`.

The cold pass is compared with the accepted outputs and the accepted times,
so a command's exit code is compared with the accepted one.
A `DIFF` line names an output file that differs, a `SLOW` line a time over
1.25 times the accepted time plus 1 s, and a `NOTIME` line a command with no
accepted time. A command's time depends on what the commands before it
cached, so times compare only when the full sequence runs. The warm pass is
compared with the cold pass: a `DIFF` line ending in `warm` names an output
file that differs between them. The last line counts the lines of each kind.

A cold run holds the lock file exclusively and a warm run holds it shared,
so a cold run never shares the machine with another command run of a gate
run, of this checkout or of another worktree of the repository. A command's
output depends on the load it runs under: `LIMITS` in `src/cli/common.py`
gives a case run a CPU limit and a wall limit, and under load the wall
limit is reached first. So an `--outputs-only` run gives the same outputs
as the cold pass of a timed run.

`--outputs-only` runs the cold pass alone, and compares its outputs alone:
it prints `DIFF` lines, and no `SLOW` or `NOTIME` line, and writes no
times to `new/`. A gate run shares the machine with whatever else runs on
it, and its times measure that load as much as the change, so times are judged by one timed gate run on `master` after a
batch of merges, with no other agent running.

Every command reads the solver files from `tests/gate/solvers/` and the
witness files from `tests/gate/witnesses/`. A command that takes a witness
file is given one at `<out-dir>/gate/wit/cur/`, copied from
`tests/gate/frozen/` before the command runs. In an output, the path of
`<out-dir>/gate/` is written as `<out>/gate/`, and a time the command prints
is dropped.

`<out-dir>/gate/new/` holds the cold pass's outputs and times,
`<out-dir>/gate/new/warm/` the warm pass's outputs, `<out-dir>/gate/times.txt`
both passes' wall times, and `<out-dir>/gate/log.txt` the lines printed
above the last line.

The accepted times depend on the machine, so every worktree of the
repository reads them from one file: the gitignored
`tests/gate/accepted/times.json` of the main checkout, the directory that
holds the repository's common git directory. The accepted outputs are read
from the worktree the gate runs in.

`--accepted` names an accepted directory other than `tests/gate/accepted/`.
Its accepted outputs and its accepted times, in its own `times.json`, are
read in place of those above.

`--accept` takes an `<out-dir>` with no `gate/` under it, runs the gate, and
then writes the cold times into the accepted times file. It writes an
output as accepted where no accepted output of that name stands, and over
one that stands only with `--replace`. `--accept` and `--outputs-only` are
not given together.

Exit status: without `--accept`, 1 when the last line counts a line of any
kind, and 0 otherwise; with `--accept`, 0 once the accepted times and
outputs are written.
"""

import argparse
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from engine import checkout
from engine.memo import write_whole

GATE = checkout.ROOT / "tests" / "gate"
SOLVERS = GATE / "solvers"
WITNESSES = GATE / "witnesses"
FROZEN = GATE / "frozen"
INPUTS = GATE / "inputs"
ACCEPTED = GATE / "accepted"
TIME_EXT = ".time"
"""The extension of the file in `new/` holding a cold run's time."""
TIMES_FILE = "times.json"
"""The accepted times, a JSON object from `<name>-<stem>` to seconds
(`times_file`)."""

STEMS = ("ac0c5833", "a934301b", "abbfd121")
RECORD_STEM = "ac0c5833"
"""The stem the `record*` commands run on, whose witness file the record
inputs fit."""

TIME_LIMIT = 560
KILL_AFTER = 5
TIMEOUT_RC = 124
"""The exit code of a command stopped at `TIME_LIMIT`, as `timeout` gives."""

SLOW_FACTOR = 1.25
SLOW_MARGIN = 1.0

type Sub = Literal["run", "lint", "witness", "derive", "store", "audit",
                   "record", "sweep", "determination-plan", "deletions"]
"""The `run_dl.py` subcommands the gate runs."""

WITNESS_FILE_SUBS: frozenset[Sub] = frozenset({"derive", "audit", "store", "witness", "record"})
"""The subcommands given a witness file."""
TEXT_ONLY_SUBS: frozenset[Sub] = frozenset({"sweep", "determination-plan", "lint"})
"""The subcommands that take no witness file, so no witness file of theirs
is compared."""

type Ext = Literal["txt", "wit.json", "rc"]
"""The extension of an output file: the normalized output, the witness file,
and the exit code."""
EXTS: tuple[Ext, ...] = ("txt", "wit.json", "rc")
"""Every output file's extension, in the order a command's are compared."""


@dataclass(frozen=True)
class Command:
    """A gate command: its name in output file names, the `run_dl.py`
    subcommand, the arguments between the stem and the witness file, and
    the arguments after the witness file."""
    name: str
    sub: Sub
    args: tuple[str, ...] = ()
    extra: tuple[str, ...] = ()

    def argv(self, stem: str, witness_file: Path) -> list[str]:
        """The `run_dl.py` arguments of the command on `stem`."""
        wf = (["--witness-file", str(witness_file)]
              if self.sub in WITNESS_FILE_SUBS else [])
        return [self.sub, stem, *self.args, *wf, *self.extra]

    def key(self, stem: str) -> str:
        """The name of the command's output files and accepted time on
        `stem`, less the extension."""
        return f"{self.name}-{stem}"

    @property
    def exts(self) -> tuple[Ext, ...]:
        return tuple(e for e in EXTS if e != "wit.json" or self.sub not in TEXT_ONLY_SUBS)


def _record(name: str, label: str, input_file: str, *extra: str) -> Command:
    """A `record` command adding the entry `label` to the witness file, with
    the inputs of a replay call read from `input_file` under `inputs/`."""
    return Command(name, "record", (label, str(INPUTS / input_file), *extra))


COMMANDS = {c.name: c for c in (
    Command("run", "run"),
    Command("lint", "lint"),
    Command("witness", "witness"),
    Command("witnesseverycase", "witness", extra=("--every-case",)),
    Command("derive", "derive"),
    Command("store", "store"),
    Command("audit", "audit"),
    _record("record52", "rarest-bg", "rarest_bg.txt", "--separates",
            "Three markers hold nine 4 cells and the solid 4x4 template sixteen 2 cells, so the rarest color is the marker color: background=RarestColor drops 4 from the marker candidates and is undefined, while the stored background keeps 4 and the copies land at the empty corners (12, 5) and (12, 14)."),
    _record("record62", "exact=stored", "stray.txt", "--separates", "test"),
    _record("record67", "exact=stored", "exact_stored.txt", "--separates",
            "At side bounds 6 to 8 the 4 cells (8, 3), (2, 3), (8, 5) form a second triple, whose empty corner is the template marker's (2, 5), so they share cells with the marker at (10, 3): $RectMarker finds the split inexact there and is undefined, while exact=stored keeps color 4 at every bound and draws the copy at (10, 3)."),
    _record("recordassign", "stride-three-side-8", "w_stride3.txt",
            "--assign", '{"marker_max_side": [[8]]}', "--separates",
            "The stride-three input with marker_max_side reassigned to 8 alone: $RectMarker reads the two 4x4 markers and draws the copy at (12, 5); marker_max_side=TileCount also reads side 2, at which no triple forms, and is undefined."),
    Command("sweep", "sweep"),
    Command("determination-plan", "determination-plan"),
    Command("deletions", "deletions"),
)}
"""Every gate command, in the order a pass runs them."""

TIME_KINDS = ("SLOW", "NOTIME")
"""The kinds of line that judge a time."""
KINDS = ("DIFF", *TIME_KINDS)
"""The kinds of line the last line counts."""

_ELAPSED_RE = re.compile(r" \([0-9.]+s\) ---$", re.M)
_LIMIT_RE = re.compile(r"^(time limit [0-9]+s; elapsed )[0-9]+s$", re.M)
_DROPPED = "runner and lib:"
OUT_MARK = "<out>/gate/"


def lock_file() -> Path:
    """The lock file in the repository's common git directory, which every
    worktree of the repository shares."""
    return checkout.git_common_dir(checkout.ROOT) / "arc-gate.lock"


def times_file(accepted: Path) -> Path:
    """The accepted times of the accepted directory `accepted`: for
    `ACCEPTED`, the machine's, `TIMES_FILE` in the main checkout's
    `ACCEPTED`; for another directory, its own `TIMES_FILE`."""
    if accepted.resolve() != ACCEPTED.resolve():
        return accepted / TIMES_FILE
    return checkout.main_checkout(checkout.ROOT) / ACCEPTED.relative_to(checkout.ROOT) / TIMES_FILE


def load() -> str:
    """The machine's load averages over 1, 5 and 15 minutes."""
    return " ".join(f"{x:.2f}" for x in os.getloadavg())


class Gate:
    """One gate run into `out/gate/`."""

    def __init__(self, out: Path, accepted: Path, timed: bool) -> None:
        self.dir = out.resolve() / "gate"
        self.new = self.dir / "new"
        self.warm = self.new / "warm"
        self.wit = self.dir / "wit" / "cur"
        self.accepted = accepted
        self.timed = timed
        """Whether the run makes the warm pass and judges the cold times;
        `--outputs-only` clears it."""
        self.times_file = times_file(accepted)
        self.times: dict[str, float] = (
            json.loads(self.times_file.read_text()) if self.times_file.exists() else {})
        self.shown = f"{checkout.shown(self.dir)}/"
        self.lock = lock_file()
        self.log_lock = threading.Lock()

    def env(self, cache: Path) -> dict[str, str]:
        return {**os.environ,
                checkout.CACHE_ENV: str(cache),
                checkout.SOLVER_FILES_ENV: str(SOLVERS),
                checkout.WITNESSES_ENV: str(WITNESSES)}

    def normalize(self, raw: str) -> str:
        """`raw` with the lines naming the runner and lib dropped, the out
        directory written as `OUT_MARK`, and the times dropped."""
        lines = [ln for ln in raw.splitlines(keepends=True) if _DROPPED not in ln]
        text = "".join(lines).replace(self.shown, OUT_MARK)
        text = _ELAPSED_RE.sub(" ---", text)
        return _LIMIT_RE.sub(r"\1Ns", text)

    def run_one(self, cmd: Command, stem: str, cold: bool, cache: Path) -> tuple[int, float]:
        """`cmd` on `stem` under the lock, its normalized output, witness
        file and exit code written to the pass's directory; the exit code
        and wall time."""
        wf = self.wit / f"{stem}.wit.json"
        shutil.copyfile(FROZEN / f"{stem}.wit.json", wf)
        argv = ["uv", "run", "--project", str(checkout.ROOT), "python",
                str(checkout.scripts() / "run_dl.py"), *cmd.argv(stem, wf)]
        base = (self.new if cold else self.warm) / cmd.key(stem)
        with open(self.lock, "a") as fh:
            fcntl.flock(fh, fcntl.LOCK_EX if cold else fcntl.LOCK_SH)
            start = time.time()
            proc = subprocess.Popen(argv, cwd=checkout.ROOT, env=self.env(cache),
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
        Path(f"{base}.raw").write_bytes(raw)
        Path(f"{base}.txt").write_text(self.normalize(raw.decode()))
        if "wit.json" in cmd.exts:
            shutil.copyfile(wf, f"{base}.wit.json")
        Path(f"{base}.rc").write_text(f"{rc}\n")
        with self.log_lock, open(self.dir / "times.txt", "a") as fh:
            fh.write(f"{cmd.name} {stem} pass{1 if cold else 2} rc={rc} wall={wall}s\n")
        return rc, wall

    def compare(self, cmd: Command, stem: str, wall: float) -> list[str]:
        """The cold run's lines: a `DIFF` line per output file that differs
        from the accepted one, and in a timed run a `SLOW` or `NOTIME` line
        for its time."""
        key = cmd.key(stem)
        lines = [f"DIFF {cmd.name} {stem} {ext}" for ext in cmd.exts
                 if not _same(self.accepted / f"{key}.{ext}", self.new / f"{key}.{ext}")]
        if not self.timed:
            return lines
        Path(self.new / f"{key}{TIME_EXT}").write_text(f"{wall}\n")
        accepted = self.times.get(key)
        if accepted is None:
            lines.append(f"NOTIME {cmd.name} {stem} time={wall}s")
        elif wall > SLOW_FACTOR * accepted + SLOW_MARGIN:
            lines.append(f"SLOW {cmd.name} {stem} time={wall}s accepted={accepted}s load={load()}")
        return lines

    def compare_warm(self, cmd: Command, stem: str) -> list[str]:
        """The warm run's lines: a `DIFF` line ending in `warm` per output
        file that differs from the cold run's."""
        key = cmd.key(stem)
        return [f"DIFF {cmd.name} {stem} {ext} warm" for ext in cmd.exts
                if not _same(self.new / f"{key}.{ext}", self.warm / f"{key}.{ext}")]

    def stem_sequence(self, stem: str, cmds: Sequence[Command]) -> None:
        """Both passes of `cmds` on `stem`, their lines written to the
        stem's log."""
        cache = self.dir / "cache" / stem
        shutil.rmtree(cache, ignore_errors=True)
        cache.mkdir(parents=True)
        lines: list[str] = []
        try:
            for cold in (True, False) if self.timed else (True,):
                for cmd in cmds:
                    if cmd.sub == "record" and stem != RECORD_STEM:
                        continue
                    _, wall = self.run_one(cmd, stem, cold, cache)
                    lines += (self.compare(cmd, stem, wall) if cold
                              else self.compare_warm(cmd, stem))
        finally:
            (self.dir / f"log-{stem}.txt").write_text("".join(f"{ln}\n" for ln in lines))
            shutil.rmtree(cache, ignore_errors=True)

    def run(self, cmds: Sequence[Command]) -> list[str]:
        """Every stem's sequence, in parallel; the lines of every stem, in
        the order of the stems' names."""
        for d in (self.new, self.warm, self.wit):
            d.mkdir(parents=True, exist_ok=True)
        errors: list[BaseException] = []

        def sequence(stem: str) -> None:
            try:
                self.stem_sequence(stem, cmds)
            except BaseException as e:
                errors.append(e)
                raise

        threads = [threading.Thread(target=sequence, args=(s,)) for s in STEMS]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        if errors:
            raise RuntimeError(f"{len(errors)} stem sequences failed") from errors[0]
        logs = [self.dir / f"log-{s}.txt" for s in sorted(STEMS)]
        missing = [p.name for p in logs if not p.exists()]
        if missing:
            raise RuntimeError(f"no log written: {', '.join(missing)}")
        text = "".join(p.read_text() for p in logs)
        (self.dir / "log.txt").write_text(text)
        return text.splitlines()

    def kinds(self) -> tuple[str, ...]:
        """The kinds of line the run makes, which the last line counts."""
        return KINDS if self.timed else tuple(k for k in KINDS if k not in TIME_KINDS)

    def accept(self, replace: bool) -> tuple[int, int]:
        """The cold times written as the machine's accepted times, and each cold
        output written as accepted where none of its name stands, or over
        it with `replace`; the counts of times and outputs written."""
        times = {p.name.removesuffix(TIME_EXT): float(p.read_text())
                 for p in sorted(self.new.glob(f"*{TIME_EXT}"))}
        merged = dict(sorted({**self.times, **times}.items()))
        write_whole(self.times_file,
                    (json.dumps(merged, indent=1) + "\n").encode())
        written = 0
        for p in sorted(p for ext in EXTS for p in self.new.glob(f"*.{ext}")):
            dest = self.accepted / p.name
            if replace or not dest.exists():
                shutil.copyfile(p, dest)
                written += 1
        return len(times), written


def _same(a: Path, b: Path) -> bool:
    """Whether both files stand and hold the same bytes."""
    return a.exists() and b.exists() and a.read_bytes() == b.read_bytes()


def main(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path, help="the output directory")
    ap.add_argument("cmds", nargs="*", metavar="cmd",
                    help=f"one of {', '.join(COMMANDS)}; every one by default, in that order")
    ap.add_argument("--accept", action="store_true",
                    help="write the run's times, and its outputs where none stands, as accepted")
    ap.add_argument("--replace", action="store_true",
                    help="with --accept, write every output over the accepted one")
    ap.add_argument("--outputs-only", action="store_true",
                    help="run the cold pass alone and compare its outputs, judging no time")
    ap.add_argument("--accepted", type=Path, default=ACCEPTED,
                    help="the accepted directory (default: tests/gate/accepted)")
    a = ap.parse_args(argv)
    if a.replace and not a.accept:
        ap.error("--replace is given without --accept")
    if a.accept and a.outputs_only:
        ap.error("--accept writes the cold times, which --outputs-only does not judge")
    unknown = [c for c in a.cmds if c not in COMMANDS]
    if unknown:
        ap.error(f"no gate command named {', '.join(unknown)}")
    cmds = [COMMANDS[c] for c in a.cmds] or list(COMMANDS.values())
    gate = Gate(a.out, a.accepted.resolve(), timed=not a.outputs_only)
    if a.accept:
        if gate.dir.exists():
            ap.error(f"{gate.dir} exists; give an empty out-dir")
        a.accepted.mkdir(parents=True, exist_ok=True)
        print(f"load before: {load()}", flush=True)
    lines = gate.run(cmds)
    for ln in lines:
        print(ln)
    counts = {k: sum(ln.startswith(f"{k} ") for ln in lines) for k in gate.kinds()}
    print("gate: " + ", ".join(f"{n} {k}" for k, n in counts.items()))
    if a.accept:
        print(f"load after: {load()}")
        times, outputs = gate.accept(a.replace)
        print(f"baseline: {times} accepted times written to {gate.times_file}, "
              f"and {outputs} new accepted outputs to {a.accepted}")
        return 0
    return 1 if any(counts.values()) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
