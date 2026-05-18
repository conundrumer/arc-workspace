#!/usr/bin/env python3
"""Stop / SubagentStop hook for arc-workspace sessions.

Activation: `/session ...` in the main session transcript, unless the most
recent invocation is `/session meta end`. SubagentStop uses `transcript_path`
for the activation check.

Detection: edits since max(last fire, last user message), capped at FIRE_CAP
per turn. SubagentStop uses `agent_transcript_path` for fires and edits.

Sounds fire only on Stop.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
HOOK_NAME = "session-stop.py"
FIRE_CAP = 5

PROMPT = "Revision check on this turn's writes. \
Fix any overfitting, leakage, fabrication, verbosity. \
Flag any gaps, inconsistencies, contradictions, tensions, redundancies."


def canon_records(transcript_path):
    records = []
    for line in Path(transcript_path).expanduser().read_text().splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    by_uuid = {r["uuid"]: r for r in records if "uuid" in r}
    if not by_uuid:
        return records
    leaf = next((r["uuid"] for r in reversed(records) if "uuid" in r), None)
    chain = set()
    cur = leaf
    while cur and cur in by_uuid:
        chain.add(cur)
        cur = by_uuid[cur].get("parentUuid")
    return [r for r in records if r.get("uuid") in chain]


def session_active(records):
    last_args = None
    for r in records:
        if r.get("type") != "user" or r.get("isMeta"):
            continue
        content = r.get("message", {}).get("content")
        if not isinstance(content, str):
            continue
        if "<command-name>/session</command-name>" not in content:
            continue
        m = re.search(r"<command-args>(.*?)</command-args>", content, re.DOTALL)
        last_args = m.group(1).strip() if m else ""
    if last_args is None:
        return False
    first_line = last_args.splitlines()[0].strip() if last_args else ""
    return not first_line.startswith("meta end")


def fire_count_and_ts(records):
    """Fires-since-last-user count, plus last fire and user-message timestamps."""
    fire_count = 0
    fire_ts = ""
    user_ts = ""
    for r in records:
        ts = r.get("timestamp", "")
        if r.get("type") == "user" and not r.get("isMeta") and ts:
            content = r.get("message", {}).get("content")
            if isinstance(content, str):
                user_ts = ts
                fire_count = 0
        if r.get("type") == "system" and r.get("subtype") == "stop_hook_summary":
            for hi in r.get("hookInfos", []):
                if HOOK_NAME in hi.get("command", ""):
                    if ts > fire_ts:
                        fire_ts = ts
                    fire_count += 1
                    break
    return fire_count, fire_ts, user_ts


def has_edits_after(records, window_ts):
    for r in records:
        if r.get("type") != "assistant":
            continue
        if r.get("timestamp", "") <= window_ts:
            continue
        for block in r.get("message", {}).get("content", []):
            if block.get("type") == "tool_use" and block.get("name") in EDIT_TOOLS:
                return True
    return False


def play_sound(name):
    path = Path(__file__).parent / "sounds" / f"{name}.wav"
    subprocess.run(["afplay", str(path)], check=False)


def main():
    event = json.load(sys.stdin)
    is_subagent = event.get("hook_event_name") == "SubagentStop"
    main_path = event.get("transcript_path")
    detect_path = event.get("agent_transcript_path") if is_subagent else main_path
    if not main_path or not detect_path:
        sys.exit(0)
    if not session_active(canon_records(main_path)):
        sys.exit(0)
    detect_records = canon_records(detect_path)
    fire_count, fire_ts, user_ts = fire_count_and_ts(detect_records)
    ws = max(fire_ts, user_ts)
    edits_pending = bool(ws) and has_edits_after(detect_records, ws)
    if edits_pending and fire_count >= FIRE_CAP:
        if not is_subagent:
            play_sound("gave_up")
        sys.exit(0)
    if edits_pending:
        if not is_subagent:
            play_sound("continue")
        print(PROMPT, file=sys.stderr)
        sys.exit(2)
    if fire_count > 0 and not is_subagent:
        play_sound("resolved")
    sys.exit(0)


if __name__ == "__main__":
    main()
