#!/usr/bin/env python3
"""inspect-session.py — render session(s) for a meta session to inspect.

Usage:
    scripts/inspect-session.py <session-id>   # inspect one session
    scripts/inspect-session.py                # inspect window since previous meta session

Multi-session window: previous meta session (inclusive, identified by any
user message containing META SOLVER END) + all solver sessions started
after it (identified by SOLVER START in their first user message — which
also matches META SOLVER START).
"""

import json
import sys
from pathlib import Path

PROJECT_DIR = Path.home() / ".claude/projects/-Users-davidlu-code-arc-workspace"
SOLVER_KEYWORD = "SOLVER START"
META_END_KEYWORD = "META SOLVER END"


def parse_session(file):
    records = []
    for line in file.read_text().splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def first_user_string(records):
    for r in records:
        if r.get("type") == "user":
            content = r.get("message", {}).get("content")
            if isinstance(content, str):
                return content
    return ""


def has_meta_end(records):
    for r in records:
        if r.get("type") == "user":
            content = r.get("message", {}).get("content")
            if isinstance(content, str) and META_END_KEYWORD in content:
                return True
    return False


def first_timestamp(records):
    for r in records:
        if "timestamp" in r:
            return r["timestamp"]
    return ""


def last_timestamp(records):
    for r in reversed(records):
        if "timestamp" in r:
            return r["timestamp"]
    return ""


def session_cwd(records):
    for r in records:
        if "cwd" in r:
            return r["cwd"]
    return ""


def relpath(path, cwd):
    if cwd and path.startswith(cwd + "/"):
        return path[len(cwd) + 1:]
    return path


def render_tool(name, input_, cwd):
    if name in {"Read", "Write", "Edit"}:
        return f"TOOL {name}: {relpath(input_.get('file_path', ''), cwd)}"
    if name == "Bash":
        cmd = input_.get("command", "")
        return f"TOOL Bash: {cmd.split(chr(10), 1)[0]}"
    if name == "Grep":
        return f"TOOL Grep: {input_.get('pattern', '')}"
    if name == "Glob":
        return f"TOOL Glob: {input_.get('pattern', '')}"
    if name == "Agent":
        return f"TOOL Agent: {input_.get('description', '')}"
    if name == "WebSearch":
        return f"TOOL WebSearch: {input_.get('query', '')}"
    if name == "WebFetch":
        return f"TOOL WebFetch: {input_.get('url', '')}"
    if name == "Skill":
        return f"TOOL Skill: {input_.get('skill', '')}"
    if name == "ToolSearch":
        return f"TOOL ToolSearch: {input_.get('query', '')}"
    return f"TOOL {name}"


def render(sid, records):
    cwd = session_cwd(records)
    print(f"=== SESSION {sid} ===")
    print(f"Start: {first_timestamp(records)}")
    print(f"End:   {last_timestamp(records)}")
    print()
    for r in records:
        if r.get("type") == "user":
            content = r.get("message", {}).get("content")
            if isinstance(content, str):
                print(f"USER: {content}")
        elif r.get("type") == "assistant":
            for block in r.get("message", {}).get("content", []):
                btype = block.get("type")
                if btype == "text":
                    print(f"ASST: {block.get('text', '')}")
                elif btype == "tool_use":
                    print(render_tool(block.get("name", ""), block.get("input", {}), cwd))
    print()


def main():
    if len(sys.argv) > 1:
        sid = sys.argv[1]
        file = PROJECT_DIR / f"{sid}.jsonl"
        render(file.stem, parse_session(file))
        return

    sessions = []
    for f in PROJECT_DIR.glob("*.jsonl"):
        records = parse_session(f)
        ts = first_timestamp(records)
        if ts:
            sessions.append((ts, f, records))
    sessions.sort(key=lambda x: x[0])

    prev_meta_idx = -1
    for i in range(len(sessions) - 1, -1, -1):
        if has_meta_end(sessions[i][2]):
            prev_meta_idx = i
            break

    if prev_meta_idx >= 0:
        start_idx = prev_meta_idx
    else:
        print("(No previous META SOLVER END found; including all solver sessions.)", file=sys.stderr)
        start_idx = 0

    for i in range(start_idx, len(sessions)):
        _, file, records = sessions[i]
        if i == prev_meta_idx or SOLVER_KEYWORD in first_user_string(records):
            render(file.stem, records)


if __name__ == "__main__":
    main()
