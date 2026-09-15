"""Compare the dropped peers against the shipped cases they stand beside.

    uv run python scripts/compare_peers.py          # writes .scratch/peers/compare.md

The run reads `.scratch/peers/inventory.tsv`, measures the per-case features
of every peer file that holds a dropped case beside the kept ones, and
writes the report. It runs no Souffle.
"""

import argparse
import sys
from pathlib import Path

from study.compare_peers import INVENTORY, REPORT, build, verdict


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="compare_peers.py", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inventory", type=Path, default=INVENTORY, metavar="TSV",
                    help=f"the inventory to read (default {INVENTORY})")
    ap.add_argument("--out", type=Path, default=REPORT, metavar="MD",
                    help=f"where the report goes (default {REPORT})")
    args = ap.parse_args(argv)

    if not args.inventory.exists():
        print(f"no inventory at {args.inventory}", file=sys.stderr)
        return 2

    path, cases = build(args.inventory, args.out)
    print(path)
    print(verdict(cases))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
