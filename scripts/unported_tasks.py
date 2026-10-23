"""Lists the ids of tasks that have no `programs/solvers/<id>.dl`, smallest first
(`--order size`, the default) or in name order (`--order name`).

Ids come from the `*.json` files under `data/upstream/arc-agi-{1,2}/data/{training,evaluation}/`;
`--dataset` and `--split` narrow them. Size is the gzipped byte length of
`data/tasks/<id>.json`. With `--json`, prints one JSON array of {id, size} objects
in place of one row per task.
"""

import argparse
import gzip
import json
import sys
from pathlib import Path

from arc.upstream import DATASETS, SPLITS, DatasetT, SplitT, task_ids

ROOT = Path(__file__).resolve().parent.parent
USAGE = ("usage: queue.sh [-n COUNT | --all] [--order name|size] [--json]"
         " [--dataset arc-agi-1|arc-agi-2] [--split training|evaluation]")


class _Once(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        if getattr(namespace, self.dest) is not None:
            parser.error(f"{option_string} given twice")
        setattr(namespace, self.dest, values)


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):
        print(USAGE, file=sys.stderr)
        sys.exit(2)


def parse(argv: list[str]) -> argparse.Namespace:
    parser = _Parser(usage=USAGE, add_help=False)
    parser.add_argument("-n", dest="count", type=int, default=1)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--order", choices=("name", "size"), default="size")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--dataset", choices=DATASETS, action=_Once)
    parser.add_argument("--split", choices=SPLITS, action=_Once)
    args = parser.parse_args(argv)
    if args.count < 1:
        parser.error("count")
    return args


def unsolved_ids(dataset: DatasetT | None, split: SplitT | None) -> set[str]:
    return {i for i in task_ids(dataset, split)
            if not (ROOT / "programs/solvers" / f"{i}.dl").exists()}


def task_size(task_id: str) -> int:
    path = ROOT / "data/tasks" / f"{task_id}.json"
    if not path.exists():
        sys.exit(f"queue.sh: no task file for {task_id}: {path}")
    return len(gzip.compress(path.read_bytes()))


def main(argv: list[str]) -> None:
    args = parse(argv)
    ids = unsolved_ids(args.dataset, args.split)
    rows = [{"id": i, "size": task_size(i)} for i in ids]
    rows.sort(key=(lambda r: r["id"]) if args.order == "name" else (lambda r: (r["size"], r["id"])))
    if not args.all:
        rows = rows[:args.count]
    if args.json:
        print(json.dumps(rows))
    else:
        for r in rows:
            print(f"{r['size']:5d}  {r['id']}")


if __name__ == "__main__":
    main(sys.argv[1:])
