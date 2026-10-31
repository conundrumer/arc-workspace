"""Round 3, explorer H: form-only features (the form, the library interfaces and the types of the sites).

An atom makes the labels that it stars (`*V`, `^V`). Where one branch of an OR stars a label that every other branch
names, the text puts the star at one site, and every atom of the OR that names the label makes it. An atom that makes a label is an output atom, and any other atom is a test atom. An output
is live when its label is exported (`^V`) or occurs in another atom of the form, and dead otherwise.

A literal 0 means the zero box where the type of its site is known and is not Number. Where the zero box is the grid
frame (`featlib.FRAME_ZERO_SITES`), the literal is not a degenerate site: `zero_frame` counts the atoms that have one. The type of a site comes from
featlib's typed access: the interface of a library relation, or the fields of the table that the atom reads.
"""
import collections as C

from featlib import feature, frame_zero


def _atoms(p):
    """The atoms of the candidate's body (comparisons left out), in text order."""
    body = p.clause.body
    return [a for a in body.atoms if a.operator is None] if body is not None else []


def _made(body):
    """{(OR path, label)}: the labels that a starred site inside an OR makes and every other branch of that OR names.
    Where a branch makes such a label, the text puts the star at one site, and any other branch's site makes it too."""
    named = C.defaultdict(lambda: C.defaultdict(set))
    for a in body.arguments:
        if a.label is None:
            continue
        for orp, b in a.atom.branch:
            named[orp, a.label][b].add(a.binds)
    out = set()
    for (orp, label), branches in named.items():
        starred = [b for b, flags in branches.items() if True in flags]
        siblings = {b for (o, _), by in named.items() if o == orp for b in by}
        if starred and set(branches) >= siblings:
            out.add((orp, label))
    return out


def _makes(a, made):
    """True where the site makes its label: a starred site, or a site of a label that the branches of an OR make."""
    return a.label is not None and (a.binds or any((orp, a.label) in made for orp, _ in a.atom.branch))


def _kind(atom, made):
    """'test' (the atom makes no label), 'live' (a label it makes is exported or occurs in another atom) or 'dead'."""
    outs = [a for a in atom.arguments if _makes(a, made)]
    if not outs:
        return 'test'
    for a in outs:
        if a.key or (a.variable is not None and any(o.atom is not None and o.atom is not atom for o in a.variable.occurrences)):
            return 'live'
    return 'dead'


def _degenerate(atom):
    """(zero, repeat): the atom has a literal 0 at a site of known type other than Number that is not the grid frame; a
    label occurs at two of its sites that do not make it."""
    zero = any(a.is_zero and a.resolved_type not in (None, 'Number') and not frame_zero(a) for a in atom.arguments)
    labels = [a.label for a in atom.arguments if a.joins]
    return zero, len(labels) != len(set(labels))


@feature
def h1_degenerate_by_role(p):
    """H1: atoms with a literal 0 or a repeated variable, split by the atom's role and by NOT.

    A test atom makes no label; a live atom has an output that is exported or read in another atom; a dead atom's
    outputs are read nowhere. Counted separately outside NOT (pos) and below NOT (neg). Comparison atoms are skipped.
    `zero_frame`: atoms with a literal 0 at a site where it is the grid frame. `zero_pos_test` and `test_any` are
    keys of `g1_degenerate`, which counts the same.
    """
    atoms = _atoms(p)
    made = _made(p.clause.body) if atoms else set()
    out = C.Counter()
    for a in atoms:
        zero, repeat = _degenerate(a)
        side = 'neg' if a.negated else 'pos'
        kind = _kind(a, made) if zero or repeat else None
        if zero:
            out[f'zero_{side}_{kind}'] += 1
        if repeat:
            out[f'rep_{side}_{kind}'] += 1
    keys = ['zero_pos_live', 'zero_pos_dead', 'zero_neg_test', 'zero_neg_live', 'zero_neg_dead',
            'rep_pos_test', 'rep_pos_live', 'rep_pos_dead', 'rep_neg_test', 'rep_neg_live', 'rep_neg_dead']
    res = {k: out[k] for k in keys}
    res['live_any'] = res['zero_pos_live'] + res['rep_pos_live'] + res['zero_neg_live'] + res['rep_neg_live']
    res['zero_frame'] = sum(1 for a in atoms if any(frame_zero(x) for x in a.arguments))
    return res


def _or_nodes(items, base=(), start=0):
    """(path, branch indexes) of each OR node of a scope's body, with the path an Atom's `branch` names it by."""
    for i in range(start, len(items)):
        it, path = items[i], base + (i,)
        if not isinstance(it, list) or not it:
            continue
        if not isinstance(it[0], str):
            yield from _or_nodes(it, path)
        elif it[0] == 'NOT':
            yield from _or_nodes(it, path, 1)
        elif it[0] == 'OR':
            branches = [k for k in range(1, len(it)) if isinstance(it[k], list)]
            yield path, branches
            for k in branches:
                yield from _or_nodes(it[k], path + (k,))
        elif it[0] in ('IF', 'ALL'):
            for k in range(1, len(it)):
                if isinstance(it[k], list):
                    yield from _or_nodes(it[k], path + (k,))


@feature
def h2_or_branches(p):
    """H2: the branches of OR nodes, by whether a branch has an atom with a literal 0 or a repeated variable.

    or_nodes, branches; bad: branches with such an atom; clean: branches without (an empty branch is clean);
    none_clean: OR nodes whose branches all have one; mixed: OR nodes with both kinds of branch. None without an OR node.
    """
    body = p.clause.body
    if body is None:
        return None
    nodes = dict(_or_nodes(body.body))
    if not nodes:
        return None
    bad_in = set()
    for a in body.atoms:
        if a.operator is None and any(_degenerate(a)):
            bad_in.update(a.branch)
    bad = clean = none_clean = mixed = 0
    for path, branches in nodes.items():
        flags = [(path, k) in bad_in for k in branches]
        bad += sum(flags)
        clean += len(flags) - sum(flags)
        none_clean += bool(flags) and all(flags)
        mixed += any(flags) and not all(flags)
    return {'or_nodes': len(nodes), 'bad': bad, 'clean': clean, 'none_clean': none_clean, 'mixed': mixed}


def _context(a):
    return a.branch, a.quantifier, a.conditional


def _encloses(c1, c2):
    """True where conjunctions of context c1 enclose those of context c2: c2 stands in more OR branches, or in an
    ALL or IF part, of c1."""
    return c1 != c2 and c2[0][:len(c1[0])] == c1[0] and c1[1] in (None, c2[1]) and c1[2] in (None, c2[2])


def _repeats(atoms, made):
    """(dup, dup_test, dup_neg) of the atoms, as h3_repeated_test counts them."""
    dup = dup_test = dup_neg = 0
    groups = C.defaultdict(list)
    for a in atoms:
        groups[a.key(), _context(a)].append(a)
    outer = C.defaultdict(list)
    for (key, ctx) in groups:
        outer[key].append(ctx)
    for (key, ctx), members in groups.items():
        n = len(members)
        tests = sum(_kind(a, made) == 'test' for a in members)
        if any(_encloses(c, ctx) for c in outer[key]):
            d, t = n, tests
        else:
            d, t = n - 1, tests - (tests == n)
        dup += d
        dup_test += t
        dup_neg += d if members[0].negated else 0
    return dup, dup_test, dup_neg


@feature
def h3_repeated_test(p):
    """H3: atoms that repeat another atom of the same conjunction or of an enclosing one (same relation, same label at
    every site, binding marks ignored).

    dup: all such atoms; dup_test: those that make no label, which test again a fact that the other atom already
    states or makes; dup_neg: repeats below NOT. Of atoms in one conjunction that read the same, all but one are
    repeats, the one left being an output atom where there is one; every atom is a repeat of an equal atom in an
    enclosing conjunction. The branches of an OR are separate conjunctions. Comparison atoms are counted apart, by the
    same rule, in dup_cmp (operands in either order for a symmetric comparison, and a converse operator reversed).
    """
    body = p.clause.body
    out = {'dup': 0, 'dup_test': 0, 'dup_neg': 0, 'dup_cmp': 0}
    if body is None:
        return out
    made = _made(body)
    out['dup'], out['dup_test'], out['dup_neg'] = _repeats([a for a in _atoms(p) if a.arguments], made)
    out['dup_cmp'] = _repeats([a for a in body.atoms if a.operator is not None], made)[0]
    return out
    made = _made(p.clause.body)
    groups = C.defaultdict(list)
    for a in atoms:
        groups[a.key(), _context(a)].append(a)
    outer = C.defaultdict(list)
    for (key, ctx) in groups:
        outer[key].append(ctx)
    for (key, ctx), members in groups.items():
        n = len(members)
        tests = sum(_kind(a, made) == 'test' for a in members)
        if any(_encloses(c, ctx) for c in outer[key]):
            dup, dup_test = n, tests
        else:
            dup, dup_test = n - 1, tests - (tests == n)
        out['dup'] += dup
        out['dup_test'] += dup_test
        out['dup_neg'] += dup if members[0].negated else 0
    return out
