"""Group G4, repeated atoms: the candidate's form only.

Two atoms repeat each other when they have the same relation, the same label (or the literal 0) at every site, and the
same negation, binding marks and operand order of a symmetric atom ignored (`Atom.key()`).
"""
import collections as C

from featlib import feature


def _made(body):
    """{(OR path, label)}: the labels that a starred site inside an OR makes and every other branch of that OR names."""
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


def _is_test(atom, made):
    """True where the atom makes no label."""
    return not any(a.label is not None and (a.binds or any((orp, a.label) in made for orp, _ in a.atom.branch))
                   for a in atom.arguments)


def _context(a):
    return a.branch, a.quantifier, a.conditional


def _encloses(c1, c2):
    """True where conjunctions of context c1 enclose those of context c2: c2 stands in more OR branches, or in an
    ALL or IF part, of c1."""
    return c1 != c2 and c2[0][:len(c1[0])] == c1[0] and c1[1] in (None, c2[1]) and c1[2] in (None, c2[2])


@feature
def g4_repeats(p):
    """G4 repeated atoms: atoms that repeat another atom of the same conjunction or of an enclosing one. `dup`: all
    such atoms; `dup_test`: those that make no label, which test again what another atom already states or makes;
    `dup_neg`: repeats below NOT. Of atoms in one conjunction that read the same, all but one are repeats, the one left
    being an output atom where there is one; every atom is a repeat of an equal atom in an enclosing conjunction. The
    branches of an OR are separate conjunctions. Comparison atoms count.

    Needs: form. Monotone: yes.
    """
    body = p.clause.body
    if body is None:
        return None
    out = {'dup': 0, 'dup_test': 0, 'dup_neg': 0}
    if not body.atoms:
        return out
    made = _made(body)
    groups = C.defaultdict(list)
    for a in body.atoms:
        groups[a.key(), _context(a)].append(a)
    outer = C.defaultdict(list)
    for (key, ctx) in groups:
        outer[key].append(ctx)
    for (key, ctx), members in groups.items():
        n = len(members)
        tests = sum(_is_test(a, made) for a in members)
        if any(_encloses(c, ctx) for c in outer[key]):
            dup, dup_test = n, tests
        else:
            dup, dup_test = n - 1, tests - (tests == n)
        out['dup'] += dup
        out['dup_test'] += dup_test
        out['dup_neg'] += dup if members[0].negated else 0
    return out
