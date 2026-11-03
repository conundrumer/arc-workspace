"""Union table counts per task set from case-counts.jsonl (`union_by_depth`), and the tasks of the training union streamed so far.

  python3 probe_sizes.py OUT.json

Sets: ramp 22 (ramp-fold.txt), the 37 (tasks.txt), the 99 (leave_out.txt, holds the 37), training (every other task of case-counts.jsonl).
"""
import json, statistics, sys

G = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union/'
H = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/held/'


def ids(f):
    return {l.strip() for l in open(H + f) if l.strip()}


def main():
    ramp, t37, t99 = ids('ramp-fold.txt'), ids('tasks.txt'), ids('leave_out.txt')
    sets = dict(ramp=[], t37=[], t99_other=[], training=[])
    cases = dict(ramp=[], t37=[], t99_other=[], training=[])
    for line in open(G + 'case-counts.jsonl'):
        r = json.loads(line)
        t = r.get('task')
        k = 'ramp' if t in ramp else 't37' if t in t37 else 't99_other' if t in t99 else 'training'
        u = r.get('union_by_depth') or {}
        sets[k].append(sum(u.values()))
        if 'cases' in r:
            cases[k].append(r['cases'])
    streamed = set()
    for f in ('union-training-0.jsonl', 'union-training-1.jsonl'):
        for line in open(G + f):
            try:
                streamed.add(json.loads(line)['task'])
            except Exception:
                pass
    out = {k: dict(tasks=len(v), union_tables=sum(v), median=statistics.median(v) if v else None,
                   cases=sum(cases[k]), cases_median=statistics.median(cases[k]) if cases[k] else None) for k, v in sets.items()}
    out['training_union_streamed_tasks'] = len(streamed)
    json.dump(out, open(sys.argv[1], 'w'), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
