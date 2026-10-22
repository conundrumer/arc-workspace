"""The actions of `operate.py`, the steps of its `claim`, `start` and
`relay` subcommands, the record of the lines of its `send`, the output
of its `waits`, and the context bound its `bound` sets and prints, as
`operate.py --help` gives them."""

import os
import re
import sys
import time
from enum import StrEnum
from pathlib import Path

from arc import task
from context_bound_hook import CONTEXT_BOUND, OVERRIDE, override_read, tokens_of
from controlled_markdown import mctx
from operator_reads import operator_runs
from relay_reads import read_relay, session_id
from state_assembly import read_state
from ticket_numbers import TicketNumber, staged, ticket_number
from ticket_files import ticket_path, ticket_status
from ticket_form import ticket_kind
from ticket_log import check_moves, log_moves, read_ticket
from ticketing.vocabulary import COORDINATOR, Kind, Status, queued
from transcript_snapshots import Refused
from tree_reads import main_tree

from operations import directives, relay, runs, ticket_stall, waits
from operations import codex_mode, trial_mode
from operations.mode_switch import ModeSwitch, Scope
from operations.constants import WAKE
from operations.line_store import record_lines
from operations.command_words import Action
from operations.printing import WAIT_ACTION
from operations.steps import Step
from operations.state import Message
from operations.task_work import CLAIM_HELD, claim

TASK_ID = re.compile(task.TASK_ID)


class OperateAction(StrEnum):
    """An action of this script."""
    NEXT = Action.NEXT
    RELAY = Action.RELAY
    START = runs.START
    CLAIM = "claim"
    SET_ASIDE = "set-aside"
    RESTORE = "restore"
    RELEASE = "release"
    REVIEW = Action.REVIEW
    SEND = "send"
    WAITS = "waits"
    WAIT = WAIT_ACTION
    BOUND = "bound"
    CODEX = "codex"
    TRIAL = "trial"


DEFAULT_BOUND = "default"
"""The argument of `bound` that removes the override."""


def claim_task(task_id: str) -> int:
    """Claim the task for the session, or print the session that holds
    its claim and fail."""
    holder = claim(main_tree(), task_id, session_id())
    if holder is not None:
        print(CLAIM_HELD.format(task=task_id, holder=holder), file=sys.stderr)
        return 1
    return 0


def relay_step(me: str, deadline: float) -> tuple[tuple[Step, ...], Path]:
    found, scratch = read_relay(me)
    return (relay.next_step(found),), scratch


NO_LINES = mctx("operate: send takes one or more lines on its stdin")
REFUSED = mctx("operate: send recorded no line, since it refuses each line printed below; "
               "`uv run python scripts/operate.py --help send` gives the forms it accepts")
RECORDED = mctx("Recorded the lines for the operators. Send your running operator launcher the "
                "message below alone, or, where none runs, launch an operator launcher with it "
                "as its brief:")
RELEASE_NOTE = mctx("released by Op expedite")
RELEASE_REFUSED = mctx("operate: lines recorded; draft release refused: {reason}. "
                       "Run `send` again with the same lines to finish the releases.")


def send_lines(text: str) -> int:
    """Apply the coordinator's lines as `operate.py --help send` gives."""
    texts = [ln for ln in text.splitlines() if ln.strip()]
    if not texts:
        print(NO_LINES, file=sys.stderr)
        return 1
    main = main_tree()
    bad = directives.refused(texts, main)
    if bad:
        print("\n".join([REFUSED, *bad]), file=sys.stderr)
        return 1
    tickets = main / "tickets"
    try:
        releases = expedited_requests(tickets, texts)
    except Refused as exc:
        print(exc, file=sys.stderr)
        return 1
    record_lines(main, session_id(), texts, time.time())
    try:
        for number in releases:
            log_moves(tickets, number, queued(Status.DRAFT, Kind.REQUEST), COORDINATOR,
                      Status.DRAFT, None, RELEASE_NOTE)
    except Refused as exc:
        print(RELEASE_REFUSED.format(reason=exc), file=sys.stderr)
        return 1
    print(RECORDED)
    print(WAKE)
    return 0


def expedited_requests(tickets: Path, texts: list[str]) -> list[TicketNumber]:
    """The explicitly expedited draft requests, after checking their moves
    without writes. Other kinds and statuses retain their tracker state."""
    message = Message("", 0.0, None, "\n".join(texts), stored=True)
    lines = directives.message_lines(message, directives.Forms.PREFIXED)
    numbers = dict.fromkeys(n for n, _ in directives.numbers_in(lines, directives.Directive.EXPEDITE))
    releases: list[TicketNumber] = []
    for text in numbers:
        number = ticket_number(text)
        path = ticket_path(tickets, number)
        if ticket_status(path) is Status.DRAFT and ticket_kind(read_ticket(path)) is Kind.REQUEST:
            check_moves(tickets, number, queued(Status.DRAFT, Kind.REQUEST), COORDINATOR,
                        Status.DRAFT, None, RELEASE_NOTE)
            releases.append(number)
    return releases


def print_waits(number: str) -> int:
    """Print the paths of links from ticket `number` (`waits.paths`), from
    the state `next` reads for the session's latest operator, or fail
    where no operator of the session ran `next`."""
    operators = operator_runs(session_id(), "")
    if not operators:
        print(mctx("operate: no operator of the session ran `next`"), file=sys.stderr)
        return 1
    state, _ = read_state(operators[-1][0])
    print(waits.rendered(state, waits.paths(state, number, ticket_stall.stalled(state))))
    return 0


def set_bound(args: list[str]) -> int:
    """Write the override the arguments `args` of `bound` give, or remove
    it for `DEFAULT_BOUND`, then print the bound in force and its source;
    fail on any other arguments."""
    main = main_tree()
    path = main / OVERRIDE
    match args:
        case []:
            pass
        case [word] if word == DEFAULT_BOUND:
            path.unlink(missing_ok=True)
        case [word] if (tokens := tokens_of(word)) is not None:
            with staged(path.parent, f"{tokens}\n") as tmp:
                os.replace(tmp, path)
        case _:
            print(mctx("operate: bound takes nothing, a positive whole number of tokens, "
                       "or `{default}`").format(default=DEFAULT_BOUND), file=sys.stderr)
            return 1
    override = override_read(main)
    print(f"{CONTEXT_BOUND} default" if override is None else f"{override} override")
    return 0


def set_codex(args: list[str]) -> int:
    """Set or print the switch, as `operate.py --help` gives it."""
    return set_mode(args, codex_mode.SWITCH)


def set_trial(args: list[str]) -> int:
    """Set or print the switch, as `operate.py --help` gives it."""
    return set_mode(args, trial_mode.SWITCH)


def set_mode(args: list[str], switch: ModeSwitch) -> int:
    main = main_tree()
    if switch.scope is Scope.SESSION:
        session_id()
    path = switch.path(main)
    assert path is not None
    match args:
        case []:
            pass
        case ["off"]:
            path.unlink(missing_ok=True)
        case ["on"]:
            with staged(path.parent, "on\n") as tmp:
                os.replace(tmp, path)
        case _:
            print(mctx("operate: {mode} takes nothing, on, or off").format(mode=switch.name), file=sys.stderr)
            return 1
    print("on" if switch.read(main) else "off")
    return 0
