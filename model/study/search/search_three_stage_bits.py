#!/usr/bin/env python
"""A RULE clause split at two atoms into three forms, each new form at most 2 atoms plus its read of the form before. Gives each form's surprisal, and whether the last form has the
clause's table up to column order. One row per clause and split pair, streamed; finished rows are skipped.

  <runtime python> search_three_stage_bits.py OUT.jsonl CASES.jsonl      from a kit's top folder, as search_two_stage_bits.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.getcwd(), 'model', 'study', 'sampler'))
import live  # noqa: E402
import live_try  # noqa: E402
import or_q  # noqa: E402
import search  # noqa: E402
import search_gold as G  # noqa: E402
import superdag as D  # noqa: E402
import superdag_search as SS  # noqa: E402

out, cases = sys.argv[1:3]
specs = {x['task']: x['gold_sexp'] for x in json.load(open('points-eval.json'))}
sampler = live.Sampler(os.environ['SEARCH_MODELS'])
tmp = tempfile.mkdtemp()
done = {(r['task'], r['form'], r['s1'], r['s2']) for r in map(json.loads, open(out))} if os.path.exists(out) else set()


def show(x):
    return x if isinstance(x, str) else '(' + ' '.join(show(y) for y in x) + ')'


def walk(task, forms, i):
    path = tmp + '/g.json'
    json.dump([dict(task=task, gold_sexp='\n'.join(forms))], open(path, 'w'))
    G.GOLDS = path
    G.golds.cache_clear()
    try:
        q = or_q.one(sampler, task, 'x', [i, 0])
        return q.get('total'), not (q.get('bad') or q.get('dead') or q.get('left'))
    except Exception:  # noqa: BLE001
        return None, False


def table(task, forms):
    sess, task_json, _ = live_try.session_of(task)
    run = D.Run(sampler.pri, sess, 0, 1e12, task_json, live.Limits())
    run.collect = []
    run.scope(forms)
    ct = run.collect[-1]
    return sorted(SS.table_key(D.S.parse_table(D.OneTable(ct, j)))[0][1] for _, j in D.relation_tables(ct))


def labels(atoms):
    got = []
    for t in search.flat(atoms):
        if t.startswith('*') and t[1:] not in got:
            got.append(t[1:])
    return got


with open(out, 'a') as f:
    for line in open(cases):
        c = json.loads(line)
        task, i = c['task'], c['form']
        lines = [x for x in specs[task].strip().split('\n') if not x.startswith('(OUT')]
        form = search.parse(lines[i])[0]
        atoms = form[2:]
        if any(isinstance(a, list) and a and a[0] == 'OR' for a in atoms) or len(atoms) < 3:
            continue
        scope = [lines[j] for j in c['keep']]
        whole = None
        n = len(atoms)
        for s1 in range(1, n - 1):
            for s2 in range(s1 + 1, n):
                if (task, i, s1, s2) in done or s1 > 2 or s2 - s1 > 2 or n - s2 > 2:
                    continue
                l1, l2 = labels(atoms[:s1]), labels(atoms[:s2])
                if not l1 or not l2:
                    continue
                first = show(['RULE', '&stage_a'] + atoms[:s1])
                mid = show(['RULE', '&stage_b', ['&stage_a'] + [[':' + x, '*' + x] for x in l1]] + atoms[s1:s2])
                last = show(['RULE', form[1], ['&stage_b'] + [[':' + x, '*' + x] for x in l2]] + atoms[s2:])
                b1, v1 = walk(task, scope + [first], len(scope))
                b2, v2 = walk(task, scope + [first, mid], len(scope) + 1)
                b3, v3 = walk(task, scope + [first, mid, last], len(scope) + 2)
                try:
                    if whole is None:
                        whole = table(task, scope + [lines[i]])
                    same = table(task, scope + [first, mid, last]) == whole
                except Exception as e:  # noqa: BLE001
                    same = repr(e)[:100]
                f.write(json.dumps(dict(task=task, form=i, s1=s1, s2=s2, atoms=n, bits=[b1, b2, b3], valid=bool(v1 and v2 and v3), same_table=same, whole=c['bits'])) + '\n')
                f.flush()
                print(task, i, s1, s2, b1, b2, b3, same, flush=True)
