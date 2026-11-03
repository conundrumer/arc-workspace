"""Throwaway: the summary's numbers for the report, and the record's file sizes."""
import csv
import json
import os

D = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-relation-pick-unread-forms-heldout37/'
S = json.load(open(D + 'summary.json'))
print(S['pool_tasks'])
print([{k: r[k] for k in ('set', 'forms_under', 'taken_under', 'by_kind')} for r in S['oracle'] if r['scope'].startswith('all')])
print([r['taken'] for r in S['oracle'] if r['scope'].startswith('all')][2])
for r in S['pool']:
    if r['group'] == 'all':
        print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()})
print(S['under_now'])
print(S['under_now_parents'])
rows = list(csv.DictReader(open(D + 'per-pick-unread.tsv'), delimiter='\t'))
v = [r for r in rows if r['form_kind'] == 'RULE' and r['form_valid'] == '1']
print(len(rows), len(v), sum(r['repeat_relation'] == '0' for r in v))
for f in os.scandir(D):
    if f.is_file():
        print(f.name, f.stat().st_size)
