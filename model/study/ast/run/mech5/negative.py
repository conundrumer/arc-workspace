"""Read-time all-target TRAIN row-absence proof from authenticated facts.

This is the settled mechanical lossy rule, not search-space exhaustion. Source
and child-reference authentication belongs to read_targets.load_targets.
"""
from collections import OrderedDict

_CATALOG=OrderedDict()


def case_catalog(reference,resolve):
    """Cache small catalog metadata, never observed native rows."""
    key=tuple(reference.get(k) for k in ('database','kind','key','result_sha256'))
    if key not in _CATALOG:
        case=resolve(reference)
        _CATALOG[key]=dict(task=case['task'],case=case['case'],
            tables=frozenset(t['table_id'] for t in case.get('tables',[])),
            ran=case.get('receipt',{}).get('engine')=='ran',
            replay_gaps=any(g.get('kind')=='replay' for g in case.get('gaps',[])))
        while len(_CATALOG)>512:_CATALOG.popitem(last=False)
    _CATALOG.move_to_end(key)
    return _CATALOG[key]


def derive_support(facts,base,observations,resolve):
    """Return catalog coverage and three-valued all-target containment failure.

    The completed pair journal is written after enumeration/comparison of every
    selected target. Missing case/point/scope or failed enumeration is recorded
    as a gap; interruption before that point writes no completed pair. Check
    these terminal facts, G identity and every other-case native table as well.
    Same-case eligibility is the producer's canonical gap-free scope result;
    no table-index/ordinal cutoff or second graph policy is inferred here.
    """
    gaps=[]
    refs=facts.get('case_refs',[])
    cases=[case_catalog(ref,resolve) for ref in refs]
    if not cases:gaps.append('no case observations')
    if facts.get('case_failure_refs'):gaps.append('case acquisition failed')
    if isinstance(facts.get('stopped'),dict):gaps.append('pair stopped before completion')
    # Comparison and search unknowns do not imply an incomplete enumeration.
    # A TRAIN mismatch is sufficient for a negative; TEST is required for
    # positive equalities/recoveries, not for disproving TRAIN containment.
    for gap in facts.get('gaps',[]):
        if gap.get('stage') not in ('comparison','other_target_search','search'):
            gaps.append(gap.get('reason','incomplete target enumeration'))
    names=[c['case'] for c in cases]
    if len(set(names))!=len(names):gaps.append('duplicate case observations')
    if any(c['task']!=base['task'] or not c['ran'] or c['replay_gaps'] for c in cases):
        gaps.append('case replay unavailable')
    by_case={c['case']:c for c in cases}
    if base['case'] not in by_case:gaps.append('own case observation missing')
    point=[];seen_other=set()
    statuses=[]
    for target,comparison in observations:
        role=target.get('role');case=target.get('case');table=target.get('table_id')
        statuses.append(comparison.get('containment',{}).get('status','unknown'))
        if role=='point':
            point.append(target)
            if case!=base['case'] or target.get('body_path')!=base['point']:
                gaps.append('point comparison identity differs')
        elif role in ('later','other_case'):
            if case not in by_case or table not in by_case[case]['tables']:
                gaps.append('target absent from its case observation')
            if role=='other_case':
                if case==base['case']:gaps.append('other-case target has own-case identity')
                seen_other.add((case,table))
            elif case!=base['case']:gaps.append('later target has another case identity')
        else:gaps.append('comparison has no supported target role')
    if len(point)!=1:gaps.append('exact G comparison missing or duplicated')
    expected_other={(c['case'],t) for c in cases if c['case']!=base['case'] for t in c['tables']}
    if seen_other!=expected_other:gaps.append('not every other-case native table was compared')
    catalog_complete=not gaps
    contains='contains' in statuses
    determined=bool(statuses) and all(s in ('contains','mismatch') for s in statuses)
    all_lossy=(False if contains else True if catalog_complete and determined else None)
    support=dict(complete=catalog_complete and determined,all_targets_lossy=all_lossy,
        any_target_contains=contains,target_count=len(statuses))
    return dict(complete=catalog_complete,gaps=list(dict.fromkeys(gaps))),support
