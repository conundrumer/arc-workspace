"""Profile agent runs from their Claude Code transcripts: where each run's
wall time goes, the budget of each agent type and role, the runs under a run since
an operator's previous call of `--under` on it, the agents under a run
whose work is open, as `--running` lists them, and whether one run's work
is open, as `--open` gives it. `--help` prints `USAGE`, and `--help PART` a part of the help, which `profile_runs_help` holds. `budget_of` gives the
budget of a brief of one role, as more than one run prints it,
over every run under the project directories."""

import argparse
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from controlled_markdown import mctx
from handbook.paths import console_importable, scripts_importable

console_importable()
scripts_importable()

from agent_launches import runs_under  # noqa: E402
from agents_pending import pending_agents  # noqa: E402
from agent_turns import first_time, last_time  # noqa: E402
from budgets import (budget_group, print_budgets, role_group,  # noqa: E402
                     type_budget)
from command_labels import programs  # noqa: E402
from context_bound_hook import OPERATOR  # noqa: E402
from open_agents import Listed, call_times, running_agents, work_open  # noqa: E402
from run_prints import (print_messages,  # noqa: E402
                        print_report, print_running)
from run_profile import (clock, dollars, minutes,  # noqa: E402
                         part_split, print_groups, print_split,
                         print_types)
from run_profiler import profile  # noqa: E402
from run_records import Run  # noqa: E402
from run_reads import (BACKGROUND_TASK, agent_type, blocks,  # noqa: E402
                       result_text, run_entries, run_type)
from run_readings import print_readings  # noqa: E402
from run_store import RunStore  # noqa: E402
from help_parts import print_help  # noqa: E402
from operations.roles import Role  # noqa: E402
from ticketing.times import utc_stamp  # noqa: E402
from token_prices import PRICES  # noqa: E402
from transcripts import agent_id, agent_transcripts, bare_id, find, is_subagent, transcripts
from transcript_entries import Entry, Refused, epoch, read_entries

from profile_runs_help import HELP_VALUES, ISO_TIME, PARTS, PURPOSES, REPRICED, USAGE, HelpPart  # noqa: E402
from operations.batches import LEFT_OPEN, NO_RUN, RUNS_TAKEN, lines, read_under  # noqa: E402

UNDER = "--under"
"""The option of the mode that profiles the runs under a run since an
operator's previous call of it."""

def utc_time(text: str) -> float:
    t = datetime.fromisoformat(text)
    return (t if t.tzinfo else t.replace(tzinfo=UTC)).timestamp()


def calls_under(command: str, ident: str) -> bool:
    """Whether the Bash command `command` runs this tool with `UNDER` on the
    run `ident`, as it writes the ID, with or without the `agent-` prefix."""
    want = bare_id(ident)
    for prog, rest in programs(command):
        if prog != Path(__file__).name:
            continue
        for i, word in enumerate(rest):
            given = (rest[i + 1] if word == UNDER and i + 1 < len(rest)
                     else word.removeprefix(UNDER + "=")
                     if word.startswith(UNDER + "=") else None)
            if given is not None and bare_id(given) == want:
                return True
    return False


def under_output(entries: list[Entry], call: str) -> str | None:
    """The text of the result of the Bash call `call` among `entries`,
    where that result says it completed in the foreground with no error, or
    None otherwise."""
    for e in entries:
        for b in blocks(e, "tool_result"):
            if e.get("type") == "user" and b.get("tool_use_id") == call:
                r = e.get("toolUseResult")
                r = r if isinstance(r, dict) else {}
                if b.get("is_error") or r.get(BACKGROUND_TASK) or r.get("interrupted"):
                    return None
                return result_text(b, r)
    return None


@dataclass(frozen=True)
class Previous:
    """The previous call of `UNDER` on a run: its time, the agent id of the
    operator that made it, and the agent ids its `LEFT_OPEN` line gives."""
    time: float
    agent: str
    left: frozenset[str]


def previous_call(path: Path, ident: str, undecided: list[str]) -> Previous | None:
    """The previous call of `UNDER` on the run at `path`, which `ident`
    names, as `PARTS` gives that call, or None where none stands."""
    start = first_time(path)
    found: Previous | None = None
    for p in (p for ps in agent_transcripts().values() for p in ps):
        if start is not None and p.stat().st_mtime < start:
            continue
        if agent_type(p) != OPERATOR:
            continue
        calls = read_entries(p, naming={UNDER})
        made = {b["id"]: epoch(e["timestamp"]) for e in calls
                if e.get("type") == "assistant" and e.get("timestamp")
                for b in blocks(e, "tool_use")
                if b.get("name") == "Bash" and b.get("id")
                and calls_under(str((b.get("input") or {}).get("command", "")), ident)}
        if not made:
            continue
        results = read_entries(p, naming=set(made))
        for call, t in made.items():
            text = under_output(results, call)
            if text is None:
                continue
            if (n := len(lines(text, LEFT_OPEN))) > 1:
                undecided.append(mctx(
                    "the result of the call of `{under}` at {time} by {agent} "
                    "holds {n} `{left}` lines, so it counts as no call").format(
                        under=UNDER, time=utc_stamp(t),
                        agent=agent_id(p), n=n, left=LEFT_OPEN))
                continue
            given = read_under(text)
            if given is not None and (found is None or t > found.time):
                found = Previous(t, agent_id(p), given.left)
    return found


def runs_since(path: Path, ident: str, undecided: list[str]) -> list[Path]:
    """The runs `UNDER` takes under the run at `path`, which `ident` names,
    with its first lines printed."""
    previous = previous_call(path, ident, undecided)
    taken: list[Path] = []
    left: list[str] = []
    for p in runs_under(path):
        last = last_time(p)
        if not (previous is None or agent_id(p) in previous.left
                or (last is not None and last > previous.time)):
            continue
        if work_open(p, undecided):
            left.append(agent_id(p))
        else:
            taken.append(p)
    print(LEFT_OPEN, " ".join(left) or NO_RUN)
    print(RUNS_TAKEN, len(taken), *(agent_id(p) for p in taken))
    # The harness trims the end of a result's `stdout`, so the line after
    # `RUNS_TAKEN` gives it the line break `read_under` needs.
    if previous is None:
        print(mctx("previous call: none"))
    else:
        print(mctx("previous call: {time} by {agent}").format(
            time=utc_stamp(previous.time),
            agent=previous.agent))
    return taken


def budget_of(role: Role, items: int | None, undecided: list[str]) -> float | None:
    """The budget in seconds of a brief of `role`, over every run under
    the project directories that joins its budget, for a brief that gives
    no items where `items` is None, and otherwise for a brief that gives
    `items` items, or None where it gets none. The agent type and the
    profile of each run are read through `run_store`."""
    group = role_group(role)
    store = RunStore()
    runs = [r for agent in agent_transcripts()
            if (typed := store.last_and_type(agent))[1] == role.agent_type
            and budget_group(r := store.profile(typed[0], undecided)) == group]
    store.flush()
    b = type_budget(group, runs, None, items is not None, undecided)
    if b is None:
        return None
    return b.seconds if items is None else b.seconds * items


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(add_help=False, usage=argparse.SUPPRESS)
    ap.add_argument("ids", nargs="*", metavar="ID")
    ap.add_argument(UNDER, metavar="ID",
                    help=mctx("profile the runs under the run ID since an "
                              "operator's previous call of this on it"))
    ap.add_argument("--running", metavar="ID",
                    help=mctx("list the agents under the run ID whose work "
                              "is open"))
    ap.add_argument("--calls-since", type=utc_time, metavar="TIME",
                    help=mctx("with `--running`, print of each agent's last "
                              "calls only those that ended at or after TIME "
                              "or are pending: ") + ISO_TIME)
    ap.add_argument("--pending", metavar="ID",
                    help=mctx("list the agents pending to the run ID"))
    ap.add_argument("--open", metavar="ID",
                    help=mctx("print whether the work of the run ID is open"))
    ap.add_argument("--type", help=mctx("profile only runs of these agent "
                                        "types, separated by commas"))
    ap.add_argument("--pct", type=float, default=90,
                    help=mctx("the high percentile of wall time per type"))
    ap.add_argument("--top", type=int, default=8,
                    help=mctx("labels to print per run or per type; 0 prints "
                              "none per type and all for one run"))
    ap.add_argument("--runs", action="store_true",
                    help=mctx("also print one line per run"))
    ap.add_argument("--each", action="store_true",
                    help=mctx("print for each run what one run prints"))
    ap.add_argument("--price-at", choices=sorted(PRICES), metavar="MODEL",
                    help=mctx("one of {models}; `--help runs` gives what it "
                              "does").format(models=", ".join(sorted(PRICES))))
    ap.add_argument("--since", type=utc_time, metavar="DATE",
                    help=mctx("start of the window of runs each type's "
                              "budget is taken over, in place of the type's "
                              "own: ") + ISO_TIME)
    ap.add_argument("--split", type=utc_time, metavar="TIME",
                    help=mctx("print per agent type the runs before TIME and "
                              "those at or after it apart: ") + ISO_TIME)
    if argv[:1] in (["--help"], ["-h"]):
        return print_help(argv[1:], HelpPart, lambda parts: USAGE.format(parts=parts), PURPOSES,
                          lambda part: ap.format_help() if part is HelpPart.OPTIONS
                          else PARTS[part].format(**HELP_VALUES))
    args = ap.parse_args(argv)
    types = set(args.type.split(",")) if args.type else None
    undecided: list[str] = []
    runs: list[Run] = []
    listed: list[Listed] = []
    if [bool(args.ids), bool(args.under), bool(args.running), bool(args.pending),
            bool(args.open)].count(True) != 1:
        print(mctx("refused: give one of IDs, `--under ID`, `--running ID`, "
                   "`--pending ID` and `--open ID`"),
              file=sys.stderr)
        return 2
    if args.under and args.type is not None:
        print(mctx("refused: `--under` takes no `--type`"), file=sys.stderr)
        return 2
    if args.price_at is not None and not (args.ids or args.under):
        print(mctx("refused: `--price-at` goes with IDs or `--under ID`"),
              file=sys.stderr)
        return 2
    if args.calls_since is not None and not args.running:
        print(mctx("refused: `--calls-since` goes with `--running ID` alone"),
              file=sys.stderr)
        return 2
    if args.each and not args.ids:
        print(mctx("refused: `--each` goes with IDs alone"), file=sys.stderr)
        return 2
    if args.split is not None and not args.ids:
        print(mctx("refused: `--split` goes with IDs alone"), file=sys.stderr)
        return 2
    if args.price_at is not None:
        print(mctx("price at {model}: {repriced}").format(
            model=args.price_at, repriced=REPRICED.format(model=args.price_at)))
    try:
        if args.pending:
            for agent in pending_agents(find(args.pending), undecided):
                print(agent)
        elif args.open:
            path = find(args.open)
            if not is_subagent(path):
                raise Refused(mctx("`{ident}` names a session, not an agent")
                              .format(ident=args.open))
            print(mctx("open") if work_open(path, undecided)
                  else mctx("not open"))
        elif args.running:
            listed = running_agents(find(args.running), undecided)
        else:
            paths = (runs_since(find(args.under), args.under, undecided)
                     if args.under else
                     list(dict.fromkeys(p for ident in args.ids
                                        for p in transcripts(ident))))
            runs = [profile(p, undecided, args.price_at) for p in paths
                    if not types or run_type(p)[0] in types]
            if args.under:
                runs.sort(key=lambda r: (r.start is None, r.start or 0.0))
    except Refused as e:
        print(mctx("refused: {reason}").format(reason=e), file=sys.stderr)
        return 2
    if args.running:
        print_running(listed, time.time(), args.calls_since, undecided)
    elif not runs and not args.pending and not args.open and not args.under:
        print(mctx("refused: no run to profile"), file=sys.stderr)
        return 2
    elif runs and (len(runs) == 1 or args.runs or args.each or args.under):
        whole = len(runs) == 1 or args.each
        among = call_times(runs)
        for r in runs:
            print(f"{r.label} {r.agent_type} {clock(r.start)}: {r.description}\n"
                  f"  wall {minutes(r.wall)}  {part_split(r.parts)}  "
                  f"cost {dollars(r.cost)}")
            print_readings(r, call_times([r]), among)
            if whole:
                print_messages(r, undecided)
                print_report(r, undecided)
                print_groups(r.groups, args.top, r.wall)
            if args.each and len(runs) > 1:
                print()
        if len(runs) > 1 and not args.each:
            print()
    if len(runs) > 1 and not args.running:
        print_types(runs, args.pct, args.top)
        print()
        print_budgets(runs, args.since, undecided)
    if args.split is not None:
        print_split(runs, args.split, undecided)
    for line in dict.fromkeys(undecided):
        print(mctx("undecided: {line}").format(line=line), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
