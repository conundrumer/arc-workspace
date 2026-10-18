"""The operator's command line: its actions, of which `next` and `relay`
run the loop of `operate_loop`, `review` is `operate_review`'s, `waits`
prints the paths of `operations.waits`, and the other subcommands are
`operate_actions`', and its help, which
`operate_help` holds. Run with a copy other than the main tree's,
`review` runs the main tree's copy (`tree_reads.run_in_main`).

Each fact the command reads is in the tracker, in git, under `work/`, in
a transcript, in a file it wrote for a call it printed (`operations.filing.filed`),
which a transcript points to, or in the session's step journal
(`step_journal`)."""

import argparse
import gc
import os
import sys

import script_calls
from controlled_markdown import mctx
from handbook.paths import console_importable, scripts_importable

console_importable()
scripts_importable()

import kept_reads  # noqa: E402
import step_journal  # noqa: E402
from usage_limit import USAGE_STALE  # noqa: E402
from agent_reports import RATE_LIMIT  # noqa: E402
from transcript_snapshots import Refused  # noqa: E402
from tree_reads import main_tree, run_in_main  # noqa: E402
from help_parts import print_help  # noqa: E402

from operations import journal, pacing, runs, ticket_stall, waits  # noqa: E402
from operations.directives import NUMBER  # noqa: E402
from operations.decisions import WRITE_SECONDS  # noqa: E402
from operations.command_words import Action  # noqa: E402
from operations.roles import Role  # noqa: E402
from operations.constants import BLOCK_SECONDS, LIMIT_SECONDS, RUN_SECONDS, SUBAGENT_LIMIT  # noqa: E402
from operations.task_work import release, restore, set_aside  # noqa: E402
from operate_loop import block, operator_step  # noqa: E402
from operate_actions import TASK_ID, OperateAction, claim_task, relay_step  # noqa: E402
from operate_help import PARTS, PURPOSES, USAGE, HelpPart  # noqa: E402
from operate_review import review  # noqa: E402
from relay_reads import session_id  # noqa: E402
from operator_reads import operator_runs  # noqa: E402
from state_assembly import read_state  # noqa: E402

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


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("--help", "-h"):
        return print_help(argv[1:], HelpPart, lambda parts: USAGE.format(parts=parts), PURPOSES,
                          lambda part: PARTS[part].format(
                              block=BLOCK_SECONDS, limit=LIMIT_SECONDS, run=RUN_SECONDS,
                              journal=step_journal.JOURNAL,
                              bound=journal.BOUND,
                              write=round(WRITE_SECONDS), stale=USAGE_STALE, rate_limit=RATE_LIMIT,
                              script=runs.SCRIPT_SECONDS, factor=f"{pacing.EVEN_FACTOR:g}",
                              window=pacing.DEFAULT_WINDOW, subagents=SUBAGENT_LIMIT,
                              band=f"{pacing.BAND_PCT:g}"))
    parser = argparse.ArgumentParser(prog="operate.py", add_help=False)
    parser.add_argument("action", choices=list(OperateAction))
    runs.add_arguments(parser)
    try:
        args = parser.parse_args(argv)
        match OperateAction(args.action):
            case OperateAction.NEXT:
                return block(args.ident, Action.NEXT, lambda deadline: operator_step(args.ident, deadline))
            case OperateAction.RELAY:
                return block(args.ident, Action.RELAY, lambda deadline: relay_step(args.ident, deadline))
            case OperateAction.REVIEW:
                if args.rest:
                    parser.error(mctx("review takes an agent id alone"))
                status = run_in_main("operate.py", argv)
                return review(args.ident) if status is None else status
            case OperateAction.START:
                if args.run is None or runs.start_of(args.ident, args.rest) is None:
                    parser.error(mctx("start takes {run_option} with its run, a task id, and one or more of {pass_list}")
                                 .format(run_option=runs.RUN_OPTION, pass_list=runs.PASS_LIST))
                return claim_task(args.ident)
            case OperateAction.CLAIM | OperateAction.RELEASE:
                if args.rest or not TASK_ID.fullmatch(args.ident):
                    parser.error(mctx("{action} takes a task id alone").format(action=args.action))
                if args.action == OperateAction.CLAIM:
                    return claim_task(args.ident)
                release(main_tree(), args.ident)
                return 0
            case OperateAction.SET_ASIDE:
                if (len(args.rest) != 1 or args.rest[0] not in (Role.ANALYZE, Role.CREATE)
                        or not TASK_ID.fullmatch(args.ident)):
                    parser.error(mctx("set-aside takes a task id and `analyze` or `create`"))
                print(set_aside(main_tree(), args.ident, Role(args.rest[0])))
                return 0
            case OperateAction.RESTORE:
                if len(args.rest) > 1:
                    parser.error(mctx("restore takes a task id and, optionally, the reason its pipeline stopped"))
                restore(main_tree(), args.ident, args.rest[0] if args.rest else None)
                return 0
            case OperateAction.WAITS:
                if args.rest or NUMBER.fullmatch(args.ident) is None:
                    parser.error(mctx("waits takes a ticket number alone"))
                return print_waits(args.ident)
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
