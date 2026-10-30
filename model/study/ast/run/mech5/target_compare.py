"""Shared TRAIN containment and TRAIN+TEST equality observations."""


def train_only(grouped):
    return dict(grouped,groups={k:v for k,v in grouped['groups'].items() if k[1]==1},
        required={k for k in grouped['required'] if k[1]==1},
        missing=[k for k in grouped['missing'] if k[1]==1])


def coverage(grouped):
    required=set(grouped.get('required',()))
    return (bool(required) and not grouped.get('missing') and set(grouped['groups'])==required
            and all(bool(family) for family in grouped['groups'].values()))


def compare(source,fields,target,*,seconds=1,indexes=None):
    from case_collector import compare_target
    grouped,target_fields,reference,receipt=target
    columns=[(f.get('field_name',f.get('name')),f['type']) for f in fields]
    eq_block=indexes.obstruction(source,columns,target,relation='equal') if indexes else None
    contains_block=indexes.obstruction(source,columns,target,relation='contains') if indexes else None
    equality=(dict(status='unknown',reason='stored X lacks required kept train/test entries')
              if not coverage(source) or not coverage(grouped) else
              dict(status='mismatch',reason=eq_block) if eq_block else compare_target(source['groups'],columns,grouped,target_fields,reference,seconds=seconds))
    training=train_only(grouped);xs=train_only(source)
    containment=(dict(status='unknown',reason='stored X lacks required kept train entries')
                 if not coverage(xs) or not coverage(training) else dict(status='mismatch',reason=contains_block) if contains_block else compare_target(xs['groups'],columns,training,target_fields,reference,
                                                      relation='contains',seconds=seconds))
    return dict(equality=equality,containment=containment,
                target_reference=reference,target_receipt=receipt)
