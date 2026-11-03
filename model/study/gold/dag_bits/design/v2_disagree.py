import glob, hashlib, json, sys, time
import gold_fork_reads as F, gold_pod_bits as P, gold_dag_bits as B
import form_orders as O
import or_q, live, live_try
R = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/64993706-bdea-4acd-bcaf-7d7b1e3ea40a/scratchpad/readcmp/rows.jsonl'
Dd = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-dag-bits/pod-all/'
pod = {}
for f in glob.glob(Dd + 'rows-*.jsonl'):
    for l in open(f):
        try: r = json.loads(l)
        except Exception: continue
        if r['task'] in ('8e5c0c38', '97d7923e', '89565ca0', '3a25b0d8'): pod[r['task']] = r
kit = {}
for l in open(R):
    try: r = json.loads(l)
    except Exception: continue
    kit[r.get('task')] = r
print('kit row keys', sorted(next(iter(kit.values())).keys())[:30], 'code', {t: (r.get('code'), r.get('stage')) for t, r in kit.items() if t in pod})
for t, p in pod.items():
    k = kit.get(t)
    if not k: print('no kit row', t); continue
    pf = {f['line']: f for f in p['forms']}
    for f in k['forms']:
        g = pf.get(f['line'])
        if g is None: continue
        a, b = f.get('bits'), g.get('bits')
        if (a is None) != (b is None) or (a is not None and abs(a - b) > 0.02):
            print(t, f['line'], f.get('kind'), 'kit', a, f.get('status'), 'nscope', f.get('nscope'), 'written', f.get('written'), '| walk', b, g.get('status'), 'nscope', g.get('nscope'), 'written', g.get('written'), 'bad', str(g.get('bad'))[:90], 'dead', str(g.get('dead'))[:70])
t = '97d7923e'
P.load_sampler(); F.sampler = P.sampler
allv = json.load(open('all-lines.json'))
json.dump({t: allv[t]}, open('scratch/v2-lines-%s.json' % t, 'w'))
B.setup(t, 'scratch/v2-lines-%s.json' % t, 600)
ls = [x for x in B.base_lines if not x.startswith('(OUT')]
print('base_sha match', P.sha(B.base_lines) == pod[t]['base_sha'], 'kit', hashlib.sha256('\n'.join(B.base_lines).encode()).hexdigest()[:16], pod[t]['base_sha'])
sess, tj, _ = live_try.session_of(t)
A, _ = or_q.canonical_lines(ls, sess)
C, _ = B.canonical(ls)
print('canonical forms differ', sum(x != y for x, y in zip(A, C)), 'of', len(ls))
shown = 0
for i in (21, 22, 23):
    kind = ls[i].split()[0].lstrip('(')
    sa, sc = or_q.canonical_scope(A, i), B.scope_of(C, i)
    print('LINE', i, kind, 'scope equal', sa == sc, len(sa), len(sc), 'target', ls[i][:220])
    for x, y in zip(sa, sc):
        if x != y and shown < 4:
            shown += 1; print('  or_q', x[:230]); print('  tool', y[:230])
    for name, sco in (('or_q scope', sa), ('tool scope', sc)):
        for tname, target in (('sorted_fields', or_q.sorted_fields(ls[i], sess, sco)), ('portsort', B.portsort(sco, ls[i]))):
            s2, j2, _ = live_try.session_of(t)
            try:
                w = or_q.walk_order(P.sampler, t, kind, [len(sco), 0], sco, target, s2, j2, kind)
                print('  ', name, tname, 'clean', or_q.clean(w), 'bits', round(sum(w['parts'].values()), 2), 'bad', str(w['bad'])[:120], 'dead', str(w['dead'])[:80], flush=True)
            except Exception as e:
                print('  ', name, tname, 'ERROR', type(e).__name__, str(e)[:140], flush=True)
