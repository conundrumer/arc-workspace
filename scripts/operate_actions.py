"""The actions of `operate.py`, and the steps of its `claim`, `start` and
`relay` subcommands, as `operate.py --help` gives them."""

import re
import sys
from enum import StrEnum
from pathlib import Path

from arc import task
from relay_reads import read_relay, session_id
from tree_reads import main_tree

from operations import relay, runs
from operations.command_words import Action
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
