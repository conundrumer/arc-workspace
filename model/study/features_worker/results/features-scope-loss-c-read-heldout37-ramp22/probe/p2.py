"""Probe: for the C forms of the bundle arms, compare each read's gold text with the text of its covering bank forms (names replaced by placeholders)."""
import collections, csv, json, re, sys
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/refit-tools')
import search_node_score_parity as P
RUN = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943'
KIT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943'
NAME = re.compile(r'&[rf]\d+')
pe = {x['task']: x['gold_sexp'] for x in json.load(open(KIT + '/points-eval.json'))}
rows = [x for x in csv.DictReader(open(RUN + '/scope-loss/forms.tsv'), delimiter='\t') if x['class'] == 'C' and x['arm'].startswith('bundle')]
arms = sys.argv[1:] or ['bundle_s0']
tally = collections.Counter()
bytask = collections.defaultdict(list)
for x in rows:
    if x['arm'] in arms:
        bytask[(x['arm'], x['task'])].append(int(x['g']))
def norm(t):
    return NAME.sub('&X', t)
for (arm, task), gs in sorted(bytask.items()):
    lines = [l for l in pe[task].strip().split('\n') if not l.startswith('(OUT')]
    heads = [l.split()[1] for l in lines]
    w = '%s/out/%s/%s/work/%s.out.jsonl' % (RUN, arm, task, task)
    b = P.load_bank(w + '.bank')
    fs, ns = b['forms'], b['nodes']
    covers = [json.loads(l) for l in open(w + '.cover')]
    for g in gs:
        reads = sorted({heads.index(m.split('.')[0]) for m in NAME.findall(lines[g]) if m.split('.')[0] in heads and m.split('.')[0] != heads[g]})
        for q in reads:
            cn = [c['node'] for c in covers if c['gold'] == q and c['node'] in ns]
            texts = [fs[ns[n].form].text for n in cn]
            same = any(norm(t) == norm(lines[q]) for t in texts)
            kinds = [fs[ns[n].form].kind for n in cn]
            tally['read same text' if same else ('read no kept cover' if not cn else 'read other text')] += 1
            tally['read kind %s' % lines[q].split()[0][1:]] += 1
            subs = [m for m in NAME.findall(lines[g]) if m.startswith(heads[q])]
            print(arm, task, g, 'q', q, 'same' if same else 'other', lines[q][:90], '|', texts[0][:90] if texts else None, '| refs', set(re.findall(re.escape(heads[q]) + r'(?:\.\w+)?\b', lines[g])))
print(dict(tally))
