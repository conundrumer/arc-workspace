"""Resolved site evidence and literal completeness from native inference."""
from native import require


def collect(export, clause, context):
    if export['parts'].get('argument_types')!='complete' or export['parts'].get('literal_meanings')!='complete':
        return None
    typed=export['typed_sites'];nodes={tuple(n['path']):n for n in export['nodes']}
    args={tuple(s['path']):s for s in typed['arguments']}
    comparisons={tuple(c['path']):c for c in typed['comparisons']}
    require(len(args)==len(typed['arguments']), 'duplicate typed site paths')
    for path,arg in args.items():
        require(path in nodes and arg['resolved_type'] and arg['frame'].get('status'), 'incomplete native typed argument')
        if arg.get('literal'):
            require(arg['literal']['kind']=='reserved_zero' and arg['literal'].get('meaning'), 'literal without typed meaning')
            require(arg['literal']['resolved_type']==arg['resolved_type'], 'literal type differs from site')
    # Check every zero in the exported AST, including comparisons, before
    # allowing any subset of definitions to be marked literal-complete.
    for path,node in nodes.items():
        if node['kind']=='label' and node['data'].get('use')=='reserved_zero':
            if path in args:
                require(args[path].get('literal'), 'zero argument lacks meaning')
            else:
                parent=path[:-1]
                require(parent in comparisons and comparisons[parent]['second'].get('literal'), 'changed/shown zero lacks native meaning')
    prefixes=[clause[:1]]
    if context:
        prefixes.extend(d['node']['path'] for d in context['forms'])
    selected=lambda path:any(path[:len(p)]==p for p in prefixes)
    literals=[dict(site=s,node=nodes[p]) for p,s in args.items() if s.get('literal') and selected(list(p))]
    variables=[dict(site=s,node=nodes[p]) for p,s in args.items() if selected(list(p)) and list(p)[:len(clause)]==clause]
    if 'variables' in typed:
        variables=[];seen=set()
        for v in typed['variables']:
            key=(tuple(v['scope_path']),v['label_id'])
            require(key not in seen and v['resolved_type'] and v['frame'].get('status'),'incomplete/duplicate native scoped variable')
            seen.add(key)
            for occurrence in v['occurrences']:
                require(tuple(occurrence['path']) in nodes,'scoped variable occurrence absent from AST')
            if v['scope_path']==clause[:1] or any(o['path'][:len(clause)]==clause for o in v['occurrences']):
                variables.append(dict(site=v,node=dict(sexp=v['label_spelling'])))
    constraints=[dict(site=c,node=nodes[p]) for p,c in comparisons.items() if selected(list(p))]
    return dict(literals=literals,variables=variables,comparisons=constraints,
                static_types_complete=True,made_frames_status=export['parts'].get('types_frames','pending'))


def frame_text(frame):
    status=frame['status']
    if status=='not_applicable':return 'no geometric frame required'
    if status=='contextual_reserved_zero':return frame['meaning']
    if status=='not_established_by_native_grid_analysis':return 'frame not established by static checker (native table frame shown below)'
    require(status=='established','unknown native frame status')
    result=[]
    for grid in frame['grids']:
        example=grid['example']
        result.append(grid['kind']+' frame of '+('current example' if example['kind']=='current' else 'example label '+str(example['label_id'])))
    return '; '.join(result)


def native_frames(sources, names):
    def frame(f,source):
        if f['kind']=='native_unknown':return 'native frame unknown: '+f['reason']
        if f['kind']=='read_source_column_frame':
            name=source.get('source_relation_name')
            column=source['source_column']
            return 'frame read from '+names.get(name,name or 'native source')+(' column '+str(column['index']) if column['kind']=='position' else ' entry example' if column['kind']=='entry_example' else '')
        require(f['kind']=='made','unsupported native frame expression')
        made='frame made by '+f['maker']['registry_id']+' at AST '+'.'.join(map(str,f['path']))
        if f.get('within'):made+=' within '+frame(f['within'],source)
        return made
    result=[]
    for source in sources:
        for f in source['frames']:
            text=frame(f,source)
            if text not in result:result.append(text)
    return '; '.join(result) if result else 'native sources provide no independently named frame'
