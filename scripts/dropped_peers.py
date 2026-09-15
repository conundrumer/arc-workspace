"""Inventory the alternate models past sessions wrote and did not ship.

    uv run python scripts/dropped_peers.py                  # inventory and runs
    uv run python scripts/dropped_peers.py --inventory-only # no runs
    uv run python scripts/dropped_peers.py --only 0dfd9992  # one task

The run writes `inventory.tsv` and `inventory-unmatched.txt` under
.scratch/peers/. A full run puts a few thousand Souffle runs through one
pool and takes 5 to 40 minutes.
"""

import argparse
import sys
import time
from pathlib import Path

from study.peers import (
    OUT_DIR,
    inventory,
    run_rows,
    stratum_counts,
    stratum_diverging,
    write_outputs,
)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="dropped_peers.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inventory-only", action="store_true",
                    help="skip the runs and the divergence columns")
    ap.add_argument("--only", metavar="ID", help="one task id")
    ap.add_argument("--limit", type=int, metavar="N",
                    help="stop after this many task ids")
    ap.add_argument("--out", type=Path, default=OUT_DIR, metavar="DIR",
                    help=f"where the files go (default {OUT_DIR})")
    args = ap.parse_args(argv)

    started = time.monotonic()
    rows, unmatched = inventory(only=args.only, limit=args.limit)
    print(f"{len(rows)} rows, {len(unmatched)} unmatched names",
          file=sys.stderr)

    if not args.inventory_only:
        done = [0]
        total = len({r.task_id for r in rows
                     if r.source == "scratch" and not r.is_copy})

        def progress(task_id: str) -> None:
            done[0] += 1
            print(f"[{done[0]}/{total}] {task_id}", file=sys.stderr)

        run_rows(rows, progress=progress)

    inventory_path, unmatched_path = write_outputs(rows, unmatched, args.out)
    print(f"{inventory_path}\n{unmatched_path}")
    print("strata: " + ", ".join(f"{name or '(none)'}={count}"
                                 for name, count in stratum_counts(rows).items()))
    if not args.inventory_only:
        for name, cell in stratum_diverging(rows).items():
            print(f"{name or '(none)'}: diverging={cell['diverging']} "
                  f"matching={cell['matching']}")
    print(f"wall time: {time.monotonic() - started:.1f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
