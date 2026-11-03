"""Throwaway: the text of corpus-v3mix gold for two non-held tasks, and the forms lists of the rank record."""
import gzip
import json

C = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/corpus-v3mix/'
R = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-relation-pick-rank-context-rows-heldout37/'
for t in ('10fcaaa3', '00d62c1b'):
    with gzip.open(C + t + '/pairs.jsonl.gz', 'rt') as f:
        r = json.loads(f.readline())
    print(t, list(r.keys())[:10])
    print(r['gold_sexp'][:1200])
for n in ('forms-test.json', 'forms-train.json'):
    f = json.load(open(R + n))
    print(n, len(f), len({x[4] for x in f}), f[:2])
print(open(R + 'partial.md').read())
print(open(R + 'walks/test-before-0.log').read()[-500:])
