"""labelcheck.py MODEL RUN: does the relation model's score depend on the author's label names in a row's prefix? Scores each
row as is, and with each label name (after * or ^ or as a :column binding's label) renamed V0, V1, ... by first appearance."""
import re
import sys

import relsteer
from gq_pair import rows

LAB = re.compile(r'([*^])([A-Za-z_][A-Za-z0-9_]*)')
VAL = re.compile(r'(\(:[^\s()]+\s+)([*^]?)([A-Za-z_][A-Za-z0-9_]*)(?=\))')


def canon(prefix):
    """Each label bound by '*X' renamed V0, V1, ... by first binding, at every column value that names it (bound or read)."""
    m = {}
    for a in prefix:
        for g in LAB.finditer(a):
            if g.group(1) == '*':
                m.setdefault(g.group(2), 'V%d' % len(m))
    tok = re.compile(r'(?<![:&$\w])([*^]?)([A-Za-z_][A-Za-z0-9_]*)\b')
    return [tok.sub(lambda g: g.group(1) + m.get(g.group(2), g.group(2)), a) for a in prefix]


sc = relsteer.Scorer(sys.argv[1], 'hgb')
n = diff = 0
big = 0.0
for r in rows(sys.argv[2] + '/relrows.jsonl.zst'):
    if not r.get('prefix'):
        continue
    a = sc.f(r)
    b = sc.f(dict(r, prefix=canon(r['prefix'])))
    d = max(abs(x - y) for x, y in zip(a, b))
    n += 1
    if d > 1e-6 and diff < 3:
        print('changed', r['prefix'], canon(r['prefix']))
    diff += d > 1e-6
    big = max(big, d)
print('rows with a prefix', n, 'rows whose scores change', diff, 'largest change', round(big, 4))

