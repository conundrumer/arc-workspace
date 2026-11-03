"""Compares the point files of two engine wheels, task by task, to show whether the two wheels give equal points (fit_trees.py --wheels-alike).

  python3 points_alike.py A B [--out JSON]      A and B are folders samples/SET/points/<plan>, or a folder written with points_write.py --out, at the same level

For each task with a file in both folders, the two files must have the same records in the same order. Each record is compared without its `seconds`, and the header is
also compared without its `wheel`. The JSON names both folders, the wheel of each, the tasks compared, and each task whose files differ with its first differing record.
"""
import argparse
import gzip
import json
import sys
from pathlib import Path

IGNORED = dict(header=('wheel', 'seconds'), other=('seconds',))


def records(p: Path):
    with gzip.open(p, 'rt') as f:
        for line in f:
            r = json.loads(line)
            drop = IGNORED['header' if r.get('record') == 'header' else 'other']
            yield {k: v for k, v in r.items() if k not in drop}


def first_wheel(folder: Path) -> str | None:
    for p in sorted(folder.glob('*.jsonl.gz')):
        with gzip.open(p, 'rt') as f:
            return json.loads(f.readline()).get('wheel')
    return None


def compare(a: Path, b: Path) -> tuple[bool, int, str | None]:
    """(equal, records compared, the first difference)."""
    n = 0
    ra, rb = records(a), records(b)
    while True:
        x, y = next(ra, None), next(rb, None)
        if x is None and y is None:
            return True, n, None
        n += 1
        if x != y:
            if x is None or y is None:
                return False, n, f'record {n}: only one file has it'
            keys = sorted(k for k in set(x) | set(y) if x.get(k) != y.get(k))
            return False, n, f'record {n} ({x.get("record", "point")}): {keys}'


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
    ap.add_argument('a', type=Path)
    ap.add_argument('b', type=Path)
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    tasks = sorted({p.name.removesuffix('.jsonl.gz') for p in args.a.glob('*.jsonl.gz')} & {p.name.removesuffix('.jsonl.gz') for p in args.b.glob('*.jsonl.gz')})
    differ, count = {}, 0
    for t in tasks:
        ok, n, why = compare(args.a / f'{t}.jsonl.gz', args.b / f'{t}.jsonl.gz')
        count += n
        if not ok:
            differ[t] = why
        print(f'{t} {"equal" if ok else "DIFFER " + str(why)}', flush=True)
    out = dict(a=str(args.a), b=str(args.b), wheels=[first_wheel(args.a), first_wheel(args.b)], ignored=IGNORED, tasks=tasks, records=count, differ=differ)
    print(f'{len(tasks)} tasks, {count} records, {len(tasks) - len(differ)} equal, {len(differ)} differ')
    if args.out:
        args.out.write_text(json.dumps(out, indent=1) + '\n')
    return 1 if differ or not tasks else 0


if __name__ == '__main__':
    sys.exit(main())
