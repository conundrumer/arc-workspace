#!/usr/bin/env python
"""Writes the frozen priors of live.py: every corpus task's gold program counted (less the tasks whose first row in the corpus has `approximated: true`, unless GOLD_APPROXIMATED=1), with no task held out, into
DATA/sampler/models/live_priors.pkl. The file holds what S reads from disk at a point (the atom priors, the stop hazards,
the compound counts of RULE bodies and of an INIT's key and port bodies, the registry's columns and types), and the program-level counts that a draw from an empty prefix
needs: the next clause's kind or the stop, by how many clauses of each kind exist, a RULE's or a DET's proposer and marks, and an INIT's
component, ports and head sites. A clause comes after what it reads and written order counts for nothing: each program is walked in WALK_ORDERS
random orders that keep its reads, and a count that depends on the order of a body's atoms is its mean over S.BodyOrders.

A sparse kind borrows signal from anywhere, at any point. Its prior takes counts from the kind itself, from the parent kind it is a sibling of (DET for RIGID_DET), from the docs' statement of what the kind does, and from the solvers that a survey names. Its trigger takes engine verdicts (SeveralValues, NotConsistent up to a pose, rows several where not determined) and table content. The same signals apply whether the kind is drawn, lifted as a repair, or rewritten into gold. Thin counts are a reason to borrow signal, not a reason to leave a kind flat or out.

  <runtime python> live_priors.py [--out PATH]
"""
import argparse
import collections
import itertools
import json
import os
import pickle
import random
import tempfile

import sample2_col as S
import sampler_paths as P

KIND_STEP = 2  # the clause count is bucketed by this step in the next-kind counts
KIND_TOP = 12  # the last bucket
WALK_KINDS = 'DEMONSTRATED', 'DET', 'INIT', 'RIGID_DET', 'RULE'  # the kinds of query that a draw or the writer makes
WALK_TOP = 8  # a kind's clause count is capped at this in a walk state
WALK_ORDERS = 8  # random orders counted per program
BORROW = 1.0  # a sparse kind's weight on its parent kind's atoms, against its own: RIGID_DET's parts from DET's bodies
READER_PROGRAM = '(RULE &r (input (:P *P) (:Col *Col)))\n(OUT (&r ^P ^Col))'  # a program, for the engine's export of the registry


def kind_bucket(n):
    return min(n // KIND_STEP, KIND_TOP)


def plain(prior):
    return {f: collections.Counter(c) for f, c in prior.total.items()}


def init_ports(form):
    """(whether the INIT has a key group, {port name}) of an INIT form; the ports of a key group are its elements after the key's body."""
    parts = [p for p in form[3:] if isinstance(p, list) and p]
    keyed = bool(parts) and parts[0][0] == 'key'
    return keyed, {p[0] for p in (parts[0][2:] if keyed else parts) if isinstance(p, list) and p}


def outside_ports(form):
    """The ports of an INIT form that follow its key group: a port that reads no key. Each is (name, head), as port_heads gives."""
    parts = [p for p in form[3:] if isinstance(p, list) and p]
    if not parts or parts[0][0] != 'key':
        return []
    return [(p[0], {h[0][1:]: len(h) - 1 for h in p[1] if isinstance(h, list)}) for p in parts[1:]]


def head_key_counts(tasks):
    """Counts over the ports in an INIT's key group: ('cols', component, port, column) -> head columns, ('key', component, port, column) -> head
    columns that name a key label, 'ports' -> ports with such a column, 'unread' -> those whose body reads no key label."""
    out = collections.Counter()
    for t in tasks:
        for f in S.corpus_forms(t):
            parts = [g for g in f[3:] if isinstance(g, list) and g] if f[0] == 'INIT' else []
            if not parts or parts[0][0] != 'key':
                continue
            keys = carets(parts[0][1], set())
            for p in parts[0][2:]:
                if not (isinstance(p, list) and p):
                    continue
                named = False
                for h in p[1]:
                    if isinstance(h, list):
                        labs = [z for z in h[1:] if isinstance(z, str)] + [y[1] for z in h[1:] if isinstance(z, list) for y in [z] if len(y) > 1]
                        out['cols', f[2], p[0], h[0][1:]] += 1
                        if keys & set(labs):
                            out['key', f[2], p[0], h[0][1:]] += 1
                            named = True
                if named:
                    out['ports'] += 1
                    out['unread'] += not keys & set(text_labels(p[2:], set()))
    return out


def text_labels(x, out):
    """The labels that the atoms x read or make, with no * or ^, added to the set out."""
    if isinstance(x, str):
        out.add(x.lstrip('*^'))
    else:
        for y in x:
            text_labels(y, out)
    return out


def walk_counts(tasks):
    """The counts of a draw's walk: 'after' maps a state, the capped clause counts of WALK_KINDS, to the next kind or 'stop' -> counts."""
    rng, after = random.Random(0), collections.defaultdict(collections.Counter)
    for t in tasks:
        forms = [f for f in S.corpus_forms(t) if f[0] in WALK_KINDS]
        heads, body, _, _ = S.strata._depths(forms)
        for j, f in enumerate(forms):  # _depths leaves out a kind it has no point group for
            if j not in body:
                heads[f[1]], body[j] = j, S.strata.reads_of(f[2:], set()) - {f[1]}
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


def rigid_counts(tasks):
    """{'forms', 'keyed', 'instance'} -> RIGID_DET forms, those with a key group, and those with an instance clause (inside the key group or not)."""
    out = collections.Counter()
    for t in tasks:
        for f in S.corpus_forms(t):
            if f[0] != 'RIGID_DET':
                continue
            parts = [g for g in f[2:] if isinstance(g, list) and g]
            keyed = bool(parts) and parts[0][0] == 'key'
            inner = parts[0][2:] if keyed else parts
            out['forms'] += 1
            out['keyed'] += keyed
            out['instance'] += any(isinstance(g, list) and g[:1] == ['instance'] for g in inner)
    return out


def rigid_parts(tasks):
    """{task: [body]} of the parts of the RIGID_DET forms: the atoms after the key group and the instance clause."""
    out = collections.defaultdict(list)
    for t in tasks:
        for f in S.corpus_forms(t) or []:
            if f[0] == 'RIGID_DET':
                parts = [g for g in f[2:] if isinstance(g, list) and g]
                while parts and parts[0][0] in ('key', 'instance'):
                    parts = [g for g in parts[0][1:] if isinstance(g, list) and g and isinstance(g[0], str)]
                out[t].append(parts)
    return out


def borrowed(own, parent):
    """(atom counts, stop hazard) of a kind whose bodies are own, {task: [body]}, with the bodies of its parent kind in the weight BORROW of its own: each
    count is the kind's own plus the parent's scaled to BORROW times the kind's atoms."""
    mine, theirs = S.Prior(own), S.Prior(parent)
    scale = BORROW * sum(mine.total['rel'].values()) / max(sum(theirs.total['rel'].values()), 1)
    atoms = {f: collections.Counter({k: mine.total[f].get(k, 0) + scale * theirs.total[f].get(k, 0) for k in {*mine.total[f], *theirs.total[f]}}) for f in S.Prior.FIELDS}
    lens, plens = (collections.Counter(len(b) for bs in x.values() for b in bs) for x in (own, parent))
    lens = {n: lens[n] + scale * plens[n] for n in {*lens, *plens}}
    return atoms, {k: (lens.get(k, 0) + 0.5) / (sum(v for n, v in lens.items() if n >= k) + 1.0) if any(n >= k for n in lens) else 1.0 for k in range(1, S.MAX_ATOMS + 1)}


def port_heads(form):
    """[(port name, {column: the count of labels its head site takes})] of an INIT form's ports, in or out of a key group. A record's fields
    count as labels."""
    ports = [q for g in form[3:] if isinstance(g, list) and g for q in (g[2:] if g[0] == 'key' else [g]) if isinstance(q, list) and q]
    return [(p[0], {h[0][1:]: len(h) - 1 for h in p[1] if isinstance(h, list)}) for p in ports]


def empty_ports(tasks):
    """{(component, port): ports with no atoms and no head columns} over the INITs of the tasks that have no key group."""
    out = collections.Counter()
    for t in tasks:
        for f in S.corpus_forms(t):
            if f[0] != 'INIT':
                continue
            parts = [g for g in f[3:] if isinstance(g, list) and g]
            if parts and parts[0][0] == 'key':
                continue
            out.update((f[2], p[0]) for p in parts if not p[1] and not any(isinstance(a, list) for a in p[2:]))
    return out


def empty_keyed(tasks):
    """(ports, heads) over the INITs of the tasks that have a key group, for the ports inside it that have no atoms: ports is {(component, port): those ports}, and heads is {(component, port, column): those
    whose head names the column}. With no atoms a head names a key label alone."""
    ports, heads = collections.Counter(), collections.Counter()
    for t in tasks:
        for f in S.corpus_forms(t):
            if f[0] != 'INIT':
                continue
            parts = [g for g in f[3:] if isinstance(g, list) and g]
            if not parts or parts[0][0] != 'key':
                continue
            for p in parts[0][2:]:
                if isinstance(p, list) and p and not any(isinstance(a, list) for a in p[2:]):
                    ports[f[2], p[0]] += 1
                    heads.update((f[2], p[0], h[0][1:]) for h in p[1] if isinstance(h, list))
    return ports, heads


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


def carets(x, out):
    """The labels of x, a list of atoms, that a ^ marks, added to the set out."""
    if isinstance(x, str):
        if len(x) > 1 and x[0] == '^':
            out.add(x[1:])
    else:
        for y in x:
            carets(y, out)
    return out


def key_labels(tasks):
    """{count of ^ labels: keys} over the key bodies of the tasks' INITs."""
    out = collections.Counter()
    for t in tasks:
        for f in S.corpus_forms(t):
            for g in f[3:] if f[0] == 'INIT' else ():
                if isinstance(g, list) and g[:1] == ['key']:
                    out[len(carets(g[1], set()))] += 1
    return out


def body_compounds(tasks):
    """{'key', 'port' or 'DET': counts in the form of S.compound_counts, over the bodies of that place. A place has no output clause, so the
    flag of 'reach' and 'comp' is False."""
    out = dict(key=collections.Counter(), port=collections.Counter(), DET=collections.Counter())
    for t in tasks:
        for f in S.corpus_forms(t):
            for place, body in init_bodies(f) if f[0] == 'INIT' else [('DET', [a for a in f[2:] if isinstance(a, list) and a[0] not in ('ONE', 'SET')])] if f[0] == 'DET' else ():
                S.count_compound(out[place], body, False)
    return out


def nested_counts(tasks):
    """{place: counts} of the ORs that stand inside a branch of an OR, in the bodies of RULEs and of an INIT's key and ports, each the mean
    over S.BodyOrders of the branch: 'branches' is the branches of ORs, 'nests' the ORs inside a branch past its first atom, 'first' those that
    are a branch's first atom, 'after' the nests with an atom after them in their branch, ('parts', n) the nests of n branches."""
    out = {k: collections.Counter(first=0) for k in ('RULE', 'key', 'port')}
    for t in tasks:
        for f in S.corpus_forms(t):
            bodies = [('RULE', [a for a in f[2:] if isinstance(a, list)])] if f[0] == 'RULE' else init_bodies(f) if f[0] == 'INIT' else []
            for place, body in bodies:
                for a in body:
                    for b in [b for b in a[1:] if isinstance(b, list)] if a and a[0] == 'OR' else ():
                        out[place]['branches'] += 1
                        law = S.BodyOrders(b)
                        for (done, i), w in law.steps.items():
                            x = law.atoms[i]
                            if not x or x[0] != 'OR':
                                continue
                            if not done:
                                out[place]['first'] += w
                                continue
                            out[place]['nests'] += w
                            out[place]['after'] += w * (len(done) + 1 < len(law.atoms))
                            out[place]['parts', len([y for y in x[1:] if isinstance(y, list)])] += w
    return out


def all_counts(tasks):
    """Counts of the ALLs in the bodies of RULEs, DETs and an INIT's key and ports, and in their ORs' branches. ('atoms', place) is the atoms
    of the place (a compound is one), ('alls', place) its ALLs, ('more', place) the ALLs with an atom after them in their body, as the mean over
    S.BodyOrders of the body, and ('guard', n) the ALLs of n guard atoms. place is 'body' for a RULE or a DET, 'key', 'port', or 'branch' for an atom
    inside a branch of an OR."""
    out = collections.Counter()

    def count(atoms, place):
        law = S.BodyOrders(atoms)
        for (done, i), w in law.steps.items():
            if law.atoms[i] and law.atoms[i][0] == 'ALL':
                out['more', place] += w * (len(done) + 1 < len(law.atoms))
        for a in law.atoms:
            if not a:
                continue
            out['atoms', place] += 1
            if a[0] == 'ALL':
                guard = a[1] if len(a) > 1 and isinstance(a[1], list) else []
                out['alls', place] += 1
                out['guard', len(guard)] += 1
            elif a[0] == 'OR':
                for b in a[1:]:
                    if isinstance(b, list):
                        count(b, 'branch')

    for t in tasks:
        for f in S.corpus_forms(t):
            if f[0] in ('RULE', 'DET'):
                count([a for a in f[2:] if isinstance(a, list)], 'body')
            elif f[0] == 'INIT':
                for place, body in init_bodies(f):
                    count(body, place)
    return out


def single_rates(tasks):
    """{kind: P(the body stops at one atom | its first atom is no compound and no method call)} over the RULE and DET bodies of the tasks, as the
    mean over S.BodyOrders of the body. The kind's hazard at one atom counts the compound bodies too, which a draw makes by the compound counts."""
    one, total = collections.Counter(), collections.Counter()
    for t in tasks:
        for f in S.corpus_forms(t):
            if f[0] not in ('RULE', 'DET'):
                continue
            law = S.BodyOrders([a for a in f[2:] if isinstance(a, list) and a[0] not in ('ONE', 'SET')])
            for (done, i), w in law.steps.items():
                if not done and law.atoms[i][0] not in ('OR', 'IF', 'ALL') and '.' not in str(law.atoms[i][0]):
                    total[f[0]] += w
                    one[f[0]] += w * (len(law.atoms) == 1)
    return {k: (one[k] + 0.5) / (total[k] + 1.0) for k in total}


def hand_counts(tasks):
    """What live.set_hand reads: the chances that the walk's first-branch and joined rules take, each a mean over the orders of an OR's branches and over
    S.BodyOrders of a list. 'else_neg', 'mirror_not' and 'p_reexport' read RULE bodies, and 'unjoined' reads RULE, DET, key and port bodies."""
    c = collections.Counter()

    def negated(a):
        return a[1] if a and a[0] == 'NOT' and isinstance(a[1], list) else None

    def count_or(a):
        parts = [[x for x in p if isinstance(x, list)] for p in a[1:] if isinstance(p, list)]
        binds = [S.atoms_bound(p, set(), set()) for p in parts]
        exported = set.intersection(*binds)
        orders = list(itertools.permutations(range(len(parts))))
        for o in orders:
            w = 1 / len(orders)
            held = collections.Counter(x for b in parts[o[0]] for x in S.atom_labels(b))
            again = {x for x, n in held.items() if n >= 2}
            c['again'] += w * len(again)
            c['again exported'] += w * len(again & exported)
            first = {b[0] for b in parts[o[0]] if b and b[0] != 'NOT'}
            for r in range(1, len(o)):
                law = S.BodyOrders(parts[o[r]], set().union(*[binds[q] for q in range(len(parts)) if q != o[r]]))
                earlier = {b[0] for q in o[:r] for b in parts[q] if b and b[0] != 'NOT'}
                c['later'] += w
                c['opens'] += w * sum(v for (done, i), v in law.steps.items() if not done and negated(law.atoms[i]) and negated(law.atoms[i])[0] in first)
                for b in parts[o[r]]:
                    n = negated(b)
                    if n and str(n[0]).startswith('&'):
                        c['mirror'] += w
                        c['mirror held'] += w * (n[0] in earlier)

    for t in tasks:
        for f in S.corpus_forms(t):
            if f[0] == 'RULE':
                places = [[a for a in f[2:] if isinstance(a, list)]]
            elif f[0] == 'DET':
                places = [[a for a in f[2:] if isinstance(a, list) and a[0] not in ('ONE', 'SET')]]
            else:
                places = [b for _, b in init_bodies(f)] if f[0] == 'INIT' else []
            for body in places:
                law = S.BodyOrders(body)
                for (done, i), w in law.steps.items():
                    a = law.atoms[i]
                    if done and a and a[0] not in ('OR', 'IF', 'ALL', 'NOT') and a[0] not in S.OPS:
                        c['atoms'] += w
                        c['unjoined'] += w * (not S.atom_labels(a) & law.bounds[done])
                for a in body if f[0] == 'RULE' else ():
                    if a and a[0] == 'OR':
                        count_or(a)
    return dict(else_neg=c['opens'] / c['later'], mirror_not=c['mirror held'] / c['mirror'], p_reexport=c['again exported'] / c['again'], unjoined=c['unjoined'] / c['atoms'])


def registry_types(regcols):
    """S.lib_types over the registry's entries, which the engine exports with any program."""
    program = S.arclog.StudyProgram.from_sexp(READER_PROGRAM, S.arclog.DecodeSettings())
    entries = json.loads(S.arclog.study_program_export_json(program))['definitions']['registry']['entries']
    with tempfile.TemporaryDirectory() as folder:
        class Rc:  # lib_types reads only the libraries path of a point
            class state:
                libraries_path = folder + '/libraries.json'
        with open(Rc.state.libraries_path, 'w') as f:
            json.dump(entries, f)
        return S.lib_types(Rc, regcols)


def fit(leave_out=()):
    tasks = sorted(t for t in os.listdir(S.CORPUS) if t not in leave_out and S.corpus_forms(t))
    kinds = collections.defaultdict(collections.Counter)  # (previous kind, bucket) -> next kind -> clauses
    lengths = collections.Counter()  # clauses before OUT -> programs
    kinds1 = collections.defaultdict(collections.Counter)  # previous kind -> next kind -> clauses
    proposers, comps = collections.Counter(), collections.Counter()
    det = collections.Counter()  # 'proposer' or 'atoms' -> clauses; ('ONE' or 'SET', the same) -> clauses
    rule = collections.Counter()  # 'proposer' or 'atoms' -> RULE clauses
    keyed, ports = collections.Counter(), collections.Counter()  # component -> INITs with a key group; (component, key group, port) -> uses
    heads = collections.Counter()  # (component, port, column) -> uses of the port whose head names the column
    head_labels = collections.defaultdict(collections.Counter)  # (component, port, column) -> count of labels at that head site -> uses
    outside, heads_out = collections.Counter(), collections.Counter()  # (component, port) -> uses after a key group; (component, port, column) -> those whose head names the column
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
            elif f[0] == 'RULE':
                how = 'proposer' if any(isinstance(x, str) for x in f[2:]) else 'atoms'
                rule[how] += 1
                proposers.update(x for x in f[2:] if isinstance(x, str))
            elif f[0] == 'INIT':
                k, used = init_ports(f)
                comps[f[2]] += 1
                keyed[f[2]] += k
                ports.update((f[2], k, p) for p in used)
                for p, head in port_heads(f):
                    heads.update((f[2], p, col) for col in head)
                    for col, n in head.items():
                        head_labels[f[2], p, col][n] += 1
                for p, head in outside_ports(f):
                    outside[f[2], p] += 1
                    heads_out.update((f[2], p, col) for col in head)
    bodies = {k: S.gold_bodies(tasks, k) for k in ('RULE', 'DET')}
    bodies['INIT'] = S.gold_port_bodies(tasks)
    rigid_atoms, rigid_hazard = borrowed(rigid_parts(tasks), bodies['DET'])
    regcols = S.registry_columns()
    regtypes = registry_types(regcols)
    compound = collections.Counter()
    for c in S.compound_counts(tasks).values():
        compound.update(c)
    top = max(lengths)
    stop = {n: (lengths[n] + 0.5) / (sum(v for m, v in lengths.items() if m >= n) + 1.0) for n in range(1, top + 1)}  # P(the program stops after n clauses | n clauses)
    empty_keys, empty_heads = empty_keyed(tasks)
    return dict(tasks=len(tasks), stop=stop, kinds=dict(kinds), kinds1=dict(kinds1), walk=walk_counts(tasks), proposers=proposers, comps=comps, det=det, rule=rule, keyed=keyed,
                ports=ports, heads=heads, head_labels=dict(head_labels), outside=outside, heads_out=heads_out, empty_ports=empty_ports(tasks), empty_keyed=empty_keys, empty_heads=empty_heads, rigid=rigid_counts(tasks), compound=compound, compounds=body_compounds(tasks), nested=nested_counts(tasks), all_forms=all_counts(tasks), single=single_rates(tasks), hand=hand_counts(tasks), head_key=head_key_counts(tasks), key_labels=key_labels(tasks), atoms={k: plain(S.Prior(b)) for k, b in bodies.items()} | dict(RIGID_DET=rigid_atoms),
                hazard={k: S.kind_hazard(b) for k, b in bodies.items()} | dict(RIGID_DET=rigid_hazard), regcols=regcols, regtypes=regtypes,
                comp_ports={k: (sorted(v[0]), [(p, [x for x in c.items() if x[0] != 'default']) for p, c in v[1].items()]) for k, v in S.component_ports().items()},
                families=S.FAMILIES)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=P.SAMPLER_DATA + '/models/live_priors.pkl')
    ap.add_argument('--leave-out', help='a file of tasks to fit without, one a line')
    a = ap.parse_args()
    got = fit(set(open(a.leave_out).read().split()) if a.leave_out else ())
    with open(a.out + '.tmp', 'wb') as f:
        pickle.dump(got, f, protocol=5)
    os.replace(a.out + '.tmp', a.out)
    print(a.out, got['tasks'], 'tasks', {k: sum(v['rel'].values()) for k, v in got['atoms'].items()}, 'atoms')


if __name__ == '__main__':
    main()
