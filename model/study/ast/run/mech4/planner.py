"""Bounded composition of the OWNER'S registry-site syntax generator.

No type/grounding or library evaluator is duplicated here. One computation
plus at most one extra grounded selector is the initial finite search layer.
"""
from common import digest


def atomic(L,info,adapter,*,maximum,per_predicate,per_mode,bindings=()):
    from registry_plan import registry_atoms,available_atoms,unsupported_named_sites
    from collections import deque
    x=L.parse(adapter['input']['binding']['callable_template'])
    bad=unsupported_named_sites(x)
    if bad:
        yield dict(kind='unsupported',registry=dict(status='unsupported',
            reason='X callable template has unsupported named sites',native_sites=bad))
        return
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
    from registry_plan import unsupported_named_sites
    x=L.parse(adapter['input']['binding']['callable_template'])
    if unsupported_named_sites(x):return
    selectors=[c for c in useful if not c['computed_fields']]
    computations=[c for c in useful if c['computed_fields']]
    seen=set();count=0
    from surface import tokens
    def make(left,right):
        right_atoms=right['atoms']
        if not right['computed_fields']:
            left_made={t[1:] for t in tokens(left['atoms']) if t.startswith('*')}
            right_made={t[1:] for t in tokens(right_atoms) if t.startswith('*')}
            collisions=left_made & right_made
            if collisions:
                prefix='Mech4Join'+digest((left['candidate_id'],right['candidate_id']))[:12]
                occupied={t.lstrip('*^') for t in tokens(left['atoms']+right_atoms)}
                renamed={}
                for i,name in enumerate(sorted(collisions)):
                    fresh=prefix+'C'+str(i)
                    while fresh in occupied:fresh+='Q'
                    occupied.add(fresh);renamed[name]=fresh
                def rename(label):
                    marker=label[0] if label.startswith(('*','^')) else ''
                    return marker+renamed.get(label.lstrip('*^'),label.lstrip('*^'))
                right_atoms=[L.rename_labels(atom,rename) for atom in right_atoms]
        body=left['atoms']+right_atoms
        candidate=dict(kind='conjunction',atoms=body,computed_fields=right['computed_fields'],
            source_kind='mixed',registry=left['registry']+right['registry'],
            clause=L.unparse(['RULE','&fix',x]+body))
        candidate['candidate_id']=digest(candidate)
        return candidate
    # Try computed outputs with restrictions before spending the bound on
    # additional selection-only combinations.
    pairs=((left,right) for left in selectors for right in computations)
    secondary=((left,right) for i,left in enumerate(selectors) for right in selectors[i+1:]
               if left.get('source_kind')!='available' or right.get('source_kind')!='available')
    import itertools
    for left,right in itertools.chain(pairs,secondary):
        candidate=make(left,right);key=candidate['candidate_id']
        if key in seen:continue
        seen.add(key);yield candidate;count+=1
        if count>=maximum:return


def fields(adapter,candidate):
    return list(adapter['input']['binding']['projected_schema'])+candidate['computed_fields']


def base_source_ids(base,bindings):
    """Identify exact available sources already inventoried by the base pass.

    Missing/ambiguous metadata is not evidence; leave those proposals active.
    This is scheduling only and never an exhaustion or negative proof.
    """
    from judge3.catalog import matches
    contexts=base.get('per_assignment',[])
    if not contexts or base.get('available_incomplete'):return set()
    prior=[c.get('available_metadata',[]) for c in contexts]
    if not all(prior):return set()
    result=set()
    for binding in bindings:
        selector=binding['definition'].get('native_selector')
        if not selector or not set(selector)&{'form','point','relation','fact'}:continue
        def present(items):
            count=0
            for item in items:
                identity=item.get('identity',{})
                if not all(k in identity for k in selector if k in ('form','point','relation','fact')):continue
                table={k:[v] for k,v in identity.items()}
                if matches(table,0,selector):count+=1
            return count==1
        if all(present(items) for items in prior):result.add(digest(binding['definition']))
    return result
