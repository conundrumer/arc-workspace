"""Ephemeral Codex trials and their native event records; trial_agent HELP
defines the command interface."""

import json
import subprocess
import uuid
from pathlib import Path
from typing import Any

from handbook.context import codex_config_value, uncommented


def run(root: Path, shared: Path, out: Path, brief: str, model: str, effort: str) -> int:
    config: dict[str, object] = {
        "model_reasoning_effort": effort,
        "project_doc_max_bytes": 0,
        "developer_instructions": uncommented(shared.read_text()),
        "approval_policy": "never",
        "mcp_servers": {},
        "features.apps": False,
        "features.plugins": False,
        "features.multi_agent": False,
        "features.multi_agent_v2": False,
        "features.hooks": False,
        "features.browser_use": False,
        "features.computer_use": False,
        "features.in_app_browser": False,
        "features.image_generation": False,
        "features.remote_plugin": False,
        "features.skip_host_skill_discovery": True,
        "features.skill_search": False,
        "features.memories": False,
        f"projects.{codex_config_value(str(root))}.trust_level": "untrusted",
        "web_search": "disabled",
    }
    command = ["codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
               "--sandbox", "read-only", "--json", "--model", model, "--cd", str(root)]
    for key, value in config.items():
        command.extend(["-c", f"{key}={codex_config_value(value)}"])
    write_status(out, None, "")
    try:
        with out.open("w") as output:
            result = subprocess.run(command, input=brief, text=True, stdout=output,
                                    stderr=subprocess.PIPE, cwd=root)
        write_status(out, result.returncode, result.stderr)
        return result.returncode
    except OSError as error:
        write_status(out, 1, str(error))
        return 1


def status(path: Path) -> dict[str, Any]:
    record = path.with_suffix(".status.json")
    return json.loads(record.read_text()) if record.exists() else {}


def write_status(path: Path, returncode: int | None, stderr: str) -> None:
    record = path.with_suffix(".status.json")
    part = record.with_name(f"{record.name}.{uuid.uuid4().hex}")
    part.write_text(json.dumps({"backend": "codex", "returncode": returncode,
                                "stderr": stderr}))
    part.replace(record)


def ready(event: dict[str, Any]) -> bool:
    return (event.get("type") == "item.completed" and
            event.get("item", {}).get("type") == "agent_message")


def failed(event: dict[str, Any]) -> bool:
    return event.get("type") in ("turn.failed", "error")


def terminal(event: dict[str, Any]) -> bool:
    return failed(event) or event.get("type") == "turn.completed"


def calls(events: list[dict[str, Any]]) -> list[str]:
    # Native records include every item phase and unfamiliar event form, so
    # the audit cannot silently lose an executed call or its failure.
    lines = [json.dumps(event, ensure_ascii=False) for event in events]
    usage = next((e["usage"] for e in events if e.get("usage") is not None), {})
    for field in ("input_tokens", "cached_input_tokens", "output_tokens"):
        lines.append(f"{field} {usage.get(field, '?')}")
    lines.append("cache_creation_input_tokens ?")
    return lines
