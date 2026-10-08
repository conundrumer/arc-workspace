"""The command line of the `operations` mod's loop: it reads the state, as
`loop_state` assembles it from the ticket tracker, git, the worktrees,
the session's transcripts and the loop's record (`ops_record`), and gives
the next step of the procedures, which the package `operations` computes.
`HELP`, which `--help` prints, gives its usage forms.

Each fact the command reads is in the tracker, in git, under `work/`, in
a transcript, in the loop's record, or in a file it wrote for a call it
gave (`steps.filed`), which the record points to."""

import argparse
import json
import math
import re
import sys
import time
from dataclasses import replace
from pathlib import Path

from arc import task
from controlled_markdown import mctx
from engine import checkout
from handbook.paths import console_importable, importable

console_importable()
# `scripts/` is no package: a test loads this module by its path, with
# `scripts/` off `sys.path`, and the modules below import from there.
importable(checkout.scripts())

from loop_state import read_state  # noqa: E402
from ops_record import LOOP, Mark, append, is_loop, mark  # noqa: E402
from profile_runs import budget_of  # noqa: E402
from ticket_numbers import session_id  # noqa: E402
from transcripts import Refused  # noqa: E402
from tree_reads import git, main_tree, scratch  # noqa: E402

from operations import briefs, plan, steps  # noqa: E402
from operations.roles import PASSES, Role  # noqa: E402
from operations.steps import BLOCK_SECONDS, Launch, Poll, Step, filed, with_report  # noqa: E402
from operations.task_work import restore, set_aside  # noqa: E402

HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/operate.py call {loop}
        uv run python scripts/operate.py made {loop} '<call>'
        uv run python scripts/operate.py tell {loop} '<line>'
        uv run python scripts/operate.py start|stop {loop}
        uv run python scripts/operate.py set-aside <task id> analyze|create
        uv run python scripts/operate.py restore <task id>
        ```
    - `call` gives the next step of the loop of the `operations` mod, as one line of JSON: `kind` names the call, the other fields are its parameters, and `key` is the step's key, the same at each read of the state that gives the same step. A step of kind `wait` gives no call, and a step of kind `reply` ends the loop with its `text`. It writes the brief of a launch, and a message to an agent other than the coordinator, to a file under the session's scratchpad, and the call's prompt or message gives that file's path. A message to the coordinator that gives labeled items keeps its first line and gives the path of the file that holds its items. The brief of a launch other than a solver pass's gives the file the agent writes its final reply to, and ends with the line `Budget: N minutes`, followed on that line by what the agent does at its budget, where the budget of its agent type over every run of that type, as `profile_runs.py --help` gives a type's budget, is N minutes rounded up. A brief that gives items, as `profile_runs.py --help` gives them, takes the type's budget per item times the number of items it gives, and any other brief takes the type's budget. Where the type has no such budget, the brief has no such line. It holds back the launch of an agent type whose definition under `.claude/agents/` a commit of `master` changed less than {reload} seconds ago until those seconds have passed. Where no step is ready and no agent the loop launched runs, it blocks for up to {block} seconds until one is.
    - `made` adds the call the mod made for a step to the loop's record, which the state reads as the calls the loop made: `<call>` is a JSON object with the call's `tool`, `input`, `result`, `error`, and the `key` that `call` gave. A step counts as made by the recorded call that gives its key.
    - `tell` gives the loop the coordinator's line, which it reads as a line of the coordinator's message.
    - `start` and `stop` record that the loop starts or stops, as the mod runs them, for the monitor loop, as `monitor.py --help` gives.
    - `set-aside` sets aside a task's earlier work in the main worktree before an Analyze or a Create pass, and `restore` puts it back and removes the task's claim, as the section `Passes on a task` of `prompts/agents/notes/launching.md` gives.
    - The session is the one `CLAUDE_CODE_SESSION_ID` gives, and the command refuses where the shell gives none.
    """)

POLL_SECONDS = 15
TASK_ID = re.compile(task.TASK_ID)


def with_budget(step: Launch) -> Launch:
    """`step` with the budget line HELP gives."""
    if step.role in PASSES:
        return step
    seconds = budget_of(step.role.agent_type, step.items, [])
    if seconds is None:
        return step
    return replace(step, brief=step.brief + "\n" + briefs.BUDGET.format(minutes=math.ceil(seconds / 60)))


def write_files(step: Step, scratch: Path) -> None:
    for path, text in filed(step, scratch).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n")


RELOAD_SECONDS = 30
"""How long after a change to an agent's definition the harness takes to
load it, as the section `Launching` of `prompts/agents/notes/launching.md`
gives."""


def reloading(step: Launch) -> float:
    """The seconds left until the harness has loaded the definition of the
    agent type `step` launches, after the last commit of `master` that
    changed it, or 0."""
    path = f".claude/agents/{step.role.agent_type}.md"
    out = git(main_tree(), "log", "-1", "--format=%ct", "master", "--", path).strip()
    return max(0.0, float(out) + RELOAD_SECONDS - time.time()) if out else 0.0


def ready_step(me: str) -> tuple[Step, Path]:
    """The next step of `me`, as HELP gives `call`'s blocking, with the
    scratchpad its files go under."""
    deadline = time.monotonic() + BLOCK_SECONDS
    while True:
        state = read_state(me)
        step = plan.next_step(state)
        if isinstance(step, Launch) and (left := reloading(step)) > 0:
            if time.monotonic() + left > deadline:
                step = Poll()
            else:
                time.sleep(left)
                continue
        if not isinstance(step, Poll) or time.monotonic() + POLL_SECONDS > deadline:
            return step, state.scratch
        time.sleep(POLL_SECONDS)


def prepared(step: Step, scratch: Path) -> Step:
    """`step` with its report and budget lines, after its files are written."""
    if isinstance(step, Launch):
        step = with_budget(with_report(step, scratch))
    write_files(step, scratch)
    return step


def call_step(me: str) -> int:
    step, scratch = ready_step(me)
    print(json.dumps(steps.call(prepared(step, scratch), scratch, steps.key(step))))
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("--help", "-h"):
        print(HELP.format(block=BLOCK_SECONDS, reload=RELOAD_SECONDS, loop=LOOP))
        return 0
    parser = argparse.ArgumentParser(prog="operate.py", add_help=False)
    parser.add_argument("action", choices=["call", "made", "tell", *Mark, "set-aside",
                                           "restore"])
    parser.add_argument("ident")
    parser.add_argument("rest", nargs="*")
    args = parser.parse_args(argv)
    if args.action in ("call", "made", "tell") and not is_loop(args.ident):
        parser.error(f"{args.action} takes the loop's id, `{LOOP}`")
    try:
        match args.action:
            case "made":
                if len(args.rest) != 1:
                    parser.error("made takes the loop's id and a call")
                append(scratch(session_id()), args.ident, json.loads(args.rest[0]))
                return 0
            case "tell":
                if len(args.rest) != 1:
                    parser.error("tell takes the loop's id and a line")
                append(scratch(session_id()), args.ident, {"line": args.rest[0]})
                return 0
            case "call":
                return call_step(args.ident)
            case Mark.START | Mark.STOP:
                if args.ident != LOOP or args.rest:
                    parser.error(f"{args.action} takes the loop's id, `{LOOP}`, alone")
                mark(scratch(session_id()), args.ident, Mark(args.action))
                return 0
            case "set-aside":
                if (len(args.rest) != 1 or args.rest[0] not in (Role.ANALYZE, Role.CREATE)
                        or not TASK_ID.fullmatch(args.ident)):
                    parser.error("set-aside takes a task id and `analyze` or `create`")
                print(set_aside(main_tree(), args.ident, Role(args.rest[0])))
                return 0
            case _:
                if args.rest:
                    parser.error("restore takes a task id alone")
                restore(main_tree(), args.ident)
                return 0
    except Refused as exc:
        print(f"operate: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
