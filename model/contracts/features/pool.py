"""Model input layer: pooling. A pooled feature lifts a feature from one level to the next: from per example to per assignment (over the
examples), or from per assignment to across assignments (over the assignments). A pooling operator is a function of the set of values, so it
does not depend on their order. A feature that reads the train output pools over the train examples only.
"""


def numeric(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def pooled(values):
    """{operator: value}: the pooled features of one feature's values, one value per example or per assignment."""
    out = {'all equal': all(v == values[0] for v in values), 'distinct': len({repr(v) for v in values})}
    out['all distinct'] = out['distinct'] == len(values)
    if values and all(numeric(v) for v in values):
        out['min'], out['max'] = min(values), max(values)
        out['spread'] = max(values) - min(values)
    if values and all(isinstance(v, bool) for v in values):
        out['share true'] = round(sum(values) / len(values), 3)
    return out


def per_assignment(examples, reads_output):
    """{(feature, operator): value}: the pooled features over the examples, from {example: {feature: value}} of one assignment. A feature for
    which reads_output(feature) holds pools over the train examples only."""
    keys = {k for f in examples.values() for k in f}
    out = {}
    for k in sorted(keys):
        names = [e for e in examples if e.startswith('train/')] if reads_output(k) else list(examples)
        for op, v in pooled([examples[e].get(k) for e in names]).items():
            out[(k, op)] = v
    return out


def hull(values):
    """The least set of the values' kind that holds them all: one value where all are equal; for numbers, the range from the least to the greatest;
    for other values, the set of values. None for a bool that takes both values, since that set holds every bool."""
    if all(v == values[0] for v in values):
        return ('value', values[0])
    if all(numeric(v) for v in values):
        return ('range', min(values), max(values))
    if all(isinstance(v, bool) for v in values):
        return None
    return ('values', sorted({repr(v) for v in values}))


def in_hull(h, v):
    """Whether value v lies in hull h."""
    if h[0] == 'value':
        return v == h[1]
    if h[0] == 'range':
        return numeric(v) and h[1] <= v <= h[2]
    return repr(v) in h[1]
