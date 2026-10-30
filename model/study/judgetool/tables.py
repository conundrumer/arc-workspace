"""Complete train/test table acquisition and the shared equality comparator."""
import ast
from collections import Counter
import itertools
from pathlib import Path
import re
import time

_PROJECT=None


def projected_rows(L,rows,indices):
    """Use the producer's one project_entries implementation, without loading
    its separately pinned renderer reader into filters' reader namespace."""
    global _PROJECT
    if _PROJECT is None:
        source=Path(__file__).resolve().parent.parent/'judge2/render2/body.py'
        tree=ast.parse(source.read_text(),str(source))
        function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='project_entries')
        namespace={'require':L.native.__globals__['_NATIVE'].require}
        exec(compile(ast.Module(body=[function],type_ignores=[]),str(source),'exec'),namespace)
        _PROJECT=namespace['project_entries']
    raw=[list(dict(value=list(c)) for c in row) for row in rows]
    projected=_PROJECT(dict(entries=[dict(example='task',choice=0,model=0,rows=raw)]),indices)[0]['rows']
    return tuple(sorted({tuple(tuple(c['value']) for c in row) for row in projected}))


class Incomplete(ValueError):
    pass


def task_output_rows(grid):
    """Encode a valid task grid as native Position/Color rows, else None."""
    if (not isinstance(grid,list) or not grid or not all(isinstance(row,list) and row for row in grid)
            or len({len(row) for row in grid})!=1
            or any(type(c) is not int or not 0<=c<=9 for row in grid for c in row)):
        return None
    h,w=len(grid),len(grid[0])
    return frozenset(((r,h-r-1,c,w-c-1),(grid[r][c],)) for r in range(h) for c in range(w))


def axis_receipt(grouped):
    """Exact native-group axes in their own case-local assignment namespace."""
    return dict(required_axes=[list(k) for k in sorted(grouped['required'])],
                present_axes=[list(k) for k in sorted(grouped['groups'])],
                missing_axes=[list(k) for k in grouped['missing']])


def comparison_type(name):
    """The shared comparison schema treats Position and Box as four margins."""
    return 'Box' if name in ('Position','Box') else name


def decode_kept(L,kept,det_relations,det_types,skip=()):
    """Adapt stored ``slot N`` and fresh ``&rN`` identities to P's decoder.

    Native row decoding and prefix compatibility remain in the canonical P
    helper. Return keys in this table's own namespace, never guessed ordinals.
    """
    def canonical(name):
        match=re.fullmatch(r'(?:slot |&r)([0-9]+)',name)
        if not match:raise Incomplete('unsupported DET slot identity: '+str(name))
        return '&r'+str(int(match[1]))
    if len(det_relations)!=len(det_types):raise Incomplete('native DET schema identity/type count differs')
    skipped=set(skip)
    active=[(name,ty) for name,ty in zip(det_relations,det_types) if name not in skipped]
    aliases={canonical(name):name for name,_ in active}
    if len(aliases)!=len(active):raise Incomplete('ambiguous native DET slot aliases')
    adapted=[dict(item,relation='slot '+canonical(item['relation'])[2:]) for item in kept]
    # A certified inserted DET derives its own value. It must never replace a
    # saved original held slot, even when its spelling is a canonical &rN.
    held={canonical(item['relation']) for item in kept}
    if any(re.fullmatch(r'(?:slot |&r)[0-9]+',name) and canonical(name) in held for name in skipped):
        raise Incomplete('inserted DET identity collides with an original held slot')
    decoded=L.decode_kept(adapted,[canonical(name) for name,_ in active],[ty for _,ty in active])
    return {aliases[name]:value for name,value in decoded.items()}


def compatible_kept(L,entry_assignment,want,det_relations,det_types,*,seconds=10):
    """One Ident renaming across every held DET slot, using _id_equal.

    P decodes held values; native reader decodes entries. Tag their flat prefix
    rows by slot and non-Ident contents, then compare one relational structure.
    Padding has an explicit arity tag, so its private sentinel cannot match a
    real Ident. No values from separate entries/models are combined.
    """
    have=dict(entry_assignment);types=dict(zip(det_relations,det_types))
    if not set(want)<=have.keys():return False
    plans=[];maximum=0
    for slot,name in enumerate(sorted(want)):
        rows,width=want[name];positions=[];at=0
        for ty in types[name]:
            if at>=width:break
            if ty=='Ident':positions.append(at)
            at+=4 if ty in L.BOXES else 1
        if at!=width:raise Incomplete('held DET prefix does not end at a physical column boundary')
        plans.append((slot,name,rows,width,positions))
        maximum=max(maximum,len(positions))
    if L.compatible(entry_assignment,want):return True
    left=[];right=[]
    for slot,name,rows,width,positions in plans:
        for collection,values in ((left,rows),(right,have[name])):
            for row in values:
                flat=tuple(L.flat(row)[:width])
                if len(flat)!=width:raise Incomplete('native DET row shorter than held prefix')
                ids=tuple(flat[i] for i in positions)
                rest=tuple(v for i,v in enumerate(flat) if i not in positions)
                collection.append(((slot,len(ids))+rest,ids))
    ids=[v for collection in (left,right) for _,values in collection for v in values]
    sentinel=min(ids,default=0)-1
    def encode(collection):
        return frozenset((tag,)+tuple((v,) for v in values)+((sentinel,),)*(maximum-len(values))
                         for tag,values in collection)
    return _id_equal(encode(left),encode(right),['Number']+['Ident']*maximum,time.monotonic()+seconds)


def read_table(L,n,t,*,example_kinds=None,entry_ids=None):
    reader=n['_native_reader']; entries=[]
    for index in reader.bytable[t]:
        if entry_ids is not None and index not in entry_ids:continue
        if example_kinds is not None and reader.entries['example_kind'][index] not in example_kinds:continue
        e=reader.entry(index,with_extents=False,projection_stop=False)
        entries.append(dict(entry=index,example=(e['example_kind'],e['example_index']),model=e['model'],
            assignment=tuple(sorted((d['relation'],tuple(tuple(r) for r in d['rows'])) for d in e['assignment'])),
            rows=tuple(sorted({tuple(tuple(c['value']) for c in row) for row in e['rows']}))))
    return entries


def kept_groups(L,n,t,record,ntrain,ntest,indices=None,*,unheld=()):
    ts=n['tables']
    return kept_entries(L,read_table(L,n,t),ts['det_relations'][t],ts['det_types'][t],record,ntrain,ntest,indices,unheld=unheld)


def kept_entries(L,entries,det_relations,det_types,record,ntrain,ntest,indices=None,*,held_entries=None,unheld=()):
    """Same kept selection for lossless cached read_table entries (no decoder)."""
    wants=[decode_kept(L,k,det_relations,det_types,skip=unheld) for k in record['evaluation']['kept_assignments']]
    slots=set(det_relations)-set(unheld); groups={}; contexts=[]; others=[];memo={}
    for e in entries:
        assignment=tuple((name,tuple(tuple(r) for r in rows)) for name,rows in e['assignment'])
        if assignment not in memo:
            if len(memo)>=128:memo.clear()
            memo[assignment]=[a for a,w in enumerate(wants) if set(w)==slots and compatible_kept(
                L,assignment,w,det_relations,det_types)]
        matching=memo[assignment]
        if held_entries is not None:
            if e['entry'] not in held_entries:raise Incomplete('native BODY entry lacks exact full-kept map')
            matching=[a for a in matching if a in held_entries[e['entry']]]
        if not matching:
            others.append(e); continue
        rows=tuple(tuple(tuple(c) for c in row) for row in e['rows']) if indices is None else projected_rows(L,e['rows'],indices)
        contexts.append(dict(e,kept_assignments=matching))
        kind,index=e['example']
        examples=[(1,i) for i in range(ntrain)]+[(2,i) for i in range(ntest)] if kind==0 else [(kind,index)]
        for a in matching:
            for kind,index in examples:
                groups.setdefault((a,kind,index),set()).add(frozenset(rows))
    wanted={(a,kind,i) for a in range(len(wants)) for kind,count in ((1,ntrain),(2,ntest)) for i in range(count)}
    if not wanted:
        raise Incomplete('empty required assignment/example axis')
    missing=sorted(wanted-groups.keys())
    return dict(groups=groups,missing=missing,contexts=contexts,other_contexts=others,
                det_relations=det_relations,required=wanted)


def full_kept_matches(L, choices, schemas, record):
    """Joint full-DET Ident match; native ordinals never inferred from subsets."""
    relations=[d['source_name'] for d in schemas];types=[d['types'] for d in schemas]
    entries=[]
    for i,values in enumerate(choices):
        decoded=decode_kept(L,values,relations,types)
        if set(decoded)!=set(relations):raise Incomplete('native FITS receipt lacks a full held assignment')
        entries.append(dict(entry=i,example=(0,0),model=0,
            assignment=tuple((name,rows) for name,(rows,width) in sorted(decoded.items())),rows=()))
    matched=kept_entries(L,entries,relations,types,record,1,0)
    if matched['missing']:raise Incomplete('native gold FITS receipt lacks a saved full kept context')
    return {e['entry']:e['kept_assignments'] for e in matched['contexts']}


def _id_equal(a,b,types,deadline,*,subset=False):
    """Exact finite relational isomorphism, preserving one consistent Ident bijection."""
    if len(a)>len(b) if subset else len(a)!=len(b):return False
    ids=[i for i,t in enumerate(types) if t=='Ident']
    if not ids:return a<=b if subset else a==b
    left=set(c[0] for r in a for i,c in enumerate(r) if i in ids)
    right=set(c[0] for r in b for i,c in enumerate(r) if i in ids)
    if len(left)>len(right) if subset else len(left)!=len(right):return False
    def signature(rows,v):
        return tuple(sorted(Counter((i,tuple((j,c) for j,c in enumerate(r) if j not in ids))
                            for r in rows for i in ids if r[i][0]==v).items()))
    ls={v:signature(a,v) for v in left}; rs={v:signature(b,v) for v in right}
    choices={v:[w for w in right if (Counter(dict(ls[v]))<=Counter(dict(rs[w])) if subset else rs[w]==ls[v])] for v in left}
    if any(not values for values in choices.values()):return False
    order=sorted(left,key=lambda v:len(choices[v])); mapping={}; used=set()
    def walk(at):
        if time.monotonic()>deadline:raise Incomplete('component-id comparison reached its time bound')
        if at==len(order):
            mapped=frozenset(tuple((mapping[c[0]],) if i in ids else c for i,c in enumerate(r)) for r in a)
            return mapped<=b if subset else mapped==b
        v=order[at]
        for w in choices[v]:
            if w in used:continue
            mapping[v]=w;used.add(w)
            # Prune every fully mapped row, rather than enumerating permutations blindly.
            okay=True
            for r in a:
                if all(r[i][0] in mapping for i in ids):
                    mapped=tuple((mapping[c[0]],) if i in ids else c for i,c in enumerate(r))
                    if mapped not in b:okay=False;break
            if okay and walk(at+1):return True
            used.remove(w);del mapping[v]
        return False
    return walk(0)


def _family_equal(a,b,types,deadline,*,contains=False):
    # Families are sets of row sets, independent of model ordinal. Renamings
    # are validated per model; duplicate isomorphic models have one meaning.
    def matches(x,y):
        return _id_equal(y,x,types,deadline,subset=True) if contains else _id_equal(x,y,types,deadline)
    return (all(any(matches(x,y) for y in b) for x in a)
            and all(any(matches(x,y) for x in a) for y in b))


def compare(candidate,columns,target,fields,*,explicit=None,seconds=10,relation='equal'):
    """Names first, otherwise type-compatible fixed column choices across ALL inputs."""
    if relation not in ('equal','contains'):raise ValueError('unsupported comparison relation')
    success='equal' if relation=='equal' else 'contains'
    names=[c[0] for c in columns]; types=[c[1] for c in columns]
    target_names=[c.get('field_name',c.get('name')) for c in fields]
    target_types=[c['type'] for c in fields]
    kind=comparison_type
    def valid(choice):
        return len(choice)==len(fields) and all(kind(types[i])==kind(t) for i,t in zip(choice,target_types))
    if explicit is not None:
        try: choices=iter([tuple(names.index(label) for label in explicit)])
        except ValueError:return dict(status='mismatch',reason='explicit output label absent')
    else:
        by_name=tuple(names.index(n) for n in target_names) if all(n in names for n in target_names) else None
        def options():
            if by_name is not None and valid(by_name):
                yield by_name
                return
            domains=[([names.index(n)] if n is not None and n in names else [i for i,t in enumerate(types) if kind(t)==kind(w)])
                     for n,w in zip(target_names,target_types)]
            for choice in itertools.product(*domains):
                if len(set(choice))==len(choice) and choice!=by_name:yield choice
        choices=options()
    if explicit is not None:
        try:selection=tuple(names.index(label) for label in explicit)
        except ValueError:return dict(status='mismatch',reason='explicit output label absent')
        if not valid(selection):return dict(status='mismatch',reason='output column types or arity differ')
    elif any(not any(kind(t)==kind(w) for t in types) for w in target_types):
        return dict(status='mismatch',reason='output column types differ')
    keys=set(target)
    if not keys or not keys<=candidate.keys():
        return dict(status='unknown',reason='required target/candidate context missing')
    deadline=time.monotonic()+seconds; attempted=0;best=None
    try:
        for choice in choices:
            if time.monotonic()>deadline:raise Incomplete('column comparison reached its time bound')
            if not valid(choice):continue
            attempted+=1
            equal={}
            for key in sorted(keys):
                projected={frozenset(tuple(row[i] for i in choice) for row in rows) for rows in candidate[key]}
                equal[key]=_family_equal(projected,target[key],target_types,deadline,contains=relation=='contains')
            train=all(v for k,v in equal.items() if k[1]==1)
            test=all(v for k,v in equal.items() if k[1]==2)
            differences=[]
            for key,matched in equal.items():
                if matched:continue
                assignment,example_kind,index=key
                detail=dict(assignment=assignment,example=('train' if example_kind==1 else 'test')+str(index+1))
                if example_kind!=2:
                    detail.update(candidate_rows=sorted({len({tuple(row[i] for i in choice) for row in rows}) for rows in candidate[key]}),
                                  target_rows=sorted({len(rows) for rows in target[key]}))
                differences.append(detail)
            current=dict(train='equal' if train else 'mismatch',test='equal' if test else 'mismatch',
                         columns=[names[i] for i in choice],indices=list(choice),differences=differences)
            if best is None or train and best['train']!='equal':best=current
            if all(equal.values()):
                return dict(status=success,relation=relation,columns=[names[i] for i in choice],indices=list(choice),choices_tried=attempted,
                            train='equal',test='equal')
    except Incomplete as error:return dict(status='unknown',reason=str(error),choices_tried=attempted)
    return dict(status='mismatch',choices_tried=attempted,**(best or {}))


def contains(candidate,columns,target,fields,**kwargs):
    """Every model on each side has a containing/contained counterpart.
    A fixed physical column map and injective target->candidate Ident map
    are checked by the SAME bounded relational comparator. No union of models.
    """
    return compare(candidate,columns,target,fields,relation='contains',**kwargs)


class TargetStore:
    def __init__(self,L,root):
        self.L=L; self.root=Path(root);self.cache={}
        import sys
        sys.path.insert(0,str(self.root/'ast/run'))
        from native_storage import load_native
        self.load_native=load_native

    def snapshot(self,ref,base):
        key=(str(Path(base).resolve()),str(ref))
        if key not in self.cache:self.cache[key]=self.L.native(self.load_native(ref,Path(base).resolve()))
        return self.cache[key]

    def selector_snapshot(self,record,base,identity):
        """Resolve a stored selector in the snapshot that supplied its proof.

        Only the mechanical inventory's explicit DET-independent fact fallback
        selects the compact gold snapshot. Other selectors use full gold replay.
        No table index is transferred between these sources.
        """
        fallback=identity.get('proof')=='det_independent_native_fact'
        if fallback and identity.get('fact')!='ex_input':
            raise Incomplete('unsupported stored selector fallback proof')
        ref=record['native']['gold'] if fallback else record['full_replay']['gold']
        native=self.snapshot(ref,base);ts=native['tables'];table=identity['table']
        if not 0<=table<len(ts['form']):raise Incomplete('stored selector table index absent in its source')
        if identity.get('fact'):
            if ts['fact'][table]!=identity['fact']:raise Incomplete('stored selector fact identity differs')
        elif (str(ts['form'][table])!=str(identity['form'])
              or ts['relation'][table]!=identity['relation']):
            raise Incomplete('stored selector table identity differs')
        if fallback and ts['det_relations'][table]:
            raise Incomplete('stored fact fallback is not DET-independent')
        return native,table,dict(native_ref=ref,table=table,identity=identity,
            source='native_gold_fact_fallback' if fallback else 'gold_full_replay')

    def target(self,record,adapter,binding,ntrain,ntest):
        # FULL replay is the source for target test data; compact display
        # projected_entries are never substituted for missing full evidence.
        full=adapter['comparison_target'].get('full_replay_body',{})
        ref=full.get('native_ref',record['full_replay']['gold'])
        native=self.snapshot(ref,adapter['source']['native_base'])
        ts=native['tables']; selector=full.get('native_selector',binding['native_selector'])
        matches=[t for t in range(len(ts['form'])) if all(str(ts[k][t])==str(v) for k,v in selector.items() if k in ('form','point','relation','fact'))]
        if len(matches)!=1:raise Incomplete('gold full-replay body selector is missing or ambiguous')
        t=matches[0]
        indices=full.get('projection_indices',[f['source_body_column'] for f in binding['projected_schema']])
        # Shared producer has already resolved LabelIds/key/port/Unit to these
        # physical columns. No second INIT layout policy is applied here.
        grouped=kept_groups(self.L,native,t,record,ntrain,ntest,indices)
        if grouped['missing']:raise Incomplete('gold full replay lacks compatible target train/test entries')
        return grouped,dict(native_ref=ref,selector=selector,table=t,
                            projection=indices,fields=binding['projected_schema'])

    def reference(self,record,adapter,reference,ntrain,ntest):
        ref=reference['native_ref']; native=self.snapshot(ref,reference.get('native_base',adapter['source']['native_base']));ts=native['tables']
        selector=reference.get('native_selector',reference.get('definition',{}).get('native_selector'))
        if not selector and reference.get('native_table_index') is None:raise Incomplete('comparison reference has no exact selector')
        matches=[t for t in range(len(ts['form'])) if all(str(ts[k][t])==str(v) for k,v in (selector or {}).items() if k in ('form','point','relation','fact'))]
        if reference.get('native_table_index') is not None:
            matches=[t for t in matches if t==reference['native_table_index']]
        if len(matches)!=1:raise Incomplete('comparison reference missing or ambiguous')
        t=matches[0]; grouped=kept_groups(self.L,native,t,record,ntrain,ntest)
        if grouped['missing']:raise Incomplete('comparison reference lacks compatible contexts')
        labels=ts.get('column_labels',ts['column_names'])[t]
        fields=[dict(field_name=(label or name),type=ty) for label,name,ty in zip(labels,ts['column_names'][t],ts['column_types'][t])]
        return grouped,fields

    def input_facts(self,record,adapter,ntrain):
        native=self.snapshot(record['full_replay']['gold'],adapter['source']['native_base']);ts=native['tables']
        found={}
        for name in ('ex_input','ex_output'):
            matches=[t for t,fact in enumerate(ts['fact']) if fact==name]
            if len(matches)!=1:raise Incomplete('missing native fact '+name)
            t=matches[0];g=kept_groups(self.L,native,t,record,ntrain,0)
            # No test output is exposed or used for continuation acceptance.
            train={k:v for k,v in g['groups'].items() if k[1]==1}
            if any(k not in train for k in g['required']):raise Incomplete('native fact train context missing')
            fields=[dict(field_name=n,type=ty) for n,ty in zip(ts['column_names'][t],ts['column_types'][t])]
            found[name]=(train,fields)
            if name=='ex_input':
                indices=[i for i,f in enumerate(fields) if f['type']!='Example']
                found['input']=({k:{frozenset(tuple(r[i] for i in indices) for r in rows) for rows in family}
                                  for k,family in train.items()},[fields[i] for i in indices])
        return found

    def mutant_snapshot(self,record,adapter):
        """Exact authenticated X source/index; ALL and KEPT can share a selector."""
        binding=adapter['input']['binding']
        ref=binding['native_ref']
        if ref!=record['native']['mutant']:
            raise Incomplete('X binding native reference differs from the source record')
        native=self.snapshot(ref,adapter['source']['native_base']);ts=native['tables']
        table=binding['native_table_index'];selector=binding['native_selector']
        if type(table) is not int or not 0<=table<len(ts['form']):
            raise Incomplete('X binding native table index is absent')
        if (not {'form','point'}<=selector.keys() or
                not all(str(ts[k][table])==str(v) for k,v in selector.items()
                        if k in ('form','point','relation','fact'))):
            raise Incomplete('X binding native table index differs from its BODY selector')
        schema=native['_native_reader'].schema(table);expected=binding['source_body_schema']
        if len(schema)!=len(expected):raise Incomplete('X physical BODY schema width differs from binding')
        for actual,want in zip(schema,expected):
            if any(actual[k]!=want[k] for k in ('index','type')):
                raise Incomplete('X physical BODY column identity/type differs from binding')
            if any(actual[k]!=want[k] for k in ('name','frame','slot','label') if k in want):
                raise Incomplete('X physical BODY column metadata differs from binding')
            if ('native_source_label' in want and
                    actual['source_label']!=want['native_source_label']):
                raise Incomplete('X physical BODY source label differs from binding')
        for field in binding['projected_schema']:
            index=field['source_body_column']
            if index is None:
                if (field['type']!='Unit' or not (
                        (field.get('source_projection',{}).get('inserted_constant') or {}).get('kind')=='unit'
                        or field.get('native_label_identity',{}).get('kind')=='implicit_unit')):
                    raise Incomplete('X projection lacks certified inserted Unit evidence')
            elif (type(index) is not int or not 0<=index<len(schema)
                  or comparison_type(schema[index]['type'])!=comparison_type(field['type'])):
                raise Incomplete('X projection physical column/type differs from binding')
        return native,table

    def mutant_input(self,record,adapter,ntrain,ntest):
        binding=adapter['input']['binding'];native,table=self.mutant_snapshot(record,adapter)
        grouped=kept_groups(self.L,native,table,record,ntrain,ntest,[f['source_body_column'] for f in binding['projected_schema']])
        if grouped['missing']:raise Incomplete('X lacks compatible contexts')
        return grouped,binding['projected_schema']
