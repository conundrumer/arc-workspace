"""The fit of features_port_fit.py, with the gain at beta 2 split by place and by keyed or free, and the median gain per form at each form's deepest ranked prefix.

  features_port_split.py ROWS_DIR HELD_FORMS
"""
import collections, runpy, statistics as st, sys
g = runpy.run_path('features_port_fit.py')
res, te = g['res'], g['te']
rows = []
for r in te:
    gold = [x for x in r['rows'] if x['src'] == 'gold' and x['logq'] is not None and 's' in x]
    deep = None
    for x in gold:
        pool = [y for y in r['rows'] if y['src'] == 'search' and y['place'] == x['place'] and y['atoms'] == x['atoms'] and y['logq'] is not None]
        if len(pool) < 2:
            continue
        rk = lambda b: 1 + sum(y['logq'] + b * y['s'] > x['logq'] + b * x['s'] for y in pool)
        import math
        d = math.log2(rk(0)) - math.log2(rk(2))
        rows.append((x['place'], x['keyed'], x['atoms'], d, r['task'], r['line']))
        if deep is None or x['atoms'] >= deep[0]:
            deep = (x['atoms'], d)
    if deep:
        rows.append(('deep', None, deep[0], deep[1], r['task'], r['line']))
for name, f in (('key', lambda x: x[0] == 'key'), ('port keyed', lambda x: x[0] == 'port' and x[1]), ('port free', lambda x: x[0] == 'port' and not x[1]), ('deepest per form', lambda x: x[0] == 'deep')):
    v = [x[3] for x in rows if f(x)]
    if v:
        print(name, 'n', len(v), 'mean', round(sum(v) / len(v), 2), 'median', round(st.median(v), 2), 'better', sum(a > 0 for a in v), 'worse', sum(a < 0 for a in v))
import pickle
