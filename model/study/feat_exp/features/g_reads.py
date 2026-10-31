"""Group G6, which earlier tables the form reads: the candidate's form and the clauses before the point.

A read of an earlier clause is an atom of the candidate's body whose interface is a table of that clause (or the port
of an instance that clause declares). The age of a read is the number of clauses between that clause and the point
(1 for the clause just before). A clause is pending when it declares a relation and no later clause before the point
reads it. A DET clause is never pending: the program declares its parameters ahead, and later clauses read them in
any order.
"""
import collections as C

from featlib import feature

READS = ('table', 'clause', 'port', 'output', 'x')


def _producer(atom, clauses):
    """The clause before the point that the atom reads, or None."""
    i = atom.interface
    if i is None or atom.kind not in READS:
        return None
    for c in clauses:
        if i.table is not None and i.table in c.table_ids:
            return c
    if i.table is None:     # a port of an instance reads no exported table: the instance's relation names its clause
        for c in clauses:
            if c.relation is not None and atom.relation.partition('.')[0] == c.relation:
                return c
    return None


def _pending(clauses):
    """The clauses before the point that declare a relation, are not DET clauses and that no later clause before the
    point reads."""
    read = set()
    for c in clauses:
        for a in c.atoms:
            src = _producer(a, [d for d in clauses if d.index < c.index])
            if src is not None:
                read.add(src.index)
    return [c for c in clauses if c.relation is not None and c.keyword != 'DET' and c.index not in read]


def _role(clause, scope):
    if clause.keyword == 'INIT':
        return clause.component, scope.name
    return 'rule', None


def _signatures(atoms):
    return C.Counter((a.relation, tuple(sorted(x.name for x in a.arguments))) for a in atoms
                     if a.operator is None and a.arguments)


@feature
def g6_reads(p):
    """G6 which earlier tables the form reads. Over the reads of earlier clauses: `n` (reads), `mean`, `min` and
    `max` age, `prev` (1 when some read has age 1), `deep` (reads with age above 5), `inputs` (reads of the input and
    example facts). Over the pending clauses: `pending`, `read` (pending clauses the candidate reads), `share`
    (read over pending), `newest` (1 when the candidate reads the most recent pending clause), `skipped` (pending
    clauses defined after the oldest pending clause that the candidate reads, which it does not read). Against the
    bodies of earlier clauses of the same role (an INIT port of the same component and name, or a RULE or DET body):
    `overlap`, the largest multiset Jaccard overlap of the atoms' relations and site names, and `exact`, 1 when it
    is 1. The key `n` and its kin are absent without a read of an earlier clause, and the pending keys without a
    pending clause.

    Needs: form. Monotone: partly.
    """
    body = p.clause.body
    if body is None:
        return None
    clauses = p.clauses_before()
    point = p.clause.index
    out = {}
    reads = [(_producer(a, clauses), a) for a in body.atoms]
    ages = [point - c.index for c, a in reads if c is not None]
    inputs = sum(a.kind == 'fact' for a in body.atoms)
    if ages:
        out.update(n=len(ages), mean=sum(ages) / len(ages), min=min(ages), max=max(ages), prev=float(min(ages) == 1),
                   deep=sum(a > 5 for a in ages), inputs=inputs)
    pend = _pending(clauses)
    if pend:
        got = {c.index for c, a in reads if c is not None}
        hit = [c for c in pend if c.index in got]
        oldest = min((c.index for c in hit), default=None)
        out.update(pending=len(pend), read=len(hit), share=len(hit) / len(pend),
                   newest=float(max(pend, key=lambda c: c.index).index in got),
                   skipped=sum(1 for c in pend if oldest is not None and c.index > oldest and c.index not in got))
    mine = _signatures(body.atoms)
    if mine:
        role = _role(p.clause, body)
        best = 0.0
        for c in clauses:
            for s in c.scopes:
                if _role(c, s) != role:
                    continue
                theirs = _signatures(s.atoms)
                union = sum((mine | theirs).values())
                if union:
                    best = max(best, sum((mine & theirs).values()) / union)
        out.update(overlap=best, exact=float(best == 1.0))
    return out or None
