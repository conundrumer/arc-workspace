#!/usr/bin/env python3
"""Stop hook for arc-workspace sessions.

Activation: scans transcript for `/session ...` invocations. Active unless the
most recent is `/session meta end`.

Detection: edits since max(last fire, last user message). Capped at FIRE_CAP
fires per turn. Set FIRE_CAP higher to allow loop-until-no-edits behavior.
"""

import json
import re
import sys
from pathlib import Path

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
HOOK_NAME = "session-stop.py"
FIRE_CAP = 5

PROMPT = "Revision check on this turn's writes. \
Fix any overfitting, leakage, fabrication, verbosity. \
Flag any gaps, inconsistencies, contradictions, tensions, redundancies."


PROMPT += "\nIf nothing to fix, end with <!-- hero -->"


def canon_records(transcript_path):
    records = []
    for line in Path(transcript_path).read_text().splitlines():
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


def main():
    event = json.load(sys.stdin)
    path = event.get("transcript_path")
    if not path:
        sys.exit(0)
    records = canon_records(path)
    if not session_active(records):
        sys.exit(0)
    fire_count, fire_ts, user_ts = fire_count_and_ts(records)
    if fire_count >= FIRE_CAP:
        sys.exit(0)
    ws = max(fire_ts, user_ts)
    if not ws or not has_edits_after(records, ws):
        sys.exit(0)
    print(PROMPT, file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
