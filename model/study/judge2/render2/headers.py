"""Authenticate native headers and reconcile computed output field roles."""
import collections
import json
from native import require

PROOFS={'resolver_label_position','declared_layout','resolved_row_path'}


def identify_computed_columns(schema,audit,relation,side):
    """Keep typed output identity separate from repeating provenance aliases."""
    from column_paths import key
    checked={c['physical_column']:c for c in audit['columns']}
    for column in schema:
        column['source_alias']=column['source_label']
        if column['type']=='Unit':
            column['source_label']='@unit-computed:'+relation+':'+str(column['index'])
            continue
        witness=checked.get(column['index'])
        path=witness['row_path'] if witness is not None else None
        column['native_row_path']=path
        identity=key(path) if path is not None else ('unverified',side,column['index'])
        column['source_label']='@relation:'+relation+':'+json.dumps(identity,separators=(',',':'))


def reconcile_computed_headers(tables):
    """One native path order and display name per relation across both sides."""
    from column_paths import key,text
    orders={};names={};paths={}
    for side in ('gold','mutant'):
        for table in tables.get(side,[]):
            order=orders.setdefault(table['source_name'],[])
            for column in table['schema']:
                if column['type']=='Unit':continue
                identity=column['source_label']
                if identity in order:continue
                order.append(identity);path=column['native_row_path'];paths[identity]=path
                if path is None:names[identity]=side+' unresolved field '+str(column['index']+1)
                elif any(kind=='written' for kind,_ in key(path)):names[identity]=text(path,'role')
                else:names[identity]=column['label'] or text(path,'role')
    for order in orders.values():
        counts=collections.Counter(names[k] for k in order)
        for identity in order:
            if counts[names[identity]]>1:
                require(paths[identity] is not None,'unverified computed column display collision')
                names[identity]+=' ('+text(paths[identity],'role')+')'
        require(len({names[k] for k in order})==len(order),'computed output field names remain ambiguous')
    for side in ('gold','mutant'):
        for table in tables.get(side,[]):
            table['column_order']=orders[table['source_name']]
            for column in table['schema']:
                if column['type']!='Unit':column['display_name']=names[column['source_label']]
    return names,orders


def bind_body_schema(table,view,*,legacy_binding=None):
    columns=view['columns']
    if legacy_binding is not None:
        require(legacy_binding['schema']=='native-legacy-body-binding-v1',
                'unknown native legacy BODY binding')
        require(legacy_binding['body_path']==view['body_path'],
                'legacy BODY binding addresses another body')
        fields={f['physical_column']:f for f in legacy_binding['fields']}
        require(len(fields)==len(legacy_binding['fields'])==len(table['schema']),
                'legacy BODY binding field coverage differs')
        current={c['body_column']:c for c in columns}
        require(len(current)==len(columns),'duplicate current BODY physical column')
        names={}
        for column in table['schema']:
            require(column['index'] in fields,'legacy BODY physical column missing')
            field=fields[column['index']]
            require(column['type']==field['legacy_physical_type']['type'],
                    'legacy BODY physical type differs from binding')
            label=current.get(field['current_physical_column'])
            require(label is not None and label['label_id']==field['label_id'],
                    'legacy BODY binding/current scoped label differs')
            column['ast_label_id']=field['label_id']
            column['source_label']='@label:'+str(field['label_id'])
            column['native_legacy_binding']=field
            names[column['source_label']]=label['label_spelling']
        table['native_legacy_body_receipt']=legacy_binding['receipt']
        return names
    require(sum(c['type']!='Unit' for c in columns)==sum(c['type']!='Unit' for c in table['schema']),'body AST/native column count mismatch')
    labels={c['label_spelling']:c for c in columns}
    require(len(labels)==len(columns),'duplicate body AST label spelling')
    names={}
    for c in table['schema']:
        if c['type']=='Unit':
            c['ast_label_id']=-1-c['index'];c['source_label']='@unit-body:'+str(c['index'])
            continue
        require(c['source_label'] in labels,'stored body label absent from source AST')
        label=labels[c['source_label']]
        require(c['type']==label['type'],'body AST/native column type mismatch')
        c['ast_label_id']=label['label_id']
        c['source_label']='@label:'+str(label['label_id'])
        names[c['source_label']]=label['label_spelling']
    return names


def audit_computed_schema(schema,definition,export):
    """Validate the native selected binding, never select an alias in Python."""
    context=definition['display_name'];gaps=[];checked=[]
    if definition.get('column_witness_status')!='complete':
        return dict(status='pending',gaps=[context+': native column witness unavailable'],columns=[])
    witnesses=definition['column_witnesses']
    require(len(witnesses)==len(schema),'native header witness width differs: '+context)
    variables={(tuple(v['scope_path']),v['label_id']):v for v in export['typed_sites'].get('variables',[])}
    for i,(c,w) in enumerate(zip(schema,witnesses)):
        require(c['index']==w['physical_column']==i,'native header physical column differs: '+context)
        require(w['definition_path']==definition['definition_path'] and w['relation']==definition['relation'],'native header definition identity differs: '+context)
        require(c['type']==w['type'],'native header type differs: '+context)
        if w.get('native_name') is not None:require(c['name']==w['native_name'],'native canonical column name differs: '+context)
        if w['status']=='unsupported' or w.get('row_path') is None:
            gaps.append(context+': native header identity unsupported at column '+str(i+1));continue
        require(w['proof'] in PROOFS and c['slot']==w['logical_slot'],'native header logical slot/proof differs: '+context)
        for binding in w['bindings']:
            require(binding['definition_path']==definition['definition_path'] and binding['output_identity']==definition['relation'],'native header binding owner differs: '+context)
            owner=binding['definition_path'];scope=binding['scope_path']
            require(scope[:len(owner)]==owner and binding['body_path'][:len(scope)]==scope,'native header binding scope differs: '+context)
            if binding['status']!='resolved':
                gaps.append(context+': native binding type unsupported at column '+str(i+1));continue
            key=(tuple(binding['scope_path']),binding['label_id'])
            require(key in variables,'native header binding lacks scoped checker variable: '+context)
            require(variables[key]['resolved_type']==binding['field_type'],'native header binding/checker type differs: '+context)
            require(binding['proof'] in PROOFS and isinstance(binding['source_column_path'],list),'native header binding proof missing: '+context)
        selected=w['selected_header_binding']
        if w['status']=='declared_without_local_label':
            require(selected is None and w['proof'] in ('declared_layout','resolved_row_path'),'native unlabelled header lacks declared proof: '+context)
            require(not c['label'] and not c['source_label'],'native unlabelled header unexpectedly has a local label: '+context)
        else:
            require(w['status']=='resolved' and selected is not None and selected in w['bindings'],'native selected header binding absent: '+context)
            if selected['status']!='resolved':continue
            key=(tuple(selected['scope_path']),selected['label_id'])
            require(selected['logical_slot']==w['logical_slot'],'native selected header logical slot differs: '+context)
            require(c['label']==variables[key]['label_spelling'],'native selected header/local label differs: '+context)
        checked.append(dict(physical_column=i,type=c['type'],row_path=w['row_path'],logical_slot=w['logical_slot'],
                            status=w['status'],proof=w['proof'],selected_header_binding=selected,
                            native_name=c['name'],label=c['label'],source_label=c['source_label']))
    return dict(status='pending' if gaps else 'complete',gaps=gaps,columns=checked)
