"""Per job, the node facts the picks read: shape levels, Ident source, shipped score, refit score; and, for the N600 jobs, node age and cover lines.
Writes prep/<set>__<arm>__<task>.json. Resumable: a job with a file is skipped.
  python -I prep.py [BUDGET_SECONDS]
"""
import json, os, sys, time
sys.dont_write_bytecode = True
HERE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/set-pick'
sys.path.insert(0, HERE)
import shapes as S
SW = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker'
sys.path[:0] = [SW + '/refit-tools', SW]
import search_node_score_parity as PA

RUN = SW + '/runs/search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943/out'
N600 = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/sampler-worker/sampler-pool-dag-nodes-train50-600s/out/nodes_s0'
SIG = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/gold-sig-n600.jsonl'
KIT = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/refit/out-r1'


def jobs():
    for arm in ('bundle_s0', 'bundle_s1', 'refit_s0', 'refit_s1'):
        for t in json.load(open(KIT + '/refit-tasks.json'))['heldout37']:
            yield 'r1', arm, t, '%s/%s/%s/work/%s' % (RUN, arm, t, t)
    for t in sorted(os.listdir(N600)):
        yield 'n600', 'nodes_s0', t, '%s/%s/work/%s' % (N600, t, t)


def build(w, with_age):
    b = PA.load_bank(w + '.out.jsonl.bank')
    nodes, forms, pol = b['nodes'], b['forms'], b['policy']
    ids = sorted(nodes)
    assert ids == list(range(len(ids)))
    kinds = [forms[nodes[i].form].kind for i in ids]
    lv = [S.levels(kinds[i], nodes[i].table_types, S.key_sig(kinds[i], nodes[i].clause)) for i in ids]
    hi = {i: 'Ident' in nodes[i].table_types for i in ids}
    src = S.ident_sources(ids, hi, {i: nodes[i].parents for i in ids})
    ship = pol.get('score_ship') or pol['score']
    rec = dict(n=len(ids), L=[[x[L] for x in lv] for L in range(4)], src=[sorted(src[i]) for i in ids],
               ship=[ship[i] for i in ids], refit=[pol['score'][i] for i in ids] if 'score_ship' in pol else None)
    if with_age:
        rec['age'] = [nodes[i].age for i in ids]
        rec['draws'] = b['draws']
        # N600 cover lines name no node: a covering node is a node whose table equals a gold table of gold-sig-n600 (types and examples), as the node score fit labels it
        task = w.split('/')[-1]
        by_pair = {}
        for l in open(SIG):
            r = json.loads(l)
            if r['task'] == task:
                for x in r['tables']:
                    if x.get('examples') is not None:
                        by_pair.setdefault(json.dumps([x['types'], x['examples']]), set()).add(x['form'])
        cov = []
        for i in ids:
            for g in by_pair.get(json.dumps([sorted(nodes[i].table_types), nodes[i].examples]), ()):
                cov.append(dict(gold=g, node=i, draw=nodes[i].age))
        rec['covers'] = cov
        rec['uses_end'] = [pol['uses'][i] for i in ids]
    return rec


def main():
    budget = float(sys.argv[1]) if len(sys.argv) > 1 else 15
    t0 = time.time()
    os.makedirs(HERE + '/prep', exist_ok=True)
    done = todo = 0
    for st, arm, t, w in jobs():
        out = '%s/prep/%s__%s__%s.json' % (HERE, st, arm, t)
        if os.path.exists(out):
            done += 1
            continue
        if time.time() - t0 > budget:
            todo += 1
            continue
        rec = build(w, st == 'n600')
        json.dump(rec, open(out + '.tmp', 'w'))
        os.replace(out + '.tmp', out)
        done += 1
    print('done', done, 'todo', todo, 'seconds %.1f' % (time.time() - t0))


main()
