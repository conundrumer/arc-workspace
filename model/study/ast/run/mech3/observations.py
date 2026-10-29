"""Read existing original-map families and compare per reader. No replay."""
if __package__:
    from .common import digest
else:
    from common import digest


def original_groups(record,side,snapshot,ntrain,ntest,legacy,selector):
    from tables import kept_groups
    evaluation=record['evaluation'];table=evaluation['table_indices'][side+'_kept']
    tables=snapshot['tables']
    if (not 0<=table<len(tables['form']) or any(str(tables[k][table])!=str(v)
            for k,v in selector.items() if k in ('form','point','relation','fact'))):
        raise ValueError('stored point table physical identity differs')
    observed=kept_groups(legacy,snapshot,table,record,ntrain,ntest)
    expected={(a,k,i) for a in range(len(evaluation['kept_assignments']))
              for k,n in ((1,ntrain),(2,ntest)) for i in range(n)}
    if observed['required']!=expected:raise ValueError('canonical grouped input/held axis differs')
    return dict(observed,receipt=dict(source='stored native snapshot',side=side,table=table,native_ref=record['native'][side],
        selector=selector,kept_sha256=digest(evaluation['kept_assignments']),matcher='tables.kept_groups',
        task_broadcast='canonical helper preserves model families and broadcasts kind 0'))


def compare_readers(projection,groups,legacy,*,seconds=1):
    from tables import compare,projected_rows
    differences=[];gaps=[]
    required=groups['gold']['required']
    if required!=groups['mutant']['required']:raise ValueError('source held/input axes differ')
    available=required & groups['gold']['groups'].keys() & groups['mutant']['groups'].keys()
    for reader in projection['readers']:
        fields=reader['fields'];columns=[('Read'+str(i),f['type']) for i,f in enumerate(fields)]
        gold_fields=[dict(field_name=name,type=ty) for name,ty in columns]
        projected={}
        for side in ('gold','mutant'):
            indices=[f[side] for f in fields]
            projected[side]={key:{frozenset(projected_rows(legacy,rows,indices)) for rows in groups[side]['groups'][key]}
                             for key in available}
        eq=compare(projected['mutant'],columns,projected['gold'],gold_fields,
                   explicit=[n for n,t in columns],seconds=seconds)
        # A mismatch on complete known model families is a positive witness to
        # a visible difference. Incomplete other inputs cannot undo it.
        if eq['status']=='mismatch':differences.append(dict(reader_path=reader['reader_path'],comparison=eq))
        if eq['status']=='unknown':gaps.append(dict(reader_path=reader['reader_path'],reason=eq.get('reason')))
    missing=sorted(required-available)
    if missing:gaps.append(dict(reason='stored reader projection lacks complete test/input coverage',contexts=missing))
    different=True if differences else False if not gaps and projection['complete'] else None
    return dict(schema='mech3-reader-difference-v1',complete=different is not None,read_difference=different,
                differences=differences,gaps=gaps,reader_count=len(projection['readers']),
                source_receipts={side:groups[side]['receipt'] for side in groups},
                policy='any per-reader joint tuple differs; extension needs every reader/input complete and equal')
