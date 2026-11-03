#!/usr/bin/env python
"""A RULE clause split at each atom into two forms: a prefix with its own head, and the rest, which reads that head. Gives the surprisal of each part with the clause's read forms
in context, and whether the two forms give the clause's table. One row per clause and split, streamed; finished rows are skipped.

  <runtime python> search_two_stage_bits.py OUT.jsonl CASES.jsonl      from a kit's top folder, as search_case_bits.py
"""
import json
import os
import sys
import tempfile

import live
import live_try
import or_q
import search
import search_gold as G
import superdag as D

out, cases = sys.argv[1:3]
specs = {x['task']: x['gold_sexp'] for x in json.load(open('points-eval.json'))}
sampler = live.Sampler(os.environ['SEARCH_MODELS'])
tmp = tempfile.mkdtemp()
done = {(r['task'], r['form'], r['split']) for r in map(json.loads, open(out))} if os.path.exists(out) else set()


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
    """The merge keys of the last form's relation tables, on a replay of forms, in a new session."""
    sess, task_json, _ = live_try.session_of(task)
    run = D.Run(sampler.pri, sess, 0, 1e12, task_json, live.Limits())
    run.collect = []
    run.scope(forms)
    ct = run.collect[-1]
    return sorted(D.table_key(D.S.parse_table(D.OneTable(ct, j)))[0][1] for _, j in D.relation_tables(ct))


with open(out, 'a') as f:
    for line in open(cases):
        c = json.loads(line)
        task, i = c['task'], c['form']
        lines = [x for x in specs[task].strip().split('\n') if not x.startswith('(OUT')]
        form = search.parse(lines[i])[0]
        atoms = form[2:]
        if any(isinstance(a, list) and a and a[0] == 'OR' for a in atoms):
            continue
        scope = [lines[j] for j in c['keep']]
        whole = None
        for s in range(1, len(atoms)):
            if (task, i, s) in done:
                continue
            labels = []
            for t in search.flat(atoms[:s]):
                if t.startswith('*') and t[1:] not in labels:
                    labels.append(t[1:])
            if not labels:
                continue
            head = '&prefix_stage'
            first = show(['RULE', head] + atoms[:s])
            read = [head] + [[':' + x, '*' + x] for x in labels]
            second = show(['RULE', form[1], read] + atoms[s:])
            b1, v1 = walk(task, scope + [first], len(scope))
            b2, v2 = walk(task, scope + [first, second], len(scope) + 1)
            try:
                if whole is None:
                    whole = table(task, scope + [lines[i]])
                same = table(task, scope + [first, second]) == whole
            except Exception as e:  # noqa: BLE001
                same = repr(e)[:100]
            f.write(json.dumps(dict(task=task, form=i, split=s, atoms=len(atoms), first=first, second=second, bits1=b1, bits2=b2, valid1=v1, valid2=v2, same_table=same, whole=c['bits'])) + '\n')
            f.flush()
            print(task, i, s, b1, b2, same, flush=True)
