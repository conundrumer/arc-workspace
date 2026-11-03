"""Labels of the scopes in scope-rows.tsv. They come from the cover map: map-cover-rows.tsv of features-kind-pick-given-scope-contents-heldout37 and cover-rows.tsv of sampler-base-cost-read-heldout37. No fact reads this file.

  label-rows.tsv        arm, task, slot, then counts of cover events of the slot's visits within 600 s:
                        any: all cover events; first: first covers of a gold form in the run; first_r1, first_r2: first covers by a kept clause that reads at least 1 or 2 forms; first_late: first covers with the form's read forms covered earlier (a row of cond-fit.py)
  cover-slot-rows.tsv   arm, task, form, draw, first, slot, kind of the gold form, nreads, clause parents, cond (1 for a row of the conditional wait)

A cover whose visit has no slot row, past 600 s, is left out and counted.
"""
import collections
import csv
import json
HERE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-pick-pair-term-heldout37/'
MAP = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-kind-pick-given-scope-contents-heldout37/'
BASE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-base-cost-read-heldout37/'
vs = {(r['arm'], r['task'], r['visit']): r['slot'] for r in csv.DictReader(open(HERE + 'visit-slot-rows.tsv'), delimiter='\t')}
cov = {(r['arm'], r['task'], r['form'], r['draw']): r for r in csv.DictReader(open(BASE + 'cover-rows.tsv'), delimiter='\t') if r['arm'].startswith('base')}
form = {}
for r in csv.DictReader(open(BASE + 'form-rows.tsv'), delimiter='\t'):
    if r['arm'].startswith('base'):
        form[r['arm'], r['task'], r['form']] = r
acc = collections.defaultdict(collections.Counter)
n = collections.Counter()
w = csv.writer(open(HERE + 'cover-slot-rows.tsv', 'w', newline=''), delimiter='\t')
w.writerow(['arm', 'task', 'form', 'draw', 'first', 'slot', 'kind', 'nreads', 'clause_parents', 'cond', 'visit_kind'])
for r in csv.DictReader(open(MAP + 'map-cover-rows.tsv'), delimiter='\t'):
    if not r['arm'].startswith('base'):
        continue
    n['cover rows'] += 1
    slot = vs.get((r['arm'], r['task'], r['visit']))
    if slot is None:
        n['past 600 s or no visit'] += 1
        n['past 600 s or no visit, first'] += r['first'] == '1'
        continue
    c = cov[r['arm'], r['task'], r['form'], r['draw']]
    f = form[r['arm'], r['task'], r['form']]
    first = r['first'] == '1'
    cp = int(c['clause_parents'])
    rd = f['ready_draw']
    good = f['bits'] not in ('', 'None') and f['own_key'] == '1'
    cond = first and good and int(f['nreads']) > 0 and rd != '' and int(r['draw']) > int(rd)
    a = acc[r['arm'], r['task'], slot]
    a['any'] += 1
    a['first'] += first
    a['first_r1'] += first and cp >= 1
    a['first_r2'] += first and cp >= 2
    a['first_late'] += cond
    w.writerow([r['arm'], r['task'], r['form'], r['draw'], int(first), slot, r['kind'], f['nreads'], cp, int(cond), c['visit_kind']])
L = ('any', 'first', 'first_r1', 'first_r2', 'first_late')
o = csv.writer(open(HERE + 'label-rows.tsv', 'w', newline=''), delimiter='\t')
o.writerow(['arm', 'task', 'slot'] + list(L))
for k, a in sorted(acc.items()):
    o.writerow(list(k) + [a[x] for x in L])
    for x in L:
        n[x + ' slots'] += a[x] > 0
        n[x + ' events'] += a[x]
print(json.dumps(n, indent=0))
