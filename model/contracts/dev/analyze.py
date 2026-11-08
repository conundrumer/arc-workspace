"""Dev labeling layer: its verdicts are not model input.

Verdicts for every table of a task from out/<task>.variants.jsonl, which may be partial.

    python3 analyze.py TASK [TASK ...]

A postcondition is the hull of a feature's values on the task's own examples (pool.hull): one value where all are equal, the range of a number, or
the set of values of a category. Input features count every example; output features (those that read the train output) the train examples.
A table's preconditions are the postconditions of the tables upstream of it: what its form reads, and so on back. A variant counts for a table where
every precondition holds on it. A variant tests a postcondition where it changes the table's features; an output postcondition is tested on output
variants only, since an input variant's example has no output.
A variant that changes a stored relation (its `stored_changed`) tests that relation, and no table downstream of it. An output variant keeps the
task's proposer values, so only a stored relation that reads the train outputs through clauses of its own can change.

An output variant edits only a train output, so a table that reads no train output is as on the task, and only a stored relation can change.
An output variant counts only where its output is one the task could have: the solver's output on an input variant (its `from`) that meets
the preconditions of every table on the way to the output (valid_input). An upstream table's relation to the output is not a condition on
that table being correct, so the output postconditions of upstream tables are not preconditions.
Per postcondition: untested (no counted variant changes the table's features), entailed (no counterexample among the counted variants that change
the table), redundant (it fails, and on every counted variant it holds exactly where some feature of a prior table keeps its value on the source
example; prior: upstream, which for an instance output includes the instance's input ports, or defined earlier in the program, other than
outputs of the same instance), or new.
Per table: informative where a postcondition is new; redundant where postconditions were tested and none is new; untested otherwise.
Live: some form on the way to OUT reads it. Writes <out dir>/<task>.verdicts.json (.verdicts.post.json with --post-pred), and
<out dir>/<task>.uses.jsonl: per variant, the tables it tests and the postconditions it falsifies.
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'features'))
sys.path.insert(0, str(HERE.parent / 'guarantees'))
import lib as G  # noqa: E402
import paths  # noqa: E402
import pool as P  # noqa: E402

OUTDIR = Path(os.environ.get('CONTRACTS_OUT', Path(__file__).parent / 'out'))
import query as Q  # noqa: E402

GEN = paths.GEN
from features import OUTPUT_FEATURES  # noqa: E402
import jsonl as J  # noqa: E402
import tablecache as C  # noqa: E402
READINGS = json.load(open(HERE / 'readings.json'))
POST_PRED = '--post-pred' in sys.argv  # an earlier feature with a postcondition also counts through "its postcondition holds"
PARENTS = '--parents' in sys.argv  # preconditions from the tables the query reads, in place of every table upstream of it


def is_output(k):
    return any(s in k for s in OUTPUT_FEATURES)


def numeric(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def postconditions(base):
    """{feature: the hull of its values on the task's own examples}, a pooled feature at the per-assignment level."""
    exs = base['examples']
    keys = {k for f in exs.values() for k in f}
    post = {}
    for k in keys:
        names = [e for e in exs if e.startswith('train/')] if is_output(k) else list(exs)
        h = P.hull([exs[e].get(k, 'MISSING') for e in names])
        if h is not None:
            post[k] = h
    return post


def holds(p, v):
    return P.in_hull(p, v)


def flags(xs):
    """A vector of flags as bytes, one byte per flag: a compact key that two equal vectors share."""
    return bytes(1 if x else 0 for x in xs)


def interned(r):
    """The record, with its feature names and its text values shared with every other record (sys.intern), so that each name is held once."""
    f = r.get('features')
    if f is not None:
        r['features'] = {sys.intern(k): (sys.intern(x) if isinstance(x, str) else x) for k, x in f.items()}
    return r


def upstream(graph, name):
    seen, todo = set(), [name.split('.')[0]]
    while todo:
        x = todo.pop()
        for y in graph.get(x, ()):
            if y not in seen:
                seen.add(y)
                todo.append(y)
    return seen


def live_tables(base, qf=None):
    """{table: live}: some form on the way to OUT reads it. An input port of an instance is live where its instance is."""
    rp = {k: set(v) for k, v in base['reads_ports'].items()}
    outs = {r for r, _ in base['out']}
    live = {r.split('.')[0] for r in outs}
    changed = True
    while changed:
        changed = False
        for f in list(rp):
            if f in live:
                continue
            if any(f in rp[l] or any(x.split('.')[0] == f for x in rp[l]) for l in live if l in rp):
                live.add(f)
                changed = True
    read = set(outs)
    for l in live:
        read |= rp.get(l, set())
    inputs = lambda t: t.partition('.')[2] in (qf or {}).get(t.split('.')[0], {}).get('inputs written', [])
    return {t: (t.split('.')[0] in live if inputs(t) else t in read if '.' in t else t.split('.')[0] in live) for t in base['tables']}


def input_features(gi, go):
    """The library's features of the input grid as a table of (P, Col), with the frame of the input."""
    import features as F
    H, W = len(gi), len(gi[0])
    rows = [[[r, H - 1 - r, c, W - 1 - c], gi[r][c]] for r in range(H) for c in range(W)]
    tab = {'columns': [('P', 'Position', 'input'), ('Col', 'Color', '')], 'rows': {'x': rows}}
    sizes = {'input': (H, W)}
    if go is not None:
        sizes['output'] = (len(go), len(go[0]))
    return {sys.intern('input|' + k): (sys.intern(v) if isinstance(v, str) else v) for k, v in F.table_features('input', tab, 'x', sizes, {}, (gi, go)).items()}


def add_input(task, base, V):
    tj = json.load(open(paths.TASKS / ('%s.json' % task)))
    grid = lambda ex: tj[ex.split('/')[0]][int(ex.split('/')[1])]
    for ex, f in base['examples'].items():
        p = grid(ex)
        f.update(input_features(p['input'], p.get('output') if ex.startswith('train') else None))
    for v in V:
        p = grid(v['source'])
        if v['kind'] == 'in':
            v['features'].update(input_features(v['grid'], None))
        else:
            v['features'].update(input_features(p['input'], C.edited_output(p['output'], v)))


def valid_input(post, live):
    """A test of whether an input variant's solver output is an output the task could have: the variant's stored values are the task's, and
    every postcondition of every table on the way to the output, other than an output postcondition, holds on it."""
    keys = [k for k in post if live.get(k.split('|')[0]) and not is_output(k)]
    return lambda v: (v['kind'] == 'in' and 'features' in v and v.get('stored', 'same') == 'same'
                      and all(holds(post[k], v['features'].get(k, 'MISSING')) for k in keys))


def analyze(task, with_input=True):
    lines = [interned(r) for r in J.records(OUTDIR / (task + '.variants.jsonl'))]
    base = next(l for l in lines if l['kind'] == 'base')
    V = [l for l in lines if l['kind'] != 'base' and 'features' in l]
    statuses = Counter(l.get('stored', 'same') for l in V)
    if with_input:
        add_input(task, base, V)
    errors = sum('error' in l for l in lines)
    post = postconditions(base)
    graph = {k: set(v) for k, v in base['graph'].items()}
    qf = Q.query_features(paths.read_gen(GEN / (task + '.arclog')))
    live = live_tables(base, qf)
    valid_in = valid_input(post, live)
    valid = {v['id'] for v in V if valid_in(v)}
    order = list(base['reads_ports'])
    res = {}
    uses = {v['id']: dict(counted=[], falsifies=[]) for v in V}  # per variant: the tables it tests, and the postconditions it falsifies
    for t in base['tables']:
        if t in ('ex_input', 'ex_output', 'input'):
            continue
        ups = upstream(graph, t)
        me = t.split('.')[0]
        port_in = set(qf.get(me, {}).get('inputs written', []))  # the instance's input ports are upstream of its outputs
        own_inputs = {x for x in base['tables'] if x.split('.')[0] == me and x.partition('.')[2] in port_in and x != t} if t.partition('.')[2] not in port_in else set()
        prior = ups | set(order[:order.index(me)] if me in order else []) | ({'input'} if with_input else set())
        own = sorted(k for k in post if k.split('|')[0] == t)
        pre_from = set(graph.get(me, ())) if PARENTS else ups
        pre = [k for k in post if (k.split('|')[0].split('.')[0] in pre_from or k.split('|')[0] in own_inputs) and not is_output(k)]
        sound = lambda v: not {x.split('.')[0] for x in v.get('stored_invalid', v.get('stored_changed', []))} & (ups - {me})  # no stored relation upstream of t changed
        held = [v for v in V if sound(v) and (v['kind'] != 'out' or v.get('from') in valid) and all(holds(post[p], v['features'].get(p, 'MISSING')) for p in pre)]
        for v in held:
            uses[v['id']]['counted'].append(t)
        verdicts = {}
        q, port = Q.of_table(qf, t), t.partition('.')[2]
        changed_of, index_of = {}, {}
        for k in own:
            if port and post[k][0] == 'value' and G.by_construction(q, port, k.split('|', 1)[1], post[k][1]):
                verdicts[k] = dict(verdict='by construction')
                continue
            kind = 'out' if is_output(k) else 'any'  # an output postcondition is tested on output variants only, since an input variant's example has no output
            if kind not in changed_of:
                changed_of[kind] = [v for v in held if (kind == 'any' or v['kind'] == 'out') and any(v['features'].get(g, 'MISSING') != base['examples'][v['source']].get(g, 'MISSING')
                                                                 for g in v['features'] if g.split('|')[0] == t)]
                cands = {g for v in changed_of[kind] for g in v['features'] if (g.split('|')[0].split('.')[0] in prior and g.split('|')[0].split('.')[0] != me) or g.split('|')[0] in own_inputs}
                index = {}
                for g in sorted(cands):
                    vec = flags(v['features'].get(g, 'MISSING') == base['examples'][v['source']].get(g, 'MISSING') for v in changed_of[kind])
                    index.setdefault(vec, []).append(g)
                    if POST_PRED and g in post:
                        vec = flags(holds(post[g], v['features'].get(g, 'MISSING')) for v in changed_of[kind])
                        index.setdefault(vec, []).append(g + ' (its postcondition)')
                index_of[kind] = index
            vs = changed_of[kind]
            ok = [holds(post[k], v['features'].get(k, 'MISSING')) for v in vs]
            if not vs:
                verdicts[k] = dict(verdict='untested', counted=len(held), changed=0, failed=0)
                continue
            if all(ok):
                verdicts[k] = dict(verdict='entailed', counted=len(held), changed=len(vs), failed=0)
                continue
            for v, o in zip(vs, ok):
                if not o:
                    uses[v['id']]['falsifies'].append(k)
            same = index_of[kind].get(flags(ok), [])
            verdicts[k] = dict(verdict='redundant' if same else 'new', counted=len(held), changed=len(vs), failed=ok.count(False), same_as=same[:3],
                               example=next(v['id'] for v, o in zip(vs, ok) if not o))
        counts = {x: sum(d['verdict'] == x for d in verdicts.values()) for x in ('new', 'redundant', 'entailed', 'by construction', 'untested')}
        verdict = 'informative' if counts['new'] else 'redundant' if counts['redundant'] or counts['entailed'] or counts['by construction'] else 'untested'
        res[t] = dict(verdict=verdict, live=live.get(t), reading=READINGS.get(task, {}).get(t), counts=counts, postconditions=verdicts)
    json.dump(res, open(OUTDIR / (task + ('.verdicts.post.json' if POST_PRED else '.verdicts.json')), 'w'), indent=1)
    J.write_all(OUTDIR / (task + '.uses.jsonl'), (dict(id=vid, **u) for vid, u in uses.items()))
    nin = sum(v['kind'] == 'in' for v in V)
    nout = sum(v['kind'] == 'out' for v in V)
    nout_ok = sum(v['kind'] == 'out' and v.get('from') in valid for v in V)
    print('== %s: %d input variants, %d output variants (%d from an input variant that meets the preconditions; stored values: %d same, %d changed, %d unsolved), %d errors'
          % (task, nin, nout, nout_ok, statuses['same'], statuses['changed'], statuses['unsolved'], errors))
    print('%-28s %-8s %-12s %-5s %s' % ('table', 'reading', 'verdict', 'live', 'postconditions: new / redundant / entailed / by construction / untested'))
    for t, r in res.items():
        c = r['counts']
        flag = '' if (r['reading'] == 'claim') == (r['verdict'] == 'informative') or r['reading'] is None else '  <- differs'
        print('%-28s %-8s %-12s %-5s %3d / %3d / %3d / %3d / %3d%s' % (t, r['reading'], r['verdict'], 'yes' if r['live'] else 'no', c['new'], c['redundant'], c['entailed'], c['by construction'], c['untested'], flag))
    return res


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    for t in args:
        analyze(t, with_input='--no-input' not in sys.argv)
