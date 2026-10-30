"""Narrow typed support certificates. Never claim search exhaustion or Reject."""
from run import digest


def no_x_rows(source,targets,*,complete,inputs,case_refs,ntrain,ntest,assignment_count):
    """Global absence of X rows rules out X-sourced recovery, including unions.

    Every target needs one explicit nonempty model witness; target families
    stay sets. The reducer owns the empty filter class and fitting-program policy.
    """
    unavailable=dict(schema='mech-no-x-rows-v1',no_recovery=None,
        reason='requires complete globally empty X and nonempty witness for every target')
    required=set(source.get('required',()))
    expected={(a,k,i) for a in range(assignment_count) for k,n in ((1,ntrain),(2,ntest)) for i in range(n)}
    if (not complete or not targets or not required or required!=expected or source.get('missing')
            or set(source['groups'])!=required):return unavailable
    if not all(family and all(not rows for rows in family) for family in source['groups'].values()):
        return unavailable
    witnesses=[]
    for grouped,fields,ref,receipt in targets:
        if (grouped.get('missing') or not grouped.get('required')
                or set(grouped['groups'])!=set(grouped['required'])
                or not all(grouped['groups'].values())):return unavailable
        witness=None
        for context in sorted(grouped['groups']):
            models=sorted(grouped['groups'][context],key=lambda rows:repr(sorted(rows)))
            for rows in models:
                if rows:
                    # Digest native decoded rowsets only as receipt identity;
                    # emptiness itself uses actual model rows, no equality hash.
                    witness=dict(context=list(context),row_count=len(rows),
                        model_sha256=digest(sorted(rows,key=repr)))
                    break
            if witness:break
        if witness is None:return unavailable
        witnesses.append(dict(target_reference=ref,target_receipt=receipt,nonempty=witness))
    return dict(schema='mech-no-x-rows-v1',no_recovery=True,complete=True,inputs=inputs,case_refs=case_refs,
        ntrain=ntrain,ntest=ntest,assignment_count=assignment_count,
        required_contexts=[list(k) for k in sorted(required)],all_X_families_present=True,
        family_counts=[dict(context=list(k),count=len(source['groups'][k])) for k in sorted(required)],
        every_X_rowset_empty=True,target_catalog_complete=True,targets=witnesses,
        scope='globally empty X; reducer owns empty filter class; no search-exhaustion/Reject claim')
