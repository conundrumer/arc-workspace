"""The gate: the gate commands on their gate stems, compared with the
accepted outputs under `tests/gate/accepted/` and the machine's accepted
counts of instructions.

    uv run python scripts/gate.py [--affected <base> | --record-deps] [--coverage] <out-dir> [cmd ...]
    uv run python scripts/gate.py --adopt <out-dir>

The paragraphs below say how the commands run and what they write, how
their outputs and counts are compared and what each line printed means,
the locks a run holds, what each option does, where the accepted outputs,
the accepted counts and the dependency record are read, and the exit
status. The arguments and options follow them, and then the stems each
command runs on.

A command runs on the stems its definition in `gating.commands` gives,
which the end of `--help` lists for each command. Every command reads the
solver files from `tests/gate/solvers/` and the witness files from
`tests/gate/witnesses/`.
On each stem, the commands run in the order of `gating.commands.COMMANDS`,
sharing one run cache from empty, and the stems run in parallel. A
command's count depends on what the commands before it on its stem
cached, so on each stem every gate command before the last one the run
judges runs, whether or not it was given. A command it runs on a stem only
for the cache state of a later command it judges gives no line, and writes
its outputs under `<out-dir>/gate/prefix/`.

A command's outputs are its output, in `<key>.txt`, the witness file, in
`<key>.wit.json`, where its subcommand is in
`gating.commands.WITNESS_FILE_SUBS`, and its exit code, in `<key>.rc`, with
`<key>` its name and stem joined by `-`. A command stopped at
`gating.run.TIME_LIMIT` has the exit code `gating.run.TIMEOUT_RC`.
A command's count is the instructions it retired, as the kernel counts
them (`instructions`): those of its `uv run` process, of the Python process
that runs the command, and of each Souffle process that Python process
reaped. The load on the machine and the kind of core the work ran on move
a count little.

Each judged command's outputs are compared with the accepted ones, so its
exit code is compared with the accepted one, and a `DIFF` line names an
output file that differs. Its count is compared with the accepted one
that ran after the same sequence: the key and the arguments of each
command that ran before it on its stem. A count compares only with one
whose run traced alike, where `--coverage`, `--record-deps` and an
`--affected` run that traces every command each trace. A count at least
`script_calls.CPU_RATIO` times the accepted one plus
`script_calls.INSTRUCTIONS_MARGIN` gives a `SLOW` line, which gives both.
A command with no such accepted count, and a command stopped at
`TIME_LIMIT`, gives no line on its count. The last line counts the
lines of each kind, and the duration footer (`engine.duration`) follows it
on stderr.

`LIMITS` in `src/cli/common.py` gives a case run a CPU limit and a wall
limit, and under load the wall limit is reached first. The gate sets the
wall limit to `TIME_LIMIT`, through `WALL_LIMIT_ENV`, so that a command is
stopped before any case run of it reaches the wall limit. A command's
outputs then depend on the load it runs under only where the load stretches
it to `TIME_LIMIT`, or a sweep to its own time limit, and either gives a
`DIFF` line.

Each command holds the heavy commands' lock (`engine.rwlock`) shared for
that command alone. A run that runs commands holds the gate lock of the
worktree it runs in (`engine.rwlock.GATE`) from before its first command
to its end, whatever its options, so no two gate runs of one worktree run
at once. A run that finds the lock held says so on stderr, with what the
holder wrote, and waits. A run that starts under an inherited hold of the
heavy commands' lock does not wait for the gate lock: where another run
holds it, it says so on stderr and exits 1.

`--coverage` traces each command: it records the lines of each Python
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

`--record-deps` traces commands as `--coverage` does, and writes their
dependencies, with the `HEAD` commit, to the dependency record. It runs on
a checkout with no change to a tracked file against `HEAD`, so that the
lines it records are the lines of that commit. It traces the commands that
the change from the record's commit to `HEAD` can affect, as `--affected`
selects them with the record's commit as `<base>`, and prints the
`affected:` line an `--affected` run prints; and on each stem it traces
each command after the first such one, since a command's runs depend on
what the commands before it cached. Each command before the first traced
one on its stem runs untraced, for the cache state alone, its outputs
under `<out-dir>/gate/prefix/`. Each command it does not trace keeps its
entry, with each line of a Python file the change modifies moved to the
number that line has at `HEAD`. The record holds an entry for each command
of the gate at `HEAD` and for no other key. Where no record stands, it
traces every command.

`--affected` runs only the commands that the change can affect, as
`gating.deps.affects` decides, and every command where no dependency record
stands. The change is the difference between the commit `<base>`, which the
change branched from, and the checkout. Its first line names the record and
the base, and counts the commands it runs. Where it runs every command, on
a checkout with no change to a tracked file against `HEAD`, it traces them
as `--record-deps` does, and writes their dependencies, with the `HEAD`
commit, to `<out-dir>/gate/record.json`.

`--adopt` runs no command. It writes the `<out-dir>/gate/record.json` that
an earlier run wrote as the dependency record, where its commit is the
`HEAD` commit of the checkout it runs in, and fails where it is another;
where none stands, it says so and leaves the dependency record as it is.
It then writes the counts that run wrote, in
`<out-dir>/gate/instructions.json`, into the accepted counts: for each
command, the lower of its count and the accepted one, and its count where
no accepted one stands or where that run gave it a `SLOW` line. It then
files a `performance` ticket, on domain `commit` and the `HEAD` commit, for
each `SLOW` line, with the line as its evidence, and none where a ticket
outside `tickets/closed/` on the same command and stem stands. It prints
the path of each ticket it files.

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

`<out-dir>/gate/new/` holds the judged commands' outputs and counts,
`<out-dir>/gate/times.txt` every command's count, and
`<out-dir>/gate/log.txt` the lines printed above the last line.

The accepted counts depend on the machine, so every worktree of the
repository reads them from one file: `accepted-instructions.json` under
`.cache/gate/` of the main worktree, the directory that holds the
repository's common git directory, or under the directory that
`ARC_GATE_RECORDS_DIR` (`gating.records.RECORDS_ENV`) names, where it is
set. The dependency record is read and written there too, as `deps.json`.
The accepted outputs are read from the worktree the gate runs in.

`--accepted` names an accepted directory other than `tests/gate/accepted/`.
Its accepted outputs, and its accepted counts, in its own
`accepted-instructions.json`, are read in place of those above.

Exit status: 1 when the last line counts a `DIFF` line, and 0 otherwise,
so a `SLOW` line fails no run; with `--adopt`, 1 where the record's commit
is not `HEAD`, and 0 otherwise; 1 where the run cannot wait for the gate
lock.
"""


import argparse
import shlex
import sys
from collections.abc import Sequence
from pathlib import Path

from controlled_markdown import mctx
from engine import rwlock
from engine.duration import footer
from gating.adopt import adopt_counts
from gating.commands import ACCEPTED, COMMANDS, GateCommand, keys_of, stems_listing
from gating.deps import TRACE, Deps, trace
from gating.deps_record import (
    RECORD_OUT,
    Record,
    adopt_record,
    affected,
    head,
    head_clean,
    read_record,
    traced_keys,
)
from gating.lines import Line, LineKind
from gating.records import deps_file
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
    picked = ap.add_mutually_exclusive_group()
    picked.add_argument("--affected", metavar="BASE",
                        help="run only the commands that the change from the commit BASE, "
                             "which it branched from, can affect")
    picked.add_argument("--record-deps", action="store_true",
                        help="trace the commands the change since the dependency record can "
                             "affect, and write the record at HEAD")
    ap.add_argument("--coverage", action="store_true",
                    help="trace every command run, writing its coverage data and "
                         "dependencies under the out-dir, and report the lines its runs on "
                         "the stems of STEMS it drops alone cover")
    ap.add_argument("--accepted", type=Path, default=ACCEPTED,
                    help="the accepted directory (default: tests/gate/accepted)")
    ap.add_argument("--adopt", action="store_true",
                    help="write the dependency record and the counts a run wrote under the "
                         "out-dir as the machine's, file a ticket on each SLOW line, and run "
                         "no command")
    # Kept only for master's `scripts/merge_change.py`, which passes them
    # to this script, until bug 11-750 is fixed: `--adopt-record` is
    # `--adopt`, and `--outputs-only` does nothing.
    ap.add_argument("--adopt-record", action="store_true", dest="adopt", help=argparse.SUPPRESS)
    ap.add_argument("--outputs-only", action="store_true", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)
    if a.adopt:
        if a.cmds or a.affected is not None or a.record_deps or a.coverage \
                or a.accepted != ACCEPTED:
            ap.error(mctx("--adopt takes no command and no other option"))
        return adopt(a.out)
    unknown = [c for c in a.cmds if c not in COMMANDS]
    if unknown:
        ap.error(f"no gate command named {', '.join(unknown)}")
    if a.record_deps and a.cmds:
        ap.error(mctx("--record-deps takes no command"))
    if a.record_deps and not head_clean():
        ap.error(mctx("--record-deps records the lines of HEAD, and the checkout changes "
                      "a tracked file against it"))
    try:
        with rwlock.mutex_held(rwlock.GATE, rwlock.gate_lock_dir(),
                               f"scripts/gate.py {shlex.join(argv)}"):
            return judged(a)
    except rwlock.GateHeld as held:
        print(held, file=sys.stderr, flush=True)
        return 1


def judged(a: argparse.Namespace) -> int:
    """The run of the commands that the parsed arguments `a` give; its exit
    status."""
    accepted = a.accepted.resolve()
    cmds = [COMMANDS[c] for c in a.cmds] or list(COMMANDS.values())
    keys = keys_of(cmds)
    if a.affected is not None:
        keys = select(cmds, a.affected)
    kept: dict[str, Deps] = {}
    if a.record_deps:
        record = read_record()
        keys = traced_keys(select(cmds, head() if record is None else record.commit))
        if record is not None:
            kept = record.moved(keys)
    records = a.affected is not None and keys == keys_of(COMMANDS.values()) and head_clean()
    gate = Gate(a.out, accepted, traced=a.record_deps or a.coverage or records,
                covers=a.coverage)
    lines = gate.run(cmds, keys)
    for ln in lines:
        print(ln)
    covered = gate.coverage_lines(cmds, keys)
    for ln in covered:
        print(ln)
    gate.log(covered)
    counts = {k: sum(ln.kind is k for ln in lines) for k in LineKind}
    print("gate: " + ", ".join(f"{n} {k}" for k, n in counts.items()))
    record_to = deps_file() if a.record_deps else gate.dir / RECORD_OUT if records else None
    if record_to is not None:
        written = Record.traced(gate.traced_dirs(Role.JUDGED)[0], kept)
        written.write(record_to)
        print(mctx("deps: the dependencies of {n} commands, {traced} of them traced, are "
                   "written to {path}").format(n=len(written.deps), traced=len(keys),
                                               path=record_to))
    return 1 if counts[LineKind.DIFF] else 0


def select(cmds: Sequence[GateCommand], base: str) -> set[str]:
    """The keys of `cmds` an `--affected` run judges, those the change from
    `base` can affect; its first line printed."""
    run, commit, n = affected(cmds, base)
    if commit is None:
        print(mctx("affected: no dependency record stands at {path}, so every one of the "
                   "{n} commands runs").format(path=deps_file(), n=n), flush=True)
        return run
    print(mctx("affected: {run} of the {n} commands run, by the dependency record of "
               "{commit} and the change from {base}").format(
        run=len(run), n=n, commit=commit[:12], base=base), flush=True)
    return run


def adopt(out: Path) -> int:
    """The adopt step of the run under `out`, as `--help` gives it; its exit
    status."""
    rc = adopt_record(out)
    if rc != 0:
        return rc
    grown = adopt_counts(out)
    if grown:
        commit = head()
        for path in filed(grown, commit):
            print(path)
    return 0


def filed(grown: Sequence[Line], commit: str) -> list[Path]:
    """The `performance` ticket filed on the commit `commit` for each `SLOW`
    line of `grown` that no ticket outside `tickets/closed/` on its command
    and stem stands for."""
    # Imported here, so that each traced command, whose run imports this
    # script, imports none of them.
    from handbook.paths import scripts_importable
    from operations.log_commands import AGENT
    from ticketing.text import ticket_text
    from ticketing.vocabulary import DEFECT_SECTIONS, Domain, Kind

    scripts_importable()
    from check_script_calls import open_subjects
    from file_ticket import file_ticket, main_tickets

    tickets = main_tickets()
    impact, evidence = DEFECT_SECTIONS
    standing = open_subjects(tickets)
    out: list[Path] = []
    for ln in grown:
        subject = mctx("gate command {cmd} on {stem}").format(cmd=ln.cmd, stem=ln.stem)
        if subject in standing:
            continue
        title = mctx("{subject}: its instruction count grew past the accepted one").format(
            subject=subject)
        text = ticket_text(Kind.PERFORMANCE, title, {
            impact: mctx("Each gate run of `{cmd}` on {stem} retires more instructions than "
                         "its accepted count, and so takes CPU time that the work of every other "
                         "session on the machine goes without.").format(cmd=ln.cmd, stem=ln.stem),
            evidence: f"```\n{ln}\n```"})
        out.append(file_ticket(tickets, Domain.COMMIT.value, commit, AGENT, text))
    return out


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
