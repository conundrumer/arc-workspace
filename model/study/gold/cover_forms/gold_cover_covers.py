"""Writes covers.json: each task's covering clauses, written in gold's names, from swaps Consistent on train whose other forms are current. The forms of a candidate are the forms it reads, then the clause."""
import collections, glob, json
L = json.load(open('/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-helper-forms-a036da074/lines.json'))
out, tally = collections.defaultdict(list), collections.Counter()
seen = set()
for src, files in (('train', ['/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-cover-rows/swaps-all.jsonl']), ('heldout', sorted(glob.glob('swaps-heldout-*.jsonl')))):
    for f in files:
        for l in open(f):
            r = json.loads(l)
            tally[src, 'rows'] += 1
            if r.get('train') != 'Consistent' or 'program' not in r:
                continue
            tally[src, 'consistent'] += 1
            t, i = r['task'], int(r['swap_line'])
            ls = [x for x in r['program'].splitlines() if x.strip()]
            n = len(L.get(t, []))
            extra = len(ls) - n
            if not n or extra < 0 or ls[:i] != L[t][:i] or ls[i + extra + 1:] != L[t][i + 1:]:
                tally[src, 'not current'] += 1
                continue
            forms = ls[i:i + extra + 1]
            if (t, i, tuple(forms)) in seen:
                continue
            seen.add((t, i, tuple(forms)))
            tally[src, 'kept'] += 1
            out[t].append(dict(line=i, forms=forms, source=src))
json.dump(out, open('covers.json', 'w'))
print(dict(tally), len(out), sum(len(v) for v in out.values()))
