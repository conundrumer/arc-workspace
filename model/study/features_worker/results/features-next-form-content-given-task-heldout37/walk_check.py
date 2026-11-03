"""Counts the walk rows whose total equals the census bits, and whose relation picks sum to the census's relation parts. Writes walk-check.json."""
import glob
import json

R = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-next-form-content-given-task-heldout37/'
c = {}
for x in open('/Users/davidlu/code/arc-workspace/work/lm/data-study/census/census-bands-cheapest/forms.jsonl'):
    r = json.loads(x)
    c[r['task'], r['form']] = r
out = {}
for split, folder in (('dev', 'walks'), ('held', 'walks-held')):
    n = same = no_bits = rel_same = errors = 0
    for p in glob.glob(R + folder + '/walk-%s-*.jsonl' % split):
        for x in open(p):
            r = json.loads(x)
            n += 1
            e = c.get((r['task'], r['form']))
            errors += bool(r.get('error'))
            if not e or e.get('bits') is None:
                no_bits += 1
                continue
            same += r['total'] is not None and abs(r['total'] - e['bits']) < .02
            rel = sum(v for k, v in e['parts'].items() if k.endswith('relation') or k.endswith('relation (op)'))
            rel_same += abs(sum(q['q_bits'] for q in r['picks']) - rel) < .05
    out[split] = dict(forms=n, census_no_bits=no_bits, total_equal=same, relation_part_equal=rel_same, errors=errors)
json.dump(out, open(R + 'walk-check.json', 'w'), indent=1)
print(out)
