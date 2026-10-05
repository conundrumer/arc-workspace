"""Profile agent runs from their Claude Code transcripts: where each run's
wall time goes. `--help` prints HELP."""

import argparse
import filecmp
import json
import math
import re
import shlex
import sys
import time
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from enum import Enum
from functools import cache
from pathlib import Path
from typing import Any

from controlled_markdown import mctx
from engine import checkout
from handbook.context import agent_names, agent_sources
from handbook.paths import console_importable, importable

console_importable()
# `scripts/` is no package: a test loads this module by its path, with
# `scripts/` off `sys.path`, and `file_ticket` imports from there.
importable(checkout.scripts())

from cli import command_args  # noqa: E402
from cli.parser import parser as run_dl_parser  # noqa: E402
from file_ticket import TICKET_HEAD  # noqa: E402
from quota import epoch  # noqa: E402
from solver_console import config  # noqa: E402

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
    - An ID is an agent id, a session id, or the path of a `.jsonl` transcript. A session brings its main transcript, as type `main`, and each of its subagents' transcripts. Each transcript is a run.
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
    - More than one run prints, per agent type, the number of runs, the minimum, median, P-th percentile and maximum of wall time, the total, the median and P-th percentile of active time, which is wall time less `idle`, and each part's share of the total, then each type's labels by time, with the number of runs each appears in.
    - More than one run also prints the budget of each agent type, which is {factor} times a median wall time, printed with the runs it is taken over:
        - The window of a type that has an agent document under `prompts/agents/` is the runs whose first entry is at or after the last commit that changed that document, a document it includes or inlines, a lib file its rendered prompt holds, a script under `scripts/` its rendered prompt names, or a package under `src/` its rendered prompt runs with `-m`, and not a module such a script or package imports. `--since DATE`, an ISO date or datetime read in local time where it gives no offset, sets the window of every type to the runs whose first entry is at or after DATE. Where the window holds at least {window_runs} runs of the type, the median is taken over them.
        - A type with no agent document has a window only with `--since`, and a type whose paths no commit changed has none, and an `undecided` line on stderr names it.
        - Otherwise it is taken over the type's runs whose `waits` and `idle` together are under {low_wait_pct}% of wall time. A type with no such run gets no budget, and an `undecided` line on stderr names it.
    - `--running ID` lists the running agents under the run ID, where ID is a session id or an agent id: the agents the run launched, the agents those launched, and so on, whether or not their parent has completed. An agent has completed when its turn has ended, when its last entry is the harness's note that the user interrupted it, or when its parent has its result or a notification of it and its transcript has not changed since. The agents are listed in launch order, each parent's agents after it. In an agent's shell, `$CLAUDE_CODE_SESSION_ID` holds the id of the top-level session, in a subagent as well, so `--running $CLAUDE_CODE_SESSION_ID` lists the running agents of the whole session. For each agent it prints:
        - its agent id, type and launch description, its parent, which is the agent id of the agent that launched it or `main`, the time since its first entry, its active time with the time of the message it is measured from and, where that message's period has ended, the time it ended, its budget, and its context size in tokens, which is the input of its last request;
        - its working directory, as its first entry gives it;
        - its last text output, the end of the text of its last assistant entry that gives text;
        - each call it has in flight, with its label, its command and the time since the call;
        - each command or agent it backgrounded that is still running, with its label, its command and the time since the call;
        - its last {recent} calls in order, each with its label, its command and its duration, or `pending`.
    - `--pending ID` prints the agent id of each agent pending to the run ID, one per line, in launch order, where ID is a session id or an agent id. An agent is pending to the run that launched it from the Agent call that launched it, or from the run's last SendMessage call that resumed it, until the run holds the result of that Agent call, where the result does not say the agent runs in the background, or until any transcript of the session holds a notification of the agent, a notification that it stopped with work of its own still running among them. A SendMessage call to an agent whose result says neither that it resumed the agent nor that it queued the message resumes none, and an `undecided` line on stderr names it.
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
    - A run whose agent type is unknown is refused, and so is an ID that names transcripts that differ. A call whose agent type is unknown is labelled `agent ?`, and a Bash call with no command is labelled `shell`; an `undecided` line on stderr names each.
    """).format(factor=BUDGET_FACTOR, window_runs=WINDOW_RUNS,
                low_wait_pct=LOW_WAIT_PCT, recent=RECENT_CALLS,
                width=COMMAND_WIDTH)


class Part(Enum):
    MODEL = "model"
    TOOLS = "tools"
    WAITS = "waits"
    IDLE = "idle"


type Key = tuple[Part, str]
type Entry = dict[str, Any]

MAIN = "main"
WRITE_TOOLS = ("Write", "Edit", "NotebookEdit")
# A brief line that states a budget, and the opening of a line that words one.
BUDGET_LINE = re.compile(r"Budget: (\d+(?:\.\d+)?) minutes\.?")
BUDGET_OPENING = re.compile(r"budget\s*:", re.I)
LIST_MARKER = re.compile(r"^\s*(?:[-*+]|\d+[.)])?\s*")
WAIT_TOOLS = ("Monitor", "TaskOutput")
AGENT_TOOLS = ("Agent", "Task")
KNOWN = {"gate.py": "gate", "merge_change.py": "merge_change.py",
         "materialize.py": "materialize.py", "pytest": "pytest",
         "pyright": "pyright"}
RUN_DL = "run_dl.py"
SETUP = {"cd", "echo", "export", "set", "true", ":", "printf", "date",
         "source", ".", "uptime", "[", "[[", "test"}
WRAPPERS = {"timeout", "time", "nice", "env", "exec", "command", "sudo", "uv",
            "run"}
# Options that take the next word as their value, by the wrapper they follow.
# A wrapper not listed takes no such option.
UV_OPTIONS = frozenset({"--env-file", "--with", "--python", "-p", "--project",
                        "--directory", "--package", "--extra", "--group",
                        "--from"})
WRAPPER_OPTIONS = {"timeout": frozenset({"-s", "-k"}),
                   "env": frozenset({"-u", "--unset", "-C", "--chdir", "-S",
                                     "--split-string"}),
                   "uv": UV_OPTIONS, "run": UV_OPTIONS}
OPENERS = {"do", "then", "else", "elif", "if", "while", "until", "!", "{", "("}
CLOSERS = {"for", "case", "done", "fi", "esac", "}"}
POLL = "poll"
# The start of the text of the entry the harness writes where the user
# interrupts a run.
INTERRUPTED = "[Request interrupted by user"
# The openings of the message of a SendMessage result where the call resumed
# the agent it was sent to, and where it queued the message to a running one.
RESUMING = "Resuming agent"
QUEUED = "Message queued"
# Ways a Bash result says the harness, not the call, moved it to the
# background after it had run in the foreground.
MOVED = ("timedOutAfterMs", "assistantAutoBackgrounded", "backgroundedByUser")
AGENT_MESSAGE = re.compile(r'<agent-message from="([^"]+)"')
NOTIFICATION = re.compile(r"<task-notification>(.*?)</task-notification>", re.S)
TAG = re.compile(r"<(task-id|tool-use-id)>([^<]+)</\1>")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2[ \t]*(?=\n|$)",
                     re.S)
REDIRECT = re.compile(r"\d*>&\d+|&>")
ASSIGNMENT = re.compile(r"^(\w+)=(.*)$", re.S)
VARIABLE = re.compile(r"\$\{(\w+)\}|\$(\w+)")


class Refused(Exception):
    pass


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


# Transcripts.

def project_dirs() -> list[Path]:
    dirs: list[Path] = []
    for d in (config.USER_PROJECTS, config.PROJECTS):
        if d.is_dir() and d.resolve() not in [x.resolve() for x in dirs]:
            dirs.append(d)
    return dirs


def one_of(ident: str, found: list[Path]) -> Path | None:
    if not found:
        return None
    if all(filecmp.cmp(found[0], p, shallow=False) for p in found[1:]):
        return found[0]
    raise Refused(mctx("`{ident}` names more than one transcript, and they "
                       "differ; give the path of one of {paths}").format(
        ident=ident, paths=", ".join(str(p) for p in found)))


def find(ident: str) -> Path:
    if ident.endswith(".jsonl"):
        path = Path(ident).expanduser()
        if not path.is_file():
            raise Refused(mctx("no file `{path}`").format(path=path))
        return path
    name = ident.removeprefix("agent-")
    for pattern in (f"*/{ident}.jsonl", f"*/*/subagents/**/agent-{name}.jsonl"):
        found = sorted(p for d in project_dirs() for p in d.glob(pattern))
        path = one_of(ident, found)
        if path:
            return path
    raise Refused(mctx("no transcript of session or agent `{ident}` under "
                       "{dirs}").format(ident=ident, dirs=", ".join(
                           str(d) for d in project_dirs())))


def is_subagent(path: Path) -> bool:
    return "subagents" in path.parts


def transcripts(ident: str) -> list[Path]:
    path = find(ident)
    if is_subagent(path):
        return [path]
    return [path, *sorted(path.with_suffix("").glob("subagents/**/agent-*.jsonl"))]


def agent_id(path: Path) -> str:
    return path.stem.removeprefix("agent-")


def read_meta(path: Path) -> dict[str, Any] | None:
    meta = path.with_suffix(".meta.json")
    if not meta.is_file():
        return None
    return json.loads(meta.read_text())


def subagent_meta(path: Path) -> dict[str, Any]:
    """The `.meta.json` of the subagent whose transcript is at `path`, which
    must give its agent type."""
    meta = read_meta(path)
    if meta is None or "agentType" not in meta:
        raise Refused(mctx("the agent type of `{path}` is unknown: its "
                           ".meta.json is absent or gives none").format(path=path))
    return meta


def run_type(path: Path) -> tuple[str, str]:
    if not is_subagent(path):
        return MAIN, ""
    meta = subagent_meta(path)
    return meta["agentType"], meta.get("description", "")


def parent_id(path: Path) -> str:
    """The agent id of the parent of the agent whose transcript is at
    `path`, or `main`, which its `.meta.json` gives by naming no parent."""
    return subagent_meta(path).get("parentAgentId") or MAIN


def read_entries(path: Path, naming: set[str] | None = None) -> list[Entry]:
    """The entries of the transcript at `path`, or with `naming` only those
    whose line holds one of its words, which spares parsing the rest."""
    entries: list[Entry] = []
    with path.open() as fh:
        for line in fh:
            if naming is not None and not any(w in line for w in naming):
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def blocks(entry: Entry, kind: str) -> list[dict[str, Any]]:
    content = (entry.get("message") or {}).get("content")
    if not isinstance(content, list):
        return []
    return [b for b in content if isinstance(b, dict) and b.get("type") == kind]


def text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
    return ""


# Bash commands.

def segment_program(words: list[str]) -> tuple[str | None, list[str]]:
    """The program a simple command runs, and its arguments, past
    environment assignments, wrappers such as timeout and uv run, and an
    interpreter given a script or module."""
    toks = [t for t in (t.strip("(){}") for t in words) if t]
    i, interp, wrapper = 0, None, None
    while i < len(toks):
        t = toks[i]
        base = Path(t).name
        if interp is None and base in WRAPPERS:
            wrapper, i = base, i + 1
        elif interp is None and (ASSIGNMENT.match(t)
                                 or re.fullmatch(r"\d+[smh]?", t)):
            i += 1
        elif interp is None and re.fullmatch(r"python[\d.]*|bash|sh|zsh", base):
            interp, i = base, i + 1
        elif interp and t == "-c":
            return interp, toks[i + 1:]
        elif interp and t == "-m" and i + 1 < len(toks):
            return toks[i + 1], toks[i + 2:]
        elif interp and t.startswith("-") and t != "-":
            i += 1
        elif interp and t != "-" and not t.startswith("<"):
            return base, toks[i + 1:]
        elif interp:
            return interp, toks[i + 1:]
        elif wrapper and t in WRAPPER_OPTIONS.get(wrapper, frozenset()):
            i += 2
        elif t.startswith("-"):
            i += 1
        else:
            return base, toks[i + 1:]
    return interp, []


def shell_segments(cmd: str) -> list[str]:
    """The simple commands of a shell command line: split at ;, &, |, newlines,
    and the openings of $( and backquotes, outside quotes."""
    segs: list[str] = []
    cur: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(cmd):
        c = cmd[i]
        if quote:
            if c == quote:
                quote = None
            elif c == "\\" and quote == '"':
                cur.append(c)
                i += 1
                c = cmd[i] if i < len(cmd) else ""
            cur.append(c)
        elif c in "'\"":
            quote = c
            cur.append(c)
        elif c == "\\":
            cur.append(cmd[i:i + 2])
            i += 1
        elif c in ";&|\n`" or cmd.startswith("$(", i):
            segs.append("".join(cur))
            cur = []
            i += 1 if c == "$" else 0
        else:
            cur.append(c)
        i += 1
    segs.append("".join(cur))
    return segs


def split_words(seg: str) -> list[str]:
    """The words of a simple command, with quotes removed and comments
    dropped, or its blank-separated words where its quotes do not pair."""
    try:
        return shlex.split(seg, comments=True)
    except ValueError:
        return [w.strip("'\"") for w in seg.split()]


def simple_commands(cmd: str) -> Iterator[list[str]]:
    """The words of each simple command of a Bash command line, past the
    keywords that open it, with the values of the shell variables set
    before it put in place of their names."""
    cmd = REDIRECT.sub(" ", HEREDOC.sub(" ", cmd)).replace("\\\n", " ")
    values: dict[str, str] = {}

    def expand(word: str) -> str:
        return VARIABLE.sub(lambda m: values.get(m.group(1) or m.group(2), m.group(0)),
                            word)

    for seg in shell_segments(cmd):
        words = split_words(seg)
        while words and words[0] in OPENERS:
            words.pop(0)
        if words and words[0] == "export":
            words.pop(0)
        sets = [ASSIGNMENT.match(w) for w in words]
        if words and all(sets):
            for m in sets:
                if m:
                    values[m.group(1)] = expand(m.group(2))
            continue
        yield [expand(w) for w in words]


@cache
def run_dl_commands() -> frozenset[str]:
    return frozenset(run_dl_parser()[1])


def run_dl_command(args: list[str]) -> str:
    """The command a run of `run_dl.py` with the arguments `args` runs, or
    the help flag it gives."""
    return command_args(args, run_dl_commands())[0]


def command_label(cmd: str) -> str:
    """The known commands a Bash command runs, joined by " + ", or else
    `poll` for one that runs sleep, or else the first program it runs
    past setup, or else the first program it runs."""
    known: list[str] = []
    first: str | None = None
    setup: str | None = None
    for prog, rest in programs(cmd):
        label = f"{RUN_DL} {run_dl_command(rest)}" if prog == RUN_DL else KNOWN.get(prog)
        if label and label not in known:
            known.append(label)
        if prog in SETUP:
            setup = setup or prog
        else:
            first = first or prog
    if known:
        return " + ".join(known)
    if runs_sleep(cmd):
        return POLL
    return first or setup or "shell"


def programs(cmd: str) -> Iterator[tuple[str, list[str]]]:
    """The program each simple command of a Bash command runs, with its
    arguments, as `segment_program` gives them."""
    for words in simple_commands(cmd):
        if not words or words[0] in CLOSERS:
            continue
        prog, rest = segment_program(words)
        if prog:
            yield prog, rest


def runs_sleep(cmd: str) -> bool:
    """Whether a simple command of a Bash command runs `sleep`: the call
    waits by timer."""
    return any(prog == "sleep" for prog, _ in programs(cmd))


# Profiles.

def call_command(block: dict[str, Any]) -> str:
    """The command of a call, as HELP gives it."""
    name, inp = block.get("name"), block.get("input") or {}
    if name == "Bash":
        command = str(inp.get("command", ""))
        kinds = "".join(f"kind {m.group('kind')}: "
                        for m in TICKET_HEAD.finditer(command))
        return kinds + command
    if name in AGENT_TOOLS:
        return str(inp.get("description", ""))
    if name in WRITE_TOOLS:
        return str(inp.get("file_path") or inp.get("notebook_path") or "")
    if name == "SendMessage":
        return f"to {inp.get('to', '?')}: {inp.get('message', '')}"
    if name == "SubagentHandback":
        return str(inp.get("message", ""))
    return ""


def request_input(entry: Entry) -> int | None:
    """The input tokens of the request an assistant entry answers, or None
    where the entry gives no usage."""
    usage = (entry.get("message") or {}).get("usage")
    if not isinstance(usage, dict):
        return None
    return sum(usage.get(k) or 0 for k in (
        "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))


def results_by_call(entries: list[Entry]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for e in entries:
        r = e.get("toolUseResult")
        if e.get("type") != "user" or not isinstance(r, dict):
            continue
        for b in blocks(e, "tool_result"):
            out[b.get("tool_use_id", "")] = r
    return out


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


def session_of(path: Path) -> Path:
    """The session directory a transcript belongs to."""
    session = path.parents[1] if is_subagent(path) else path.with_suffix("")
    while is_subagent(session):
        session = session.parent
    return session


@cache
def session_agents(session: Path) -> dict[str, Path]:
    return {agent_id(p): p for p in session.glob("subagents/**/agent-*.jsonl")}


def classify(block: dict[str, Any], result: dict[str, Any] | None,
             session: Path, undecided: list[str], run: str) -> Call:
    name, inp = block.get("name"), block.get("input") or {}
    r = result or {}
    task_ids = [str(r[k]) for k in ("backgroundTaskId", "taskId", "agentId") if r.get(k)]
    launched = bool(r.get("backgroundTaskId")) or r.get("status") == "async_launched"
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
    if "command" not in inp:
        undecided.append(mctx("{run}: Bash call {call} gives no command").format(
            run=run, call=block.get("id")))
    label = command_label(inp.get("command", ""))
    background = (Part.WAITS, f"bg {label}")
    moved = launched and any(k in r for k in MOVED)
    if launched and not moved:
        return Call(background, background, task_ids)
    if inp.get("run_in_background"):
        return Call(background, None, task_ids)
    pending = (Part.WAITS, POLL) if label == POLL else (Part.TOOLS, label)
    return Call(pending, background if launched else None, task_ids)


def is_prompt(entry: Entry) -> bool:
    """Whether an entry gives the model a message: a user entry that answers
    no tool call, or a message queued while the model worked."""
    if entry.get("type") == "attachment":
        return (entry.get("attachment") or {}).get("type") == "queued_command"
    return entry.get("type") == "user" and not blocks(entry, "tool_result")


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


def message_text(entry: Entry) -> str:
    """The text of a user entry, or of a message queued while the model
    worked."""
    if entry.get("type") == "attachment":
        a = entry.get("attachment") or {}
        return text_of(a.get("prompt")) if a.get("type") == "queued_command" else ""
    return text_of((entry.get("message") or {}).get("content"))


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


def notified(entry: Entry) -> list[str]:
    text = message_text(entry)
    return [v for body in NOTIFICATION.findall(text) for _, v in TAG.findall(body)]


def profile(path: Path, undecided: list[str]) -> Run:
    agent_type, description = run_type(path)
    label = agent_id(path) if is_subagent(path) else path.stem
    session = session_of(path)
    entries = read_entries(path)
    results = results_by_call(entries)
    starts, ends = turns(entries)
    # The index of the prompt the model first answers: the brief is the
    # prompts up to it.
    briefed = min(starts, default=len(entries))
    parent = parent_id(path) if is_subagent(path) else None
    children = session_launches(session)[1].get(label, frozenset())
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
                spans[tid] = Span(c.pending[1], call_command(b), t)
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
               messages, others, unknown, cwd)


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


# Running agents.

@cache
def session_launches(session: Path) -> tuple[dict[str, Path], dict[str, frozenset[str]]]:
    """The transcripts of a session's agents by the Agent call that launched
    each, and the agent ids of the agents each subagent launched, by its
    agent id, as their `.meta.json` files give them."""
    by_call: dict[str, Path] = {}
    children: dict[str, set[str]] = {}
    for aid, p in session_agents(session).items():
        meta = read_meta(p) or {}
        if meta.get("toolUseId"):
            by_call[meta["toolUseId"]] = p
        if meta.get("parentAgentId"):
            children.setdefault(meta["parentAgentId"], set()).add(aid)
    return by_call, {k: frozenset(v) for k, v in children.items()}


@dataclass
class Launch:
    """An agent a run launched: its agent id, where the run's transcript
    gives it, its transcript, where one gives the call as its launch, the
    time of the run's last call that launched or resumed it, and the time
    of the run's last sign that it reported, or None where the run holds
    none."""
    agent: str | None
    path: Path | None
    since: float
    done: float | None

    @property
    def pending(self) -> bool:
        """Whether the agent is pending to the run: the run holds no sign
        that it reported since the call that launched or last resumed it."""
        return self.done is None or self.since > self.done


def resumed(result: dict[str, Any], run: str, call: str,
            undecided: list[str]) -> str | None:
    """The agent id of the agent a SendMessage call resumed, as its result
    gives it, or None where the call resumed none or its result is of an
    unknown form."""
    if result.get("resumedAgentId"):
        return str(result["resumedAgentId"])
    message = str(result.get("message", ""))
    if message.startswith(RESUMING):
        return (result.get("pin") or {}).get("id")
    if result.get("pin") and not message.startswith(QUEUED):
        undecided.append(mctx("{run}: the result of SendMessage call {call} "
                              "says neither that it resumed an agent nor "
                              "that it queued the message").format(
            run=run, call=call))
    return None


def launched(path: Path, undecided: list[str]) -> list[Launch]:
    """The agents the run at `path` launched, in the order of their launch.
    A sign that an agent reported is the run's notification of it, or a
    result of its launch that does not say the agent runs in the
    background."""
    entries = [e for e in read_entries(path) if e.get("timestamp")]
    results = results_by_call(entries)
    answered = {b.get("tool_use_id"): epoch(e["timestamp"]) for e in entries
                if e.get("type") == "user" for b in blocks(e, "tool_result")}
    told = {v: epoch(e["timestamp"]) for e in entries
            if e.get("type") != "assistant" for v in notified(e)}
    resumes = {aid: epoch(e["timestamp"]) for e in entries
               if e.get("type") == "assistant"
               for b in blocks(e, "tool_use") if b.get("name") == "SendMessage"
               if (aid := resumed(results.get(b.get("id", "")) or {}, path.stem,
                                  b.get("id", ""), undecided))}
    by_call = session_launches(session_of(path))[0]
    out: list[Launch] = []
    for e in entries:
        if e.get("type") != "assistant":
            continue
        for b in blocks(e, "tool_use"):
            if b.get("name") not in AGENT_TOOLS:
                continue
            tid = b.get("id", "")
            result = results.get(tid) or {}
            background = result.get("status") == "async_launched"
            signs = [told.get(tid), told.get(result.get("agentId", "")),
                     None if background else answered.get(tid)]
            done = max((t for t in signs if t is not None), default=None)
            child = by_call.get(tid)
            aid = agent_id(child) if child else result.get("agentId")
            since = max(epoch(e["timestamp"]), resumes.get(aid or "", 0.0))
            if child is None and done is None:
                undecided.append(mctx("{run}: no transcript gives call {call} as "
                                      "its launch").format(run=path.stem, call=tid))
            out.append(Launch(aid, child, since, done))
    return out


def pending_agents(path: Path, undecided: list[str]) -> list[str]:
    """The agent ids of the agents pending to the run at `path`, in the
    order of their launch, as HELP gives them."""
    own = [a for a in launched(path, undecided) if a.pending and a.agent]
    if not own:
        return []
    told = session_notified(session_of(path), {a.agent for a in own if a.agent},
                            min(a.since for a in own))
    out: list[str] = []
    for a in own:
        last = told.get(a.agent or "")
        if a.agent and (last is None or last <= a.since):
            out.append(a.agent)
    return out


def session_notified(session: Path, agents: set[str],
                     since: float) -> dict[str, float]:
    """The time of the last notification of each of `agents` that a
    transcript of `session` changed at or after `since` holds."""
    out: dict[str, float] = {}
    for p in [session.with_suffix(".jsonl"), *session_agents(session).values()]:
        if not p.is_file() or p.stat().st_mtime < since:
            continue
        for e in read_entries(p, naming=agents):
            if not e.get("timestamp") or e.get("type") == "assistant":
                continue
            for v in notified(e):
                if v in agents:
                    out[v] = max(out.get(v, 0.0), epoch(e["timestamp"]))
    return out


def parent_label(path: Path) -> str:
    return agent_id(path) if is_subagent(path) else MAIN


def running_agents(path: Path, undecided: list[str]) -> list[tuple[str, Path]]:
    """The agents under the run at `path` whose parent holds no sign that
    they completed, or whose transcript changed after the last sign, each
    with its parent, each parent's agents after it."""
    parents = session_launches(session_of(path))[1]
    out: list[tuple[str, Path]] = []
    for a in launched(path, undecided):
        child = a.path
        if child is None:
            continue
        if a.done is None or child.stat().st_mtime > a.done:
            out.append((parent_label(path), child))
        if agent_id(child) in parents:
            out.extend(running_agents(child, undecided))
    return out


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
            paths = [p for ident in args.ids for p in transcripts(ident)]
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
