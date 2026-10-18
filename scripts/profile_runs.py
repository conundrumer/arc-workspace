"""Profile agent runs from their Claude Code transcripts: where each run's
wall time goes, the budget of each agent type and role, the runs under a run since
the previous call of `--under` on it (`under_runs`), the agents under a run
whose work is open, as `--running` lists them, and whether one run's work
is open, as `--open` gives it. `--help` prints `USAGE`, and `--help PART` a part of the help, which `profile_runs_help` holds."""

import argparse
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from controlled_markdown import mctx
from handbook.paths import console_importable, scripts_importable

console_importable()
scripts_importable()

from agents_pending import pending_agents  # noqa: E402
from budgets import group_budgets, print_budgets, run_budget  # noqa: E402
from open_agents import call_times, running_agents, work_open  # noqa: E402
from run_prints import (print_messages,  # noqa: E402
                        print_report, print_running)
from run_profile import (clock, dollars, minutes,  # noqa: E402
                         part_split, print_groups, print_split,
                         print_types)
from run_profiler import profile  # noqa: E402
from run_records import Run  # noqa: E402
from run_reads import run_type  # noqa: E402
from run_readings import print_readings  # noqa: E402
from help_parts import print_help  # noqa: E402
from token_prices import PRICES  # noqa: E402
from transcripts import find, is_subagent, transcripts  # noqa: E402
from transcript_snapshots import Refused, print_refused  # noqa: E402

from profile_runs_help import HELP_VALUES, ISO_TIME, PARTS, PURPOSES, REPRICED, USAGE, HelpPart  # noqa: E402
from under_runs import UNDER, runs_since  # noqa: E402
from operator_state import line_where  # noqa: E402


def utc_time(text: str) -> float:
    t = datetime.fromisoformat(text)
    return (t if t.tzinfo else t.replace(tzinfo=UTC)).timestamp()


def print_profiles(runs: list[Run], args: argparse.Namespace, each_run: bool,
                   undecided: list[str]) -> None:
    if runs and each_run:
        # The budgets read every run under the project directories, so of
        # their `undecided` lines, only those on a run taken are kept.
        read: list[str] = []
        budgets = group_budgets(read) if args.each else None
        among = call_times(runs)
        for r in runs:
            print(f"{r.label} {r.agent_type} {clock(r.start)}: {r.description}\n"
                  f"  wall {minutes(r.wall)}  {part_split(r.parts)}  "
                  f"cost {dollars(r.cost)}")
            print_readings(r, call_times([r]), among)
            if len(runs) == 1 or args.each:
                print_messages(r, undecided,
                               run_budget(budgets, r) if budgets is not None else None)
                print_report(r, undecided)
                print_groups(r.groups, args.top, r.wall)
            if args.each and len(runs) > 1:
                print()
        taken = {r.label for r in runs}
        undecided.extend(line for line in read if line_where(line) in taken)
        if len(runs) > 1 and not args.each:
            print()
    if len(runs) > 1:
        print_types(runs, args.pct, args.top)
        print()
        print_budgets(runs, args.since, undecided)


def profiled(paths: list[Path], args: argparse.Namespace, undecided: list[str]) -> list[Run]:
    types = set(args.type.split(",")) if args.type else None
    return [profile(p, undecided, args.price_at) for p in paths
            if not types or run_type(p)[0] in types]


def ids_mode(args: argparse.Namespace, undecided: list[str]) -> int:
    runs = profiled(list(dict.fromkeys(p for ident in args.ids for p in transcripts(ident))),
                    args, undecided)
    if not runs:
        print_refused(mctx("no run to profile"))
        return 2
    print_profiles(runs, args, len(runs) == 1 or args.runs or args.each, undecided)
    if args.split is not None:
        print_split(runs, args.split, undecided)
    return 0


def under_mode(args: argparse.Namespace, undecided: list[str]) -> int:
    runs = profiled(runs_since(find(args.under), args.under, undecided), args, undecided)
    runs.sort(key=lambda r: (r.start is None, r.start or 0.0))
    print_profiles(runs, args, True, undecided)
    return 0


def running_mode(args: argparse.Namespace, undecided: list[str]) -> int:
    print_running(running_agents(find(args.running), undecided), time.time(), args.calls_since,
                  undecided)
    return 0


def pending_mode(args: argparse.Namespace, undecided: list[str]) -> int:
    for agent in pending_agents(find(args.pending), undecided):
        print(agent)
    return 0


def open_mode(args: argparse.Namespace, undecided: list[str]) -> int:
    path = find(args.open)
    if not is_subagent(path):
        raise Refused(mctx("`{ident}` names a session, not an agent").format(ident=args.open))
    print(mctx("open") if work_open(path, undecided) else mctx("not open"))
    return 0


RUNNING_OPTION = "--running"
PENDING_OPTION = "--pending"
OPEN_OPTION = "--open"
TYPE_OPTION = "--type"
PRICE_AT = "--price-at"
CALLS_SINCE = "--calls-since"
EACH = "--each"
SPLIT = "--split"


def dest(option: str) -> str:
    """The attribute `argparse` gives the value of `option` as."""
    return option.removeprefix("--").replace("-", "_")


@dataclass(frozen=True)
class Mode:
    """A mode of the command: the form `refusal` names it by, and the
    attribute of its argument."""
    form: str
    dest: str
    run: Callable[[argparse.Namespace, list[str]], int]


def option_mode(option: str, run: Callable[[argparse.Namespace, list[str]], int]) -> Mode:
    return Mode(f"`{option} ID`", dest(option), run)


IDS = Mode("IDs", "ids", ids_mode)
UNDER_MODE = option_mode(UNDER, under_mode)
RUNNING = option_mode(RUNNING_OPTION, running_mode)
PENDING = option_mode(PENDING_OPTION, pending_mode)
OPEN = option_mode(OPEN_OPTION, open_mode)
MODES = (IDS, UNDER_MODE, RUNNING, PENDING, OPEN)

FLAGS: dict[str, tuple[Mode, ...]] = {
    TYPE_OPTION: (IDS, RUNNING, PENDING, OPEN),
    PRICE_AT: (IDS, UNDER_MODE),
    CALLS_SINCE: (RUNNING,),
    EACH: (IDS,),
    SPLIT: (IDS,),
}
"""Each flag that goes with only some modes, with those modes."""


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(add_help=False, usage=argparse.SUPPRESS)
    ap.add_argument(IDS.dest, nargs="*", metavar="ID")
    ap.add_argument(UNDER, metavar="ID",
                    help=mctx("profile the runs under the run ID since the "
                              "previous call of this on it, as `--help under` "
                              "gives it"))
    ap.add_argument(RUNNING_OPTION, metavar="ID",
                    help=mctx("list the agents under the run ID whose work "
                              "is open"))
    ap.add_argument(CALLS_SINCE, type=utc_time, metavar="TIME",
                    help=mctx("with `--running`, print of each agent's last "
                              "calls only those that ended at or after TIME "
                              "or are pending: ") + ISO_TIME)
    ap.add_argument(PENDING_OPTION, metavar="ID",
                    help=mctx("list the agents pending to the run ID"))
    ap.add_argument(OPEN_OPTION, metavar="ID",
                    help=mctx("print whether the work of the run ID is open"))
    ap.add_argument(TYPE_OPTION, help=mctx("profile only runs of these agent "
                                        "types, separated by commas"))
    ap.add_argument("--pct", type=float, default=90,
                    help=mctx("the high percentile of wall time per type"))
    ap.add_argument("--top", type=int, default=8,
                    help=mctx("labels to print per run or per type; 0 prints "
                              "none per type and all for one run"))
    ap.add_argument("--runs", action="store_true",
                    help=mctx("also print one line per run"))
    ap.add_argument(EACH, action="store_true",
                    help=mctx("print for each run what one run prints"))
    ap.add_argument(PRICE_AT, choices=sorted(PRICES), metavar="MODEL",
                    help=mctx("one of {models}; `--help runs` gives what it "
                              "does").format(models=", ".join(sorted(PRICES))))
    ap.add_argument("--since", type=utc_time, metavar="DATE",
                    help=mctx("start of the window of runs each type's "
                              "budget is taken over, in place of the type's "
                              "own: ") + ISO_TIME)
    ap.add_argument(SPLIT, type=utc_time, metavar="TIME",
                    help=mctx("print per agent type the runs before TIME and "
                              "those at or after it apart: ") + ISO_TIME)
    return ap




def mode_given(args: argparse.Namespace, dest: str) -> bool:
    """A mode's ID given as `""` is no mode."""
    return bool(getattr(args, dest))


def flag_given(args: argparse.Namespace, dest: str) -> bool:
    """A time flag at the epoch is given, though `0.0 == False`."""
    value = getattr(args, dest)
    return value is not None and value is not False


def refusal(args: argparse.Namespace) -> str | None:
    """Why the modes and the flags of `args` do not go together, or None
    where they do."""
    if sum(mode_given(args, m.dest) for m in MODES) != 1:
        forms = [m.form for m in MODES]
        return mctx("give one of {modes}").format(
            modes=", ".join(forms[:-1]) + " and " + forms[-1])
    mode = next(m for m in MODES if mode_given(args, m.dest))
    for flag, modes in FLAGS.items():
        if flag_given(args, dest(flag)) and mode not in modes:
            return mctx("`{flag}` goes only with {modes}").format(
                flag=flag, modes=" or ".join(m.form for m in modes))
    return None


def main(argv: list[str]) -> int:
    ap = parser()
    if argv[:1] in (["--help"], ["-h"]):
        return print_help(argv[1:], HelpPart, lambda parts: USAGE.format(parts=parts), PURPOSES,
                          lambda part: ap.format_help() if part is HelpPart.OPTIONS
                          else PARTS[part].format(**HELP_VALUES))
    args = ap.parse_args(argv)
    if (why := refusal(args)) is not None:
        print_refused(why)
        return 2
    if args.price_at is not None:
        print(mctx("price at {model}: {repriced}").format(
            model=args.price_at, repriced=REPRICED.format(model=args.price_at)))
    undecided: list[str] = []
    try:
        status = next(m for m in MODES if mode_given(args, m.dest)).run(args, undecided)
    except Refused as e:
        print_refused(e)
        return 2
    if status != 0:
        return status
    for line in dict.fromkeys(undecided):
        print(mctx("undecided: {line}").format(line=line), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
