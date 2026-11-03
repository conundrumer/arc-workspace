"""Probe: the relation map with port renames, the table check of the target, and the walks, for the C forms of the bundle arms. Streams one line per form to
probe/p4.jsonl and skips forms done. Stops at the end of the form in progress after BUDGET seconds.

  p4.py BUDGET [--nowalk]
"""
import bisect, collections, csv, json, os, re, sys, time
t0 = time.time()
BUDGET = float(sys.argv[1])
WALK = '--nowalk' not in sys.argv
KIT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/kits/sampler-pool-tiekey-value-0729e4943'
ENGINE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-0a7d32160/py313-path'
RUN = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943'
OLD = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = HERE + ('/p4.jsonl' if WALK else '/p4-map.jsonl')
os.environ.update(P_DAG='1', ORDER_FREE='tie,key', ARCLOG_IDENT_SOURCE='value', RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', ONE_REPAIR='30', CHOOSE_LIFT='0')
sys.dont_write_bytecode = True
sys.path[:0] = [KIT + '/model/study/sampler', ENGINE, '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/refit-tools']
import live, or_q, superdag as D, form_orders as O
import search_node_score_parity as P
NAME = re.compile(r'&[rf]\d+(?:\.\w+)?')
sampler = live.Sampler(KIT + '/models-tk')
pe = {x['task']: x['gold_sexp'] for x in json.load(open(KIT + '/points-eval.json'))}
items = [(x['arm'], x['task'], int(x['g'])) for x in csv.DictReader(open(RUN + '/scope-loss/forms.tsv'), delimiter='\t') if x['class'] == 'C' and x['arm'].startswith('bundle')]
done = set()
if os.path.exists(OUT):
    for l in open(OUT):
        x = json.loads(l)
        done.add((x['arm'], x['task'], x['g']))
todo = [x for x in items if x not in done]


def col_sigs(tb):
    spans, at = [], 0
    for w in tb['widths']:
        spans.append((at, at + w))
        at += w
    entries = [(tuple(ex), rows) for ex, _, rows, _, _ in tb['entries']]
    return [(str(t), hash(tuple(sorted((ex, hash(frozenset(r[a:b] for r in rows))) for ex, rows in entries)))) for t, (a, b) in zip(tb['types'], spans)]


def relations(texts, sess, d):
    run = D.Run(sampler.pri, sess, 0, time.monotonic() + 60, d, live.Limits())
    run.collect = []
    dec, pg = run.scope(texts)
    out = {}
    for i, ct in enumerate(run.collect):
        for s, j in D.relation_tables(ct):
            try:
                tb = D.S.parse_table(D.OneTable(ct, j))
            except Exception:  # noqa: BLE001  a table past the work cap, as gold_keys counts it
                continue
            nm = pg.names.get('&r%d' % s, '&r%d' % s)
            h, _, sub = nm.partition('.')
            out[(pg.written.get(h, h), int(sub) if sub else None)] = dict(slot=s, form=i, key=D.table_key(tb)[0], labels=list(tb['labels']), sigs=col_sigs(tb))
    return out


def port_map(gr, sr):
    """{gold label: scope label} by column signature, or None where the labels are not plain."""
    if '' in gr['labels'] or '' in sr['labels'] or len(set(gr['labels'])) < len(gr['labels']) or len(set(sr['labels'])) < len(sr['labels']):
        return None
    free = collections.defaultdict(list)
    for p, sg in enumerate(sr['sigs']):
        free[sg].append(p)
    out = {}
    for p, sg in enumerate(gr['sigs']):
        if not free[sg]:
            return None
        out[gr['labels'][p]] = sr['labels'][free[sg].pop(0)]
    return out


def rename(tree, ref, new, pm):
    """Renames the atoms of relation ref in tree: the relation to new, and each port :X to :pm[X]. Gives the count of record ports left as they are."""
    rec = 0
    if isinstance(tree, list):
        if tree and tree[0] == ref:
            tree[0] = new
            for p in tree[1:]:
                if isinstance(p, list) and p and p[0].startswith(':'):
                    if any(isinstance(y, list) for y in p[1:]):
                        rec += 1
                    elif pm is not None and p[0][1:] in pm:
                        p[0] = ':' + pm[p[0][1:]]
        for y in tree:
            rec += rename(y, ref, new, pm)
    return rec


sl_cache, r1_cache, banks = {}, {}, {}
with open(OUT, 'a') as fh:
    for arm, task, g in todo:
        if time.time() - t0 > BUDGET:
            break
        t1 = time.time()
        row = dict(arm=arm, task=task, g=g)
        lines = [l for l in pe[task].strip().split('\n') if not l.startswith('(OUT')]
        heads = [l.split()[1] for l in lines]
        kind = lines[g].split()[0][1:]
        sl = json.load(open('%s/scope-loss/cache/%s__%s.json' % (OLD, arm, task)))
        r1 = json.load(open('%s/r1-forms/cache/%s__%s.json' % (OLD, arm, task)))
        rows = next(x for x in sl['golds'] if x['g'] == g)['rows']
        ops = {o['i']: o for o in sl['ops']}
        hk = [x['i'] for x in rows if x['hk'] and ops[x['i']]['lost'] == 0]
        if not hk:
            row['status'] = 'no held-with-kind opening with lost 0'
            fh.write(json.dumps(row) + '\n'); fh.flush(); continue
        i = max(hk, key=lambda i: (ops[i]['slot_tries'], -i))
        allops = sorted(r1['openings'], key=lambda o: o['time'])
        o = [x for x in allops if x['picks']][i]
        times = [x['time'] for x in allops]
        k = bisect.bisect_right(times, o['time'])
        nxt = times[k] if k < len(times) else float('inf')
        v = next(v for v in sorted(r1['visits'], key=lambda v: v['time']) if o['time'] <= v['time'] < nxt and not v['resume'])
        bank = P.load_bank('%s/out/%s/%s/work/%s.out.jsonl.bank' % (RUN, arm, task, task))
        fs = bank['forms']
        fids = sorted(v['fids'], key=lambda f: (fs[f].depth, f))
        scope = [fs[f].text for f in fids]
        sess, d, _ = D.session_of(task)
        grel = relations(lines, sess, d)
        srel = relations(scope, sess, d)
        V = sess.vocabulary
        toks = or_q.gold_rest(sess, lines[:g], lines[g], kind)
        rel_toks = [V.name(t) for t in toks if re.fullmatch(r'&r\d+', V.name(t) or '')]
        refs = [m for m in NAME.findall(lines[g]) if m != heads[g]]
        by_slot = {val['slot']: kk for kk, val in grel.items()}
        tree = O.parse(lines[g])[0]
        how, recs = [], 0
        if len(refs) != len(rel_toks):
            how.append('refs and tokens differ')
        for ref in dict.fromkeys(refs):
            tok = rel_toks[refs.index(ref)] if len(refs) == len(rel_toks) else None
            gk = by_slot.get(int(tok[2:])) if tok else None
            if gk is None:
                how.append('%s: no gold table' % ref); continue
            gr = grel[gk]
            cands = sorted((kk for kk, val in srel.items() if val['key'] == gr['key']), key=lambda kk: (kk[1] is not None, kk[1] != gk[1]))
            if not cands:
                how.append('%s: not in scope' % ref); continue
            why = []
            for h, j in cands:
                sr = srel[(h, j)]
                sub = ref.partition('.')[2]
                if j is not None:
                    if not sub or gk[1] != j:
                        why.append('INIT relation of another place'); continue
                    new = '%s.%s' % (h, sub)
                else:
                    new = h
                same = gr['labels'] == sr['labels']
                pm = None if same else port_map(gr, sr)
                if not same and pm is None:
                    why.append('ports not mapped %s %s' % (gr['labels'], sr['labels'])); continue
                recs += rename(tree, ref, new, pm)
                how.append('%s -> %s %s' % (ref, new, 'same labels' if same else 'renamed %s' % pm))
                break
            else:
                how.append('%s: %s' % (ref, ' / '.join(why)))
        if recs:
            how.append('record ports %d' % recs)
        target = O.unparse(tree)
        row.update(kind=kind, opening=i, n_hk=len(hk), slot_tries=ops[i]['slot_tries'], scope_n=len(scope), how=how, target=target[:300])
        bad = [h for h in how if ':' in h and '->' not in h]
        if bad:
            row['status'] = 'unmapped'
        else:
            try:
                target = or_q.sorted_fields(target, sess, scope)
                trel = relations(scope + [target], sess, d)
                tkeys = sorted(str(val['key']) for val in trel.values() if val['form'] == len(scope))
                gkeys = sorted(str(val['key']) for val in grel.values() if val['form'] == g)
                row['table_check'] = tkeys == gkeys
                row['status'] = 'mapped' if tkeys == gkeys else 'table differs'
            except Exception as e:
                row.update(status='replay error', error=repr(e)[:200])
            if WALK and row['status'] == 'mapped':
                tw = time.time()
                S = or_q.walk(sampler, task, arm, [g, 0], scope, target, sess, d, kind)
                gscope = or_q.canonical_scope(lines, g)
                R = or_q.walk(sampler, task, arm, [g, 1], gscope, or_q.sorted_fields(lines[g], sess, gscope), sess, d, kind)
                row.update(S=S.get('total'), R=R.get('total'), S_ok=not (S.get('bad') or S.get('dead') or S.get('left')), R_ok=not (R.get('bad') or R.get('dead') or R.get('left')),
                           S_orders=S['orders'].get('orders'), S_valid=S['orders'].get('valid'), R_valid=R['orders'].get('valid'), walk_s=round(time.time() - tw, 1),
                           S_parts=S['parts'], R_parts=R['parts'], S_bad=S.get('bad'), R_bad=R.get('bad'))
        row['sec'] = round(time.time() - t1, 1)
        fh.write(json.dumps(row) + '\n'); fh.flush()
        print(arm, task, g, row['status'], row.get('S'), row.get('R'), row['sec'], '|', '; '.join(how)[:200], flush=True)
print('done %d todo %d, %.1f s' % (len(done) + sum(1 for _ in open(OUT)) - len(done), len(items) - sum(1 for _ in open(OUT)), time.time() - t0))
