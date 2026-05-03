"""Dump every train/test pair of an upstream task into patch column form.

Output is a stub for hand-editing into a real patch — grids are labeled with
'# <set> <idx> <grid>' comments and emitted plain (no '~' change cells, no
'@' verb headers).

Usage:
  uv run python scripts/patch_stub.py <task_id>

Refuses if data/patches/<task_id>.arcpatch already exists.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from arc.task import Grid
from arc.upstream import load

PATCHES_DIR = Path(__file__).resolve().parents[1] / "data" / "patches"

CELL_WIDTH = 4


def format_grid(grid: Grid) -> str:
    return "\n".join("".join(f"{c:<{CELL_WIDTH}}" for c in row).rstrip() for row in grid)


def format_stub(task_id: str) -> str:
    task, _ = load(task_id)
    blocks: list[str] = []
    for set_name, examples in (("train", task.train), ("test", task.test)):
        for i, ex in enumerate(examples):
            blocks.append(f"# {set_name} {i} input\n{format_grid(ex.input)}")
            blocks.append(f"# {set_name} {i} output\n{format_grid(ex.output)}")
    return "\n\n".join(blocks) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_id")
    args = parser.parse_args()

    out = PATCHES_DIR / f"{args.task_id}.arcpatch"
    if out.exists():
        print(f"refuse: {out} already exists", file=sys.stderr)
        return 1

    out.write_text(format_stub(args.task_id))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
