"""Shared comparisons and branch-local diagnostics; no Reject certificates."""
from .target_search import axes


def train_only(grouped):
    return dict(grouped,groups={k:v for k,v in grouped['groups'].items() if k[1]==1},
        required={k for k in grouped['required'] if k[1]==1},
        missing=[k for k in grouped['missing'] if k[1]==1])


def row_obstruction(source,target,reference):
    """Diagnostic for one at-most-one-row branch, never settled-space support.

    Several needed X-reading union branches can multiply row counts. Computed
    columns also make raw containment misses insufficient negative evidence.
    """
    try:
        for x,g in axes(source,target,reference):
            xf=source['groups'][x];gf=target['groups'][g]
            if not xf or not gf:return dict(branch_local_only=True,impossible=None,reason='empty model-family evidence')
            xs=sorted(map(len,xf));gs=sorted(map(len,gf))
            if max(gs)>max(xs) or min(xs)<min(gs):
                return dict(branch_local_only=True,impossible=True,source_context=x,target_context=g,
                    X_model_row_counts=xs,target_model_row_counts=gs,
                    reason='at-most-one-row-per-X transform cannot meet target model row counts')
        return dict(branch_local_only=True,impossible=False,reason='row count does not rule out computed columns')
    except (ValueError,KeyError) as error:return dict(branch_local_only=True,impossible=None,reason=str(error))


def coverage(grouped):
    required=set(grouped.get('required',()))
    return (bool(required) and not grouped.get('missing') and set(grouped['groups'])==required
            and all(bool(family) for family in grouped['groups'].values()))


def compare(source,fields,target,*,seconds=1):
    from case_collector import compare_target
    grouped,target_fields,reference,receipt=target
    columns=[(f.get('field_name',f.get('name')),f['type']) for f in fields]
    equality=(dict(status='unknown',reason='stored X lacks required kept train/test entries')
              if not coverage(source) or not coverage(grouped) else
              compare_target(source['groups'],columns,grouped,target_fields,reference,seconds=seconds))
    training=train_only(grouped);xs=train_only(source)
    containment=(dict(status='unknown',reason='stored X lacks required kept train entries')
                 if not coverage(xs) or not coverage(training) else compare_target(xs['groups'],columns,training,target_fields,reference,
                                                      relation='contains',seconds=seconds))
    obstruction=row_obstruction(xs,training,reference)
    return dict(equality=equality,containment=containment,row_obstruction=obstruction,
                target_reference=reference,target_receipt=receipt)
