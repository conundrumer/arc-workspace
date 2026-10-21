"""The operator's command line: its actions, of which `next` and `relay`
run the loop of `operate_loop`, `wait` is `operate_loop`'s, `review` is
`operate_review`'s, and the other subcommands are `operate_actions`', and
its help, which `operate_help` holds. Run with a copy other than the main tree's,
`review` runs the main tree's copy (`tree_reads.run_in_main`).

Each fact the command reads is in the tracker, in git, under `work/`, in
a transcript, in a file it wrote for a call it printed (`operations.filing.filed`),
which a transcript points to, or in the session's step journal
(`step_journal`)."""

import argparse
import gc
import os
import sys
import time

from engine.checkout import ROOT

import script_calls
from controlled_markdown import mctx
from handbook.paths import console_importable, scripts_importable

console_importable()
scripts_importable()

import kept_reads  # noqa: E402
import operate_service  # noqa: E402
import step_journal  # noqa: E402
from usage_limit import USAGE_STALE  # noqa: E402
from agent_reports import RATE_LIMIT  # noqa: E402
from transcript_snapshots import Refused  # noqa: E402
from tree_reads import main_tree, run_in_main  # noqa: E402
from help_parts import print_help  # noqa: E402

from operations import codex_mode, journal, pacing, runs, trial_mode  # noqa: E402
from operations.directives import NUMBER  # noqa: E402
from operations.decisions import WRITE_SECONDS  # noqa: E402
from operations.command_words import Action  # noqa: E402
from operations.roles import Role  # noqa: E402
from operations.constants import (BLOCK_SECONDS, LIMIT_SECONDS, RUN_SECONDS, SUBAGENT_LIMIT,  # noqa: E402
                                  WAIT_CAP, WAIT_SECONDS_IDLE)
from operations.task_work import release, restore, set_aside  # noqa: E402
from operate_loop import block, operator_step, wait  # noqa: E402
from operate_actions import (TASK_ID, OperateAction, claim_task, print_waits, relay_step,  # noqa: E402
                             send_lines, set_bound, set_codex, set_trial)
from operate_help import PARTS, PURPOSES, USAGE, HelpPart  # noqa: E402
from operate_review import review  # noqa: E402

def main(argv: list[str]) -> int:
    codex_mode.enabled.cache_clear()
    trial_mode.enabled.cache_clear()
    if not argv or argv[0] in ("--help", "-h"):
        return print_help(argv[1:], HelpPart, lambda parts: USAGE.format(parts=parts), PURPOSES,
                          lambda part: PARTS[part].format(
                              block=BLOCK_SECONDS, limit=LIMIT_SECONDS, run=RUN_SECONDS,
                              journal=step_journal.JOURNAL,
                              bound=journal.BOUND,
                              write=round(WRITE_SECONDS), stale=USAGE_STALE, rate_limit=RATE_LIMIT,
                              script=runs.SCRIPT_SECONDS, factor=f"{pacing.EVEN_FACTOR:g}",
                              window=pacing.DEFAULT_WINDOW, subagents=SUBAGENT_LIMIT,
                              band=f"{pacing.BAND_PCT:g}", idle=WAIT_SECONDS_IDLE,
                              cap=WAIT_CAP))
    parser = argparse.ArgumentParser(prog="operate.py", add_help=False)
    parser.add_argument("action", choices=list(OperateAction))
    runs.add_arguments(parser)
    try:
        if argv == [OperateAction.SEND]:
            return send_lines(sys.stdin.read())
        if argv == [OperateAction.BOUND]:
            return set_bound([])
        if argv == [OperateAction.CODEX]:
            return set_codex([])
        if argv == [OperateAction.TRIAL]:
            return set_trial([])
        args = parser.parse_args(argv)
        match OperateAction(args.action):
            case OperateAction.NEXT:
                if operate_service.CURRENT.get() is None:
                    return operate_service.client(args.ident)
                return block(args.ident, Action.NEXT, lambda deadline: operator_step(args.ident, deadline))
            case OperateAction.RELAY:
                from relay_reads import session_id
                try:
                    operate_service.prepare(ROOT, session_id(),
                                           time.monotonic() + operate_service.START_SECONDS)
                except (OSError, operate_service.Expired, operate_service.Unavailable):
                    pass
                return block(args.ident, Action.RELAY, lambda deadline: relay_step(args.ident, deadline))
            case OperateAction.WAIT:
                if args.rest:
                    parser.error(mctx("wait takes an agent id alone"))
                return wait(args.ident)
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
            case OperateAction.SEND:
                parser.error(mctx("send takes its lines on its stdin alone"))
            case OperateAction.WAITS:
                if args.rest or NUMBER.fullmatch(args.ident) is None:
                    parser.error(mctx("waits takes a ticket number alone"))
                return print_waits(args.ident)
            case OperateAction.BOUND:
                if args.run is not None:
                    parser.error(mctx("bound takes no {run_option}").format(run_option=runs.RUN_OPTION))
                return set_bound([args.ident, *args.rest])
            case OperateAction.CODEX:
                if args.run is not None:
                    parser.error(mctx("codex takes no {run_option}").format(run_option=runs.RUN_OPTION))
                return set_codex([args.ident, *args.rest])
            case OperateAction.TRIAL:
                if args.run is not None:
                    parser.error(mctx("trial takes no {run_option}").format(run_option=runs.RUN_OPTION))
                return set_trial([args.ident, *args.rest])
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
    try:
        code = main(sys.argv[1:])
    finally:
        kept_reads.flush()
    sys.stdout.flush()
    sys.stderr.flush()
    # `os._exit` skips the `atexit` call that writes the record's line.
    script_calls.record()
    os._exit(code)
