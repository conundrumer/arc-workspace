"""The record of the calls the `operations` mod made for a loop: one JSON
line per call, with
the key of the step it made, written by `operate.py made` and read back
into the state's calls, made steps and launched agents. The result of a
recorded Agent call is a JSON object whose `agentId` gives the agent the
call launched. The coordinator's lines reach the loop through
`operate.py tell`, as entries of the same record with a `line` in place of
a `tool`, and `operate.py start` and `operate.py stop` mark in the
operations loop's record each start and stop of that loop, which the
monitor reads as the loop's runs; the messages of the agents the loop
launched reach the main session, and are read from its transcript."""

import json
import time
from enum import StrEnum
from pathlib import Path
from typing import Any

from agent_launches import sent_to
from agent_turns import has_ended
from filed_texts import unfiled
from loop_reads import final_reply, merge_outcome, pass_tickets, unfiled_call
from run_reads import agent_messages, is_prompt, run_entries
from transcripts import Refused, epoch, find

from controlled_markdown import mctx
from operations.constants import COORDINATOR
from operations.monitor import Run
from operations.roles import PASSES, Role, described
from operations.state import Agent, Call, Made, Message, Printed
from operations.steps import unfenced

RECORDS = "operations"
"""The directory under the session's scratchpad that holds the records."""

LOOP = "ops"
"""The id of the session's one operations loop, which `operate.py`
takes."""

MONITOR = "ops-monitor"
"""The id of the session's one monitor loop, which `monitor.py` takes in
place of a monitor's agent id."""


def holder(session: str) -> str:
    """The id by which the operations loop of `session` holds a ticket
    (`operations.roles.LOOP_HOLDER`)."""
    return f"{LOOP}-{session}"


def is_loop(me: str) -> bool:
    return me in (LOOP, MONITOR)


class Mark(StrEnum):
    """The key of an entry that marks a start or a stop of a loop, written
    as `{"<mark>": true}`. A monitor record may hold a `start` entry, which
    marks no run."""
    START = "start"
    STOP = "stop"


def mark(scratch: Path, loop: str, m: Mark) -> None:
    write(scratch, loop, {m: True})


def runs(scratch: Path) -> list[Run]:
    """The runs of the operations loop that its record's marks give, in
    order. A stop where no run is open is a fault of the record."""
    out: list[Run] = []
    for e in raw_entries(scratch, LOOP):
        t = float(e["time"])
        if e.get(Mark.START) is True:
            out.append(Run(t, None, t))
        elif e.get(Mark.STOP) is True:
            if not out or out[-1].stop is not None:
                raise Refused(mctx("{path}: a stop at {time} ends no run").format(
                    path=record_path(scratch, LOOP), time=t))
            out[-1] = Run(out[-1].start, t, out[-1].last)
    calls = [float(e["time"]) for loop in (LOOP, MONITOR) for e in entries(scratch, loop)
             if "tool" in e]
    ends = [r.start for r in out[1:]] + [float("inf")]
    return [Run(r.start, r.stop, max([r.last, *(t for t in calls if r.start <= t < end)]))
            for r, end in zip(out, ends, strict=True)]


TOOLS = frozenset({"Agent", "SendMessage", "Bash"})
"""The tools whose calls the mod makes, by the names the harness gives them."""


def record_path(scratch: Path, loop: str) -> Path:
    return scratch / RECORDS / f"{loop}.jsonl"


def append(scratch: Path, loop: str, entry: dict[str, Any]) -> None:
    """Add the call or the coordinator's line `entry` to the record of
    `loop`, stamped with the time it is written."""
    if not (isinstance(entry.get("line"), str)
            or entry.get("tool") in TOOLS and isinstance(entry.get("input"), dict)):
        raise Refused(mctx("a recorded entry takes a line, or a tool of the mod's and an "
                           "input object"))
    write(scratch, loop, entry)


def write(scratch: Path, loop: str, entry: dict[str, Any]) -> None:
    path = record_path(scratch, loop)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps({**entry, "time": time.time()}) + "\n")


def raw_entries(scratch: Path, loop: str) -> list[dict[str, Any]]:
    """Each entry of the record of `loop`, marks included, in the order
    written."""
    path = record_path(scratch, loop)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines()]


def entries(scratch: Path, loop: str) -> list[dict[str, Any]]:
    """The calls and the coordinator's lines in the record of `loop`, in the
    order written; an entry that is neither and no mark is a fault of the
    record."""
    path = record_path(scratch, loop)
    out: list[dict[str, Any]] = []
    for n, e in enumerate(raw_entries(scratch, loop), 1):
        if any(e.get(m) is True for m in Mark):
            continue
        if not (isinstance(e.get("line"), str)
                or e.get("tool") in TOOLS and isinstance(e.get("input"), dict)):
            raise Refused(mctx("{path}:{n} is no entry of the mod's").format(path=path, n=n))
        out.append(e)
    return out


def launched(scratch: Path, loop: str) -> set[str]:
    """The agent ids of the agents the record of `loop` gives as launched."""
    return {launched_id(e.get("result"), float(e["time"]))
            for e in entries(scratch, loop) if e.get("tool") == "Agent"}


def launched_id(result: str | None, time: float) -> str:
    """The agent id the result of a recorded launch at `time` gives; a
    launch whose result gives none is a fault of the record."""
    aid = json.loads(result or "{}").get("agentId")
    if not isinstance(aid, str):
        raise Refused(mctx("the recorded launch at {time} gives no agent id").format(time=time))
    return aid


def read_record(scratch: Path, loop: str, owner: str, subjects: dict[str, float],
                undecided: list[str]) -> tuple[list[Call], list[Made], list[Message]]:
    """The calls in the record of `loop`, as calls of `owner`, in the order
    written, each with
    the file the command wrote for it read in place of the line that gives
    it (`loop_reads.unfiled_call`), and with what a merge call did, by
    `subjects`, the time of the latest commit of `master` with each subject
    (`loop_reads.merge_outcome`); the steps among them that a
    SendMessage or a Bash call made; and the coordinator's lines."""
    calls: list[Call] = []
    made: list[Made] = []
    lines: list[Message] = []
    for e in entries(scratch, loop):
        if isinstance(e.get("line"), str):
            lines.append(Message(owner, float(e["time"]), None, e["line"]))
            continue
        tool, inp = e["tool"], e["input"]
        t, error = float(e["time"]), bool(e.get("error"))
        inp, result = unfiled_call(owner, tool, inp, e.get("result"), undecided)
        c = Call(owner, t, tool, inp, result, error, merge_outcome(
            owner, str(inp.get("command", "")) if tool == "Bash" else "", t, result, error,
            subjects, undecided))
        calls.append(c)
        key = e.get("key")
        if tool == "SendMessage":
            made.append(Made(key, Printed.SEND_MESSAGE, str(inp["to"]), str(inp["message"]), c))
        elif tool == "Bash":
            made.append(Made(key, Printed.BASH, None, str(inp["command"]), c))
    return calls, made, lines


def record_messages(owner: str, scratch: Path, session: str, agents: list[Agent],
                    undecided: list[str]) -> list[Message]:
    """The messages that reached the operations loop `owner`: those that the agents in `agents`,
    and the auditors the monitor loop launched, sent the main session, and
    the monitor loop's messages to the coordinator, which its record keeps
    for the operations loop, from `MONITOR`."""
    ids = {a.agent_id for a in agents if a.agent_id} | launched(scratch, MONITOR)
    where = mctx("{run}: a message from").format(run=owner)
    sent = [Message(owner, epoch(stamp), s, unfiled(unfenced(text), f"{where} {s}", undecided))
            for e in run_entries(find(session)) if is_prompt(e) and (stamp := e.get("timestamp"))
            for s, text in agent_messages(e) if s in ids]
    return sent + [Message(owner, float(e["time"]), MONITOR, str(e["input"]["message"]))
                   for e in entries(scratch, MONITOR)
                   if e.get("tool") == "SendMessage" and e["input"].get("to") == COORDINATOR]


def record_agents(calls: list[Call], main: Path,
                  passes: dict[str, tuple[str, ...] | None]) -> list[Agent]:
    """The agents the Agent calls among `calls` launched with a description
    the command gave, each pending until its transcript gives its turn
    ended, with the final reply in that transcript as its report, and, for
    a solver pass with a report, the tickets its report lists in `passes`
    (`loop_reads.pass_tickets`). A launch whose result gives no agent
    id is a fault of the record."""
    out: list[Agent] = []
    for c in calls:
        if c.tool != "Agent" or (d := described(str(c.input.get("description", "")))) is None:
            continue
        aid = launched_id(c.result, c.time)
        try:
            path = find(aid)
        except Refused:
            # The harness writes a launched agent's transcript after its launch.
            path = None
        reply = final_reply(path) if path is not None else None
        out.append(Agent(aid, c.loop, d.role, d.subject, str(c.input.get("prompt", "")),
                         c.time, path is None or not has_ended(path),
                         (reply,) if reply else (), notifies=True,
                         messaged=sent_to(path) if d.role is Role.DOC_REVIEWER and path
                         else None))
        if d.role in PASSES and reply is not None:
            passes[aid] = pass_tickets(reply.text, main)
    return out
