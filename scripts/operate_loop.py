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
from dataclasses import replace
from pathlib import Path

from collections.abc import Callable

import file_events
import script_calls
import step_journal
import ticket_log
import tree_reads
from accepted_messages import accepted_after
from agent_deliveries import last_delivered
from budgets import budget_of
from context_bound_hook import ACTIONS
from controlled_markdown import mctx
from file_reads import held_paths, stats_stand_but
from relay_reads import LOCK_DIR, read_relay, session_id, wait_lock, wait_running
from run_reads import agent_type
from state_assembly import DUE_SINCE, UNWAITED_SINCE, read_state, write_record
from state_reads import partial
from transcripts import find

from operations import briefs, order, plan, ticket_stall, unwaited
from operations.command_words import Action
from operations.constants import BLOCK_SECONDS, LIMIT_SECONDS, WAIT_CAP
from operations.pacing import Until
from operations.filing import filed, with_report
from operations.printing import batch_line, key_line, listing_line, printed
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


def arm_watchdog(me: str) -> None:
    """Print that the agent runs the command again, and end the process,
    once `LIMIT_SECONDS` have passed, as `--help next` gives it."""
    def expire(_signum: int, _frame: object) -> None:
        print(printed(Poll(), me, Path()), flush=True)
        script_calls.record()
        os._exit(0)
    signal.signal(signal.SIGALRM, expire)
    signal.alarm(LIMIT_SECONDS)


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
    (steps, scratch), accepted = waited(me, read_again(step_at), lambda out: not isinstance(out[0][0], Poll))
    head = steps[0]
    if isinstance(head, EndTurn | Wait) and accepted:
        head = Poll()
        steps = (head,)
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


def waited[T](me: str, out_at: Callable[[float], T], ready: Callable[[T], bool]) -> tuple[T, bool]:
    """The first output `out_at` gives at a full read that `ready` holds
    for, or that a message reached `me` at since the last delivery to it,
    with whether such a message reached it, or else the output of the full
    read at the deadline, `BLOCK_SECONDS` from the call (`watched`). The
    call is the one of `me` that runs (`single_instance`), and its watchdog
    (`arm_watchdog`) is disarmed at its return."""
    single_instance(me)
    arm_watchdog(me)
    path = find(me)
    since = last_delivered(path)

    def read(deadline: float) -> tuple[T, bool]:
        return out_at(deadline), accepted_after(path, since, [])

    out, accepted = watched(read, lambda o: ready(o[0]) or o[1], BLOCK_SECONDS)
    signal.alarm(0)
    return out, accepted


def watched[T](out_at: Callable[[float], T], ready: Callable[[T], bool], seconds: float) -> T:
    """The first output `out_at` gives at a full read that `ready` holds
    for, or else the output of the full read at the deadline, `seconds`
    from the call. `Reads` gives when each read starts and which read it
    is."""
    reads = Reads(time.monotonic() + seconds)
    changed: set[str] | None = None
    while True:
        started, cpu = time.monotonic(), cpu_seconds()
        reads.start(started, changed)
        stats_stand_but(changed)
        out = out_at(reads.deadline)
        spent = cpu_seconds() - cpu
        more, changed = reads.after(changed, ready(out), started, spent)
        if not more:
            break
    reads.close()
    return out


class Reads:
    """When each read of `watched` starts, and whether it is a full read,
    which reads each held source again, or a partial read, which reads
    again only the stats of the paths that changed
    (`file_reads.stats_stand_but`).

    A full read comes at the first read, at most `FALLBACK_SECONDS` after
    the last full read, before the deadline, and after a partial read whose
    output would end the call. Between them, the call waits on the file
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
        full read."""
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
            time.sleep(POLL_SECONDS)
            return True, None
        return True, self.changed_paths(self.changes, started, spent)

    def changed_paths(self, changes: file_events.Changes, started: float,
                      spent: float) -> set[str] | None:
        """Wait for the read after the one that started at `started` and
        took `spent` CPU seconds, and give the paths that changed since the
        last read for a partial read, or None for a full read."""
        full_due = min(self.full_at + FALLBACK_SECONDS, self.deadline - POLL_SECONDS)
        earliest = started + max(POLL_SECONDS, READ_SHARE * spent)
        time.sleep(max(min(earliest, full_due) - time.monotonic(), 0))
        changes.wait(full_due - time.monotonic())
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
    party (`unwaited.times`) for the next read. Where a run has not
    ended by `deadline`, the step is the wait."""
    here = tree_reads.scratch(session_id())
    while True:
        if not ran(here, deadline):
            return (Poll(),), here
        state, watch = read_and_record(me, here)
        step = plan.next_step(state, watch, wait_running(me))
        if isinstance(step, Bash) and not partial():
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
    those of that state."""
    state, watch = read_state(me)
    write_record(here, DUE_SINCE, ticket_stall.due_times(state))
    write_record(here, UNWAITED_SINCE, unwaited.times(state))
    return state, watch


def ran(scratch: Path, deadline: float) -> bool:
    """Whether each Bash run of the journal of `scratch` ended by
    `deadline`, waited on in steps of `RUN_POLL_SECONDS`."""
    while step_journal.running(scratch, time.time()):
        if time.monotonic() + RUN_POLL_SECONDS > deadline:
            return False
        time.sleep(RUN_POLL_SECONDS)
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
