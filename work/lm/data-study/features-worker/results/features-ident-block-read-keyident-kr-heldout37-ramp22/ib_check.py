"""The checks of the design.

  ib_check.py c1c2 TASK            C1 (Ident-only list equals the pinned list) and C2 (the shape at its scope equals the full replay's)
  ib_check.py c3 TASK G [N]        C3 (Clause.tables holds the clause's own tables): N drawn clauses at the scope of form G (default 5)
  ib_check.py c4 [N]               C4 (DAG invariance of shapes, facts and links): N corpus stems (default 20), gold's order and one other valid order
  ib_check.py c5 TASK G,G [N]      C5 (seed and order stability): two runs of N draws (default 64) at each form, Jeffreys intervals overlap
"""
import json
import os
import random
import sys
import time

import ib_lib as L

MODEL = L.MODELS['37']


def load_task(task):
    st = L.set_of(task)
    forms = L.forms_of(L.held_gold()[task]) if st != 'corpus' else L.forms_of(L.corpus_gold(task))
    sampler = L.live.Sampler(L.MODELS[st])
    sess, d = L.session_of(L.task_path(task, st))
    return st, forms, sampler, sess, d


def full(task):
    st, forms, sampler, sess, d = load_task(task)
    t0 = time.time()
    cts, err = L.replay(sampler, d, sess, forms)
    info, reads = L.analyze(forms, cts)
    print('%s: full replay of %d forms in %.1fs, %d analyzed%s' % (task, len(forms), time.time() - t0, len(info), ', error ' + err if err else ''), flush=True)
    return st, forms, sampler, sess, d, info, reads


def c1c2(task):
    st, forms, sampler, sess, d, info, reads = full(task)
    ok = True
    got = [a['i'] for a in info if a['ident_only']]
    want = L.ident_list()[task]['ident_only']
    print('C1 ident-only forms: replay %s, pinned %s: %s' % (got, want, 'PASS' if got == want else 'FAIL'))
    ok &= got == want
    by = {a['i']: a for a in info}
    rng = random.Random('c2 ' + task)
    ident = [a['i'] for a in info if a['ident_only']]
    plain = [a['i'] for a in info if a['tabs'] and not a['holds']]
    picks = rng.sample(ident, min(4, len(ident))) + rng.sample(plain, min(2, len(plain)))
    for g in picks:
        scope = sorted(by[g]['scope'])
        order = L.valid_order(scope, reads, random.Random('c2 %s %d' % (task, g)))
        t0 = time.time()
        cts, err = L.replay(sampler, d, sess, [forms[j] for j in order] + [forms[g]])
        shape = L.shape_of(by[g]['kind'], forms[g], cts[-1]) if len(cts) == len(order) + 1 else None
        good = shape == by[g]['shape']
        ok &= good
        print('C2 form %d (%s, scope %d, order %s): scope-order replay %s, full replay %s, %.1fs: %s' % (
            g, 'ident' if by[g]['ident_only'] else 'plain', len(scope), order[:6], shape, by[g]['shape'], time.time() - t0, 'ok' if good else 'MISMATCH ' + str(err)), flush=True)
    print('C1 C2:', 'PASS' if ok else 'FAIL')
    return ok


def c3(task, g, n=5):
    st, forms, sampler, sess, d, info, reads = full(task)
    by = {a['i']: a for a in info}
    kind = by[g]['kind']
    scope = sorted(by[g]['scope'])
    order = L.valid_order(scope, reads, random.Random('c3 %s %d' % (task, g)))
    texts = [forms[j] for j in order]
    print('C3: %s form %d kind %s scope %d' % (task, g, kind, len(texts)), flush=True)
    ok, got, tries, t0 = True, 0, 0, time.time()
    while got < n and tries < 3 * n:
        c = sampler.clause(sess, L.draw_seed(task, g, 10000 + tries), time.monotonic() + 20, d, texts, kind)
        tries += 1
        if c is None:
            continue
        got += 1
        drawn = L.shape_of(kind, c.text, c.tables)
        cts, err = L.replay(sampler, d, sess, texts + [c.text])
        replayed = L.shape_of(kind, c.text, cts[-1]) if len(cts) == len(texts) + 1 else None
        good = drawn == replayed
        ok &= good
        print('  clause %d: Clause.tables %s, replay %s: %s  %s' % (got, drawn, replayed, 'ok' if good else 'MISMATCH ' + str(err), c.text[:90].replace('\n', ' ')), flush=True)
    ok &= got == n
    print('C3 %d clauses in %d tries, %.1fs: %s' % (got, tries, time.time() - t0, 'PASS' if ok else 'FAIL'))
    return ok


def c4(n=20):
    stems = L.corpus_stems()
    pick = random.Random('c4').sample(stems, n)
    sampler = L.live.Sampler(L.MODELS['corpus'])
    ok, t0 = True, time.time()
    for k, stem in enumerate(pick):
        forms = L.forms_of(L.corpus_gold(stem))
        sess, d = L.session_of(L.task_path(stem, 'corpus'))
        cts, err = L.replay(sampler, d, sess, forms)
        info, reads = L.analyze(forms, cts)
        order = L.valid_order(set(range(len(forms))), reads, random.Random('c4 ' + stem))
        cts2, err2 = L.replay(sampler, d, sess, [forms[j] for j in order])
        info2, _ = L.analyze([forms[j] for j in order], cts2)
        A = {a['head']: (a['shape'], a['facts'], a['link'], a['holds'], a['ident_only']) for a in info}
        B = {a['head']: (a['shape'], a['facts'], a['link'], a['holds'], a['ident_only']) for a in info2}
        bad = [h for h in A.keys() | B.keys() if A.get(h) != B.get(h)]
        moved = sum(1 for x, y in enumerate(order) if x != y)
        ok &= not bad
        print('  [%d/%d, %.1fs] %s: %d forms, %d/%d analyzed, %d moved in the other order, %d disagree%s%s' % (
            k + 1, n, time.time() - t0, stem, len(forms), len(A), len(B), moved, len(bad), (' ' + str(bad[:3])) if bad else '', (' errors %s %s' % (err, err2)) if err or err2 else ''), flush=True)
    print('C4 %d stems, %.1fs: %s' % (n, time.time() - t0, 'PASS' if ok else 'FAIL'))
    return ok


def c5(task, gs, n=64):
    st, forms, sampler, sess, d, info, reads = full(task)
    by = {a['i']: a for a in info}
    ok = True
    for g in gs:
        a = by[g]
        kind, want = a['kind'], L.within(a['shape'])
        ident_heads = {by[j]['head'] for j in a['scope'] if by[j]['holds']}
        res = []
        for run in ('a', 'b'):
            h = tries = 0
            t0, cpu0 = time.time(), time.process_time()
            for b in range(-(-n // 32)):
                order = L.valid_order(a['scope'], reads, random.Random('c5 %s %s %d %d' % (run, task, g, b)))
                texts = [forms[j] for j in order]
                seeds = [L.draw_seed('c5' + run + task, g, i) for i in range(32 * b, min(32 * b + 32, n))]
                for r in L.draw_batch(sampler, sess, d, texts, kind, seeds, ident_heads):
                    tries += 1
                    h += r is not None and L.within(r[0]) == want
            lo, hi = L.jeffreys(h, tries)
            res.append((lo, hi))
            print('  form %d run %s: %d of %d draws have within-kind shape %s, Jeffreys [%.3f, %.3f], %.2f s a draw' % (g, run, h, tries, want, lo, hi, (time.time() - t0) / tries), flush=True)
        good = res[0][0] <= res[1][1] and res[1][0] <= res[0][1]
        ok &= good
        print('C5 form %d intervals %s' % (g, 'overlap' if good else 'DO NOT OVERLAP'), flush=True)
    print('C5:', 'PASS' if ok else 'FAIL')
    return ok


if __name__ == '__main__':
    L.setup()
    a = sys.argv[1:]
    if a[:1] == ['c1c2']:
        ok = c1c2(a[1])
    elif a[:1] == ['c3']:
        ok = c3(a[1], int(a[2]), int(a[3]) if len(a) > 3 else 5)
    elif a[:1] == ['c4']:
        ok = c4(int(a[1]) if len(a) > 1 else 20)
    elif a[:1] == ['c5']:
        ok = c5(a[1], [int(x) for x in a[2].split(',')], int(a[3]) if len(a) > 3 else 64)
    else:
        sys.exit(__doc__)
    sys.exit(0 if ok else 1)
