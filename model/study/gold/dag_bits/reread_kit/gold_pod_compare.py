"""Compares pod rows with dag-kit rows (gold_dag_bits.py), form by form, for the stems that both hold.

  python3 gold_pod_compare.py POD_ROWS.jsonl OLD_ROWS_GLOB [STEM ...]

Both tools read the same text, the same priors and the same canonical scope idea. They differ in the sampler (master e1434cf72 against 9467760e0a14), in the cap (256 against 120), and in how a scope's relation column order is set (or_q.sorted_fields against gold_dag_bits.portsort). So the figures of a form are compared on forms that both give as `exact` or `one`: the gap is read against work/measures.md, "Spread": an ancestor's canonical order moves a reader's bits by a median of 0, a mean of +0.12, over 1 bit on 42 of 200 forms and over 3 bits on 8 of 200, and a gap under about 3 bits is not a read.
Prints, by stem, the forms compared, the gaps' median, mean and maximum, the counts of gaps over 0.05, 1 and 3 bits, and each form over 0.05 bits; and the statuses of the old rows against the new rows. Counts forms of status `none` in the old rows and in the new rows, and the lines that differ.
"""
import collections, glob, json, statistics, sys


def rows(paths):
    out = {}
    for p in paths:
        for l in open(p):
            try:
                r = json.loads(l)
            except json.JSONDecodeError:
                continue
            out[r['task']] = r
    return out


def main():
    new, old = rows([sys.argv[1]]), rows(glob.glob(sys.argv[2]))
    stems = sys.argv[3:] or sorted(set(new) & set(old))
    tot = collections.Counter()
    for t in stems:
        n, o = {f['line']: f for f in new[t]['forms']}, {f['line']: f for f in old[t]['forms']}
        gaps, notes = [], []
        for i in sorted(n):
            a, b = n[i], o.get(i)
            if b is None:
                continue
            tot['old none'] += b['status'] == 'none'
            tot['new none'] += a['status'] == 'none'
            if (b['status'] == 'none') != (a['status'] == 'none'):
                tot['none differs'] += 1
                notes.append('line %d: none in %s' % (i, 'old' if b['status'] == 'none' else 'new'))
            if b['status'] in ('exact', 'one') and a['status'] in ('exact', 'one') and a['bits'] is not None and b['bits'] is not None:
                g = a['bits'] - b['bits']
                gaps.append(g)
                if abs(g) > 0.05:
                    notes.append('line %d %s %s/%s: new %.3f old %.3f gap %+.3f (orders %s/%s)' % (i, a['kind'], a['status'], b['status'], a['bits'], b['bits'], g, a['orders'], b['orders']))
        stat = collections.Counter((o[i]['status'], n[i]['status']) for i in n if i in o)
        print('%s: %d forms, %d compared on exact/one; gap median %+.3f mean %+.3f max |gap| %.3f; over 0.05: %d, over 1: %d, over 3: %d' % (
            t, len(n), len(gaps), statistics.median(gaps) if gaps else 0, statistics.mean(gaps) if gaps else 0, max((abs(g) for g in gaps), default=0), sum(abs(g) > 0.05 for g in gaps), sum(abs(g) > 1 for g in gaps), sum(abs(g) > 3 for g in gaps)))
        print('  statuses (old, new):', dict(stat))
        for x in notes:
            print('  ', x)
        tot['compared'] += len(gaps)
        tot['over 0.05'] += sum(abs(g) > 0.05 for g in gaps)
        tot['over 1'] += sum(abs(g) > 1 for g in gaps)
        tot['over 3'] += sum(abs(g) > 3 for g in gaps)
    print('all:', dict(tot))


if __name__ == '__main__':
    main()
