"""The loop of `operate.py next`, `relay` and `review`: it reads the
state, as `state_assembly` assembles it, and prints the next step of the
operator's procedures, which the package `operations` computes, within
the block and the guards that `operate.py --help next` gives (`waited`),
which `review` waits within too."""

import fcntl
import math
import os
import signal
import time
from dataclasses import replace
from pathlib import Path

from collections.abc import Callable

import script_calls
import step_journal
from accepted_messages import accepted_after
from agent_deliveries import last_delivered
from budgets import budget_of
from context_bound_hook import ACTIONS
from controlled_markdown import mctx
from run_reads import agent_type
from state_assembly import read_state
from transcripts import find

from operations import briefs, order, plan
from operations.command_words import Action
from operations.constants import BLOCK_SECONDS, LIMIT_SECONDS
from operations.filing import filed, with_report
from operations.printing import batch_line, key_line, listing_line, printed
from operations.roles import Role
from operations.steps import Bash, EndTurn, Launch, ListingHold, Poll, Send, Step

POLL_SECONDS = 15
CALLS = (Launch, Send)
"""The steps after whose call the operator runs `next` again."""
LOCK_DIR = Path("/tmp")


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
        case EndTurn(ListingHold(held, Launch() as wait)):
            return EndTurn(ListingHold(held, with_budget(with_report(wait, scratch))))
        case _:
            return step


def print_step(step: Step, scratch: Path, me: str) -> None:
    """Write the files `step` gives, and those of the launch of an end of
    turn, then print it."""
    made = [step.hold.wait] if isinstance(step, EndTurn) and step.hold and step.hold.wait else []
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
    the end of the turn of `relay`."""
    if not served(me, action):
        return 0
    (steps, scratch), accepted = waited(me, step_at, lambda out: not isinstance(out[0][0], Poll))
    head = steps[0]
    if isinstance(head, EndTurn) and accepted:
        head = Poll()
        steps = (head,)
    if action is Action.NEXT:
        step_journal.give(scratch, [s for s in steps if isinstance(s, CALLS)], me, time.time())
        if isinstance(head, EndTurn) and head.hold is not None and head.hold.wait is not None:
            step_journal.give_failed(scratch, head.hold.launch, me, time.time(),
                                     listing_line(head.hold.launch))
    if len(steps) > 1:
        print(batch_line(steps, me, action))
    elif isinstance(head, CALLS):
        print(key_line(head, me, action))
    for step in steps:
        print_step(prepared(step, scratch), scratch, me)
    return 0


def waited[T](me: str, out_at: Callable[[float], T], ready: Callable[[T], bool]) -> tuple[T, bool]:
    """The first output `out_at` gives, read again each `POLL_SECONDS`
    with the deadline `BLOCK_SECONDS` from the call, that `ready` holds
    for, or the last one read where that deadline would pass before the
    next read or a message reached `me` since the last delivery to it,
    with whether such a message reached it. The call is the one of `me`
    that runs (`single_instance`), and its watchdog (`arm_watchdog`) is
    disarmed at its return."""
    single_instance(me)
    arm_watchdog(me)
    deadline = time.monotonic() + BLOCK_SECONDS
    path = find(me)
    since = last_delivered(path)
    while True:
        out = out_at(deadline)
        accepted = accepted_after(path, since, [])
        if ready(out) or accepted or time.monotonic() + POLL_SECONDS > deadline:
            signal.alarm(0)
            return out, accepted
        time.sleep(POLL_SECONDS)


def operator_step(me: str, deadline: float) -> tuple[tuple[Step, ...], Path]:
    """The operator's next step, a launch given with the launches after it
    (`order.batch`).
    `steps.Undecided.reread` gives why the command reads the state again
    before it launches an analyst on a step marked `reread`. A Bash step
    the command runs itself, after each Bash run of the session's journal
    ended, and reads the state again once it ended (`ran`); where a run
    has not ended by `deadline`, the step is the wait."""
    while True:
        state, watch = read_state(me)
        if not ran(state.scratch, deadline):
            return (Poll(),), state.scratch
        step = plan.next_step(state, watch)
        if isinstance(step, Bash):
            step_journal.start_run(state.scratch, step, me, state.main_tree, time.time())
            continue
        if isinstance(step, Launch) and step.reread:
            state, watch = read_state(me)
            step = plan.next_step(state, watch)
        if isinstance(step, Launch):
            return order.batch(state, watch, step), state.scratch
        return (step,), state.scratch


def ran(scratch: Path, deadline: float) -> bool:
    """Whether each Bash run of the journal of `scratch` ended by
    `deadline`, waited on in steps of `RUN_POLL_SECONDS`."""
    while step_journal.running(scratch, time.time()):
        if time.monotonic() + RUN_POLL_SECONDS > deadline:
            return False
        time.sleep(RUN_POLL_SECONDS)
    return True


RUN_POLL_SECONDS = 1.0
