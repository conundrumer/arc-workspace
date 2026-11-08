"""draw_targets.py --skeleton DIR [--points DIR] PATH [PATH ...]

For each task's file of sampled-query records (PATH is a `draws.jsonl[.zst]` file, or a folder searched for such files), it counts the last steps by what `points_write.py --draws` does with
their state (docs/sample-build/training-instances.md, "Sampled queries of the search"), from the task's skeleton file in DIR (`<task>.jsonl`). A last step's ground-truth part is the
state's queries that are queries of the skeleton. It prints one JSON line a task, as it goes:
- `last steps`, with each repeat counted;
- `matched`: the state is a skeleton sample's state;
- `to add: last steps` and `to add: states`: the state is no sample's state, its ground-truth part is a sample's state, and that sample has a target query that the state has not written;
- `to add: queries outside the union`: the distinct queries of those states that are no skeleton query (the queries that `points_write.py` writes a query record for);
- the last steps that are not added, each for one reason (`GROUND_TRUTH`, `NO_HASH` and `NO_TARGET` of `points_write.py`, which are also the reasons in the headers).

With --points DIR (the folder of the plan's files that `points_write.py` wrote, `<task>.jsonl.zst`) it also compares the header's `draw_counts` of each task with those counts, and prints
`OK` or the differences:
- `matched`, and the counts of the three reasons above, must equal;
- `added` plus the other `not added: <reason>` (a step that gives no query record, a sample that fails) must equal `to add: last steps`;
- `added states` must be at most `to add: states`.
The exit status is 1 where a task differs."""
import argparse
import collections
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # model/study
import study_zst as Z  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # model/study/samples
from points_write import GROUND_TRUTH, NO_HASH, NO_TARGET  # noqa: E402  (the reasons that the headers' draw_counts use)


def record_files(paths: list[str]) -> list[str]:
    """The record files of the paths, by logical name."""
    found = set()
    for p in map(Path, paths):
        if p.is_dir():
            found |= {Z.logical(f) for f in p.rglob('draws.jsonl*') if f.name in ('draws.jsonl', 'draws.jsonl.zst')}
        else:
            found.add(Z.logical(p))
    return sorted(found)


def last_steps(path: str) -> tuple[str, list[list]]:
    """(the task, [state, count] of each record in file order, the count being the record and its repeats)."""
    task = ''
    at: dict[int, list] = {}
    out: list[list] = []
    with Z.open_text(path) as f:
        for line in f:
            rec = json.loads(line)
            if 'repeat' in rec:
                at[int(rec['repeat'])][1] += 1
            elif 'steps' in rec:
                task = rec['task']
                at[int(rec['draw'])] = entry = [frozenset(rec['steps'][-1]['state']), 1]
                out.append(entry)
    return task, out


def count_task(task: str, steps: list[list], skeleton: Path) -> dict:
    records = [json.loads(line) for line in open(skeleton / f'{task}.jsonl') if '"record": "query"' in line or '"record": "sample"' in line]
    union = {r['hash'] for r in records if r['record'] == 'query'}
    targets = {frozenset(r['state']['queries']): set(r['target_queries']) for r in records if r['record'] == 'sample'}
    c: collections.Counter = collections.Counter()
    added: set[frozenset] = set()
    for state, n in steps:
        c['last steps'] += n
        if state in targets:
            c['matched'] += n
        elif None in state:
            c[NO_HASH] += n
        elif frozenset(state & union) not in targets:
            c[GROUND_TRUTH] += n
        elif not targets[frozenset(state & union)] - state:
            c[NO_TARGET] += n
        else:
            c['to add: last steps'] += n
            added.add(state)
    c['to add: states'] = len(added)
    c['to add: queries outside the union'] = len({h for st in added for h in st} - union)
    return dict(c)


def compare(task: str, c: dict, points: Path) -> list[str]:
    """The differences between the counts and the header's draw_counts of the task's points file; empty where there is none."""
    path = points / f'{task}.jsonl'
    if not Z.exists(path):
        return ['no points file']
    with Z.open_text(path) as f:
        header = json.loads(f.readline())
    dc = header.get('draw_counts')
    if dc is None:
        return ['the header has no draw_counts']
    bad = []
    for key, mine in (('matched', c.get('matched', 0)), ('not added: ' + GROUND_TRUTH, c.get(GROUND_TRUTH, 0)), ('not added: ' + NO_HASH, c.get(NO_HASH, 0)),
                      ('not added: ' + NO_TARGET, c.get(NO_TARGET, 0))):
        if dc.get(key, 0) != mine:
            bad.append(f'{key}: header {dc.get(key, 0)}, here {mine}')
    fixed = {'not added: ' + r for r in (GROUND_TRUTH, NO_HASH, NO_TARGET)}
    other = {k: v for k, v in dc.items() if k.startswith('not added: ') and k not in fixed}
    if dc.get('added', 0) + sum(other.values()) != c.get('to add: last steps', 0):
        bad.append(f'added {dc.get("added", 0)} + other not added {sum(other.values())} != to add {c.get("to add: last steps", 0)}')
    if dc.get('added states', 0) > c.get('to add: states', 0):
        bad.append(f'added states {dc.get("added states", 0)} > to add {c.get("to add: states", 0)}')
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
    ap.add_argument('paths', nargs='+')
    ap.add_argument('--skeleton', type=Path, required=True)
    ap.add_argument('--points', type=Path)
    args = ap.parse_args()
    files = record_files(args.paths)
    t0 = time.time()
    total: collections.Counter = collections.Counter()
    differ = 0
    for i, path in enumerate(files, 1):
        task, steps = last_steps(path)
        if not steps:
            print(json.dumps(dict(task=Path(path).parent.name, note='no sampled-query record')), flush=True)
            continue
        if not (args.skeleton / f'{task}.jsonl').exists():
            print(json.dumps(dict(task=task, note='no skeleton file', **{'last steps': sum(n for _, n in steps)})), flush=True)
            total['tasks with no skeleton file'] += 1
            continue
        c = count_task(task, steps, args.skeleton)
        total.update(c)
        line: dict = dict(task=task, **c)
        if args.points is not None:
            bad = compare(task, c, args.points)
            differ += bool(bad)
            line['check'] = bad or 'OK'
        print(json.dumps(line), flush=True)
        el = time.time() - t0
        print(f'{i}/{len(files)} files, {i / max(el, 1e-9):.1f} files/s, ETA {el / i * (len(files) - i):.0f}s', file=sys.stderr, flush=True)
    print(json.dumps(dict(task='all', **total, **({'tasks that differ': differ} if args.points is not None else {}))), flush=True)
    return 1 if differ else 0


if __name__ == '__main__':
    sys.exit(main())
