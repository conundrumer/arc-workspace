"""Small judge-facing view; full receipts stay in stored records."""
import json


def clause(result):
    view={}
    if 'kind' in result:view['kind']=result['kind']
    if result.get('comparison_only'):
        view.update(target_id=result['target_id'],case=result['case'],source_name=result['source_name'],comparison_only=True)
        view['selection']=result['selection']
    view['outcome']=result.get('outcome',result.get('engine','unknown'))
    reason=result.get('reason')
    if not reason and result.get('verified'):
        reason='Matches '+result.get('target_id','G')+' on train and test.'
        if result.get('provenance',{}).get('status')=='single_row_lib':reason+=' Lib gives exactly one row per X row.'
    if not reason and result.get('continuation_passed'):reason='Nonempty on every train input; differs from X, available tables and targets.'
    if reason:view['reason']=reason
    if result.get('graded') is False:view['graded']=False
    if result.get('table'):
        table=result['table'];groups=[]
        for g in table['groups']:
            groups.append(dict(example=g['example'],assignment=g['assignment'],model=g['model'],
                row_count=g['row_count'],rows=g['rows'],omitted_rows=g['omitted_rows']))
        view['table']=dict(columns=[name+':'+ty for name,ty in table['columns']],groups=groups,
                           total_rows=table['total_rows'],omitted_rows=table['omitted_rows'])
    groups={}
    for item in result.get('comparisons',[]):
        c=item['comparison'];name=item['target_id']
        if c['status']=='equal':detail=dict(result='equal on train and test')
        elif c.get('differences'):
            differences=[]
            for d in c['differences']:
                value=dict(d)
                if all(x['assignment']==0 for x in c['differences']):value.pop('assignment')
                for field in ('candidate_rows','target_rows'):
                    if field in value and len(value[field])==1:value[field]=value[field][0]
                differences.append(value)
            detail=dict(differs=differences)
        else:
            why=c.get('reason','rows differ')
            if c.get('target_columns') is not None:why+=f" ({c['candidate_columns']} vs {c['target_columns']} columns)"
            detail=dict(difference=why)
        key=json.dumps(detail,sort_keys=True)
        if key not in groups:groups[key]=dict(targets=[],**detail)
        groups[key]['targets'].append(name)
    targets=list(groups.values())
    if targets:view['targets']=targets
    return view


def render(result):
    if 'outcomes' in result:
        value=dict(outcomes=[clause(o) for o in result['outcomes']],no_clause_found=result['no_clause_found'])
    else:value=clause(result)
    # Compact rows and lists; no hashes, native ids, paths or receipts.
    return json.dumps(value,ensure_ascii=False,separators=(',', ':'))+'\n'
