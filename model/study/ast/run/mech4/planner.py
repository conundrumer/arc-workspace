"""Bounded composition of the OWNER'S registry-site syntax generator.

No type/grounding or library evaluator is duplicated here. One computation
plus at most one extra grounded selector is the initial finite search layer.
"""
from common import digest


def atomic(L,info,adapter,*,maximum,per_predicate,per_mode,bindings=()):
    from registry_plan import registry_atoms,available_atoms
    from collections import deque
    x=L.parse(adapter['input']['binding']['callable_template'])
    count=0
    streams=deque([iter(registry_atoms(L,info,adapter,per_predicate=per_predicate,per_mode=per_mode)),
                   iter(available_atoms(L,bindings,adapter,per_source=per_predicate))])
    while streams:
        stream=streams.popleft()
        try:planned=next(stream)
        except StopIteration:continue
        streams.append(stream)
        if planned['status']!='candidate':
            yield dict(kind='unsupported',registry=planned)
            continue
        body=[planned['atom']]
        candidate=dict(kind=planned['kind'],atoms=body,computed_fields=planned['computed_fields'],
            registry=[{k:planned[k] for k in ('entry_id','entry_sha256','mode')}],
            source_kind=planned.get('source_kind','library'),
            clause=L.unparse(['RULE','&fix',x]+body))
        candidate['candidate_id']=digest(candidate)
        yield candidate;count+=1
        if count>=maximum:return


def combined(L,adapter,useful,*,maximum):
    """Native conjunctions, never intersections/unions of decoded model masks."""
    x=L.parse(adapter['input']['binding']['callable_template'])
    selectors=[c for c in useful if not c['computed_fields']]
    computations=[c for c in useful if c['computed_fields']]
    seen=set();count=0
    for i,left in enumerate(selectors):
        for right in selectors[i+1:]+computations:
            # Restrict X before computing; the native prefix proof then checks
            # one row for every X row that reaches the computation.
            body=left['atoms']+right['atoms']
            candidate=dict(kind='conjunction',atoms=body,computed_fields=right['computed_fields'],
                source_kind='mixed',
                registry=left['registry']+right['registry'],clause=L.unparse(['RULE','&fix',x]+body))
            key=digest(candidate)
            if key in seen:continue
            seen.add(key);candidate['candidate_id']=key
            yield candidate;count+=1
            if count>=maximum:return


def fields(adapter,candidate):
    return list(adapter['input']['binding']['projected_schema'])+candidate['computed_fields']
