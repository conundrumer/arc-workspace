#!/usr/bin/env python
"""The factor `key_rel` of the priors (live.py, KEY_IDENT=rel): how much likelier a declared relation with an Ident column is at an atom start of an INIT's key body than P says.

  <runtime python> key_rel_counts.py ROWS_DIR [ROWS_DIR ...] PRIORS_IN PRIORS_OUT [--leave-out FILE] [--score ROWS_DIR]

Each ROWS_DIR is a rows folder of live_rows.py. Its relrows rows of place `key` and phase `root` give, at each atom start of gold's key bodies, the options with P's shares and gold's pick. A row counts when
no label in its scope has the type Ident and an option is a declared relation with an Ident column. With p the P share on those options and g whether gold is one of them, the factor m on their
weights is the one that makes the sum of g less m p / (m p + 1 - p) zero (a one-parameter likelihood). PRIORS_OUT is PRIORS_IN with
`key_rel`, {'Ident': dict(m, rows, forms, gold_share, p_share, bits_before, bits_after, rows_dirs, commit)}: the bits are gold's pick, the mean over the rows, under P and under P with m. The rows leave out
the leave-out tasks (a file of tasks, one a line), which a fold holds back.
--score ROWS_DIR reads another rows folder and prints the change in bits of gold's key atoms that m makes: the mean per form that has a key, per INIT form, and the count of INIT forms it touches. A form
with several orders gives the mean over its orders.
"""
import argparse
import collections
import json
import math
import os
import pickle
import subprocess
import sys

import sampler_paths  # noqa: F401
from judge3.framed_jsonl import iter_json


def ident_rows(folder, leave=()):
    """(task, form, order, p, g, p_gold) of the rows of the folder's relrows that m acts on: p the P share on the declared relations with an Ident column, g whether gold is one of them, p_gold gold's P share (None: gold is no option)."""
    for r in iter_json(folder + '/relrows.jsonl.zst'):
        if r.get('place') != 'key' or r['phase'] != 'root' or r['task'] in leave or any(str(t) == 'Ident' for t in r['scope']):
            continue
        ident = [o for o in r['options'] if o['kind'] == 'derived' and any(str(t) == 'Ident' for t in o.get('types') or ())]
        if not ident:
            continue
        total = sum(o['p'] for o in r['options']) or 1.0
        gold = next((o['p'] / total for o in r['options'] if o['tok'] == r['gold']), None)
        yield r['task'], r['point'][0], r.get('order', 0), sum(o['p'] for o in ident) / total, any(o['tok'] == r['gold'] for o in ident), gold


def fit(rows):
    """The m with sum(g - m p / (m p + 1 - p)) = 0, by bisection on log m (the sum falls as m grows)."""
    lo, hi = -7.0, 7.0
    for _ in range(60):
        mid = (lo + hi) / 2
        m = math.exp(mid)
        if sum(g - m * p / (m * p + 1 - p) for _, _, _, p, g, _ in rows) > 0:
            lo = mid
        else:
            hi = mid
    return math.exp((lo + hi) / 2)


def bits(p_gold, p, g, m):
    """Gold's pick in bits under P with m on the Ident options: -log2 of its share."""
    return -math.log2(p_gold * (m if g else 1.0) / (m * p + 1 - p))


def score(folder, m):
    """Prints the mean change in bits per form that has a key, and per INIT form, of gold's key atoms under m."""
    change = collections.defaultdict(float)  # (task, form, order) -> the change of its key atoms
    for task, form, order, p, g, pg in ident_rows(folder):
        if pg:
            change[task, form, order] += bits(pg, p, g, m) - bits(pg, p, g, 1.0)
    per_form = collections.defaultdict(list)
    for (task, form, order), v in change.items():
        per_form[task, form].append(v)
    keyed = {(r['task'], r['point'][0]) for r in iter_json(folder + '/relrows.jsonl.zst') if r.get('place') == 'key'}
    init = {(t['task'], f['i']) for t in iter_json(folder + '/tasks.jsonl') for f in t['forms'] if f['kind'] == 'INIT'}
    total = sum(sum(v) / len(v) for v in per_form.values())
    print('m %.3f: %d of %d INIT forms touched; change per keyed form %.3f bits (%d forms), per INIT form %.3f bits (%d forms)'
          % (m, len(per_form), len(init), total / max(len(keyed), 1), len(keyed), total / max(len(init), 1), len(init)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='+', help='rows folders, then the priors file to read and the priors file to write')
    ap.add_argument('--leave-out', help='a file of tasks to leave out, one a line')
    ap.add_argument('--score', help='a rows folder to score the fitted m on')
    a = ap.parse_args()
    *folders, src, dest = a.paths
    leave = set(open(a.leave_out).read().split()) if a.leave_out else set()
    rows = [x for f in folders for x in ident_rows(f, leave)]
    m = fit(rows)
    n = len(rows)
    scored = [x for x in rows if x[5]]
    commit = subprocess.run(['git', '-C', os.path.dirname(os.path.abspath(__file__)), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    with open(src, 'rb') as f:
        pri = pickle.load(f)
    pri['key_rel'] = dict(Ident=dict(
        m=m, rows=n, forms=len({(t, f) for t, f, *_ in rows}), gold_share=sum(x[4] for x in rows) / n, p_share=sum(x[3] for x in rows) / n,
        bits_before=sum(bits(pg, p, g, 1.0) for _, _, _, p, g, pg in scored) / len(scored), bits_after=sum(bits(pg, p, g, m) for _, _, _, p, g, pg in scored) / len(scored),
        rows_dirs=[os.path.abspath(f) for f in folders], commit=commit))
    with open(dest + '.tmp', 'wb') as f:
        pickle.dump(pri, f, protocol=5)
    os.replace(dest + '.tmp', dest)
    print(json.dumps(pri['key_rel']['Ident'], indent=1))
    if a.score:
        score(a.score, m)
    print(dest)


if __name__ == '__main__':
    sys.exit(main())
