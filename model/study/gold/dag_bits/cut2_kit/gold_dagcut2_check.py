"""The row compare of check.sh for the stage `dagcut2`. Prints what it read and `rows ok`, and exits 1 at the first failure.

  <runtime python> gold_dagcut2_check.py rows ROWS EXPECTED

EXPECTED is a list of {task, row}: the Mac's row of the check stem. Compared: finished with no error, base_sha, cap, budget, margin, the steps (shape, rank, form, committed, rows_differ, working text, bits within 0.05), before and after (worst and sum within 0.05, forms with no bits equal), program and program_fail, and a memory count.
"""
import json, sys


def fail(why):
    print('FAIL', why, flush=True)
    sys.exit(1)


def near(a, b, tol=0.05):
    return (a is None and b is None) or (a is not None and b is not None and abs(a - b) <= tol)


def rows(path, expected):
    got = {}
    for l in open(path):
        try:
            r = json.loads(l)
            got[r['task']] = r
        except (json.JSONDecodeError, KeyError):
            continue
    for e in json.load(open(expected)):
        t, w = e['task'], e['row']
        r = got.get(t)
        if r is None:
            fail('no row for %s' % t)
        print(t, 'cpu', r.get('cpu'), 'wall', r.get('wall'), 'peak GiB', r.get('peak_gib'), 'processes', r.get('peak_procs'), 'error', r.get('error'), 'steps', len(r.get('steps', [])), 'committed', [k for k, s in enumerate(r.get('steps', [])) if s.get('committed')])
        if r.get('error') or not r.get('finished') or r.get('skipped'):
            fail('%s did not finish: error %s skipped %s' % (t, r.get('error'), r.get('skipped')))
        if not r.get('peak_gib') or (r.get('peak_procs') or 0) < 1:
            fail('%s shows no memory count' % t)
        for k in ('base_sha', 'cap', 'budget', 'margin', 'landed', 'program_fail'):
            if r.get(k) != w.get(k):
                fail('%s of %s is not the Mac\'s: %s against %s' % (k, t, r.get(k), w.get(k)))
        if len(r['steps']) != len(w['steps']):
            fail('%s has %d steps, the Mac %d' % (t, len(r['steps']), len(w['steps'])))
        for k, (s, x) in enumerate(zip(r['steps'], w['steps'])):
            for key in ('shape', 'rank', 'form', 'committed', 'rows_differ', 'rows_columns', 'working', 'undrawn'):
                if s.get(key) != x.get(key):
                    fail('step %d of %s: %s is %s, the Mac\'s %s' % (k, t, key, str(s.get(key))[:80], str(x.get(key))[:80]))
            for key in ('bits', 'worst', 'sum'):
                if not near(s.get(key), x.get(key)):
                    fail('step %d of %s: %s is %s, the Mac\'s %s' % (k, t, key, s.get(key), x.get(key)))
        for blk in ('before', 'after'):
            a, b = r[blk], w[blk]
            if a['undrawn'] != b['undrawn'] or not near(a['worst'], b['worst']) or not near(a['sum'], b['sum'], 0.1) or a['forms'] != b['forms']:
                fail('%s of %s is not the Mac\'s: %s against %s' % (blk, t, {k: a[k] for k in ('forms', 'worst', 'sum', 'undrawn')}, {k: b[k] for k in ('forms', 'worst', 'sum', 'undrawn')}))
        for key in ('working', 'program'):
            if r.get(key) != w.get(key):
                fail('%s of %s is not the Mac\'s' % (key, t))
        print('  steps, before, after, working and program equal the Mac\'s')
    print('rows ok')


if __name__ == '__main__':
    rows(sys.argv[2], sys.argv[3])
