#!/usr/bin/env python3
"""Extract user review comments from solver-session transcripts.

Mirrors 80db06f8's extract.py, with the session filter widened to include
/session-skill sessions and the whole corpus (697 transcripts).
"""
import json, glob, os, re, sys

PROJ = "/Users/davidlu/.claude/projects/-Users-davidlu-code-arc-workspace"
OUT = os.path.dirname(os.path.abspath(__file__))

TASK_RE = re.compile(r"^Task:\s+([0-9a-f]{8})\b", re.M)
SESSION_CMD_RE = re.compile(
    r"<command-name>\s*/session\b.*?</command-name>(.*?)(?:</local-command-stdout>|$)",
    re.S)
SESSION_ARG_RE = re.compile(r"<command-args>\s*([0-9a-f]{8}|solver)\b", re.S)

BRIEF_MARKS = [
    "You are the first session of a chained flow",
    "You are a later session of a chained flow",
    "You are the final session of a chained flow",
    "Write the handoff report for the session that takes over from you",
    "Your last turn was cut off at the output limit",
    "Two turns went entirely to thinking",
    "your previous turn was cut off by a usage limit",
    "Commit the changes that solver workers left in the working tree",
    "Then do steps 2-4 of the creation pass",
    "Then do steps 2-5 of the creation pass",
    "Your report is in. Now step back from the pass and write the callouts",
    "Base directory for this skill",
    "<command-name>", "<command-message>", "<local-command",
    "<system-reminder>", "Caveat: The messages below were generated",
    "[Request interrupted",
    "This session is being continued from a previous conversation",
    "<user-prompt-submit-hook>",
    "Stop hook feedback:", "<task-notification>",
    "<bash-input>", "<bash-stdout>", "<bash-stderr>",
    "Continue from where you left off.",
    "Revision check on this turn's writes",
]

TRIGGERS = {"determine", "fit", "cleanup", "handoff", "commit", "next", "continue", "go",
            "ok", "yes", "no", "y", "n", "done", "review", "solver", "prune",
            "revise", "ack", "edited", "compact", "stop", "wait", "thanks",
            "ship it", "lgtm", "yep", "sure", "k", "callouts", "callout",
            "simplify", "audit"}


def blocks_text(msg):
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts = []
        for b in c:
            if isinstance(b, dict) and b.get("type") == "text":
                parts.append(b.get("text") or "")
            elif isinstance(b, dict) and b.get("type") == "tool_result":
                return None
        return "\n".join(parts)
    return None


def is_human(text):
    if not text:
        return False
    t = text.strip()
    if not t:
        return False
    for m in BRIEF_MARKS:
        if m in t:
            return False
    if t.startswith("/"):
        return False
    low = t.lower().strip(" .!?`")
    if low in TRIGGERS:
        return False
    if len(t) < 3:
        return False
    return True


def main():
    sessions = []
    for path in sorted(glob.glob(os.path.join(PROJ, "*.jsonl"))):
        rows = []
        try:
            with open(path, errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
        except Exception:
            continue
        tid = None
        kind = None
        opened = False
        comments = []
        last_asst = ""
        last_asst_ts = ""
        ts0 = None
        for r in rows:
            typ = r.get("type")
            if r.get("isSidechain"):
                continue
            msg = r.get("message")
            if typ == "assistant" and isinstance(msg, dict):
                c = msg.get("content")
                if isinstance(c, list):
                    txt = "\n".join(b.get("text", "") for b in c
                                    if isinstance(b, dict) and b.get("type") == "text")
                    if txt.strip():
                        last_asst = txt
                        last_asst_ts = r.get("timestamp") or ""
                continue
            if typ != "user" or not isinstance(msg, dict):
                continue
            text = blocks_text(msg)
            if text is None:
                continue
            if not opened:
                m = TASK_RE.search(text)
                if m:
                    tid = m.group(1)
                    kind = "console"
                    ts0 = r.get("timestamp")
                    opened = True
                    continue
                if "<command-name>" in text and "/session" in text:
                    a = SESSION_ARG_RE.search(text)
                    arg = a.group(1) if a else "solver"
                    tid = arg if arg != "solver" else "?"
                    kind = "skill"
                    ts0 = r.get("timestamp")
                    opened = True
                    continue
                # keep scanning past wrappers; a real human first message that is
                # neither means this is not a solver session
                if any(mk in text for mk in BRIEF_MARKS):
                    continue
                if text.strip():
                    break
                continue
            if is_human(text):
                comments.append({
                    "ts": r.get("timestamp"),
                    "text": text.strip(),
                    "prev": last_asst.strip(),
                    "prev_ts": last_asst_ts,
                })
        if tid and comments:
            sessions.append({
                "file": os.path.basename(path),
                "task": tid,
                "kind": kind,
                "start": ts0,
                "n": len(comments),
                "comments": comments,
            })
    sessions.sort(key=lambda s: s["start"] or "")
    with open(os.path.join(OUT, "corpus.json"), "w") as f:
        json.dump(sessions, f)
    total = sum(s["n"] for s in sessions)
    import collections
    print(f"solver sessions with comments: {len(sessions)}  comments: {total}")
    print(collections.Counter(s["kind"] for s in sessions))
    eras = collections.Counter(
        "new" if (c["ts"] or "") >= "2026-08-26T01:00" else "old"
        for s in sessions for c in s["comments"])
    print(eras)


if __name__ == "__main__":
    main()
