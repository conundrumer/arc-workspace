"""Dev labeling layer: for each family of postconditions, how often it is falsifiable on claims and on plumbing, over tasks.

    python3 families.py TASK [TASK ...]

A table counts for a family where the family has a tested postcondition on it, and as falsifiable where one of those is new or redundant.
"""
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

OUTDIR = Path(os.environ.get('CONTRACTS_OUT', Path(__file__).parent / 'out'))
FAMILIES = [
    ('empty', r'^empty$'),
    ('one row', r'^one row$'),
    ('rows', r'^rows$'),
    ('covers the grid', r' covers the grid$'),
    ('key determines the row', r'^key determines the row$'),
    ('column determines column', r' determines '),
    ('distinct values', r' distinct$'),
    ('number range', r' (min|max|top-two ratio)$'),
    ('cell count', r' cells$'),
    ('components', r' components'),
    ('shape (line, edge, region)', r' (on one line|touches the grid edge|outside is one region)$'),
    ('bounding box', r' bounding box | (shorter side min|longer side max|every box is square|share of the grid|more than one cell along each axis|is the whole grid)$'),
    ('per group', r' per group of '),
    ('least distance', r' least distance '),
    ('relation to another table', r' (vs &|vs input|on the boundary of|neighbors in|inside &|on the border of|distance from the middle)'),
    ('relation to the train output', r' (vs the changed cells|overlap with the changed cells|is the set of painted colors|within the output colors|overlap with the output cells)$'),
]
c = Counter()
for task in sys.argv[1:]:
    p = OUTDIR / (task + '.verdicts.post.json')
    if not p.exists():
        continue
    for t, r in json.load(open(p)).items():
        if r['reading'] is None:
            continue
        reading = 'claim' if r['reading'] == 'claim' else 'plumbing'
        for fam, pat in FAMILIES:
            vs = [v['verdict'] for k, v in r['postconditions'].items() if re.search(pat, k.split('|', 1)[1]) and v['verdict'] != 'untested']
            if vs:
                c[fam, reading, 'tested'] += 1
                c[fam, reading, 'falsifiable'] += any(v in ('new', 'redundant') for v in vs)
                c[fam, reading, 'new'] += any(v == 'new' for v in vs)
print('%-30s %-26s %-26s %s' % ('family', 'claims falsifiable', 'plumbing falsifiable', 'ratio'))
for fam, _ in FAMILIES:
    a, n = c[fam, 'claim', 'falsifiable'], c[fam, 'claim', 'tested']
    b, m = c[fam, 'plumbing', 'falsifiable'], c[fam, 'plumbing', 'tested']
    if n or m:
        ra, rb = a / max(1, n), b / max(1, m)
        print('%-30s %3d of %3d (%3.0f%%)          %3d of %3d (%3.0f%%)          %s' % (fam, a, n, 100 * ra, b, m, 100 * rb, '%.1f' % (ra / rb) if rb else 'inf'))
