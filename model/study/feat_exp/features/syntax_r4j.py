"""Round 4, explorer J: form-only features (the form and the library interfaces).

A site term is `*V` (binds V), `^V` (binds V and exports it as a key column), a plain variable, or a literal.
"""
from featlib import feature, parse

COMPARISON = {'=', '!=', '<', '>', '<=', '>='}


def _walk(tree):
    """Every relation atom of a parsed form, including atoms inside OR and NOT."""
    if isinstance(tree, list):
        if tree and isinstance(tree[0], str) and tree[0] not in ('OR', 'NOT', 'IF') and not tree[0].startswith(':'):
            yield tree
            return
        for t in tree:
            yield from _walk(t)


def _site_terms(node):
    for s in node[1:]:
        if isinstance(s, list) and s and isinstance(s[0], str) and s[0].startswith(':'):
            for t in s[1:]:
                if isinstance(t, list):
                    if t and isinstance(t[0], str) and t[0].startswith(':'):
                        yield from _site_terms([None, t])
                elif isinstance(t, str):
                    yield t


def _variables(atom):
    """The variable names an atom mentions (starred or not), and the number of its site terms."""
    if atom[0] in COMPARISON:
        terms = [t for t in atom[1:] if isinstance(t, str)]
    else:
        terms = list(_site_terms(atom))
    return {t.lstrip('*^') for t in terms if t and (t[0] in '*^' or t[0].isupper())}, len(terms)


@feature
def j2_atom_graph(p):
    """J2: how the atoms of the form connect through shared variables.

    parts: connected components of the graph whose nodes are the atoms that mention a variable, two atoms being joined
    when they share a variable; isolated: atoms with site terms and no variable (every term a literal such as `0`);
    extra: parts above 1. A form with extra parts is a product of independent factors. None for a form without atoms.
    """
    atoms_ = [_variables(a) for a in _walk(parse(p.form))]
    if not atoms_:
        return None
    with_vars = [v for v, n in atoms_ if v]
    isolated = sum(1 for v, n in atoms_ if not v and n)
    parent = list(range(len(with_vars)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    owner = {}
    for i, vs in enumerate(with_vars):
        for v in vs:
            if v in owner:
                parent[find(i)] = find(owner[v])
            else:
                owner[v] = i
    comps = len({find(i) for i in range(len(with_vars))})
    parts = comps + isolated
    return {'comps': comps, 'isolated': isolated, 'parts': parts, 'extra': max(parts - 1, 0)}
