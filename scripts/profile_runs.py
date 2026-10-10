"""Profile agent runs from their Claude Code transcripts: where each run's
wall time goes, the budget of each agent type, the runs under a run since
an operator's previous call of `--under` on it, the agents under a run
whose work is open, as `--running` lists them, and whether one run's work
is open, as `--open` gives it. `--help` prints HELP. `budget_of` gives the
budget of one agent type for a brief, as more than one run prints it,
over every run of that type under the project directories."""

import argparse
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from handbook.paths import console_importable, importable

console_importable()
# `scripts/` is no package: a test loads this module by its path, with
# `scripts/` off `sys.path`, and the modules below import from there.
importable(checkout.scripts())

from agent_launches import pending_agents, runs_under  # noqa: E402
from agent_turns import first_time, last_time  # noqa: E402
from budgets import (BUDGET_FACTOR, LOW_WAIT_PCT, MEDIAN_RUNS,  # noqa: E402
                     print_budgets, type_budget)
from command_labels import programs  # noqa: E402
from context_bound_hook import CONTEXT_BOUND, OPERATOR  # noqa: E402
from open_agents import Listed, running_agents, work_open  # noqa: E402
from run_prints import (RECENT_CALLS, print_messages,  # noqa: E402
                        print_report, print_running)
from run_profile import (COMMAND_WIDTH, Run, clock, dollars, minutes,  # noqa: E402
                         part_split, print_groups, print_types, profile)
from run_reads import (BACKGROUND_TASK, agent_type, blocks, run_type,  # noqa: E402
                       result_text)
from ticketing.times import utc_stamp  # noqa: E402
from token_prices import PRICES  # noqa: E402
from transcripts import (Entry, Refused, agent_id, agent_transcripts,  # noqa: E402
                         bare_id, chain, epoch, find, is_subagent, read_entries,
                         transcripts)

from operations.batches import LEFT_OPEN, NO_RUN, RUNS_TAKEN, lines, read_under  # noqa: E402

UNDER = "--under"
"""The option of the mode that profiles the runs under a run since an
operator's previous call of it."""

ISO_TIME = mctx("an ISO date or datetime, in UTC where it gives no offset")
"""The times `utc_time` reads."""

REPRICED = mctx("each token cost is of the same requests at the same token "
                "counts, priced at {model}; it is not what these runs would "
                "cost had they run on {model}, since runs on another model "
                "make their own requests, with their own output lengths and "
                "their own tokenizer's counts")
"""What a token cost repriced at `--price-at MODEL` is."""

HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/profile_runs.py ID [ID ...] [--type TYPE[,TYPE]] [--pct P] [--top N] [--runs] [--since DATE] [--price-at MODEL]
        uv run python scripts/profile_runs.py --under ID [--pct P] [--top N] [--since DATE] [--price-at MODEL]
        uv run python scripts/profile_runs.py --running ID [--calls-since TIME]
        uv run python scripts/profile_runs.py --pending ID
        uv run python scripts/profile_runs.py --open ID
        ```
    - The items below say what an ID names, the zone of the times the tool reads and prints, how a run's wall time is cut into parts, what one run and several runs print, the budget of each agent type, what `--under`, `--running`, `--pending` and `--open` print, and how a call's command is printed. The options follow them.
    - An ID is an agent id, a session id, or the path of a `.jsonl` transcript. A session brings its main transcript, as type `main`, and the run of each of its subagents. A run is the transcript of one agent, or where the top-level session takes a new session id while a subagent runs, that subagent's transcripts under each session's directory: each one under a later session goes on from the one before it, its first entry answering that one's last. A run's agent type, description and launching call are those the earliest of its transcripts' `.meta.json` files that gives each gives.
    - Each time the tool prints is in UTC, as `YYYY-MM-DDTHH:MMZ` where no item below gives another form. A DATE or TIME it reads is {iso_time}.
    - A run's wall time, from its first entry to its last, is cut at each entry's time, and each interval goes to one part:
        - `tools`: a tool call is pending. A Bash call is labelled by the known commands it runs, joined by ` + `: `gate`, `merge_change.py`, `materialize.py`, `pytest`, `pyright`, and `run_dl.py` with its subcommand. A Bash call that runs none is labelled by the first program it runs past setup, and any other call by its tool.
        - `waits`: a foreground Agent, Monitor or TaskOutput call or a poll is pending, or the turn has ended while an agent or command the run backgrounded is running. These are labelled `agent TYPE`, `poll` and `bg LABEL`.
        - `model`: no call is pending and the turn has not ended.
        - `idle`: the turn has ended and nothing the run launched is running, so the run waits on the user or on a message.
    - A turn starts at a message the model answers, so a local command such as `/compact` starts none. It ends at the model's last entry, or at the result of a call that ends it, such as SubagentHandback.
    - Calls that are pending at once share an interval in equal parts. While the model works, backgrounded work that runs goes to `model`.
    - A poll is a Bash call that runs `sleep` and none of the known commands, in a loop or not. A command the harness moves to the background on its timeout counts under its own label up to then, and under `bg LABEL` after.
    - A command the run backgrounded runs until a notification of it in the run's transcripts, other than in an assistant entry. Where none follows, it runs while a process holds open the output file its result names, and where no process holds that file, it ended when the file was last written. Where its result names no file, or that file is gone, whether it runs is unknown, and it counts as running. Where `lsof` writes to stderr when it lists the files open in that file's directory, which files a process holds open is unknown, and the ID is refused.
    - A run's token cost is the list price of the tokens its requests used, from the price table of `token_prices`, each request priced once at the full usage its entries give. A run with a request whose model or usage the table does not price has an unknown cost, printed `?`, and an `undecided` line on stderr names the model or the field.
    - `--price-at MODEL` prices each request at the prices the table gives MODEL, in place of those of the model that made it, and a MODEL the table does not price is refused. Where it is given, the tool first prints `price at MODEL:` and that {repriced}.
    - One run, and each run `--runs` prints, prints its wall time and its token cost.
    - One run prints its parts and its labels by time, with each label's share of the wall time and its calls, and for backgrounded work the time it ran from launch to its notification, or for a command that ended with none, to its end.
    - One run of a subagent, completed or not, also prints each message from its parent, as `--running` defines those messages: the time it arrived, its active time, which is the run's wall time less `idle` over that message's period, and the budget in force for it, which is the budget `--running` gives from the messages up to it. A message whose active time is past its budget is marked `past budget`. A message with no budget in force prints none, and a run with an unknown message prints no active time and no budget.
    - One run of a subagent also prints, after `report to the parent:`, the latest entry of its parent's transcripts after the parent's latest message to it that gives a report of it, with the entry's time, its kind and the start of its text, or where none does, `none after the message at` and that message's time. The parent's transcripts are, under each session of the run, the main transcript where the parent is `main`, and otherwise the transcripts of the parent's run. An entry gives a report where it is:
        - `notification`: a notification of the agent with the status `completed` and a result, other than one whose note says the agent stopped with background work of its own still running;
        - `result`: the result of a foreground Agent call that launched the agent;
        - `message`: a message from the agent.
    - A report's text is the entry's text, and of a message that delivers the agent's SubagentHandback, that text without the harness's preamble and indent. An entry whose text is the harness's pointer to such a message, or the line an agent gives after it sent its final reply by SendMessage, gives no report. A report whose text is the path alone of a report file that `operate.py next` gives in a brief is that file's text, for the latest report that gives that path; an earlier one keeps the path as its text, and where the file is gone, an `undecided` line on stderr names it.
    - Where the latest message from the parent is unknown, or no transcript of the parent is found, it prints `?`. A notification or a launch result whose status is of no known form gives no report, and where no `.meta.json` of the run gives a `toolUseId`, no launch result is matched to it. A launch result whose status is of no known form counts as not in the background, wherever it is read. An `undecided` line on stderr names each, and each distinct line is printed once.
    - More than one run prints, per agent type, the number of runs, the minimum, median, P-th percentile and maximum of wall time, the total, the median and P-th percentile of active time, which is wall time less `idle`, and each part's share of the total, then per agent type the total token cost of its runs of known cost, its share of that total over all types, the median cost of such a run, and the number of runs of unknown cost it leaves out, then each type's labels by time, with the number of runs each appears in.
    - More than one run also prints the budget of each agent type, which is {factor} times a median wall time, printed with the runs it is taken over. That median is taken over the runs an operator launched alone, with or without a budget in force, and of those, over the runs their budget did not cut. An operator launched a run where its parent, as `--running` gives it, is an agent of type `{operator}`, and a run whose parent's type no transcript of the sessions of the run gives is left out, and an `undecided` line on stderr names it. A run's budget cut it where the active time of a message from its parent with a budget in force, as one run prints that budget, is at or past that budget, so that its wall time is no measure of what its work needed. Where the active time of such a message is unknown and no other message shows it cut, whether its budget cut it is unknown: it is left out, and an `undecided` line on stderr names it.
        - A brief gives items where its first line is one of the lines `operations.briefs` gives for a brief of several items of the same work, each item a ticket number. Where the brief of some run of a type gives items, it also prints, on a line led by `per item`, the type's budget per item, which is {factor} times the median of the wall time per item, a run's wall time over the number of items its brief gives. That median is taken by the lines below over the runs an operator launched that their budget did not cut and whose brief gives items.
        - The window of a type that has an agent document under `prompts/agents/` is the runs whose first entry is at or after the last commit that changed that document, a document it includes or inlines, a lib file its rendered prompt holds, a script under `scripts/` its rendered prompt names, or a package under `src/` its rendered prompt runs with `-m`, and not a module such a script or package imports. `--since DATE` sets the window of every type to the runs whose first entry is at or after DATE. Where the window holds at least {median_runs} of the runs the median is taken over, it is taken over them.
        - A type with no agent document has a window only with `--since`, and a type whose paths no commit changed has none, and an `undecided` line on stderr names it.
        - Otherwise it is taken over those of these runs whose `waits` and `idle` together are under {low_wait_pct}% of wall time, where at least {median_runs} runs are such. A type with fewer such runs gets no budget, and an `undecided` line on stderr names it with their count as its reason.
    - `--under ID` profiles the runs under the run ID, where ID is a session id or an agent id: the agents whose `.meta.json` gives the run ID as `parentAgentId`, or for a session gives none, the agents whose `.meta.json` gives one of those, and so on.
        - Its previous call is the latest call of `--under` on the same ID, as the call writes it, with or without the `agent-` prefix, made by an agent of type `{operator}` in any transcript under the project directories that changed at or after the run ID's first entry, whose result says it completed in the foreground with no error and was not interrupted, and whose result holds one `left open:` line and one `runs taken:` line, the count on the `runs taken:` line followed by as many agent ids, read from the result's content, or where that content is the harness's `<persisted-output>` preview of a large output and the result gives a `stdout`, from that `stdout`. A line counts only where a line break ends it. A call whose result holds more than one `left open:` line counts as none, and an `undecided` line on stderr names that call. A call's time is the time of the entry that makes it.
        - Where a previous call stands, it considers the runs whose last timestamped entry is after that call's time and each run that call's `left open:` line gives, and where none stands, every run under the ID. Of those, it takes each run whose work is not open, by the rule by which `--running` lists an agent, as `--open` gives it, and leaves out the others.
        - It prints `left open:` and the agent id of each run it left out, separated by spaces, or `none`; then `runs taken:`, their count, and the agent id of each run taken, separated by spaces; then `previous call:` and that call's time, as `YYYY-MM-DDTHH:MM:SSZ`, with `by` and the agent id of the agent that made it, or `none`; then the line `--runs` prints for each run taken, in the order of their first entries, and what one run or more than one run prints.
    - `--running ID` lists the agents under the run ID whose work is open, where ID is a session id or an agent id, and a run that goes on under a later session is listed under that session's id. Of the agents the run launched, the agents those launched, and so on, an agent's work is open where its turn is in progress, whether or not its parent's work is open, or where its turn has ended, its parent's work is open, and no report of it reached its parent after the parent's latest message to it, as `report to the parent:` gives a report, read here from each transcript of the parent's run. A parent's work is open where the parent is `main` or listed, and the run ID's work is open where it is `main` or would be listed under `main`. Where no transcript of the parent of the run ID, or of a parent above it, gives its launch, whether its work is open is unknown, it counts as open, and an `undecided` line on stderr names it. An agent's turn counts as ended where it has ended, where its last entry is the harness's note that the user interrupted it, or where its parent has its result, or a transcript of the sessions of its run or of its parent's run holds a notification of it, and its transcript holds no `user` or `assistant` entry timestamped after the latest of those, so an attachment the harness writes after the turn has ended does not count. A report after the latest message the agent received from anyone closes its work, whether or not the parent's latest message to it is known, and so does a notification of it after that message, of any status but `running`, other than one whose note says the agent stopped with background work of its own still running. Otherwise, an agent whose turn has ended is listed where the parent's latest message to it is unknown. Where these rules give the work of an agent, of the run ID or of a run above it as not open, and its turn has ended while work of its own still runs, whether its work is open is unknown: it counts as open, and an `undecided` line on stderr names it with that work. An agent's work of its own is each command it backgrounded that is still running, each agent it launched in the background that this rule does not reach, as `running:` gives such an agent, and whose launch no notification has followed, and each agent it launched whose turn is in progress or whose work of its own still runs. The agents are listed in launch order, each parent's agents after it. In an agent's shell, `$CLAUDE_CODE_SESSION_ID` holds the id of the top-level session, in a subagent as well, so `--running $CLAUDE_CODE_SESSION_ID` lists the agents of the whole session whose work is open. For each agent it prints:
        - its agent id, type and launch description, its parent, which is the agent id of the agent that launched it or `main`, the time since its first entry, its active time with the time of the message it is measured from and, where that message's period has ended, the time it ended, its budget, and its context size in tokens, which is the input of its last request, followed, for an agent of type `operator`, by `bound` and the operator's bound of {bound} tokens, led by `past` where its context is past that bound;
        - its working directory, as its first entry gives it;
        - for an agent whose turn has ended, after `turn ended:`, the time of its last `user` or `assistant` entry, which is when the turn ended, and the time since, and after `report to the parent:` what one run prints there, from the same transcripts;
        - its last text output, the end of the text of its last assistant entry that gives text;
        - each call it has in flight, with its label, its command and the time since the call;
        - after `running:`, each command it backgrounded that is still running, and each agent it launched in the background that is itself listed and whose launch no notification in the transcripts of the run that launched it has followed, each with its label, its command and the time since the call. An agent this rule does not reach, because no transcript gives its launch or because no `.meta.json` of the sessions of the run that launched it gives that run as the parent of any agent, is printed there as well, and an `undecided` line on stderr names it;
        - its last {recent} calls in order, each with its label, its command and its duration, or `pending`.
    - `--calls-since TIME` keeps of each listed agent's last {recent} calls only those that ended at or after TIME, and those that are pending. It prints them after `recent since` and TIME, as `YYYY-MM-DDTHH:MM:SSZ`, and where it keeps none, prints `none` after TIME.
    - `--pending ID` prints the agent id of each agent pending to the run ID, one per line, in launch order, where ID is a session id or an agent id. An agent is pending to the run that launched it from the Agent call that launched it, or from the last SendMessage call that resumed it, by the run or by any agent of the run's sessions, main among them, until the run holds the result of that Agent call, where the result does not say the agent runs in the background, or until any transcript of the sessions of the run or of the agent's run holds a notification of the agent, a notification that it stopped with work of its own still running among them. A SendMessage call to an agent whose result says neither that it resumed the agent nor that it queued the message resumes none, and an `undecided` line on stderr names it.
    - `--open ID` prints `open` where the work of the run ID is open, by the rule by which `--running` lists an agent, applied to the run ID, and `not open` otherwise, where ID is an agent id. An ID that names a session's main transcript is refused.
    - The messages from a listed agent's parent are its brief, the messages its first turn answers, and each later message its parent sent: one the harness gives as from the parent's agent id, or, for an agent `main` launched, as from the coordinator or queued with no tag. The origin the harness gives a queued message is the one its attachment gives. A notification of the agent's own backgrounded work, a message from an agent it launched, from the user, from another agent, or, for an agent `main` did not launch, from the coordinator or queued with no tag, and a note of the harness are none. A message from another agent is one the harness gives as from an agent id other than the parent's and those of the agents it launched. A later message whose sender is none of these, or from an agent no transcript of the sessions of the run gives the type of, is unknown, and an `undecided` line on stderr names it. A line of a message from the parent that gives a file `operate.py next` wrote for the message is read as that file's text, and where the file is gone, an `undecided` line on stderr names it.
    - The period of a message from the parent runs from it to the next message from the parent or from another agent, or to the run's last entry.
    - A listed agent's active time is its wall time less `idle` over the period of the latest message from its parent, with its wall time running to now where that period and its turn have not ended. An agent with an unknown message has no active time and no budget.
    - Its budget is the N of the line of the form `Budget: N minutes` in the latest message from its parent that has a line of that form, and an agent none of whose parent's messages has one gets no budget. A line is of that form where it opens, past a list marker, with `Budget: N minutes`, and ends there or goes on after `.`, `,`, `;` or `:`; the text after it gives nothing. A line that opens with `Budget:` in another form gives no budget, and a message with lines of more than one N gives none, and an `undecided` line on stderr names each.
    - A call's command and an agent's text output are printed on one line, a command cut to its first {width} characters and a text output to its last {width}. A call's command is:
        - for a Bash call, its command, led by the kind of each ticket it files, as `kind K:`;
        - for an Agent call, its description;
        - for a Write, Edit or NotebookEdit call, the path of the file it writes;
        - for a SendMessage call, its recipient, as `to R:`, and its message;
        - for a SubagentHandback call, its message;
        - for any other call, nothing past its label.
    - A run whose agent type is unknown is refused, and so is an ID that names transcripts that differ and are not the transcripts of one run. A call whose agent type is unknown is labelled `agent ?`, a Bash call with no command is labelled `shell`, and a call whose input lacks a field its command reads, of those above but a SendMessage call's message, is printed without that field; an `undecided` line on stderr names each.
    """).format(factor=BUDGET_FACTOR, median_runs=MEDIAN_RUNS,
                low_wait_pct=LOW_WAIT_PCT, recent=RECENT_CALLS,
                width=COMMAND_WIDTH, bound=f"{CONTEXT_BOUND:,}",
                iso_time=ISO_TIME, operator=OPERATOR,
                repriced=REPRICED.format(model="MODEL"))


def utc_time(text: str) -> float:
    t = datetime.fromisoformat(text)
    return (t if t.tzinfo else t.replace(tzinfo=UTC)).timestamp()


def calls_under(command: str, ident: str) -> bool:
    """Whether the Bash command `command` runs this tool with `UNDER` on the
    run `ident`, as it writes the ID, with or without the `agent-` prefix."""
    want = bare_id(ident)
    for prog, rest in programs(command):
        if prog != Path(__file__).name:
            continue
        for i, word in enumerate(rest):
            given = (rest[i + 1] if word == UNDER and i + 1 < len(rest)
                     else word.removeprefix(UNDER + "=")
                     if word.startswith(UNDER + "=") else None)
            if given is not None and bare_id(given) == want:
                return True
    return False


def under_output(entries: list[Entry], call: str) -> str | None:
    """The text of the result of the Bash call `call` among `entries`,
    where that result says it completed in the foreground with no error, or
    None otherwise."""
    for e in entries:
        for b in blocks(e, "tool_result"):
            if e.get("type") == "user" and b.get("tool_use_id") == call:
                r = e.get("toolUseResult")
                r = r if isinstance(r, dict) else {}
                if b.get("is_error") or r.get(BACKGROUND_TASK) or r.get("interrupted"):
                    return None
                return result_text(b, r)
    return None


@dataclass(frozen=True)
class Previous:
    """The previous call of `UNDER` on a run: its time, the agent id of the
    operator that made it, and the agent ids its `LEFT_OPEN` line gives."""
    time: float
    agent: str
    left: frozenset[str]


def previous_call(path: Path, ident: str, undecided: list[str]) -> Previous | None:
    """The previous call of `UNDER` on the run at `path`, which `ident`
    names, as HELP gives that call, or None where none stands."""
    start = first_time(path)
    found: Previous | None = None
    for p in (p for ps in agent_transcripts().values() for p in ps):
        if start is not None and p.stat().st_mtime < start:
            continue
        if agent_type(p) != OPERATOR:
            continue
        calls = read_entries(p, naming={UNDER})
        made = {b["id"]: epoch(e["timestamp"]) for e in calls
                if e.get("type") == "assistant" and e.get("timestamp")
                for b in blocks(e, "tool_use")
                if b.get("name") == "Bash" and b.get("id")
                and calls_under(str((b.get("input") or {}).get("command", "")), ident)}
        if not made:
            continue
        results = read_entries(p, naming=set(made))
        for call, t in made.items():
            text = under_output(results, call)
            if text is None:
                continue
            if (n := len(lines(text, LEFT_OPEN))) > 1:
                undecided.append(mctx(
                    "the result of the call of `{under}` at {time} by {agent} "
                    "holds {n} `{left}` lines, so it counts as no call").format(
                        under=UNDER, time=utc_stamp(t),
                        agent=agent_id(p), n=n, left=LEFT_OPEN))
                continue
            given = read_under(text)
            if given is not None and (found is None or t > found.time):
                found = Previous(t, agent_id(p), given.left)
    return found


def runs_since(path: Path, ident: str, undecided: list[str]) -> list[Path]:
    """The runs `UNDER` takes under the run at `path`, which `ident` names,
    with its first lines printed."""
    previous = previous_call(path, ident, undecided)
    taken: list[Path] = []
    left: list[str] = []
    for p in runs_under(path):
        last = last_time(p)
        if not (previous is None or agent_id(p) in previous.left
                or (last is not None and last > previous.time)):
            continue
        if work_open(p, undecided):
            left.append(agent_id(p))
        else:
            taken.append(p)
    print(LEFT_OPEN, " ".join(left) or NO_RUN)
    print(RUNS_TAKEN, len(taken), *(agent_id(p) for p in taken))
    # The harness trims the end of a result's `stdout`, so the line after
    # `RUNS_TAKEN` gives it the line break `read_under` needs.
    if previous is None:
        print(mctx("previous call: none"))
    else:
        print(mctx("previous call: {time} by {agent}").format(
            time=utc_stamp(previous.time),
            agent=previous.agent))
    return taken


def budget_of(kind: str, items: int | None, undecided: list[str]) -> float | None:
    """The budget in seconds of the agent type `kind`, over every run of
    that type under the project directories, for a brief that gives no
    items where `items` is None, and otherwise for a brief that gives
    `items` items, or None where it gets none."""
    runs = [profile(last, undecided) for paths in agent_transcripts().values()
            if agent_type(last := chain(paths[0])[-1]) == kind]
    b = type_budget(kind, runs, None, items is not None, undecided)
    if b is None:
        return None
    return b.seconds if items is None else b.seconds * items


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", metavar="ID")
    ap.add_argument(UNDER, metavar="ID",
                    help=mctx("profile the runs under the run ID since an "
                              "operator's previous call of this on it"))
    ap.add_argument("--running", metavar="ID",
                    help=mctx("list the agents under the run ID whose work "
                              "is open"))
    ap.add_argument("--calls-since", type=utc_time, metavar="TIME",
                    help=mctx("with `--running`, print of each agent's last "
                              "calls only those that ended at or after TIME "
                              "or are pending: ") + ISO_TIME)
    ap.add_argument("--pending", metavar="ID",
                    help=mctx("list the agents pending to the run ID"))
    ap.add_argument("--open", metavar="ID",
                    help=mctx("print whether the work of the run ID is open"))
    ap.add_argument("--type", help=mctx("profile only runs of these agent "
                                        "types, separated by commas"))
    ap.add_argument("--pct", type=float, default=90,
                    help=mctx("the high percentile of wall time per type"))
    ap.add_argument("--top", type=int, default=8,
                    help=mctx("labels to print per run or per type; 0 prints "
                              "none per type and all for one run"))
    ap.add_argument("--runs", action="store_true",
                    help=mctx("also print one line per run"))
    ap.add_argument("--price-at", choices=sorted(PRICES), metavar="MODEL",
                    help=mctx("one of {models}; the text above gives what it "
                              "does").format(models=", ".join(sorted(PRICES))))
    ap.add_argument("--since", type=utc_time, metavar="DATE",
                    help=mctx("start of the window of runs each type's "
                              "budget is taken over, in place of the type's "
                              "own: ") + ISO_TIME)
    args = ap.parse_args(argv)
    types = set(args.type.split(",")) if args.type else None
    undecided: list[str] = []
    runs: list[Run] = []
    listed: list[Listed] = []
    if [bool(args.ids), bool(args.under), bool(args.running), bool(args.pending),
            bool(args.open)].count(True) != 1:
        print(mctx("refused: give one of IDs, `--under ID`, `--running ID`, "
                   "`--pending ID` and `--open ID`"),
              file=sys.stderr)
        return 2
    if args.under and args.type is not None:
        print(mctx("refused: `--under` takes no `--type`"), file=sys.stderr)
        return 2
    if args.price_at is not None and not (args.ids or args.under):
        print(mctx("refused: `--price-at` goes with IDs or `--under ID`"),
              file=sys.stderr)
        return 2
    if args.calls_since is not None and not args.running:
        print(mctx("refused: `--calls-since` goes with `--running ID` alone"),
              file=sys.stderr)
        return 2
    if args.price_at is not None:
        print(mctx("price at {model}: {repriced}").format(
            model=args.price_at, repriced=REPRICED.format(model=args.price_at)))
    try:
        if args.pending:
            for agent in pending_agents(find(args.pending), undecided):
                print(agent)
        elif args.open:
            path = find(args.open)
            if not is_subagent(path):
                raise Refused(mctx("`{ident}` names a session, not an agent")
                              .format(ident=args.open))
            print(mctx("open") if work_open(path, undecided)
                  else mctx("not open"))
        elif args.running:
            listed = running_agents(find(args.running), undecided)
        else:
            paths = (runs_since(find(args.under), args.under, undecided)
                     if args.under else
                     list(dict.fromkeys(p for ident in args.ids
                                        for p in transcripts(ident))))
            runs = [profile(p, undecided, args.price_at) for p in paths
                    if not types or run_type(p)[0] in types]
            if args.under:
                runs.sort(key=lambda r: (r.start is None, r.start or 0.0))
    except Refused as e:
        print(mctx("refused: {reason}").format(reason=e), file=sys.stderr)
        return 2
    if args.running:
        print_running(listed, time.time(), args.calls_since, undecided)
    elif not runs and not args.pending and not args.open and not args.under:
        print(mctx("refused: no run to profile"), file=sys.stderr)
        return 2
    elif runs and (len(runs) == 1 or args.runs or args.under):
        for r in runs:
            print(f"{r.label} {r.agent_type} {clock(r.start)}: {r.description}\n"
                  f"  wall {minutes(r.wall)}  {part_split(r.parts)}  "
                  f"cost {dollars(r.cost)}")
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
