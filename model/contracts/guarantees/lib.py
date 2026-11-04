"""Dev layer, second order: what a lib component's output guarantees by construction, in terms of the feature library. Not model input.

Each rule names a component, an output port and a feature, and the value the component fixes for that feature, on any input. A rule may require
a condition on the query (its query features): an unkeyed instance, for example. The dev labeling marks a postcondition that a rule fixes to the
same value as entailed by construction, and tests it on no variant.
"""

# (component, port, feature, value, condition on the query features or None)
RULES = [
    ('BoundingBox', 'box', 'B distinct', 1, lambda q: not q.get('keyed')),
    ('BoundingBox', 'box', 'rows', 1, lambda q: not q.get('keyed')),
    ('Singleton', 'value', 'rows', 1, lambda q: not q.get('keyed')),
    ('Order', 'rank', 'R min', 0, None),
    ('Order', 'dual_rank', 'R min', 0, None),
    ('Order', 'maximal', 'empty', False, None),
    ('Order', 'minimal', 'empty', False, None),
    ('Ray', 'ray', 'K min', 0, None),
    ('Frame', 'cell', 'P components', 1, None),
    ('Frame', 'cell', 'P outside is one region', True, None),
]


def by_construction(query, port, feature, value):
    """True where a rule fixes `feature` of the instance output `port` of a query of these query features to `value`."""
    comp = query.get('component')
    for c, p, f, v, cond in RULES:
        if c == comp and p == port and f == feature and v == value and (cond is None or cond(query)):
            return True
    return False
