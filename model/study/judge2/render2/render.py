"""Deterministic evidence display. AST facts are never recovered from text."""
import hashlib
import json
from native import Native, require
from assignments import full_gold_status

VERSION = 'render2-partial-3'


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(compact(value).encode()).hexdigest()


def facts(record, task, orientations, structured=None, orientation_types=None):
    require(record['record_format'] == 'ast-study-pair-v4', 'expected v4 pair')
    require(record['status'] == record['evaluation']['status'] == 'complete', 'pair evaluation incomplete')
    from render2.execution import validate_train_example
    report = record['evaluation']
    require(report['gold_fits'] is True, 'no gold FITS assignment')
    kept = report['kept_assignments']
    require(kept and len(report['outputs']) == len(kept), 'incomplete kept OUT evidence')
    require(record['K'] == len(record['identity']['edits']), 'K differs from edit list')
    require(record['audit']['outside_atoms_unchanged'] is True, 'producer AST audit failed')
    tables = {}
    for side in ('gold', 'mutant'):
        require(report[side + '_tables']['status'] == 'complete', side + ' tables incomplete')
        native = Native(record['native'][side])
        tables[side] = native.table(report['table_indices'][side + '_kept'], kept)
        require(tables[side]['point'] == 1, 'expected native body table')
    for output in report['outputs']:
        choice = output['assignment']
        require(type(choice) is int and 0 <= choice < len(kept), 'invalid OUT choice')
        require(output['mutant']['status'] == 'complete', 'mutant OUT incomplete')
        for side, examples in (('gold', output['gold_train']), ('mutant', output['mutant']['train'])):
            require(len(examples) == len(task['train']), 'OUT examples missing')
            for i, ex in enumerate(examples):
                validate_train_example(ex,context=f'producer choice {choice+1} {side} train{i+1}')
                require(ex['example'] == i, 'OUT example index differs from train order')
    require(sorted(o['assignment'] for o in report['outputs']) == list(range(len(kept))), 'OUT choices missing/duplicated')
    result = dict(version=VERSION, pair_id=digest(record['identity']), task=record['task'],
                case=record['case'], kind=record['kind'], K=record['K'], operation=record['operation'],
                identity=record['identity'], programs=record['programs'], producer_audit=record['audit'],
                tables=tables, kept_assignments=kept, outputs=report['outputs'],gold_fits=report['gold_fits'],
                comparisons=report['kept_comparisons'], orientations=orientations,
                faults=[],
                orientation_types=orientation_types or {},
                task_data=dict(train=task['train'], test=[dict(input=e['input']) for e in task['test']]),
                pending=['Original changed atom nodes and exact after-edit path correspondence',
                         'Resolved literal meanings at every AST site and clause variable frames',
                         'Structured relation definitions, component/library meanings and reader closure',
                         'INIT input-port projection evidence',
                         'Independent native comparison-count audit',
                         'Full decoded kept DET assignments',
                         'Exact-kept continuation and DET admissibility',
                         'Computed relation/component outputs under exact-kept choices',
                         'Detailed native OUT rows and execution/table consistency'])
    if structured is not None:
        result['structured'] = structured
        naming=structured.get('relation_names',{})
        if naming.get('status')!='complete':
            result['pending'].append('Source relation names unavailable: '+naming.get('reason','native source-name map absent'))
        observation=structured.get('full_gold_evaluation')
        if observation is not None:
            status=full_gold_status(observation,scope=structured.get('full_gold_scope'))
            if status['status']!='complete':
                result['pending'].append('Full gold relation-table replay '+status['status']+': '+str(status.get('reason','unknown reason')))
        if all(c['deleted'] or c.get('after') for c in structured['changes']):
            result['pending'].remove('Original changed atom nodes and exact after-edit path correspondence')
        component_evidence=structured.get('components')
        if component_evidence is not None:
            from components import audit_components
            result['components']=audit_components(component_evidence,structured)
            for side in ('gold','mutant'):
                status=component_evidence.get('report',{}).get(side+'_status',{})
                if status.get('status')=='fault':result['faults'].append(side+' component collection fault: '+compact(status))
            if result['components']['status']=='complete':
                result['pending'].remove('Computed relation/component outputs under exact-kept choices')
            else:
                result['pending'].extend(result['components'].get('gaps') or [result['components'].get('reason','component rows unavailable')])
        from components import audit_continuation
        continuation=audit_continuation(component_evidence,result)
        if continuation:
            result['continuation']=continuation
            from out import audit_out
            detailed=audit_out(continuation,result)
            if detailed:
                result['native_out']=detailed
                if detailed['status']=='complete':result['pending'].remove('Detailed native OUT rows and execution/table consistency')
            if continuation['status']=='complete':result['pending'].remove('Exact-kept continuation and DET admissibility')
            else:result['pending'].extend(continuation['gaps'])
        if result.get('components'):
            from components import attach_choice_extents
            attach_choice_extents(result)
        from body import enrich
        enrich(result, structured)
        if result.get('assignment_audit')=='complete':
            result['pending'].remove('Full decoded kept DET assignments')
        if result.get('comparison_audit') is not None:
            result['pending'].remove('Independent native comparison-count audit')
        contexts=structured.get('contexts',{})
        if contexts and all(c is not None and all(l.get('semantics',{}).get('status')=='authored_contract' for l in c['libraries']) for c in contexts.values()):
            result['pending'].remove('Structured relation definitions, component/library meanings and reader closure')
        if result.get('projection_audit',{}).get('status')=='complete':
            result['pending'].remove('INIT input-port projection evidence')
        sites=structured.get('sites',{})
        frames=structured.get('frame_sources',{})
        for side,frame in frames.items():
            if frame and frame.get('status')=='fault':
                message=side+' frame export fault: '+frame['reason']
                result['faults'].append(message);result['pending'].append(message)
        if set(sites)=={'gold','mutant'} and all(s is not None for s in sites.values()):
            result['pending'].remove('Resolved literal meanings at every AST site and clause variable frames')
            if any(s['made_frames_status']!='complete' for s in sites.values()) and not (set(frames)=={'gold','mutant'} and all(v is not None and v.get('complete') is True for v in frames.values())):
                result['pending'].append('Native made-frame provenance for clause arguments')
    if result.get('components'):
        from headers import reconcile_computed_headers
        names,orders=reconcile_computed_headers(result['components']['tables'])
        require(not (set(names)&set(result.get('column_names',{}))),'computed/body column identity collision')
        result.setdefault('column_names',{}).update(names)
        result['components']['column_order']=orders
    if result.get('native_out'):
        result.setdefault('column_names',{}).update({'@out:position':result['native_out']['names']['position'],'@out:color':result['native_out']['names']['color']})
    from out import audit_fits
    audit_fits(result)
    check_visible_extents(result)
    return result


def check_visible_extents(result):
    unresolved=0
    def count(schema,rows):
        nonlocal unresolved
        for row in rows or []:
            for c,cell in zip(schema,row):
                if c['type'] in ('Position','Box','Offset') and cell.get('extent_status') not in ('resolved','no_grid'):
                    unresolved+=1
    for table in result['tables'].values():
        for e in table['entries']:
            if e['example_kind']!=2:count(table['schema'],e['rows'])
    for tables in result.get('components',{}).get('tables',{}).values():
        for table in tables:
            for e in table['entries']:
                if e['example_kind']!=2:count(table['schema'],e['rows'])
    for choice in result.get('structured',{}).get('kept_decoded') or []:
        for det in choice:
            examples=det.get('extent_examples')
            if not examples:count(det['schema'],det['rows'])
            else:
                for e in examples:
                    if e['example_kind']!=2:count(det['schema'],e['rows'])
    for e in result.get('native_out',{}).get('entries',[]):
        if not e['equals']:count([dict(type='Position'),dict(type='Color')],e['rows'])
    result['extent_audit']=dict(unresolved_visible_cells=unresolved)
    if unresolved:result['pending'].append('Native frame extent unresolved for '+str(unresolved)+' displayed geometric cells')


def cell_text(cell, ty):
    v = cell['value']
    text = compact(v) if ty in ('Box', 'Position', 'Offset') or len(v) != 1 else str(v[0])
    if 'extent' in cell:
        text += ' extent=' + compact(cell['extent'])
    return text


class RowCatalog:
    """Lossless in-document references, bound to complete native cell evidence."""
    def __init__(self):
        self.rows={}

    def lines(self,table,entry,order,values,*,allow_grid=True):
        # The exact serialized key, rather than a hash, establishes equality.
        # Include typed ordered schema, example context and all cell frame/status
        # metadata; equal display text alone cannot authorize reuse.
        key=compact(dict(schema=table['schema'],order=order,example=entry['example'],rows=entry['rows']))
        if key in self.rows:return ['  All rows: '+self.rows[key]+' (complete set defined above).']
        name='R'+str(len(self.rows)+1);self.rows[key]=name
        rows=values.rows(table,entry,order)
        return ['  '+name+f' ({len(entry["rows"])} rows, complete):',
                *(['  '+line for line in values.layout(rows,order,allow_grid=allow_grid)] if rows else ['  (empty relation)'])]


def computed_table_lines(table,values,full,title,entry_caption,catalog=None):
    """Render authenticated relation roles and rows under caller-owned axes."""
    order=table['column_order']
    schema={c['source_label']:c for c in table['schema']}
    lines=[title,'Columns: '+'; '.join(values.f['column_names'][k]+': '+(schema[k]['type'] if k in schema else 'absent') for k in order)]
    for header in table['header_audit']['columns']:
        column=table['schema'][header['physical_column']]
        if column['type']=='Unit':continue
        if header['label'] and header['label']!=column['display_name']:
            lines += ['  Field '+column['display_name']+': native provenance label '+header['label']+'.']
        if header['label'] and header['source_label'] and header['source_label']!=header['label']:
            lines += ['Source spelling '+header['source_label']+' denotes local label '+header['label']+'.']
    for entry in table['entries']:
        if entry['example_kind']==2:continue
        lines += [entry_caption(entry)]
        if catalog is not None:
            lines += catalog.lines(table,entry,order,values)
            continue
        rows=values.rows(table,entry,order)
        selection=values.grid_layout(rows,order)
        shown=rows if full or selection is not None else rows[:12]
        lines += ['  '+line for line in values.layout(shown,order,selection=selection)] if rows else ['  (empty relation)']
        if len(shown)<len(rows):lines += [f'  {len(rows)-len(shown)} more rows in pair-full.md.']
    return lines


def relation_name_lines(export):
    """Reader captions from native names; retain exact program tokens below."""
    names=export.get('relation_source_names')
    if names is None:return ['SOURCE RELATION NAMES unavailable.']
    lines=['SOURCE RELATION NAMES',
           'Exact program tokens below retain native identities; source captions follow the authenticated original writer map.']
    definitions={compact(d['relation']):d['source_name'] for d in export['definitions']['native_relations']}
    for row in names['relations']:
        identity=definitions.get(compact(row['native_relation']), 'writer slot '+str(row['relation_slot']))
        lines.append('  '+identity+' = '+row['display_name'])
    return lines


def display(f, full=False, values=None, include_programs=True, include_task=True, compact_evidence=False):
    from values import Values
    values = values or Values(f)
    catalog=RowCatalog() if compact_evidence else None
    lines = [f'PAIR {f["pair_id"]} {f["task"]} {f["case"]}',
             'Status: '+('FAULT' if f.get('faults') else 'PENDING' if f['pending'] else 'READY'),
             f'{f["kind"]}; K={f["K"]}; operation={f["operation"]}',
             'Outstanding evidence: ' + ('; '.join(f['pending']) or 'none'), '',
             'CHANGE']
    if f.get('structured'):
        lines[-1:-1]=relation_name_lines(f['structured']['gold'])+['']
    changes = {tuple(c['path']):c for c in f.get('structured',{}).get('changes',[])}
    for edit in f['identity']['edits']:
        path = '.'.join(map(str, edit['at']))
        change = changes.get(tuple(edit['at']))
        if change:
            lines += [f'  AST {path}: '+change['before']['sexp']+' → '+
                      ('deleted' if change['deleted'] else change['after']['sexp'] if change.get('after') else 'PENDING mutant node correspondence')]
            continue
        lines += [f'  AST {path}: {edit["kind"]}; gold atom → ' +
                  ('deleted' if edit['replacement'] is None else 'mutant atom') +
                  ' — exact atom text PENDING structured export.']
    if f['K'] > 1:
        lines += ['Single-edit effects unavailable in the stored record; shown effect combines all edits.']
    if f.get('structured'):
        lines += ['', 'CHANGED CLAUSE', f['structured']['clause']['sexp']]
        if f['structured'].get('mutant_clause'):
            lines += ['MUTANT CLAUSE',f['structured']['mutant_clause']['sexp']]
        if f['structured'].get('owner') != f['structured']['clause']:
            lines += ['OWNING DEFINITION',f['structured']['owner']['sexp']]
    contexts_ready=all(c is not None for c in f.get('structured',{}).get('contexts',{}).values()) and bool(f.get('structured',{}).get('contexts'))
    selected_scope=contexts_ready and any(c.get('definition_scope')=='downstream_only' for c in f['structured']['contexts'].values())
    lines += ['', ('CLAUSE AND READERS: selected downstream definitions below; upstream-only tables are outside this view.' if selected_scope else 'CLAUSE AND READERS: native definition closure below.' if contexts_ready else 'CLAUSE AND READERS: definitions and meanings PENDING structured export.'),
              *([] if compact_evidence else ['Exact full programs available with detail.py --program.']), '',
              'TABLE SCOPE: complete body witnesses at each gold-kept DET choice.',
              'For INIT: reader rows before key/port projection and component computation.',
              f.get('projection_audit',{}).get('caption','Native projection scope PENDING.'),
              'One numbered choice is one full gold assignment retained by the producer; mutant uses that same full assignment.',
              ('Full decoded DET choices below; body-read subsets follow.' if f.get('structured',{}).get('kept_decoded') else 'Full decoded DET choices: PENDING Term::decode; body-read subsets follow.'),
              'Coordinates are (row,col)/height×width; ZERO means all four frame margins zero.', '']
    if any(cell.get('extent_status')=='unresolved' for table in f['tables'].values() for entry in table['entries'] if entry['example_kind']!=2 for row in entry['rows'] for cell in row):
        lines += ['Native extent [-1,-1] means this row has no unique computed reference-frame size (unavailable or ambiguous).',
                  'Such values show their exact [top bottom left right] margins, without guessed coordinates or size.','']
    observation=f.get('structured',{}).get('full_gold_evaluation')
    if observation is not None:
        status=full_gold_status(observation,scope=f['structured'].get('full_gold_scope'))
        if status['status']!='complete':
            lines += ['Full gold relation-table replay '+status['status']+': '+str(status.get('reason','unknown reason'))+'. Missing replay rows are unavailable; no claim of complete full-program evaluation.','']
    if f.get('structured',{}).get('kept_decoded'):
        lines += ['FULL KEPT DET CHOICES (same numbered assignments for tables and OUT)']
        for i,choice in enumerate(f['structured']['kept_decoded'],1):
            lines += [f'Choice {i}']
            for det in choice:
                visible=[(i,c) for i,c in enumerate(det['schema']) if c['type']!='Unit']
                lines += ['  '+(det.get('display_name') or det['definition'])+' ('+', '.join(c['name'] for i,c in visible)+')']
                examples=det.get('extent_examples')
                examples=examples if examples else [dict(example='task',example_kind=0,model=0,rows=det['rows'])]
                for entry in examples:
                    if entry['example_kind']==2:continue
                    lines += ['    '+entry['example']+'; model '+str(entry['model'])+f'; rows={len(entry["rows"])}']
                    shown=entry['rows'] if full else entry['rows'][:12]
                    for row in shown:
                        lines += ['    '+(', '.join(c['name']+'='+values.text(row[j],c,entry['example']) for j,c in visible) or '{} (empty record)')]
                    if len(shown)<len(entry['rows']):lines += [f'    {len(entry["rows"])-len(shown)} more rows in pair-full.md (full assignment).']
        evidence=f['structured'].get('choice_evidence')
        if evidence:
            gold={d['source_name']:d for d in evidence['gold']['dets']}
            names_by_source={d['source_name']:d.get('display_name',d['source_name']) for d in f['structured']['gold']['definitions']['native_relations']}
            for mutant in evidence['mutant']['dets']:
                source=gold[mutant['source_name']]
                for j,(a,b) in enumerate(zip(source['types'],mutant['types'])):
                    if a!=b:lines += ['  '+names_by_source[mutant['source_name']]+f' column {j+1}: declared type {a} → {b}; held values above retain their gold {a} decoding.']
        lines += ['']
    libraries={}
    for side,context in f.get('structured',{}).get('contexts',{}).items():
        if context is None:continue
        lines += [side.upper()+' DEFINITIONS AND DOWNSTREAM READERS']
        for definition in context['forms']:
            lines += [('  reader: ' if definition['downstream'] else '  definition: ')+definition['node']['sexp']]
        for library in context['libraries']:
            libraries[library['id']]=library
        lines += ['']
    if libraries:
        lines += ['RELATION / COMPONENT MEANINGS']
        for library in libraries.values():
            semantics=library.get('semantics',{})
            if semantics.get('status')=='authored_contract':
                lines += ['  '+library['name']+': '+semantics['contract_markdown']]
            else:
                lines += ['  '+library['name']+': PENDING authored semantic contract.']
            if library['implementation']=='arclog':
                lines += ['  definition: '+library['declaration']['sexp']]
                if library.get('arclog_implementation'):
                    lines += ['  implementation: '+library['arclog_implementation']['sexp']]
        lines += ['']
    from sites import frame_text,native_frames
    for side,sites in f.get('structured',{}).get('sites',{}).items():
        if sites is None:continue
        lines += [side.upper()+' TYPED LITERALS AND CLAUSE FRAMES']
        seen=set()
        provenance=f['structured'].get('frame_sources',{}).get(side)
        bodyview=f['structured'].get('body_views',{}).get(side)
        native_variables={}
        relation_names={r['source_name']:r.get('display_name',r['source_name']) for r in f['structured'][side].get('definitions',{}).get('native_relations',[])}
        if provenance is not None and provenance.get('complete') is True and bodyview:
            for b in provenance['bodies']:
                for v in b['variables']:
                    native_variables.setdefault((tuple(b['owner_path']),v['label_id']),[]).append(v)
        for item in sites['variables']:
            s=item['site'];key=(tuple(s['scope_path']),s['label_id'],s['resolved_type'],compact(s['frame']))
            if s.get('literal') or key in seen:continue
            seen.add(key)
            text='  '+item['node']['sexp']+' (scope AST '+'.'.join(map(str,s['scope_path']))+'): '+s['resolved_type']+'; '+frame_text(s['frame'])
            variable=native_variables.get((tuple(s['scope_path']),s['label_id']))
            if variable and any(v['frame_applicable'] for v in variable):
                text+='; '+native_frames([source for v in variable for source in v['sources']],relation_names)
            lines += [text]
        for item in sites['literals']:
            s=item['site'];lines += ['  AST '+'.'.join(map(str,s['path']))+': '+s['literal']['meaning']+'; '+frame_text(s['frame'])]
        for item in sites['comparisons']:
            s=item['site'];lines += ['  '+item['node']['sexp']+': first '+s['first']['resolved_type']+' ('+frame_text(s['first']['frame'])+'); second '+s['second']['resolved_type']+' ('+frame_text(s['second']['frame'])+')'+
                ('; '+s['second']['literal']['meaning'] if s['second'].get('literal') else '')]
        lines += ['']
    identitykeys = sorted({c['source_label'] or '@slot:'+str(c['slot'])
                           for t in f['tables'].values() for c in t['schema']})
    allkeys = [k for k in identitykeys if any((c['source_label'] or '@slot:'+str(c['slot']))==k and c['type']!='Unit' for t in f['tables'].values() for c in t['schema'])]
    # Anonymous label names await AST export, rather than showing invented cN.
    names = {k: f.get('column_names',{}).get(k) or (k if not k.startswith('@slot:') else f'unnamed column {i+1} (name pending)')
             for i,k in enumerate(allkeys)}
    names.update(f.get('column_names',{}))
    rendered = {}
    for side, table in f['tables'].items():
        schema={c['source_label'] or '@slot:'+str(c['slot']):c for c in table['schema']}
        lines += [side.upper() + ' BODY', 'Columns: ' + '; '.join(
            names[k]+': '+(schema[k]['type']+((' in '+schema[k]['frame'] if schema[k]['frame'] else ' (native per-row frame or gridless margins)') if schema[k]['type'] in ('Position','Box','Offset') else '') if k in schema else 'absent')
            for k in allkeys)]
        for entry in table['entries']:
            if entry['example_kind'] == 2:
                continue
            label = f'{side} choice {entry["choice"]}; {entry["example"]}; model {entry["model"]}'
            lines += [label + f'; rows={len(entry["rows"])}']
            for det in entry['assignment']:
                lines += ['  Body reads held DET '+(det.get('display_name') or '(relation name pending)')+
                          f'; complete decoded values in Choice {entry["choice"]} above (exact native read subset checked).']
            if not entry['assignment']:lines += ['  Body reads no held DET relations.']
            rows = values.rows(table,entry,allkeys)
            rendered[(side,entry['choice'],entry['example'],entry['model'])] = rows
            if catalog is not None:
                lines += catalog.lines(table,entry,allkeys,values)
            else:
                selection=values.grid_layout(rows,allkeys)
                shown = rows if full or selection is not None else rows[:12]
                if len(shown)<len(rows):lines += [f'  First {len(shown)} of {len(rows)} rows (sample; complete rows in detail):']
                lines += ['  '+line for line in values.layout(shown,allkeys,selection=selection)] if rows else ['  (empty relation)']
                if len(shown)<len(rows):
                    lines += [f'  {len(rows)-len(shown)} more rows: detail.py --table {side}.']
        lines += ['']
        if table.get('body_projection',{}).get('status')=='complete':
            projection = table['body_projection']
            label='INIT KEY' if projection['kind']=='key' else table['port']+' PORT HEAD'
            lines += [side.upper()+' PROJECTED '+label+' (deduplicated; body context retained above)']
            for entry in projection['entries']:
                if entry['example'].startswith('test'): continue
                lines += [f'choice {entry["choice"]}; {entry["example"]}; model {entry["model"]}; projected rows={len(entry["rows"])}']
                for row in entry['rows'] if full else entry['rows'][:12]:
                    fields=', '.join(names[c['source_label']]+'='+values.text(cell,c,entry['example']) for c,cell in zip(projection['columns'],row) if c['type']!='Unit')
                    if projection.get('record_width')==0:
                        lines += ['  '+(fields+'; projected record = {}' if fields else '{} (empty record)')]
                    else:lines += ['  '+(fields or '{} (empty record)')]
                if not entry['rows']:lines += ['  (empty relation)']
                if not full and len(entry['rows'])>12:lines += ['  remaining projected rows in detail.']
            lines += ['']
    lines += ['ROW CHANGES (paired only when rows agree in every other column)']
    for comparison in f.get('comparison_audit',[]):
        choice,example=comparison['choice'],comparison['example']
        if example.startswith('test'):continue
        gm,mm=comparison['gold_model'],comparison['mutant_model']
        goldrows=rendered.get(('gold',choice,example,gm),rendered.get(('gold',choice,'task',gm)))
        mutantrows=rendered.get(('mutant',choice,example,mm),rendered.get(('mutant',choice,'task',mm)))
        require(goldrows is not None and mutantrows is not None,'audited row-change model pair absent from display')
        def rowkey(r):return tuple(r.key.get(k) for k in identitykeys)
        g={rowkey(r):r for r in goldrows};m={rowkey(r):r for r in mutantrows}
        missing=set(g)-set(m);extra=set(m)-set(g)
        lines += [f'choice {choice}; {example}; gold model {gm}, mutant model {mm}; {comparison["scope_alignment"]}: shared={len(set(g)&set(m))}, missing={len(missing)}, extra={len(extra)}']
        pairs=[]
        # Unique one-column matches are explanatory pairings, not causal attribution.
        for field in allkeys:
            c=identitykeys.index(field)
            a={};b={}
            for k in missing:a.setdefault(k[:c]+k[c+1:],[]).append(k)
            for k in extra:b.setdefault(k[:c]+k[c+1:],[]).append(k)
            for rest in sorted(a.keys()&b.keys(),key=repr):
                if len(a[rest])==len(b[rest])==1:
                    old,new=a[rest][0],b[rest][0]
                    pairs.append((old,new,c));missing.remove(old);extra.remove(new)
        for old,new,c in pairs if full else pairs[:8]:
            context=', '.join(names[k]+'='+g[old].text[k] for k in allkeys if k!=identitykeys[c])
            lines += ['  '+context+': '+names[identitykeys[c]]+' '+g[old].text[identitykeys[c]]+' → '+m[new].text[identitykeys[c]]]
        if not full and len(pairs)>8:lines += [f'  {len(pairs)-8} more paired changes in detail.']
    component_tables=f.get('components',{}).get('tables',{})
    if component_tables:
        lines += ['', 'COMPUTED RELATION AND COMPONENT OUTPUTS',
                  'Native execution under the numbered full held gold DET values; these values override proposal bodies.',
                  'Headers use native output field roles; provenance labels are stated separately and can repeat.',
                  'Native physical columns, scoped provenance labels and declared layouts are authenticated.',
                  'This does not establish DET admissibility or execution from the mutated candidate relation.']
        for side,tables in component_tables.items():
            for table in tables:
                lines += computed_table_lines(table,values,full,
                    side.upper()+' '+table['display_name']+' — computed written relation',
                    lambda entry:f'choice {entry["choice"]}; {entry["example"]}; model {entry["model"]}; rows={len(entry["rows"])}',catalog=catalog)
    from render2.execution import given_text,fit_text
    lines += ['', 'TRAIN OUTPUT-SET FITS',
              'Native accepted-set judgements apply to the complete set of distinct model grids; GIVEN comparisons below are per model.']
    for item in f['fits_evidence']:
        lines += [f'choice {item["choice"]}; {item["side"]}; train{item["example"]+1}; '+item['origin']+': '+fit_text(item['evidence'])]
    continuation=f.get('continuation')
    if continuation:
        names_by_source={d['source_name']:d.get('display_name',d['source_name']) for d in f['structured']['gold']['definitions']['native_relations']}
        lines += ['', 'HELD DET ADMISSIBILITY AND CONDITIONAL CONTINUATION',
                  'Each DET is checked with only its own held intervention removed; other gold DET values stay held.',
                  'Conditional execution reinstates every held value even when its proposal no longer admits it.']
        for choice in continuation['report']['choices']:
            lines += [f'Choice {choice["assignment"]+1}']
            for det in choice['admissibility']:
                state=('admissible' if det['admissible'] else 'INADMISSIBLE') if det['status']=='complete' else det['status']
                if det['status']=='complete' and not det['admissible'] and det.get('comparison')=='held row set equals a native domain value':
                    lines += ['  '+names_by_source[det['source_name']]+': UNRESOLVED native evidence conflict: boolean says INADMISSIBLE; explanation says '+det['comparison']+'.']
                else:lines += ['  '+names_by_source[det['source_name']]+': '+state+'; '+det.get('comparison',det.get('reason','native domain check incomplete'))]
            for example in choice['out'].get('train',[]):
                lines += [f'  conditional OUT train{example["example"]+1}: '+fit_text(example)]
                if not example['models']:lines += ['  No models enumerated.']
                for i,model in enumerate(example['models']):
                    state=given_text(model)
                    lines += [f'  conditional OUT train{example["example"]+1}; model {i}: '+state]
        lines += ['Historical OUT equality/cell counts agree with this exact-kept continuation.' if continuation['status']=='complete' else 'Continuation evidence incomplete; see outstanding evidence.',
                  ('Detailed native OUT rows/grids below.' if f.get('native_out') else 'Detailed raw OUT rows/grids and execution/table consistency remain PENDING.')]
    if f.get('native_out'):
        out=f['native_out'];names=out['names'];order=['@out:position','@out:color']
        schema=[dict(index=i,type=ty,source_label=key,frame='') for i,(ty,key) in enumerate(zip(('Position','Color'),order))]
        lines += ['', 'NATIVE CONDITIONAL OUT', 'Projection from original OUT body at AST '+'.'.join(map(str,out['binding']['body_path']))+': '+names['position']+' (Position), '+names['color']+' (Color); duplicate rows removed by native execution.']
        for entry in out['empty_examples']:
            lines += [f'choice {entry["choice"]}; {entry["example"]}: no models enumerated; no mutant OUT grid.']
            from grids import train_panels,fits_inline
            example=f['task_data']['train'][entry['example_index']]
            if full or fits_inline(example,None):lines += ['  '+line for line in train_panels(example,None)]
            else:lines += ['  Task grids exceed 15x15: pair-full.md, NATIVE CONDITIONAL OUT, '+entry['example']+'.']
        for entry in out['entries']:
            lines += [f'choice {entry["choice"]}; {entry["example"]}; model {entry["model"]}; rows={len(entry["rows"] or [])}; '+given_text(entry)]
            if entry.get('value_kind')=='undefined':
                from grids import train_panels,fits_inline
                example=f['task_data']['train'][entry['example_index']]
                if full or fits_inline(example,None):lines += ['  '+line for line in train_panels(example,None,include_reference=include_task)]
                else:lines += ['  Task grids exceed 15x15: pair-full.md, NATIVE CONDITIONAL OUT, '+entry['example']+'.']
                lines += ['  undefined OUT; no row set or grid was produced.'];continue
            if entry['equals']:
                lines += ['  This mutant model equals the GIVEN train output; output-set FITS is reported separately.']
                continue
            from grids import train_panels,fits_inline
            example=f['task_data']['train'][entry['example_index']]
            if full or fits_inline(example,entry['grid']):
                lines += ['  '+line for line in train_panels(example,entry['grid'],include_reference=include_task)]
            else:
                lines += ['  Task/OUT grids exceed 15x15: pair-full.md, NATIVE CONDITIONAL OUT, '+f'choice {entry["choice"]}, {entry["example"]}, model {entry["model"]}.']
            if entry['grid'] is None:lines += ['  Native OUT does not define a grid; exact decoded rows follow.']
            if compact_evidence and entry['grid'] is not None:continue
            rows=values.rows(dict(schema=schema),entry,order)
            shown=rows if full else rows[:12]
            lines += ['  '+line for line in values.layout(shown,order,allow_grid=False)] if rows else ['  (no OUT rows)']
            if len(shown)<len(rows):lines += [f'  {len(rows)-len(shown)} more OUT rows in pair-full.md.']
    if include_task:lines += ['', 'TEST INPUTS']
    for i,example in enumerate(f['task_data']['test'] if include_task else [],1):
        grid=example['input'];lines += [f'test{i} input']
        if full or (len(grid)<=15 and max(map(len,grid),default=0)<=15):
            from grids import grid_lines
            lines += ['  '+line for line in grid_lines(grid)]
        else:lines += [f'  Input exceeds 15x15: pair-full.md, TEST INPUTS, test{i}.']
    lines += ['', ('OUT at each full gold-kept choice (historical producer report; exact-kept comparison checked above)' if f.get('continuation',{}).get('status')=='complete' else 'OUT at each full gold-kept choice (producer report; execution/table audit PENDING)')]
    for out in f['outputs']:
        for side,examples in (('gold',out['gold_train']),('mutant',out['mutant']['train'])):
            for ex in examples:
                lines += [f'choice {out["assignment"]+1}; producer {side}; train{ex["example"]+1}: '+fit_text(ex)]
                models=[f'model {i}: '+given_text(m) for i,m in enumerate(ex['models'])]
                lines += ['  '+('; '.join(models) if models else 'no models enumerated')]
    if not compact_evidence:
        lines += ['', 'Task grids: show.py BATCH --task '+f['task'],
                  'Full decoded rows: detail.py SAMPLE_DIRECTORY 1 --table gold (or mutant).',
                  'Raw storage and audit details: detail.py SAMPLE_DIRECTORY 1 --raw.', '']
    if full and include_programs:
        for side in ('gold','mutant'):
            lines += [side.upper()+' EXACT PROGRAM', '```arclog',f['programs'][side].rstrip(),'```','']
    return '\n'.join(lines)


def audit(text, expected, serialized=None):
    parsed = json.loads(serialized if serialized is not None else compact(expected))
    require(parsed == expected, 'round-trip evidence differs from native source')
    require(display(parsed) == text, 'human-facing text differs from evidence')
    return dict(round_trip='complete', native_rows='complete', status='fault' if expected.get('faults') else 'pending' if expected['pending'] else 'ready', gaps=expected['pending'],faults=expected.get('faults',[]))
