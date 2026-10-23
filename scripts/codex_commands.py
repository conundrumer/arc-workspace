"""Completed literal shell invocations and messages from native Codex rollouts."""

import json
import re
from typing import Any

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

def result_text(output: Any) -> tuple[str, str | None, bool]:
    """Read result text, a yielded cell id, and evidence that a shell is unfinished."""
    blocks = output_blocks(output)
    texts = blocks or [output if isinstance(output, str) else json.dumps(output)]
    running = False
    for text in texts:
        try:
            value = json.loads(text)
        except ValueError:
            value = None
        if isinstance(value, dict) and (value.get("session_id") is not None
                                       or value.get("isError") or value.get("error")
                                       or value.get("exit_code") not in (None, 0)):
            running = True
    joined = "\n".join(texts)
    cell = re.search(r"Script running with cell ID ([^\s]+)", joined)
    running = running or "Process running with session ID" in joined
    failed = any(marker in joined for marker in
                 ("Script failed", "Script terminated", "Script execution failed"))
    result = command_output(texts)
    if cell is not None:
        result = joined.partition("Output:\n")[2]
    return result, cell[1] if cell else None, running or failed

def live_commands(activity: list[dict[str, Any]], *, include_prompts: bool = False) -> list[dict[str, Any]]:
    """Emit source-proven literal calls only after their complete result, in observation order.

    A yielded exec remains pending through waits on its cell id. Shell events,
    unresolved cells, failed results and results with a live shell earn no evidence.
    """
    pending: dict[str, tuple[str, str, list[str]]] = {}
    cells: dict[str, tuple[str, str, list[str]]] = {}
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in activity:
        previous_length = len(out)
        p = row["payload"]
        kind = p.get("type")
        message = rollout_message(row) if include_prompts else None
        if message is not None and message[0] == "user":
            out.append({"type": "user", "uuid": str(len(out)),
                        "message": {"content": message[1]}})
        if row.get("type") == "response_item":
            if kind in ("function_call", "custom_tool_call"):
                identity = p["call_id"]
                if identity in seen:
                    continue
                seen.add(identity)
                command = native_shell_call(p)
                if command is not None:
                    pending[identity] = (identity, command, [])
                elif kind == "function_call" and p.get("name") in ("wait", "functions.wait"):
                    args = json.loads(p["arguments"])
                    state = cells.pop(args.get("cell_id"), None)
                    if state is not None and not args.get("terminate"):
                        pending[identity] = state
            elif kind in ("function_call_output", "custom_tool_call_output"):
                state = pending.pop(p["call_id"], None)
                if state is None:
                    continue
                identity, command, chunks = state
                result, cell, refused = result_text(p["output"])
                if refused or p.get("is_error"):
                    continue
                chunks.append(result)
                if cell is not None:
                    cells[cell] = state
                    continue
                out.extend(command_entries(identity, command, "".join(chunks)))
        if include_prompts:
            for entry in out[previous_length:]:
                entry["timestamp"] = row["timestamp"]
    return out
