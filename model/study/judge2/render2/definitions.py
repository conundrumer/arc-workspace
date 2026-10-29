"""Follow resolver edges, never relation-looking tokens in engine text."""
from native import require


def under(path, parent):
    return path[:len(parent)] == parent


def context(export, owner, *, downstream_only=False):
    if export['parts'].get('definitions_readers') != 'complete':
        return None
    definitions = export['definitions']
    graph = {n['node']:n for n in definitions['graph_nodes']}
    nodes = {tuple(n['path']):n for n in export['nodes']}
    registry = {e['id']:e for e in definitions['registry']['entries']}
    require(len(graph)==len(definitions['graph_nodes']), 'duplicate resolver graph IDs')
    for n in graph.values():
        require(all(i in graph for i in n['reads']), 'resolver read has no definition')
        require(all(tuple(p) in nodes for p in n['forms']), 'definition AST path missing')
    seeds = {i for i,n in graph.items() if any(under(p,owner) or under(owner,p) for p in n['forms'])}
    require(seeds, 'changed owner absent from resolver graph')
    downstream = set(seeds)
    while True:
        more = {i for i,n in graph.items() if set(n['reads']) & downstream}
        if more <= downstream:break
        downstream.update(more)
    selected = downstream | {i for i,n in graph.items() if n['definition']['kind']=='out'}
    pending = list(selected)
    while pending:
        i=pending.pop()
        for read in graph[i]['reads']:
            if read not in selected:selected.add(read);pending.append(read)
    # Top-level engine-written definitions retain their INIT subports/keys.
    form_paths = {tuple(p[:1]) for i in (downstream if downstream_only else selected) for p in graph[i]['forms'] if p}
    require(all(p in nodes for p in form_paths), 'missing defining top-level AST node')
    forms = [dict(node=nodes[p], downstream=any(i in downstream and any(tuple(q[:1])==p for q in graph[i]['forms']) for i in graph))
             for p in sorted(form_paths) if p != tuple(owner[:1])]
    libraries = set()
    for reader in definitions['readers']:
        if not any(under(reader['reader_path'],list(p)) for p in form_paths | {tuple(owner[:1])}):continue
        resolved=reader['resolution']
        if resolved['kind']=='library':
            require(resolved['id'] in registry, 'named library relation has no definition')
            libraries.add(resolved['id'])
        elif resolved['kind']=='graph_node':
            require(resolved['node'] in selected, 'named relation missing from supplied read closure')
        else:
            raise ValueError('named relation has no resolved definition: '+str(reader))
    # Fact definitions are graph nodes rather than library readers.
    facts={'Input':'input','ExInput':'ex_input','ExOutput':'ex_output'}
    for i in selected:
        definition=graph[i]['definition']
        if definition['kind']=='fact':
            fact=definition['relation']['fact']
            require(fact in facts,'unknown native fact kind')
            libraries.add('fact:'+facts[fact])
    pending=list(libraries)
    while pending:
        key=pending.pop()
        require(key in registry, 'library dependency lacks definition: '+key)
        for read in registry[key]['reads']:
            if 'lib' in read:child='lib:'+read['lib']
            elif 'fact' in read:
                require(read['fact'] in facts,'unknown native library fact')
                child='fact:'+facts[read['fact']]
            else:
                raise ValueError('unsupported library-local read requires native definition: '+str(read))
            require(child in registry, 'library read lacks definition: '+child)
            if child not in libraries:libraries.add(child);pending.append(child)
    return dict(forms=forms, libraries=[registry[k] for k in sorted(libraries)],
                graph_nodes=[graph[i] for i in sorted(selected)], complete_definitions=not downstream_only,
                definition_scope='downstream_only' if downstream_only else 'read_closure')
