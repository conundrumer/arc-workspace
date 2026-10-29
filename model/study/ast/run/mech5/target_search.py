"""Propose selectors for OTHER targets; verify through the shared evaluator.

This is the existing nonlib grammar, not a second library implementation. A
finite miss, an unrenderable proposal, or a stopped search never covers the
settled library/union space. Main G uses existing witnesses, never a new search.
"""
from run import digest


def axes(source,target,reference,kind=1):
    """One transform across all kept contexts; never zip cases' ordinals."""
    if any(k[1]==kind for k in source.get('missing',[])+target.get('missing',[])):
        raise ValueError('source/target kept context coverage incomplete')
    xs=source['groups'];gs=target['groups'];other=reference.get('role')=='other_case'
    if not other:
        wanted=sorted(k for k in gs if k[1]==kind)
        if not wanted or any(k not in xs for k in wanted):raise ValueError('train input/context missing')
        return [(k,k) for k in wanted]
    assignments=sorted({k[0] for k in xs});gold=sorted(k for k in gs if k[1]==kind)
    result=[((a,k,i),(b,k,i)) for a in assignments for b,k,i in gold]
    if not result or any(x not in xs for x,g in result):raise ValueError('cross-case train input/context missing')
    return result


def available_for_search(source,selection,adapter,train_axes):
    """Only deterministic, shared-resolver-admitted sources; no model unions."""
    allowed=adapter['availability']['definitions']
    result=[];bindings=[];omitted=[]
    for grouped,fields,reference,receipt in selection.get('available',[]):
        name=reference.get('source_name') or reference.get('display_name')
        if not name:
            name=reference.get('target_id','').split(': ',1)[-1]
        selector=reference.get('native_selector',{})
        matches=[d for d in allowed if all(str(selector.get(k))==str(v)
            for k,v in d['definition']['native_selector'].items() if k in ('form','point','relation','fact'))]
        definition=matches[0] if len(matches)==1 else None
        template=(definition or {}).get('table_receipt',{}).get('callable_atom')
        if not template:
            omitted.append(dict(source=name,reason='no shared callable relation binding'));continue
        values=[]
        for x,g in train_axes:
            family=grouped['groups'].get(x)
            if family is None or len(family)!=1:break
            values.append(next(iter(family)))
        else:
            result.append(dict(types=tuple(f['type'] for f in fields),rows=tuple(values)))
            bindings.append(dict(name=name,template=template,fields=fields,receipt=receipt))
            continue
        omitted.append(dict(source=name,reason='missing or nondeterministic compatible source model'))
    return result,bindings,omitted


def propose(source,fields,target,reference,selection,adapter,*,seconds=1,cache=None,counters=None):
    from algorithm import solve
    from tables import comparison_type
    gold,gold_fields,ref,receipt=target
    ordered=axes(source,gold,reference)
    available,bindings,omitted=available_for_search(source,selection,adapter,ordered)
    available=[dict(a,types=tuple(comparison_type(t) for t in a['types'])) for a in available]
    target_types=tuple(comparison_type(f['type']) for f in gold_fields)
    target_models=tuple(frozenset(gold['groups'][g]) for x,g in ordered)
    source_types=tuple(comparison_type(f['type']) for f in fields)
    source_models=tuple(frozenset(source['groups'][x]) for x,g in ordered)
    # Alias targets with exactly the same native row families ask the same
    # proposal question. Reuse only exact values/context ordering and available
    # inputs; candidate verification still checks the full cached target set.
    query=(target_types,target_models,source_types,source_models,
           tuple((a['types'],tuple(a['rows'])) for a in available),seconds)
    proof=cache.get(query) if cache is not None else None
    if proof is not None and counters is not None:counters['proposal_queries_reused']+=1
    if proof is None:
        if counters is not None:counters['proposal_queries_run']+=1
        proof=solve(target_types,target_models,source_types,source_models,available,seconds)
        if cache is not None:
            cache[query]=proof
            while len(cache)>64:cache.popitem(last=False)
    return proof,bindings,dict(axes=ordered,available_omitted=omitted,
        grammar='base nonlib selector grammar; not the settled library/union space',
        gold_receipt=receipt,source_to_target='one transform over all listed train contexts')


def clause(L,witness,binding,available,*,source_columns=None,output_columns=None):
    """Render canonical native sites, without inferring INIT/record layouts.

    source_columns maps old raw X indices to virtual public X indices when
    admitting an existing raw witness. Hidden witnesses cannot become sites.
    """
    mapping=source_columns
    def label(index):
        if mapping is not None:
            if index not in mapping:raise ValueError('witness reads a private/unmapped X column')
            index=mapping[index]
        return 'V'+str(index)
    output=output_columns if output_columns is not None else witness['projection']
    names=[label(i) for i in output]
    operators=dict(eq='=',ne='!=',lt='<',le='<=',gt='>',ge='>=')
    sequence=0
    def atom(a):
        nonlocal sequence
        kind=a['kind']
        if kind=='comparison':
            right=(label(a['right']) if 'right' in a else '0')
            if 'right' not in a and any(v!=0 for v in a['value']):raise ValueError('nonzero literal not admitted')
            return [[operators[a['op']],label(a['left']),right]]
        if kind=='false':
            if not binding['projected_schema']:raise ValueError('zero-width false constraint unavailable')
            return [['!=','V0','V0']]
        if kind not in ('semijoin','antijoin'):
            raise ValueError('canonical proposal has no admitted clause renderer for '+kind)
        definition=available[a['available']];joined={}
        for x,c in zip(a['columns'],a['source_columns']):
            name=label(x)
            if c in joined and joined[c]!=name:raise ValueError('repeated selector column needs additional equality')
            joined[c]=name
        if kind=='antijoin' and set(joined)!=set(range(len(definition['fields']))):
            raise ValueError('partial-site antijoin needs native-admitted existential binding')
        sequence+=1
        names_by_column={i:joined.get(i,'*Select'+str(sequence)+'_'+str(i)) for i in range(len(definition['fields']))}
        tree=L.parse(definition['template'])
        def rename(value):
            raw=value.lstrip('*^')
            if raw=='0':return value
            if not raw.startswith('V') or not raw[1:].isdigit():raise ValueError('callable selector column binding unavailable')
            return names_by_column[int(raw[1:])]
        tree=L.rename_labels(tree,rename)
        return [["NOT",tree]] if kind=='antijoin' else [tree]
    branches=[]
    for branch in witness.get('selection_any',[witness.get('selection',[])]):
        branches.append([part for item in branch for part in atom(item)])
    body=[L.parse(binding['callable_template'])]
    if len(branches)>1:body.append(['OR']+branches)
    elif branches:body.extend(branches[0])
    return dict(clause=L.unparse(['RULE','&fix']+body),columns=names,
                witness_sha256=digest(witness))

