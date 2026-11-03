"""Fits the co-read model from gold: which table shapes appear together in one gold form's reads. Writes model.json.
  python -I fit.py
Data: the 50 N600 training tasks. Table types from gold-sig-n600.jsonl, kinds and key sections from the N600 kit's gold text, whose reads equal those of gold-sig.
The 37 held-out tasks and the 22 ramp tasks are checked to be absent.
"""
import collections, json, sys
sys.dont_write_bytecode = True
HERE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/set-pick'
sys.path.insert(0, HERE)
import shapes as S
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/refit-tools')
import search_node_score_read as R

FW = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/'
W = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/'
KIT = W + 'kits/sampler-pool-dag-nodes-train50-final-8be414670/points-eval.json'


def gold_tables(task_sig, sexp):
    """[(shapes of each table, has Ident)] per gold form, [reads] per form, kinds."""
    lines = [x for x in sexp.strip().split('\n') if x.strip() and not x.startswith('(OUT')]
    info = R.gold_info(sexp)
    assert info['reads'] == task_sig['reads']
    tabs = collections.defaultdict(list)
    for t in task_sig['tables']:
        if 'types' in t:  # an unfinished table has no types; its form has no shape
            tabs[t['form']].append(t['types'])
    out = []
    for q, x in enumerate(lines):
        kind = info['kinds'][q]
        key = S.key_sig(kind, x)
        out.append(([S.levels(kind, ty, key) for ty in tabs[q]], any('Ident' in ty for ty in tabs[q])))
    return out, info['reads'], info['kinds']


def main():
    held = set(open(W + 'held/tasks.txt').read().split()) | set(open(W + 'held/ramp-fold.txt').read().split())
    sig = [json.loads(l) for l in open(FW + 'gold-sig-n600.jsonl')]
    gold = {x['task']: x['gold_sexp'] for x in json.load(open(KIT))}
    C = [collections.defaultdict(collections.Counter) for _ in range(4)]
    M = [collections.Counter() for _ in range(4)]
    idc = collections.Counter()
    st = collections.Counter()
    tasks = []
    fold = int(sys.argv[1]) if len(sys.argv) > 1 else None  # fold k: the tasks at sorted index i with i % 5 == k leave the fit
    order = sorted(r['task'] for r in sig)
    for r in sig:
        assert r['task'] not in held
        if fold is not None and order.index(r['task']) % 5 == fold:
            continue
        tasks.append(r['task'])
        forms, reads, kinds = gold_tables(r, gold[r['task']])
        src = S.ident_sources(range(len(forms)), [f[1] for f in forms], reads)
        st['forms'] += len(forms)
        for h, rd in enumerate(reads):
            st['reads_%s' % min(len(rd), 3)] += 1
            if len(rd) < 2:
                continue
            for q1 in rd:
                for q2 in rd:
                    if q1 == q2 or not forms[q1][0] or not forms[q2][0]:
                        continue
                    w = 1.0 / (len(forms[q1][0]) * len(forms[q2][0]))
                    st['pairs'] += 1
                    for a in forms[q1][0]:
                        for b in forms[q2][0]:
                            for L in range(4):
                                C[L][a[L]][b[L]] += w
                                M[L][b[L]] += w
                    idc['co_' + S.ident_class(src[q1], src[q2])] += 1
        # every ordered pair of distinct gold forms of the task, for the Ident base rate
        for q1 in range(len(forms)):
            for q2 in range(len(forms)):
                if q1 != q2:
                    idc['all_' + S.ident_class(src[q1], src[q2])] += 1
    # Ident factor: P(class | co-read, both Ident) / P(class | any pair, both Ident)
    co = idc['co_same'] + idc['co_diff']
    al = idc['all_same'] + idc['all_diff']
    fac = {'na': 1.0}
    for c in ('same', 'diff'):
        fac[c] = ((idc['co_' + c] + 1) / (co + 2)) / ((idc['all_' + c] + 1) / (al + 2))
    model = dict(tasks=sorted(tasks), C=[{a: dict(v) for a, v in c.items()} for c in C], M=[dict(m) for m in M], ident=fac, ident_counts=dict(idc), stats=dict(st))
    json.dump(model, open(HERE + ('/model.json' if fold is None else '/model-f%d.json' % fold), 'w'))
    print('tasks', len(tasks), dict(st))
    print('distinct shapes per level', [len(m) for m in M], 'anchors per level', [len(c) for c in C])
    print('ident counts', dict(idc), 'factors', fac)


main()
