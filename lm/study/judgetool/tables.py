"""Complete train/test table acquisition and the shared equality comparator."""
import ast
from collections import Counter
import itertools
from pathlib import Path
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


def read_table(L,n,t,*,example_kinds=None):
    reader=n['_native_reader']; entries=[]
    for index in reader.bytable[t]:
        if example_kinds is not None and reader.entries['example_kind'][index] not in example_kinds:continue
        e=reader.entry(index,with_extents=False,projection_stop=False)
        entries.append(dict(entry=index,example=(e['example_kind'],e['example_index']),model=e['model'],
            assignment=tuple(sorted((d['relation'],tuple(tuple(r) for r in d['rows'])) for d in e['assignment'])),
            rows=tuple(sorted({tuple(tuple(c['value']) for c in row) for row in e['rows']}))))
    return entries


def kept_groups(L,n,t,record,ntrain,ntest,indices=None):
    ts=n['tables']; entries=read_table(L,n,t)
    wants=[L.decode_kept(k,ts['det_relations'][t],ts['det_types'][t]) for k in record['evaluation']['kept_assignments']]
    slots=set(ts['det_relations'][t]); groups={}; contexts=[]; others=[]
    for e in entries:
        matching=[a for a,w in enumerate(wants) if set(w)==slots and L.compatible(e['assignment'],w)]
        if not matching:
            others.append(e); continue
        rows=e['rows'] if indices is None else projected_rows(L,e['rows'],indices)
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
                det_relations=ts['det_relations'][t],required=wanted)


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
    def kind(t):return 'Box' if t in ('Position','Box') else t
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

    def mutant_input(self,record,adapter,ntrain,ntest):
        binding=adapter['input']['binding'];native=self.snapshot(record['native']['mutant'],adapter['source']['native_base'])
        ts=native['tables'];selector=binding['native_selector']
        matches=[t for t in range(len(ts['form'])) if all(str(ts[k][t])==str(v) for k,v in selector.items() if k in ('form','point','relation','fact'))]
        if len(matches)!=1:raise Incomplete('X native body selector missing or ambiguous')
        grouped=kept_groups(self.L,native,matches[0],record,ntrain,ntest,[f['source_body_column'] for f in binding['projected_schema']])
        if grouped['missing']:raise Incomplete('X lacks compatible contexts')
        return grouped,binding['projected_schema']
