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
"""

from __future__ import annotations

import argparse
import json
import re
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
    args = ap.parse_args()

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
