"""Probe: one form end to end. The held-with-kind opening of most slot tries, its recorded scope, the relation map by table key, the target text, and or_q.walk
under the recorded scope (S) and under gold's ancestor scope (R). Prints times.

  p3.py ARM TASK G
"""
import bisect, collections, json, os, re, sys, time
t0 = time.time()
KIT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943'
ENGINE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-0a7d32160/py313-path'
RUN = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943'
OLD = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad'
os.environ.update(P_DAG='1', ORDER_FREE='tie,key', ARCLOG_IDENT_SOURCE='value', RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', ONE_REPAIR='30', CHOOSE_LIFT='0')
sys.dont_write_bytecode = True
sys.path[:0] = [KIT + '/model/study/sampler', ENGINE, '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/refit-tools']
import live, live_try, or_q, superdag as D
import search_node_score_parity as P
arm, task, g = sys.argv[1], sys.argv[2], int(sys.argv[3])
NAME = re.compile(r'&[rf]\d+(?:\.\w+)?')
sampler = live.Sampler(KIT + '/models-tk')
pe = {x['task']: x['gold_sexp'] for x in json.load(open(KIT + '/points-eval.json'))}
lines = [l for l in pe[task].strip().split('\n') if not l.startswith('(OUT')]
heads = [l.split()[1] for l in lines]
kind = lines[g].split()[0][1:]
sl = json.load(open('%s/scope-loss/cache/%s__%s.json' % (OLD, arm, task)))
r1 = json.load(open('%s/r1-forms/cache/%s__%s.json' % (OLD, arm, task)))
rows = next(x for x in sl['golds'] if x['g'] == g)['rows']
ops = {o['i']: o for o in sl['ops']}
hk = [x['i'] for x in rows if x['hk'] and ops[x['i']]['lost'] == 0]
i = max(hk, key=lambda i: (ops[i]['slot_tries'], -i))
allops = sorted(r1['openings'], key=lambda o: o['time'])
pick_ops = [o for o in allops if o['picks']]
o = pick_ops[i]
times = [x['time'] for x in allops]
nxt = times[bisect.bisect_right(times, o['time'])] if bisect.bisect_right(times, o['time']) < len(times) else float('inf')
vs = sorted(r1['visits'], key=lambda v: v['time'])
v = next(v for v in vs if o['time'] <= v['time'] < nxt and not v['resume'])
assert v['kind'] == kind, (v['kind'], kind)
bank = P.load_bank('%s/out/%s/%s/work/%s.out.jsonl.bank' % (RUN, arm, task, task))
fs = bank['forms']
fids = sorted(v['fids'], key=lambda f: (fs[f].depth, f))
scope = [fs[f].text for f in fids]
print('opening %d of %d hk, slot tries %d, scope %d forms; load %.1f s' % (i, len(hk), ops[i]['slot_tries'], len(scope), time.time() - t0), flush=True)


def col_sigs(tb):
    spans, at = [], 0
    for w in tb['widths']:
        spans.append((at, at + w))
        at += w
    entries = [(tuple(ex), rows) for ex, _, rows, _, _ in tb['entries']]
    return [(str(t), hash(tuple(sorted((ex, hash(frozenset(r[a:b] for r in rows))) for ex, rows in entries)))) for t, (a, b) in zip(tb['types'], spans)]


def relations(texts, sess, d):
    """{(written head, j or None): (slot, key, labels, sigs)} of a replay."""
    run = D.Run(sampler.pri, sess, 0, time.monotonic() + 60, d, live.Limits())
    run.collect = []
    dec, pg = run.scope(texts)
    out = {}
    for ct in run.collect:
        for s, j in D.relation_tables(ct):
            tb = D.S.parse_table(D.OneTable(ct, j))
            nm = pg.names.get('&r%d' % s, '&r%d' % s)
            h, _, sub = nm.partition('.')
            out[(pg.written.get(h, h), int(sub) if sub else None)] = (s, D.table_key(tb)[0], tb['labels'], col_sigs(tb))
    return out, pg


sess, d, _ = D.session_of(task)
t1 = time.time()
grel, gpg = relations(lines, sess, d)
srel, spg = relations(scope, sess, d)
print('replays %.1f s: gold %d relations, scope %d relations' % (time.time() - t1, len(grel), len(srel)), flush=True)
# gold refs of g, in text order, with their slots from g's tokens
toks = or_q.gold_rest(sess, lines[:g], lines[g], kind)
V = sess.vocabulary
rel_toks = [V.name(t) for t in toks if re.fullmatch(r'&r\d+', V.name(t) or '')]
refs = [m for m in NAME.findall(lines[g]) if m != heads[g]]
print('refs', refs, 'rel tokens', rel_toks)
by_slot = {val[0]: k for k, val in grel.items()}
target = lines[g]
for ref, tok in zip(refs, rel_toks):
    gk = by_slot.get(int(tok[2:]))
    key = grel[gk][1] if gk else None
    cands = [k for k, val in srel.items() if val[1] == key]
    print(ref, '-> gold rel', gk, 'scope candidates', cands)
    if cands:
        (h, j) = cands[0]
        sub = ref.partition('.')[2]
        new = h + ('.' + sub if j is not None and sub else '')
        target = re.sub(re.escape(ref) + r'(?![\w.])', new, target)
t2 = time.time()
target = or_q.sorted_fields(target, sess, scope)
print('target', target[:300], flush=True)
S = or_q.walk(sampler, task, arm, [g, 0], scope, target, sess, d, kind)
t3 = time.time()
print('S walk %.1f s: total %s orders %s' % (t3 - t2, S.get('total'), {k: S['orders'].get(k) for k in ('orders', 'exact', 'walked', 'valid')}), flush=True)
print('S parts', S['parts'])
gscope = or_q.canonical_scope(lines, g)
gt = or_q.sorted_fields(lines[g], sess, gscope)
R = or_q.walk(sampler, task, arm, [g, 1], gscope, gt, sess, d, kind)
t4 = time.time()
print('R walk %.1f s (scope %d forms): total %s orders %s' % (t4 - t3, len(gscope), R.get('total'), {k: R['orders'].get(k) for k in ('orders', 'exact', 'walked', 'valid')}), flush=True)
print('R parts', R['parts'])
print('atoms S', S.get('atoms'))
print('atoms R', R.get('atoms'))
print('total %.1f s' % (time.time() - t0))
