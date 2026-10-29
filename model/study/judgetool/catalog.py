"""Target inventory consumer; source identity and scope belong to judge3.

All values are acquired through the shared native reader. Other-case columns
are matched by type, and that case's own saved DET values are used.
"""
from tables import Incomplete,compare


def entries(adapter):
    catalog=adapter.get('target_catalog',{})
    if catalog.get('schema') not in (None,'judge-target-catalog-v1'):
        raise Incomplete('unsupported target catalog schema')
    return catalog.get('targets',[]),catalog.get('complete') is True,catalog.get('gaps',[])


def acquire(ev,record,adapter,reference,ntrain,ntest):
    """Acquire a target from fresh replay; selectors are identity only.

    Pass the shared ReplayEvaluator, not a saved TargetStore. Prefer iterating
    live_targets.acquire directly: omitted declared aliases are not gold tables.
    """
    if not hasattr(ev,'replay_program'):
        raise TypeError('target acquisition requires shared ReplayEvaluator, not saved snapshots')
    if reference.get('role')=='point':
        from checks import observe_gold
        binding=reference.get('binding',adapter['comparison_target']['binding'])
        groups,receipt=observe_gold(ev,record,adapter,binding,ntrain,ntest)
        return groups,binding['projected_schema'],receipt
    import live_targets
    targets,gaps,receipts,available=live_targets.acquire(ev,record,adapter,ntrain,ntest,only_case=reference['case'])
    selector=reference.get('native_selector',{})
    for grouped,fields,ref,receipt in targets:
        if ref['case']==reference['case'] and all(str(ref['native_selector'].get(k))==str(v)
              for k,v in selector.items() if k in ('form','point','relation','fact')):
            return grouped,fields,receipt
    stopped=[g for g in gaps if g.get('case')==reference['case']]
    if stopped:raise Incomplete('gold case replay stopped: '+str(stopped[0].get('reason')))
    raise Incomplete('gold replay returned no table entry at the requested target selector')


def equality(candidate,columns,grouped,fields,reference,explicit=None):
    if grouped.get('missing'):
        return compare(candidate,columns,{},fields,explicit=explicit)
    if reference.get('role')!='other_case':
        return compare(candidate,columns,grouped['groups'],fields,explicit=explicit)
    # Kept DET ordinals are local to a case. Never zip them across cases.
    # Check each target kept context against every candidate kept context.
    # A single fixed column map must work for the whole Cartesian comparison.
    target={};expanded={}
    assignments=sorted({k[0] for k in candidate})
    target_assignments=sorted({k[0] for k in grouped['groups']})
    for i,a in enumerate(assignments):
        for j,b in enumerate(target_assignments):
            axis=i*len(target_assignments)+j
            for (ga,kind,index),family in grouped['groups'].items():
                if ga!=b:continue
                key=(axis,kind,index);target[key]=family
                if (a,kind,index) in candidate:expanded[key]=candidate[(a,kind,index)]
    result=compare(expanded,columns,target,fields,explicit=explicit)
    result['context_mapping']='all candidate kept contexts x all target-case kept contexts; no ordinal alignment'
    return result
