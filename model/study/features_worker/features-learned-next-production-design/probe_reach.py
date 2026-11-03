"""Reach per depth of the union graph's tables, summed over tasks, per job and time, from reach-SET.jsonl.

  python3 probe_reach.py SET OUT.json

Per (job, seconds): tasks, and per depth (5 and up pooled) the tables, reached and read past summed over the tasks.
"""
import collections, json, sys

G = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union/'


def main():
    s, out = sys.argv[1], sys.argv[2]
    agg = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    ntask = collections.Counter()
    for line in open(G + 'reach-%s.jsonl' % s):
        r = json.loads(line)
        k = '%s @ %ss' % (r.get('job'), r.get('seconds'))
        ntask[k] += 1
        for d, c in (r.get('per') or {}).items():
            b = '5+' if int(d) >= 5 else d
            for f in ('tables', 'reached', 'read_past'):
                agg[k][b][f] += c.get(f, 0)
    res = {k: dict(tasks=ntask[k], per={b: dict(agg[k][b]) for b in sorted(agg[k])}) for k in sorted(agg)}
    json.dump(res, open(out, 'w'), indent=1)
    for k, v in res.items():
        print(k, v['tasks'], ' '.join('%s:%d/%d+%d' % (b, c['reached'], c['tables'], c['read_past']) for b, c in v['per'].items()))


if __name__ == '__main__':
    main()
