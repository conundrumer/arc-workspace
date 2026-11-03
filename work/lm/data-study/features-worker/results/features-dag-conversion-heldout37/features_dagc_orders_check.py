#!/usr/bin/env python
"""Checks of the order table, with no engine: features_dagc_env.sh 1 features_dagc_orders_check.py PART > orders-check-PART.txt

1. accepted / tried by form against the census folder's valid-share.jsonl (held), on forms with no OR, and on forms with an OR (where the OR branch orders change the count).
2. A scramble of a form's text (bodies and branches permuted, label names kept) gives the same draws and the same rendered texts, so the same accepted list.
3. The share of steps of the drawn orders whose next item equals the first item of gold's written order that the prefix leaves, against the mean of 1 over the count of ready items at that step.
"""
import collections
import json
import statistics
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import features_dag_order as D  # noqa: E402
import features_dagc_lib as L  # noqa: E402

L.setup_engine(L.HELD_CORPUS, L.BASE / 'models-base')
import features_dagc_modes as M  # noqa: E402
import features_dagc_orders as O  # noqa: E402

CENSUS = L.SCRATCH / 'records/features-dag-order-census-heldout37'


def rows(part):
    out = []
    for p in sorted(Path(L.OUT_DIR).glob('orders-%s-shard*.jsonl' % part)):
        out += [json.loads(x) for x in open(p)]
    return out


def main():
    part = sys.argv[1]
    rs = rows(part)
    gold = L.base_gold() if part in ('held', 'dev') else L.fit_gold()
    print('part %s: %d forms; law %s; kinds %s' % (part, len(rs), dict(collections.Counter(r['law'] for r in rs)), dict(collections.Counter(r['kind'] for r in rs))))
    print('step-law forms:', [(r['task'], r['line_id'], r['kind']) for r in rs if r['law'] == 'step'])
    # 1
    if part == 'held':
        old = {(r['task'], r['line']): r for r in map(json.loads, open(CENSUS / 'valid-share.jsonl'))}
        cmp = collections.defaultdict(collections.Counter)
        for r in rs:
            o = old.get((r['task'], r['line_id']))
            text = gold[r['task']][r['line_id']]
            has_or = '(OR ' in text
            if o is None:
                cmp[has_or]['no old row'] += 1
                continue
            same = (o['tried'], o['accepted']) == (r['tried'], r['accepted'])
            share_new, share_old = r['accepted'] / r['tried'], o['accepted'] / o['tried']
            cmp[has_or]['forms'] += 1
            cmp[has_or]['same tried and accepted'] += same
            cmp[has_or]['same share to 3 places'] += abs(share_new - share_old) < 5e-4
            cmp[has_or]['share differs by over .05'] += abs(share_new - share_old) > .05
            cmp[has_or]['n_orders differs'] += o['n_orders'] != r['n_orders']
        for k, v in sorted(cmp.items()):
            print('forms with %s OR: %s' % ('an' if k else 'no', dict(v)))
        # mean share
        for k in (False, True):
            xs = [r['accepted'] / r['tried'] for r in rs if r['tried'] and ('(OR ' in gold[r['task']][r['line_id']]) == k]
            ys = [old[(r['task'], r['line_id'])]['accepted'] / old[(r['task'], r['line_id'])]['tried'] for r in rs if r['tried'] and ('(OR ' in gold[r['task']][r['line_id']]) == k and (r['task'], r['line_id']) in old]
            print('mean accepted/tried, OR=%s: new %.4f old %.4f over %d forms' % (k, statistics.fmean(xs), statistics.fmean(ys), len(xs)))
    # 2
    bad, n = [], 0
    for r in rs[:400]:
        text = gold[r['task']][r['line_id']]
        dag = D.FormDag(text)
        other_text = dag.render(dag.random_order(77))
        o2 = D.FormDag(other_text)
        n += 1
        a = [dag.render(dag.random_order(s)) for s in range(12)]
        b = [o2.render(o2.random_order(s)) for s in range(12)]
        ids = lambda d, s: d.leaves(d.random_order(s))  # noqa: E731
        same = a == b and all(ids(dag, s) == ids(o2, s) for s in range(12))
        if dag.count_orders() is not None and dag.count_orders() <= 256:
            same = same and sorted(dag.render(o) for o in dag.all_orders()) == sorted(o2.render(o) for o in o2.all_orders())
        prog1, prog2 = D.ProgramDag(gold[r['task']]), D.ProgramDag([other_text if i == r['line_id'] else x for i, x in enumerate(gold[r['task']])])
        key = D.parse(text)[1]
        same = same and prog1.content[key] == prog2.content[key]
        if not same:
            bad.append((r['task'], r['line_id']))
    print('scramble: %d forms, %d differ %s' % (n, len(bad), bad[:5]))
    # 3
    steps = hits = 0
    expect = expect_adm = 0.0
    steps_adm = 0
    for r in rs:
        text = gold[r['task']][r['line_id']]
        written = D.FormDag(text)
        w = written.written_order()
        for t in r['orders']:
            d = D.FormDag(t)
            order = d.written_order()
            outers = O.outer_labels(D, M, d)
            for path, ids in order.items():
                if path.startswith('or|') or path not in d.item_preds:
                    continue
                preds = d.item_preds[path]
                wpath = w.get(path)
                if wpath is None or sorted(wpath) != sorted(ids):
                    continue
                trees = {a.id: D.strip_marks(a.tree) for b in d.all_bodies if b.path == path for a in b.items}
                outer0 = outers[path]
                bound = set(outer0)
                for j in range(len(ids) - 1):
                    done = set(ids[:j])
                    ready = [i for i in ids if i not in done and preds[i] <= done]
                    adm = O.admitted(D, M, trees, preds, done, bound, outer0)
                    bound |= dict(adm).get(ids[j], set())
                    wn = next(i for i in wpath if i not in done)
                    if wn not in ready or len(ready) < 2:
                        continue
                    steps += 1
                    hits += ids[j] == wn
                    expect += 1 / len(ready)
                    if wn in dict(adm):
                        steps_adm += 1
                        expect_adm += 1 / len(adm)
    print('next item equals gold\'s written next item at %d of %d steps (%.4f); mean 1 over the DAG-ready count: %.4f; mean 1 over the count of ready items that atom_binds admits (steps where the written item is admitted, %d): %.4f' % (hits, steps, hits / max(steps, 1), expect / max(steps, 1), steps_adm, expect_adm / max(steps_adm, 1)))


if __name__ == '__main__':
    main()
