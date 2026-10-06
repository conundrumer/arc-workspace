"""Profile agent runs from their Claude Code transcripts: where each run's
wall time goes. `--help` prints HELP."""

import argparse
import math
import re
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from controlled_markdown import mctx
from engine import checkout
from handbook.context import agent_names, agent_sources
from handbook.paths import console_importable, importable

console_importable()
# `scripts/` is no package: a test loads this module by its path, with
# `scripts/` off `sys.path`, and the modules below import from there.
importable(checkout.scripts())

from agent_launches import (Report, pending_agents, reports,  # noqa: E402
                            run_launches, running_agents)
from command_labels import AGENT_TOOLS, POLL, call_command, command_label  # noqa: E402
from quota import epoch  # noqa: E402
from run_reads import (AGENT_MESSAGE, BACKGROUND, MAIN, NOTIFICATION, blocks,  # noqa: E402
                       is_prompt, message_text, notified, parent_id, read_meta,
                       results_by_call, run_entries, run_type, session_agents,
                       session_of, text_of)
from transcripts import (Entry, Refused, agent_id, find,  # noqa: E402
                         is_subagent, transcripts)

# The terms of a type's budget, which HELP states.
BUDGET_FACTOR = 2
WINDOW_RUNS = 5
LOW_WAIT_PCT = 10
# The number of a running agent's last calls that `--running` prints.
RECENT_CALLS = 8
# The characters of a call's command or of an agent's text output that
# `--running` prints.
COMMAND_WIDTH = 160

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
    - Where the latest message from the parent is unknown, or no transcript of the parent is found, it prints `?`. A notification or a launch result whose status is of no known form gives no report. An `undecided` line on stderr names each.
    - More than one run prints, per agent type, the number of runs, the minimum, median, P-th percentile and maximum of wall time, the total, the median and P-th percentile of active time, which is wall time less `idle`, and each part's share of the total, then each type's labels by time, with the number of runs each appears in.
    - More than one run also prints the budget of each agent type, which is {factor} times a median wall time, printed with the runs it is taken over:
        - The window of a type that has an agent document under `prompts/agents/` is the runs whose first entry is at or after the last commit that changed that document, a document it includes or inlines, a lib file its rendered prompt holds, a script under `scripts/` its rendered prompt names, or a package under `src/` its rendered prompt runs with `-m`, and not a module such a script or package imports. `--since DATE`, an ISO date or datetime read in local time where it gives no offset, sets the window of every type to the runs whose first entry is at or after DATE. Where the window holds at least {window_runs} runs of the type, the median is taken over them.
        - A type with no agent document has a window only with `--since`, and a type whose paths no commit changed has none, and an `undecided` line on stderr names it.
        - Otherwise it is taken over the type's runs whose `waits` and `idle` together are under {low_wait_pct}% of wall time. A type with no such run gets no budget, and an `undecided` line on stderr names it.
    - `--running ID` lists the running agents under the run ID, where ID is a session id or an agent id, and a run that goes on under a later session is listed under that session's id: the agents the run launched, the agents those launched, and so on, whether or not their parent has completed. An agent has completed when its turn has ended, when its last entry is the harness's note that the user interrupted it, or when its parent has its result or a notification of it and its transcript has not changed since. The agents are listed in launch order, each parent's agents after it. In an agent's shell, `$CLAUDE_CODE_SESSION_ID` holds the id of the top-level session, in a subagent as well, so `--running $CLAUDE_CODE_SESSION_ID` lists the running agents of the whole session. For each agent it prints:
        - its agent id, type and launch description, its parent, which is the agent id of the agent that launched it or `main`, the time since its first entry, its active time with the time of the message it is measured from and, where that message's period has ended, the time it ended, its budget, and its context size in tokens, which is the input of its last request;
        - its working directory, as its first entry gives it;
        - its last text output, the end of the text of its last assistant entry that gives text;
        - each call it has in flight, with its label, its command and the time since the call;
        - each command or agent it backgrounded that is still running, with its label, its command and the time since the call;
        - its last {recent} calls in order, each with its label, its command and its duration, or `pending`.
    - `--pending ID` prints the agent id of each agent pending to the run ID, one per line, in launch order, where ID is a session id or an agent id. An agent is pending to the run that launched it from the Agent call that launched it, or from the last SendMessage call that resumed it, by the run or by any agent of the run's sessions, main among them, until the run holds the result of that Agent call, where the result does not say the agent runs in the background, or until any transcript of the session holds a notification of the agent, a notification that it stopped with work of its own still running among them. A SendMessage call to an agent whose result says neither that it resumed the agent nor that it queued the message resumes none, and an `undecided` line on stderr names it.
    - The messages from a running agent's parent are its brief, the messages its first turn answers, and each later message its parent sent: one the harness gives as from the parent's agent id, or, for an agent `main` launched, as from the coordinator or queued with no tag. The origin the harness gives a queued message is the one its attachment gives. A notification of the agent's own backgrounded work, a message from an agent it launched, from the user, from another agent, or, for an agent `main` did not launch, from the coordinator or queued with no tag, and a note of the harness are none. A message from another agent is one the harness gives as from an agent id other than the parent's and those of the agents it launched. A later message whose sender is none of these is unknown, and an `undecided` line on stderr names it.
    - The period of a message from the parent runs from it to the next message from the parent or from another agent, or to the run's last entry.
    - A running agent's active time is its wall time less `idle` over the period of the latest message from its parent, with its wall time running to now where that period has not ended. An agent with an unknown message has no active time and no budget.
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


class Part(Enum):
    MODEL = "model"
    TOOLS = "tools"
    WAITS = "waits"
    IDLE = "idle"


type Key = tuple[Part, str]

# A brief line that states a budget, and the opening of a line that words one.
BUDGET_LINE = re.compile(r"Budget: (\d+(?:\.\d+)?) minutes\.?")
BUDGET_OPENING = re.compile(r"budget\s*:", re.I)
LIST_MARKER = re.compile(r"^\s*(?:[-*+]|\d+[.)])?\s*")
WAIT_TOOLS = ("Monitor", "TaskOutput")
# The start of the text of the entry the harness writes where the user
# interrupts a run.
INTERRUPTED = "[Request interrupted by user"
# Ways a Bash result says the harness, not the call, moved it to the
# background after it had run in the foreground.
MOVED = ("timedOutAfterMs", "assistantAutoBackgrounded", "backgroundedByUser")


@dataclass
class Group:
    time: float = 0.0
    calls: int = 0
    ran: float = 0.0


@dataclass
class Span:
    """A call's span: its label, its command, the time of the call
    and the time of its result."""
    label: str
    command: str
    start: float
    end: float | None = None


@dataclass
class Message:
    """A message to a run: the index of its entry, its time, its text, and
    the run's `idle` time before it."""
    index: int
    time: float
    text: str
    idle: float


class Origin(Enum):
    """The kinds of origin the harness gives a message it delivers to a
    running agent: a notification of the agent's backgrounded work, and a
    message from the coordinator, the user or another agent."""
    TASK_NOTIFICATION = "task-notification"
    COORDINATOR = "coordinator"
    HUMAN = "human"
    PEER = "peer"


class Sender(Enum):
    """Who a message after a run's brief is from, as HELP gives it."""
    PARENT = "parent"
    AGENT = "agent"
    OTHER = "other"
    UNKNOWN = "unknown"


@dataclass
class Run:
    label: str
    agent_type: str
    description: str
    start: float | None
    wall: float
    parts: dict[Part, float]
    groups: dict[Key, Group]
    spans: list[Span]
    in_flight: list[Span]
    backgrounded: list[Span]
    # Whether the run's turn has ended, or its last entry is the harness's
    # note that the user interrupted it.
    ended: bool
    context: int | None
    said: str | None
    # The messages from the run's parent, the brief first, the messages
    # from other agents, and the text of each later message whose sender is
    # unknown.
    messages: list[Message]
    others: list[Message]
    unknown: list[str]
    cwd: str | None
    path: Path

    @property
    def active(self) -> float:
        return self.wall - self.parts[Part.IDLE]

    def period_end(self, i: int) -> Message | None:
        """The message that ends the period of the `i`-th message from the
        run's parent, or None where the period runs to the run's last entry."""
        m = self.messages[i]
        later = [n for n in (*self.messages[i + 1:i + 2], *self.others)
                 if n.index > m.index]
        return min(later, key=lambda n: n.index, default=None)

    def active_from(self, i: int) -> float | None:
        """The active time over the period of the `i`-th message from the
        run's parent. None where its start or a message is unknown."""
        if self.start is None or self.unknown:
            return None
        m = self.messages[i]
        nxt = self.period_end(i)
        if nxt is not None:
            return (nxt.time - m.time) - (nxt.idle - m.idle)
        end = self.start + self.wall
        return (end - m.time) - (self.parts[Part.IDLE] - m.idle)

    def active_at(self, now: float) -> float | None:
        """The active time of a run whose turn has not ended, over the period
        of the latest message from its parent, to `now` where that period has
        not ended: the time since its last entry goes to a pending call or
        to the model, so it is active. None where its start or that message
        is unknown."""
        if self.start is None or not self.messages:
            return None
        last = len(self.messages) - 1
        active = self.active_from(last)
        if active is None or self.period_end(last) is not None:
            return active
        return active + max(0.0, now - (self.start + self.wall))

    @property
    def low_wait(self) -> bool:
        """Whether the run's `waits` and `idle` are under LOW_WAIT_PCT% of
        its wall time."""
        waited = self.parts[Part.WAITS] + self.parts[Part.IDLE]
        return waited * 100 < self.wall * LOW_WAIT_PCT


@dataclass
class Call:
    """Where a tool call's time goes: `pending` while it is pending, and
    `background` once its result says it runs in the background."""
    pending: Key
    background: Key | None
    task_ids: list[str] = field(default_factory=list)


# Profiles.

def request_input(entry: Entry) -> int | None:
    """The input tokens of the request an assistant entry answers, or None
    where the entry gives no usage."""
    usage = (entry.get("message") or {}).get("usage")
    if not isinstance(usage, dict):
        return None
    return sum(usage.get(k) or 0 for k in (
        "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))


def launched_type(inp: dict[str, Any], result: dict[str, Any] | None,
                  session: Path) -> str | None:
    """The type of the agent an Agent call launched: the type the call gives,
    or else the type of the agent its result names."""
    if inp.get("subagent_type"):
        return inp["subagent_type"]
    aid = (result or {}).get("agentId")
    path = session_agents(session).get(aid) if aid else None
    meta = read_meta(path) if path else None
    return meta.get("agentType") if meta else None


def classify(block: dict[str, Any], result: dict[str, Any] | None,
             session: Path, undecided: list[str], run: str) -> Call:
    name, inp = block.get("name"), block.get("input") or {}
    r = result or {}
    task_ids = [str(r[k]) for k in ("backgroundTaskId", "taskId", "agentId") if r.get(k)]
    launched = bool(r.get("backgroundTaskId")) or r.get("status") == BACKGROUND
    if name in AGENT_TOOLS:
        kind = launched_type(inp, result, session)
        if kind is None:
            kind = "?"
            undecided.append(mctx("{run}: the agent type of call {call} is "
                                  "unknown").format(run=run, call=block.get("id")))
        key = (Part.WAITS, f"agent {kind}")
        return Call(key, key if launched else None, task_ids)
    if name in WAIT_TOOLS:
        return Call((Part.WAITS, name), None, task_ids)
    if name != "Bash":
        return Call((Part.TOOLS, str(name)), None, task_ids)
    label = command_label(inp.get("command", ""))
    background = (Part.WAITS, f"bg {label}")
    moved = launched and any(k in r for k in MOVED)
    if launched and not moved:
        return Call(background, background, task_ids)
    if inp.get("run_in_background"):
        return Call(background, None, task_ids)
    pending = (Part.WAITS, POLL) if label == POLL else (Part.TOOLS, label)
    return Call(pending, background if launched else None, task_ids)


def turns(entries: list[Entry]) -> tuple[set[int], set[int]]:
    """The indices of the entries that start a turn and of those that end
    one. A prompt starts a turn when the next message entry is the model's;
    a local command, such as /compact, gives the model none. An assistant
    entry with no tool call ends a turn when it says so, or when the next
    message entry is a prompt, and the result of a call that ends the turn,
    such as SubagentHandback, ends one."""
    starts: set[int] = set()
    ends: set[int] = set()
    nxt: Entry | None = None
    for i in range(len(entries) - 1, -1, -1):
        e = entries[i]
        if is_prompt(e) and nxt is not None and nxt.get("type") == "assistant":
            starts.add(i)
        if e.get("type") == "assistant" and not blocks(e, "tool_use"):
            stop = (e.get("message") or {}).get("stop_reason")
            if stop in ("end_turn", "stop_sequence") or (
                    nxt is not None and is_prompt(nxt)):
                ends.add(i)
        if e.get("toolEndsTurn"):
            ends.add(i)
        if e.get("type") in ("user", "assistant") or is_prompt(e):
            nxt = e
    return starts, ends


def sender(entry: Entry, parent: str, children: frozenset[str]) -> Sender:
    """Who a message after a run's brief is from, where `parent` is the
    agent id of the run's parent or `main`, and `children` the agent ids of
    the agents the run launched."""
    text = message_text(entry)
    queued = entry.get("type") == "attachment"
    given = (entry.get("attachment") or {}) if queued else entry
    kind = (given.get("origin") or {}).get("kind")
    if kind is not None and kind not in Origin:
        return Sender.UNKNOWN
    origin = None if kind is None else Origin(kind)
    from_main = Sender.PARENT if parent == MAIN else Sender.OTHER
    if origin is Origin.TASK_NOTIFICATION or NOTIFICATION.search(text):
        return Sender.OTHER
    if origin is Origin.COORDINATOR:
        return from_main
    if origin is Origin.HUMAN:
        return Sender.OTHER
    if origin is Origin.PEER or queued:
        m = AGENT_MESSAGE.search(text)
        if m:
            return sent_by(m.group(1), parent, children)
        if queued:
            return from_main
        return Sender.UNKNOWN
    if entry.get("isMeta") or entry.get("isCompactSummary") or text.startswith(INTERRUPTED):
        return Sender.OTHER
    return Sender.UNKNOWN


def sent_by(agent: str, parent: str, children: frozenset[str]) -> Sender:
    """Who a message the agent `agent` sent is from, for a run whose parent
    is `parent` and which launched the agents `children`."""
    if agent == parent:
        return Sender.PARENT
    return Sender.OTHER if agent in children else Sender.AGENT


def profile(path: Path, undecided: list[str]) -> Run:
    agent_type, description = run_type(path)
    label = agent_id(path) if is_subagent(path) else path.stem
    session = session_of(path)
    entries = run_entries(path)
    results = results_by_call(entries)
    starts, ends = turns(entries)
    # The index of the prompt the model first answers: the brief is the
    # prompts up to it.
    briefed = min(starts, default=len(entries))
    parent = parent_id(path) if is_subagent(path) else None
    children = run_launches(path)[1].get(label, frozenset())
    messages: list[Message] = []
    others: list[Message] = []
    unknown: list[str] = []

    parts = dict.fromkeys(Part, 0.0)
    groups: dict[Key, Group] = {}
    calls: dict[str, Call] = {}
    pending: dict[str, Key] = {}
    running: dict[str, tuple[Key, float]] = {}   # tool-use id -> key, start
    by_task: dict[str, str] = {}                # task id -> tool-use id
    spans: dict[str, Span] = {}
    context: int | None = None
    said: str | None = None
    idle = False
    prev: float | None = None
    first: float | None = None

    def group(key: Key) -> Group:
        return groups.setdefault(key, Group())

    def share(keys: Iterable[Key], d: float) -> None:
        keys = list(keys)
        for k in keys:
            group(k).time += d / len(keys)
            parts[k[0]] += d / len(keys)

    for i, e in enumerate(entries):
        if not e.get("timestamp"):
            continue
        t = epoch(e["timestamp"])
        if prev is not None and t > prev:
            d = t - prev
            if pending:
                share(pending.values(), d)
            elif not idle:
                parts[Part.MODEL] += d
            elif running:
                share([k for k, _ in running.values()], d)
            else:
                parts[Part.IDLE] += d
        prev = t if prev is None else max(t, prev)
        first = t if first is None else first
        etype = e.get("type")
        if parent is not None and i > briefed and is_prompt(e):
            who = sender(e, parent, children)
            if who is Sender.PARENT:
                messages.append(Message(i, t, message_text(e), parts[Part.IDLE]))
            elif who is Sender.AGENT:
                others.append(Message(i, t, message_text(e), parts[Part.IDLE]))
            elif who is Sender.UNKNOWN:
                unknown.append(message_text(e))
        if etype == "assistant":
            idle = False
            tokens = request_input(e)
            context = context if tokens is None else tokens
            text = "\n".join(b.get("text", "") for b in blocks(e, "text")).strip()
            said = text or said
            for b in blocks(e, "tool_use"):
                tid = b.get("id", "")
                c = calls[tid] = classify(b, results.get(tid), session,
                                          undecided, label)
                pending[tid] = c.pending
                spans[tid] = Span(c.pending[1], call_command(b, undecided, label), t)
                group(c.pending).calls += 1
        elif etype == "user":
            for b in blocks(e, "tool_result"):
                tid = b.get("tool_use_id", "")
                pending.pop(tid, None)
                if tid in spans:
                    spans[tid].end = t
                c = calls.get(tid)
                if c and c.background:
                    if c.background != c.pending:
                        group(c.background).calls += 1
                    running[tid] = (c.background, t)
                    for task in c.task_ids:
                        by_task[task] = tid
        if i in starts:
            idle = False
        if i in ends:
            idle = True
            pending.clear()
        for ident in notified(e) if etype != "assistant" else []:
            tid = by_task.get(ident, ident)
            if tid in running:
                k, start = running.pop(tid)
                group(k).ran += t - start
    end = prev or 0.0
    last_message = [e for e in entries if e.get("type") in ("user", "assistant")][-1:]
    interrupted = any(e.get("type") == "user" and text_of(
        (e.get("message") or {}).get("content")).startswith(INTERRUPTED)
        for e in last_message)
    brief = [message_text(e) for e in entries[:briefed + 1] if is_prompt(e)]
    if brief and first is not None:
        messages.insert(0, Message(briefed, first, "\n".join(brief), 0.0))
    cwd = next((e["cwd"] for e in entries if e.get("cwd")), None)
    in_flight = [spans[tid] for tid in pending if tid in spans]
    backgrounded = [spans[tid] for tid in running if tid in spans]
    for k, start in running.values():
        group(k).ran += end - start
    wall = end - first if first is not None else 0.0
    if first is None:
        undecided.append(mctx("{run}: no entry gives a time, so its start "
                              "is unknown").format(run=label))
    return Run(label, agent_type, description, first, wall, parts,
               {k: g for k, g in groups.items() if g.time or g.calls},
               list(spans.values()), in_flight, backgrounded, idle or interrupted, context, said,
               messages, others, unknown, cwd, path)


# Output.

def minutes(s: float) -> str:
    return f"{s / 60:.1f}m"


def percentile(values: list[float], p: float) -> float:
    """The nearest-rank percentile of a list of numbers."""
    v = sorted(values)
    return v[max(0, min(len(v) - 1, math.ceil(len(v) * p / 100) - 1))]


def clock(t: float | None) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(t)) if t is not None else "?"


def by_agent_type(runs: list[Run]) -> dict[str, list[Run]]:
    by_type: dict[str, list[Run]] = {}
    for r in runs:
        by_type.setdefault(r.agent_type, []).append(r)
    return by_type


def type_window(kind: str, undecided: list[str]) -> float | None:
    """The start of the window of the agent type `kind`, as HELP gives it:
    the time of the last commit that changed its paths, or None where it
    has no agent document or no commit changed them."""
    if kind not in agent_names():
        return None
    paths = [str(checkout.shown(p)) for p in agent_sources(kind)]
    out = checkout.git_out(checkout.ROOT, "log", "-1", "--format=%ct", "--",
                           *paths).strip()
    if not out:
        undecided.append(mctx("{kind}: no commit changed its paths, so it has "
                              "no window").format(kind=kind))
        return None
    return float(out)


def print_budgets(runs: list[Run], since_date: float | None,
                  undecided: list[str]) -> None:
    """Print each agent type's budget, its basis, and the runs it is taken
    over. `since_date` is the start of the window `--since` sets, where it
    is given."""
    by_type = by_agent_type(runs)
    print(f"{'type':<18} {'budget':>7} {'runs':>4}  basis")
    for kind in sorted(by_type):
        rs = by_type[kind]
        since = since_date if since_date is not None else type_window(kind, undecided)
        window: list[Run] = []
        if since is not None:
            for r in rs:
                if r.start is None:
                    undecided.append(mctx("{run}: its start is unknown, so it is "
                                          "left out of the window").format(run=r.label))
                elif r.start >= since:
                    window.append(r)
        if len(window) >= WINDOW_RUNS:
            basis, chosen = mctx("since {date}").format(date=clock(since)), window
        else:
            basis = mctx("waits and idle under {pct}% of wall").format(pct=LOW_WAIT_PCT)
            chosen = [r for r in rs if r.low_wait]
        if not chosen:
            undecided.append(mctx("{kind}: no run has waits and idle under "
                                  "{pct}% of wall, so it has no budget").format(
                kind=kind, pct=LOW_WAIT_PCT))
            continue
        budget = BUDGET_FACTOR * percentile([r.wall for r in chosen], 50)
        print(f"{kind:<18} {minutes(budget):>7} {len(chosen):>4}  {basis}")


def part_split(parts: dict[Part, float]) -> str:
    return "  ".join(f"{p.value} {minutes(parts[p])}" for p in Part)


def print_groups(groups: dict[Key, Group], top: int, wall: float,
                 present: dict[Key, int] | None = None) -> None:
    ranked = sorted(groups.items(), key=lambda kv: (-kv[1].time, kv[0][0].value, kv[0][1]))
    for (part, label), g in ranked[:top or None]:
        pct = f"{100 * g.time / wall:3.0f}%" if wall else "   -"
        ran = f"  ran {minutes(g.ran)}" if g.ran else ""
        runs = f"  in {present[(part, label)]} runs" if present else ""
        print(f"  {part.value:<5} {minutes(g.time):>8} {pct}  {g.calls:>4}x  {label}{ran}{runs}")


def print_types(runs: list[Run], pct: float, top: int) -> None:
    by_type = by_agent_type(runs)
    order = sorted(by_type, key=lambda k: (-sum(r.wall for r in by_type[k]), k))
    print(f"{'type':<18} {'runs':>4} {'min':>7} {'p50':>7} {f'p{pct:g}':>7} "
          f"{'max':>7} {'total':>8} {'act p50':>8} {f'act p{pct:g}':>8}  "
          + "  ".join(f"{p.value:>6}" for p in Part))
    for kind in order:
        rs = by_type[kind]
        walls = [r.wall for r in rs]
        active = [r.active for r in rs]
        total = sum(walls)
        shares = "  ".join(
            f"{(100 * sum(r.parts[p] for r in rs) / total if total else 0):5.0f}%"
            for p in Part)
        print(f"{kind:<18} {len(rs):>4} {minutes(min(walls)):>7} "
              f"{minutes(percentile(walls, 50)):>7} {minutes(percentile(walls, pct)):>7} "
              f"{minutes(max(walls)):>7} {minutes(total):>8} "
              f"{minutes(percentile(active, 50)):>8} {minutes(percentile(active, pct)):>8}  {shares}")
    if top == 0:
        return
    for kind in order:
        rs = by_type[kind]
        merged: dict[Key, Group] = {}
        present: dict[Key, int] = {}
        for r in rs:
            for k, g in r.groups.items():
                m = merged.setdefault(k, Group())
                m.time += g.time
                m.calls += g.calls
                m.ran += g.ran
                present[k] = present.get(k, 0) + 1
        total = sum(r.wall for r in rs)
        print(f"\n{kind}: {minutes(total)} over {len(rs)} runs")
        print_groups(merged, top, total, present)


def one_line(text: str, tail: bool = False) -> str:
    """`text` on one line, cut to its first COMMAND_WIDTH characters, or
    with `tail` to its last."""
    line = " ".join(text.split())
    if len(line) <= COMMAND_WIDTH:
        return line
    if tail:
        return "..." + line[3 - COMMAND_WIDTH:]
    return line[:COMMAND_WIDTH - 3] + "..."


def budget_openings(text: str) -> list[str]:
    """The lines of `text` that open with `Budget:`, past a list marker."""
    lines = (LIST_MARKER.sub("", line).strip() for line in text.splitlines())
    return [line for line in lines if BUDGET_OPENING.match(line)]


def message_name(r: Run, m: Message) -> str:
    """How an `undecided` line names a message from the parent of `r`."""
    if m is r.messages[0]:
        return mctx("the brief")
    return mctx("the message at {time}").format(time=clock(m.time))


def budgets_in_force(r: Run, undecided: list[str]) -> list[float | None]:
    """The budget in minutes in force for each message from the parent of
    `r`, which the latest message up to it states, as HELP gives it, or
    None."""
    for text in r.unknown:
        undecided.append(mctx("{run}: the sender of the message `{text}` is "
                              "unknown, so the run has no active time and no "
                              "budget").format(run=r.label, text=one_line(text)))
    budget: float | None = None
    budgets: list[float | None] = []
    for m in r.messages:
        stated: set[float] = set()
        for line in budget_openings(m.text):
            match = BUDGET_LINE.fullmatch(line)
            if match:
                stated.add(float(match.group(1)))
            else:
                undecided.append(mctx("{run}: the line `{line}` of {message} is "
                                      "not of the form `Budget: N minutes`, so "
                                      "it gives no budget").format(
                    run=r.label, line=line, message=message_name(r, m)))
        if len(stated) > 1:
            undecided.append(mctx("{run}: {message} states more than one budget, "
                                  "{values}, so it gives none").format(
                run=r.label, message=message_name(r, m),
                values=", ".join(f"{v:g}" for v in sorted(stated))))
        if stated:
            budget = next(iter(stated)) if len(stated) == 1 else None
        budgets.append(None if r.unknown else budget)
    return budgets


def of_budget(budget: float | None) -> str:
    """The text that follows an active time to give its budget in minutes."""
    return f" of budget {minutes(budget * 60)}" if budget is not None else ""


def print_span(m: Span, time_text: str) -> None:
    command = f": {one_line(m.command)}" if m.command else ""
    print(f"    {time_text:>8}  {m.label}{command}")


def print_running(runs: list[tuple[str, Run]], now: float,
                  undecided: list[str]) -> None:
    for parent, r in runs:
        since = minutes(now - r.start) if r.start is not None else "?"
        active_time = r.active_at(now)
        ended = r.period_end(len(r.messages) - 1) if r.messages else None
        to = " " + mctx("to {time}").format(time=clock(ended.time)) if ended else ""
        active = (mctx("{active} since {time}{to}").format(
            active=minutes(active_time), time=clock(r.messages[-1].time), to=to)
            if active_time is not None else "?")
        budget = next(reversed(budgets_in_force(r, undecided)), None)
        context = f"{r.context:,}" if r.context is not None else "?"
        print(f"{r.label} {r.agent_type}  parent {parent}  {since}  "
              f"active {active}{of_budget(budget)}  "
              f"context {context} tokens: {r.description}")
        print(f"  cwd: {r.cwd or '?'}")
        print(f"  said: {one_line(r.said, tail=True) if r.said is not None else '-'}")
        for title, spans in (("in flight", r.in_flight), ("running", r.backgrounded)):
            if spans:
                print(f"  {title}:")
            for m in spans:
                print_span(m, minutes(now - m.start))
        print("  recent:")
        for m in r.spans[-RECENT_CALLS:]:
            print_span(m, minutes(m.end - m.start) if m.end is not None else "pending")


def print_messages(r: Run, undecided: list[str]) -> None:
    """Print each message from the parent of `r` with its active time and
    the budget in force for it, marking each active time past its budget."""
    if r.agent_type == MAIN:
        return
    print("  messages from the parent:")
    budgets = budgets_in_force(r, undecided)
    for i, (m, budget) in enumerate(zip(r.messages, budgets, strict=True)):
        active = r.active_from(i)
        past = ("  past budget" if active is not None and budget is not None
                and active > budget * 60 else "")
        active_text = minutes(active) if active is not None else "?"
        print(f"    {clock(m.time)}  active {active_text}{of_budget(budget)}{past}")


def print_report(r: Run, undecided: list[str]) -> None:
    """Print the latest report of the subagent of `r` that reached its
    parent after the parent's latest message to it, as HELP gives it."""
    if r.agent_type == MAIN:
        return
    found: list[Report] | None = None
    if r.unknown or not r.messages:
        undecided.append(mctx("{run}: the latest message from its parent is "
                              "unknown, so whether a report reached the parent "
                              "after it is unknown").format(run=r.label))
    else:
        found = reports(r.path, r.messages[-1].time, undecided)
    if found is None:
        print("  " + mctx("report to the parent: ?"))
    elif not found:
        print("  " + mctx("report to the parent: none after the message at "
                          "{time}").format(time=clock(r.messages[-1].time)))
    else:
        last = found[-1]
        print("  " + mctx("report to the parent: {time} {kind}: {text}").format(
            time=clock(last.time), kind=last.kind.value, text=one_line(last.text)))


def iso_date(text: str) -> float:
    return epoch(text)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=HELP,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*", metavar="ID")
    ap.add_argument("--running", metavar="ID",
                    help=mctx("list the agents the run ID launched that have "
                              "not completed"))
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
    listed: list[tuple[str, Run]] = []
    if [bool(args.ids), bool(args.running), bool(args.pending)].count(True) != 1:
        print(mctx("refused: give one of IDs, `--running ID` and `--pending ID`"),
              file=sys.stderr)
        return 2
    try:
        if args.pending:
            for agent in pending_agents(find(args.pending), undecided):
                print(agent)
        elif args.running:
            profiled = ((parent, profile(p, undecided)) for parent, p in
                        running_agents(find(args.running), undecided))
            listed = [(parent, r) for parent, r in profiled if not r.ended]
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
    for line in undecided:
        print(mctx("undecided: {line}").format(line=line), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
