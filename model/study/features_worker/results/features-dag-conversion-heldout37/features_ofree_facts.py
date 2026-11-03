"""The fact layer of this lane's reads: it can't emit a fact that reads written order.

The ban covers lexical order: the last atom, an atom's index, its position in a body, and a form's place in gold's text. Facts of the read graph are allowed: depth, the size of a body or prefix as a set, which atoms share labels, and join structure.

A read imports `row_facts` and `option_facts`, or passes its own names through `check`. `check` raises BannedFact on a name outside the allow list. A row's `written` field isn't read here. `invariant` proves the layer on text: it permutes each body's atoms and each branch's atoms, renames labels and drops the marks `*` and `^`, and requires the same facts for each left-out atom.

Row facts are NAME = FAMILY:VALUE. Option facts are NAME = opt_WHAT.
"""
import collections
import random
import re

import features_ofree_text as T

# A row's facts, by family. Each family is a fact of the set, of the slot or of the read graph.
ROW_FAMILIES = {
    'place': 'the kind of body: RULE, DET, key or port',
    'comp': "the component of the form's INIT",
    'port': "the component's port this body fills",
    'under': 'the left-out atom sits under NOT, OR, ALL or IF',
    'scf': 'a form family in the scope',
    'sc': 'a component, proposer or component port in the scope',
    'scr': 'a head read by a form of the scope',
    'in': 'a relation of another atom of the conjunction',
    'neg': 'a relation under NOT among the other atoms',
    'near': 'a relation in the same body outside the conjunction',
    'size': 'the count of other atoms kept, as a threshold',
    'inb': 'a head of the body of a form that a kept atom reads',
    'col': 'a column named by a kept atom',
    'join': 'two kept atoms share a label',
    'open': 'a column whose label no other kept atom holds',
    'parts': 'the kept atoms make two or more components by shared labels',
}
OPT_NAMES = {
    'opt_depth1': "the option's form is at depth 1 or more of the read graph", 'opt_depth2': 'the same at 2', 'opt_depth3': 'the same at 3', 'opt_depth5': 'the same at 5',
    'opt_nbody2': "the option's form has 2 or more atoms", 'opt_nbody4': 'the same at 4',
    'opt_inctx': 'a kept atom reads the same relation', 'opt_anc': "the option's form is an ancestor of a form that a kept atom reads", 'opt_desc': "the option's form reads a form that a kept atom reads",
    'opt_readers1': 'a form of the scope reads the option', 'opt_readers2': 'the same for 2 forms', 'opt_readers4': 'the same for 4 forms', 'opt_unread': 'no form of the scope and no kept atom reads the option',
}
# Tiers: scope has no atom of the body. set adds the other atoms as a set and their count. dag adds join structure. open adds what a body with one atom missing shows: labels left open, and forms left unread.
TIER_FAMILIES = {
    'scope': {'place', 'comp', 'port', 'under', 'scf', 'sc', 'scr'},
    'set': {'place', 'comp', 'port', 'under', 'scf', 'sc', 'scr', 'in', 'neg', 'near', 'size'},
    'dag': {'place', 'comp', 'port', 'under', 'scf', 'sc', 'scr', 'in', 'neg', 'near', 'size', 'inb', 'col', 'join'},
    'open': {'place', 'comp', 'port', 'under', 'scf', 'sc', 'scr', 'in', 'neg', 'near', 'size', 'inb', 'col', 'join', 'open', 'parts'},
}
TIER_OPTS = {
    'scope': set(),
    'set': {'opt_inctx'},
    'dag': {'opt_inctx', 'opt_depth1', 'opt_depth2', 'opt_depth3', 'opt_depth5', 'opt_nbody2', 'opt_nbody4', 'opt_anc', 'opt_desc'},
    'open': {'opt_inctx', 'opt_depth1', 'opt_depth2', 'opt_depth3', 'opt_depth5', 'opt_nbody2', 'opt_nbody4', 'opt_anc', 'opt_desc', 'opt_readers1', 'opt_readers2', 'opt_readers4', 'opt_unread'},
}
SIZES = (1, 2, 3, 4, 6, 8)


class BannedFact(Exception):
    pass


def check(names):
    """Raises BannedFact on a name outside the allow list. Returns the names."""
    for n in names:
        fam, sep, _ = n.partition(':')
        if n in OPT_NAMES:
            continue
        if not sep or fam not in ROW_FAMILIES:
            raise BannedFact(n)
    return names


def row_facts(r, rec, tier, keep=None):
    """The fact names of row r of form record rec. keep lists the context atoms kept, where a read drops some: default all."""
    fams = TIER_FAMILIES[tier]
    ctx = r['ctx'] if keep is None else [r['ctx'][i] for i in keep]
    out = {'place:' + r['place']}
    if r['comp']:
        out |= {'comp:' + r['comp'], 'port:' + r['port']}
    out |= {'under:' + u for u in r['under']}
    for o in rec['opts']:
        out |= {'scf:' + o['fam'], 'sc:' + o['tok']}
        if o['comp']:
            out.add('sc:' + o['comp'])
    out |= {'scr:' + h for h in rec['scope_heads']}
    if 'in' in fams:
        for c in ctx:
            if c['t']:
                out.add(c['w'] + ':' + c['t'])
        n = len(ctx)
        out |= {'size:%d' % s for s in SIZES if n >= s}
    if 'inb' in fams:
        for c in ctx:
            out |= {'inb:' + h for h in c['inb']}
            if c['t']:
                out |= {'col:%s.%s' % (c['t'], x) for x in c['cols']}
        who = collections.defaultdict(set)
        for i, c in enumerate(ctx):
            for x in c['ls']:
                who[x].add(i)
        for s in who.values():
            ts = sorted(ctx[i]['t'] or '' for i in s)
            for a in range(len(ts)):
                for b in range(a + 1, len(ts)):
                    out.add('join:%s~%s' % (ts[a], ts[b]))
    if 'open' in fams:
        cnt = collections.Counter(x for c in ctx for x in set(c['ls']))
        for c in ctx:
            if c['t']:
                out |= {'open:%s.%s' % (c['t'], col) for x, col in zip(c['ls'], c['cols']) if cnt[x] == 1}
        p = list(range(len(ctx)))

        def find(x):
            while p[x] != x:
                p[x] = p[p[x]]
                x = p[x]
            return x
        first = {}
        for i, c in enumerate(ctx):
            for x in c['ls']:
                if x in first:
                    p[find(i)] = find(first[x])
                else:
                    first[x] = i
        if len({find(i) for i in range(len(ctx))}) >= 2:
            out.add('parts:2')
    return check(out)


def option_facts(o, r, rec, tier, keep=None):
    """The fact names of derived option o at row r."""
    want = TIER_OPTS[tier]
    if not want:
        return []
    ctx = r['ctx'] if keep is None else [r['ctx'][i] for i in keep]
    out = []
    fs = [c['f'] for c in ctx if c['f']]
    d, nb, rd = o['depth'], o['nbody'], o['readers']
    inctx = o['f'] in fs
    for n, v in (('opt_depth1', d >= 1), ('opt_depth2', d >= 2), ('opt_depth3', d >= 3), ('opt_depth5', d >= 5), ('opt_nbody2', nb >= 2), ('opt_nbody4', nb >= 4), ('opt_inctx', inctx), ('opt_readers1', rd >= 1), ('opt_readers2', rd >= 2), ('opt_readers4', rd >= 4), ('opt_unread', rd == 0 and not inctx)):
        if v and n in want:
            out.append(n)
    if 'opt_anc' in want and any(o['f'] in rec['anc'].get(f, ()) for f in fs):
        out.append('opt_anc')
    if 'opt_desc' in want and any(f in o['anc'] for f in fs):
        out.append('opt_desc')
    return check(out)


def scramble(line, rng):
    """A form with its body's atoms in a random order, recursively, and an INIT's ports too. Its meaning as a set of atoms stays."""
    p = T.sexp(line)[0]

    def conj(c):
        c = [atom(x) for x in c]
        rng.shuffle(c)
        return c

    def atom(a):
        if a and a[0] in T.COMPOUND:
            return [a[0]] + [conj(x) if T.is_conj(x) else x for x in a[1:]]
        return a

    if p[0] in ('RULE', 'DET') and len(p) > 2 and isinstance(p[2], list):
        return p[:2] + conj(p[2:])
    if p[0] == 'INIT':
        rest = []
        for x in p[3:]:
            if x[0] == 'key':
                ports = [q[:2] + conj(q[2:]) for q in x[2:]]
                rng.shuffle(ports)
                rest.append(['key', conj(x[1])] + ports)
            else:
                rest.append(x[:2] + conj(x[2:]))
        rng.shuffle(rest)
        return p[:3] + rest
    return p


def unparse(x):
    return '(' + ' '.join(unparse(y) if isinstance(y, list) else y for y in x) + ')' if isinstance(x, list) else x


def strip_marks(text, caps, names):
    """Drops `*` and `^`, and renames each label, so nothing of a label's written name or first binding is left."""
    def sub(m):
        w = m[1]
        return w if w in caps or T.CONST.match(w) else names.setdefault(w, 'Z%d' % len(names))
    return re.sub(r'(?<=[\s(])([A-Z][A-Za-z_0-9]*)(?=[\s)])', sub, re.sub(r'[*^]', '', text))


def signature(rec, tier):
    """Each row's label and facts, and its options' facts, as a multiset."""
    c = collections.Counter()
    for r in rec['rows']:
        opts = frozenset((o['f'], o['p'], frozenset(option_facts(o, r, rec, tier))) for o in rec['opts'])
        c[(r['key'], r['place'], tuple(r['under']), frozenset(row_facts(r, rec, tier)), opts)] += 1
    return c


def invariant(tasks, lines_of, reg, tiers=('scope', 'set', 'dag', 'open'), seed=0):
    """Fails unless each left-out atom's facts stay the same when its body and ports are shuffled, the forms' lines are shuffled, the marks are dropped and the labels are renamed. Returns the count of rows compared."""
    rng = random.Random(seed)
    txt = open(T.REGISTRY, encoding='utf8').read()
    caps = set(re.findall(r'^\((?:component|proposer) (\w+)', txt, re.M)) | {'RULE', 'DET', 'INIT', 'OUT', 'RIGID_DET', 'CHOOSE', 'NOT', 'OR', 'ALL', 'IF', 'ONE', 'SET'}
    n = 0
    for t in tasks:
        lines = lines_of(t)
        a = {r['name']: r for r in T.records(t, lines, reg)}
        names = {}
        scr = [strip_marks(unparse(scramble(x, rng)), caps, names) for x in lines]
        rng.shuffle(scr)
        b = {r['name']: r for r in T.records(t, scr, reg)}
        if set(a) != set(b):
            raise AssertionError('forms differ on ' + t)
        for k, ra in a.items():
            for tier in tiers:
                sa, sb = signature(ra, tier), signature(b[k], tier)
                if sa != sb:
                    raise AssertionError('facts differ on %s %s tier %s: %s' % (t, k, tier, list((sa - sb).items())[:1]))
            n += len(ra['rows'])
    return n
