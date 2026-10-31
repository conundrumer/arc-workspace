"""Form-only features of explorer B, round 2: the role of a degenerate argument in an atom.

An atom is a generator when one of its sites makes a new label (a starred site, or the first site in a later branch
of an OR of a label the OR exports). It is a filter when none does. A site argument is degenerate when it is the
literal `0` (except at a site where it is the grid frame, `featlib.FRAME_ZERO_SITES`, which `zero_frame` counts), or
when a label occurs at two sites of the same atom that do not make it.
"""
import collections as C

from featlib import feature, frame_zero, signature


def _made(scope):
    """The arguments that make their label. A label made outside every OR is made at its starred site. A label that an
    OR's first branch makes and every later branch names is made in each branch of that OR, at the branch's positive
    site (or `=` operand) of the label, outside NOT, ALL and IF tests, whose atom comes first in canonical order,
    wherever the stars stand."""
    out = {id(a) for a in scope.arguments if a.binds}
    branches = C.defaultdict(set)
    for a in scope.atoms:
        for orp, k in a.branch:
            branches[orp].add(k)
    for v in scope.variables.values():
        for b in v.binders:
            for orp, k in b.atom.branch:
                if k != 1:
                    continue
                picks = []
                for kk in sorted(branches[orp]):
                    occ = [a for a in v.occurrences if a.atom is not None and a.atom.branch and a.atom.branch[-1] == (orp, kk)
                           and not a.atom.negated and a.atom.conditional != 'test' and a.atom.quantifier is None
                           and (a.atom.operator is None or (a.atom.operator == '=' and a is a.atom.first))]
                    if not occ:
                        picks = None
                        break
                    picks.append(min(occ, key=lambda a: (repr(signature(a.atom)), a.name)))
                if picks:
                    out -= {id(a) for a in v.occurrences if a.atom is not None and any(o == orp for o, _ in a.atom.branch)}
                    out |= {id(a) for a in picks}
    return out


def _profile(atom, made):
    """(makes, zero, repeat) of an atom. `zero` counts its sites with the literal 0, but the sites where it is the grid
    frame (`featlib.FRAME_ZERO_SITES`). `repeat` counts labels at two or more of its sites that do not make them."""
    makes = any(id(a) in made for a in atom.arguments)
    zero = sum(a.is_zero and not frame_zero(a) for a in atom.arguments)
    names = C.Counter(a.label for a in atom.arguments if a.label and id(a) not in made)
    repeat = sum(1 for n in names.values() if n > 1)
    return makes, zero, repeat


def _atoms(p):
    body = p.clause.body
    if body is None:
        return [], set()
    return [a for a in body.atoms if not a.operator and a.arguments], _made(body)


@feature
def b1_degenerate_generator(p):
    """B1: atoms that make a new label and take the literal 0 or a repeated label at their other sites. `zero_frame`: such atoms with a literal 0 at a site where it is the grid frame."""
    zero = repeat = frame = 0
    atoms, made = _atoms(p)
    for a in atoms:
        makes, z, r = _profile(a, made)
        if makes:
            zero += z > 0
            repeat += r > 0
            frame += any(frame_zero(x) for x in a.arguments)
    return {'zero': zero, 'repeat': repeat, 'any': zero + repeat, 'zero_frame': frame}


@feature
def b2_degenerate_filter(p):
    """B2: atoms that make no label and take the literal 0 or a repeated label at their sites. `zero_frame`: such atoms with a literal 0 at a site where it is the grid frame."""
    zero = repeat = frame = 0
    atoms, made = _atoms(p)
    for a in atoms:
        makes, z, r = _profile(a, made)
        if not makes:
            zero += z > 0
            repeat += r > 0
            frame += any(frame_zero(x) for x in a.arguments)
    return {'zero': zero, 'repeat': repeat, 'any': zero + repeat, 'zero_frame': frame}
