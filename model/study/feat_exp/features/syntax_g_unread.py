"""Group G3, labels made and read nowhere: the finished clause's form, the library interfaces and the types of the
sites.

An atom makes the labels that it stars (`*V`, `^V`). Where one branch of an OR stars a label that every other branch
names, every atom of the OR that names the label makes it. A label is unread when it is not exported (`^V`, or a head
of an INIT port) and no atom outside its makers names it. A label is computed when a library relation or macro makes
it. A cell label has the type Position or Box in a grid frame (input, output or no frame tag).
"""
import collections as C

from featlib import feature

LIBRARY_KINDS = ('relation', 'macro')
TABLE_KINDS = ('fact', 'table', 'clause', 'port', 'output', 'x')


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


def _makes(a, made):
    return a.label is not None and (a.binds or any((orp, a.label) in made for orp, _ in a.atom.branch))


def _is_cell(v):
    frame = v.frame
    return v.resolved_type in ('Position', 'Box') and (frame is None or frame in ('', 'input', 'output'))


COMPARE = {'<': 'strict', '>': 'strict', '<=': 'nonstrict', '>=': 'nonstrict', '!=': 'neq', '=': 'eq'}


@feature
def g3_unread(p):
    """G3 labels made and read nowhere. `unread`: labels that the clause makes and no other atom names, by type
    (`unread_cell`, `unread_number`, `unread_key`, `unread_value`; a key label is an Ident, or a Position or Box that is not a cell, since a table passes such a label on to a later clause as an object's identity or a cell of a relation's site; a value label is any other type, such as a Color). Of the labels that a library atom makes: `ungrounded`, cell
    labels that no positive read of a fact or table names; `free_number`, Number labels that no comparison names. And
    `uncompared`: library relations or macros with two or more atoms that make a Number, where no comparison joins
    a Number of one such atom to a Number of another.

    Needs: full. Monotone: no.
    """
    body = p.clause.body
    if body is None:
        return None
    made = _made(body)
    out = C.Counter({'unread': 0, 'unread_cell': 0, 'unread_number': 0, 'unread_key': 0, 'unread_value': 0, 'ungrounded': 0,
                     'free_number': 0, 'uncompared': 0})
    owner = C.defaultdict(set)
    for v in body.variables.values():
        makers = [a for a in v.occurrences if a.atom is not None and _makes(a, made)]
        if not makers:
            continue
        maker_atoms = {id(a.atom) for a in makers}
        read = any(a.atom is None or id(a.atom) not in maker_atoms for a in v.occurrences) or v.key
        computed = any(a.atom.kind in LIBRARY_KINDS for a in makers)
        if not read:
            out['unread'] += 1
            kind = 'cell' if _is_cell(v) else 'number' if v.resolved_type == 'Number' else \
                'key' if v.resolved_type in ('Ident', 'Position', 'Box') else 'value'
            out['unread_' + kind] += 1
        if computed and _is_cell(v):
            grounded = any(id(a.atom) not in maker_atoms and a.atom.kind in TABLE_KINDS and not a.atom.negated
                           for a in v.joins)
            out['ungrounded'] += not grounded
        if computed and v.resolved_type == 'Number':
            out['free_number'] += not any(a.atom is not None and a.atom.operator for a in v.occurrences)
    nums = C.defaultdict(lambda: C.defaultdict(set))
    for a in body.arguments:
        at = a.atom
        if at.kind in LIBRARY_KINDS and a.column_type == 'Number' and _makes(a, made):
            nums[at.relation][id(at)].add(a.label)
            owner[a.label].add((at.relation, id(at)))
    compared = set()
    for at in body.comparisons:
        u, v = at.first, at.second
        if u is None or v is None or u.label is None or v.label is None or at.operator not in COMPARE:
            continue
        compared |= {ru for ru, iu in owner[u.label] for rv, iv in owner[v.label] if ru == rv and iu != iv}
    out['uncompared'] = sum(1 for rel, by in nums.items() if len(by) >= 2 and rel not in compared)
    return dict(out)
