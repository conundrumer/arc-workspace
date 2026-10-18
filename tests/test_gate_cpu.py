"""The gate's counts of instructions: the count of a command, and the
adopt step's accepted counts. A count that misses a process, or an
adopted count that hides a growth, lets a slowdown pass every merge in
silence."""

import os
import sys
from pathlib import Path

from gating import run
from gating.adopt import adopted
from gating.commands import COMMANDS
from gating.lines import LineKind
from gating.records import AcceptedCount, Counts, Tracing

BURN = "x = 0\nfor i in range({n}):\n    x += i\n"


def counted(tmp_path: Path, n: int) -> int:
    env = {"PATH": os.environ.get("PATH", "")}
    rc, _, count = run.measured([sys.executable, "-c", BURN.format(n=n)], env,
                                tmp_path / f"counted-{n}")
    assert rc == 0 and count is not None
    return count


def test_a_command_s_count_holds_the_work_of_its_python_process(tmp_path: Path):
    small, large = counted(tmp_path, 10 ** 5), counted(tmp_path, 10 ** 7)
    assert large - small > 5 * 10 ** 9


def counts(**by_key: AcceptedCount) -> Counts:
    return {Tracing.UNTRACED: dict(by_key), Tracing.TRACED: {}}


G = 10 ** 9


def test_the_adopt_step_keeps_the_lower_count_and_takes_a_grown_one_with_its_slow_line():
    cmd = next(iter(COMMANDS.values()))
    a, b = (cmd.key(s) for s in cmd.stems[:2])
    after = ()
    accepted = counts(**{a: AcceptedCount(10 * G, after), b: AcceptedCount(10 * G, after)})
    ran = counts(**{a: AcceptedCount(12 * G, after), b: AcceptedCount(40 * G, after)})
    out, grown = adopted(accepted, ran)
    assert out[Tracing.UNTRACED] == {a: AcceptedCount(10 * G, after),
                                     b: AcceptedCount(40 * G, after)}
    assert [(ln.kind, ln.cmd, ln.stem) for ln in grown] == [(LineKind.SLOW, cmd.name,
                                                             cmd.stems[1])]


def test_a_count_after_another_sequence_or_tracing_replaces_none_it_compares_with():
    cmd = next(iter(COMMANDS.values()))
    a = cmd.key(cmd.stems[0])
    accepted = counts(**{a: AcceptedCount(G, ())})
    ran: Counts = {Tracing.UNTRACED: {a: AcceptedCount(30 * G, (("x", ()),))},
                   Tracing.TRACED: {a: AcceptedCount(40 * G, ())}}
    out, grown = adopted(accepted, ran)
    assert grown == []
    assert out[Tracing.UNTRACED][a].instructions == 30 * G
    assert out[Tracing.TRACED][a].instructions == 40 * G
