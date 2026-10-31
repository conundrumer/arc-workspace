"""Group G7, a join that cuts a domain: the candidate's form and the available tables (not X).

A site makes its label at a starred site; a label that the first branch of an OR makes and every later branch names is
made in each branch, at the branch's positive site of the label, outside NOT, ALL and IF tests, whose atom comes first
in canonical order.
"""
import collections as C

from featlib import feature, signature

READS = ('table', 'fact')


def _made(scope):
    """The ids of the arguments that make their label."""
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


def _domains(arg):
    """(assignment, train) -> set of values of the table column an argument reads, or None."""
    table = arg.atom.table
    col = arg.atom.interface.column(arg.name)
    if table is None or col is None or col.index is None:
        return None
    out = {}
    for e in table.all_entries:  # the test entries too, where the tables have them
        out.setdefault((e['assignment'], e['train'] if 'train' in e else ('test', e['test'])), set()).update(tuple(r[col.index]['value']) for r in e['rows'])
    return out


@feature
def g7_join_cut(p):
    """G7 a join that cuts a domain: for each label that a positive read of one available table makes and a positive
    read of another available table holds at a site that does not make it (Ident labels left out, since Ident values
    are local to their table), the share of the making column's
    values per context that the other table's column also holds. `min`: the smallest share; `cut`: joins with a share
    below 1; `vacuous`: joins with share 1; `void`: joins with a context where no value is held. None without such a
    join.

    Needs: form. Monotone: yes.
    """
    body = p.clause.body
    if body is None:
        return None
    made = _made(body)
    joins = []
    for v in body.variables.values():
        if v.resolved_type == 'Ident':
            continue
        sites = [a for a in v.occurrences if a.atom is not None and a.atom.operator is None and not a.atom.negated
                 and a.atom.kind in READS and a.atom.interface is not None and a.atom.interface.table]
        for b in sites:
            if id(b) not in made:
                continue
            for j in sites:
                if id(j) not in made and j.atom.interface.table != b.atom.interface.table:
                    joins.append((b, j))
    shares = []
    void = 0
    for b, j in joins:
        s = _domains(b)
        t = _domains(j)
        if s is None or t is None:
            continue
        per = [len(s[k] & t[k]) / len(s[k]) for k in s if s[k] and k in t]
        if not per:
            continue
        shares.append(sum(per) / len(per))
        void += any(v == 0 for v in per)
    if not shares:
        return None
    return {'min': min(shares), 'cut': sum(v < 1 for v in shares), 'vacuous': sum(v == 1 for v in shares),
            'void': void}
