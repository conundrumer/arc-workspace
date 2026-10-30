"""Native conditional OUT rows/grids and their original projection identities."""
from native import require
from assignments import term_cells


def audit_out(continuation,result):
    if not continuation or not continuation['detailed_rows']:return None
    report=continuation['report'];binding=report.get('out_bindings')
    require(binding and binding['schema']=='arclog-study-out-bindings-v1' and binding['complete'],'OUT native projection incomplete')
    nodes={tuple(n['path']):n for n in result['structured']['mutant']['nodes']}
    require(tuple(binding['body_path']) in nodes,'OUT body definition missing')
    columns=sorted(binding['columns'],key=lambda c:c['out_column'])
    require([c['role'] for c in columns]==['position','color'] and columns[0]['type'] in ('Position','Box') and columns[1]['type']=='Color','native OUT column contract differs')
    for column in columns:
        require(column['occurrences'],'OUT column has no original AST site')
        for occurrence in column['occurrences']:require(tuple(occurrence['path']) in nodes,'OUT projection occurrence missing from original AST')
    tables=[];empty_examples=[];complete=True
    for choice in report['choices']:
        if choice['out']['status']!='complete':
            complete=False
            continue
        for example in choice['out']['train']:
            from render2.execution import validate_train_example
            validate_train_example(example,context='native detailed OUT train example')
            index=example['example'];expected=result['task_data']['train'][index]['output']
            require(example['expected_grid']==expected,'OUT expected grid differs from task train output')
            if not example['models']:
                empty_examples.append(dict(choice=choice['assignment']+1,example_index=index,example='train'+str(index+1)))
            for model_no,model in enumerate(example['models']):
                diagnostic=dict(status=model['status'],differing_cells=model.get('differing_cells'))
                if model['status']!='complete':
                    complete=False
                    continue
                if model.get('value_kind')=='undefined':
                    require(model['equals'] is False and model['grid_defined'] is False,'undefined native OUT claims a grid')
                    tables.append(dict(**diagnostic,choice=choice['assignment']+1,example='train'+str(index+1),example_kind=1,example_index=index,model=model_no,rows=None,grid=None,equals=False,reason=model['reason'],value_kind='undefined'))
                    continue
                typed=model['rows'];packed=model['packed_rows']
                require(len(typed)==len(packed),'OUT typed/packed row count differs')
                require(len({tuple(row) for row in packed})==len(packed),'OUT native projection was not deduplicated')
                rows=[]
                for row,raw in zip(typed,packed):
                    require(len(row)==len(raw)==2,'OUT row width differs from binding')
                    cells=[]
                    for term,value,column in zip(row,raw,columns):
                        require(term['type']==('Position' if column['role']=='position' else 'Color') and term['encoding_u32']==value%(2**32),'OUT typed cell differs from native packed cell')
                        cell=dict(value=term_cells(term))
                        if column['role']=='position':
                            if 'extent_status' in term:
                                cell['extent_status']=term['extent_status']
                                require(term['extent_status'] in ('resolved','unresolved'),'invalid native OUT cell extent status')
                                extent=term.get('extent')
                                require((term['extent_status']=='resolved' and extent and len(extent)==2 and min(extent)>0) or (term['extent_status']=='unresolved' and extent is None),'OUT extent/status conflict')
                                if extent is not None:cell['extent']=extent
                            else:
                                grid=model['grid']
                                cell['extent_status']='resolved' if model['grid_defined'] else 'unresolved'
                                cell['extent']=[len(grid),len(grid[0])] if model['grid_defined'] else [-1,-1]
                        cells.append(cell)
                    rows.append(cells)
                grid=model['grid']
                require(model['grid_defined']==(grid is not None),'native OUT grid-defined flag differs')
                if grid is not None:
                    require(grid and grid[0] and all(len(row)==len(grid[0]) for row in grid),'native OUT grid is not rectangular')
                    h,w=len(grid),len(grid[0]);actual={}
                    for row in rows:
                        t,b,l,r=row[0]['value'];color=row[1]['value'][0]
                        require(0<=t<h and 0<=l<w and h-t-b==1 and w-l-r==1,'OUT cell does not lie in native OUT grid frame')
                        require((t,l) not in actual or actual[t,l]==color,'native OUT grid has conflicting colors')
                        actual[t,l]=color
                    require(len(actual)==h*w and all(actual[i,j]==grid[i][j] for i in range(h) for j in range(w)),'native OUT rows/grid disagree')
                    require(model['equals']==(grid==expected),'native OUT equality differs from supplied grid')
                tables.append(dict(**diagnostic,choice=choice['assignment']+1,example='train'+str(index+1),example_kind=1,example_index=index,
                                   model=model_no,rows=rows,grid=grid,equals=model['equals'],reason=model.get('reason'),value_kind=model.get('value_kind')))
    names={c['role']:nodes[tuple(c['occurrences'][0]['path'])]['sexp'] for c in columns}
    return dict(binding=binding,names=names,entries=tables,empty_examples=empty_examples,status='complete' if complete else 'pending')


def compare_fits(current,stored):
    """Authenticate native FITS metadata only where both reports supplied it."""
    from render2.execution import example_fit
    a,b=example_fit(current),example_fit(stored)
    if a is None or b is None:return
    require(a==b,'historical/live accepted-set FITS differs')
    for key in ('fit_comparison','distinct_output_grids','output_set_defined','accepted_candidate_sizes'):
        if key in current and key in stored:
            require(current[key]==stored[key],'historical/live accepted-set '+key+' differs')


def audit_fits(result):
    """Keep producer and guarded native replay judgements explicitly separate."""
    from render2.execution import validate_train_example,example_fit
    observed=(result.get('structured',{}).get('components') or {}).get('body_observation',{}).get('report',{})
    live={o['assignment']:o for o in observed.get('outputs',[])}
    entries=[];missing=0
    for output in result['outputs']:
        number=output['assignment'];current=live.get(number,{})
        for side,stored in (('gold',output['gold_train']),('mutant',output['mutant']['train'])):
            examples=current.get('gold_train') if side=='gold' else current.get('mutant',{}).get('train')
            if examples is not None:require(len(examples)==len(stored),'native FITS train coverage differs')
            for i,producer in enumerate(stored):
                validate_train_example(producer,context=f'producer {side} train{i+1}')
                original=example_fit(producer)
                if side=='gold' and original is not None:require(original,'kept gold example has native FITS false')
                chosen=producer;origin='historical producer'
                if examples is not None:
                    fresh=examples[i];validate_train_example(fresh,context=f'native replay {side} train{i+1}')
                    require(fresh['example']==producer['example'],'native FITS example identity differs')
                    compare_fits(fresh,producer)
                    if example_fit(fresh) is not None:
                        chosen=fresh;origin='exact-kept native replay'
                        if side=='gold':require(example_fit(fresh),'native replay kept gold example has FITS false')
                if example_fit(chosen) is None:missing+=1
                entries.append(dict(choice=number+1,side=side,example=i,origin=origin,evidence=chosen))
    result['fits_evidence']=entries
    if missing:result['pending'].append('Native accepted-set FITS unavailable for '+str(missing)+' train observations')
