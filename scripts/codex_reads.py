"""The command results of a launcher's Codex turns, saved by codex_agent.

The launcher's calls locate the scratch directory. Each call must have a
record, in order. Failed attempts before session creation contribute no
walk. A fresh-call refusal proved by its tool result permits a retry in
a new directory before any call is accepted. Once a session exists,
records must match codex-session, and the latest turn must have completed.
Missing or unreadable evidence refuses handback, including a repeated handback.
The results are given in the transcript form the checklist hook reads.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from codex_agent import FRESH_REFUSAL
from command_labels import segment_program, simple_commands
from run_reads import blocks, is_prompt

from operations.roles import Role


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


def timestamp(entry: dict[str, Any]) -> float | None:
    value = entry.get("timestamp")
    return datetime.fromisoformat(value).timestamp() if isinstance(value, str) else None


def commands(entry: dict[str, Any]):
    """Find turn launches, leaving help and session controls out."""
    for block in blocks(entry, "tool_use"):
        if entry.get("type") != "assistant" or block.get("name") != "Bash":
            continue
        for words in simple_commands(str((block.get("input") or {}).get("command", ""))):
            program, args = segment_program(words)
            if program != "codex_agent.py" or (args and args[0] in ("show", "steer", "interrupt")):
                continue
            options = args[:args.index("--")] if "--" in args else args
            if any(arg in ("-h", "--help") for arg in options):
                continue
            if len(args) < 5:
                raise ValueError("the Codex call gives no matching role and scratch directory")
            agent_type = Role(args[0]).agent_type
            for i, arg in enumerate(args):
                if arg == "--agent-type":
                    agent_type = args[i + 1]
                elif arg.startswith("--agent-type="):
                    agent_type = arg.partition("=")[2]
            directory = Path(args[1])
            if not directory.is_absolute():
                raise ValueError("the Codex scratch directory must be absolute")
            yield block["id"], agent_type, directory


def calls(entries: list[dict[str, Any]]) -> list[Call]:
    ends = {}
    for entry in entries:
        for block in blocks(entry, "tool_result"):
            ends[block.get("tool_use_id")] = timestamp(entry)
    until = max((t for e in entries if (t := timestamp(e)) is not None), default=None)
    return [Call(role, directory, timestamp(entry), ends.get(call), until, call)
            for entry in entries for call, role, directory in commands(entry)]


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
                      call_id: str, scratch: Path) -> bool:
    """Require proof of preparation failure and that no turn record is its own.

    Older launchers have only their error output. Their scratch must be empty
    or contain timed records starting at a later call. New launchers also save
    an identified preparation failure, separate from Codex's turn history.
    """
    import re

    output = launch_output(entries, call_id)
    body = output.removeprefix("Exit code 1\n").removesuffix("\n\n[exited with code 1]")
    exit_one = output.startswith("Exit code 1\n") or output.endswith("[exited with code 1]")
    failure = re.fullmatch(
        r"codex_agent: launch failed before Codex started \[([0-9a-f]{32})\]: (.*)",
        body, re.S)
    interval = None
    if failure:
        path = scratch / "codex-launch-failures.jsonl"
        if not path.exists():
            return False
        saved = [json.loads(line) for line in path.read_text().splitlines()]
        matches = [r for r in saved if r.get("id") == failure[1]
                   and r.get("error") == failure[2]]
        if len(matches) != 1:
            return False
        interval = matches[0]["started"], matches[0]["ended"]
        if not all(isinstance(t, (int, float)) for t in interval) or interval[0] > interval[1]:
            return False
    else:
        # A traceback must locate the failure inside instruction construction,
        # not merely mention that function in a later Codex error or answer.
        frames = re.findall(r'^  File "([^"\n]+)", line \d+, in (\S+)\n    ([^\n]+)',
                            body, re.M)
        traceback = (body.startswith("Traceback (most recent call last):\n")
                     and exit_one
                     and len(frames) >= 4
                     and [(Path(p).name, f) for p, f, _ in frames[:4]] == [
                         ("codex_agent.py", "<module>"), ("codex_agent.py", "main"),
                         ("codex_agent.py", "run"), ("codex_agent.py", "role_instructions")]
                     and frames[2][2].startswith("instructions = ")
                     and "role_instructions(" in frames[2][2])
        diagnostic = (exit_one
                      and re.fullmatch(r"codex_agent: /[^\n]+:\d+: no-marker: [^\n]+", body))
        if not (traceback or diagnostic):
            return False

    block = next(b for b in blocks(entries[index], "tool_use") if b.get("id") == call_id)
    launches = [args for program, args in map(segment_program, simple_commands(
        str((block.get("input") or {}).get("command", "")))) if program == "codex_agent.py"]
    if len(launches) != 1:
        raise ValueError("the failed Bash call contains more than one Codex command")
    if interval is not None:
        # The matching identifier is written only by preparation's exception
        # handler. It cannot consume a turn record, even on a failed resume.
        return True
    if "--resume" in launches[0]:
        return False
    path = scratch / "codex-events.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
    if not records:
        return not (scratch / "codex-session").exists()
    start = timestamp(entries[index])
    later = next((timestamp(e) for e in entries[index + 1:]
                  for _, _, directory in commands(e) if directory == scratch), None)
    if start is None or later is None or later <= start:
        return False
    return all(isinstance(r.get("started"), (int, float)) and r["started"] >= later
               for r in records)


def walk_entries(entries: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    """The Codex command results among a launcher's entries, with its
    prompts kept in order so a message after a stop removes its bound.
    Raise where a call, record or completed turn cannot be read."""
    out: list[dict[str, Any]] = []
    scratch: Path | None = None
    records: list[dict[str, Any]] = []
    used = 0
    started = False
    refused = {b.get("tool_use_id") for entry in entries
               for b in blocks(entry, "tool_result")
               if isinstance(b.get("content"), str)
               and b["content"].strip() in ("codex_agent: " + FRESH_REFUSAL,
                                            "Exit code 1\ncodex_agent: " + FRESH_REFUSAL)}
    for index, entry in enumerate(entries):
        if is_prompt(entry):
            out.append(entry)
        for call_id, agent_type, directory in commands(entry):
            if call_id in refused:
                block = next(b for b in blocks(entry, "tool_use") if b.get("id") == call_id)
                launches = [program for program, _ in map(segment_program, simple_commands(
                    str((block.get("input") or {}).get("command", ""))))
                    if program == "codex_agent.py"]
                if len(launches) != 1:
                    raise ValueError("the refused Bash call contains more than one Codex command")
                if scratch is not None:
                    raise ValueError("a fresh launch was refused after an accepted Codex call")
                continue
            if agent_type != kind:
                raise ValueError("the Codex call gives no matching agent type")
            if unrecorded_launch(entries, index, call_id, directory):
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
            started = True
            text = record["input"]
            if not isinstance(text, str):
                raise ValueError("the Codex input is not text")
            out.append({"type": "user", "message": {"content": text}})
            events = [json.loads(line) for line in record["output"].splitlines()]
            if used == len(records) and (record["ok"] is not True
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
                if not isinstance(command, str) or not isinstance(result, str):
                    raise ValueError("the Codex command or output is not text")
                out.extend([
                    {"type": "assistant", "message": {"content": [
                        {"type": "tool_use", "name": "Bash", "id": call,
                         "input": {"command": command}}]}},
                    {"type": "user", "message": {"content": [
                        {"type": "tool_result", "tool_use_id": call, "content": result}]}},
                ])
    if used != len(records):
        raise ValueError("the launcher's calls do not match the Codex turn records")
    return out
