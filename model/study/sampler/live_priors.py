#!/usr/bin/env python
"""Writes the frozen priors of live.py: every corpus task's gold program counted, with no task held out, into
DATA/sampler/models/live_priors.pkl. The file holds what S reads from disk at a point (the atom priors, the stop hazards,
the compound counts of RULE bodies and of an INIT's key and port bodies, the registry's columns and types), and the program-level counts that a draw from an empty prefix
needs: the next clause's kind or the stop, by how many clauses of each kind exist, a DET's proposer and marks, and an INIT's
component and ports. A clause comes after what it reads and written order counts for nothing: each program is walked in WALK_ORDERS
random orders that keep its reads.

  <runtime python> live_priors.py [--out PATH]
"""
import argparse
import collections
import os
import pickle
import random

import sample2_col as S
import sampler_paths as P

KIND_STEP = 2  # the clause count is bucketed by this step in the next-kind counts
KIND_TOP = 12  # the last bucket
WALK_KINDS = 'DET', 'INIT', 'RULE'  # the kinds that a draw makes
WALK_TOP = 8  # a kind's clause count is capped at this in a walk state
WALK_ORDERS = 8  # random orders counted per program


def kind_bucket(n):
    return min(n // KIND_STEP, KIND_TOP)


def plain(prior):
    return {f: collections.Counter(c) for f, c in prior.total.items()}


def init_ports(form):
    """(whether the INIT has a key group, {port name}) of an INIT form; the ports of a key group are its elements after the key's body."""
    parts = [p for p in form[3:] if isinstance(p, list) and p]
    keyed = bool(parts) and parts[0][0] == 'key'
    return keyed, {p[0] for p in (parts[0][2:] if keyed else parts) if isinstance(p, list) and p}


def walk_counts(tasks):
    """The counts of a draw's walk: 'after' maps a state, the capped clause counts of WALK_KINDS, to the next kind or 'stop' -> counts."""
    rng, after = random.Random(0), collections.defaultdict(collections.Counter)
    for t in tasks:
        forms = [f for f in S.corpus_forms(t) if f[0] in WALK_KINDS]
        heads, body, _, _ = S.strata._depths(forms)
        needs = {j: {heads[r] for r in rs if r in heads and heads[r] < j} for j, rs in body.items()}
        for _ in range(WALK_ORDERS):
            left, have = dict(needs), collections.Counter()
            while left:
                j = rng.choice([j for j, ns in left.items() if not ns & left.keys()])
                del left[j]
                after[tuple(min(have[k], WALK_TOP) for k in WALK_KINDS)][forms[j][0]] += 1
                have[forms[j][0]] += 1
            after[tuple(min(have[k], WALK_TOP) for k in WALK_KINDS)]['stop'] += 1
    return dict(kinds=WALK_KINDS, top=WALK_TOP, after=dict(after))


def init_bodies(form):
    """[(place, atoms)] of the key and ports of an INIT form: place is 'key' or 'port'."""
    out = []
    for g in form[3:]:
        if isinstance(g, list) and g[:1] == ['key']:
            out.append(('key', [a for a in g[1] if isinstance(a, list)]))
            out += [('port', [a for a in p[2:] if isinstance(a, list)]) for p in g[2:] if isinstance(p, list)]
        elif isinstance(g, list) and g:
            out.append(('port', [a for a in g[2:] if isinstance(a, list)]))
    return out


def body_compounds(tasks):
    """{'key' or 'port': counts in the form of S.compound_counts, with ('after',) as compound has it, over the bodies of that place.
    A place has no output clause, so the flag of 'reach' and 'comp' is False."""
    out = dict(key=collections.Counter(), port=collections.Counter())
    for t in tasks:
        for f in S.corpus_forms(t):
            for place, body in init_bodies(f) if f[0] == 'INIT' else ():
                c, ci = out[place], next((i for i, a in enumerate(body) if a and a[0] in ('OR', 'IF')), None)
                for k in range(1, (len(body) if ci is None else ci + 1) + 1):
                    c['reach', False, k] += 1
                if ci is None:
                    continue
                parts = [b for b in body[ci][1:] if isinstance(b, list)]
                c['comp', False, ci + 1] += 1
                c['shape', body[ci][0] + str(len(parts))] += 1
                c['after', ] += ci < len(body) - 1
                if body[ci][0] == 'OR':
                    pos1 = {x[0] for x in parts[0] if isinstance(x, list) and x and x[0] != 'NOT'}
                    for b in parts[1:]:
                        c['later', ] += 1
                        c['neg1', ] += any(isinstance(x, list) and x and x[0] == 'NOT' and isinstance(x[1], list) and x[1][0] in pos1 for x in b)
                for b in parts:
                    if b:
                        c['blen', len(b)] += 1
    return out


def fit():
    tasks = sorted(t for t in os.listdir(S.CORPUS) if S.corpus_forms(t))
    kinds = collections.defaultdict(collections.Counter)  # (previous kind, bucket) -> next kind -> clauses
    lengths = collections.Counter()  # clauses before OUT -> programs
    kinds1 = collections.defaultdict(collections.Counter)  # previous kind -> next kind -> clauses
    proposers, comps = collections.Counter(), collections.Counter()
    det = collections.Counter()  # 'proposer' or 'atoms' -> clauses; ('ONE' or 'SET', the same) -> clauses
    keyed, ports = collections.Counter(), collections.Counter()  # component -> INITs with a key group; (component, key group, port) -> uses
    heads = collections.Counter()  # (component, port, column) -> uses of the port whose head names the column
    for t in tasks:
        prev, n = '^', 0
        lengths[sum(f[0] != 'OUT' for f in S.corpus_forms(t))] += 1
        for f in S.corpus_forms(t):
            if f[0] == 'OUT':
                continue
            kinds[prev, kind_bucket(n)][f[0]] += 1
            kinds1[prev][f[0]] += 1
            prev, n = f[0], n + 1
            if f[0] == 'DET':
                how = 'proposer' if any(isinstance(x, str) for x in f[2:]) else 'atoms'
                det[how] += 1
                proposers.update(x for x in f[2:] if isinstance(x, str))
                for x in f[2:]:
                    if x in (['ONE'], ['SET']):
                        det[x[0], how] += 1
            elif f[0] == 'INIT':
                k, used = init_ports(f)
                comps[f[2]] += 1
                keyed[f[2]] += k
                ports.update((f[2], k, p) for p in used)
                for p, head, _ in S.port_parts(f) + [q for g in f[3:] if isinstance(g, list) and g[:1] == ['key'] for q in S.port_parts(['', '', ''] + g[2:])]:
                    heads.update((f[2], p, col) for col, _ in head)
    bodies = {k: S.gold_bodies(tasks, k) for k in ('RULE', 'DET')}
    bodies['INIT'] = S.gold_port_bodies(tasks)
    regcols = S.registry_columns()
    with os.scandir(S.FSTORE) as points:
        lib = next(points).path + '/libraries.json'  # one file, the same at every point

    class Rc:  # lib_types reads only the libraries path of a point
        class state:
            libraries_path = lib
    compound = collections.Counter()
    for c in S.compound_counts(tasks).values():
        compound.update(c)
    for t in tasks:  # S's counts leave out the atoms after a compound: ('after',) has the RULE compounds with an atom after them
        for f in S.corpus_forms(t):
            body = [a for a in f[2:] if isinstance(a, list)] if f[0] == 'RULE' else []
            compound['after', ] += next((i < len(body) - 1 for i, a in enumerate(body) if a and a[0] in ('OR', 'IF')), False)
    top = max(lengths)
    stop = {n: (lengths[n] + 0.5) / (sum(v for m, v in lengths.items() if m >= n) + 1.0) for n in range(1, top + 1)}  # P(the program stops after n clauses | n clauses)
    return dict(tasks=len(tasks), stop=stop, kinds=dict(kinds), kinds1=dict(kinds1), walk=walk_counts(tasks), proposers=proposers, comps=comps, det=det, keyed=keyed,
                ports=ports, heads=heads, compound=compound, compounds=body_compounds(tasks), atoms={k: plain(S.Prior(b)) for k, b in bodies.items()},
                hazard={k: S.kind_hazard(b) for k, b in bodies.items()}, regcols=regcols, regtypes=S.lib_types(Rc, regcols),
                comp_ports={k: (sorted(v[0]), [(p, [x for x in c.items() if x[0] != 'default']) for p, c in v[1].items()]) for k, v in S.component_ports().items()},
                families=S.FAMILIES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=P.SAMPLER_DATA + '/models/live_priors.pkl')
    a = ap.parse_args()
    got = fit()
    with open(a.out + '.tmp', 'wb') as f:
        pickle.dump(got, f, protocol=5)
    os.replace(a.out + '.tmp', a.out)
    print(a.out, got['tasks'], 'tasks', {k: sum(v['rel'].values()) for k, v in got['atoms'].items()}, 'atoms')


if __name__ == '__main__':
    main()
