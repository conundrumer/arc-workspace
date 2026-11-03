"""The checks of the design.

  tw_check.py k1k2 [N]               K1 (the walk reads only the DAG) and K2 (the walk's invariants) on N corpus stems (default 20)
  tw_check.py k3 TASK STEP [N]       K3 (the pattern on both sides): gold's form at the step, and N drawn clauses (default 5)
  tw_check.py k6 TASK NDRAW [STEPS]  K6 (order stability of the proposal): NDRAW draws at each of two steps (default 12,8), batch 0 against batches 1 to 3
K4 is in tw_shapes.py, K5 in tw_fit.py.
"""
import random
import sys
import time

import tw_lib as T

L = T.L


def independent_mode(parents, chain):
    """The mode of the walk.md text, written again: EXTEND, BT d (largest j < m in the reads), else JUMP."""
    m = len(chain)
    if m and chain[m - 1] in parents:
        return 'EXTEND', 0
    js = [j for j in range(1, m) if chain[j - 1] in parents]  # 1-based j < m
    if js:
        d = m - max(js)
        return 'BT%s' % ('3+' if d >= 3 else d), d
    return 'JUMP', 0


def k1k2(n=20):
    D = T.dago()
    stems = random.Random('k1k2').sample(T.tasks_of('corpus'), n)
    ok1 = ok2 = True
    t0, steps = time.time(), 0
    for stem in stems:
        forms = T.gold_forms(stem)
        dag = D.ProgramDag(forms)
        order = dag.random_order(7)
        forms2 = [dag.lines[k] for k in order]
        dag2 = D.ProgramDag(forms2)
        moved = sum(1 for a, b in zip(T.dago().ProgramDag(forms).lines, order) if a != b)
        for seed in range(4):
            r1 = T.walk(forms, seed, dag=dag)
            r2 = T.walk(forms2, seed, dag=dag2)
            seq1 = [(dag.content[r['key_f']], r['mode']) for r in r1]
            seq2 = [(dag2.content[r['key_f']], r['mode']) for r in r2]
            if seq1 != seq2:
                ok1 = False
                print('K1 FAIL %s seed %d (%d forms moved in the other text)' % (stem, seed, moved))
            # K2 on the walk of the original text
            placed = []
            for t, r in enumerate(r1):
                steps += 1
                f, chain, S = r['key_f'], list(r['_chain']), set(r['_S'])
                bad = []
                if not dag.parent_ids[f] <= S:
                    bad.append('not a linear extension')
                if any(chain[i] not in dag.parent_ids[chain[i + 1]] for i in range(len(chain) - 1)):
                    bad.append('chain link does not read')
                if r['key_h'] != (placed[-1] if placed else ''):
                    bad.append('head is not the form placed last')
                if (chain[-1] if chain else '') != r['key_h']:
                    bad.append('head is not the chain top')
                mode, d = independent_mode(dag.parent_ids[f], chain)
                if (mode, d) != (r['mode'], r['d']):
                    bad.append('mode %s,%s recomputed %s,%s' % (r['mode'], r['d'], mode, d))
                if S != set(placed):
                    bad.append('S is not the placed set')
                if r['t'] != len(placed) or r['m'] != len(chain):
                    bad.append('t or m')
                if bad:
                    ok2 = False
                    print('K2 FAIL %s seed %d t %d: %s' % (stem, seed, t, '; '.join(bad)))
                placed.append(f)
            if sorted(placed) != sorted(dag.lines):
                ok2 = False
                print('K2 FAIL %s seed %d: the walk does not place every form once' % (stem, seed))
    print('%d stems x 4 seeds, %d steps, %.1f s' % (n, steps, time.time() - t0))
    print('K1', 'PASS' if ok1 else 'FAIL')
    print('K2', 'PASS' if ok2 else 'FAIL')
    return ok1 and ok2


def load(task):
    D = T.dago()
    live = T.setup()
    st = L.set_of(task)
    forms = T.gold_forms(task)
    dag = D.ProgramDag(forms)
    recs = T.walk(forms, 0, task=task, dag=dag)
    sampler = live.Sampler(L.MODELS[st])
    sess, d = L.session_of(L.task_path(task, st))
    return st, forms, dag, recs, sampler, sess, d


def k3(task, step, n=5):
    st, forms, dag, recs, sampler, sess, d = load(task)
    r = recs[step]
    f, S, chain = r['key_f'], set(r['_S']), list(r['_chain'])
    text = dag.lines[f]
    want = T.pattern(dag.parent_ids[f], chain, S, dag)
    got = T.pattern_of_text(text, S, chain, dag)
    ok = want == got
    print('K3 step %d form %s %s: pattern from the walk %s, from the text through the draw path %s: %s' % (step, f, r['kind_f'], want, got, 'ok' if ok else 'MISMATCH'))
    texts = [dag.lines[k] for k in sorted(S, key=lambda k: [x['key_f'] for x in recs].index(k))]
    assert len(texts) == step
    kind, got_n, tries, t0 = r['kind_f'], 0, 0, time.time()
    while got_n < n and tries < 3 * n:
        c = sampler.clause(sess, T.draw_seed(task, f, 9000 + tries), time.monotonic() + 20, d, texts, kind)
        tries += 1
        if c is None:
            continue
        got_n += 1
        names = T.NAME.findall(c.text)
        own = names[0] if names else None  # the clause's head, a name that forms do not use
        outside = sorted({x for x in names if x not in S and x != own})
        good = not outside
        ok &= good
        print('  clause %d: reads %d scope heads, pattern %s, names outside S %s: %s  %s' % (
            got_n, len(set(names) & S), T.pattern_of_text(c.text, S, chain, dag), outside, 'ok' if good else 'FAIL', c.text[:80].replace('\n', ' ')), flush=True)
    ok &= got_n == n
    print('%d clauses in %d tries, %.1f s' % (got_n, tries, time.time() - t0))
    print('K3', 'PASS' if ok else 'FAIL')
    return ok


def overlap(a, b):
    return a[0] <= b[1] and b[0] <= a[1]


def k6(task, ndraw, steps=(12, 8)):
    st, forms, dag, recs, sampler, sess, d = load(task)
    rows = T.held_shape_rows(task)
    if rows is None:
        sys.exit('no R/shapes/%s.json: run tw_shapes.py first' % task)
    g_of = {T.head_of(f): g for g, f in enumerate(forms)}
    ok = True
    for step in steps:
        r = recs[step]
        f, S = r['key_f'], set(r['_S'])
        chain = list(r['_chain'])
        placed = [x['key_f'] for x in recs[:step]]
        want_shape = L.within(rows[g_of[f]][1])
        want_pat = T.pattern(dag.parent_ids[f], chain, S, dag)
        kind = r['kind_f']
        tally = {}
        t0 = time.time()
        for b in range(4):
            order = placed if b == 0 else dag.random_order(b, keys=S)
            texts = [dag.lines[k] for k in order]
            hs = hp = hj = 0
            for i in range(ndraw):
                if i == 0:
                    T.gc_clean()
                c = sampler.clause(sess, T.draw_seed(task, f, b * 1000 + i), time.monotonic() + 20, d, texts, kind)
                if c is None:
                    continue
                sh = L.within(L.shape_of(kind, c.text, c.tables)) == want_shape
                pt = T.pattern_of_text(c.text, S, chain, dag) == want_pat
                hs += sh
                hp += pt
                hj += sh and pt
            tally[b] = (hs, hp, hj)
        n0, n1 = ndraw, 3 * ndraw
        good = True
        for j, name in enumerate(('shape', 'pattern', 'joint')):
            h0, h1 = tally[0][j], sum(tally[b][j] for b in (1, 2, 3))
            i0, i1 = L.jeffreys(h0, n0), L.jeffreys(h1, n1)
            ov = overlap(i0, i1)
            if name == 'joint':
                good = ov
            print('  step %d %s %s %s (gold %s | %s): batch 0 %d/%d [%.2f, %.2f], batches 1-3 %d/%d [%.2f, %.2f]: %s' % (
                step, name, f, kind, want_shape, want_pat, h0, n0, i0[0], i0[1], h1, n1, i1[0], i1[1], 'overlap' if ov else 'DO NOT OVERLAP'), flush=True)
        ok &= good
        print('  step %d: %.1f s' % (step, time.time() - t0), flush=True)
    print('K6', 'PASS' if ok else 'FAIL')
    return ok


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if a[0] == 'k1k2':
        ok = k1k2(int(a[1]) if len(a) > 1 else 20)
    elif a[0] == 'k3':
        ok = k3(a[1], int(a[2]), int(a[3]) if len(a) > 3 else 5)
    elif a[0] == 'k6':
        ok = k6(a[1], int(a[2]), tuple(int(x) for x in a[3].split(',')) if len(a) > 3 else (12, 8))
    else:
        sys.exit(__doc__)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
