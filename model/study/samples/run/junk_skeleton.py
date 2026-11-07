#!/usr/bin/env python
"""junk_skeleton.py OUT SPLIT RUN [RUN ...] [--states K] [--seed S]: skeleton files whose samples are small states like those a search visits: the closure of a target query, with queries the search draws in many tasks that read no query.

RUN folders hold the draw records of train tasks. A query counts as drawn in a task when a draw of that task has it, reading no query, with no QueryHash of the task's union. The queries drawn in at least MIN_TASKS tasks are the list; a state takes 2 to 6 of them by their counts. Up to K states per task, half of them over a closure of at most SMALL queries where the task has them. A state's targets are every query with a non-empty closure inside the state's union queries, not in the state. `points_write.py SPLIT --skeleton OUT --samples-per-task 0` writes the points."""
import argparse, sys, collections, hashlib, json, random, re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from study_paths import DATA_ROOT  # noqa: E402

SAMPLES = DATA_ROOT / 'samples'
OWN = re.compile(r'^\((\w+) &f(\d+)')
NAME = re.compile(r'&f\d+')
MIN_TASKS, SMALL = 4, 4


def junk_list(runs):
    counts = collections.Counter()
    for run in map(Path, runs):
        for r in map(json.loads, open(run / 'results.jsonl')):
            path = SAMPLES / 'train' / 'skeleton' / f"{r['task']}.jsonl"
            draws = run / 'jobs' / r['job'] / 'draws.jsonl'
            if not path.exists() or not draws.exists():
                continue
            gold = {json.loads(x)['hash'] for x in open(path) if x.startswith('{"record": "query"')}
            here = set()
            for line in open(draws):
                d = json.loads(line)
                if 'steps' not in d:
                    continue
                s = d['steps'][-1]
                m = OWN.match(s['text'])
                if m is None or s['query_hash'] in gold or m.group(1) not in ('RULE', 'DET', 'INIT') or len(set(NAME.findall(s['text']))) != 1:
                    continue
                if d.get('result') in ('new', 'equal'):
                    here.add(NAME.sub('&r0', s['text']))
            counts.update(here)
    return [(t, n) for t, n in counts.most_common() if n >= MIN_TASKS]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('out'); ap.add_argument('split'); ap.add_argument('runs', nargs='+'); ap.add_argument('--states', type=int, default=6); ap.add_argument('--seed', type=int, default=0)
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    junk = junk_list(a.runs)
    print(len(junk), 'queries in the list; the first:', junk[:6], flush=True)
    (out.parent / (out.name + '.junk.json')).write_text(json.dumps(junk))
    texts = [t for t, _ in junk]
    weights = [n for _, n in junk]
    tot = collections.Counter()
    for path in sorted((SAMPLES / a.split / 'skeleton').glob('*.jsonl')):
        task = path.stem
        records = [json.loads(x) for x in path.read_text().splitlines()]
        queries = {r['hash']: r for r in records if r['record'] == 'query'}
        samples = [r for r in records if r['record'] == 'sample']
        targets = sorted({t for s in samples for t in s['target_queries'] if queries[t]['closure']})
        closure = {h: set(q['closure']) for h, q in queries.items()}
        rng = random.Random(f'{a.seed}:{task}')
        rng.shuffle(targets)
        small = [t for t in targets if len(closure[t]) <= SMALL]
        picked, seen = [], set()
        for t in small[:a.states // 2] + targets:
            if len(picked) >= a.states:
                break
            key = frozenset(closure[t])
            if key not in seen:
                seen.add(key)
                picked.append(t)
        extra, made = {}, []
        for t in picked:
            gold = closure[t]
            chosen = set()
            for _ in range(rng.randint(2, 6)):
                chosen.add(rng.choices(texts, weights)[0])
            ids = {}
            for text in chosen:
                h = hashlib.sha256(text.encode()).hexdigest()[:32]
                ids[h] = text
                extra[h] = dict(record='query', hash=h, kind=OWN.match(text.replace('&r0', '&f0')).group(1), hash_exact=False, body_exact=False, body='', body_decodes=None, inputs=[], outputs=[], graph_tables={}, graph_queries=[], program=[text], closure=[], off_union=True)
            state = sorted(gold) + sorted(ids)
            aim = sorted(x for x in targets if x not in gold and closure[x] <= gold)
            state_id = hashlib.sha256(json.dumps(sorted(state)).encode()).hexdigest()[:32]
            made.append(dict(record='sample', id=hashlib.sha256(f'junk:{task}:{state_id}'.encode()).hexdigest()[:32], task=task, split=records[0]['split'], eval_only=False, off_union=len(ids), state=dict(id=state_id, queries=state),
                             target_queries=aim, target_tables=[], refused_target_queries=0, no_progress_queries=0, frontier_depth=0))
            tot['size'] += len(state); tot['targets'] += len(aim); tot['gold'] += len(gold)
        tot['tasks'] += 1; tot['samples'] += len(made)
        if made:
            with (out / f'{task}.jsonl').open('w') as f:
                f.write(json.dumps(dict(records[0], samples=len(made))) + '\n')
                for r in list(queries.values()) + list(extra.values()) + made:
                    f.write(json.dumps(r) + '\n')
    print(dict(tot), 'mean size %.1f, gold share %.2f' % (tot['size'] / max(tot['samples'], 1), tot['gold'] / max(tot['size'], 1)))


if __name__ == '__main__':
    main()
