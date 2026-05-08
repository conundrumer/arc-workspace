#!/usr/bin/env python3
"""inspect-session.py — render session(s) for a meta session to inspect.

Usage:
    scripts/inspect-session.py <session-id>   # inspect one session
    scripts/inspect-session.py                # inspect multi-session window
    scripts/inspect-session.py --solver-only  # window, omit meta sessions

Multi-session window: the boundary is the oldest meta session that ended
(identified by any user message containing META SESSION END or legacy
META SOLVER END). All later sessions are included if their first user
message contains SESSION START or SOLVER START — both also match the
META variants, so later meta sessions are included too.

--solver-only filters the window output to non-meta sessions. A
session is meta if its first user message starts with META SESSION START
or META SOLVER START. Ignored when a session-id is provided.
"""

import json
import sys
from pathlib import Path

PROJECT_DIR = Path.home() / ".claude/projects/-Users-davidlu-code-arc-workspace"
SESSION_KEYWORDS = ("SESSION START", "SOLVER START")
META_START_KEYWORDS = ("META SESSION START", "META SOLVER START")
META_END_KEYWORDS = ("META SESSION END", "META SOLVER END")


def parse_session(file):
    """Parse JSONL and return only the canon branch.

    Rewinds leave orphaned branches in the file. The canon branch is the chain
    from the most recently written record back to the root via parentUuid.
    """
    records = []
    for line in file.read_text().splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not records:
        return records
    by_uuid = {r["uuid"]: r for r in records if "uuid" in r}
    canon_leaf_uuid = next(
        (r["uuid"] for r in reversed(records) if "uuid" in r), None
    )
    if canon_leaf_uuid is None:
        return records
    chain = set()
    cur = canon_leaf_uuid
    while cur is not None and cur in by_uuid:
        chain.add(cur)
        cur = by_uuid[cur].get("parentUuid")
    return [r for r in records if r.get("uuid") in chain]


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
            if isinstance(content, str):
                if any(line.strip() in META_END_KEYWORDS for line in content.splitlines()):
                    return True
    return False


def is_meta_session(records):
    fus = first_user_string(records)
    return any(fus.startswith(k) for k in META_START_KEYWORDS)


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
    args = sys.argv[1:]
    solver_only = False
    if "--solver-only" in args:
        solver_only = True
        args = [a for a in args if a != "--solver-only"]

    if args:
        if solver_only:
            print("(--solver-only ignored when a session-id is provided.)", file=sys.stderr)
        sid = args[0]
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
        print("(No previous META SESSION END found; including all solver sessions.)", file=sys.stderr)
        start_idx = 0

    for i in range(start_idx, len(sessions)):
        _, file, records = sessions[i]
        fus = first_user_string(records)
        included = i == prev_meta_idx or any(k in fus for k in SESSION_KEYWORDS)
        if not included:
            continue
        if solver_only and is_meta_session(records):
            continue
        render(file.stem, records)


if __name__ == "__main__":
    main()
