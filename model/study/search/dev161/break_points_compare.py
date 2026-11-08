"""break_points_compare.py A B [--tasks T,T] [--all] [--b-tol X]

Two outputs of break_points.py (A and B, each OUT or OUT.zst, and the OUT-shard* files of each) over the same jobs. The jobs are taken in the order of A, matched to B by the job's name; for each,
its tables are taken in the order of A's line, matched to B by graph table. The comparison stops at the first table where the class, the bits b or the production differs, and prints that table's
line in A and in B. The counts follow.

  class       the field cls
  b           the field b (None where b is infinite), differing by more than --b-tol (default 0, the output's rounding)
  production  the QueryHash of the production that was scored (field query) where both lines have it, else the text of the production (field text, its first 160 characters; an output
              of an older break_points.py has no field query); a table with no production scored (class 0, 1, 2 or x) has none, and differs from one that has
Where a field is the one that differs, the line says which. --all goes on to the end and counts every difference without printing the lines (the first 5 of each kind are printed).

Run with any Python that reads zstd (the study runtime python):  PY -I break_points_compare.py A B
"""
import argparse
import collections
import io
import json
import subprocess
import sys
from pathlib import Path


def read_lines(out):
    """The JSON lines of OUT and of OUT-shard* (each plain or .zst), as break_points.read_lines reads them."""
    base = Path(out[:-4] if out.endswith('.zst') else out)
    names = [base] + sorted({Path(p[:-4] if p.endswith('.zst') else p) for p in map(str, base.parent.glob(base.name + '-shard*'))})
    for n in names:
        for p in (Path(str(n) + '.zst'), n):
            if p.exists():
                if p.suffix == '.zst':
                    text = io.TextIOWrapper(io.BytesIO(subprocess.run(['zstd', '-dcq', str(p)], capture_output=True, check=True).stdout), encoding='utf-8')
                else:
                    text = open(p, encoding='utf-8')
                for l in text:
                    if l.strip():
                        yield json.loads(l)
                break


def jobs_of(out):
    got = {}
    for j in read_lines(out):
        got[j['job']] = j
    return got


def same_production(ta, tb):
    """Whether two lines of one graph table scored the same production: the same QueryHash where both lines have it, else the same text (None for both where none was scored)."""
    if ta.get('query') and tb.get('query'):
        return ta['query'] == tb['query']
    return ta.get('text') == tb.get('text')


def differs(ta, tb, tol):
    """The fields in which two lines of one graph table differ: a list of 'class', 'b', 'production'."""
    out = []
    if ta['cls'] != tb['cls']:
        out.append('class')
    ba, bb = ta.get('b'), tb.get('b')
    if (ba is None) != (bb is None) or (ba is not None and abs(ba - bb) > tol) or bool(ta.get('b_inf')) != bool(tb.get('b_inf')):
        out.append('b')
    if not same_production(ta, tb):
        out.append('production')
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('a')
    ap.add_argument('b')
    ap.add_argument('--tasks')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--b-tol', type=float, default=0.0)
    a = ap.parse_args()
    A, B = jobs_of(a.a), jobs_of(a.b)
    want = set(a.tasks.split(',')) if a.tasks else None
    c = collections.Counter()
    c['jobs in A'], c['jobs in B'] = len(A), len(B)
    for k in ('jobs compared', 'tables compared', 'tables equal', 'tables that differ', 'differ in class', 'differ in b', 'differ in production'):
        c[k] += 0
    shown = collections.Counter()
    stop = None
    for name, ja in A.items():
        if want and ja['task'] not in want:
            continue
        jb = B.get(name)
        if jb is None:
            c['jobs of A not in B'] += 1
            continue
        c['jobs compared'] += 1
        tb = {t['t']: t for t in jb['tables']}
        for ta in ja['tables']:
            b = tb.get(ta['t'])
            if b is None:
                c['tables of A not in B'] += 1
                kinds = ['table missing in B']
            else:
                kinds = differs(ta, b, a.b_tol)
                c['tables compared'] += 1
            if not kinds:
                c['tables equal'] += 1
                continue
            for k in kinds:
                c['differ in ' + k] += 1
            c['tables that differ'] += 1
            key = '+'.join(kinds)
            if not a.all:
                stop = (name, ta, b, kinds)
                break
            if shown[key] < 5:
                shown[key] += 1
                print('--- differ in %s: job %s table %s' % (key, name, ta['t']))
                print('A', json.dumps(ta, sort_keys=True))
                print('B', json.dumps(b, sort_keys=True))
        if stop:
            break
    c['jobs of B not in A'] = len(set(B) - set(A) - ({n for n, j in B.items() if want and j['task'] not in want}))
    if stop:
        name, ta, b, kinds = stop
        print('FIRST DIFFERENCE, in %s: job %s table %s' % (' and '.join(kinds), name, ta['t']))
        print('A', json.dumps(ta, sort_keys=True))
        print('B', json.dumps(b, sort_keys=True))
    else:
        print('NO DIFFERENCE' if not c['tables that differ'] and not c['tables of A not in B'] else 'differences counted above')
    print('counts (stopped at the first difference: %s):' % ('yes' if stop else 'no'))
    for k, v in c.items():
        print('%8d  %s' % (v, k))
    sys.exit(1 if stop or c['tables that differ'] else 0)


if __name__ == '__main__':
    main()
