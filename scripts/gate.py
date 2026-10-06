"""The gate: the gate commands on their gate stems, compared with the
accepted outputs under `tests/gate/accepted/` and the machine's accepted
times.

    uv run python scripts/gate.py [--affected <base>] <out-dir> [cmd ...]
    uv run python scripts/gate.py --outputs-only [--affected <base> | --record-deps] [--coverage] <out-dir> [cmd ...]
    uv run python scripts/gate.py --accept [--replace] [--affected <base>] <out-dir> [cmd ...]
    uv run python scripts/gate.py --adopt-record <out-dir>

The paragraphs below say how the commands run and what they write, how
their outputs and times are compared and what each line printed means, the
locks a run holds, what each option does, where the accepted outputs, the
accepted times and the dependency record are read, and the exit status.
The arguments and options follow them, and then the stems each command runs
on.

A command runs on the stems its definition in `gating.commands` gives,
which the end of `--help` lists for each command. Every command reads the
solver files from `tests/gate/solvers/` and the witness files from
`tests/gate/witnesses/`.
On each stem, the commands run in the order given, which is the order a
pass runs them, sharing one run cache from empty: this is the cold pass.
Then the same sequence runs again with every result cached: this is the
warm pass. The stems run in parallel, other than in the cold pass of a
timed run, which runs one command at a time.

A command's outputs are its output, in `<key>.txt`, the witness file, in
`<key>.wit.json`, where its subcommand is in
`gating.commands.WITNESS_FILE_SUBS`, and its exit code, in `<key>.rc`, with
`<key>` its name and stem joined by `-`. A command stopped at
`gating.run.TIME_LIMIT` has the exit code `gating.run.TIMEOUT_RC`.

The cold pass is compared with the accepted outputs and the accepted times,
so a command's exit code is compared with the accepted one.
A `DIFF` line names an output file that differs, and a `NOTIME` line a
command with no accepted time. A time over 1.25 times the accepted time plus
1 s gives a `SLOW` or a `LOADED` line, which gives the outside CPU: the CPU
time that processes outside the gate's process tree used over the command's
run, the machine's busy CPU time less the gate tree's own. Where the outside
CPU is over one core on average, the line is a `LOADED` line, and otherwise
a `SLOW` line. With `--accept`, a line above the last line gives the outside
CPU over the whole run. A command's time depends on what the commands before it
on its stem cached, so times compare only where the sequence runs in full up
to it: on each stem, a timed run runs each command given before the last one
whose time it judges. The warm pass is
compared with the cold pass: a `DIFF` line ending in `warm` names an output
file that differs between them. The last line counts the lines of each kind,
and the duration footer (`engine.duration`) follows it on stderr.

`LIMITS` in `src/cli/common.py` gives a case run a CPU limit and a wall
limit, and under load the wall limit is reached first. The gate sets the
wall limit to `TIME_LIMIT`, through `WALL_LIMIT_ENV`, so that a command is
stopped before any case run of it reaches the wall limit. A command's
outputs then depend on the load it runs under only where the load stretches
it to `TIME_LIMIT`, or a sweep to its own time limit, and either gives a
`DIFF` line.

A timed run holds the heavy commands' lock (`engine.rwlock`) exclusively
once, over its whole cold pass, so a cold command shares the machine with no
other heavy command, of this checkout or of another worktree of the
repository. Each warm command, and each command of an `--outputs-only` run,
holds it shared for that command alone, and the run holds nothing between
two such commands, so a heavy command outside the run waits at most for the
run's commands in flight. The warm pass starts after the cold pass releases
its hold, since a warm command that asked for a shared hold while the run
holds the lock exclusively would wait for the run itself. Where the run has
to wait for the lock, it says so on stderr once for the cold pass's hold,
and once for its commands' shared holds.

`--outputs-only` runs the cold pass alone, and compares its outputs alone:
it prints `DIFF` lines, and no `SLOW`, `LOADED` or `NOTIME` line, and writes no
times to `new/`. An `--outputs-only` run shares the machine with the other
heavy commands, and its times measure that load as much as the change, so
times are judged by one timed gate run on `master` after a batch of merges,
over the commands the batch can affect (`--affected`).
A `SLOW` line of that run blocks no merge.

`--coverage` traces each cold command: it records the lines of each Python
file under `src/` and `scripts/` the command runs, through coverage.py, and
the other files of the checkout it opens to read and the directories it
lists, through an audit hook. `<out-dir>/gate/cov/` then holds each
command's coverage data, which `coverage combine` reads, and
`<out-dir>/gate/deps/` each command's dependencies.
With `--coverage`, each command given that runs on a stem list chosen from
`gating.commands.STEMS` (`gating.commands.dropped_stems`), and runs on each
of its own stems, also runs, traced, on each stem of `STEMS` it drops, at
its place in the stem's sequence, its outputs, coverage data and
dependencies written under `<out-dir>/gate/dropped/` and compared with
none. Above the last line, a `coverage:` line then gives, for each such
command, the lines of `src/` and `scripts/` that its runs on all of `STEMS`
cover and its runs on its own stems do not, the run cache's pruning lines
(`gating.deps.pruning_lines`) left out.
A traced run that wrote no dependencies counts as covering no line, and a
`coverage:` line names the command and each stem of such a run.
One more `coverage:` line names each command that runs on only part of
its own stems, as `--affected` may run it, and so gets none.

`--record-deps` traces every command as `--coverage` does, and writes their
dependencies, with the `HEAD` commit, to the dependency record. It runs on
a checkout with no change to a tracked file against `HEAD`, so that the
lines it records are the lines of that commit.

`--affected` runs only the commands that the change can affect, as
`gating.deps.affects` decides, and every command where no dependency record
stands. The change is the difference between the commit `<base>`, which the
change branched from, and the checkout. Its first line names the record and
the base, and counts the commands it runs. In a timed run, it also judges
each command that `loaded.json` keeps, whether or not the change can affect
it, and a second line counts those the change cannot affect. A command it
runs on a stem only for the cache state of a later command it judges gives
no line, runs in the cold pass alone, and writes its outputs under
`<out-dir>/gate/prefix/`. In an `--outputs-only` run, where it runs every
command, on a checkout with no change to a tracked file against `HEAD`, it
traces them as `--record-deps` does, and writes their dependencies, with
the `HEAD` commit, to `<out-dir>/gate/record.json`.

`--adopt-record` runs no command: it writes the `<out-dir>/gate/record.json`
that an earlier run wrote as the dependency record, where its commit is the
`HEAD` commit of the checkout it runs in, and fails where it is another.
Where none stands, it says so and leaves the dependency record as it is.

A command that takes a witness file is given one at
`<out-dir>/gate/wit/cur/`, copied from `tests/gate/frozen/` before the
command runs. The `record` commands, `grid` and `relation` read their input
files from `tests/gate/inputs/`. The `context` command renders each of its
readers' contexts from `<out-dir>/gate/documents/`, copied from
`tests/gate/documents/` before the commands run, so a change to the
checkout's own documents changes none of its outputs. Its readers are the
session, codex, and each name `tests/gate/documents/` defines for a reader
that takes a name. In an output, the path of `<out-dir>/gate/` is written
as `<out>/gate/`, and a time the command prints is dropped.

`<out-dir>/gate/new/` holds the cold pass's outputs and times,
`<out-dir>/gate/new/warm/` the warm pass's outputs, `<out-dir>/gate/times.txt`
both passes' wall times, and `<out-dir>/gate/log.txt` the lines printed
above the last line.

The accepted times depend on the machine, so every worktree of the
repository reads them from one file: `times.json` under `.cache/gate/` of
the main worktree, the directory that holds the repository's common git
directory. The dependency record is read and written there too, as
`deps.json`. So are the commands that a timed run gives a `LOADED` line, as
`loaded.json`, until a later timed run judges their time and gives them no
`LOADED` line; the cold pass writes it before it releases its hold. The
accepted outputs are read from the worktree the gate runs in.

`--accepted` names an accepted directory other than `tests/gate/accepted/`.
Its accepted outputs, its accepted times, in its own `times.json`, and the
commands kept for a timed run, in its own `loaded.json`, are read in place
of those above.

`--accept` takes an `<out-dir>` with no `gate/` under it, runs the gate,
and then writes each cold time and output as accepted where no accepted
time or output of its name stands, and over one that stands only with
`--replace`, so that an accepting run after a regression keeps the faster
times. `--accept` and `--outputs-only` are not given together.

Exit status: without `--accept`, 1 when the last line counts a line of any
kind, and 0 otherwise; with `--accept`, 0 once the accepted times and
outputs are written.
"""


import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from controlled_markdown import mctx
from engine.duration import footer
from gating.commands import ACCEPTED, COMMANDS, GateCommand, keys_of, stems_listing
from gating.cpu import CpuSample
from gating.deps import TRACE, trace
from gating.deps_record import RECORD_OUT, Record, adopt_record, affected, head_clean
from gating.records import deps_file, loaded_file, read_loaded
from gating.run import Gate, Role


def main(argv: Sequence[str]) -> int:
    if argv[:1] == [TRACE]:
        deps_out, cov_out, script, *args = argv[1:]
        return trace(Path(deps_out), Path(cov_out), Path(script), args)
    with footer("gate"):
        return run_gate(argv)


def run_gate(argv: Sequence[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, epilog=stems_listing(),
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path, help="the output directory")
    ap.add_argument("cmds", nargs="*", metavar="cmd",
                    help=f"one of {', '.join(COMMANDS)}; every one by default, in that order")
    ap.add_argument("--accept", action="store_true",
                    help="write the run's times and outputs as accepted where none stands")
    ap.add_argument("--replace", action="store_true",
                    help="with --accept, write every time and output over the accepted one")
    ap.add_argument("--outputs-only", action="store_true",
                    help="run the cold pass alone and compare its outputs, judging no time")
    picked = ap.add_mutually_exclusive_group()
    picked.add_argument("--affected", metavar="BASE",
                        help="run only the commands that the change from the commit BASE, "
                             "which it branched from, can affect, and in a timed run those "
                             "loaded.json keeps")
    picked.add_argument("--record-deps", action="store_true",
                        help="with --outputs-only, trace every command and write the "
                             "dependency record")
    ap.add_argument("--coverage", action="store_true",
                    help="with --outputs-only, trace every command run, writing its coverage "
                         "data and dependencies under the out-dir, and report the lines its "
                         "runs on the stems of STEMS it drops alone cover")
    ap.add_argument("--accepted", type=Path, default=ACCEPTED,
                    help="the accepted directory (default: tests/gate/accepted)")
    ap.add_argument("--adopt-record", action="store_true",
                    help="write the dependencies an --affected run traced under the out-dir "
                         "as the dependency record, and run no command")
    a = ap.parse_args(argv)
    if a.adopt_record:
        if a.cmds or a.accept or a.replace or a.outputs_only or a.affected is not None \
                or a.record_deps or a.coverage or a.accepted != ACCEPTED:
            ap.error(mctx("--adopt-record runs no command, so it takes no command and "
                          "no other option"))
        return adopt_record(a.out)
    if a.replace and not a.accept:
        ap.error("--replace is given without --accept")
    if a.accept and a.outputs_only:
        ap.error("--accept writes the cold times, which --outputs-only does not judge")
    if (a.record_deps or a.coverage) and not a.outputs_only:
        ap.error(mctx("--record-deps and --coverage each run a trace of the sequence, whose "
                      "times do not compare, so each needs --outputs-only"))
    unknown = [c for c in a.cmds if c not in COMMANDS]
    if unknown:
        ap.error(f"no gate command named {', '.join(unknown)}")
    if a.record_deps and a.cmds:
        ap.error(mctx("--record-deps records every command, so it takes no command"))
    if a.record_deps and not head_clean():
        ap.error(mctx("--record-deps records the lines of HEAD, and the checkout changes "
                      "a tracked file against it"))
    timed = not a.outputs_only
    cmds = [COMMANDS[c] for c in a.cmds] or list(COMMANDS.values())
    keys = keys_of(cmds)
    if a.affected is not None:
        keys = select(cmds, a.affected, a.accepted.resolve(), timed)
    records = (not timed and a.affected is not None and keys == keys_of(COMMANDS.values())
               and head_clean())
    gate = Gate(a.out, a.accepted.resolve(), timed=timed,
                traced=a.record_deps or a.coverage or records, covers=a.coverage)
    if a.accept:
        if gate.dir.exists():
            ap.error(f"{gate.dir} exists; give an empty out-dir")
        a.accepted.mkdir(parents=True, exist_ok=True)
    sample = CpuSample.now() if a.accept else None
    lines = gate.run(cmds, keys)
    if sample is not None:
        print(f"run: {sample.outside(CpuSample.now())}")
    for ln in lines:
        print(ln)
    covered = gate.coverage_lines(cmds, keys)
    for ln in covered:
        print(ln)
    gate.log(covered)
    counts = {k: sum(ln.kind is k for ln in lines) for k in gate.kinds()}
    print("gate: " + ", ".join(f"{n} {k}" for k, n in counts.items()))
    record_to = deps_file() if a.record_deps else gate.dir / RECORD_OUT if records else None
    if record_to is not None:
        Record.traced(gate.traced_dirs(Role.JUDGED)[0]).write(record_to)
        print(mctx("deps: the dependencies of {n} commands are written to {path}").format(
            n=len(keys), path=record_to))
    if a.accept:
        times, outputs = gate.accept(a.replace)
        print(f"baseline: {times} accepted times written to {gate.times_file}, "
              f"and {outputs} new accepted outputs to {a.accepted}")
        return 0
    return 1 if any(counts.values()) else 0


def select(cmds: Sequence[GateCommand], base: str, accepted: Path, timed: bool) -> set[str]:
    """The keys of `cmds` an `--affected` run judges: those the change from
    `base` can affect, and in a timed run those `loaded_file` keeps beside
    the accepted times of `accepted`; its first lines printed."""
    run, commit, n = affected(cmds, base)
    if commit is None:
        print(mctx("affected: no dependency record stands at {path}, so every one of the "
                   "{n} commands runs").format(path=deps_file(), n=n), flush=True)
        return run
    kept = (read_loaded(loaded_file(accepted)) & keys_of(cmds)) - run if timed else set()
    print(mctx("affected: {run} of the {n} commands run, by the dependency record of "
               "{commit} and the change from {base}").format(
        run=len(run), n=n, commit=commit[:12], base=base), flush=True)
    if kept:
        print(mctx("affected: {kept} more commands run, each kept for the LOADED line of "
                   "an earlier timed run").format(kept=len(kept)), flush=True)
    return run | kept


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
