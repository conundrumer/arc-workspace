"""The actions of `operate.py`, the steps of its `claim`, `start` and
`relay` subcommands, and the output of its `waits`, as `operate.py --help`
gives them."""

import re
import sys
from enum import StrEnum
from pathlib import Path

from arc import task
from controlled_markdown import mctx
from operator_reads import operator_runs
from relay_reads import read_relay, session_id
from state_assembly import read_state
from tree_reads import main_tree

from operations import relay, runs, ticket_stall, waits
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
