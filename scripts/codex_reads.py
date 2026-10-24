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
from codex_commands import (command_entries, command_output, live_commands, native_shell_call,
                            output_blocks, rollout_message)
from codex_agent import BUSY_REFUSAL, FRESH_REFUSAL
from command_labels import segment_program, simple_commands
from run_reads import blocks, is_prompt

from operations.roles import GENERAL, Role
from codex_ticket import Assignment
from state_reads import DERIVED, state_cache


from codex_native_reads import (_native_sessions, Native, native_assignments, native_projection, native_find, native_turn, native_execution, native_receipt, native_agents, native_sent)


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
    if (body in ("codex_agent: " + FRESH_REFUSAL, "codex_agent: " + BUSY_REFUSAL)
            or re.fullmatch(r"codex_agent: work call refused: seat .+ is busy; no thread or turn accepted; wait for its owner, then retry", body)):
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
