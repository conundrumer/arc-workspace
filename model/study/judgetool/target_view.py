"""Read-only pages of comparison targets, never clause inputs."""
import re
from checks import counts_table
from catalog import acquire
from evaluator import sha
from tables import Incomplete


def view_target(ev,record,target,target_id,*,limit=30,offset=0,assignment=None,example=None):
    adapter=target['adapter'];ntrain=target['ntrain'];ntest=target['ntest']
    references=adapter['target_catalog']['targets']
    selected=[r for r in references if r['target_id']==target_id]
    if len(selected)!=1:raise ValueError('target_id is not a unique target in this document')
    reference=selected[0]
    if offset<0 or limit<0:raise ValueError('row offset and limit must be nonnegative')
    values=reference.get('kept_assignments',record['evaluation']['kept_assignments'])
    if assignment is not None and not 0<=assignment<len(values):
        raise ValueError('kept assignment index is outside this target case')
    example_index=None
    if example is not None:
        if not re.fullmatch(r'train[1-9][0-9]*',example):
            raise ValueError('example must name a train input, e.g. train1; test rows are withheld')
        example_index=int(example[5:])-1
        if example_index>=ntrain:raise ValueError('train example index is outside this task')
    grouped,fields,receipt=acquire(ev,record,adapter,reference,ntrain,ntest)
    # The document's exact physical schema supplies the display names. It does
    # not supply values. Other-case equality continues to ignore these names.
    display=reference.get('fields') or grouped.get('catalog_reference',{}).get('display_fields') or fields
    if [f['type'] for f in display]!=[f['type'] for f in fields]:
        raise Incomplete('target display schema differs from fresh replay schema')
    columns=[(f.get('field_name') or f.get('name') or str(i+1),f['type']) for i,f in enumerate(display)]
    required={k for k in grouped['required'] if k[1]==1
              and (assignment is None or k[0]==assignment) and (example_index is None or k[2]==example_index)}
    rows={k:v for k,v in grouped['groups'].items() if k in required}
    missing=sorted(required-rows.keys())
    base=dict(schema='judgetool-target-view-v1',graded=False,comparison_only=True,target_id=target_id,
        case=reference['case'],source_name=(reference.get('definition') or {}).get('display_name') or
            grouped.get('catalog_reference',{}).get('target_id',target_id).split(': ',1)[-1],
        source_sha256=sha(record),adapter_sha256=sha(adapter),target_receipt=receipt,
        selection=dict(assignment=assignment,example=example,offset=offset,limit=limit))
    if missing:
        return dict(base,engine='incomplete',reason='gold replay has no compatible kept entry for selected train inputs',missing_contexts=missing)
    return dict(base,engine='ran',table=counts_table(rows,columns,limit,offset=offset),
                reason='Comparison-only target; viewing it does not make it available to clauses.')
