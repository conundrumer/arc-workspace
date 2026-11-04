"""Dev labeling layer: the values some proposers offer on a task, by their definitions in the lib, to tell which stored relation lost its value
where a variant leaves the engine no assignment at all.

proposer_values(name, task_json) is the set of values, or None for a proposer this module does not define. "Every input" counts the test inputs.
"""
from collections import Counter

TYPE_DOMAINS = {'AxisDomain', 'D4Domain', 'DiagAxisDomain', 'DiagDirDomain', 'DirDomain', 'SenseDomain', 'SymDomain'}  # every value of the type, on any task


def counts(g):
    return Counter(c for row in g for c in row)


def proposer_values(name, task_json):
    inputs = [p['input'] for p in task_json['train'] + task_json['test']]
    outputs = [p['output'] for p in task_json['train']]
    if name == 'SharedColor':
        return set.intersection(*(set(counts(g)) for g in inputs))
    if name == 'DominantColor':
        return set.intersection(*({c for c, n in counts(g).items() if n == max(counts(g).values())} for g in inputs))
    if name == 'RarestColor':
        return set.intersection(*({c for c, n in counts(g).items() if n == min(counts(g).values())} for g in inputs))
    if name == 'AnyOutNewColor':
        return set().union(*(set(counts(g)) for g in outputs)) - set().union(*(set(counts(g)) for g in inputs))
    if name == 'VanishedColor':
        return set.intersection(*(set(counts(g)) for g in inputs)) - set().union(*(set(counts(g)) for g in outputs))
    if name == 'ConstInDim':
        return set.intersection(*({len(g), len(g[0])} for g in inputs))
    if name == 'ConstOutDim':
        return set.intersection(*({len(g), len(g[0])} for g in outputs))
    return None


def missing(pins, proposer_of, task_json):
    """The pinned relations whose one-column value its proposer no longer offers; a relation whose proposer is undefined here counts as missing,
    and one of a type domain never does."""
    out = []
    for rel, rows in pins.items():
        name = proposer_of.get(rel)
        if name in TYPE_DOMAINS:
            continue
        vals = proposer_values(name, task_json)
        if vals is None or len(rows) != 1 or len(rows[0]) != 1 or rows[0][0] not in vals:
            out.append(rel)
    return sorted(out)
