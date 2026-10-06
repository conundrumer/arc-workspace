"""Profile agent runs from their Claude Code transcripts: where each run's
wall time goes, the budget of each agent type, and the agents under a run
whose work is open, as `--running` lists them. `--help` prints HELP."""

import argparse
import sys
import time

from controlled_markdown import mctx
from engine import checkout
from handbook.paths import console_importable, importable

console_importable()
# `scripts/` is no package: a test loads this module by its path, with
# `scripts/` off `sys.path`, and the modules below import from there.
importable(checkout.scripts())

from agent_launches import pending_agents  # noqa: E402
from budgets import (BUDGET_FACTOR, LOW_WAIT_PCT, WINDOW_RUNS,  # noqa: E402
                     print_budgets)
from open_agents import Listed, running_agents  # noqa: E402
from quota import epoch  # noqa: E402
from run_prints import (RECENT_CALLS, print_messages,  # noqa: E402
                        print_report, print_running)
from run_profile import (COMMAND_WIDTH, Run, clock, minutes,  # noqa: E402
                         part_split, print_groups, print_types, profile)
from run_reads import run_type  # noqa: E402
from transcripts import Refused, find, transcripts  # noqa: E402

HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/profile_runs.py ID [ID ...] [--type TYPE[,TYPE]] [--pct P] [--top N] [--runs] [--since DATE]
        uv run python scripts/profile_runs.py --running ID
        uv run python scripts/profile_runs.py --pending ID
        ```
    - The items below say what an ID names, how a run's wall time is cut into parts, what one run and several runs print, the budget of each agent type, what `--running` and `--pending` print, and how a call's command is printed. The options follow them.
    - An ID is an agent id, a session id, or the path of a `.jsonl` transcript. A session brings its main transcript, as type `main`, and the run of each of its subagents. A run is the transcript of one agent, or where the top-level session takes a new session id while a subagent runs, that subagent's transcripts under each session's directory: each one under a later session goes on from the one before it, its first entry answering that one's last. A run's agent type, description and launching call are those the earliest of its transcripts' `.meta.json` files that gives each gives.
    - A run's wall time, from its first entry to its last, is cut at each entry's time, and each interval goes to one part:
        - `tools`: a tool call is pending. A Bash call is labelled by the known commands it runs, joined by ` + `: `gate`, `merge_change.py`, `materialize.py`, `pytest`, `pyright`, and `run_dl.py` with its subcommand. A Bash call that runs none is labelled by the first program it runs past setup, and any other call by its tool.
        - `waits`: a foreground Agent, Monitor or TaskOutput call or a poll is pending, or the turn has ended while an agent or command the run backgrounded is running. These are labelled `agent TYPE`, `poll` and `bg LABEL`.
        - `model`: no call is pending and the turn has not ended.
        - `idle`: the turn has ended and nothing the run launched is running, so the run waits on the user or on a message.
    - A turn starts at a message the model answers, so a local command such as `/compact` starts none. It ends at the model's last entry, or at the result of a call that ends it, such as SubagentHandback.
    - Calls that are pending at once share an interval in equal parts. While the model works, backgrounded work that runs goes to `model`.
    - A poll is a Bash call that runs `sleep` and none of the known commands, in a loop or not. A command the harness moves to the background on its timeout counts under its own label up to then, and under `bg LABEL` after.
    - One run prints its parts and its labels by time, with each label's share of the wall time and its calls, and for backgrounded work the time it ran from launch to its notification.
    - One run of a subagent, completed or not, also prints each message from its parent, as `--running` defines those messages: the time it arrived, its active time, which is the run's wall time less `idle` over that message's period, and the budget in force for it, which is the budget `--running` gives from the messages up to it. A message whose active time is past its budget is marked `past budget`. A message with no budget in force prints none, and a run with an unknown message prints no active time and no budget.
    - One run of a subagent also prints, after `report to the parent:`, the latest entry of its parent's transcripts after the parent's latest message to it that gives a report of it, with the entry's time, its kind and the start of its text, or where none does, `none after the message at` and that message's time. The parent's transcripts are, under each session of the run, the main transcript where the parent is `main`, and otherwise the transcripts of the parent's run. An entry gives a report where it is:
        - `notification`: a notification of the agent with the status `completed` and a result, other than one whose note says the agent stopped with background work of its own still running;
        - `result`: the result of a foreground Agent call that launched the agent;
        - `message`: a message from the agent.
    - Where the latest message from the parent is unknown, or no transcript of the parent is found, it prints `?`. A notification or a launch result whose status is of no known form gives no report, and where no `.meta.json` of the run gives a `toolUseId`, no launch result is matched to it. A launch result whose status is of no known form counts as not in the background, wherever it is read. An `undecided` line on stderr names each, and each distinct line is printed once.
    - More than one run prints, per agent type, the number of runs, the minimum, median, P-th percentile and maximum of wall time, the total, the median and P-th percentile of active time, which is wall time less `idle`, and each part's share of the total, then each type's labels by time, with the number of runs each appears in.
    - More than one run also prints the budget of each agent type, which is {factor} times a median wall time, printed with the runs it is taken over:
        - The window of a type that has an agent document under `prompts/agents/` is the runs whose first entry is at or after the last commit that changed that document, a document it includes or inlines, a lib file its rendered prompt holds, a script under `scripts/` its rendered prompt names, or a package under `src/` its rendered prompt runs with `-m`, and not a module such a script or package imports. `--since DATE`, an ISO date or datetime read in local time where it gives no offset, sets the window of every type to the runs whose first entry is at or after DATE. Where the window holds at least {window_runs} runs of the type, the median is taken over them.
        - A type with no agent document has a window only with `--since`, and a type whose paths no commit changed has none, and an `undecided` line on stderr names it.
        - Otherwise it is taken over the type's runs whose `waits` and `idle` together are under {low_wait_pct}% of wall time. A type with no such run gets no budget, and an `undecided` line on stderr names it.
    - `--running ID` lists the agents under the run ID whose work is open, where ID is a session id or an agent id, and a run that goes on under a later session is listed under that session's id. Of the agents the run launched, the agents those launched, and so on, whether or not their parent's work is open, an agent's work is open where its turn is in progress, or where its turn has ended and no report of it reached its parent after the parent's latest message to it, as `report to the parent:` gives a report, read here from each transcript of the parent's run. An agent's turn counts as ended where it has ended, where its last entry is the harness's note that the user interrupted it, or where its parent has its result or a notification of it and its transcript holds no `user` or `assistant` entry timestamped after the latest of those, so an attachment the harness writes after the turn has ended does not count. A report after the latest message the agent received from anyone closes its work, whether or not the parent's latest message to it is known. Otherwise, an agent whose turn has ended is listed where the parent's latest message to it is unknown. The agents are listed in launch order, each parent's agents after it. In an agent's shell, `$CLAUDE_CODE_SESSION_ID` holds the id of the top-level session, in a subagent as well, so `--running $CLAUDE_CODE_SESSION_ID` lists the agents of the whole session whose work is open. For each agent it prints:
        - its agent id, type and launch description, its parent, which is the agent id of the agent that launched it or `main`, the time since its first entry, its active time with the time of the message it is measured from and, where that message's period has ended, the time it ended, its budget, and its context size in tokens, which is the input of its last request;
        - its working directory, as its first entry gives it;
        - for an agent whose turn has ended, after `turn ended:`, the time of its last `user` or `assistant` entry, which is when the turn ended, and the time since, and after `report to the parent:` what one run prints there, from the same transcripts;
        - its last text output, the end of the text of its last assistant entry that gives text;
        - each call it has in flight, with its label, its command and the time since the call;
        - each command or agent it backgrounded that is still running, with its label, its command and the time since the call;
        - its last {recent} calls in order, each with its label, its command and its duration, or `pending`.
    - `--pending ID` prints the agent id of each agent pending to the run ID, one per line, in launch order, where ID is a session id or an agent id. An agent is pending to the run that launched it from the Agent call that launched it, or from the last SendMessage call that resumed it, by the run or by any agent of the run's sessions, main among them, until the run holds the result of that Agent call, where the result does not say the agent runs in the background, or until any transcript of the session holds a notification of the agent, a notification that it stopped with work of its own still running among them. A SendMessage call to an agent whose result says neither that it resumed the agent nor that it queued the message resumes none, and an `undecided` line on stderr names it.
    - The messages from a listed agent's parent are its brief, the messages its first turn answers, and each later message its parent sent: one the harness gives as from the parent's agent id, or, for an agent `main` launched, as from the coordinator or queued with no tag. The origin the harness gives a queued message is the one its attachment gives. A notification of the agent's own backgrounded work, a message from an agent it launched, from the user, from another agent, or, for an agent `main` did not launch, from the coordinator or queued with no tag, and a note of the harness are none. A message from another agent is one the harness gives as from an agent id other than the parent's and those of the agents it launched. A later message whose sender is none of these is unknown, and an `undecided` line on stderr names it.
    - The period of a message from the parent runs from it to the next message from the parent or from another agent, or to the run's last entry.
    - A listed agent's active time is its wall time less `idle` over the period of the latest message from its parent, with its wall time running to now where that period and its turn have not ended. An agent with an unknown message has no active time and no budget.
    - Its budget is the N of the line of the form `Budget: N minutes` in the latest message from its parent that has a line of that form, and an agent none of whose parent's messages has one gets no budget. A line that opens with `Budget:` in another form gives no budget, and a message with lines of more than one N gives none, and an `undecided` line on stderr names each.
    - A call's command and an agent's text output are printed on one line, a command cut to its first {width} characters and a text output to its last {width}. A call's command is:
        - for a Bash call, its command, led by the kind of each ticket it files, as `kind K:`;
        - for an Agent call, its description;
        - for a Write, Edit or NotebookEdit call, the path of the file it writes;
        - for a SendMessage call, its recipient, as `to R:`, and its message;
        - for a SubagentHandback call, its message;
        - for any other call, nothing past its label.
    - A run whose agent type is unknown is refused, and so is an ID that names transcripts that differ and are not the transcripts of one run. A call whose agent type is unknown is labelled `agent ?`, a Bash call with no command is labelled `shell`, and a call whose input lacks a field its command reads, of those above but a SendMessage call's message, is printed without that field; an `undecided` line on stderr names each.
    """).format(factor=BUDGET_FACTOR, window_runs=WINDOW_RUNS,
                low_wait_pct=LOW_WAIT_PCT, recent=RECENT_CALLS,
                width=COMMAND_WIDTH)


def iso_date(text: str) -> float:
    return epoch(text)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", metavar="ID")
    ap.add_argument("--running", metavar="ID",
                    help=mctx("list the agents under the run ID whose work "
                              "is open"))
    ap.add_argument("--pending", metavar="ID",
                    help=mctx("list the agents pending to the run ID"))
    ap.add_argument("--type", help=mctx("profile only runs of these agent "
                                        "types, separated by commas"))
    ap.add_argument("--pct", type=float, default=90,
                    help=mctx("the high percentile of wall time per type"))
    ap.add_argument("--top", type=int, default=8,
                    help=mctx("labels to print per run or per type; 0 prints "
                              "none per type and all for one run"))
    ap.add_argument("--runs", action="store_true",
                    help=mctx("also print one line per run"))
    ap.add_argument("--since", type=iso_date, metavar="DATE",
                    help=mctx("start of the window of runs each type's "
                              "budget is taken over, in place of the type's "
                              "own: an ISO date or datetime, in local time "
                              "where it gives no offset"))
    args = ap.parse_args(argv)
    types = set(args.type.split(",")) if args.type else None
    undecided: list[str] = []
    runs: list[Run] = []
    listed: list[Listed] = []
    if [bool(args.ids), bool(args.running), bool(args.pending)].count(True) != 1:
        print(mctx("refused: give one of IDs, `--running ID` and `--pending ID`"),
              file=sys.stderr)
        return 2
    try:
        if args.pending:
            for agent in pending_agents(find(args.pending), undecided):
                print(agent)
        elif args.running:
            listed = running_agents(find(args.running), undecided)
        else:
            paths = list(dict.fromkeys(p for ident in args.ids
                                       for p in transcripts(ident)))
            runs = [profile(p, undecided) for p in paths
                    if not types or run_type(p)[0] in types]
    except Refused as e:
        print(mctx("refused: {reason}").format(reason=e), file=sys.stderr)
        return 2
    if args.running:
        print_running(listed, time.time(), undecided)
    elif not runs and not args.pending:
        print(mctx("refused: no run to profile"), file=sys.stderr)
        return 2
    elif len(runs) == 1 or args.runs:
        for r in runs:
            print(f"{r.label} {r.agent_type} {clock(r.start)}: {r.description}\n"
                  f"  wall {minutes(r.wall)}  {part_split(r.parts)}")
        if len(runs) == 1:
            print_messages(runs[0], undecided)
            print_report(runs[0], undecided)
            print_groups(runs[0].groups, args.top, runs[0].wall)
        else:
            print()
    if len(runs) > 1 and not args.running:
        print_types(runs, args.pct, args.top)
        print()
        print_budgets(runs, args.since, undecided)
    for line in dict.fromkeys(undecided):
        print(mctx("undecided: {line}").format(line=line), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
