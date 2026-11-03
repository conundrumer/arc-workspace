import pickle, sys, collections, json, csv, gzip, re, os
K = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-extended-text-pass1-8be414670/'


class S:
    def __init__(s, *a, **k):
        pass

    def __setstate__(s, x):
        pass


class U(pickle.Unpickler):
    def find_class(self, m, n):
        try:
            return super().find_class(m, n)
        except Exception:
            return type(n, (S,), {})


for m in ('models-base', 'models-cover'):
    d = U(open(K + m + '/live_priors.pkl', 'rb')).load()
    k1 = d['kinds1']
    got = collections.Counter()
    for c in k1.values():
        got.update(c)
    print(m, d.get('tasks'), dict(got))
R = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-base-cost-read-heldout37/kind-rows.tsv'
c = collections.Counter()
e = collections.Counter()
for r in csv.DictReader(open(R), delimiter='\t'):
    a = r['arm'][:4]
    c[a, r['kind']] += int(r['visits']) - int(r['resume_visits'])
    e[a, r['kind']] += int(r['tries'])
print(sorted(c.items()))
print(sorted(e.items()))
G = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gen-v3-11f6a212c/'
ev = set(open('/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/arm/eval-tasks.txt').read().split())
held = set(open('/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/held/tasks.txt').read().split())
print(len(ev), len(held), len(held & ev))
A = sorted(os.listdir(G + 'ast-corpus'))
print(len(A), len(set(A) & ev))
arc = {f[:-7] for f in os.listdir(G + 'corpus/gen') if f.endswith('.arclog')}
print(len(arc), len(arc - set(A)), sorted(arc - set(A))[:5], len(set(A) - arc))
c = collections.Counter()
mism = n = noalt = 0
for t in A:
    s = json.loads(gzip.open(G + 'ast-corpus/%s/pairs.jsonl.gz' % t, 'rt').readline())['gold_sexp']
    ks = [l.split(' ', 1)[0][1:] for l in s.strip().split('\n')]
    if t in ev:
        continue
    c.update(ks)
    src = open(G + 'corpus/gen/%s.arclog' % t).read()
    if 'ALTS' in src or 'ALT ' in src:
        continue
    noalt += 1
    a = collections.Counter(re.findall(r'^\((RULE|DET|INIT|RIGID_DET|CHOOSE|OUT|RULE_OR_DET|DET_OR_RULE)\s', src, re.M))
    b = collections.Counter(ks)
    n += 1
    if a != b:
        mism += 1
        if mism < 4:
            print(t, a, b)
print(c, 'no-ALT tasks', noalt, 'kind count mismatch', mism)
