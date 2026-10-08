"""The operator's command line and its loops: it reads the state, as
`operator_state` assembles it from the ticket tracker, git, the worktrees
and the transcripts of the session's operators, and prints the next step
of the operator's procedures, which the package `operations` computes.
`HELP`, which `--help` prints, gives its usage forms.

Each fact the command reads is in the tracker, in git, under `work/`, in
a transcript, or in a file it wrote for a call it printed (`steps.filed`),
which a transcript points to."""

import argparse
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

from operator_state import read_state  # noqa: E402
from profile_runs import budget_of  # noqa: E402
from transcripts import Refused  # noqa: E402
from tree_reads import git, main_tree  # noqa: E402

from operations import briefs, plan, steps  # noqa: E402
from operations.roles import PASSES, Role  # noqa: E402
from operations.steps import (FOREGROUND_MS, STEP_KEY, WAIT_SECONDS, Bash,  # noqa: E402
                             EndTurn, Launch, Poll, Send, Step, StopWait, Wait, filed, next_command,
                             passed_over_line, key_line, printed, with_report)
from operations.task_work import restore, set_aside  # noqa: E402

HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/operate.py next <agent id>
        uv run python scripts/operate.py wait <agent id>
        uv run python scripts/operate.py set-aside <task id> analyze|create
        uv run python scripts/operate.py restore <task id>
        uv run python scripts/operate.py pass-over <agent id> <key> '<line>'
        ```
    - `next` prints the next step of the operator whose agent id it is given: one call to make, with its parameters, the final reply, or the decision lines of a ticket analyst on a held step, for the operator to apply, where the operator that launched that analyst printed its final reply since. It writes the brief of a launch, and a message to an agent other than the coordinator, to a file under the session's scratchpad, and the call's prompt or message gives that file's path. A message to the coordinator that gives labeled items keeps its first line and gives the path of the file that holds its items. The brief of a launch other than a solver pass's gives the file the agent writes its final reply to, and ends with the line `Budget: N minutes`, followed on that line by what the agent does at its budget, where the budget of its agent type over every run of that type, as `profile_runs.py --help` gives a type's budget, is N minutes rounded up. A brief that gives items, as `profile_runs.py --help` gives them, takes the type's budget per item times the number of items it gives, and any other brief takes the type's budget. Where the type has no such budget, the brief has no such line. It holds back the launch of an agent type whose definition under `.claude/agents/` a commit of `master` changed less than {reload} seconds ago until those seconds have passed. Where no step is ready and no agent runs that this operator launched or last resumed itself, other than one a notification said has not reported yet, it blocks for up to {block} seconds until one is, then prints it, or prints that the operator runs it again.
    - Before each call it prints, `next` prints that step's key, on a line that gives the command to run after the call, so the text it prints ends with the call's last field. The key is the same at each read of the state that gives the same step. `pass-over` passes over the step whose key it is given, by the `Override:` or `Decision:` line it is given, which rules the step out, from the moment its call is made, in a Bash call of its own or with other commands. From then on, `next` passes that step over for each operator, gives that step, once, as one its procedure waits on, to a ticket analyst it launches to rule it, other than a launch of a ticket analyst to rule a step, and goes on with the other procedures. A pipeline whose next pass is passed over stops instead.
    - A step `next` printed counts as made by the call the operator made: a Bash call whose command runs the printed command among others, or the call the operator made right after the call of `next` that printed the step.
    - `wait` is the operator's wait in the background: it ends once the state gives a step, or after {wait} seconds.
    - `set-aside` sets aside a task's earlier work in the main worktree before an Analyze or a Create pass, and `restore` puts it back and removes the task's claim, as the section `Passes on a task` of `prompts/agents/notes/launching.md` gives.
    - The session is the one `CLAUDE_CODE_SESSION_ID` gives, and the command refuses where the shell gives none.
    """)

BLOCK_SECONDS = (FOREGROUND_MS // 1000) - 30
"""The longest foreground block of `next`, under the bound on a
foreground call, with room for the read of the state."""

POLL_SECONDS = 15
CALLS = (Launch, Send, Bash, StopWait)
"""The steps after whose call the operator runs `next` again."""
TASK_ID = re.compile(task.TASK_ID)


def with_budget(step: Launch) -> Launch:
    """`step` with the budget line HELP gives."""
    if step.role in PASSES:
        return step
    seconds = budget_of(step.role.agent_type, step.items, [])
    if seconds is None:
        return step
    return replace(step, brief=step.brief + "\n" + briefs.BUDGET.format(minutes=math.ceil(seconds / 60)))


def print_step(step: Step, scratch: Path, me: str) -> None:
    """Write the files `step` gives, then print it."""
    for path, text in filed(step, scratch).items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n")
    print(printed(step, me, scratch))


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


def next_step(me: str) -> int:
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
            if isinstance(step, CALLS):
                print(key_line(step, me))
            if isinstance(step, Launch):
                step = with_budget(with_report(step, state.scratch))
            print_step(step, state.scratch, me)
            return 0
        time.sleep(POLL_SECONDS)


def wait(me: str) -> int:
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() + POLL_SECONDS < deadline:
        time.sleep(POLL_SECONDS)
        step = plan.next_step(read_state(me))
        if not isinstance(step, (Wait, EndTurn)):
            print(mctx("A step is ready: run `{command}`.").format(command=next_command(me)))
            return 0
    print(mctx("The wait ended: run `{command}`.").format(command=next_command(me)))
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("--help", "-h"):
        print(HELP.format(block=BLOCK_SECONDS, wait=WAIT_SECONDS, reload=RELOAD_SECONDS))
        return 0
    parser = argparse.ArgumentParser(prog="operate.py", add_help=False)
    parser.add_argument("action", choices=["next", "wait", "set-aside", "restore",
                                           steps.PASS_OVER])
    parser.add_argument("ident")
    parser.add_argument("rest", nargs="*")
    args = parser.parse_args(argv)
    try:
        match args.action:
            case "next":
                return next_step(args.ident)
            case "wait":
                return wait(args.ident)
            case "set-aside":
                if (len(args.rest) != 1 or args.rest[0] not in (Role.ANALYZE, Role.CREATE)
                        or not TASK_ID.fullmatch(args.ident)):
                    parser.error("set-aside takes a task id and `analyze` or `create`")
                print(set_aside(main_tree(), args.ident, Role(args.rest[0])))
                return 0
            case steps.PASS_OVER:
                if len(args.rest) != 2 or not STEP_KEY.fullmatch(args.rest[0]):
                    parser.error("pass-over takes an agent id, a step's key and a line")
                print(passed_over_line(args.rest[0]))
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
