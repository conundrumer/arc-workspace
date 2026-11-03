"""Counts of the cover harvest by task set, on the census figures of Bits.whole: stems taken, gold forms replaced and removed, forms brought in, bits cut by sum and by worst form, and stems whose worst form crosses under a bar.

  python3 gold_cover_count.py
"""
import collections, glob, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
BARS = (13, 18, 21.5, 25, 28, 32)

rows = {}
for p in sorted(glob.glob(HERE + '/rows-*.jsonl')):
    for l in open(p):
        if l.endswith('\n'):
            r = json.loads(l)
            rows[r['stem']] = r
done = set(rows)
for p in glob.glob(HERE + '/none-*.jsonl'):
    done |= {json.loads(l)['stem'] for l in open(p) if l.endswith('\n')}

c = collections.defaultdict(collections.Counter)
for t, r in rows.items():
    s = r.get('set', '?')
    c[s]['rows'] += 1
    c[s]['set aside'] += bool(r.get('set_aside'))
    c[s]['time cap'] += bool(r.get('time_cap'))
    if not r.get('taken'):
        continue
    b, a = r['before'], r['after']
    stood = [v for v in r['verdicts'] if v['verdict'].startswith('stands')]
    c[s]['taken'] += 1
    c[s]['gold forms covered'] += len(stood)
    c[s]['gold forms removed'] += sum(len(v.get('removed', [])) for v in stood)
    c[s]['forms brought in'] += sum(len(v.get('brought', [])) for v in stood)
    c[s]['sum cut'] += b['sum'] - a['sum']
    c[s]['worst cut'] += b['worst'] - a['worst']
    c[s]['worst lower'] += a['worst'] < b['worst']
    c[s]['sum higher'] += a['sum'] > b['sum']
    c[s]['undrawable fewer'] += len(a['undrawable']) < len(b['undrawable'])
    for x in BARS:
        c[s]['under %s' % x] += a['worst'] <= x < b['worst']

print('stems with a row or a none line:', len(done))
for s in sorted(c):
    print(s, {k: round(v, 1) for k, v in c[s].items()})
