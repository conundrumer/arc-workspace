"""For the forms whose read relation is absent from the recorded scope: the gold form that the clause reads, the cover lines of that gold
form before the opening, the covering nodes' forms and texts, and which of those forms the recorded scope holds. Records only, no engine."""
import bisect
import json
import re
import sys

KIT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943'
RUN = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943'
OLD = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad'
REC = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/9899b29d-4bf5-4cd3-9cdc-a669f9aea9b2/scratchpad/records/features-scope-loss-c-read-heldout37-ramp22'
sys.path[:0] = ['/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/refit-tools']
import search_node_score_parity as P  # noqa: E402

pe = {x['task']: x['gold_sexp'] for x in json.load(open(KIT + '/points-eval.json'))}
rows = [json.loads(l) for f in ('forms.0of2.jsonl', 'forms.1of2.jsonl') for l in open('%s/%s' % (REC, f))]
for r in rows:
    if r['status'] != 'read relation not in the scope':
        continue
    arm, task, g = r['arm'], r['task'], r['g']
    lines = [l for l in pe[task].strip().split('\n') if not l.startswith('(OUT')]
    heads = [l.split()[1] for l in lines]
    ref = r['absent'][0]
    q = heads.index(ref.split('.')[0])
    print('=' * 100)
    print(arm, task, 'g%d' % g, 'reads', ref, '-> gold form q=%d' % q)
    print('  gold q text:', lines[q][:400])
    r1 = json.load(open('%s/r1-forms/cache/%s__%s.json' % (OLD, arm, task)))
    bank = P.load_bank('%s/out/%s/%s/work/%s.out.jsonl.bank' % (RUN, arm, task, task))
    fs, nodes = bank['forms'], bank['nodes']
    allops = sorted(r1['openings'], key=lambda o: o['time'])
    o = [x for x in allops if x['picks']][r['opening']]
    print('  opening time', o['time'], 'scope fids', r['scope_fids'])
    cov = [c for c in r1['covers'] if c['gold'] == q]
    print('  cover lines of q:', len(cov))
    for c in sorted(cov, key=lambda c: c['time'])[:6]:
        f = c.get('form', nodes[c['node']].form if c['node'] in nodes else None)
        inscope = f in r['scope_fids']
        print('   node %s form %s kept %s time %.1f before_opening %s in_scope %s' % (c['node'], f, c['kept'], c['time'], c['time'] < o['time'], inscope))
        if f in fs:
            print('     text:', fs[f].text[:400], '| kind', fs[f].kind, 'depth', fs[f].depth, 'parents', fs[f].parents, 'nodes of form', fs[f].nodes)
    # any scope form whose text equals gold q up to names
    norm = lambda t: re.sub(r'[*^](?=[A-Za-z_])', '', re.sub(r'&[rf]\d+(\.\w+)?', '&', t))  # noqa: E731
    same = [f for f in r['scope_fids'] if norm(fs[f].text) == norm(lines[q])]
    print('  scope forms with gold q text up to names:', same)
    comp = lines[q].split()[2] if lines[q].startswith('(INIT') else None
    print('  scope forms that are INITs of component %s:' % comp, [(f, fs[f].text[:200]) for f in r['scope_fids'] if fs[f].text.startswith('(INIT') and fs[f].text.split()[2] == comp])
