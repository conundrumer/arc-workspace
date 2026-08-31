"""Matching a shape signature with the parser: the worked example.

A shape signature names an operation with no stable lexical anchor: the
relation names vary per solver, and the operation lives in rule
structure. Grep misses those sites; a survey matches them with a script
under its scratch path, over the parsed corpus:

    from dl.corpus import each_solver

    for path, program, idx in each_solver():
        ...

`idx.refs` holds every atom reference: its role (head/pos/neg/agg), its
resolved relation key, its rule index into `idx.rules`, and its line.
Start there; reach for `body_literals` when the shape involves
comparisons, disjunctions, or aggregate bodies. For the node types,
read the `# --- AST ---` and `# --- reference index ---` sections of
`src/dl/dlparse.py`; the lexer and parser sections are not needed.

The test below matches the Unanimous shape: one relation twice positive
in a rule, with a disequality between the two bindings of one argument.
A match is a candidate, not a home: each hit is read in its rule, per
the survey procedure.
"""

from itertools import combinations

from dl.dlparse import TOP, Cmp, Index, Var, body_literals, parse


def unanimous_sites(idx: Index) -> list[tuple[int, tuple[str, str]]]:
    """(line, relation key) of each rule holding the Unanimous shape."""
    hits = []
    by_rule: dict[int, dict] = {}
    for ref in idx.refs:
        if ref.role == "pos":
            by_rule.setdefault(ref.rule, {}).setdefault(ref.key, []).append(ref.atom)
    for n, by_key in by_rule.items():
        rule = idx.rules[n].rule
        diseq = {
            frozenset((c.lhs.name, c.rhs.name))
            for c in body_literals(rule)
            if isinstance(c, Cmp) and c.op == "!="
            and isinstance(c.lhs, Var) and isinstance(c.rhs, Var)
        }
        for key, atoms in by_key.items():
            for a1, a2 in combinations(atoms, 2):
                if len(a1.args) == len(a2.args) and any(
                    isinstance(x, Var) and isinstance(y, Var)
                    and frozenset((x.name, y.name)) in diseq
                    for x, y in zip(a1.args, a2.args)
                ):
                    hits.append((rule.line, key))
    return hits


FIXTURE = """\
.decl item(k: number, v: number)
.decl other(k: number, v: number)
.decl clash(k: number)
clash(K) :- item(K, V1), item(K, V2), V1 != V2.
.decl pair(k: number, a: number, b: number)
pair(K, A, B) :- item(K, A), item(K, B).
.decl diff(a: number, b: number)
diff(A, B) :- item(_, A), other(_, B), A != B.
"""


def test_unanimous_shape_match():
    """The planted site is the only hit: `pair` repeats the relation with
    no disequality, and `diff`'s disequality spans two relations."""
    idx = Index(parse(FIXTURE))
    assert unanimous_sites(idx) == [(4, (TOP, "item"))]
