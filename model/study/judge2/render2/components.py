"""Exact-kept native relation collection, with explicit entry/choice maps."""
import json
from native import Native,case_payload,require


def collect(engine,evaluator,gold,mutant,record,contexts,exports):
    point=next(p for p in gold.points() if list(p.body_path)==record['identity']['body'])
    # This is a fresh observation, never an alternate historical assignment.
    # The native collection guard below must accept exact historical equality.
    observed,gbody,mbody=evaluator.evaluate_pair(gold,point,mutant)
    try:
        text,g,m=engine.study_component_tables(evaluator,gold,mutant,json.dumps(record['evaluation']['kept_assignments']))
    except ValueError as error:
        if 'stored kept assignments differ' in str(error):
            return dict(status='pending',reason=str(error),scope='historical component replay unavailable; no alternate FITS accepted')
        raise
    report=json.loads(text)
    require(report['schema']=='arclog-study-component-tables-v1','unknown component evidence schema')
    require(report['kept_assignments']==record['evaluation']['kept_assignments'],'component replay changed historical choices')
    raw={'gold':case_payload(g),'mutant':case_payload(m)}
    body_observation=dict(report=json.loads(observed),native={'gold':case_payload(gbody),'mutant':case_payload(mbody)})
    continuation=None
    if hasattr(engine,'study_continuation'):
        text,_,_=engine.study_continuation(evaluator,gold,mutant,json.dumps(record['evaluation']['kept_assignments']))
        continuation=json.loads(text)
        require(continuation['kept_assignments']==record['evaluation']['kept_assignments'],'continuation changed historical choices')
    return dict(status='observed',report=report,native=raw,continuation=continuation,body_observation=body_observation)


def packing_gaps(report, scope):
    """Preserve global native packing evidence without assigning it to an entry."""
    packing=report.get('packing')
    if packing is None:return []
    require(isinstance(packing,dict) and packing.get('status')=='stopped',
            'unknown native output packing status')
    require(isinstance(packing.get('stops'),list) and packing['stops'],
            'native output packing stop diagnostics absent')
    return [scope+' native output packing '+json.dumps(packing,sort_keys=True)]


def audit_components(evidence,structured):
    if evidence.get('status')!='observed':return dict(status=evidence['status'],reason=evidence['reason'],tables={})
    report=evidence['report'];result={};gaps=packing_gaps(report,'component')
    kinds={'task':0,'train':1,'test':2}
    for side in ('gold','mutant'):
        native=Native(evidence['native'][side]);mapping=report[side+'_assignment_map']
        if mapping is None:
            status=report[side+'_status']
            require(status['status']!='complete','complete component collection has no entry map')
            result[side]=[]
            gaps.append(side+' component collection '+json.dumps(status,sort_keys=True))
            continue
        definitions={r['source_name']:r for r in structured[side]['definitions']['native_relations']}
        forms={tuple(d['node']['path']) for d in structured['contexts'][side]['forms']}
        forms.add(tuple(structured['owner']['path']))
        selectors={(d['native_selector']['form'],d['native_selector']['point'],d['native_selector']['relation']):d for d in definitions.values()}
        tables=[];seen=set()
        for table_map in mapping:
            t=table_map['table'];require(t not in seen,'duplicate component mapped table');seen.add(t)
            if not 0<=t<len(native.tables['width']):
                context=dict(side=side,table=t,source_name=table_map.get('source_name'),
                             native_table_count=len(native.tables['width']),
                             collection_status=report.get(side+'_status'))
                packing=packing_gaps(report,'component')
                require(False,'mapped component table absent: '+json.dumps(context,sort_keys=True)+
                        ('; '+'; '.join(packing) if packing else ''))
            selector=(native.tables['form'][t],native.tables['point'][t],native.tables['relation'][t])
            require(selector in selectors,'materialized relation missing structured definition')
            definition=selectors[selector]
            require(table_map['source_name']==definition['source_name'],'component relation identity differs')
            indices=native.bytable[t];mapped=table_map['entries']
            require(len(indices)==len(mapped),'component entry map coverage differs')
            entries=[]
            for position,(e,entry_map) in enumerate(zip(indices,mapped)):
                require(entry_map['table_entry']==position,'component map is not table-relative native order')
                require(native.entries['example_kind'][e]==kinds[entry_map['example_kind']] and native.entries['example_index'][e]==entry_map['example_index'] and native.entries['model'][e]==entry_map['model'],'component native entry axes differ')
                choice=entry_map['kept_assignment']
                if choice is None:
                    gaps.append(side+' '+definition['display_name']+': native fault/no-entries placeholder')
                    continue
                require(type(choice) is int and 0<=choice<len(report['kept_assignments']),'component map choice outside full choices')
                try:entry=native.entry(e)
                except ValueError as error:
                    gaps.append(side+' '+definition['display_name']+': '+str(error));continue
                entry['choice']=choice+1
                expected={d['relation']:d['rows'] for d in report['kept_assignments'][choice]}
                for det in entry['assignment']:
                    require(det['relation'] in expected,'component DET absent from full held choice')
                    full={d['source_name']:d for d in structured['kept_decoded'][choice]}
                    from assignments import check_held_schema
                    check_held_schema(det['relation'],det['types'],structured,side)
                    flat=[[v for c in row for v in c['value']] for row in full[det['relation']]['rows']]
                    require(sorted(flat)==sorted(det['rows']),'component native assignment differs from held choice')
                entries.append(entry)
            if tuple(definition['definition_path']) not in forms:continue
            schema=native.schema(t)
            from headers import audit_computed_schema,identify_computed_columns
            header_audit=audit_computed_schema(schema,definition,structured[side])
            gaps.extend(side+' '+gap for gap in header_audit['gaps'])
            identify_computed_columns(schema,header_audit,definition['source_name'],side)
            require(len({c['source_label'] for c in schema if c['type']!='Unit'})==sum(c['type']!='Unit' for c in schema),'native computed columns have ambiguous source identities')
            tables.append(dict(display_name=definition['display_name'],source_name=definition['source_name'],
                               definition_path=definition['definition_path'],schema=schema,entries=entries,header_audit=header_audit))
        require(seen==set(range(2,len(native.tables['width']))),'native relation tables missing entry maps')
        result[side]=tables
        if report[side+'_status']['status']!='complete':gaps.append(side+' component collection '+json.dumps(report[side+'_status'],sort_keys=True))
    return dict(status='complete' if not gaps else 'pending',tables=result,gaps=sorted(set(gaps)))


def audit_continuation(evidence,result):
    if not evidence or not evidence.get('continuation'):return None
    from render2.execution import validate_train_example,example_fit
    report=evidence['continuation']
    require(report['schema']=='arclog-study-continuation-v1','unknown continuation schema')
    require(report['kept_assignments']==result['kept_assignments'],'continuation full choices differ')
    require([c['assignment'] for c in report['choices']]==list(range(len(result['kept_assignments']))),'continuation choice coverage differs')
    gaps=packing_gaps(report,'continuation')
    for choice,historical in zip(report['choices'],result['outputs']):
        full={d['relation'] for d in result['kept_assignments'][choice['assignment']]}
        require({d['source_name'] for d in choice['admissibility']}==full,'DET admissibility coverage differs')
        for det in choice['admissibility']:
            if det['status']!='complete':gaps.append('DET admissibility '+det['source_name']+': '+det['status'])
            else:
                require(type(det['admissible']) is bool,'native DET admissibility missing')
                if det.get('comparison')=='held row set equals a native domain value' and not det['admissible']:
                    gaps.append('Contradictory native DET admissibility for '+det['source_name'])
        live=choice['out']
        if live['status']!='complete':gaps.append('conditional OUT '+live['status']);continue
        require(len(live['train'])==len(historical['mutant']['train']),'conditional OUT example coverage differs')
        for current,stored in zip(live['train'],historical['mutant']['train']):
            validate_train_example(current,context='native continuation train example')
            validate_train_example(stored,context='producer continuation train example')
            from out import compare_fits
            compare_fits(current,stored)
            if example_fit(current) is None:gaps.append('Native conditional OUT accepted-set FITS unavailable')
            require(current['example']==stored['example'],'conditional OUT train identity differs')
            require(len(current['models'])==len(stored['models']),'conditional OUT model coverage differs')
            for a,b in zip(current['models'],stored['models']):
                require(a['status']==b['status'],'historical/live conditional OUT model status differs')
                if a['status']!='complete':gaps.append('conditional OUT model '+a['status']);continue
                for key in ('equals','differing_cells'):
                    require(a[key]==b[key],'historical/live conditional OUT '+key+' differs')
    return dict(status='complete' if not gaps else 'pending',gaps=gaps,report=report,
                detailed_rows=all('rows' in m or m.get('value_kind')=='undefined' for c in report['choices'] for t in c['out'].get('train',[]) for m in t['models']))


def unavailable_choice_extent(det,reason,result):
    """Preserve unavailable native annotations without inventing example rows."""
    det.pop('extent_examples',None)
    det['extent_evidence']=dict(status='unresolved',reason=reason)
    for row in det['rows']:
        for schema,cell in zip(det['schema'],row):
            if schema['type'] in ('Position','Box','Offset'):
                cell.pop('extent',None)
                cell['extent_status']='no_grid' if schema['type']=='Offset' else 'unresolved'
    if det['rows'] and any(c['type'] in ('Position','Box') for c in det['schema']):
        result['pending'].append('Native full-choice extent unavailable for '+(det.get('display_name') or det['source_name'])+': '+reason)


def attach_choice_extents(result):
    """Consume native full-choice annotations without merging example frames."""
    evidence=result['structured'].get('components') or {}
    sidecar=evidence.get('report',{}).get('full_choice_extents')
    decoded=result['structured'].get('kept_decoded') or []
    if sidecar is None:
        for choice in decoded:
            for det in choice:
                unavailable_choice_extent(det,'native full-choice extent sidecar unavailable',result)
        return
    require(sidecar['schema']=='arclog-study-choice-extents-v1','unknown full-choice extent schema')
    require([c['assignment'] for c in sidecar['choices']]==list(range(len(decoded))),'full-choice extent assignment coverage differs')
    kinds={'task':0,'train':1,'test':2}
    for number,(choice,annotations) in enumerate(zip(decoded,sidecar['choices'])):
        by_name={d['source_name']:d for d in annotations['dets']}
        require(set(by_name)=={d['source_name'] for d in choice},'full-choice extent DET coverage differs')
        packed={d['relation']:d['rows'] for d in result['kept_assignments'][number]}
        for det in choice:
            annotation=by_name[det['source_name']];examples=[]
            status=annotation.get('status')
            require(status in ('complete','unresolved'),'unknown native full-choice extent variant for '+det['source_name'])
            if status=='unresolved':
                unavailable_choice_extent(det,annotation.get('reason','no exact held extent examples materialized'),result)
                continue
            require(isinstance(annotation.get('examples'),list) and annotation['examples'],
                    'complete native full-choice extent lacks examples for '+det['source_name'])
            det['extent_evidence']=dict(status='complete')
            original={tuple(raw):row for raw,row in zip(packed[det['source_name']],det['rows'])}
            require(len(original)==len(det['rows']),'duplicate full-choice packed row')
            for example in annotation['examples']:
                rows=[]
                for annotated in example['rows']:
                    raw=tuple(annotated['packed_row']);require(raw in original,'extent sidecar row absent from exact held choice')
                    row=[dict(c) for c in original[raw]]
                    geometric={i for i,c in enumerate(det['schema']) if c['type'] in ('Position','Box','Offset')}
                    require({c['column'] for c in annotated['cells']}==geometric,'choice geometric annotation coverage differs')
                    for cell in annotated['cells']:
                        i=cell['column'];status=cell['extent_status'];extent=cell['extent']
                        require(status in ('no_grid','resolved','unresolved'),'invalid full-choice native extent status')
                        require((status=='resolved' and extent and len(extent)==2 and min(extent)>0) or (status!='resolved' and extent is None),'full-choice extent/status conflict')
                        row[i]['extent_status']=status
                        if extent is not None:row[i]['extent']=list(extent)
                        else:row[i].pop('extent',None)
                    rows.append(row)
                require({tuple(r['packed_row']) for r in example['rows']}==set(original),'choice extent example row coverage differs')
                kind=example['example_kind'];require(kind in kinds,'invalid choice extent example kind')
                name='task' if kind=='task' else kind+str(example['example_index']+1)
                examples.append(dict(example=name,example_kind=kinds[kind],example_index=example['example_index'],model=example['model'],rows=rows))
            det['extent_examples']=examples
