"""target_rule_check.py --skeleton DIR [--out FILE] [--tasks T,T,...]

Compares, for each sample of each task's skeleton file in DIR, the sample's `target_queries` (skeleton.py's own) with `points_write.scan_targets` over the same state: the rule that
`points_write.py --draws` uses for a state with no skeleton sample. No engine runs. It prints one JSON line a task, as it goes, and a last line with the totals.

With --out FILE (`.jsonl`, written as a zstd stream) it also writes one line for each sample where the two differ: task, sample id, the queries only the scan gives (`only_scan`), the queries
only the sample has (`only_sample`), and the sample's `refused_target_queries` and `no_progress_queries`. A restart skips the tasks that FILE already holds a `done` line for."""
import argparse
import collections
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # model/study
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # model/study/samples
import study_zst as Z  # noqa: E402
from points_write import scan_targets  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
    ap.add_argument('--skeleton', type=Path, required=True)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--tasks')
    args = ap.parse_args()
    tasks = sorted(p.stem for p in args.skeleton.glob('*.jsonl'))
    if args.tasks:
        tasks = [t for t in tasks if t in set(args.tasks.split(','))]
    done: set[str] = set()
    if args.out is not None and Z.exists(args.out):
        with Z.open_text(args.out) as f:
            done = {rec['done'] for rec in map(json.loads, f) if 'done' in rec}
    out = Z.open_text(args.out, 'a', line_buffering=True) if args.out is not None else None
    total: collections.Counter = collections.Counter()
    t0 = time.time()
    todo = [t for t in tasks if t not in done]
    for i, task in enumerate(todo, 1):
        records = [json.loads(line) for line in open(args.skeleton / f'{task}.jsonl') if '"record": "query"' in line or '"record": "sample"' in line]
        union = {r['hash']: r for r in records if r['record'] == 'query'}
        c: collections.Counter = collections.Counter()
        for s in (r for r in records if r['record'] == 'sample'):
            got, want = set(scan_targets(frozenset(s['state']['queries']), union)), set(s['target_queries'])
            c['samples'] += 1
            if got == want:
                c['equal'] += 1
                continue
            c['differ'] += 1
            c['only in the scan'] += len(got - want)
            c['only in the sample'] += len(want - got)
            if out is not None:
                out.write(json.dumps(dict(task=task, sample=s['id'], only_scan=sorted(got - want), only_sample=sorted(want - got), refused=s['refused_target_queries'], no_progress=s['no_progress_queries'])) + '\n')
        if out is not None:
            out.write(json.dumps(dict(done=task)) + '\n')
        total.update(c)
        print(json.dumps(dict(task=task, **c)), flush=True)
        el = time.time() - t0
        print(f'{i}/{len(todo)} tasks, {i / max(el, 1e-9):.1f} tasks/s, ETA {el / i * (len(todo) - i):.0f}s', file=sys.stderr, flush=True)
    if out is not None:
        out.close()
    print(json.dumps(dict(task='all', **total)), flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
