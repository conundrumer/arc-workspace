"""The operator's command line: its actions, of which `next`, `relay` and
`review` run the loop of `operate_loop`, and its help, which
`operate_help` holds.

Each fact the command reads is in the tracker, in git, under `work/`, in
a transcript, in a file it wrote for a call it printed (`operations.filing.filed`),
which a transcript points to, or in the session's step journal
(`step_journal`)."""

import argparse
import gc
import os
import re
import sys
from enum import StrEnum
from pathlib import Path

import script_calls
from arc import task
from controlled_markdown import mctx
from handbook.paths import console_importable, scripts_importable

console_importable()
scripts_importable()

import kept_reads  # noqa: E402
import step_journal  # noqa: E402
from operator_reads import read_operator  # noqa: E402
from state_assembly import read_state  # noqa: E402
from relay_reads import read_relay, session_id  # noqa: E402
from usage_limit import USAGE_STALE  # noqa: E402
from agent_reports import RATE_LIMIT, parent_type  # noqa: E402
from run_reads import parent_id  # noqa: E402
from transcripts import find  # noqa: E402
from transcript_entries import Refused  # noqa: E402
from tree_reads import main_tree  # noqa: E402
from ticket_files import ticket_path  # noqa: E402
from ticket_numbers import parsed_number  # noqa: E402
from ticket_reads import read_ticket  # noqa: E402
from help_parts import print_help  # noqa: E402

from operations import doc_review, journal, pacing, relay, runs  # noqa: E402
from operations.decisions import WRITE_SECONDS  # noqa: E402
from operations.command_words import Action  # noqa: E402
from operations.roles import Role  # noqa: E402
from operations.constants import BLOCK_SECONDS, FOREGROUND_MS, LIMIT_SECONDS, SUBAGENT_LIMIT  # noqa: E402
from operations.steps import Launch, Step, Undecided  # noqa: E402
from operations.task_work import CLAIM_HELD, claim, restore, set_aside  # noqa: E402
from operate_loop import block, operator_step, prepared, print_step, serving  # noqa: E402
from operate_help import PARTS, PURPOSES, USAGE, HelpPart  # noqa: E402

TASK_ID = re.compile(task.TASK_ID)


class OperateAction(StrEnum):
    """An action of this script."""
    NEXT = Action.NEXT
    RELAY = Action.RELAY
    START = runs.START
    CLAIM = "claim"
    SET_ASIDE = "set-aside"
    RESTORE = "restore"
    REVIEW = Action.REVIEW


def claim_task(task_id: str) -> int:
    """Claim the task for the session, or print the session that holds
    its claim and fail."""
    holder = claim(main_tree(), task_id, session_id())
    if holder is not None:
        print(CLAIM_HELD.format(task=task_id, holder=holder), file=sys.stderr)
        return 1
    return 0


def review(editor: str) -> int:
    """Print the step `doc_review.editor_review` gives the doc editor
    `editor`, as `--help review` gives it."""
    path = find(editor)
    parent = parent_id(path)
    kind = parent_type(path)
    if kind != Role.OPERATOR.agent_type:
        print(doc_review.NO_OPERATOR.format(agent=editor))
        return 0
    state, _ = read_state(parent, change_filed(parent, editor))
    step = doc_review.editor_review(state, editor)
    if isinstance(step, str):
        print(step)
        return 0
    if isinstance(step, Undecided):
        print(f"operate: {step.what}", file=sys.stderr)
        return 1
    if not isinstance(step, Launch):
        raise TypeError(f"review step {step!r} is no launch")
    print_step(prepared(step, state.scratch), state.scratch, editor)
    return 0


def change_filed(operator: str, editor: str) -> float | None:
    """The time of the first log line of the change of the doc editor
    `editor`, as the launches of `operator` give that change, or None where
    they give no such launch or that ticket is not read."""
    agents = read_operator(operator, find(operator), main_tree(), [], {}).agents
    mine = [a for a in agents if a.agent_id == editor and a.role is Role.DOC_EDITOR]
    number = parsed_number(mine[-1].subject) if mine else None
    if number is None:
        return None
    try:
        return read_ticket(ticket_path(main_tree() / "tickets", number)).filed
    except (Refused, ValueError, OSError):
        return None


def relay_step(me: str, deadline: float) -> tuple[tuple[Step, ...], Path]:
    found, scratch = read_relay(me)
    return (relay.next_step(found),), scratch


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("--help", "-h"):
        return print_help(argv[1:], HelpPart, lambda parts: USAGE.format(parts=parts), PURPOSES,
                          lambda part: PARTS[part].format(
                              block=BLOCK_SECONDS, limit=LIMIT_SECONDS, foreground=FOREGROUND_MS // 1000,
                              journal=step_journal.JOURNAL,
                              bound=journal.BOUND,
                              write=round(WRITE_SECONDS), stale=USAGE_STALE, rate_limit=RATE_LIMIT,
                              script=runs.SCRIPT_SECONDS, factor=f"{pacing.EVEN_FACTOR:g}",
                              window=pacing.DEFAULT_WINDOW, operator=serving(Action.NEXT),
                              launcher=serving(Action.RELAY), subagents=SUBAGENT_LIMIT))
    parser = argparse.ArgumentParser(prog="operate.py", add_help=False)
    parser.add_argument("action", choices=list(OperateAction))
    runs.add_arguments(parser)
    args = parser.parse_args(argv)
    try:
        match OperateAction(args.action):
            case OperateAction.NEXT:
                return block(args.ident, Action.NEXT, lambda deadline: operator_step(args.ident, deadline))
            case OperateAction.RELAY:
                return block(args.ident, Action.RELAY, lambda deadline: relay_step(args.ident, deadline))
            case OperateAction.REVIEW:
                if args.rest:
                    parser.error(mctx("review takes an agent id alone"))
                return review(args.ident)
            case OperateAction.START:
                if args.run is None or runs.start_of(args.ident, args.rest) is None:
                    parser.error(mctx("start takes {run_option} with its run, a task id, and one or more of {pass_list}")
                                 .format(run_option=runs.RUN_OPTION, pass_list=runs.PASS_LIST))
                return claim_task(args.ident)
            case OperateAction.CLAIM:
                if args.rest or not TASK_ID.fullmatch(args.ident):
                    parser.error(mctx("claim takes a task id alone"))
                return claim_task(args.ident)
            case OperateAction.SET_ASIDE:
                if (len(args.rest) != 1 or args.rest[0] not in (Role.ANALYZE, Role.CREATE)
                        or not TASK_ID.fullmatch(args.ident)):
                    parser.error(mctx("set-aside takes a task id and `analyze` or `create`"))
                print(set_aside(main_tree(), args.ident, Role(args.rest[0])))
                return 0
            case OperateAction.RESTORE:
                if len(args.rest) > 1:
                    parser.error(mctx("restore takes a task id and, optionally, the reason its pipeline stopped"))
                restore(main_tree(), args.ident)
                return 0
    except Refused as exc:
        print(f"operate: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    # The state a call reads is large: a collection of the cyclic garbage
    # walks all of it, at each threshold the reads cross and at the exit
    # of the interpreter, for minutes on a session with thousands of
    # agents. The process makes little such garbage, and the system takes
    # back its memory at the exit.
    gc.disable()
    kept_reads.open_store()
    code = main(sys.argv[1:])
    kept_reads.flush()
    sys.stdout.flush()
    sys.stderr.flush()
    # `os._exit` skips the `atexit` call that writes the record's line.
    script_calls.record()
    os._exit(code)
