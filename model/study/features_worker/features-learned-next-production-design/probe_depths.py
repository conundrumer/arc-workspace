"""Gold tables per depth of a set's union graph (graph-tables-SET.jsonl), with OR tables, root DETs and kit-unreachable tables per depth, and productions per depth with their bits (graph-prods-SET.jsonl).

  python3 probe_depths.py SET OUT.json

Depth 5 and up are pooled as 5+.
"""
import collections, json, statistics, sys

G = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union/'


def band(d):
    return '5+' if d is None or d >= 5 else str(d)


def main():
    s, out = sys.argv[1], sys.argv[2]
    tab = collections.defaultdict(collections.Counter)
    for line in open(G + 'graph-tables-%s.jsonl' % s):
        t = json.loads(line)
        b = band(t.get('depth'))
        tab[b]['tables'] += 1
        tab[b]['or_tables'] += t.get('productions', 0) > 1
        tab[b]['root_det'] += bool(t.get('root_det'))
        tab[b]['kit_unreachable'] += bool(t.get('kit_unreachable'))
    bits = collections.defaultdict(list)
    nobits = collections.Counter()
    for line in open(G + 'graph-prods-%s.jsonl' % s):
        p = json.loads(line)
        b = band(p.get('depth'))
        if p.get('bits') is None:
            nobits[b] += 1
        else:
            bits[b].append(p['bits'])
    res = {}
    for b in sorted(set(tab) | set(bits)):
        xs = sorted(bits[b])
        res[b] = dict(tab[b], productions=len(xs) + nobits[b], productions_without_bits=nobits[b],
                      bits_median=round(statistics.median(xs), 2) if xs else None,
                      bits_p90=round(xs[int(.9 * len(xs))], 2) if xs else None)
    json.dump(res, open(out, 'w'), indent=1)
    print(json.dumps(res))


if __name__ == '__main__':
    main()
