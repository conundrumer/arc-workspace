"""Model input layer: where each feature sits in the feature structure.

Each feature has three coordinates.
- What it reads: `static` (the program's text, the column types inferred from it, and the engine's flows of its columns, without the rows) or
  `dynamic` (the rows the query gives when it runs; it may also read the column types).
- Aggregation level: `per example` (one table at one example under one assignment; a table that a determination gives is the same at every
  example), `per assignment` (one table across all examples under one assignment), or `across assignments` (one table across its assignments).
- Arity: the number of tables a feature reads: its owner, and each other table. Each other table stands to the owner as a `parent` (a table the owner's query reads), an `ancestor` at a depth (a table that many
  queries upstream, 2 or more), or a `base table` (input, ex_input, ex_output: the task's own grids).
"""
import re

import engine as E
from features import STRUCTURE
from grammar import SCHEMAS, tails
import across as AX
import assignments as AS
import progress as PR

BASE = {'input', 'ex_input', 'ex_output'}
OTHER = re.compile('⟨t:[^⟩]*⟩')  # another table's token in a feature key (features.py)
PLACE = re.compile(r'^\[(parent|ancestor (\d+)|table) ')  # how another table stands to the owner, in its `<token> describe`
PROVENANCE = (' origin kinds', ' copy steps', ' from the input', ' from the train outputs', ' from a task parameter')
TABLE_PROVENANCE = re.compile(r'^(columns of \w+ origin|every column is a copy|some column from the train outputs|some column from a task parameter|steps from the input grid|tables before it)$')
DEPENDENCE = re.compile(r' (relation atoms|joins|alternatives|alternatives bind it from different sources|under a NOT|under an ALL|(computed|tested) by \w+|'
                        r'compared by \S+|made equal to (zero|another variable))$|^(relation atoms|lib atoms|comparisons|NOTs|ALLs|ORs|joined variables|'
                        r'reads one table twice|variables not at a column)$| (shares an atom with|interchangeable with) (\w+\.)?\u27e8c:[^\u27e9]*\u27e9$')  # dependence.py
WITH_OUTPUT = tuple(x.strip() for x in tails(SCHEMAS, lambda reads: reads == {'output'})) + tuple(x.strip() for x in PR.WITH_OUTPUT)
WITH_CHANGED = tuple(x.strip() for x in tails(SCHEMAS, lambda reads: reads == {'input', 'output'})) + tuple(x.strip() for x in PR.WITH_BOTH)  # the cells where the input and the train output differ
WITH_INPUT = tuple(x.strip() for x in tails(SCHEMAS, lambda reads: reads == {'input'})) + tuple(x.strip() for x in PR.WITH_INPUT)


def depth(graph, a, b):
    """The number of queries from table a back to table b, or None where b is not upstream of a."""
    a, b = E.node(a), E.node(b)
    seen, layer, d = {a}, {a}, 0
    while layer:
        d += 1
        layer = {y for x in layer for y in graph.get(x, ()) if y not in seen}
        if b in layer:
            return d
        seen |= layer
    return None


def other(graph, owner, table):
    """(name, relation to the owner, depth) of one other table a feature reads; a table of the program is named by its place, and a base
    table by its own name."""
    if table in BASE:
        return (table, 'base table', None)
    d = depth(graph, owner, table)
    return ('[parent]' if d == 1 else '[ancestor %s]' % d, 'parent' if d == 1 else 'ancestor', d)


def coordinates(key, graph, static=frozenset(), describe=None):
    """{'reads', 'level', 'arity', 'others'} of a feature key 'owner|feature', or of a static feature name in `static`. A provenance feature
    (provenance.py), a dependence feature (dependence.py) and a description read the program's text and the engine's export, and no row. describe: {token: its `<token> describe`}
    of the owner's record, which gives the place of each other table that a key names."""
    if key in static:
        return dict(reads='static', level='per example', arity=1, others=[])
    owner, _, feat = key.partition('|')
    named = list(dict.fromkeys(OTHER.findall(feat)))
    if feat.endswith(PROVENANCE) or feat.endswith(' describe') or TABLE_PROVENANCE.match(feat) or DEPENDENCE.search(feat):
        return dict(reads='static', level='per example', arity=1, others=[])
    if named:
        others = []
        for tok in named:
            m = PLACE.match((describe or {}).get(tok, ''))
            where, k = (m[1], m[2]) if m else ('table', None)
            others.append((tok, 'parent' if where == 'parent' else 'ancestor', 1 if where == 'parent' else int(k) if k else None))
    elif feat.endswith(WITH_INPUT):
        others = [other(graph, owner, 'input')]
    elif feat.endswith(WITH_CHANGED):
        others = [other(graph, owner, 'input'), other(graph, owner, 'ex_output')]
    elif feat.endswith(WITH_OUTPUT):
        others = [other(graph, owner, 'ex_output')]
    elif feat == 'selectivity':
        others = [other(graph, owner, u) for u in sorted(graph.get(E.node(owner), ()))]
    elif feat in STRUCTURE and feat != 'Cartesian product':
        others = [other(graph, owner, u) for u in sorted(E.upstream(graph, owner))] + [other(graph, owner, 'input')]
    else:
        others = []
    level = 'across assignments' if feat.endswith(AS.ACROSS) or feat == 'assignments of its table' else 'per assignment' if feat.endswith(AX.ACROSS) else 'per example'
    return dict(reads='dynamic', level=level, arity=1 + len(others), others=others)
