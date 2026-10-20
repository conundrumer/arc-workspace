"""Synthetic Codex CLI turns and the launcher calls they answer."""

import json
from pathlib import Path


def turn(scratch: Path, results: list[tuple[str, str]], *, first: bool = True,
         text: str = "Do the work.") -> dict:
    """Save one completed turn and give its launcher's Bash call."""
    scratch.mkdir(exist_ok=True)
    (scratch / "codex-session").write_text("thread\n")
    events = [{"type": "item.completed", "item": {
        "type": "command_execution", "command": command, "aggregated_output": result}}
        for command, result in results]
    events.append({"type": "turn.completed"})
    with (scratch / "codex-events.jsonl").open("w" if first else "a") as f:
        f.write(json.dumps({"thread": "thread", "input": text, "ok": True, "output": "\n".join(map(json.dumps, events))}) + "\n")
    return {"type": "assistant", "message": {"content": [{
        "type": "tool_use", "name": "Bash", "id": "codex",
        "input": {"command": f"uv run python scripts/codex_agent.py code-reviewer '{scratch}' "
                  f"/tmp/brief gpt-6.1-sol high <<'INPUT'\n{text}\nINPUT"}}]}}
