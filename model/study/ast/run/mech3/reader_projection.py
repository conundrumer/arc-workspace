"""Exact native reader projections. No engine execution or name/ordinal joins.

One projection per reader atom, preserving its joint tuple. INIT has one
canonical component-input interface reader. Native graph ids stay within one
export; the unchanged reader AST and public row paths bind the two sides.
"""
if __package__:
    from .common import digest
else:
    from common import digest


class Unavailable(ValueError):pass


def require(value,message):
    if not value:raise Unavailable(message)


def compatible(*types):
    from tables import comparison_type
    return len({comparison_type(t) for t in types})==1


def part(value):
    if value.get('kind')=='written' or set(value)=={'name'}:
        require(isinstance(value.get('name'),str),'native written field identity missing')
        return ('written',value['name'])
    if value.get('kind')=='slot' or set(value)=={'slot'}:
        require(type(value.get('slot')) is int,'native slot field identity missing')
        return ('slot',value['slot'])
    raise Unavailable('unsupported native column identity')


def row_path(value):
    require(isinstance(value,list),'native row path missing')
    return tuple(part(p) for p in value)


def read_paths(site,prefix=()):
    """Read native Site/NamedLabel structure, never a printed label spelling."""
    path=prefix+(part(site['column']),)
    for argument in site['args']:
        if 'site' in argument:yield from read_paths(argument['site'],path)
        elif 'field' in argument:
            yield path+(part(argument['field']),)
        else:
            require(len(site['args'])==1,'multiple unnamed site arguments lack native field identity')
            yield path


def field_identity(field):
    identity=field.get('native_label_identity',{})
    scope=identity.get('scope_path',identity.get('owner_path'))
    return (tuple(scope or ()),identity.get('label_id'))


def binding_field(binding,witness,point):
    """Follow native header bindings to one scoped BODY column, or Unit."""
    if witness['type']=='Unit' and witness.get('status')=='declared_without_local_label':
        require(witness.get('proof') in ('declared_layout','resolved_row_path'),
                'read Unit lacks native declared layout/projection proof')
        return None,dict(header=witness,type='Unit',constant='native implicit Unit',
            unit_projection_certificate=dict(schema='mech3-native-unit-projection-v1',
                native_header=witness,source_body_column=None,proof=witness['proof'],
                projection_helper='judge2/render2/body.py:project_entries',
                meaning='native declared Unit without local label; canonical projector supplies the unique Unit'))
    require(witness.get('status')=='resolved' and witness.get('proof') in
            ('resolver_label_position','declared_layout','resolved_row_path'),
            'read native header placement/proof is unavailable')
    candidates=[b for b in witness.get('bindings',[]) if b.get('body_path')==point and b.get('status')=='resolved']
    selected=witness.get('selected_header_binding')
    if selected and selected.get('body_path')==point and selected.get('status')=='resolved':
        require(selected in witness['bindings'],'selected header binding is not in native bindings')
        candidates.append(selected)
    unique={(tuple(b['scope_path']),b['label_id']):b for b in candidates}
    require(len(unique)==1,'read field lacks a unique native binding at this BODY')
    identity,proof=next(iter(unique.items()))
    require(proof.get('proof') in ('resolver_label_position','declared_layout','resolved_row_path'),
            'scoped BODY binding proof is unavailable')
    matches=[f for f in binding['projected_schema'] if field_identity(f)==identity]
    require(len(matches)==1,'read field lacks one scoped physical BODY column')
    field=matches[0]
    from native_correspondence import canonical_bound_field_type
    require(compatible(canonical_bound_field_type(field),witness['type'],proof['field_type']),'reader/header/BODY types disagree')
    return field['source_body_column'],dict(header=witness,binding=proof,body_field=field)


def relation_field(binding,witness,point):
    """Place a read header column in the DET relation's own table, for a DET whose BODY has no column.

    The rows of such a DET come from its lib proposer, so no BODY column can hold the field. The native header
    places the field at its physical column of the DET relation by the DET's declared layout or row path; the
    relation's native table under each kept assignment gives its values."""
    require(binding['projected_schema']==[],'relation-table DET projection requires a BODY without columns')
    require(witness.get('status')=='declared_without_local_label' and witness.get('bindings')==[]
            and witness.get('selected_header_binding') is None
            and witness.get('proof') in ('declared_layout','resolved_row_path')
            and type(witness.get('physical_column')) is int and witness['physical_column']>=0,
            'read DET relation column lacks native declared placement')
    return None,dict(header=witness,type=witness['type'],relation_column=witness['physical_column'],
        proof=witness['proof'],meaning='DET relation column without a BODY column; values from the DET relation table')


def side_readers(export,binding,point,*,field=binding_field):
    """The native readers of the DET at `point`, each read field placed by `field`: a BODY column by
    `binding_field`, or a column of the DET relation's own table by `relation_field`."""
    from definition_binding import definition_node
    require(export['parts'].get('definitions_readers')=='complete','native resolved reader inventory incomplete')
    nodes={tuple(n['path']):n for n in export['nodes']}
    owner=tuple(binding['owner_path'])
    owners=[n for p,n in nodes.items() if p==owner]
    require(len(owners)==1 and owners[0]['kind']=='clause','reader mapper requires native RULE/DET clause owner')
    defines=owners[0]['data']['defines']
    definitions=[d for d in export['definitions']['native_relations'] if d['relation']==defines]
    require(len(definitions)==1,'changed clause lacks one native output definition')
    definition=definitions[0];node=definition_node(export,definition)
    require(definition.get('column_witness_status')=='complete','native output field witnesses incomplete')
    headers=definition['column_witnesses'];result={}
    for reader in export['definitions']['readers']:
        resolution=reader['resolution']
        if resolution.get('kind')!='graph_node' or resolution.get('node')!=node:continue
        path=tuple(reader['reader_path'])
        # Recursive reads inside the changed owner require separate recursion
        # semantics; don't claim an unchanged downstream observation there.
        require(path[:len(owner)]!=owner,'recursive reader inside changed clause needs explicit correspondence')
        atom=nodes.get(path)
        # A RIGID_DET instance row is a bare atom: its export has no conjunct tag.
        require(atom is not None and atom['kind'] in ('atom','not')
                and atom['data'].get('node',atom['kind']) in ('atom','not_atom'),
                'native resolved reader lacks an atom or NOT atom export')
        paths=tuple(p for s in atom['data']['sites'] for p in read_paths(s))
        fields=[]
        for read in paths:
            found=[w for w in headers if row_path(w.get('row_path'))==read]
            require(len(found)==1,'reader site does not identify one native scalar header field')
            witness=found[0];index,proof=field(binding,witness,point)
            fields.append(dict(row_path=list(read),physical_index=index,type=witness['type'],proof=proof))
        # Dedup repeated occurrences of one field, retaining the native path.
        unique={tuple(tuple(v) for v in f['row_path']):f for f in fields}
        key=digest(dict(reader_path=path,relation=defines))
        require(key not in result,'duplicate native reader occurrence')
        result[key]=dict(reader_path=list(path),relation=defines,atom=atom['data'],
            fields=[unique[k] for k in sorted(unique)],resolution=reader['resolution'])
    return result


def pair_readers(record,exports,bindings,*,side_cache=None):
    """Return paired exact physical projections, or a named unavailable cause."""
    require(record.get('audit',{}).get('outside_atoms_unchanged') is True,
            'source lacks native unchanged-outside-body audit')
    kind=bindings['gold']['kind']
    if kind.startswith('INIT'):
        g=bindings['gold'];x=bindings['mutant']
        gf={row_path(f['callable_row_path']):f for f in g['projected_schema']}
        xf={row_path(f['callable_row_path']):f for f in x['projected_schema']}
        require(len(gf)==len(g['projected_schema']) and len(xf)==len(x['projected_schema']),
                'component input has ambiguous native field paths')
        require(gf.keys()==xf.keys(),'gold/mutant component input interfaces differ')
        fields=[]
        for p in sorted(gf):
            a,b=gf[p],xf[p]
            fields.append(dict(row_path=list(p),gold=a['source_body_column'],mutant=b['source_body_column'],
                type=a['type'],gold_type=a['type'],mutant_type=b['type'],gold_identity=a['native_label_identity'],mutant_identity=b['native_label_identity']))
        return dict(schema='mech3-reader-projection-v1',complete=True,readers=[dict(kind='component_input_interface',
            reader_path=g['body_path'],fields=fields,gold_binding=g,mutant_binding=x)],source_sha256=digest(record),
            policy='canonical projected key/port tuple is one direct interface reader; private witnesses excluded')
    sides={}
    for side in ('gold','mutant'):
        key=None
        if side=='gold' and side_cache is not None:
            key=digest(dict(task=record['task'],case=record['case'],program=record['gold_sexp'],binding=bindings[side]))
        if key is not None and key in side_cache:sides[side]=side_cache[key]
        else:
            sides[side]=side_readers(exports[side],bindings[side],record['point'])
            if key is not None:
                side_cache[key]=sides[side]
                while len(side_cache)>64:side_cache.pop(next(iter(side_cache)))
    require(sides['gold'].keys()==sides['mutant'].keys(),'resolved reader inventories differ across mutation')
    result=[]
    for key,g in sides['gold'].items():
        x=sides['mutant'][key]
        require(g['atom']==x['atom'],'reader atom changed outside selected mutation body')
        gm={tuple(tuple(p) for p in f['row_path']):f for f in g['fields']}
        xm={tuple(tuple(p) for p in f['row_path']):f for f in x['fields']}
        require(gm.keys()==xm.keys(),'reader field identities differ across programs')
        fields=[]
        for p in sorted(gm):
            a,b=gm[p],xm[p]
            fields.append(dict(row_path=list(p),gold=a['physical_index'],mutant=b['physical_index'],
                               type=a['type'],gold_type=a['type'],mutant_type=b['type'],gold_proof=a['proof'],mutant_proof=b['proof']))
        result.append(dict(kind='resolved_reader_atom',reader_path=g['reader_path'],fields=fields,
                           gold_receipt=g,mutant_receipt=x))
    return dict(schema='mech3-reader-projection-v1',complete=True,readers=result,source_sha256=digest(record),
                policy='per-reader joint projection; never union fields from unrelated reader atoms')


def reader_header_union(readers):
    """Select actual reader-named native headers, retaining distinct aliases."""
    chosen={}
    for reader in readers:
        for field in reader['fields']:
            proof=field['proof'];header=proof.get('header')
            require(header is not None,'read field lacks its complete native header identity')
            key=row_path(header['row_path'])
            column=dict(row_path=header['row_path'],header_physical_column=header['physical_column'],
                source_body_column=field['physical_index'],type=header['type'],native_header=header,
                scoped_binding=proof.get('binding'),body_field=proof.get('body_field'),
                unit_projection_certificate=proof.get('unit_projection_certificate'))
            if key in chosen:
                require({k:v for k,v in chosen[key].items() if k!='reader_paths'}==column,
                        'reader aliases disagree on one native header binding')
            else:
                chosen[key]=dict(column,reader_paths=[])
            chosen[key]['reader_paths'].append(reader['reader_path'])
    require(chosen or not readers,'empty DET projection has readers but no certified named scalar fields')
    columns=sorted(chosen.values(),key=lambda f:f['header_physical_column'])
    require(len({c['header_physical_column'] for c in columns})==len(columns),
            'native header physical identity has distinct public paths')
    return columns


def det_transport(record,exports,bindings):
    """Canonical DET target selection receipt for MetadataProducer consumers.

    The approved DET target is the union of actual reader-named declared HEADER
    fields. Keep distinct header aliases even when they bind the same BODY
    LabelId. This target union does not change the per-reader attribute policy.
    Formatting the callable and projecting rows remain shared-owner operations.
    """
    require(bindings['gold']['kind'].casefold()=='det','DET transport requested for another point kind')
    projection=pair_readers(record,exports,bindings)
    sides={}
    for side in ('gold','mutant'):
        columns=reader_header_union([r[side+'_receipt'] for r in projection['readers']])
        sides[side]=dict(raw_binding=bindings[side],columns=columns,
            program_sha256=digest(record[side+'_sexp']),export_sha256=digest(exports[side]))
    return dict(schema='mech3-det-header-projection-v1',source_sha256=digest(record),
        complete=True,body_path=record['point'],sides=sides,
        no_readers_proof=dict(complete=True,count=len(projection['readers']),
                              exports_complete=True) if not projection['readers'] else None,
        reader_projection=projection,
        policy='union of reader-named declared header identities; distinct aliases retained; private/unread columns excluded')
