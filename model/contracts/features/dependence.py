"""Model input layer: the dependence features of a table, from the structure of the bodies that give it: what binds, computes, tests, filters,
negates and offers alternatives for each of its columns. They read the program, and no row.

A body is the engine's IR of one body that the evaluator joins for the table, read into this form:

    {'columns': [the variable at each column of the table], 'nodes': [node, ...]}

with one node for each part of the body:

    {'kind': 'atom', 'id': atom identity, 'reads': ('table', n) | ('fact', name) | ('key', None) | ('absent', None), 'args': [(column identity, variable or None), ...]}
    {'kind': 'lib', 'id': atom identity, 'relation': lib name, 'args': [(lib column, variable or None), ...], 'computes': [variable, ...]}
    {'kind': 'cmp', 'op': operator, 'first': variable, 'second': variable or None (0), 'makes': whether it makes its first variable}
    {'kind': 'not' | 'all', 'outer': [variable, ...], 'body': body}
    {'kind': 'or', 'exported': [variable, ...], 'branches': [body, ...]}

A variable is the engine's identity of a label, and None stands for a term. A feature names a column by its place in the table, which
features.py turns into the column's token, and a lib relation and an operator by their given names.
"""
from collections import Counter


def walk(body):
    """Every node of body, those of its NOT, ALL and OR bodies included."""
    for n in body['nodes']:
        yield n
        if n['kind'] in ('not', 'all'):
            yield from walk(n['body'])
        elif n['kind'] == 'or':
            for b in n['branches']:
                yield from walk(b)


def conjunctions(body):
    """body and the body of each branch of its OR nodes, at any depth: the conjunctions in which an atom binds its variables."""
    yield body
    for n in body['nodes']:
        if n['kind'] == 'or':
            for b in n['branches']:
                yield from conjunctions(b)


def held(n):
    return [v for _, v in n['args'] if v is not None]


def sources(body, v):
    """The (relation read, column) pairs that bind v in body: those of its atoms, and those of the branches of an OR that exports v."""
    out = set()
    for n in body['nodes']:
        if n['kind'] == 'atom':
            out |= {(n['reads'], c) for c, x in n['args'] if x == v}
        elif n['kind'] == 'lib' and v in n['computes']:
            out.add((('lib', n['relation']), None))
        elif n['kind'] == 'cmp' and n['makes'] and n['first'] == v:
            out.add((('equal', None), None))
        elif n['kind'] == 'or' and v in n['exported']:
            for b in n['branches']:
                out |= sources(b, v)
    return out


def column_features(body, v):
    """The features of the column whose variable is v, in one body: its relation atoms are those of the body's own conjunction; a join,
    a lib atom, a comparison, a NOT, an ALL and an OR count in that conjunction and in each branch of an OR, at any depth."""
    f = {'relation atoms': sum(1 for n in body['nodes'] if n['kind'] == 'atom' and v in held(n))}
    f['joins'] = False
    f['alternatives'] = 0
    f['alternatives bind it from different sources'] = False
    for conj in conjunctions(body):
        nodes = conj['nodes']
        if sum(1 for n in nodes if n['kind'] == 'atom' and v in held(n)) >= 2:
            f['joins'] = True
        for n in nodes:
            if n['kind'] == 'lib' and v in held(n):
                f[('computed by ' if v in n['computes'] else 'tested by ') + n['relation']] = True
            elif n['kind'] == 'cmp' and v in (n['first'], n['second']):
                if n['makes'] and n['first'] == v:
                    f['made equal to ' + ('zero' if n['second'] is None else 'another variable')] = True
                else:
                    f['compared by ' + n['op']] = True
            elif n['kind'] == 'not' and v in n['outer']:
                f['under a NOT'] = True
            elif n['kind'] == 'all' and v in n['outer']:
                f['under an ALL'] = True
            elif n['kind'] == 'or' and v in n['exported']:
                f['alternatives'] += len(n['branches'])
                if len({frozenset(sources(b, v)) for b in n['branches']}) > 1:
                    f['alternatives bind it from different sources'] = True
    return f


def table_features(body):
    """The features of the table, in one body."""
    nodes = list(walk(body))
    kinds = Counter(n['kind'] for n in nodes)
    f = {'relation atoms': kinds['atom'], 'lib atoms': kinds['lib'], 'comparisons': kinds['cmp'], 'NOTs': kinds['not'], 'ALLs': kinds['all'],
         'ORs': kinds['or']}
    joined = twice = 0
    for conj in conjunctions(body):
        atoms = [n for n in conj['nodes'] if n['kind'] == 'atom']
        per_var = Counter(v for n in atoms for v in set(held(n)))
        joined += sum(1 for c in per_var.values() if c >= 2)
        reads = Counter(n['reads'] for n in atoms)
        twice += sum(1 for r, c in reads.items() if c >= 2 and r[0] in ('table', 'fact'))
    f['joined variables'] = joined
    f['reads one table twice'] = twice > 0
    variables = {v for n in nodes for v in (held(n) if n['kind'] in ('atom', 'lib') else [])}
    f['variables not at a column'] = len(variables - set(body['columns']))
    return f


def pair_features(body, i, j):
    """The features of the pair of columns i and j, in one body; the pair is unordered."""
    a, b = body['columns'][i], body['columns'][j]
    f = {}
    f['shares an atom with'] = any(n['kind'] == 'atom' and a in held(n) and b in held(n) for n in body['nodes'])
    return f


def features(bodies, symmetries=()):
    """(column features [{feature: value}] by column, table features {feature: value}, pair features [(i, j, feature, value)]) of a table
    given by `bodies`, each body read as the module's docstring gives. Over several bodies, a count is the greatest, and a bool holds where it
    holds in some body. symmetries: the permutations of the table's columns under which its content is the same, each a list that gives
    the column that each column goes to; a pair feature `interchangeable with` holds where one of them takes one column of the pair to the
    other."""
    if not bodies:
        return None
    width = len(bodies[0]['columns'])
    cols = [merge(column_features(b, b['columns'][i]) for b in bodies) for i in range(width)]
    table = merge(table_features(b) for b in bodies)
    pairs = []
    for i in range(width):
        for j in range(width):
            if i != j:
                pf = merge(pair_features(b, i, j) for b in bodies)
                pf['interchangeable with'] = any(p[i] == j or p[j] == i for p in symmetries)
                pairs += [(i, j, k, v) for k, v in pf.items()]
    return cols, table, pairs


def merge(dicts):
    out = {}
    for d in dicts:
        for k, v in d.items():
            if isinstance(v, bool):
                out[k] = out.get(k, False) or v
            else:
                out[k] = max(out.get(k, v), v)
    return out
