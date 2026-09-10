"""One-off: tag every solver the user has not approved.

Approval used to stand outside the solver files, in the ledger's `approved`
rows and in state/approved.txt. It now stands in the file, as the `// draft`
line the console writes and approval removes. This script reads the two old
records once and writes the tag into every solver they leave out.

Run it from the repo root: `uv run python tools/console/tag_drafts.py`.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from solver_console import config, solvers  # noqa: E402

APPROVED_FILE = config.STATE_DIR / "approved.txt"


def approved_ids() -> set[str]:
    """What the two old records hold between them."""
    ids = set()
    try:
        ids |= set(APPROVED_FILE.read_text().split())
    except OSError:
        pass
    try:
        text = config.LEDGER.read_text(errors="replace")
    except OSError:
        return ids
    for line in text.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("stage") == "approved" and row.get("task"):
            ids.add(str(row["task"]))
    return ids


def main() -> int:
    approved = approved_ids()
    tagged, missed = [], []
    for path in sorted(config.SOLVERS.glob("*.dl")):
        stem = path.stem
        if path.name.startswith(".") or stem in approved:
            continue
        if solvers.is_draft(stem):
            continue
        solvers.mark_draft(stem)
        # a session writing the same file drops the line again; one retry
        if not solvers.is_draft(stem):
            solvers.mark_draft(stem)
        (tagged if solvers.is_draft(stem) else missed).append(stem)
    print(f"{len(approved)} approved, {len(tagged)} tagged")
    if missed:
        print("not tagged: " + " ".join(missed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
