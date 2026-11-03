#!/usr/bin/env python
"""Recount of gold's worst form with the forms that a repair step finds set to 0 bits.

  features_repair_recount.py OUT.json TASKS_FILE POINTS.json CENSUS.jsonl [CENSUS.jsonl ...]

CENSUS rows of the parents context give each form's bits. POINTS.json is the gold list that the census walked. TASKS_FILE is the task list of the read.

Rule, from the lists and commits, which name tasks and not forms:
- ONE repair (one_repair.py; list: the tasks of the --one check in sampler-one-repair/check.sh): the repair adds marks to a form. A form of a listed task whose text holds a `(ONE` mark is set to 0.
- CHOOSE lift (choose_lift.py, commit 96f903721; list: the tasks that its check names): the lift adds a whole CHOOSE form. A form of kind CHOOSE on a listed task is set to 0. The census has no row for that kind, so it leaves the count of forms with no walk.
A form that keeps no bits after that (not valid, or no walk) stays undrawable, and a task with one isn't counted under a bar in the column `every form drawable`.
"""
import collections
import json
import sys

ONE = '8e5c0c38 f560132c a6953f00 ba97ae07 89565ca0 df8cc377 a3325580 caa06a1f dc2aa30b b7999b51 b7cb93ac bd283c4a cc9053aa d4c90558 e6721834'.split()
CHOOSE = '4cd1b7b2 681b3aeb 6a1e5592 83b6b474 f8cc533f 150deff5 184a9768 626c0bcc 67c52801 b7cb93ac 1a244afd'.split()
BARS = 25, 28, 32
KINDS = 'RULE', 'INIT', 'DET'


def valid(r):
    return 'total' in r and not r.get('bad') and not r.get('dead') and not r.get('left')


def worst_of(forms):
    """(worst bits over forms with bits, count of forms with no bits). forms: bits or None."""
    have = [x for x in forms if x is not None]
    return (max(have) if have else None), len(forms) - len(have)


def counts(table):
    """Tasks under each bar: with every form drawable, and over the forms with bits."""
    return {b: dict(every_form_drawable=sum(w is not None and w < b and not n for w, n in table.values()), forms_with_bits=sum(w is not None and w < b for w, n in table.values())) for b in BARS}


out, tasks_file, points, files = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4:]
tasks = open(tasks_file).read().split()
gold = {x['task']: [l for l in x['gold_sexp'].splitlines() if l.strip()] for x in json.load(open(points))}
rows = collections.defaultdict(dict)
for f in files:
    for l in open(f):
        r = json.loads(l)
        if r.get('scope') == 'parents':
            rows[r['task'][:8]][r['line']] = r
before, after, changed = {}, {}, []
for t in tasks:
    lines = gold[t]
    a, b = [], []
    n_one = n_choose = 0
    for i, x in enumerate(lines):
        kind = x.split()[0].lstrip('(')
        if kind == 'OUT':
            continue
        r = rows[t].get(i)
        bits = float(r['total']) if r is not None and valid(r) else None
        a.append(bits)
        if t in ONE and '(ONE' in x:
            n_one += 1
            bits = 0.
        elif t in CHOOSE and kind == 'CHOOSE':
            n_choose += 1
            bits = 0.
        b.append(bits)
    before[t], after[t] = worst_of(a), worst_of(b)
    if n_one or n_choose:
        changed.append(dict(task=t, one_forms=n_one, choose_forms=n_choose, before=before[t], after=after[t]))
res = dict(
    tasks=len(tasks),
    one_list=len(ONE), one_in_read=sorted(set(ONE) & set(tasks)), one_outside=len(set(ONE) - set(tasks)),
    choose_list=len(CHOOSE), choose_in_read=sorted(set(CHOOSE) & set(tasks)), choose_outside=len(set(CHOOSE) - set(tasks)),
    in_both_lists=sorted(set(ONE) & set(CHOOSE)),
    before=counts(before), after=counts(after), changed=changed,
    lowest_after=sorted((round(w, 2), t, n) for t, (w, n) in after.items() if w is not None and not n)[:5],
    lowest_with_undrawable_form=sorted((round(w, 2), t, n) for t, (w, n) in after.items() if w is not None and n)[:5],
    undrawable_tasks_before=sum(bool(n) for w, n in before.values()), undrawable_tasks_after=sum(bool(n) for w, n in after.values()))
with open(out, 'w') as f:
    json.dump(res, f, indent=1)
print(json.dumps(res))
