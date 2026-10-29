"""Lazy bounded clause planner; library semantics remain in the shared engine.

Grounded library atoms/computations come from the shared registry-site adapter.
This finite plan is a searched subset, NEVER a proof of the full recovery space.
"""
import itertools


def candidates(adapter, plan):
    if plan.get('schema') != 'mech-lib-plan-v1':
        raise ValueError('expected mech-lib-plan-v1')
    # Exact explicit clauses support recovered historical witnesses and larger
    # union clauses; every one still passes the shared evaluator's provenance.
    for candidate in plan.get('candidates', []):
        if set(candidate) - {'clause', 'columns', 'target', 'role'}:
            raise ValueError('unexpected candidate fields')
        yield dict(candidate)
    if not plan.get('generate', True):
        return
    binding = adapter['input']['binding']
    source = binding['projected_schema']
    fields = adapter['comparison_target']['binding']['projected_schema']
    x = binding['callable_template']
    restrictions = plan.get('restriction_atoms', [])
    computations = plan.get('computations', [])
    depth = plan.get('max_restrictions', 2)
    if depth < 0 or depth > len(restrictions):
        depth = min(max(depth, 0), len(restrictions))
    if not all(isinstance(a, str) and a.strip() for a in restrictions):
        raise ValueError('restriction_atoms must be grounded clause syntax')
    def kind(t):
        return 'Box' if t in ('Position', 'Box') else t
    # Let the shared comparator search target column bindings once per replay;
    # rerunning the identical native program per permutation wastes most work.
    # Repeated explicit output columns remain available in supplied candidates.
    direct = iter([dict(atoms=[], columns=None)])
    for base in itertools.chain(direct, computations):
        if not isinstance(base.get('atoms'), list) or (base.get('columns') is not None and not isinstance(base.get('columns'), list)):
            raise ValueError('computation needs grounded atoms and ordered output columns')
        if base['columns'] is not None and len(base['columns']) != len(fields):
            raise ValueError('computation output arity differs from target')
        for n in range(depth+1):
            for selectors in itertools.combinations(restrictions, n):
                body = ' '.join([x] + base['atoms'] + list(selectors))
                yield dict(clause='(RULE &fix ' + body + ')', columns=base['columns'], role='recovery')
