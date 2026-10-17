"""A run: the solver pipelines that the script an `Op run: <path>` line of the
coordinator's gives starts, as `scripts/operate.py --help run` gives the
script's form. `scripts/run_scripts.py` loads and calls the script at
each read of the state, with the `Run` this module gives, and the state
holds what it gave (`state.Computed.run_starts`).

A run script's `takes`, which `scripts/operate.py --help run` gives,
reads a `RunTicket`; the state holds what it gave
(`state.Computed.run_takes`), and `taking.admits` applies it.

A run's pipelines are the calls of `operate.py start` that an operator of
the session made with the run's `RUN_OPTION`, which its step gives, each
with that call's time as its start; a failed call is a pipeline that
stopped on its failure's text."""

import argparse
import re
import shlex
from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path
from typing import TypeGuard

from arc.task import TASK_ID
from controlled_markdown import mctx
from operations.command_words import COMMAND, RUN_COMMAND, simple_commands
from operations.constants import COORDINATOR
from operations.directives import Directive, Line, Pipeline
from operations.roles import PASSES, Role
from operations import taking
from operations.state import Call, Start, Starts, State, Takes, Ticket, Tool
from operations.tracker import wait_line
from ticketing.vocabulary import SETTLED, Domain, Kind, Status
from operations.steps import Bash, Send, Step

__all__ = ["Begun", "Run", "RunTicket", "Start", "fault_message", "read_starts", "read_takes",
           "run_tickets", "start_command", "start_of"]

START = "start"
"""The action of `operate.py` that starts a run's pipeline."""

RUN_OPTION = "--run"
"""The option of `operate.py start` that gives the run whose step the call
makes, so that each run reads back its own pipelines."""

TASK_ID_FORM = re.compile(TASK_ID)

PASS_NAMES = frozenset(r.value for r in PASSES)

PASS_LIST = ", ".join(f"`{r.value}`" for r in PASSES)
"""The passes a start takes, as the error text of `operate.py start`
lists them."""

SCRIPT_SECONDS = 10
"""How long the load and the call of a run script may take at one read."""


@dataclass(frozen=True, kw_only=True)
class Standing:
    """Where a pipeline stands, as its run's script reads it, as
    `scripts/operate.py --help run` gives its fields."""
    stopped: str | None = None
    passing: bool = False
    held: bool = False


@dataclass(frozen=True)
class Begun(Standing):
    """A pipeline of a run, as its script reads it, as
    `scripts/operate.py --help run` gives its fields."""
    task: str
    passes: tuple[Role, ...]


@dataclass(frozen=True)
class Run:
    """What a run script reads: the tasks of the queue that no claim file
    and no pipeline of the run gives, in the queue's order, and the run's
    pipelines that run and that ended."""
    queue: tuple[str, ...]
    running: tuple[Begun, ...]
    ended: tuple[Begun, ...]


@dataclass(frozen=True)
class RunTicket:
    """A ticket, as a run script's `takes` reads it. `waits_on` is the
    change it waits on, `filed_by_run` whether a pipeline of the run, that
    runs or that ended, filed it (its domain is `task` and its subject is
    that pipeline's task), and `reached_by_run` whether a chain of links
    reaches it from a ticket a pipeline of the run filed
    (`taking.reached`), as a change that settles such a ticket is."""
    number: str
    kind: Kind
    status: Status
    domain: Domain
    subject: str
    filer: str
    depends_on: tuple[str, ...]
    waits_on: str | None
    filed_by_run: bool
    reached_by_run: bool


def run_tickets(state: State, run: Run) -> tuple[RunTicket, ...]:
    """The `RunTicket` of each ticket outside `tickets/closed/` and
    `tickets/deferred/`, in the tracker's order."""
    tasks = {b.task for b in (*run.running, *run.ended)}

    def filed(t: Ticket) -> bool:
        return t.domain is Domain.TASK and t.subject in tasks
    reached = taking.reached(state, {n for n, t in state.tracker.tickets.items() if filed(t)})
    out: list[RunTicket] = []
    for t in sorted(state.tracker.tickets.values(), key=lambda t: t.order):
        if t.status in SETTLED:
            continue
        line = wait_line(t)
        out.append(RunTicket(t.number, t.kind, t.status, t.domain, t.subject, t.filer,
                             t.depends_on, line.on_change if line is not None else None,
                             filed(t), t.number in reached))
    return tuple(out)


def read_takes(takes: Callable[[RunTicket], object], tickets: Iterable[RunTicket]) -> Takes:
    """The numbers of the tickets of `tickets` that `takes` admits, or the
    text of the first result that is no `bool`."""
    out: set[str] = set()
    for t in tickets:
        result = takes(t)
        if not isinstance(result, bool):
            return mctx("`takes` gave {result} for ticket {number}, which is no `bool`").format(
                result=repr(result), number=t.number)
        if result:
            out.add(t.number)
    return frozenset(out)


@dataclass(frozen=True)
class Started:
    """A pipeline of a run: the pipeline its call started, or the reason
    its call failed."""
    pipeline: Pipeline
    failed: str | None


def start_command(ln: Line, s: Start) -> str:
    return " ".join([RUN_COMMAND, START, RUN_OPTION, shlex.quote(run_id(ln)), s.task, *s.passes])


def run_id(ln: Line) -> str:
    """The run of the `Op run:` line `ln`, as its start calls give it: the
    time of its message and its path."""
    return f"{ln.message.time:.6f}:{ln.rest}"


def script_path(main: Path, ln: Line) -> Path:
    """The path of the script of the `Op run:` line `ln`: absolute, or
    relative to the main tree `main`."""
    return main / ln.rest


def given(state: State, ln: Line) -> Starts:
    """What the script of the `Op run:` line `ln` gave at this read."""
    return state.computed.run_starts[run_id(ln)]


def run_lines(lines: Iterable[Line]) -> list[Line]:
    """The `Op run:` lines of `lines`. A run stands while its line is among
    the lines the operator received (`state.State.received`)."""
    return [ln for ln in lines if ln.kind is Directive.RUN and ln.rest]


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Add to `parser`, after its action, the arguments of `operate.py`
    that `start` reads: its task id, its passes and its run."""
    parser.add_argument("ident")
    parser.add_argument("rest", nargs="*")
    parser.add_argument(RUN_OPTION)


def call_parser() -> argparse.ArgumentParser:
    """The parser of the words of a call of `operate.py` after the script."""
    parser = argparse.ArgumentParser(add_help=False, exit_on_error=False)
    parser.add_argument("action")
    add_arguments(parser)
    return parser


CALL_PARSER = call_parser()


def start_words(c: Call) -> tuple[str, Start] | None:
    """The run, the task and the passes of the call `c`, where it is a Bash
    call of `operate.py start`, or None."""
    if c.tool != Tool.BASH:
        return None
    return command_start(str(c.input.get("command", "")))


@cache
def command_start(command: str) -> tuple[str, Start] | None:
    """`start_words` of a Bash call of `command`. The procedures ask it of
    each call of the session's operators many times in one read."""
    lead = RUN_COMMAND.split()
    script = lead.index(COMMAND)
    for words in simple_commands(command):
        if len(words) > script and words[:script] == lead[:script] and words[script].endswith(COMMAND):
            try:
                args = CALL_PARSER.parse_args(words[script + 1:])
            except argparse.ArgumentError:
                continue
            start = start_of(args.ident, args.rest)
            if args.action == START and args.run is not None and start is not None:
                return args.run, start
    return None


def started(state: State, ln: Line) -> list[Started]:
    """The pipelines of the run of `ln`, in the order of their calls."""
    out: list[Started] = []
    for c in state.transcripts.calls:
        words = start_words(c)
        if words is None or words[0] != run_id(ln):
            continue
        p = Pipeline(words[1].task, words[1].passes, c.time, c.operator)
        failed = (c.result or "").strip() if c.result is not None and c.error else None
        out.append(Started(p, failed))
    return out


def view(state: State, listed: tuple[str, ...], ln: Line,
         stands: Mapping[Pipeline, tuple[bool, Standing]]) -> Run:
    """The `Run` the script of `ln` reads, where `listed` is the queue's
    full listing and `stands` gives, for each pipeline of the run, whether
    it ended and where it stands."""
    pipelines = started(state, ln)
    taken = {s.pipeline.task for s in pipelines}
    queue = tuple(t for t in listed if t not in state.git.claims and t not in taken)
    running: list[Begun] = []
    over: list[Begun] = []
    for s in pipelines:
        task, passes = s.pipeline.task, tuple(s.pipeline.passes)
        if s.failed is not None:
            over.append(Begun(task, passes, stopped=s.failed))
            continue
        ended, standing = stands[s.pipeline]
        (over if ended else running).append(Begun(task, passes, **asdict(standing)))
    return Run(queue, tuple(running), tuple(over))


def is_task_id(task: object) -> TypeGuard[str]:
    return isinstance(task, str) and TASK_ID_FORM.fullmatch(task) is not None


def start_of(task: object, passes: object) -> Start | None:
    """The start of the task id `task` and the non-empty sequence of
    passes `passes`, or None where they are in no such form."""
    if not is_task_id(task):
        return None
    if isinstance(passes, str) or not isinstance(passes, Iterable):
        return None
    listed = list(passes)
    if not listed or not all(p in PASS_NAMES for p in listed):
        return None
    return Start(task, tuple(Role(p) for p in listed))


def read_starts(result: object) -> Starts:
    """The starts of a script's result, or the text of the way it is in no
    form the command reads: an iterable of objects with a task id as
    `task` and a non-empty sequence of passes as `passes`."""
    if isinstance(result, (str, bytes)) or not isinstance(result, Iterable):
        return mctx("the result of `starts` is no iterable of starts")
    out: list[Start] = []
    for item in result:
        task = getattr(item, "task", None)
        passes = getattr(item, "passes", None)
        if not is_task_id(task):
            return mctx("the start {item} gives no task id as `task`").format(item=repr(item))
        start = start_of(task, passes)
        if start is None:
            return mctx("the start {item} gives no non-empty sequence of passes as "
                        "`passes`").format(item=repr(item))
        out.append(start)
    return tuple(out)


class Stopped(StrEnum):
    """What a fault stops a run from doing."""
    STARTS_NOTHING = mctx("starts nothing")
    TAKES_NOTHING = mctx("takes no ticket")


STARTS_NOTHING = Stopped.STARTS_NOTHING
TAKES_NOTHING = Stopped.TAKES_NOTHING


def fault_message(ln: Line, stopped: Stopped, fault: str) -> Send:
    """The message that gives the coordinator the fault that stops the run
    of its line `ln`."""
    return Send(COORDINATOR, mctx("The run of the line `{line}` {stopped}: "
                                  "{fault}").format(
        line=ln.text, stopped=stopped, fault=fault), f"{run_id(ln)} {stopped.name} {fault}")


def takes_given(state: State, ln: Line) -> Takes:
    """What the `takes` of the script of the `Op run:` line `ln` gave at this
    read."""
    return state.computed.run_takes[run_id(ln)]


def next_start(state: State, ln: Line, running: Iterable[Pipeline]) -> Step | None:
    """The run's next step: the call that starts the first start the
    script gave whose task no pipeline of `running` gives and that matches
    no pipeline of the run by its task and its passes, or None where the
    script gave a fault or no such start."""
    starts = given(state, ln)
    if isinstance(starts, str):
        return None
    busy = {p.task for p in running}
    had = {(s.pipeline.task, s.pipeline.passes) for s in started(state, ln)}
    for s in starts:
        if s.task not in busy and (s.task, s.passes) not in had:
            return Bash(start_command(ln, s), f"{s.task} {' '.join(s.passes)}",
                        occasion=run_id(ln))
    return None

