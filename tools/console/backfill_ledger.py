"""One-time backfill of solver provenance into the console ledger.

The ledger records which model wrote each solver stage, but it only starts
recording when the console runs a stage. Solvers committed before that have no
entry. This script recovers their provenance from the Claude Code transcripts:
a session that edited `programs/solvers/<id>.dl` wrote that solver, and the
assistant rows carrying those edits report the model.

One line is appended per (task, session) pair, with stage "legacy" and source
"backfill". Pairs already in the ledger are skipped, so re-running is safe, and
the file is only ever appended to — the live console appends to the same file.

    uv run python tools/console/backfill_ledger.py --dry-run
    uv run python tools/console/backfill_ledger.py

`--approvals` recovers the approvals instead. The console commits only
approved solvers and names them in its subject, so each id in such a subject
gets an "approved" line with source "git", dated to its earliest such commit.
A solver written by fable before the console existed was approved by hand, so
a task with a legacy line on a fable model gets one with source "legacy",
dated to that line. A task that already has an "approved" line is skipped.

    uv run python tools/console/backfill_ledger.py --approvals --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOLVER_DIR = REPO / "programs" / "solvers"
LEDGER = REPO / "tools" / "console" / "state" / "reports" / "ledger.jsonl"
TRANSCRIPT_DIR = (
    Path.home() / ".claude" / "projects" / "-Users-davidlu-code-arc-workspace"
)

SOLVER_PATH = re.compile(r"programs/solvers/([0-9a-z_]+)\.dl")
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
FABLE = "claude-fable"


def is_real_model(model: str | None) -> bool:
    """Haiku rows are topline/summarizer noise, and <synthetic> rows have no author."""
    if not model:
        return False
    return "haiku" not in model and not model.startswith("<")


def normalize(model: str) -> str:
    return model.split("[", 1)[0].strip()


def scan_transcript(path: Path, tasks: set[str]) -> dict[str, Counter[str]]:
    """Models per task edited in this transcript, plus the transcript-wide tally under ""."""
    per_task: dict[str, Counter[str]] = {}
    overall: Counter[str] = Counter()
    with path.open(errors="replace") as fh:
        for line in fh:
            touches_solver = "programs/solvers/" in line
            if not touches_solver and '"model"' not in line:
                continue
            try:
                row = json.loads(line)
            except (ValueError, TypeError):
                continue
            if row.get("type") != "assistant":
                continue
            model = row.get("message", {}).get("model")
            if not is_real_model(model):
                continue
            model = normalize(model)
            overall[model] += 1
            if not touches_solver:
                continue
            for block in row.get("message", {}).get("content") or []:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                if block.get("name") not in EDIT_TOOLS:
                    continue
                target = (block.get("input") or {}).get("file_path") or ""
                found = SOLVER_PATH.search(target)
                if found and found.group(1) in tasks:
                    per_task.setdefault(found.group(1), Counter())[model] += 1
    per_task[""] = overall
    return per_task


APPROVAL_SUBJECT = re.compile(r"^(?:Add|Update) ")
TASK_ID = re.compile(r"\b[0-9a-f]{8}\b")


def git_approvals() -> dict[str, int]:
    """Task id -> the time of the earliest console commit that named it."""
    out = subprocess.run(["git", "log", "--format=%ct%x09%s"], cwd=REPO,
                         capture_output=True, text=True, check=True).stdout
    table: dict[str, int] = {}
    for line in out.splitlines():
        ts, _, subject = line.partition("\t")
        if not APPROVAL_SUBJECT.match(subject):
            continue
        for tid in TASK_ID.findall(subject):
            table[tid] = int(ts)     # newest first: the last seen is the earliest
    return table


def ledger_rows(ledger: Path) -> list[dict]:
    if not ledger.exists():
        return []
    out = []
    with ledger.open(errors="replace") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except (ValueError, TypeError):
                continue
            if isinstance(row, dict) and row.get("task"):
                out.append(row)
    return out


def backfill_approvals(ledger: Path, dry_run: bool) -> None:
    rows = ledger_rows(ledger)
    have = {str(row["task"]) for row in rows if row.get("stage") == "approved"}
    found: dict[str, tuple[int, str]] = {}
    for row in rows:
        if row.get("stage") == "legacy" and str(row.get("model") or "").startswith(FABLE):
            found[str(row["task"])] = (int(row.get("ts") or 0), "legacy")
    for tid, ts in git_approvals().items():
        found[tid] = (ts, "git")
    fresh = [{"task": tid, "stage": "approved", "backend": None, "model": None,
              "session": None, "ts": ts, "source": source}
             for tid, (ts, source) in sorted(found.items())
             if tid not in have and (SOLVER_DIR / f"{tid}.dl").exists()]
    for row in fresh:
        print(f"{row['task']}  approved  {row['ts']}  {row['source']}")
    if not dry_run and fresh:
        ledger.parent.mkdir(parents=True, exist_ok=True)
        with ledger.open("a") as fh:
            for row in fresh:
                fh.write(json.dumps(row) + "\n")
    print(f"{len(have)} already approved, "
          f"{len(fresh)} {'to append' if dry_run else 'appended'}")


def existing_pairs(ledger: Path) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    if not ledger.exists():
        return pairs
    with ledger.open(errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except (ValueError, TypeError):
                continue
            pairs.add((str(row.get("task")), str(row.get("session"))))
    return pairs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="print, do not write")
    ap.add_argument("--ledger", type=Path, default=LEDGER)
    ap.add_argument("--transcripts", type=Path, default=TRANSCRIPT_DIR)
    ap.add_argument("--approvals", action="store_true",
                    help="recover approvals from the console's commits instead")
    args = ap.parse_args()
    if args.approvals:
        backfill_approvals(args.ledger, args.dry_run)
        return

    tasks = {p.stem for p in SOLVER_DIR.glob("*.dl")}
    transcripts = sorted(args.transcripts.glob("*.jsonl"))
    print(f"{len(tasks)} solvers, {len(transcripts)} transcripts")

    entries: list[dict[str, object]] = []
    ambiguous: list[tuple[str, str, dict[str, int]]] = []
    for path in transcripts:
        found = scan_transcript(path, tasks)
        overall = found.pop("")
        if not found:
            continue
        session = path.stem
        ts = int(path.stat().st_mtime)
        for task, models in sorted(found.items()):
            if len(models) > 1:
                ambiguous.append((task, session, dict(models.most_common())))
            model = (models or overall).most_common(1)
            if not model:
                continue
            entries.append(
                {
                    "task": task,
                    "stage": "legacy",
                    "backend": "claude",
                    "model": model[0][0],
                    "session": session,
                    "ts": ts,
                    "source": "backfill",
                }
            )

    entries.sort(key=lambda e: (e["task"], e["ts"]))
    seen = existing_pairs(args.ledger)
    fresh = [e for e in entries if (e["task"], e["session"]) not in seen]

    covered = {e["task"] for e in entries}
    misses = sorted(tasks - covered)
    by_model: Counter[str] = Counter()
    fable_tasks: set[str] = set()
    for entry in entries:
        by_model[str(entry["model"])] += 1
        if str(entry["model"]).startswith(FABLE):
            fable_tasks.add(str(entry["task"]))

    if args.dry_run:
        for entry in fresh:
            print(json.dumps(entry))
    else:
        args.ledger.parent.mkdir(parents=True, exist_ok=True)
        with args.ledger.open("a") as fh:
            for entry in fresh:
                fh.write(json.dumps(entry) + "\n")

    print()
    print(f"lines: {len(entries)} built, {len(entries) - len(fresh)} already in ledger, "
          f"{len(fresh)} {'to append' if args.dry_run else 'appended'}")
    print(f"coverage: {len(covered)}/{len(tasks)} solvers, {len(misses)} without provenance")
    for task in misses[:20]:
        print(f"  miss {task}")
    if len(misses) > 20:
        print(f"  ... and {len(misses) - 20} more")
    print("lines per model:")
    for model, count in by_model.most_common():
        print(f"  {model} {count}")
    print(f"solvers with a {FABLE} line: {len(fable_tasks)}")
    print(f"ambiguous (task, session) pairs: {len(ambiguous)}")
    for task, session, models in ambiguous[:20]:
        print(f"  {task} {session} {models}")
    if len(ambiguous) > 20:
        print(f"  ... and {len(ambiguous) - 20} more")


if __name__ == "__main__":
    main()
