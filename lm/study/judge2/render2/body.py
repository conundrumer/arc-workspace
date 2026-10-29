"""Engine-identity column alignment, port projection and comparison auditing."""
from native import require


def project_entries(table,indices):
    """Project native cells without changing their assignment/example/model axes."""
    projected=[]
    for entry in table['entries']:
        rows=[];seen={}
        for row in entry['rows']:
            cells=[row[i] if i is not None else dict(value=[0]) for i in indices]
            key=tuple(tuple(c['value']) for c in cells)
            if key in seen:
                require(seen[key]==cells,'projected native value has conflicting frame evidence')
            else:
                seen[key]=cells;rows.append(cells)
        projected.append(dict(example=entry['example'],choice=entry['choice'],model=entry['model'],rows=rows))
    return projected


def enrich(result, structured):
    decoded = structured.get('kept_decoded')
    if decoded is not None:
        require(len(decoded)==len(result['kept_assignments']), 'decoded kept choices missing')
        for side,table in result['tables'].items():
            for entry in table['entries']:
                choice={d['source_name']:d for d in decoded[entry['choice']-1]}
                evidence=structured.get('choice_evidence')
                if evidence:
                    body=structured['body_views'][side]['body_path']
                    from assignments import body_dependencies
                    require(body_dependencies(evidence[side],body)=={d['relation'] for d in entry['assignment']},'native body DET read subset differs from compiled evidence')
                for det in entry['assignment']:
                    require(det['relation'] in choice, 'body DET absent from full choice')
                    expected=choice[det['relation']]
                    det['display_name']=expected['display_name']
                    det['columns']=[c['name'] for c in expected['schema']]
                    from assignments import check_held_schema
                    check_held_schema(det['relation'],det['types'],structured,side)
                    rows=[[v for cell in row for v in cell['value']] for row in expected['rows']]
                    require(sorted(rows)==sorted(det['rows']), 'native body DET differs from decoded full kept assignment')
        result['assignment_audit']='complete'
    views = structured.get('body_views', {})
    if set(views) != {'gold','mutant'}:
        return
    names = {};projection_kinds=[];projection_states=[]
    for side in ('gold','mutant'):
        table, view = result['tables'][side], views[side]
        require(table['form'] == view['native_table_selector']['form'], 'body AST/native form mismatch')
        columns = view['columns']
        from headers import bind_body_schema
        for key,name in bind_body_schema(table,view).items():names.setdefault(key,name)
        refresh_body_extents(table,view,side,structured,result['kept_assignments'])
        table['port'] = view['input_port']
        # Stored BodyViews may predate the engine's column-order fix. Join by
        # native source-label spelling; slot can mean an old LabelId or a new
        # body-column ordinal. The export supplies the original LabelId.
        native_index={c['ast_label_id']:c['index'] for c in table['schema']}
        require(len(native_index)==len(table['schema']),'body projection has duplicate native LabelIds')
        nodes={tuple(n['path']):n for n in structured[side]['nodes']}
        parent=nodes.get(tuple(view['body_path'][:-1]))
        if view['kind']=='INIT key':
            require(parent is not None and parent['kind']=='init_key','INIT key body lacks native key declaration')
            require(view['body_path'][:len(view['owner_path'])]==view['owner_path'],'INIT key body owner differs')
            labels=[c['label_id'] for c in parent['data']['columns']]
            require(len(labels)==len(set(labels)),'INIT key declaration has duplicate LabelIds')
            require(all(label in native_index for label in labels),'INIT key LabelId absent from native body')
            indices=[native_index[label] for label in labels]
            table['body_projection']=dict(kind='key',status='complete',columns=[table['schema'][i] for i in indices],
                                          record_width=len(indices),entries=project_entries(table,indices),declaration_path=parent['path'])
            projection_kinds.append('key');projection_states.append('complete')
            continue
        projection = [dict(p,body_column=native_index[p['label_id']] if p['body_column'] is not None else None) for p in view['input_port_projection']]
        if table['port'] is not None:
            for p in projection:
                if p['body_column'] is None:
                    require(p.get('inserted_constant',{}).get('kind')=='unit' and p['type']=='Unit','unknown inserted port constant')
                else:
                    require(0 <= p['body_column'] < len(columns), 'port projection column absent')
                    require(table['schema'][p['body_column']]['ast_label_id'] == p['label_id'], 'port projection label differs')
            key_columns=[i for label in view.get('group_key_label_ids',[]) for i,c in enumerate(table['schema']) if c['ast_label_id']==label]
            if len(key_columns)!=len(view.get('group_key_label_ids',[])):
                table['body_projection']=dict(kind='input_port',status='pending',reason='native key labels have no stored body-witness values')
                projection_kinds.append('input_port');projection_states.append('pending')
                continue
            projected=project_entries(table,key_columns+[p['body_column'] for p in projection])
            projection_schema=[]
            for p in projection:
                if p['body_column'] is not None:projection_schema.append(table['schema'][p['body_column']])
                else:
                    key='@unit:'+str(p['port_column']);names[key]='implicit Unit'
                    projection_schema.append(dict(type='Unit',frame='',source_label=key))
            table['body_projection'] = dict(kind='input_port',status='complete',columns=[table['schema'][i] for i in key_columns]+projection_schema,
                                           group_key_columns=len(key_columns),record_width=len(projection),entries=projected)
            projection_kinds.append('input_port');projection_states.append('complete')
        else:
            require(not view['kind'].startswith('INIT'),'native INIT body has no key or input-port identity')
            projection_kinds.append('body');projection_states.append('complete')
    require(all(names.values()), 'body label has no engine display name')
    result['column_names'] = names
    required=any(k!='body' for k in projection_kinds)
    ready=all(s=='complete' for s in projection_states)
    caption=('Native key/port projections below.' if ready else 'Native key/port projection evidence PENDING.') if required else 'These body witnesses are not key/port projections.'
    result['projection_audit']=dict(status='complete' if ready else 'pending',required=required,kinds=projection_kinds,caption=caption)
    check_comparisons(result)


def check_comparisons(result):
    tables = result['tables']
    schemas = {s:{c['ast_label_id']:c['type'] for c in t['schema']} for s,t in tables.items()}
    require(all(len(schemas[s]) == len(tables[s]['schema']) for s in tables), 'duplicate original body label IDs')
    equal_schema = schemas['gold'] == schemas['mutant']
    # Non-Unit IDs were authenticated against the native BodyView. Unit IDs
    # are synthetic display keys, so cannot prove native alignment absent.
    no_alignment = any(ty!='Unit' and schemas['mutant'].get(label)!=ty
                       for label,ty in schemas['gold'].items())
    entries = {s:{(e['choice'],e['example'],e['model']):e for e in t['entries']} for s,t in tables.items()}
    require(all(len(entries[s]) == len(tables[s]['entries']) for s in tables), 'duplicate body assignment/model entry')
    checked = []
    reports=result['comparisons']
    alignments={r.get('model_alignment','legacy_same_index') for r in reports}
    require(len(alignments)==1,'native comparison model alignment is mixed or absent')
    alignment=next(iter(alignments))
    require(alignment in ('cartesian','legacy_same_index'),'native comparison alignment cannot authenticate row pairs: '+str(alignment))
    examples={e['example'] for t in tables.values() for e in t['entries']} - {'task'}
    if not examples:examples={'task'}
    expected_keys=set()
    for example in examples:
        for choice in range(1,len(result['kept_assignments'])+1):
            models={}
            for side in tables:
                relevant=[e for e in tables[side]['entries'] if e['choice']==choice and e['example']==example]
                if not relevant:relevant=[e for e in tables[side]['entries'] if e['choice']==choice and e['example']=='task']
                models[side]={e['model'] for e in relevant}
            require(models['gold'] and models['mutant'],'body comparison model domain absent')
            if alignment=='legacy_same_index':
                require(models['gold']==models['mutant'],'legacy body comparison model domains differ')
            expected_keys.update((choice,example,g,m) for g in models['gold'] for m in models['mutant'] if alignment=='cartesian' or g==m)
    order = sorted(schemas['gold'])
    for report in reports:
        require(report['status']=='complete', 'comparison stopped/faulted')
        i=report['example']; ntrain=len(result['task_data']['train'])
        example = 'task' if i is None else 'train'+str(i+1) if i<ntrain else 'test'+str(i-ntrain+1)
        choice=report['assignment']+1
        models={s:report[s+'_model'] if alignment=='cartesian' else report['model'] for s in tables}
        require(all(type(m) is int and m>=0 for m in models.values()),'native comparison model axis absent or invalid')
        if alignment=='cartesian':require(report['model']==models['gold'],'legacy comparison alias differs from gold model')
        selected = {};counts = {}
        scopes=[]
        for side in tables:
            model=models[side]
            entry = entries[side].get((choice,example,model), entries[side].get((choice,'task',model)))
            require(entry is not None, 'comparison refers to absent body example/choice/model')
            scopes.append(entry['example'])
            counts[side] = len(entry['rows'])
            if equal_schema:
                cols = {c['ast_label_id']:c['index'] for c in tables[side]['schema']}
                selected[side] = {tuple(tuple(row[cols[c]]['value']) for c in order) for row in entry['rows']}
        scope_alignment='same' if scopes[0]==scopes[1] else 'broadcast_task_wide'
        if 'scope_alignment' in report:require(report['scope_alignment']==scope_alignment,'native comparison scope alignment differs')
        if equal_schema:
            kept = len(selected['gold'] & selected['mutant'])
            extra, missing = len(selected['mutant'])-kept, len(selected['gold'])-kept
        else:
            require(no_alignment,'unequal body schema comparison alignment projection identity unavailable')
            # Native order=None compares no shared tuples. Complete exported
            # rows preserve native cardinality even when readable cells alias.
            kept = 0
            extra, missing = counts['mutant'], counts['gold']
        relation = 'equal' if not extra and not missing else 'subset' if not extra else 'superset' if not missing else 'overlap'
        actual=dict(schema_equal=equal_schema,kept=kept,extra=extra,missing=missing,relation=relation)
        for key,value in actual.items():
            require(report.get(key)==value, f'native comparison {key} differs at choice {choice}/{example}: {value} != {report.get(key)}')
        checked.append(dict(choice=choice,example=example,gold_model=models['gold'],mutant_model=models['mutant'],model_alignment=alignment,scope_alignment=scope_alignment,**actual))
    keys=[(r['choice'],r['example'],r['gold_model'],r['mutant_model']) for r in checked]
    require(len(keys)==len(set(keys)) and set(keys)==expected_keys,'native comparison report has gaps/duplicate entries')
    result['comparison_audit'] = checked


def refresh_body_extents(table,view,side,structured,kept):
    """Accept fresh native extent metadata only on exactly equal body rows."""
    observation=(structured.get('components') or {}).get('body_observation')
    if not observation or observation['report'].get('status')!='complete':return
    payload=observation['native'][side]
    if 'extent_status' not in payload['entries']:return
    from native import Native
    native=Native(payload)
    fresh=native.table(observation['report']['table_indices'][side+'_kept'],kept)
    from headers import bind_body_schema
    bind_body_schema(fresh,view)
    columns={c['ast_label_id']:c for c in table['schema']}
    current={c['ast_label_id']:c for c in fresh['schema']}
    require({k:c['type'] for k,c in columns.items()}=={k:c['type'] for k,c in current.items()},'stored/fresh body schemas differ')
    key=lambda e:(e['choice'],e['example'],e['model'])
    entries={key(e):e for e in fresh['entries']}
    require(len(entries)==len(fresh['entries']) and set(entries)=={key(e) for e in table['entries']},'stored/fresh body entry axes differ')
    order=sorted(columns)
    for entry in table['entries']:
        live=entries[key(entry)]
        rowkey=lambda row,cols:tuple(tuple(row[cols[k]['index']]['value']) for k in order)
        rows={rowkey(r,current):r for r in live['rows']}
        require(len(rows)==len(live['rows']) and set(rows)=={rowkey(r,columns) for r in entry['rows']},'stored/fresh body values differ')
        require(len(live['rows'])==len(entry['rows']),'stored/fresh body row counts differ')
        for row in entry['rows']:
            source=rows[rowkey(row,columns)]
            for label in order:
                old=row[columns[label]['index']];new=source[current[label]['index']]
                if 'extent_status' not in new:continue
                if new['extent_status']=='resolved' and old.get('extent') and min(old['extent'])>0:
                    require(old['extent']==new['extent'],'stored/fresh resolved body extents differ')
                old['extent_status']=new['extent_status']
                if 'extent' in new:old['extent']=list(new['extent'])
                else:old.pop('extent',None)
    table['extent_audit']='equal fresh body values, original label identities, entry axes and choices'
