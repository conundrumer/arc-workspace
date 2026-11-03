#!/usr/bin/env python
"""Checks the bits this record pays against the census's. Stdlib, plus zstandard for the rank record's held walk.

  <runtime python> features_unread_check.py

Writes bits-check.json in this folder.
- walk: for each form of walk-held-before.jsonl, the form's total and each relation pick against census-base.jsonl, scope of all earlier forms.
- rank: for each relation pick of the rank record's held walk (RULE forms, parents scope) that the census has, q_bits against the census's relation bits, parents scope.
"""
import collections
import io
import json
import os

import features_unread_lib as L

HERE = os.path.dirname(os.path.abspath(__file__)) + '/'


def census():
    out = {}
    for x in open(L.BASE + 'census-base.jsonl'):
        r = json.loads(x)
        out[(r['task'], r['line'], r['scope'])] = r
    return out


def picks_of(r):
    """The relation bits of a census row, in pick order: for each atom the op pick, then the relation pick."""
    out = []
    for d in r['detail']:
        for k in ('relation (op)', 'relation'):
            if k in d['cur']:
                out.append(d['cur'][k])
    return out


def compare(rows, cen, scope):
    n = c = 0
    forms = fsame = 0
    worst = []
    for task, line, total, got in rows:
        r = cen[(task, line, scope)]
        want = picks_of(r)
        forms += 1
        if total is not None and abs(total - r['total']) < 0.011:
            fsame += 1
        elif total is not None:
            worst.append((task, line, total, r['total']))
        for a, b in zip(got, want):
            n += 1
            d = abs(a - b)
            c += d <= 0.0011
            if d > 0.0011:
                worst.append((task, line, a, b))
        if len(got) != len(want):
            worst.append((task, line, 'picks', len(got), len(want)))
    return dict(forms=forms, form_total_equal=fsame, picks=n, picks_equal_to_001=c, differ=worst[:40], differ_count=len(worst))


def main():
    cen = census()
    out = {}
    path = HERE + 'walk-held-before.jsonl'
    if os.path.exists(path):
        rows = []
        for x in open(path):
            r = json.loads(x)
            if r.get('error'):
                continue
            rows.append((r['task'], r['line'], r['total'], [p['q_bits'] for p in r['picks']]))
        out['walk'] = compare(rows, cen, 'before')
    import zstandard
    forms = collections.OrderedDict()
    with open(L.RANK + 'walks/features-walk-held-0of1.jsonl.zst', 'rb') as f:
        for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f, read_across_frames=True), encoding='utf8'):
            if line.startswith('{"rec": "form"'):
                d = json.loads(line)
                forms.setdefault((d['task'], d['line']), dict(total=d['total'], picks=[]))['total'] = d['total']
            elif line.startswith('{"rec": "rel"'):
                d = json.loads(line)
                forms.setdefault((d['task'], d['line']), dict(total=None, picks=[]))['picks'].append(d['q_bits'])
    out['rank'] = compare([(t, i, v['total'], v['picks']) for (t, i), v in forms.items()], cen, 'parents')
    json.dump(out, open(HERE + 'bits-check.json', 'w'), indent=1)
    print({k: {x: y for x, y in v.items() if x != 'differ'} for k, v in out.items()})
    print({k: v['differ'][:6] for k, v in out.items()})


if __name__ == '__main__':
    main()
