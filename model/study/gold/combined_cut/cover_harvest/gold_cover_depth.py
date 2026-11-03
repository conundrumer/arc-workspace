"""The harvest per depth of gold table: for each set (training, the 37, the ramp) and depth, the gold tables in the stems the harvest read, the tables a search node covered and replaced, by kind of difference, and the tries the search paid to the cover (log2 of its draw). Depth is the longest chain of gold table reads below a table in the text before the harvest: a table that reads no gold table has depth 1. With revert.jsonl present, the replaced tables of reverted stems are counted apart.

  python3 gold_cover_depth.py
"""
import collections, glob, gzip, json, math, os, re, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
HEAD = re.compile(r'\((\w+) (&[A-Za-z_0-9]+)')
LABEL = re.compile(r'&[A-Za-z_0-9]+')
SETS = ('ramp', '37', 'training')


def depths(t):
    """{label: depth} of the gold tables of the stem's text before the harvest."""
    with gzip.open(HERE + '/../view-before-harvest/' + t + '/pairs.jsonl.gz', 'rt') as f:
        ls = [x for x in json.loads(f.readline())['gold_sexp'].splitlines() if x.strip() and not x.startswith('(OUT')]
    got = {}
    for x in ls:
        lab = HEAD.match(x)[2]
        got[lab] = 1 + max((got[r] for r in set(LABEL.findall(x[HEAD.match(x).end():])) if r in got), default=0)
    return got


def band(d):
    return str(d) if d < 8 else '8+'


def main():
    sets = {}
    for p in glob.glob(HERE + '/rows-*.jsonl') + glob.glob(HERE + '/none-*.jsonl'):
        for l in open(p):
            if l.endswith('\n'):
                r = json.loads(l)
                sets.setdefault(r['stem'], r.get('set'))
    revert = {json.loads(l)['stem'] for l in open(HERE + '/revert.jsonl')} if os.path.exists(HERE + '/revert.jsonl') else set()
    kinds = {(r['stem'], r['gold']): r['kind'] for r in map(json.loads, open(HERE + '/pair-kinds.jsonl'))}
    total = collections.Counter()
    dep = {}
    for t, s in sets.items():
        if s not in SETS or not os.path.exists(HERE + '/../view-before-harvest/' + t):
            continue
        dep[t] = depths(t)
        for d in dep[t].values():
            total[s, band(d)] += 1
    got = collections.defaultdict(list)
    for l in open(HERE + '/pairs.jsonl'):
        p = json.loads(l)
        d = band(dep[p['stem']][p['gold_parts']['label']])
        got[p['set'], d].append(dict(kind=kinds[p['stem'], p['gold']], tries=math.log2(max(p['draw'], 1)), reverted=p['stem'] in revert))
    names = sorted({k for v in got.values() for k in (x['kind'] for x in v)})
    print('| Depth | ' + ' | '.join('%s: replaced / tables' % s for s in SETS) + ' | log2 tries, median, ' + ', '.join(SETS) + ' |')
    for d in sorted({d for _, d in total}, key=lambda x: (len(x), x)):
        cells = []
        for s in SETS:
            v = got[s, d]
            kept = [x for x in v if not x['reverted']]
            cells.append('%d / %d%s' % (len(kept), total[s, d], ' (%d reverted)' % (len(v) - len(kept)) if len(v) > len(kept) else ''))
        med = ['%.1f' % statistics.median(x['tries'] for x in got[s, d]) if got[s, d] else '-' for s in SETS]
        print('| %s | %s | %s |' % (d, ' | '.join(cells), ', '.join(med)))
    print()
    print('| Depth | ' + ' | '.join(names) + ' |')
    for d in sorted({d for _, d in got}, key=lambda x: (len(x), x)):
        print('| %s | %s |' % (d, ' | '.join(', '.join(str(sum(x['kind'] == k for x in got[s, d])) for s in SETS) for k in names)))


if __name__ == '__main__':
    main()
