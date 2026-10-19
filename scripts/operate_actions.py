"""The actions of `operate.py`, the steps of its `claim`, `start` and
`relay` subcommands, the record of the lines of its `send`, and the
output of its `waits`, as `operate.py --help` gives them."""

import re
import sys
import time
from enum import StrEnum
from pathlib import Path

from arc import task
from controlled_markdown import mctx
from operator_reads import operator_runs
from relay_reads import read_relay, session_id
from state_assembly import read_state
from tree_reads import main_tree

from operations import directives, relay, runs, ticket_stall, waits
from operations.constants import WAKE
from operations.state import record_lines
from operations.command_words import Action
from operations.printing import WAIT_ACTION
from operations.steps import Step
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


def send_lines(text: str) -> int:
    """Record the non-blank lines of `text` in the session's store, all of
    them or, where `directives.refused` refuses any, none, and print the
    message that wakes the operators, or the refused lines and fail."""
    texts = [ln for ln in text.splitlines() if ln.strip()]
    if not texts:
        print(NO_LINES, file=sys.stderr)
        return 1
    main = main_tree()
    bad = directives.refused(texts, main)
    if bad:
        print("\n".join([REFUSED, *bad]), file=sys.stderr)
        return 1
    record_lines(main, session_id(), texts, time.time())
    print(RECORDED)
    print(WAKE)
    return 0


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
