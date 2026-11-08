"""The old graph of a set ($UNION_SCRATCH/graph-before-maps/graph-{tables,prods,tasks}-SET.jsonl; UNION_SCRATCH default: the scratchpad of session 64993706) against the new one (graph-*-SET.jsonl in work/lm/data-study/gold/gold-union): prints counts of tasks, tables, queries, OR tables, splits and joins of old tables, and changes of goal depth and path bits.

  .venv/bin/python graph_compare.py SET
"""
import json, os, sys, collections
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../..'))  # model/study
import study_zst as Z
s = sys.argv[1]
OLD = os.environ.get('UNION_SCRATCH', '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/64993706-bdea-4acd-bcaf-7d7b1e3ea40a/scratchpad') + '/graph-before-maps/'
NEW = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-union/'
def load(d, f):
    got = collections.defaultdict(list)
    for l in Z.open_text(d + 'graph-%s-%s.jsonl' % (f, s)):
        r = json.loads(l); got[r['task']].append(r)
    return got
ot, nt, op, np_, ok, nk = load(OLD, 'tables'), load(NEW, 'tables'), load(OLD, 'prods'), load(NEW, 'prods'), load(OLD, 'tasks'), load(NEW, 'tasks')
c = collections.Counter(); ex = collections.defaultdict(list)
import gzip, os
def types_of(t):
    p = '/Users/davidlu/code/arc-workspace/work/lm/data-study/samples/%s/rows/%s.jsonl.gz' % (s, t)
    if not os.path.exists(p): return {}
    got = {}
    for l in gzip.open(p, 'rt'):
        r = json.loads(l)
        if r['t'] == 'function':
            for o in r['outputs']: got[r['id'], o['name']] = tuple(sorted(x for x in o['types'] if x != 'Example'))
    return got
for t in sorted(set(ok) | set(nk)):
    o, n = ok.get(t, [{}])[0], nk.get(t, [{}])[0]
    if o.get('error') or n.get('error'):
        c['task error old %s new %s' % (o.get('error'), n.get('error'))] += 1
        if o.get('error') or n.get('error'): continue
    c['tasks'] += 1
    c['source ' + str(n.get('tables_source'))] += 1
    c['unmatched queries'] += n.get('unmatched') or 0
    c['assignments with shared DET value sets'] += n.get('shared_value_sets') or 0
    c['old tables'] += len(ot[t]); c['new tables'] += len(nt[t])
    c['old productions (idents)'] += len(op[t]); c['new queries (QueryHash)'] += len(np_[t])
    c['new queries holding several idents'] += sum(len(p['idents']) > 1 for p in np_[t])
    c['new capped tables'] += sum(r.get('capped', False) for r in nt[t])
    c['old OR tables'] += sum(r['productions'] > 1 for r in ot[t]); c['new OR tables'] += sum(r['productions'] > 1 for r in nt[t])
    where = collections.defaultdict(set)
    for r in nt[t]:
        for m in r['members']: where[m].add(r['table'])
    olds = collections.defaultdict(set)
    ty = types_of(t)
    ntypes = {r['table']: {ty.get(tuple(x)) for x in r.get('tables', [])} for r in nt[t]}
    for r in ot[t]:
        news = set().union(*(where.get(m, set()) for m in r['members']))
        if any(x.startswith('u') for x in news):
            c['old tables over unmatched queries'] += 1
            continue
        if len(news) > 1:
            c['old tables split'] += 1
            tys = set().union(*(ntypes.get(x, set()) for x in news))
            if len(tys) > 1:
                c['old tables split, column types differ'] += 1
                ex['split types'].append((t, r['table'], sorted(map(str, tys))))
            elif len(ex['split']) < 6: ex['split'].append((t, r['table'], r['members'], sorted(news)))
        for x in news: olds[x].add(r['table'])
        if len(r['members']) > 1 and len(news) == 1: c['old merges kept'] += 1
    for x, os_ in olds.items():
        if len(os_) > 1:
            c['new tables joining old tables'] += 1
            if len(ex['join']) < 6: ex['join'].append((t, x, sorted(os_)))
    if o.get('goal_depth') != n.get('goal_depth'): c['goal_depth changed'] += 1
    if (o.get('path') or {}).get('bits') != (n.get('path') or {}).get('bits'): c['path bits changed'] += 1
for k, v in c.items(): print(k, v)
for k, v in ex.items():
    for e in v: print(k, e)
