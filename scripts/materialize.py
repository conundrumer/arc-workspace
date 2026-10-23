"""Materialize every upstream task → data/tasks/<id>.json at its highest variant level."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from arc.jsonio import format_file
from arc.materialize import materialize_default
from arc.upstream import UPSTREAM_DIR, task_ids
from controlled_markdown import mctx
from engine import checkout
from worktree_submodules import set_up_in_script

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "tasks"


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    if not set_up_in_script(checkout.ROOT):
        return 1
    ids = sorted(task_ids())
    if not ids:
        print(mctx("{path} holds no task").format(path=UPSTREAM_DIR), file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.json"):
        old.unlink()
    written = 0
    failures: list[tuple[str, str]] = []
    for tid in ids:
        try:
            file_dict = materialize_default(tid)
            (OUT_DIR / f"{tid}.json").write_text(format_file(file_dict))
            written += 1
        except Exception as e:
            failures.append((tid, f"{type(e).__name__}: {e}"))

    print(f"wrote {written}/{len(ids)} tasks")
    if failures:
        print(f"\n{len(failures)} failures:")
        for tid, msg in failures[:20]:
            print(f"  {tid}: {msg}")
        if len(failures) > 20:
            print(f"  ... +{len(failures) - 20} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
