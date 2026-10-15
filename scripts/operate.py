"""The operator's command line and its loops: it reads the state, as
`operator_state` assembles it from the ticket tracker, git, the worktrees
and the transcripts of the session's operators, and prints the next step
of the operator's procedures, which the package `operations` computes.
`USAGE`, which `--help` prints, gives its usage forms, and `PARTS` the
rest of its help, a part at a time.

Each fact the command reads is in the tracker, in git, under `work/`, in
a transcript, or in a file it wrote for a call it printed (`operations.filing.filed`),
which a transcript points to."""

import argparse
import fcntl
import gc
import math
import os
import re
import signal
import sys
import time
from dataclasses import replace
from enum import StrEnum
from pathlib import Path

from arc import task
from controlled_markdown import mctx
from handbook.paths import console_importable, scripts_importable

console_importable()
scripts_importable()

from agent_launches import accepted_after, last_delivered  # noqa: E402
from operator_reads import read_operator  # noqa: E402
from operator_state import read_state  # noqa: E402
from relay_reads import read_relay, session_id  # noqa: E402
from usage_limit import USAGE_STALE  # noqa: E402
from agent_reports import RATE_LIMIT, parent_type  # noqa: E402
from profile_runs import budget_of  # noqa: E402
from run_reads import parent_id  # noqa: E402
from transcripts import Refused, find  # noqa: E402
from tree_reads import main_tree  # noqa: E402
from ticket_files import ticket_path  # noqa: E402
from ticket_numbers import parsed_number  # noqa: E402
from ticket_reads import read_ticket  # noqa: E402
from help_parts import print_help  # noqa: E402

from operations import briefs, doc_review, plan, relay, runs  # noqa: E402
from operations.decisions import WRITE_SECONDS  # noqa: E402
from operations.monitor import ALERTS  # noqa: E402
from operations.command_words import Action  # noqa: E402
from operations.roles import BARE_BRIEFS, Role  # noqa: E402
from operations.filing import filed, with_report  # noqa: E402
from operations.printing import key_line, printed  # noqa: E402
from operations.state import State  # noqa: E402
from operations.steps import (BLOCK_SECONDS, LIMIT_SECONDS, Bash, EndTurn, Launch, Poll, Send,  # noqa: E402
                              Step, Undecided)
from collections.abc import Callable  # noqa: E402
from operations.task_work import CLAIM_HELD, claim, restore, set_aside  # noqa: E402


class HelpPart(StrEnum):
    """Each part of the help, by the word `--help` takes to print it, in the
    order the bare `--help` lists them."""
    NEXT = "next"
    RULINGS = "rulings"
    RUN = "run"
    RELAY = "relay"
    REVIEW = "review"
    ALERTS = "alerts"


USAGE = mctx("""
    - Usage:
        ```
        uv run python scripts/operate.py next <agent id>
        uv run python scripts/operate.py relay <agent id>
        uv run python scripts/operate.py review <agent id>
        uv run python scripts/operate.py start --run <run> <task id> <pass> ...
        uv run python scripts/operate.py claim <task id>
        uv run python scripts/operate.py set-aside <task id> analyze|create
        uv run python scripts/operate.py restore <task id> [<reason>]
        ```
    {parts}
    - `claim` claims a task for the session, and, where a claim on the task stands, fails and prints the session that holds it.
    - `set-aside` sets aside a task's earlier work in the main worktree before an Analyze or a Create pass, as [Passes on a task](prompts/agents/notes/launching.md#passes-on-a-task) gives.
    - `restore` puts that work back and removes the task's claim, as that section gives.
        - `<reason>` is the reason the task's pipeline stopped, or empty where that pipeline ran to its end, and `next` then takes that pipeline as ended with that reason.
    - The session is the one `CLAUDE_CODE_SESSION_ID` gives.
    """)
"""The help the bare `--help` prints."""

PURPOSES = {
    HelpPart.NEXT: mctx("what `next` prints, and when a step counts as made"),
    HelpPart.RULINGS: mctx("the forms of the rulings `next` applies"),
    HelpPart.RUN: mctx("the `Run:` line and the run script `next` reads"),
    HelpPart.RELAY: mctx("what `relay` prints"),
    HelpPart.REVIEW: mctx("what `review` prints"),
    HelpPart.ALERTS: mctx("the alerts `next` sends"),
}
"""What each part of the help gives."""

PARTS = {
    HelpPart.NEXT: mctx("""
    - `next` prints the next step of the operator whose agent id it is given: one call to make, with its parameters, or the final reply.
        - Before the final reply, it prints a SendMessage call that sends the reply's text to the agent that launched the operator.
        - It then prints the SubagentHandback call whose message is the line that says so.
        - It writes the brief of a launch, and a message to an agent other than the coordinator, to a file under the session's scratchpad, and the call's prompt or message gives that file's path.
        - The value of a prompt or a message parameter it prints stands between two lines of three backticks, and the value to pass is the text between those lines, without them.
        - A message to the coordinator that gives labeled items keeps its first line and gives the path of the file that holds its items.
        - The brief of a launch other than a solver pass's gives the file the agent writes its final reply to.
        - The brief of a launch other than a solver pass's ends with the line `Budget: N minutes`, followed on that line by what the agent does at its budget, where `profile_runs.py --help budget` gives a budget for the brief over every run under the project directories.
            - N is that budget in minutes, rounded up: the budget per item times the number of items for a brief that gives items, as that help gives them, and the budget per run for any other brief.
        - Where its last call of a launch failed with a result whose first line is `Agent type '<agent type>' not found`, or starts with that text followed by `.`, less than {load} seconds after the last write of its rendered definition `.claude/agents/<agent type>.md`, it gives the launch again once {retry} seconds have passed since that call, in place of a step on that failure.
        - An agent whose latest notification has the status `failed` and a summary that gives `{rate_limit}` was stopped by the usage limit.
            - `next` counts such an agent as running, and takes nothing from that notification as its report.
            - Once the usage file of the Claude config directory (`$CLAUDE_CONFIG_DIR/usage.json`, or `~/.claude/usage.json` where that is unset) was written after that stop, less than {stale} seconds ago, with a `used_pct` under 100 in each window, `next` prints, ahead of every other step, a SendMessage call that asks the agent to carry on its work, once for each such stop.
        - Where no step is ready, it blocks for up to {block} seconds until one is, then prints it, or prints that the operator runs it again.
            - The block also ends, and it prints that the operator runs it again, once a message to the operator waits that the harness accepted after the latest `user` entry of the operator's transcript before the call.
        - Where it has printed no step {limit} seconds after it started, it prints that the operator runs it again, and ends.
        - A call of `next` or `relay` ends each call of either for the same agent id that runs.
    - Before each call it prints, `next` prints that step's key, on a line that gives the command to run after the call.
        - The key is the same at each read of the state that gives the same step.
    - A ticket file whose read refuses or fails, other than a file that moved during the read, leaves its ticket out of every procedure.
        - A ticket that depends on it waits.
        - `next` gives that file, once for each content it has and once its last write is {write} seconds old, to a ticket analyst it launches, as a step it cannot place, with the read's failure, and goes on with every other procedure.
        - Where the file still does not read once that analyst returned, the final reply gives it.
    - A step `next` printed counts as made by the call the operator made: a Bash call whose command runs the printed command among others, or the call the operator made right after the call of `next` that printed the step, other than a call of `next` alone.
    """),
    HelpPart.RULINGS: mctx("""
    - `next` applies the rulings that the coordinator gives an operator of the session, and that the reply of a ticket analyst on a held step gives, each a line in one of these forms, matched whole, past a list marker:
        - `Decision: <decision key> <choice>` rules a held step, with one of the choices that step gives.
        - `Override: <task id> <pass> <override>` gives the override, labelled as an override, in the brief of the next launch of that pass on that task.
        - `Override: pass over <step key>` passes over the step whose key it gives, for each operator.
            - `next` gives that step, once, as one its procedure waits on, to a ticket analyst it launches to rule it, other than a launch of a ticket analyst to rule a step, and goes on with the other procedures.
            - A pipeline whose next pass is passed over stops instead.
            - A ruling on a solver pass holds for each pipeline on its task, unless the work set aside for an earlier pipeline on that task went back (`restore`) after the ruling and before that pipeline's line or `start` call.
            - A solver pass's key is `<task id>-<pass>`, its task id and its pass (`analyze`, `create` or `refine`).
                - A ruling can name a pass that was never printed.
    - A coordinator's line that opens with `Override:` or `Decision:` in none of these forms goes back to the coordinator once, as undecided.
    - A ticket analyst's reply on a step that gives its decision key, with no ruling in these forms, goes back to it once.
        - Where its answer gives none either, the step stays held.
    - A step `next` cannot place gives no decision key: its ticket analyst makes the act it needs and gives no ruling.
    """),
    HelpPart.RUN: mctx("""
    - `next` reads a coordinator's line `Run: <path>` as a run: the solver pipelines that the Python script at `<path>`, absolute or relative to the main tree, starts.
        - Write a run script under `work/runs/` in the main tree.
        - It defines `starts(run: Run) -> Iterable[Start]`, with `Run` and `Start(task, passes)` from the module `operations.runs`, each `passes` a non-empty sequence whose every item is `analyze`, `create` or `refine`.
        - `run.queue` gives the task ids of the queue, in the order of their names, less each task a claim file gives and each task of the run's pipelines.
        - `run.running` and `run.ended` give the run's pipelines, each with `task`, `passes` and `stopped`, which gives, for an ended one, the reason it stopped, or None where it ran to its end.
        - At each read of the state, `next` loads the script again and calls `starts`.
        - `next` gives as a step the `start` of the first item `starts` gives whose task no pipeline of the session runs and that matches no pipeline of the run by task and passes, and passes over each other item.
            - That `start` has as `<run>` the time of the line's message and its path.
        - A `start` on a task whose claim file stands ends that pipeline, with the failure's text as its reason.
        - Where `starts` raises or gives a result in no form above, the run starts nothing while that fault stands.
        - The line is done once no pipeline of the run runs, no fault of the load or of `starts` stands, and `starts` gives nothing to start.
        - The script may define `takes(ticket: RunTicket) -> bool`, with `RunTicket` from the module `operations.runs`, which the same load calls on each ticket outside `tickets/closed/` and `tickets/deferred/`.
            - A `RunTicket` gives:
                - `number`, `kind`, `status`, `domain`, `subject`, `filer`, `priority` and `depends_on`: the ticket's.
                - `waits_on`: the change it waits on, or None.
                - `filed_by_run`: whether a pipeline of the run, running or ended, filed it.
                - `reached_by_run`: whether a chain of `depends_on` and `waits_on` links reaches it from a ticket such a pipeline filed.
            - From the line on, also once it is done, the operator launches a ticket analyst on an open ticket, and takes an open change, only where the `takes` of each run whose script defines one gives `True` for it.
                - A ticket an `Expedite:` line gives passes, and so does a change that an operator took before and that went back to `tickets/open/`.
            - Where `takes` raises or gives a result that is no `bool`, the run takes no ticket while that fault stands.
        - Where the script fails to load, or the load and the calls of `starts` and `takes` run past {script} seconds, the run starts nothing, and takes no ticket unless the script loaded and defines no `takes`, while that fault stands.
        - The coordinator gets the text of each fault, once for each distinct text.
    """),
    HelpPart.RELAY: mctx("""
    - `relay` prints the next step of the operator launcher whose agent id it is given, in the forms of `next`.
        - Where an operator of the launcher's runs and no line of the coordinator's waits for it, it prints at once, with no block, that the launcher ends its turn with no call.
            - Where a message to the launcher waits that the harness accepted during the call, as the block of `next` reads one, it prints instead that the launcher runs the command again.
        - Its first step launches an operator whose brief is the launcher's brief.
        - Each later message of the coordinator's to the launcher goes, unchanged, to the operator of the launcher's that runs, or, where none runs or the one that runs sent the launcher its final reply, into the brief of the next operator it launches.
        - Where an operator's final reply ends it for its context, it launches a fresh operator.
            - Where the launcher's context is past the bound `context_bound_hook.py` gives, it sends the coordinator instead the launcher's final reply, which asks for a fresh operator launcher whose brief is the lines that wait for a next operator, and gives them.
        - It sends the coordinator any other final reply of an operator, and an operator's end with no final reply, after a line that gives that operator's agent id.
            - It then prints the launcher's final reply, unless a line of the coordinator's waits for a next operator.
    """),
    HelpPart.REVIEW: mctx("""
    - `review` prints, to the doc editor whose agent id it is given, which an operator of the session launched, the launch of its change's doc reviewer, in the form of `next`'s, with the brief `next` gives a doc reviewer, the doc editor as its launcher, and each editor of the change in its worktree.
        - Where the change already has a doc reviewer, whoever launched it, it prints that reviewer's agent id and that the doc editor launches no other.
        - Where an editor the change's ticket gives has no agent in the worktree, or another editor of the change there has not reported, it prints instead that the operator launches the review, and that the doc editor gives its final reply.
        - Where the agent is no doc editor that an operator of the session launched, it prints that no launch is printed, and that the agent gives its final reply.
        - It reads the state as the doc editor's operator's `next` reads it.
    """),
    HelpPart.ALERTS: ALERTS,
}
"""The text of each part of the help."""

POLL_SECONDS = 15
CALLS = (Launch, Send, Bash)
"""The steps after whose call the operator runs `next` again."""
TASK_ID = re.compile(task.TASK_ID)
LOCK_DIR = Path("/tmp")


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


def with_budget(step: Launch) -> Launch:
    """`step` with the budget line `--help next` gives."""
    if step.role in BARE_BRIEFS:
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


def reloading(step: Launch, state: State) -> float:
    """The seconds left until the launch `step` is made: where
    `plan.unloaded` gives its last call, until `plan.RETRY_SECONDS` after
    that call."""
    failed = plan.unloaded(state, step)
    return 0.0 if failed is None else max(0.0, failed.time + plan.RETRY_SECONDS - time.time())


def single_instance(me: str) -> None:
    """End each other call of `next` or `relay` for `me` that runs, as
    `--help next` gives it, and hold the lock that marks this call as the
    one that runs until the process ends."""
    fd = os.open(LOCK_DIR / f"operate-{me}.lock", os.O_RDWR | os.O_CREAT, 0o600)
    while True:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            pass
        held = os.pread(fd, 32, 0).decode().strip()
        if held.isdigit() and int(held) != os.getpid():
            try:
                os.kill(int(held), signal.SIGTERM)
            except ProcessLookupError:
                pass
        time.sleep(0.2)
    os.ftruncate(fd, 0)
    os.pwrite(fd, f"{os.getpid()}\n".encode(), 0)


def arm_watchdog(me: str) -> None:
    """Print that the agent runs the command again, and end the process,
    once `LIMIT_SECONDS` have passed, as `--help next` gives it."""
    def expire(_signum: int, _frame: object) -> None:
        print(printed(Poll(), me, Path()), flush=True)
        os._exit(0)
    signal.signal(signal.SIGALRM, expire)
    signal.alarm(LIMIT_SECONDS)


def block(me: str, action: Action, step_at: Callable[[float], tuple[Step, Path]]) -> int:
    """Print the step `step_at` gives, with the scratchpad its files go
    under, by the deadline it is given, as `--help next` gives the block of `next`
    and `--help relay` the end of the turn of `relay`."""
    single_instance(me)
    arm_watchdog(me)
    deadline = time.monotonic() + BLOCK_SECONDS
    path = find(me)
    since = last_delivered(path)
    while True:
        step, scratch = step_at(deadline)
        if isinstance(step, EndTurn) and accepted_after(path, since, []):
            step = Poll()
        if (not isinstance(step, Poll) or time.monotonic() + POLL_SECONDS > deadline
                or accepted_after(path, since, [])):
            signal.alarm(0)
            if isinstance(step, CALLS):
                print(key_line(step, me, action))
            if isinstance(step, Launch):
                step = with_budget(with_report(step, scratch))
            print_step(step, scratch, me)
            return 0
        time.sleep(POLL_SECONDS)


def operator_step(me: str, deadline: float) -> tuple[Step, Path]:
    """The operator's next step, with a launch held until `reloading` gives
    no wait, or the wait, where the hold runs past `deadline`.
    `steps.Undecided.reread` gives why the command reads the state again
    before it launches an analyst on a step marked `reread`."""
    while True:
        state, watch = read_state(me)
        step = plan.next_step(state, watch)
        if isinstance(step, Launch) and step.reread:
            state, watch = read_state(me)
            step = plan.next_step(state, watch)
        if isinstance(step, Launch) and (left := reloading(step, state)) > 0:
            if time.monotonic() + left > deadline:
                return Poll(), state.scratch
            time.sleep(left)
            continue
        return step, state.scratch


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
    print_step(with_budget(with_report(step, state.scratch)), state.scratch, editor)
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


def relay_step(me: str, deadline: float) -> tuple[Step, Path]:
    found, scratch = read_relay(me)
    return relay.next_step(found), scratch


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("--help", "-h"):
        return print_help(argv[1:], HelpPart, lambda parts: USAGE.format(parts=parts), PURPOSES,
                          lambda part: PARTS[part].format(
                              block=BLOCK_SECONDS, limit=LIMIT_SECONDS, load=plan.LOAD_SECONDS,
                              retry=plan.RETRY_SECONDS,
                              write=round(WRITE_SECONDS), stale=USAGE_STALE, rate_limit=RATE_LIMIT,
                              script=runs.SCRIPT_SECONDS))
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
    code = main(sys.argv[1:])
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(code)
