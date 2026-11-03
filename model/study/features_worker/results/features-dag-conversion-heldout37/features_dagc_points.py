#!/usr/bin/env python
"""Scope points of the parents and cut kinds, with no engine.

  python -I features_dagc_points.py PART [--check]        writes points-PART.jsonl

PART is one of held-parents, test-parents, parents (RULE forms of the fit tasks), held-cut, dev-cut, test-cut, fit-cut. The pool parts (held-pool, held-wide, fit-pool) come from
the copies features_ps_points.py and features_ps_points_fit.py, and init77 from item 15.
A point: task, form (the content key of ProgramDag), key (the head), kind, line_id (the form's line in gold; for joins only), scope (the scope's form texts in a topological order), scope_rule,
scope_id (a hash of the sorted content keys of the scope's forms), target_seed, arm, stratum, and line (the point's id in its file).
  parents: the scope is ProgramDag.random_order(s, ancestors(key)), seed 0.
  cut: the forms before the target in ProgramDag.random_order(s, non_descendants(key) | {key}), seeds 0 and 1.
Gold is held and dev: base gold of points-base.json; test and fit: the first pair of each task of corpus-v3mix. fit-cut has the RULE forms of all fit tasks, and the DET and INIT forms of the test tasks.
--check tests each scope: topological, holds each form that the target reads, holds no descendant of the target, and a cut scope equals the prefix of its seed's order.
"""
import argparse
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path('/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-conversion-heldout37')))
import features_dag_order as D  # noqa: E402
import features_dagc_lib as L  # noqa: E402

PARTS = {  # part -> (task source, scope rule, kinds, kinds outside the test tasks)
    'held-parents': ('held', 'parents'), 'held-cut': ('held', 'cut'), 'dev-cut': ('dev', 'cut'),
    'test-parents': ('test', 'parents'), 'test-cut': ('test', 'cut'), 'fit-cut': ('fit', 'cut'), 'parents': ('fit', 'parents'),
}


def scope_id(prog, keys) -> str:
    return D.short(''.join(sorted(prog.content[k] for k in keys)), 16)


def points_of(part: str):
    src, rule = PARTS[part]
    allg = None
    if src in ('held', 'dev'):
        allg = L.base_gold()
        gold = {t: allg[t] for t in (L.held_tasks() if src == 'held' else L.dev_tasks())}
    else:
        tasks = L.test_tasks() if src == 'test' else L.fit_tasks()
        gold = L.fit_gold(tasks)
    test = set(L.test_tasks()) if part in ('fit-cut', 'parents') else None
    for t, lines in gold.items():
        prog = D.ProgramDag(lines)
        for i, text in enumerate(lines):
            kind = L.kind_of(text)
            if kind not in L.KINDS or (test is not None and kind != 'RULE' and t not in test):
                continue
            key = D.parse(text)[1]
            if rule == 'parents':
                keys = prog.ancestors(key)
                yield dict(task=t, form=prog.content[key], key=key, kind=kind, line_id=i, scope=prog.texts(prog.random_order(0, keys)), scope_rule='parents', scope_id=scope_id(prog, keys),
                           target_seed=0, arm='', stratum='')
                continue
            for s in (0, 1):
                order = prog.random_order(s, prog.non_descendants(key) | {key})
                keys = order[:order.index(key)]
                yield dict(task=t, form=prog.content[key], key=key, kind=kind, line_id=i, scope=prog.texts(keys), scope_rule='cut', scope_id=scope_id(prog, keys),
                           target_seed=s, arm='', stratum='')


def check(path: str, part: str):
    src, rule = PARTS[part]
    bad, n = [], 0
    allg = L.base_gold() if src in ('held', 'dev') else None
    for line in open(path):
        r = json.loads(line)
        n += 1
        lines = allg[r['task']] if allg else L.fit_gold([r['task']])[r['task']]
        prog = D.ProgramDag(lines)
        key = r['key']
        sc = [D.parse(x)[1] for x in r['scope']]
        at = {k: j for j, k in enumerate(sc)}
        topo = all(at[p] < at[k] for k in sc for p in prog.parent_ids[k] if p in at)
        reads = prog.ancestors(key) <= set(sc)
        nodesc = not (set(sc) & (prog.descendants(key) | {key}))
        ok = topo and reads and nodesc
        if rule == 'cut':
            order = prog.random_order(r['target_seed'], prog.non_descendants(key) | {key})
            ok = ok and sc == order[:order.index(key)]
        else:
            ok = ok and set(sc) == prog.ancestors(key)
        if not ok:
            bad.append((r['task'], r['line_id'], dict(topo=topo, reads=reads, nodesc=nodesc)))
    print('check %s: %d points, %d fail %s' % (part, n, len(bad), bad[:3]))
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('part', choices=sorted(PARTS))
    ap.add_argument('--out', default=str(L.OUT_DIR))
    ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    path = Path(a.out) / ('points-%s.jsonl' % a.part)
    if not a.check:
        n = 0
        with open(path, 'w') as f:
            for n, p in enumerate(points_of(a.part)):
                f.write(json.dumps(dict(p, line=n)) + '\n')
        print('%s: %d points to %s' % (a.part, n + 1, path))
    check(str(path), a.part)


if __name__ == '__main__':
    main()
