"""Codex assignments, execution evidence and validated reports.

Enrolled identities are projected from the session's registered ticket stores.
Their own rollouts supply execution and usage; current validator receipts supply
reports. Launcher command results remain readable for unenrolled calls.

A `codex_agent.py` call is a launch where `codex_agent.work_args` gives its
arguments; a call it refuses runs no turn. A launch with an argument the shell
expands, or with a relative scratch directory, cannot be read.

The launcher's calls locate the scratch directory. Calls need records in
order, except that a killed process with no record in its interval
may be followed by a recorded resume in the same directory. Failed attempts
before session creation contribute no walk. A fresh-call refusal proved by
its tool result permits a retry in a new directory before any call is accepted.
Once a session exists, records must match codex-session, and the latest turn must have completed.
Missing or unreadable evidence refuses handback once for each launch call, so a repeated handback with no new launch is allowed.
The results are given in the transcript form the checklist hook reads.
"""

import json
import re
import shlex
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import codex_agent
from codex_agent import BUSY_REFUSAL, FRESH_REFUSAL
from command_labels import segment_program, simple_commands
from run_reads import blocks, is_prompt

from operations.roles import GENERAL, Role
from codex_ticket import Assignment
from state_reads import DERIVED, state_cache


@dataclass(frozen=True)
class Native:
    store: Path
    manifest: Path
    assignment: Assignment
    state: dict[str, Any]


_native_sessions: dict[str, Path] = {}


def rollout_message(row: dict[str, Any]) -> tuple[str, str] | None:
    payload = row["payload"]
    kind = payload.get("type")
    if row.get("type") == "response_item" and kind == "message":
        return payload["role"], "\n".join(part["text"] for part in payload["content"] if "text" in part)
    if row.get("type") == "event_msg":
        if kind in ("user_message", "agent_message"):
            return ("user" if kind == "user_message" else "assistant"), payload["message"]
        item = payload.get("item", {})
        if kind == "item_completed" and item.get("type") in ("UserMessage", "AgentMessage"):
            return ("user" if item["type"] == "UserMessage" else "assistant"), "\n".join(
                part["text"] for part in item["content"] if "text" in part)
    return None


def native_assignments(session_scratch: Path | None = None, *, include_history: bool = False) -> list[Native]:
    """One projection of enrolled operations identities and their current turns."""
    from ticket_numbers import session_id
    from tree_reads import scratch

    directory = (session_scratch or scratch(session_id())) / "codex-stores"
    return list(native_projection(directory, include_history))


@state_cache(DERIVED)
def native_projection(directory: Path, include_history: bool) -> tuple[Native, ...]:
    """The projection of the stores in `directory`, read once per state."""
    import codex_ticket
    from file_reads import stat_read

    stat_read(directory)
    result = []
    for pointer in sorted(directory.glob("*.json")):
        stat_read(pointer)
        store = Path(json.loads(pointer.read_text())["store"])
        stat_read(store / "state.json")
        state = json.loads((store / "state.json").read_text())
        records = list(state["agents"].items())
        if include_history:
            records += [(item["agent"], item) for item in state.get("history", [])]
        for agent, item in records:
            manifest = store / "assignments" / f"{agent}-{item['revision']}.json"
            stat_read(manifest)
            assignment = codex_ticket.Assignment.read(manifest)
            stat_read(assignment.brief)
            stat_read(assignment.report)
            if (assignment.agent != agent or assignment.operator != state["operator"]
                    or assignment.ticket != state["ticket"]):
                raise ValueError("native assignment differs from its store")
            result.append(Native(store, manifest, assignment, item))
            _native_sessions[agent] = directory.parent
    unique = {(item.assignment.agent, item.assignment.revision): item for item in result}
    if len(unique) != len(result):
        raise ValueError("native operations identity occurs in more than one store")
    return tuple(sorted(result, key=lambda item: (item.state["reserved"],
        item.assignment.subject or item.assignment.ticket, item.assignment.role.value, item.assignment.revision)))


def native_find(agent: str, session_scratch: Path | None = None) -> Native | None:
    if session_scratch is None and agent in _native_sessions:
        session_scratch = _native_sessions[agent]
    return next((item for item in native_assignments(session_scratch)
                 if item.assignment.agent == agent), None)


def native_turn(item: Native, home: Path | None = None):
    import codex_rollout
    from file_reads import stat_read

    thread, turn = item.state["native"], item.state["turn"]
    if thread is None or turn is None:
        raise ValueError("native submission has no accepted turn")
    path = codex_rollout.rollout_path(thread, home or Path.home())
    stat_read(path)
    found = [value for value in codex_rollout.read_turns(path) if value.turn == turn]
    if len(found) != 1:
        raise ValueError("native assignment has no unique rollout turn")
    return found[0]


def native_execution(assignment: Assignment, state: dict[str, Any], home: Path) -> tuple[list[dict[str, Any]], str]:
    """Read commands, inputs and the final reply from this assignment's own turn."""
    from codex_ticket import Binding
    import codex_rollout

    turn = native_turn(Native(Path(), Path(), assignment, state), home)
    entries: list[dict[str, Any]] = [{"type": "user", "uuid": str(assignment.revision),
        "timestamp": datetime.fromtimestamp(turn.started).astimezone().isoformat(),
        "message": {"content": assignment.brief.read_text()}}]
    binding = Binding.read(assignment.scratch)
    history = []
    if binding is not None:
        store_state = json.loads((binding.store / "state.json").read_text())
        accepted = {item["turn"] for item in store_state.get("history", [])
                    if item["agent"] == assignment.agent and item["native"] == state["native"]}
        history = [old for old in codex_rollout.turns(state["native"], home) if old.turn in accepted]
    entries = [entry for old in history for entry in live_commands(old.activity, include_prompts=True)] + entries
    entries.extend(live_commands(turn.activity, include_prompts=True))
    reply = ""
    for row in turn.activity:
        payload = row["payload"]
        message = rollout_message(row)
        if message is not None and message[0] == "assistant":
            reply = message[1]
        if payload.get("type") == "task_complete" and isinstance(payload.get("last_agent_message"), str):
            reply = payload["last_agent_message"]
        elif (row.get("type") == "response_item" and payload.get("type") == "message"
              and payload.get("role") == "assistant" and payload.get("phase") == "final"):
            reply = "\n".join(part["text"] for part in payload["content"] if "text" in part)
        elif row.get("type") == "event_msg" and payload.get("type") == "agent_message":
            reply = payload["message"]
    return entries, reply


def native_shell_call(payload: dict[str, Any]) -> str | None:
    """Read one literal shell call from a native tool invocation; refuse code expressions."""
    if payload.get("type") == "function_call" and payload.get("name") in ("exec_command", "functions.exec_command"):
        return json.loads(payload["arguments"])["cmd"]
    if payload.get("type") != "custom_tool_call" or payload.get("name") != "exec":
        return None
    found = re.fullmatch(r"\s*(?:text\(\s*)?await tools\.exec_command\(\s*(\{.*\})\s*\)\s*\)?\s*;?\s*",
                         payload["input"], re.S)
    if found is None:
        return None
    source = found[1]
    position = 1
    values = {}
    decoder = json.JSONDecoder()
    while True:
        key = re.match(r'\s*(?:"([a-z_]+)"|([a-z_]+))\s*:\s*', source[position:])
        if key is None:
            return None
        name = key[1] or key[2]
        if name in values or name not in {"cmd", "workdir", "yield_time_ms", "max_output_tokens", "login", "tty"}:
            return None
        position += key.end()
        try:
            value, end = decoder.raw_decode(source[position:])
        except ValueError:
            return None
        values[name] = value
        position += end
        tail = re.match(r"\s*([,}])\s*", source[position:])
        if tail is None:
            return None
        position += tail.end()
        if tail[1] == "}":
            return values.get("cmd") if position == len(source) and isinstance(values.get("cmd"), str) else None


def native_receipt(item: Native, home: Path | None = None):
    """Revalidate the current report bytes and terminal execution on every read."""
    from codex_reports import Evidence, Outcome, Validated, validate
    from codex_ticket import Phase, Terminal
    from codex_reconcile import matching_input
    from codex_rollout import TurnEnd

    if (not item.state["validated"] or item.state["phase"] != Phase.ENDED
            or item.state.get("status") != Terminal.COMPLETED):
        return None
    turn = native_turn(item, home)
    if turn.ended is None or turn.end_state is not TurnEnd.COMPLETE:
        raise ValueError("receipt has no terminal rollout evidence")
    matching_input(item.assignment, item.manifest, turn)
    value = dict(item.state["receipt"])
    value["manifest"] = Path(value["manifest"])
    value["outcome"] = Outcome(value["outcome"])
    previous = Validated(**value)
    entries, reply = native_execution(item.assignment, item.state, home or Path.home())
    return validate(item.manifest, reply, Evidence(item.assignment.agent, item.assignment.revision,
                    item.assignment.inputs_digest, entries), previous.outcome, previous)


def native_agents(owner: str, session_scratch: Path | None = None,
                  home: Path | None = None):
    """Assemble launches and validated reports for the existing operations joins."""
    from operator_reads import AgentsRead
    from operations.state import Agent, Report, Waits
    from codex_reports import Outcome
    from codex_ticket import Phase

    agents = []
    messaged: dict[str, frozenset[str]] = {}
    items = native_assignments(session_scratch)
    by_native = {item.state["native"]: item.assignment.agent for item in items if item.state["native"]}
    by_native.update({item.state["runtime"]: item.assignment.agent for item in items if item.state.get("runtime")})
    launched: dict[str, float] = {}
    for item in native_assignments(session_scratch, include_history=True):
        launched[item.assignment.agent] = min(item.state["reserved"],
                                              launched.get(item.assignment.agent, item.state["reserved"]))
    for item in items:
        assignment, state = item.assignment, item.state
        parent = state["parent"] or assignment.operator
        if parent != owner:
            continue
        reports = ()
        try:
            receipt = native_receipt(item, home)
            dispatch = assignment.scratch / "codex-dispatch.json"
            if (receipt is not None and receipt.outcome is not Outcome.FINISHED
                    and dispatch.exists() and json.loads(dispatch.read_text()).get("call")):
                receipt = None
            if receipt is not None:
                reports = (Report(assignment.report.stat().st_mtime, assignment.report.read_text(), assignment.report),)
        except (OSError, ValueError, KeyError, StopIteration):
            receipt = None
        reviewing = native_reviewing(item, home) if assignment.role in (Role.CODE_EDITOR, Role.DOC_EDITOR) else None
        agents.append(Agent(assignment.agent, parent, assignment.role,
            assignment.subject or assignment.ticket, assignment.brief.read_text(),
            launched[assignment.agent], state["reserved"],
            None if receipt or state["phase"] == Phase.ENDED else Waits.AT_WORK,
            reports, True, report_file=(assignment.report if receipt is not None
                or assignment.role in (Role.CODE_EDITOR, Role.DOC_EDITOR) else None), reviewing=reviewing))
        try:
            messaged[assignment.agent] = native_sent(item, by_native, home)
        except (OSError, ValueError, KeyError):
            messaged[assignment.agent] = frozenset()
    return AgentsRead(tuple(agents), messaged, {})


def native_reviewing(item: Native, home: Path | None = None) -> float | None:
    """Count an editor's own isolated review command, including its live call."""
    from operations.command_words import Action, is_next

    try:
        turn = native_turn(item, home)
    except (OSError, ValueError, KeyError):
        return None
    first = None
    for row in turn.activity:
        payload = row["payload"]
        if row.get("type") != "response_item" or payload.get("type") not in ("function_call", "custom_tool_call"):
            continue
        command = native_shell_call(payload)
        if command is not None:
            if is_next(command, item.assignment.agent, Action.REVIEW):
                first = first or timestamp(row)
                continue
        first = None
    return first


def native_sent(item: Native, identities: dict[str, str], home: Path | None = None) -> frozenset[str]:
    """Recipients of successful native messages in the sender's own rollout."""
    pending = {}
    sent = set()
    for row in native_turn(item, home).activity:
        payload = row["payload"]
        if row.get("type") != "response_item":
            continue
        if (payload.get("type") == "function_call"
                and payload.get("name", "").removeprefix("collaboration.") in ("send_message", "followup_task")):
            pending[payload["call_id"]] = json.loads(payload["arguments"])["target"]
        elif payload.get("type") == "function_call_output" and payload["call_id"] in pending:
            output = payload["output"]
            result = (json.loads(output) if output.strip() else None) if isinstance(output, str) else output
            if (result is None or (isinstance(result, dict) and not result.get("error") and not result.get("isError")
                    and (result.get("status") in ("sent", "delivered", "queued", "accepted", "running")
                         or isinstance(result.get("message_id"), str)))):
                target = pending[payload["call_id"]]
                if target in identities:
                    sent.add(identities[target])
    return frozenset(sent)


@dataclass(frozen=True)
class Call:
    """A launcher command's role, scratch directory and transcript interval."""
    role: str
    scratch: Path
    started: float | None
    ended: float | None
    until: float | None
    call_id: str
    transcript: Path | None = None
    work_role: Role | None = None

    @property
    def work_name(self) -> str:
        return self.work_role.value if self.role == GENERAL and self.work_role else self.role


def timestamp(entry: dict[str, Any]) -> float | None:
    value = entry.get("timestamp")
    return datetime.fromisoformat(value).timestamp() if isinstance(value, str) else None


def work_calls(command: str) -> list[tuple[Role, Path, str, bool]]:
    """The role, absolute scratch directory, agent type and resume flag of each
    work call, in order. Raise ValueError where a call cannot be read."""
    found = []
    for words in simple_commands(command):
        program, args = segment_program(words)
        if program != "codex_agent.py":
            continue
        if args and args[0] in codex_agent.CONTROLS:
            continue
        if any("$" in arg or "`" in arg for arg in args):
            raise ValueError(f"the Codex call {shlex.join(args)} has an argument the shell expands")
        ns = codex_agent.work_args(args)
        if ns is None:
            continue
        if not ns.scratch.is_absolute():
            raise ValueError("the Codex scratch directory must be absolute")
        role = Role(ns.agent)
        found.append((role, ns.scratch, ns.agent_type or role.agent_type, ns.resume))
    return found


def launches(entry: dict[str, Any]):
    """Find turn launches: the work calls `work_calls` gives."""
    for block in blocks(entry, "tool_use"):
        if entry.get("type") != "assistant" or block.get("name") != "Bash":
            continue
        for role, directory, agent_type, _ in work_calls(
                str((block.get("input") or {}).get("command", ""))):
            yield block["id"], agent_type, directory, role


def commands(entry: dict[str, Any]):
    for call, kind, directory, _ in launches(entry):
        yield call, kind, directory


def no_turn(entries: list[dict[str, Any]], call: str, scratch: Path) -> bool:
    """Prove no turn from the scratch path or this call's own diagnostics.

    If scratch exists and is not a directory, codex_agent.run reaches no
    transport: a fresh call fails at the latest at scratch.mkdir, and a resume
    at saved_thread's read of codex-session.
    """
    if scratch.exists() and not scratch.is_dir():
        return True
    output = launch_output(entries, call)
    lines = output.removeprefix("Exit code 1\n").splitlines()
    lines = [line for line in lines if line.strip()]
    if lines and lines[-1] == "[exited with code 1]":
        lines.pop()
    if lines and lines[0].startswith("warning: "):
        lines.pop(0)
    if lines and re.fullmatch(
            r"codex_agent: shared daemon (?:unavailable or refused|refused): .*; falling back to codex exec",
            lines[0]):
        lines.pop(0)
    body = "\n".join(lines)
    if body in ("codex_agent: " + FRESH_REFUSAL, "codex_agent: " + BUSY_REFUSAL):
        return True
    failure = re.fullmatch(
        r"codex_agent: launch failed before Codex started \[([0-9a-f]{32})\]: (.*)",
        body, re.S)
    if failure is None:
        return False
    return preparation_interval(scratch, failure) is not None


def preparation_interval(scratch: Path, failure: re.Match[str]) -> tuple[float, float] | None:
    """Validate an identifier-bearing diagnostic against its saved record."""
    path = scratch / "codex-launch-failures.jsonl"
    saved = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    matches = [r for r in saved if r.get("id") == failure[1] and r.get("error") == failure[2]]
    if len(matches) != 1:
        return None
    start, end = matches[0].get("started"), matches[0].get("ended")
    if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or start > end:
        return None
    return start, end



def fresh_refusals(entries: list[dict[str, Any]]):
    refused = set()
    for entry in entries:
        try:
            for call, _, scratch in commands(entry):
                if no_turn(entries, call, scratch):
                    refused.add(call)
        except (OSError, ValueError, KeyError, IndexError):
            continue
    return refused


def calls(entries: list[dict[str, Any]], gaps: list[str] | None = None) -> list[Call]:
    entries = without_hook_refusals(entries)
    ends = {}
    for entry in entries:
        for block in blocks(entry, "tool_result"):
            ends[block.get("tool_use_id")] = timestamp(entry)
    until = max((t for e in entries if (t := timestamp(e)) is not None), default=None)
    refused = fresh_refusals(entries)
    out = []
    for index, entry in enumerate(entries):
        try:
            for call, role, directory, work in launches(entry):
                if call not in refused and not unrecorded_launch(entries, index, call, directory):
                    out.append(Call(role, directory, timestamp(entry), ends.get(call), until,
                                    call, work_role=work))
        except (OSError, ValueError, KeyError, IndexError) as exc:
            if gaps is None:
                raise
            gaps.append(f"launcher entry {index}: {exc}")
    return out


def launch_output(entries: list[dict[str, Any]], call_id: str) -> str:
    """Read only the result tied to this call, including a background log."""
    from run_reads import output_file

    for entry in entries:
        for block in blocks(entry, "tool_result"):
            if block.get("tool_use_id") != call_id:
                continue
            path = output_file(block)
            if path is not None:
                try:
                    return path.read_text().strip()
                except FileNotFoundError:
                    return ""
            content = block.get("content")
            return content.strip() if isinstance(content, str) else ""
    return ""


def unrecorded_launch(entries: list[dict[str, Any]], index: int,
                      call_id: str, scratch: Path, used: int = 0,
                      *, recover_killed: bool = False) -> bool:
    """Require a failed or killed launch and evidence that it owns no turn record.

    Output filters may discard the exit status or most of a traceback. Saved
    preparation failures can instead be bound by their call interval.
    Identifier-bearing diagnostics are decoded only by `no_turn`.
    Otherwise require failure output and an empty scratch or records outside
    this call's interval. Missing records alone never prove a failed launch.
    Saved walks may recover killed processes; accounting retains those calls
    so their missing usage evidence remains visible.
    """
    import re
    from run_reads import output_file

    output = launch_output(entries, call_id)
    if "codex_agent: launch failed before Codex started [" in output:
        return False
    body = output.removeprefix("Exit code 1\n").removesuffix("\n\n[exited with code 1]")
    result = next((b for e in entries for b in blocks(e, "tool_result")
                   if b.get("tool_use_id") == call_id), {})
    start = timestamp(entries[index])
    later = next((timestamp(e) for e in entries[index + 1:]
                  for _, _, directory in commands(e) if directory == scratch), None)
    if recover_killed and re.search(r"(?:^|\n)\[killed\]$", output):
        # A killed launcher may leave its daemon turn running without writing
        # a record. Only a later call in this directory can recover it; that
        # call still has to supply its own readable, completed turn record.
        if start is None or later is None or later <= start:
            return False
        path = scratch / "codex-events.jsonl"
        records = ([json.loads(line) for line in path.read_text().splitlines()]
                   if path.exists() else [])
        # Earlier records belong to earlier launch ids in this same directory.
        return bool(records) and all(isinstance(r.get("started"), (int, float))
                                     and (r["started"] < start or r["started"] >= later)
                                     for r in records)
    end = next((timestamp(e) for e in entries[index + 1:]
                for b in blocks(e, "tool_result") if b.get("tool_use_id") == call_id), None)
    # A background acknowledgement is not the end of preparation. Its next
    # launch (or the transcript's last timestamp) bounds the saved failure.
    if output_file(result) is not None:
        end = max((t for e in entries if (t := timestamp(e)) is not None), default=None)
    bounds = [t for t in (end, later) if t is not None]
    end = min(bounds) if bounds else None
    interval = None
    path = scratch / "codex-launch-failures.jsonl"
    saved = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    if start is not None and end is not None:
        matches = [r for r in saved
                   if isinstance(r.get("started"), (int, float))
                   and isinstance(r.get("ended"), (int, float))
                   and start <= r["started"] <= r["ended"] <= end]
        if len(matches) == 1:
            interval = matches[0]["started"], matches[0]["ended"]

    # Filters may leave just a terminal exception, and a pipeline may
    # report success despite it. Explicit evidence of turn execution still
    # refuses: its missing record cannot be explained by preparation.
    frames = re.findall(r'^  File "([^"\n]+)", line \d+, in (\S+)\n    ([^\n]+)',
                        body, re.M)
    executing = any(Path(p).name == "codex_agent.py" and (
        f in ("daemon_turn", "execute", "usage_record")
        or (f == "run" and re.search(r"\b(?:daemon_turn|runner|usage_record)\(", code)))
        for p, f, code in frames)
    executing = executing or bool(re.search(
        r'"type"\s*:\s*"(?:thread\.started|turn\.(?:started|completed|failed)|item\.completed)"'
        r'|codex_agent: (?:daemon turn failed|codex exec exited)', output))
    failed = (result.get("is_error") is True
              or re.search(r"(?:^Exit code [1-9]\d*\n|\[exited with code [1-9]\d*\]$)", output)
              or re.search(r"(?:^|\n)(?:\w+\.)*\w*(?:Error|Exception): [^\n]+$", body))
    if interval is None and (executing or not failed):
        return False

    block = next(b for b in blocks(entries[index], "tool_use") if b.get("id") == call_id)
    launches = work_calls(str((block.get("input") or {}).get("command", "")))
    if len(launches) != 1:
        raise ValueError("the failed Bash call contains more than one Codex launch")
    if interval is None and launches[0][3]:
        return False
    path = scratch / "codex-events.jsonl"
    records = ([json.loads(line) for line in path.read_text().splitlines()]
               if path.exists() else [])[used:]
    if not records:
        return used > 0 or not (scratch / "codex-session").exists()
    if start is None or later is None or later <= start:
        return False
    return all(isinstance(r.get("started"), (int, float)) and r["started"] >= later
               for r in records)


def without_hook_refusals(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove Bash calls the harness says a PreToolUse hook prevented.

    No part of such a call ran, so even parsing its launch arguments or
    using it to bound another call's turn would give it an effect it had not.
    The diagnostic after the harness prefix belongs to the refusing hook.
    """
    refused = {b.get("tool_use_id") for entry in entries if entry.get("type") == "user"
               for b in blocks(entry, "tool_result")
               if b.get("is_error") is True and isinstance(b.get("content"), str)
               and b["content"].startswith("PreToolUse:Bash hook error:")}
    out = []
    for entry in entries:
        skipped = [b for b in blocks(entry, "tool_use")
                   if b.get("name") == "Bash" and b.get("id") in refused]
        if entry.get("type") == "assistant" and skipped:
            message = entry["message"]
            out.append({**entry, "message": {**message, "content": [
                b for b in message["content"] if b not in skipped]}})
        else:
            out.append(entry)
    return out


def walk_entries(entries: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    """The Codex command results among a launcher's entries, with its
    prompts kept in order so a message after a stop removes its bound.
    Raise where a call, record or completed turn cannot be read."""
    native = native_walk(entries, kind)
    return saved_entries(entries, kind, latest_complete=True) if native is None else native


def native_walk(entries: list[dict[str, Any]], kind: str) -> list[dict[str, Any]] | None:
    """The results of a native assignment's turns, whose receipt holds its
    walk check, or None where the launcher's calls bind no native assignment."""
    from codex_ticket import Binding, Store, Assignment

    bound_calls = [binding for call in calls(entries) if (binding := Binding.read(call.scratch)) is not None]
    if bound_calls:
        binding = bound_calls[-1]
        store = Store(binding.store)
        state = store.snapshot()["agents"][binding.agent]
        manifest = store.manifest(binding.agent, state["revision"])
        assignment = Assignment.read(manifest)
        item = Native(binding.store, manifest, assignment, state)
        if (assignment.agent_type or assignment.role.agent_type) != kind or native_receipt(item) is None:
            raise ValueError("native assignment has no matching validated report")
        return native_execution(assignment, state, Path.home())[0]
    return None


def saved_entries(entries: list[dict[str, Any]], kind: str,
                  *, latest_complete: bool) -> list[dict[str, Any]]:
    """Project saved turns; strict consumers also require final completion."""
    entries = without_hook_refusals(entries)
    out: list[dict[str, Any]] = []
    scratch: Path | None = None
    records: list[dict[str, Any]] = []
    used = 0
    started = False
    owned_turns: set[str] = set()
    refused = fresh_refusals(entries)
    unanswered = False
    for index, entry in enumerate(entries):
        if is_prompt(entry):
            out.append(entry)
        for call_id, agent_type, directory in commands(entry):
            if call_id in refused:
                block = next(b for b in blocks(entry, "tool_use") if b.get("id") == call_id)
                launches = work_calls(str((block.get("input") or {}).get("command", "")))
                if len(launches) != 1:
                    raise ValueError("the refused Bash call contains more than one Codex launch")
                unanswered = scratch is not None
                continue
            if agent_type != kind:
                raise ValueError("the Codex call gives no matching agent type")
            if unrecorded_launch(entries, index, call_id, directory,
                                 used if directory == scratch else 0, recover_killed=True):
                continue
            if scratch is None:
                scratch = directory
                thread = (scratch / "codex-session").read_text().strip()
                if not thread:
                    raise ValueError("the Codex session id is empty")
                if not (scratch / "codex-events.jsonl").exists():
                    raise ValueError(f"the Codex launch {call_id} has no turn record in {scratch}")
                records = [json.loads(line) for line in
                           (scratch / "codex-events.jsonl").read_text().splitlines()]
            elif directory != scratch:
                raise ValueError("the launcher changed its Codex scratch directory")
            if used == len(records):
                raise ValueError(f"the Codex launch {call_id} has no turn record in {scratch}")
            record = records[used]
            unanswered = False
            call_start = timestamp(entry)
            later = next((timestamp(e) for e in entries[index + 1:]
                          for _, _, d in commands(e) if d == scratch), None)
            recorded = record.get("started")
            if isinstance(recorded, (int, float)) and (
                    (call_start is not None and recorded < call_start)
                    or (later is not None and recorded >= later)):
                raise ValueError(f"the Codex launch {call_id} has no matching turn record in {scratch}")
            used += 1
            if record["thread"] is None:
                if started or record["ok"] is not False or used == len(records):
                    raise ValueError("the Codex attempt has no session")
                continue
            if record["thread"] != thread:
                raise ValueError("the Codex record belongs to another session")
            turn_id = record.get("turn")
            if isinstance(turn_id, str):
                if turn_id in owned_turns:
                    raise ValueError("a Codex turn belongs to more than one work call")
                owned_turns.add(turn_id)
            started = True
            text = record["input"]
            if not isinstance(text, str):
                raise ValueError("the Codex input is not text")
            out.append({"type": "user", "message": {"content": text}})
            events = [json.loads(line) for line in record["output"].splitlines()]
            if latest_complete and used == len(records) and (record["ok"] is not True
                    or not any(e.get("type") == "turn.completed" for e in events)):
                raise ValueError("the Codex turn did not complete")
            for n, event in enumerate(events):
                if event.get("type") == "input":
                    if not isinstance(event.get("text"), str):
                        raise ValueError("the Codex steering input is not text")
                    out.append({"type": "user", "message": {"content": event["text"]}})
                if event.get("type") != "item.completed":
                    continue
                item = event["item"]
                if item.get("type") != "command_execution":
                    continue
                call = f"{used}:{n}"
                command, result = item["command"], item["aggregated_output"]
                out.extend(command_entries(call, command, result))
    if unanswered:
        raise ValueError("a refusal after an accepted Codex call needs a valid retry")
    if used != len(records):
        raise ValueError("the launcher's calls do not match the Codex turn records")
    return out


def command_entries(call: str, command: str, result: str) -> list[dict[str, Any]]:
    """A completed command in the transcript form the step reader accepts."""
    if not isinstance(command, str) or not isinstance(result, str):
        raise ValueError("the Codex command or output is not text")
    return [
        {"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Bash", "id": call,
             "input": {"command": command}}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "tool_use_id": call, "content": result}]}},
    ]


def output_blocks(output: Any) -> list[str]:
    """The texts of a result given as `input_text` blocks, else none."""
    if (isinstance(output, list) and output
            and all(isinstance(b, dict) and b.get("type") == "input_text" and isinstance(b.get("text"), str)
                    for b in output)):
        return [b["text"] for b in output]
    return []


def command_output(blocks: list[str]) -> str:
    """The command's output text: the `output` of a trailing JSON block, else the joined blocks."""
    try:
        decoded = json.loads(blocks[-1])
    except ValueError:
        decoded = None
    if isinstance(decoded, dict) and isinstance(decoded.get("output"), str):
        return decoded["output"]
    return "".join(blocks)


def live_commands(activity: list[dict[str, Any]], *, include_prompts: bool = False) -> list[dict[str, Any]]:
    """Pair completed rollout results with commands from this turn only."""
    pending: dict[str, str] = {}
    completed: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in activity:
        previous_length = len(out)
        p = row["payload"]
        kind = p.get("type")
        message = rollout_message(row) if include_prompts else None
        if message is not None and message[0] == "user":
            out.append({"type": "user", "uuid": str(len(out)),
                        "message": {"content": message[1]}})
        if row.get("type") == "response_item" and kind in ("function_call", "custom_tool_call"):
            command = native_shell_call(p)
            if command is not None:
                pending[p["call_id"]] = command
        elif kind == "exec_command_begin":
            pending[p["call_id"]] = shlex.join(p["command"])
        elif ((row.get("type") == "response_item" and kind in ("function_call_output", "custom_tool_call_output"))
              or kind == "exec_command_end"):
            identity = p["call_id"]
            if identity not in pending or identity in completed:
                continue
            output = p["output"]
            texts = output_blocks(output)
            # A running exec returns an acknowledgement, not a completed result.
            if "Process running with session ID" in ("".join(texts) if texts else output):
                continue
            result = command_output(texts) if texts else output
            out.extend(command_entries(identity, pending[identity], result))
            completed.add(identity)
        elif kind == "item_completed" and p["item"].get("type") == "CommandExecution":
            item = p["item"]
            identity = item["id"]
            if identity not in completed:
                command = item["command"]
                out.extend(command_entries(identity, shlex.join(command) if isinstance(command, list)
                                           else command, item["aggregated_output"]))
                completed.add(identity)
        if include_prompts:
            for entry in out[previous_length:]:
                entry["timestamp"] = row["timestamp"]
    return out


def baseline_entries(entries: list[dict[str, Any]], kind: str,
                     home: Path | None = None) -> list[dict[str, Any]]:
    """Read the saved walk and the completed prefix of its current live turn.

    Only the last launcher call may lack its final record. Its accepted
    thread must have exactly one turn in that call's interval.
    """
    import codex_rollout

    entries = without_hook_refusals(entries)
    accepted = calls(entries)
    if not accepted:
        return walk_entries(entries, kind)
    last = accepted[-1]
    if any(c.role != kind or c.scratch != last.scratch for c in accepted):
        raise ValueError("the Codex baseline calls change role or scratch directory")
    path = last.scratch / "codex-events.jsonl"
    records = codex_rollout.rows(path) if path.exists() else []
    if len(records) >= len(accepted):
        return walk_entries(entries, kind)
    if len(records) != len(accepted) - 1 or last.started is None:
        raise ValueError("the Codex baseline has unmatched launcher calls")
    if any(isinstance(r.get(key), (int, float)) and r[key] >= last.started
           for r in records for key in ("started", "ended")):
        raise ValueError("a saved Codex turn overlaps the current launcher call")
    prior = []
    for entry in entries:
        if any(b.get("id") == last.call_id for b in blocks(entry, "tool_use")):
            message = entry["message"]
            entry = {**entry, "message": {**message, "content": [
                b for b in message["content"] if not (
                    b.get("type") == "tool_use" and b.get("id") == last.call_id)]}}
        prior.append(entry)
    out = saved_entries(prior, kind, latest_complete=False)
    thread = (last.scratch / "codex-session").read_text().strip()
    turns = codex_rollout.read_turns(codex_rollout.rollout_path(thread, home or Path.home()))
    end = time.time()
    found = [t for t in turns if last.started <= t.started <= end]
    if len(found) != 1 or found[0].ended is not None:
        raise ValueError("the Codex baseline has no unique current turn")
    if any(r.get("turn") == found[0].turn for r in records):
        raise ValueError("the current Codex turn already belongs to a saved call")
    out.extend(live_commands(found[0].activity))
    return out
