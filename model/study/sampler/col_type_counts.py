#!/usr/bin/env python
"""The table COL_TYPE of sample2_col.py (ORDER_FREE=col): the chance that an atom of a derived relation names a column, by the place of the body, the column's type and whether that type is in scope.

  <runtime python> col_type_counts.py ROWS OUT.json

ROWS is a rows folder of live_rows.py (its choices.jsonl.zst). The rows used are those of phase `cols` on a declared relation. At a row, the column options are the columns
above the last one the atom names. Where gold names column j, column j is named and each option before it is passed; where gold stops, every option is passed. The rows are in
random valid orders, so `scope_types` is that of each order's walk, and a row's options and gold do not depend on P's shares: rows made under any P give the same counts.

OUT.json has `counts` ({"place|type|scoped": [named, offered]}, a column with no type under the type `None`) and the lines to paste into sample2_col.py: a rate is (named + .5) / (offered + 1)
where the key has MIN_OFFERED options offered at least; every other key takes the rate of its place and scoped, over all types.
"""
import collections
import json
import os
import re
import sys

import sampler_paths as P

sys.path.append(P.CODE)
from judge3.framed_jsonl import iter_json  # noqa: E402

MIN_OFFERED = 30  # the options a (place, type, scoped) key must have been offered to have a rate of its own


def count(path):
    """{(place, type, scoped): [named, offered]} over the declared-relation column picks of the choices file at path."""
    out = collections.defaultdict(lambda: [0, 0])
    for r in iter_json(path):
        if r.get('phase') != 'cols' or r.get('rel') != 'declared':
            continue
        last = max(map(int, re.findall(r'\(:(\d+)', r['text'])), default=-1)
        fwd = [o for o in r['options'] if o['kind'] == 'column' and int(o['tok'][1:]) > last]
        if r['gold'] != 'STOP' and int(r['gold'][1:]) <= last:  # a column named below the last one: no draw of the table
            continue
        for o in fwd:
            if r['gold'] != 'STOP' and int(o['tok'][1:]) > int(r['gold'][1:]):
                break
            c = out[r['place'], o['ctype'], o['ctype'] in r['scope_types']]
            c[0] += o['tok'] == r['gold']
            c[1] += 1
    return out


def main():
    rows, dest = sys.argv[1:3]
    counts = count(rows if rows.endswith('.zst') else os.path.join(rows, 'choices.jsonl.zst'))
    pooled = collections.defaultdict(lambda: [0, 0])
    for (place, _, scoped), (named, offered) in counts.items():
        pooled[place, scoped][0] += named
        pooled[place, scoped][1] += offered
    rate = lambda c: round((c[0] + 0.5) / (c[1] + 1), 3)  # noqa: E731
    table = {k: rate(c) for k, c in sorted(counts.items(), key=str) if c[1] >= MIN_OFFERED and k[1] is not None}
    default = {k: rate(c) for k, c in sorted(pooled.items())}
    with open(dest, 'w') as f:
        json.dump(dict(rows=rows, counts={'%s|%s|%s' % k: v for k, v in sorted(counts.items(), key=str)},
                       col_type='COL_TYPE = {%s}' % ', '.join('%r: %s' % (k, v) for k, v in table.items()),
                       col_type_default='COL_TYPE_DEFAULT = {%s}' % ', '.join('%r: %s' % (k, v) for k, v in default.items())), f, indent=1)
    print(len(counts), 'keys,', sum(c[1] for c in counts.values()), 'options offered;', len(table), 'in COL_TYPE;', dest)


if __name__ == '__main__':
    main()
