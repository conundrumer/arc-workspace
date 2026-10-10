"""The operator's command line and its loops: it reads the state, as
`operator_state` assembles it from the ticket tracker, git, the worktrees
and the transcripts of the session's operators, and prints the next step
of the operator's procedures, which the package `operations` computes.
`HELP`, which `--help` prints, gives its usage forms.

Each fact the command reads is in the tracker, in git, under `work/`, in
a transcript, or in a file it wrote for a call it printed (`operations.filing.filed`),
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

from agent_launches import accepted_after, last_delivered  # noqa: E402
from operator_state import read_state, read_watch  # noqa: E402
from profile_runs import budget_of  # noqa: E402
from transcripts import Refused, find  # noqa: E402
from tree_reads import git, main_tree  # noqa: E402

from operations import briefs, plan  # noqa: E402
from operations.decisions import WRITE_SECONDS  # noqa: E402
from operations.monitor import REPORT_TEXT, ROUTES  # noqa: E402
from operations.roles import PASSES, Role  # noqa: E402
from operations.filing import filed, with_report  # noqa: E402
from operations.printing import key_line, printed  # noqa: E402
from operations.steps import BLOCK_SECONDS, Bash, Launch, Poll, Send, Step  # noqa: E402
from operations.task_work import restore, set_aside  # noqa: E402

HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/operate.py next <agent id>
        uv run python scripts/operate.py set-aside <task id> analyze|create
        uv run python scripts/operate.py restore <task id>
        ```
    - `next` prints the next step of the operator whose agent id it is given: one call to make, with its parameters, or the final reply. Before the final reply, it prints a SendMessage call that sends the coordinator the reply's text, and the final reply it then prints is the line that says so. It writes the brief of a launch, and a message to an agent other than the coordinator, to a file under the session's scratchpad, and the call's prompt or message gives that file's path. The value of a prompt or a message parameter it prints stands between two lines of three backticks, and the value to pass is the text between those lines, without them. A message to the coordinator that gives labeled items keeps its first line and gives the path of the file that holds its items. The brief of a launch other than a solver pass's gives the file the agent writes its final reply to, and ends with the line `Budget: N minutes`, followed on that line by what the agent does at its budget, where the budget `profile_runs.py --help` gives the brief, over every run under the project directories, is N minutes rounded up. A brief that gives items, as `profile_runs.py --help` gives them, takes that budget per item times the number of items it gives, and any other brief takes that budget for a run. Where there is no such budget, the brief has no such line. It holds back the launch of an agent type whose definition under `.claude/agents/` a commit of `master` changed less than {reload} seconds ago until those seconds have passed. Where no step is ready, it blocks for up to {block} seconds until one is, then prints it, or prints that the operator runs it again. The block ends too, and it prints that the operator runs it again, once a message to the operator waits that the harness accepted after the latest `user` entry of the operator's transcript before the call: a SubagentHandback of an agent the operator launched or last resumed, or a SendMessage call, in any transcript of the session, to the operator's agent id or name, each with a result that gives success, and for SendMessage that it queued the message or resumed the operator. Each such message thus ends at most one call early, since the result of that call is a later `user` entry.
    - Before each call it prints, `next` prints that step's key, on a line that gives the command to run after the call, so the text it prints ends with the call's last field. The key is the same at each read of the state that gives the same step.
    - `next` applies the rulings that the coordinator gives an operator of the session, and that the reply of a ticket analyst on a held step gives, each a line in one of these forms, matched whole, past a list marker:
        - `Decision: <decision key> <choice>` rules a held step, with one of the choices that step gives.
        - `Override: <task id> <pass> <override>` gives the override, labelled as an override, in the brief of the next launch of that pass on that task.
        - `Override: pass over <step key>` passes over the step whose key it gives, for each operator: `next` gives that step, once, as one its procedure waits on, to a ticket analyst it launches to rule it, other than a launch of a ticket analyst to rule a step, and goes on with the other procedures. A pipeline whose next pass is passed over stops instead. A solver pass's key is `<task id>-<pass>`, its task id and its pass (`analyze`, `create` or `refine`), so a ruling can name a pass that was never printed, and the ruling holds whatever overrides the pass's brief gains.
    - A coordinator's line that opens with `Override:` or `Decision:` in none of these forms goes back to the coordinator once, as undecided. A ticket analyst's reply on a step that gives its decision key, with no ruling in these forms, goes back to it once, and where its answer gives none either, the step stays held. A step `next` cannot place gives no decision key: its ticket analyst makes the act it needs and gives no ruling.
    - A ticket file whose read refuses or fails, other than a file that moved during the read, leaves its ticket out of every procedure, and a ticket that depends on it waits. `next` gives that file, once for each content it has and once its last write is {write} seconds old, to a ticket analyst it launches, as a step it cannot place, with the read's failure, and goes on with every other procedure. Where the file still does not read once that analyst returned, the final reply gives it.
    - A step `next` printed counts as made by the call the operator made: a Bash call whose command runs the printed command among others, or the call the operator made right after the call of `next` that printed the step, other than a call of `next` alone.
    - `set-aside` sets aside a task's earlier work in the main worktree before an Analyze or a Create pass, and `restore` puts it back and removes the task's claim, as the section `Passes on a task` of `prompts/agents/notes/launching.md` gives.
    - The session is the one `CLAUDE_CODE_SESSION_ID` gives, and the command refuses where the shell gives none.
    {report_form}
    {routes}
    """)

POLL_SECONDS = 15
CALLS = (Launch, Send, Bash)
"""The steps after whose call the operator runs `next` again."""
TASK_ID = re.compile(task.TASK_ID)


def with_budget(step: Launch) -> Launch:
    """`step` with the budget line HELP gives."""
    if step.role in PASSES:
        return step
    seconds = budget_of(step.role, step.items, [])
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
    path = find(me)
    since = last_delivered(path)
    while True:
        state = read_state(me)
        step = plan.next_step(state, read_watch(state))
        if isinstance(step, Launch) and (left := reloading(step)) > 0:
            if time.monotonic() + left > deadline:
                step = Poll()
            else:
                time.sleep(left)
                continue
        if (not isinstance(step, Poll) or time.monotonic() + POLL_SECONDS > deadline
                or accepted_after(path, since, [])):
            if isinstance(step, CALLS):
                print(key_line(step, me))
            if isinstance(step, Launch):
                step = with_budget(with_report(step, state.scratch))
            print_step(step, state.scratch, me)
            return 0
        time.sleep(POLL_SECONDS)


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("--help", "-h"):
        print(HELP.format(block=BLOCK_SECONDS, reload=RELOAD_SECONDS, write=round(WRITE_SECONDS), report_form=REPORT_TEXT, routes=ROUTES))
        return 0
    parser = argparse.ArgumentParser(prog="operate.py", add_help=False)
    parser.add_argument("action", choices=["next", "set-aside", "restore"])
    parser.add_argument("ident")
    parser.add_argument("rest", nargs="*")
    args = parser.parse_args(argv)
    try:
        match args.action:
            case "next":
                return next_step(args.ident)
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
