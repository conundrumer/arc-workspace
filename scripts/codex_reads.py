"""The command results of a launcher's Codex turns, saved by codex_agent.

The launcher's calls locate the scratch directory. Each call must have a
record, in order. Failed attempts before session creation contribute no
walk. Once a session exists, records must match codex-session, and the
latest turn must have completed. Missing or unreadable evidence refuses
handback, including a repeated handback.
The results are given in the transcript form the checklist hook reads.
"""

import json
from pathlib import Path
from typing import Any

from command_labels import segment_program, simple_commands
from run_reads import blocks, is_prompt


def walk_entries(entries: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    """The Codex command results among a launcher's entries, with its
    prompts kept in order so a message after a stop removes its bound.
    Raise where a call, record or completed turn cannot be read."""
    out: list[dict[str, Any]] = []
    scratch: Path | None = None
    records: list[dict[str, Any]] = []
    used = 0
    started = False
    for entry in entries:
        if is_prompt(entry):
            out.append(entry)
        for block in blocks(entry, "tool_use"):
            if entry.get("type") != "assistant" or block.get("name") != "Bash":
                continue
            for words in simple_commands(str((block.get("input") or {}).get("command", ""))):
                program, args = segment_program(words)
                if program != "codex_agent.py":
                    continue
                if len(args) < 5 or args[0] != kind:
                    raise ValueError("the Codex call gives no matching role and scratch directory")
                directory = Path(args[1])
                # Relative paths after a shell cd cannot be located from the hook's cwd.
                if not directory.is_absolute():
                    raise ValueError("the Codex scratch directory must be absolute")
                if scratch is None:
                    scratch = directory
                    thread = (scratch / "codex-session").read_text().strip()
                    if not thread:
                        raise ValueError("the Codex session id is empty")
                    records = [json.loads(line) for line in
                               (scratch / "codex-events.jsonl").read_text().splitlines()]
                elif directory != scratch:
                    raise ValueError("the launcher changed its Codex scratch directory")
                record = records[used]
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
    if scratch is None or used != len(records):
        raise ValueError("the launcher's calls do not match the Codex turn records")
    return out
