"""PostToolUse hook for console workers: when a tool call touches another
task's solver file, add a note on where that solver stands. Approved and
committed solvers are reference; anything else gets a note, once per session.

Reads `approved.txt` (ids the console holds in the approved state) and asks
git about the rest. The worker's own task, from CONSOLE_TASK, is exempt.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CONSOLE_ROOT") or Path(__file__).resolve().parents[2])
STATE = Path(os.environ.get("CONSOLE_STATE_DIR") or Path(__file__).parent / "state")
SOLVER_ID = re.compile(r"\b([0-9a-f]{8})\.dl\b")


def git_ok(*args: str) -> bool:
    return subprocess.run(["git", *args], cwd=ROOT,
                          capture_output=True).returncode == 0


def standing(item_id: str, approved: set[str]) -> str | None:
    """The note an id deserves, or None for ratified reference."""
    if item_id in approved:
        return None
    path = f"programs/solvers/{item_id}.dl"
    if not git_ok("cat-file", "-e", f"HEAD:{path}"):
        return (f"note: {item_id}.dl is not approved — don't use it as reference; "
                "it still counts as a survey caller.")
    if git_ok("diff", "--quiet", "HEAD", "--", path):
        return None
    return (f"note: {item_id}.dl has uncommitted edits — the committed "
            "version is the ratified reference.")


def main() -> None:
    try:
        ev = json.load(sys.stdin)
    except Exception:
        return
    blob = json.dumps(ev.get("tool_input")) + json.dumps(ev.get("tool_response"))
    ids = sorted(set(SOLVER_ID.findall(blob))
                 - {os.environ.get("CONSOLE_TASK", "")})
    if not ids:
        return
    seen_file = STATE / "refnote" / f"{ev.get('session_id') or 'unknown'}.txt"
    seen = set(seen_file.read_text().split()) if seen_file.exists() else set()
    try:
        approved = set((STATE / "approved.txt").read_text().split())
    except OSError:
        approved = set()
    notes, noted = [], []
    for item_id in ids:
        if item_id in seen:
            continue
        note = standing(item_id, approved)
        if note:
            notes.append(note)
            noted.append(item_id)
    if not notes:
        return
    seen_file.parent.mkdir(parents=True, exist_ok=True)
    seen_file.write_text("".join(i + "\n" for i in sorted(seen | set(noted))))
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse", "additionalContext": "\n".join(notes)}}))


if __name__ == "__main__":
    main()
