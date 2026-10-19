"""Read the run of an agent from its Claude Code transcripts: its
`.meta.json`, its entries and the texts, call results, messages,
notifications and request sizes they give, and the session its transcripts
belong to."""

import re
import sys
from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

from controlled_markdown import mctx
from operations.constants import COORDINATOR as MAIN
from operations.printed_forms import POLL_AGAIN
from token_prices import request_input
from file_reads import is_file
from state_reads import DERIVED, Kept, state_cache
from transcripts import (agent_id, chain, first_parent, is_subagent, main_transcript,
                         session_agent_transcripts, session_directory)
from entry_reads import read_entries
from transcript_entries import blocks, epoch, meta_path, transcript_meta
from transcript_snapshots import Entry, Refused

UNKNOWN_TYPE = mctx("the agent type of `{path}` is unknown: its .meta.json is "
                    "absent or gives none")
AGENT_MESSAGE = re.compile(r'<agent-message from="([^"]+)"')
AGENT_MESSAGE_END = "</agent-message>"
NOTIFICATION = re.compile(r"<task-notification>(.*?)</task-notification>", re.S)
TAG = re.compile(r"<(task-id|tool-use-id)>([^<]+)</\1>")
RESUMED_ELSEWHERE = re.compile(r'\AAgent "[^"]*" was resumed by another agent and now reports '
                               r"to it; its completion will not be delivered here\.\Z")
"""The whole summary of a notification that gives no status and says its
agent was resumed by another agent, which its completion reaches instead."""
BACKGROUND_TASK = "backgroundTaskId"
"""The key of the result of a Bash call that runs in the background, which
gives that call's task id."""
OUTPUT_FILE = re.compile(r"Output is being written to: (\S+?)\.?(?:\s|$)")
"""The text of a tool result that names the file a command that runs in the
background writes its output to."""


def member[E: Enum](kind: type[E], value: object) -> E | None:
    return next((m for m in kind if m.value == value), None)


class Status(Enum):
    """The statuses the harness gives a notification."""
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"
    STOPPED = "stopped"
    RUNNING = "running"


class LaunchStatus(Enum):
    """The statuses the harness gives the result of an Agent call."""
    ASYNC_LAUNCHED = "async_launched"
    """The agent runs in the background."""
    COMPLETED = "completed"
    """The agent ran in the foreground and reported."""


def launch_status(result: dict[str, Any], undecided: list[str],
                  call: str) -> LaunchStatus | None:
    """The status of `result`, the result of the Agent call `call`. A status
    of no known form gives an `undecided` line that names only the call, so
    a result that several readers read gives one line."""
    status = member(LaunchStatus, result.get("status"))
    if status is None:
        undecided.append(mctx("Agent call {call}: its result gives the status "
                              "`{status}`, of no known form").format(
            call=call, status=result.get("status")))
    return status


def in_background(result: dict[str, Any], undecided: list[str], call: str) -> bool:
    """Whether `result`, the result of the Agent call `call`, says the agent
    runs in the background. A status of no known form counts as not."""
    return launch_status(result, undecided, call) is LaunchStatus.ASYNC_LAUNCHED


@dataclass
class Notification:
    """A notification the harness gives a run: the task id and tool-use id
    it names, its status as it words it, its note, its result and its
    summary, each None where it gives none."""
    ids: list[str]
    status_text: str | None
    note: str | None
    result: str | None
    summary: str | None

    @property
    def resumed_elsewhere(self) -> bool:
        """Whether it is of the form `RESUMED_ELSEWHERE` gives, which gives
        no report and no stop."""
        return (self.status_text is None and self.summary is not None
                and RESUMED_ELSEWHERE.match(self.summary.strip()) is not None)

    @property
    def status(self) -> Status | None:
        """Its status, or None where it gives none or one of no known form."""
        return member(Status, self.status_text)


def read_meta(path: Path) -> dict[str, Any] | None:
    """The `.meta.json` of the run of the subagent whose transcript is at
    `path`: each key as the earliest of its transcripts' `.meta.json` files
    that gives the key gives it, or None where none of them has one."""
    metas = [m for p in chain(path) if (m := transcript_meta(p)) is not None]
    if not metas:
        return None
    out: dict[str, Any] = {}
    for meta in reversed(metas):
        out.update(meta)
    return out


@state_cache(DERIVED, kept=Kept.DISK)
def agent_type(path: Path) -> str | None:
    """The agent type of the run whose transcript is at `path`: `main` for a
    session's main transcript, and for a subagent's, the type its
    `.meta.json` gives (`read_meta`), or None where it gives none. A
    transcript whose first entry answers no entry is the first of its run
    (`transcripts.chain`), so where its own `.meta.json` gives a type, that
    is the run's, and the search of every session for the run's other
    transcripts is spared."""
    if not is_subagent(path):
        return MAIN
    own = (transcript_meta(path) or {}).get("agentType")
    if own is None or first_parent(path) is not None:
        own = (read_meta(path) or {}).get("agentType")
    return own if isinstance(own, str) else None


def subagent_meta(path: Path) -> dict[str, Any]:
    """The `.meta.json` of the subagent whose transcript is at `path`, which
    must give its agent type (`agent_type`)."""
    meta = read_meta(path)
    if meta is None or agent_type(path) is None:
        raise Refused(UNKNOWN_TYPE.format(path=path))
    return meta


def run_type(path: Path) -> tuple[str, str]:
    kind = agent_type(path)
    if kind is None:
        raise Refused(UNKNOWN_TYPE.format(path=path))
    return kind, (read_meta(path) or {}).get("description", "")


def meta_parent(meta: dict[str, Any]) -> str:
    """The agent id of the parent of the agent whose `.meta.json` is
    `meta`, or `main`, which it gives by naming no parent."""
    return meta.get("parentAgentId") or MAIN


def parent_id(path: Path) -> str:
    """The parent of the agent whose transcript is at `path`
    (`meta_parent`)."""
    return meta_parent(subagent_meta(path))


def run_entries(path: Path, naming: set[str] | None = None) -> Iterator[Entry]:
    """The entries of the run of the agent whose transcript is at `path`,
    across its transcripts, or with `naming` only those `read_entries`
    gives with it, each line parsed only when it is reached."""
    return (e for p in chain(path) for e in read_entries(p, naming=naming))


def text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
    return ""


PERSISTED = "<persisted-output>"
"""What opens the content of a tool result the harness cut to a preview of
an output too large to give in full."""


def result_text(block: dict[str, Any], result: Any) -> str:
    """The text of the `tool_result` block `block`, whose entry gives
    `result` as its `toolUseResult`: its content, or the result's `stdout`
    where that content is a `PERSISTED` preview and the result gives one.
    The content holds stderr lines that `stdout` leaves out."""
    text = text_of(block.get("content"))
    out = result.get("stdout") if isinstance(result, dict) else None
    return out if text.startswith(PERSISTED) and isinstance(out, str) else text


def tool_results(entry: Entry) -> list[tuple[str, dict[str, Any], str]]:
    """Each `tool_result` block of `entry`, with the id of the call it
    answers and its text (`result_text`)."""
    if entry.get("type") != "user":
        return []
    result = entry.get("toolUseResult")
    return [(b.get("tool_use_id", ""), b, result_text(b, result))
            for b in blocks(entry, "tool_result")]


def output_file(block: dict[str, Any]) -> Path | None:
    """The file the `tool_result` block `block` names as the one its
    command writes its output to, or None where it names none."""
    m = OUTPUT_FILE.search(text_of(block.get("content")))
    return Path(m.group(1)) if m else None


def results_by_call(entries: Iterable[Entry]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for e in entries:
        r = e.get("toolUseResult")
        if e.get("type") != "user" or not isinstance(r, dict):
            continue
        for b in blocks(e, "tool_result"):
            out[b.get("tool_use_id", "")] = r
    return out


def session_of(path: Path) -> Path:
    """The session directory a transcript belongs to."""
    session = path.parents[1] if is_subagent(path) else session_directory(path)
    while is_subagent(session):
        session = session.parent
    return session


def run_sessions(path: Path) -> list[Path]:
    """The sessions of the transcripts of the run at `path`, in their
    order."""
    return list(dict.fromkeys(session_of(p) for p in chain(path)))

@state_cache(DERIVED)
def session_agents(session: Path) -> dict[str, Path]:
    return {agent: paths[-1] for agent, paths in session_agent_transcripts(session).items()}


def type_in(sessions: Iterable[Path], agent: str) -> str | None:
    """The type of the agent `agent` (`agent_type`), from its transcript
    under the first of `sessions` that holds one, or None where none does
    or that transcript gives no type."""
    path = next((p for s in sessions if (p := session_agents(s).get(agent))), None)
    return agent_type(path) if path else None


def caller_id(hook: dict[str, Any]) -> str | None:
    """The agent id of the caller of the hook input `hook`, or None where
    the caller is the main session: the input of a call inside a subagent
    gives the subagent's agent id, and the main session's gives none."""
    return hook.get("agent_id") or None


def hook_session(hook: dict[str, Any]) -> Path:
    return session_of(Path(hook["transcript_path"]))


def caller_transcript(hook: dict[str, Any]) -> Path:
    """The transcript of the caller of the hook input `hook`, under its
    session (`hook_session`, `caller_id`). Raises `ValueError` where the
    session holds no transcript of the caller."""
    session = hook_session(hook)
    caller = caller_id(hook)
    if caller is None:
        return main_transcript(session)
    path = session_agents(session).get(caller)
    if path is None:
        raise ValueError(f"no transcript of agent {caller} under {session}")
    return path


def session_transcripts(session: Path) -> list[Path]:
    """The transcripts of `session`: its main transcript, where it has one,
    and those of its subagents."""
    main = main_transcript(session)
    return [*([main] if is_file(main) else []), *session_agents(session).values()]


def entry_input(entry: Entry) -> int | None:
    """The input tokens of the request an assistant entry answers, or None
    where the entry gives no usage or no count."""
    usage = (entry.get("message") or {}).get("usage")
    if not isinstance(usage, dict):
        return None
    return int(request_input(usage)) or None


def context_size(entries: Iterable[Entry]) -> int | None:
    """The context of a run whose entries are given last first: the input
    tokens of its latest request, or None where no assistant entry gives a
    count."""
    return next((t for e in entries if e.get("type") == "assistant"
                 and (t := entry_input(e)) is not None), None)


def is_prompt(entry: Entry) -> bool:
    """Whether an entry gives the model a message: a user entry that answers
    no tool call, a user entry that holds a text block outside its
    `tool_result` blocks, such as a fork's directive, or a message queued
    while the model worked."""
    if entry.get("type") == "attachment":
        return (entry.get("attachment") or {}).get("type") == "queued_command"
    return entry.get("type") == "user" and (not blocks(entry, "tool_result")
                                            or bool(blocks(entry, "text")))


def message_text(entry: Entry) -> str:
    """The text of a user entry, or of a message queued while the model
    worked."""
    if entry.get("type") == "attachment":
        a = entry.get("attachment") or {}
        return text_of(a.get("prompt")) if a.get("type") == "queued_command" else ""
    return text_of((entry.get("message") or {}).get("content"))


def field_text(body: str, name: str) -> str | None:
    m = re.search(rf"<{name}>(.*?)</{name}>", body, re.S)
    return m.group(1) if m else None


def notifications(entry: Entry) -> list[Notification]:
    out: list[Notification] = []
    for body in NOTIFICATION.findall(message_text(entry)):
        status = field_text(body, "status")
        out.append(Notification([v for _, v in TAG.findall(body)],
                                status and status.strip(), field_text(body, "note"),
                                field_text(body, "result"), field_text(body, "summary")))
    return out


def agent_messages(entry: Entry) -> list[tuple[str, str]]:
    """The agent id of the sender and the text of each message from an
    agent that `entry` gives."""
    text = message_text(entry)
    out: list[tuple[str, str]] = []
    for m in AGENT_MESSAGE.finditer(text):
        start = text.find(">", m.end()) + 1
        end = text.find(AGENT_MESSAGE_END, start)
        out.append((m.group(1), text[start:end if end >= 0 else None].strip()))
    return out


def notified(entry: Entry) -> list[str]:
    return [v for n in notifications(entry) for v in n.ids]


def parent_label(path: Path) -> str:
    return agent_id(path) if is_subagent(path) else MAIN



REFUSALS = ("Permission for this action was denied", "The user doesn't want to proceed",
            "PreToolUse:", "Blocked:", "<tool_use_error>Blocked:")
"""The openings of the result of a call the harness, the permission
classifier, the user or a hook refused."""


def refused_at(entries: list[Entry]) -> list[float]:
    """The times of the results of `entries` that give a refused call."""
    return [epoch(e["timestamp"]) for e in entries if e.get("timestamp")
            for b in blocks(e, "tool_result") if b.get("is_error")
            and result_text(b, e.get("toolUseResult")).lstrip().startswith(REFUSALS)]


def tool_calls(entries: Iterable[Entry], names: Collection[str]) -> set[str]:
    """The ids of the calls of `entries` whose tool is one of `names`."""
    return {str(b.get("id")) for e in entries if e.get("type") == "assistant"
            for b in blocks(e, "tool_use") if b.get("name") in names}


class Called(Protocol):
    call: str


def bash_ids(entries: Iterable[Entry]) -> set[str]:
    """The ids of the Bash calls of `entries`."""
    return tool_calls(entries, ("Bash",))


def bash_spans[S: Called](spans: Iterable[S], bash: Collection[str]) -> list[S]:
    """The spans of `spans` whose call is one of `bash`, ids of Bash calls
    (`bash_ids`)."""
    return [s for s in spans if s.call in bash]


WAIT_LEAD = ": 'unattended-wait:"
"""The lead of a command that waits, whose repeats count as no repeated
command."""


def repeated_runs(calls: list[tuple[str, str, float]], texts: Mapping[str, str],
                  least: int) -> list[float]:
    """The time of the last call of each run of `least` or more consecutive
    calls of `calls`, each a Bash call's id, command and start, with the same
    command and the same result text in `texts`, the text of each result by
    its call (`result_texts`), other than a command led by `WAIT_LEAD`, a call
    whose result ends with `POLL_AGAIN`, and a call with no result."""
    keys = [None if given is None or command.lstrip().startswith(WAIT_LEAD)
            or given[1].strip().endswith(POLL_AGAIN) else given
            for (_, command, _), given in zip(calls, call_keys(calls, texts))]
    return [calls[last][2] for first, last in key_runs(keys) if last - first + 1 >= least]


def key_runs[K](keys: Sequence[K | None]) -> list[tuple[int, int]]:
    """The first and last index of each run of equal consecutive keys of
    `keys`, in order, None being in no run."""
    out: list[tuple[int, int]] = []
    for i, k in enumerate(keys):
        if k is None:
            continue
        if out and out[-1][1] == i - 1 and keys[i - 1] == k:
            out[-1] = (out[-1][0], i)
        else:
            out.append((i, i))
    return out


def result_texts(entry: Entry, calls: Collection[str]) -> dict[str, str]:
    """The text of each result of `entry` to a call of `calls`, by its
    call."""
    return {cid: text for cid, _, text in tool_results(entry) if cid in calls}


def call_keys(calls: list[tuple[str, str, float]],
              texts: Mapping[str, str]) -> list[tuple[str, str] | None]:
    """The command and result text of each call of `calls`, as
    `repeated_runs` takes them, or None for a call with no result."""
    return [(command, texts[cid]) if cid in texts else None for cid, command, _ in calls]


def same_since(calls: list[tuple[str, str, float]], texts: Mapping[str, str]) -> float | None:
    """The start of the first call of the last run of calls of `calls`, as
    `repeated_runs` takes them, with the same command and the same result
    text, a command led by `WAIT_LEAD` included, where that run holds two
    calls or more, and None otherwise."""
    runs = key_runs(call_keys(calls, texts))
    if not runs or runs[-1][1] != len(calls) - 1 or runs[-1][0] == runs[-1][1]:
        return None
    return calls[runs[-1][0]][2]


def caller_type(hook: str, data: dict[str, Any]) -> tuple[Path, str | None]:
    """The transcript of the caller of the hook input `data`, and its agent
    type, or None where it is unknown, which the hook `hook` says on stderr
    with an `allowed:` line."""
    path = caller_transcript(data)
    kind = agent_type(path)
    if kind is None:
        print(f"{hook}: allowed: {UNKNOWN_TYPE.format(path=path)}", file=sys.stderr)
    return path, kind
