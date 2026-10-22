"""The loop of `operate.py next`, `relay` and `review`: it reads the
state, as `state_assembly` assembles it, and prints the next step of the
operator's procedures, which the package `operations` computes, within
the block and the guards that `operate.py --help next` gives (`waited`),
which `review` waits within too, and the block of `operate.py wait`
(`wait`), which prints nothing."""

import fcntl
import math
import os
import signal
import time
from dataclasses import dataclass, replace
from pathlib import Path

from collections.abc import Callable

import file_events
import read_interrupts
import script_calls
import operate_service
import step_journal
import ticket_log
import tree_reads
from accepted_messages import Inbox
from budgets import budget_of
from context_bound_hook import ACTIONS
from controlled_markdown import mctx
from file_reads import held_paths, stats_stand_but
from relay_reads import LOCK_DIR, read_relay, session_id, wait_lock, wait_running
from run_reads import agent_type
from session_records import DUE_SINCE, UNWAITED_SINCE, write_record
from shown_state import write_shown
from state_assembly import read_state
from state_reads import partial
from transcripts import find

from operations import briefs, order, plan, ticket_stall, unwaited
from operations.command_words import Action
from operations.constants import BLOCK_SECONDS, COORDINATOR, LIMIT_SECONDS, WAIT_CAP
from operations.pacing import Until
from operations.filing import filed, with_report
from operations.printing import batch_line, key_line, listing_line, printed
from operations.printed_forms import AFTER_TIMEOUT, STATE_READ_TIMEOUT
from operations.monitor import MonitorState
from operations.roles import Role
from operations.state import State
from operations.steps import Bash, EndTurn, Launch, Poll, Send, Step, Wait

POLL_SECONDS = 15
FALLBACK_SECONDS = 90
"""The longest time between the starts of two full reads of a call
(`waited`)."""
READ_SHARE = 10
"""A read starts no sooner than this many times the CPU seconds of the
read before it, after that read's start (`waited`)."""
CALLS = (Launch, Send)
"""The steps after whose call the operator runs `next` again."""


def with_budget(step: Launch) -> Launch:
    """`step` with the budget line `--help next` gives."""
    if step.role is not Role.CODE_EDITOR:
        return step
    seconds = budget_of(step.role, step.items, [])
    if seconds is None:
        return step
    return replace(step, brief=step.brief + "\n" + briefs.BUDGET.format(minutes=math.ceil(seconds / 60)))


def prepared(step: Step, scratch: Path) -> Step:
    """`step` with each launch it prints given its report file and its
    budget line."""
    match step:
        case Launch():
            return with_budget(with_report(step, scratch))
        case EndTurn(hold) if hold is not None and (wait := step.wait) is not None:
            return EndTurn(replace(hold, wait=with_budget(with_report(wait, scratch))))
        case _:
            return step


def print_step(step: Step, scratch: Path, me: str) -> None:
    """Write the files `step` gives, and those of the launch of an end of
    turn, then print it."""
    made = [wait] if isinstance(step, EndTurn) and (wait := step.wait) is not None else []
    for s in (step, *made):
        for path, text in filed(s, scratch).items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text + "\n")
    print(printed(step, me, scratch))


def single_instance(me: str) -> None:
    """End each other call of `next` or `relay` for `me` that runs, as
    `--help next` gives it, and hold the lock that marks this call as the
    one that runs until the process ends."""
    fd = os.open(LOCK_DIR / f"operate-{me}.lock", os.O_RDWR | os.O_CREAT, 0o600)
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            pass
        held = os.pread(fd, 32, 0).decode().strip()
        if held.isdigit() and int(held) != os.getpid():
            try:
                os.kill(int(held), signal.SIGTERM)
            except ProcessLookupError:
                pass
        time.sleep(0.2)
    os.ftruncate(fd, 0)
    os.pwrite(fd, f"{os.getpid()}\n".encode(), 0)


def arm_watchdog(me: str, output: Callable[[str], int] | None = None) -> None:
    """Print a failure report for the coordinator and end the process once
    `LIMIT_SECONDS` have passed, as `--help next` gives it. A caller can pass
    `output`, which prints and returns the exit status."""
    def expire(_signum: int, _frame: object) -> None:
        status = 1
        if output is None:
            timeout_output(me)
        else:
            status = output(me)
        script_calls.record()
        os._exit(status)
    signal.signal(signal.SIGALRM, expire)
    signal.alarm(LIMIT_SECONDS)


def timeout_output(me: str) -> None:
    step = Send(COORDINATOR, STATE_READ_TIMEOUT.format(agent=me, seconds=LIMIT_SECONDS),
                "state-read-timeout")
    print(AFTER_TIMEOUT, flush=True)
    print(printed(step, me, Path()), flush=True)


NOT_SERVED = mctx("{agent} is no {kind} of the session, so no step is printed: give your final "
                  "reply.")
"""The line `served` prints to an agent of another type than the one an
action serves."""


def serving(action: Action) -> str:
    """The agent type `action` serves, as `context_bound_hook.ACTIONS` gives it."""
    return next(k for k, a in ACTIONS.items() if a is action)


def served(me: str, action: Action) -> bool:
    """Whether the agent `me` is of the type `action` serves; where it is
    not, print `NOT_SERVED`."""
    kind = serving(action)
    if agent_type(find(me)) == kind:
        return True
    print(NOT_SERVED.format(agent=me, kind=kind))
    return False


def block(me: str, action: Action,
          step_at: Callable[[float], tuple[tuple[Step, ...], Path]]) -> int:
    """Print the steps of one output `step_at` gives, one step or several
    launches, with the scratchpad their files go under, by the deadline it
    is given, as `--help next` gives the block of `next` and `--help relay`
    the end of the turn of `relay`, each read made again once where a
    worktree or a file it reads is gone (`read_again`)."""
    if not served(me, action):
        return 0
    outcome = waited(me, read_again(step_at), lambda out: not isinstance(out[0][0], Poll))
    operate_service.check()
    if isinstance(outcome, MessageAccepted):
        with operate_service.side_effect():
            print_step(Poll(), Path(), me)
        return 0
    if isinstance(outcome, Running):
        print(outcome.text())
        return 0
    steps, scratch = outcome
    head = steps[0]
    with operate_service.side_effect():
        if action is Action.NEXT:
            step_journal.give(scratch, [s for s in steps if isinstance(s, CALLS)], me, time.time())
            if isinstance(head, EndTurn) and (hold := head.hold) is not None and head.wait is not None:
                held = hold.launch
                step_journal.give_failed(scratch, held, me, time.time(), listing_line(held))
        if len(steps) > 1:
            print(batch_line(steps, me, action))
        elif isinstance(head, CALLS):
            print(key_line(head, me, action))
        for step in steps:
            print_step(prepared(step, scratch), scratch, me)
    return 0


def read_again[T](out_at: Callable[[float], T]) -> Callable[[float], T]:
    """`out_at`, which reads the state and plans, called again once where
    a call raises `FileNotFoundError` or `ticket_log.Moved`: the second call
    lists the worktrees and their files again, so it reads no worktree or
    file that a merge removed, and no ticket file that another call moved,
    after the first call listed it. A second `FileNotFoundError` or `Moved`
    is raised, so a worktree that git still lists with its directory gone ends
    the command."""
    def again(deadline: float) -> T:
        try:
            return out_at(deadline)
        except (FileNotFoundError, ticket_log.Moved):
            return out_at(deadline)
    return again


def cpu_seconds() -> float:
    """The CPU seconds of this process's threads and of the child processes
    it has waited on, in user and system mode."""
    t = os.times()
    return t.user + t.system + t.children_user + t.children_system


class MessageAccepted:
    """A successful inbox wake-up, with no planned output."""


@dataclass
class Running:
    """A standalone call whose state read outlasts its bound, with the
    seconds the call has run; the read's kept results let the call made
    again go on from them."""
    seconds: float

    def text(self) -> str:
        """What the call prints: that the read runs, and to run it again."""
        return operate_service.running_text(operate_service.standalone_phase, self.seconds)


def waited[T](me: str, out_at: Callable[[float], T],
              ready: Callable[[T], bool]) -> T | MessageAccepted | Running:
    """Wait for confirmed planned output or an accepted inbox message.
    Inbox acceptance needs no completed state read. A standalone call whose
    read is still running `operate_service.FINISH_SECONDS` before
    `LIMIT_SECONDS` end returns `Running` at its next checkpoint, and the
    watchdog stays armed for a read that reaches none."""
    current = operate_service.CURRENT.get()
    standalone = current is None
    started = time.monotonic()
    if standalone:
        single_instance(me)
        limit = started + LIMIT_SECONDS
        arm_watchdog(me)
    else:
        limit = current.deadline
    finish = limit - operate_service.FINISH_SECONDS

    def bounded() -> None:
        if time.monotonic() >= finish:
            raise read_interrupts.Bounded()
    try:
        inbox = Inbox(find(me), [])
        with read_interrupts.scope(inbox.accepted):
            if not standalone:
                return watched(out_at, ready, BLOCK_SECONDS, finish)
            with read_interrupts.request_scope(bounded):
                return watched(out_at, ready, BLOCK_SECONDS, finish)
    except read_interrupts.Accepted:
        return MessageAccepted()
    except read_interrupts.Bounded:
        return Running(time.monotonic() - started)
    finally:
        if standalone:
            signal.alarm(0)


def watched[T](out_at: Callable[[float], T], ready: Callable[[T], bool], seconds: float,
               finish: float | None = None) -> T:
    """The first full actionable output, or the last full pending output
    when the block ends. With an absolute `finish` limit, each read after
    the first reserves the greatest completed read's wall duration; a
    partial read also reserves its full confirmation. Without that limit,
    the block ends with a full read at its scheduling deadline."""
    reads = Reads(time.monotonic() + seconds)
    changed: set[str] | None = None
    duration = 0.0
    pending: tuple[T] | None = None
    try:
        while True:
            read_interrupts.checkpoint()
            if finish is not None and pending is not None:
                remaining = finish - time.monotonic()
                if remaining < duration:
                    read_interrupts.checkpoint(force=True)
                    return pending[0]
                if remaining < 2 * duration:
                    changed = None
            started, cpu = time.monotonic(), cpu_seconds()
            reads.start(started, changed)
            stats_stand_but(changed)
            operate_service.check()
            deadline = reads.deadline
            if finish is not None:
                deadline = min(deadline, finish - duration)
            out = out_at(deadline)
            read_interrupts.checkpoint(force=True)
            duration = max(duration, time.monotonic() - started)
            spent = cpu_seconds() - cpu
            ends = ready(out)
            if changed is None:
                if ends:
                    return out
                pending = (out,)
            if finish is not None:
                reads.deadline = min(reads.deadline, finish - duration)
                if time.monotonic() + duration > finish:
                    assert pending is not None
                    read_interrupts.checkpoint(force=True)
                    return pending[0]
            more, changed = reads.after(changed, ends, started, spent)
            if not more:
                assert pending is not None
                read_interrupts.checkpoint(force=True)
                return pending[0]
    finally:
        reads.close()


class Reads:
    """When each read of `watched` starts, and whether it is a full read,
    which reads each held source again, or a partial read, which reads
    again only the stats of the paths that changed
    (`file_reads.stats_stand_but`).

    A full read comes at the first read, at most `FALLBACK_SECONDS` after
    the last full read, before the deadline, and after a partial read whose
    output would end the call, where `watched` admits that read. When no
    full read fits the call limit, `watched` returns its last full pending
    output. Between them, the call waits on the file
    events of the paths whose stats it holds (`file_events.Changes`), and a
    read that a change starts is a partial read. A read starts no sooner
    than `POLL_SECONDS`, nor `READ_SHARE` times the CPU seconds of the read
    before it (`cpu_seconds`), after that read's start. Where the stream does not start,
    each read is a full read, `POLL_SECONDS` apart."""

    def __init__(self, deadline: float) -> None:
        self.deadline = deadline
        self.full_at = time.monotonic()
        self.changes: file_events.Changes | None = None
        self.unwatched = False

    def start(self, at: float, changed: set[str] | None) -> None:
        """Note the start at `at` of a read, a partial one of the paths
        `changed`, or a full one where it is None."""
        if changed is None:
            self.full_at = at
            if self.changes is not None:
                self.changes.take()

    def after(self, changed: set[str] | None, ends: bool, started: float,
              spent: float) -> tuple[bool, set[str] | None]:
        """Whether another read follows the read of the paths `changed`, a
        full read where it is None, that started at `started`, took `spent`
        CPU seconds, and whose output would end the call where `ends`; and,
        once the wait for it is over, the paths of that read, or None for a
        full read. `watched` checks admission after this wait and can
        return the preceding full pending output."""
        if ends:
            return changed is not None, None
        if changed is None and time.monotonic() + POLL_SECONDS > self.deadline:
            return False, None
        if not self.unwatched and changed is None:
            try:
                if self.changes is None:
                    self.changes = file_events.Changes(held_paths())
                else:
                    self.changes.watch(held_paths())
            except file_events.Unwatched:
                self.unwatched = True
        if self.changes is None or self.unwatched:
            read_interrupts.sleep(POLL_SECONDS, operate_service.pause)
            return True, None
        return True, self.changed_paths(self.changes, started, spent)

    def changed_paths(self, changes: file_events.Changes, started: float,
                      spent: float) -> set[str] | None:
        """Wait for the read after the one that started at `started` and
        took `spent` CPU seconds, and give the paths that changed since the
        last read for a partial read, or None for a full read. `watched`
        can convert that partial read to a full read or return its last
        full pending output when the call limit admits no full read."""
        full_due = min(self.full_at + FALLBACK_SECONDS, self.deadline - POLL_SECONDS)
        earliest = started + max(POLL_SECONDS, READ_SHARE * spent)
        read_interrupts.sleep(max(min(earliest, full_due) - time.monotonic(), 0),
                              operate_service.pause)
        while time.monotonic() < full_due:
            read_interrupts.checkpoint()
            current = operate_service.CURRENT.get()
            if current is not None:
                current.check(code=False)
            interval = 0.2 if current is not None else 1.0
            changes.wait(min(interval, full_due - time.monotonic()))
            paths = changes.take()
            if paths:
                return paths
        return changes.take() if time.monotonic() < full_due else None

    def close(self) -> None:
        """Stop the wait on the file events."""
        if self.changes is not None:
            self.changes.close()


def operator_step(me: str, deadline: float) -> tuple[tuple[Step, ...], Path]:
    """The operator's next step, a launch given with the launches after it
    (`order.batch`).
    `steps.Undecided.reread` gives why the command reads the state again
    before it launches an analyst on a step marked `reread`. A Bash step
    the command runs itself, and it reads the state once each Bash run of
    the session's journal ended (`ran`), so that the read holds that run's
    moves. A Bash step planned at a partial read (`state_reads.partial`)
    is the output, with no run, so the full read `waited` makes after it
    plans again and runs the Bash step it gives. After each read, it
    writes the session's records of the times from which a step has been
    due (`ticket_stall.due_times`) and from which a ticket has waited on no
    party (`unwaited.times`) for the next read, and the record of the state
    the ticket dashboard shows. Where a run has not
    ended by `deadline`, the step is the wait."""
    here = tree_reads.scratch(session_id())
    while True:
        if not ran(here, deadline):
            return (Poll(),), here
        state, watch = read_and_record(me, here)
        read_interrupts.checkpoint()
        step = plan.next_step(state, watch, wait_running(me))
        if isinstance(step, Bash) and not partial():
            with operate_service.side_effect():
                step_journal.start_run(here, step, me, state.main_tree, time.time())
            continue
        if isinstance(step, Launch) and step.reread:
            state, watch = read_and_record(me, here)
            step = plan.next_step(state, watch, wait_running(me))
        if isinstance(step, Launch):
            return order.batch(state, watch, step), here
        return (step,), here


def read_and_record(me: str, here: Path) -> tuple[State, MonitorState]:
    """The state `read_state` gives `me`, once the records under `here` of
    the times from which a step has been due (`ticket_stall.due_times`) and
    from which a ticket has waited on no party (`unwaited.times`) hold
    those of that state, and the record of the state the ticket dashboard
    shows (`shown_state.Shown`) holds that state's."""
    state, watch = read_state(me)
    operate_service.check()
    record_state(here, state)
    return state, watch


@read_interrupts.deferred
def record_state(here: Path, state: State) -> None:
    with operate_service.side_effect():
        write_record(here, DUE_SINCE, ticket_stall.due_times(state))
        write_record(here, UNWAITED_SINCE, unwaited.times(state))
        write_shown(here, state)


def ran(scratch: Path, deadline: float) -> bool:
    """Whether each Bash run of the journal of `scratch` ended by
    `deadline`, waited on in steps of `RUN_POLL_SECONDS`."""
    while step_journal.running(scratch, time.time()):
        if time.monotonic() + RUN_POLL_SECONDS > deadline:
            return False
        read_interrupts.sleep(RUN_POLL_SECONDS, operate_service.pause)
    return True


RUN_POLL_SECONDS = 1.0


def wait(me: str) -> int:
    """Block, as `operate.py --help wait` gives it, for the operator `me`,
    or, where `me` is an operator launcher, for the last operator it
    launched, while holding the lock of `wait_lock` for `me`; where
    another call holds that lock, or the launcher launched no operator
    with a known agent id, return at once."""
    fd = os.open(wait_lock(me), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0
    operator = me
    if agent_type(find(me)) == serving(Action.RELAY):
        runs = read_relay(me)[0].runs
        operator = runs[-1].agent_id if runs else None
    if operator is None:
        return 0

    def ready_at(_deadline: float) -> Step:
        state, watch = read_state(operator)
        return plan.ready_step(state, watch)

    first = ready_at(0.0)
    if not isinstance(first, Poll):
        return 0
    seconds = float(WAIT_CAP)
    if isinstance(first.pace, Until):
        seconds = min(seconds, first.pace.time - time.time())
    watched(ready_at, lambda s: not isinstance(s, Poll) or s.pace != first.pace, seconds)
    return 0
