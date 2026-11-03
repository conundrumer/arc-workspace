#!/usr/bin/env python
"""Checks of the arrays and the form bits (item 8). Writes data-check.txt.

  features_dagc_env.sh 1 features_dagc_data_check.py NAME POINTS WALKS... [--n 50]

1. Columns and tokens of data-NAME.npz pass check_columns and check_tokens, and the file has a `checked` field.
2. At every pick, the softmax of the `lq` column gives the walk's `q_bits` at gold (the off arm's bits equal the walk's).
3. Weights: a point's weights sum to its mean count of picks per finished walk, and every weight is in (0, 1].
4. Keys that two walks reached with different options or weights are counted: `weights` must be 0 (`dead_only` is the flag `dead by join`, which reads the scope's types as a set and can differ across orders).
5. Scramble: for N points of the walks (RULE, with a scope), the arrays of each pick are equal when the scope's forms are shuffled in line order, in bodies, in branches and in ports, the marks dropped. Label names stay, since a form's content key holds them.
6. Power: the same scramble moves the first-atom root of features_perrel_keys.py (the key this record replaces) on some forms.
"""
import json
import random
import re
import sys
import time
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path('/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-conversion-heldout37')))
import features_dagc_check as CK  # noqa: E402
import features_dagc_data as DD  # noqa: E402
import features_dagc_facts as F  # noqa: E402
import features_dagc_keys as K  # noqa: E402
import features_dagc_lib as L  # noqa: E402
import features_dagc_matrix as M  # noqa: E402
import features_ofree_facts as FL  # noqa: E402
import features_ofree_text as T  # noqa: E402


def old_root(line):
    """The root of the first-atom key of features_perrel_keys.py, on a form text: the head of its first body atom."""
    w = line.split()
    rest = line.split(None, 2)[2] if len(w) > 2 else ''
    a = re.match(r'\((?:NOT \()?([^\s()]+)', rest)
    return 'OR' if rest.startswith('(OR') else (a[1] if a else None)


def main():
    args = sys.argv[1:]
    n = 50
    if '--n' in args:
        i = args.index('--n')
        n = int(args[i + 1])
        del args[i:i + 2]
    name, points, walks = args[0], args[1], args[2:]
    out = []
    z = np.load(DD.OUT + 'data-%s.npz' % name, allow_pickle=False)
    chk = json.loads(str(z['checked']))
    F.check_columns(list(z['names']))
    F.check_tokens(list(z['v_heads']))
    out.append('1. %d columns and %d sparse tokens pass; checked field %s; %d picks, %d option rows' % (len(z['names']), len(z['v_heads']), chk, len(z['w']), len(z['S'])))
    st, gold = z['starts'], z['gold']
    lq = z['S'][:, 0].astype(np.float64)
    worst, m = 0.0, 0
    for i in range(len(gold)):
        if gold[i] < 0:
            continue
        a = lq[st[i]:st[i + 1]]
        b = -(a[gold[i]] - np.log(np.exp(a - a.max()).sum()) - a.max()) / np.log(2)
        worst = max(worst, abs(b - float(z['m_q_bits'][i])))
        m += 1
    out.append('2. lq-softmax bits equal the walk\'s q_bits at %d gold picks, largest difference %.5f bits' % (m, worst))
    w, cnt, gid = z['w'], z['cnt'], z['m_line']
    per = {}
    for g, c in zip(gid.tolist(), cnt.tolist()):
        per[g] = per.get(g, 0) + c
    forms = json.loads(str(z['forms']))
    nw = {}
    for f in forms:
        if f['ok']:
            nw[f['point']] = nw.get(f['point'], 0) + 1
    wsum = {}
    for g, x in zip(gid.tolist(), w.tolist()):
        wsum[g] = wsum.get(g, 0) + x
    bad = [g for g in per if abs(wsum[g] - per[g] / nw[g]) > 1e-4]
    out.append('3. weights in (0, 1]: %s; per point, the weights sum to picks per finished walk: %d of %d points off' % (bool(((w > 0) & (w <= 1.0 + 1e-6)).all()), len(bad), len(per)))
    conf = json.loads(str(z['conflicts']))
    out.append('4. keys reached with different options: %s of %d picks (weights must be 0)' % (conf, len(w)))
    # scramble
    cx = DD.Ctx(points, 'held-parents' if 'held' in points else Path(walks[0]).name.split('-off-')[0].split('-live-')[0])
    reg = T.Registry()
    txt = open(T.REGISTRY, encoding='utf8').read()
    caps = set(re.findall(r'^\((?:component|proposer) (\w+)', txt, re.M)) | {'RULE', 'DET', 'INIT', 'OUT', 'RIGID_DET', 'CHOOSE', 'NOT', 'OR', 'ALL', 'IF', 'ONE', 'SET'}
    rng = random.Random(0)
    seen, same, diff, moved, total_picks, t0 = set(), 0, 0, 0, 0, time.time()
    examples = []
    for path in walks:
        for rows, fm in DD.walk_frames(path):
            if len(seen) >= n or time.time() - t0 > 18:
                break
            p = cx.pts[fm['point']]
            if not fm['ok'] or fm['kind'] != 'RULE' or len(p['scope']) < 2 or fm['point'] in seen or not rows:
                continue
            seen.add(fm['point'])
            names = {}
            scr = [re.sub(r'[*^]', '', FL.unparse(CK.scramble_form(x, rng))) if not x.startswith('(OUT') else x for x in p['scope']]
            rng.shuffle(scr)
            q = dict(p, scope=scr, scope_id=p['scope_id'] + 'x')
            ok = True
            for line in rows:
                d = json.loads(line)
                a = DD.build_pick(d, p, cx, None)
                b = DD.build_pick(d, q, cx, None)
                total_picks += 1
                if not all(np.array_equal(a[k], b[k]) for k in ('S', 'C', 'X', 'scnt')) or a['keys'] != b['keys'] or a['sc'] != b['sc'] or a['ph'] != b['ph'] or a['toks'] != b['toks']:
                    ok = False
                    if len(examples) < 3:
                        examples.append((p['task'], p['line_id'], [k for k in ('S', 'C', 'X', 'keys', 'sc', 'ph', 'toks') if (not np.array_equal(a[k], b[k]) if k in ('S', 'C', 'X') else a[k] != b[k])]))
            same += ok
            diff += not ok
            a_roots = [old_root(x) for x in p['scope']]
            b_roots = [old_root(x) for x in scr]
            moved += sorted(map(str, a_roots)) != sorted(map(str, b_roots))
    out.append('5. scramble of the scope: %d points, %d picks; arrays, keys and tokens equal on %d points, differ on %d %s' % (len(seen), total_picks, same, diff, examples))
    out.append('6. power: the first-atom root of features_perrel_keys.py changes under the same shuffles on %d of %d scopes' % (moved, len(seen)))
    out.append('%.0f s' % (time.time() - t0))
    print('\n'.join(out))
    with open(DD.ME + 'data-check.txt', 'a') as f:
        f.write('NAME %s\n' % name + '\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
