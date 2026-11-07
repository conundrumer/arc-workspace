#!/usr/bin/env python
"""off_skeleton.py SKELETON_OUT SPLIT RUN [RUN ...] [--states K] [--seed S]: a skeleton file per task whose samples are the states that a recorded search visited.

For each task with draw records in a run of dev_run.py, it takes up to K distinct non-empty states of the draws' last steps (docs/sample-build/training-rows.md, "States off the samples"). A state's queries that the union holds are its gold part. Its targets are the union's target queries that aren't in the state and whose closure lies in the gold part. A query outside the union becomes a query record whose program is its text with local labels, and whose closure comes from what its text reads in the draw. `points_write.py SPLIT --skeleton SKELETON_OUT --samples-per-task 0` then writes the points."""
import argparse, collections, hashlib, json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'search/dev161'))
import draw_file  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from study_paths import DATA_ROOT  # noqa: E402

SAMPLES = DATA_ROOT / 'samples'
NAME = re.compile(r'&f(\d+)')
OWN = re.compile(r'^\((\w+) &f(\d+)')


def step_records(steps, known):
    """{hash: query record} for the steps outside the union, or None where a step can't be replayed from its text."""
    by_name, deps, out = {}, {}, {}
    for s in steps:
        m = OWN.match(s['text'])
        if s['query_hash'] is None or m is None or m.group(1) in ('RIGID_DET', 'DEMONSTRATED'):
            return None
        by_name[m.group(2)] = s['query_hash']
    closure_of = {}
    for s in steps:
        h = s['query_hash']
        own = OWN.match(s['text']).group(2)
        reads = {n for n in NAME.findall(s['text']) if n != own}
        if any(n not in by_name for n in reads):
            return None
        above = set()
        for n in reads:
            r = by_name[n]
            above |= closure_of[r] | {r}
        closure_of[h] = above
        if h in known:
            continue
        order = [x['query_hash'] for x in steps if x['query_hash'] in above]
        local = {n: order.index(by_name[n]) for n in reads}
        text = NAME.sub(lambda m: '&r%d' % (len(order) if m.group(1) == own else local[m.group(1)]), s['text'])
        out[h] = dict(record='query', hash=h, kind=OWN.match(s['text']).group(1), hash_exact=False, body_exact=False, body='', body_decodes=None, inputs=[], outputs=[], graph_tables={}, graph_queries=[],
                      program=[''] * len(order) + [text], closure=order, off_union=True)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('split'); ap.add_argument('runs', nargs='+'); ap.add_argument('--states', type=int, default=12); ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    jobs = {}
    for run in map(Path, a.runs):
        for r in map(json.loads, open(run / 'results.jsonl')):
            if r['arm'] in ('tree', 'tok', 'fast'):
                jobs.setdefault(r['task'], run / 'jobs' / r['job'])
    totals = collections.Counter()
    for task, job in sorted(jobs.items()):
        path = SAMPLES / a.split / 'skeleton' / f'{task}.jsonl'
        if not path.exists() or not draw_file.has_draws(job):
            totals['no skeleton or draws'] += 1
            continue
        records = [json.loads(x) for x in path.read_text().splitlines()]
        queries = {r['hash']: r for r in records if r['record'] == 'query'}
        samples = [r for r in records if r['record'] == 'sample']
        targets = {t for s in samples for t in s['target_queries']}
        closure = {h: set(q['closure']) for h, q in queries.items()}
        states = {}
        for line in open(draws):
            d = json.loads(line)
            if 'steps' not in d or len(d['steps']) < 2:
                continue
            steps = d['steps'][:-1]
            key = tuple(s['query_hash'] for s in steps)
            if None not in key and key not in states:
                states[key] = steps
        keep = sorted(states, key=lambda k: hashlib.sha256(f'{a.seed}:{task}:{k}'.encode()).hexdigest())
        # Two thirds of a task's states, where it has them, hold a query of the union; a state with none of them gives only targets that read no query.
        keep = [k for k in keep if set(k) & set(queries)]
        extra, made = {}, []
        for key in keep:
            if len(made) >= a.states:
                break
            got = step_records(states[key], queries)
            if got is None:
                totals['states with a step that does not replay'] += 1
                continue
            state = set(key)
            gold = state & set(queries)
            if any(not closure[h] <= gold for h in gold):
                totals['states whose gold queries lack their closure'] += 1
                continue
            aim = sorted(t for t in targets if t not in state and closure[t] <= gold and closure[t])  # a query that reads none of the state belongs to the empty state
            if not aim:
                totals['states with no target'] += 1
                continue
            extra.update(got)
            totals['gold share'] += len(gold) / len(state)
            totals['size'] += len(state)
            state_id = hashlib.sha256(json.dumps(sorted(state)).encode()).hexdigest()[:32]
            made.append(dict(record='sample', id=hashlib.sha256(f'off:{task}:{state_id}'.encode()).hexdigest()[:32], task=task, split=records[0]['split'], eval_only=False, off_union=len(state) - len(gold),
                             state=dict(id=state_id, queries=sorted(state)), target_queries=aim, target_tables=[], refused_target_queries=0, no_progress_queries=0, frontier_depth=0))
        totals['tasks'] += 1
        totals['samples'] += len(made)
        totals['queries outside the union'] += len(extra)
        totals['targets'] += sum(len(s['target_queries']) for s in made)
        if made:
            with (out / f'{task}.jsonl').open('w') as f:
                f.write(json.dumps(dict(records[0], samples=len(made))) + '\n')
                for r in list(queries.values()) + list(extra.values()) + made:
                    f.write(json.dumps(r) + '\n')
    print(dict(totals))
    print('mean gold share of a state %.3f, mean size %.1f' % (totals['gold share'] / max(totals['samples'], 1), totals['size'] / max(totals['samples'], 1)))


if __name__ == '__main__':
    main()
