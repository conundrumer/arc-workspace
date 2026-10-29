"""Native-row study policy. All predicates run only after evaluate_pair.

Recovery ported from scratchpad/judge2/row_recovery.py (see recovery.py).
Equality is typed, frame-aware, and permits a single column permutation.
No incomplete table is interpreted as empty or unequal.
"""
from collections import defaultdict
import re
import json
from recovery import table_witness, verify_witness

# This staged consumer captures exactly the reviewed shared reader once.
# A running process keeps its captured implementation; a new one fails on drift.
NATIVE_READER_SHA256 = "a7249bfd122fec19d0b6c42e98f4b72ab8c54b2b5abdad160dc721c57aa0d5b9"


def _load_native_reader():
    import hashlib
    from pathlib import Path
    import sys
    import types
    name = 'arc_study.native_tables'
    existing = sys.modules.get(name)
    if existing is not None:
        if getattr(existing, '__source_sha256__', None) != NATIVE_READER_SHA256:
            raise ValueError('loaded canonical native reader differs from pinned source')
        return existing
    folder = Path(__file__).resolve().parent
    path = folder / 'native_tables.py'
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != NATIVE_READER_SHA256:
        raise ValueError('canonical native reader source differs from pinned SHA256')
    module = types.ModuleType(name)
    module.__file__ = str(path)
    module.__source_sha256__ = NATIVE_READER_SHA256
    exec(compile(data, str(path), 'exec'), module.__dict__)
    parent = sys.modules.setdefault('arc_study', types.ModuleType('arc_study'))
    sys.modules[name] = module
    parent.native_tables = module
    return module


_NATIVE = _load_native_reader()


def native(obj):
    reader = _NATIVE.Native(obj, missing_extent_status='reject')
    return dict(reader.parts, values=reader.values, _native_reader=reader)


def _reader(n):
    if '_native_reader' not in n:
        n['_native_reader'] = _NATIVE.Native(n, missing_extent_status='reject')
    return n['_native_reader']


def sexp_forms(text):
    root=[]; stack=[root]
    for tok in re.findall(r'\(|\)|[^\s()]+', text):
        if tok=='(':
            node=[];stack[-1].append(node);stack.append(node)
        elif tok==')':stack.pop()
        else:stack[-1].append(tok)
    if len(stack)!=1:raise ValueError('unbalanced engine sexp')
    return root


def graph(text):
    forms=sexp_forms(text)
    def refs(node):
        if isinstance(node,str):return {node.split('.')[0]} if node.startswith('&') else set()
        return set().union(*(refs(x) for x in node)) if node else set()
    owners={f[1]:i for i,f in enumerate(forms) if len(f)>1 and isinstance(f[1],str) and f[1].startswith('&')}
    deps={i:{owners[r] for r in refs(f[2:] if f[0]!='OUT' else f[1:]) if r in owners} for i,f in enumerate(forms)}
    def ancestors(i):
        found=set(); todo=list(deps[i])
        while todo:
            j=todo.pop()
            if j not in found:found.add(j);todo.extend(deps[j])
        return found
    out=next(i for i,f in enumerate(forms) if f[0]=='OUT')
    return dict(forms=forms,dependencies=deps,ancestors={i:ancestors(i) for i in deps},out=out)


def _namespace_key(n):
    mapping=n.get('_ident_map')
    return None if mapping is None else tuple(sorted(mapping.items()))


def rows_at(n,t,with_extents=False):
    # Gold tables are reused across every candidate at a point. Materialize a
    # logical view once; each mutant view is likewise shared by its filters.
    cache=n.setdefault('_row_cache',{})
    # Without made frames the two logical views are identical.
    with_extents=bool(with_extents and n['tables']['extent_columns'][t])
    key=(t,with_extents,_namespace_key(n))
    if key not in cache:cache[key]=_rows_at(n,t,with_extents)
    return cache[key]


def empty_table(n,t,*,kept_maps,nkept,ntrain):
    """Reject only an empty whole kept TRAIN family; incomplete is unknown.

    Map selection is shared with recovery. Count every unique required entry
    before aggregating, so no nonempty/empty prefix hides a native stop/fault.
    Tests do not supply evidence; task-level entries broadcast over train.
    """
    from next_revision.family_recovery import kept_entry_groups
    groups,_=kept_entry_groups(n,t,kept_maps,nkept,ntrain)
    required=dict.fromkeys(e for assignment in groups for train in assignment for e in train)
    reader=_reader(n)
    counts=[reader.count(e,with_extents=True,projection_stop=False) for e in required]
    return not any(counts)


def _rows_at(n,t,with_extents=False):
    """Apply study policy after the shared lossless native decoder."""
    reader = _reader(n)
    ts,es,vs = reader.tables,reader.entries,reader.values
    types = ts['column_types'][t]
    result = []
    for e in reader.bytable[t]:
        if es['example_kind'][e] == 2:
            continue
        # Values are always complete. Optional extent faults/stops matter only
        # to a consumer requesting frame-aware rows, never to a raw inequality
        # certificate. The shared reader still validates every present buffer.
        entry = reader.entry(e, with_extents=with_extents, projection_stop=False)
        assignments = []
        for det in entry['assignment']:
            detrows=[]
            for row in det['rows']:
                row=list(row);at=0
                for ty in det['types']:
                    if ty == 'Ident' and '_ident_map' in n:
                        if row[at] not in n['_ident_map']:
                            raise ValueError('unmapped cross-session Ident in DET')
                        row[at]=n['_ident_map'][row[at]]
                    at+=4 if ty in _NATIVE.WIDE else 1
                detrows.append(tuple(row))
            assignments.append((det['relation'],tuple(detrows)))
        logical=[]
        for row in entry['rows']:
            cells=[]
            for ty,c in zip(types,row):
                cell=tuple(c['value'])
                if ty=='Ident' and '_ident_map' in n:
                    if cell[0] not in n['_ident_map']:
                        raise ValueError('unmapped cross-session Ident in rows')
                    cell=(n['_ident_map'][cell[0]],)
                if with_extents and ty in _NATIVE.WIDE:
                    status=c['extent_status']
                    if status=='unresolved':
                        raise ValueError('unresolved native frame extent')
                    # Both the status and dimensions are part of equality:
                    # proven no_grid is not a missing/resolved reference frame.
                    cell+=(0 if status=='no_grid' else 1,*c['extent'])
                cells.append(cell)
            logical.append(tuple(cells))
        result.append(dict(entry=e,example=(entry['example_kind'],entry['example_index']),
                           model=entry['model'],assignment=tuple(sorted(assignments)),
                           rows=tuple(sorted(set(logical)))))
    if not result:
        raise ValueError('no native entries')
    schema=tuple(('Box' if ty=='Position' else ty,frame) for ty,frame in zip(types,ts['column_frames'][t]))
    extents={}
    if with_extents:
        for r in result:
            e=r['entry']
            extents[e]=reader.raw_extent_run(e)
    return schema,result,extents


def _comparison_view(n,t,*,with_extents,maps,nkept,ntrain,fact,explicit):
    """One cached scope/schema/model-SET/signature view for either caller mode.

    Exact map content, full-kept context and actual namespace mapping are cache
    keys; Python object identity is never proof that a map/context is unchanged.
    Structural/status validation precedes typed mismatch; row materialization
    remains lazy, so incompatible schemas do not decode large row tuples.
    """
    ts=n['tables']
    schema=tuple(('Box' if ty=='Position' else ty,frame)
                 for ty,frame in zip(ts['column_types'][t],ts['column_frames'][t]))
    selected=[item for item in (maps or ()) if item['table']==t]
    context=json.dumps(selected,sort_keys=True,separators=(',',':')) if explicit else None
    key=(t,bool(with_extents),bool(explicit),nkept,ntrain,bool(fact),context,
         n.get('_kept_context_key'),_namespace_key(n),schema)
    cache=n.setdefault('_comparison_views',{})
    if key in cache:return cache[key]
    view=dict(schema=schema,table=t,maps=maps,fact=fact,explicit=explicit,
              nkept=nkept,ntrain=ntrain,with_extents=with_extents)
    if explicit:
        if type(nkept) is not int or nkept<=0 or type(ntrain) is not int or ntrain<=0:
            raise ValueError('kept equality requires assignments and train inputs')
        if fact:
            # Canonical DET-independent input proof; never invent kept maps.
            from next_revision.family_recovery import _input_fact
            _,rows,_=rows_at(n,t,with_extents)
            view['fact_trains'],_=_input_fact(n,t,rows,ntrain)
        else:
            if maps is None:raise ValueError('kept equality lacks an explicit assignment map')
            from next_revision.family_recovery import kept_entry_groups
            groups,_=kept_entry_groups(n,t,maps,nkept,ntrain)
            required=dict.fromkeys(e for assignment in groups for train in assignment for e in train)
            reader=_reader(n)
            for entry in required:reader.count(entry,with_extents=with_extents,projection_stop=False)
    if len(cache)>=256:cache.clear()
    cache[key]=view
    return view


def _comparison_families(view,n):
    if 'families' in view:return view['families']
    t=view['table']
    if view['explicit']:
        if view['fact']:
            trains=view['fact_trains']
            families=[tuple(frozenset((value,)) for value in trains) for _ in range(view['nkept'])]
        else:
            from next_revision.family_recovery import kept_families
            _,rows,_=rows_at(n,t,view['with_extents'])
            families,_=kept_families(n,t,rows,view['maps'],view['nkept'],view['ntrain'])
        result={(assignment,train):family for assignment,trains in enumerate(families)
                for train,family in enumerate(trains)}
    else:
        _,rows,_=rows_at(n,t,view['with_extents']);result={}
        for row in rows:
            key=(row['example'],row['assignment'],row['model'])
            if key in result:raise ValueError('duplicate assignment/model entry')
            result[key]=frozenset((frozenset(row['rows']),))
    view['families']=result
    return result


def _comparison_signatures(view,n,keys):
    key=tuple(keys)
    cached=view.get('signatures')
    if cached is not None and cached[0]==key:return cached[1]
    families=_comparison_families(view,n)
    result=[tuple(frozenset(frozenset(row[column] for row in model) for model in families[group])
                  for group in keys) for column in range(len(view['schema']))]
    view['signatures']=(key,result)
    return result


def equal_tables(a,ai,b,bi,*,amaps=None,bmaps=None,nkept=None,ntrain=None,a_fact=False,b_fact=False):
    # One equality implementation. Only the explicit scope construction differs.
    scope=dict(amaps=amaps,bmaps=bmaps,nkept=nkept,ntrain=ntrain,a_fact=a_fact,b_fact=b_fact)
    if not _equal_tables(a,ai,b,bi,with_extents=False,**scope):return False
    return _equal_tables(a,ai,b,bi,with_extents=True,**scope)


def _equal_tables(a,ai,b,bi,*,with_extents,amaps,bmaps,nkept,ntrain,a_fact,b_fact):
    explicit=amaps is not None or bmaps is not None or a_fact or b_fact
    va=_comparison_view(a,ai,with_extents=with_extents,maps=amaps,nkept=nkept,ntrain=ntrain,fact=a_fact,explicit=explicit)
    vb=_comparison_view(b,bi,with_extents=with_extents,maps=bmaps,nkept=nkept,ntrain=ntrain,fact=b_fact,explicit=explicit)
    sa,sb=va['schema'],vb['schema']
    if sorted(sa)!=sorted(sb):return False
    ka,kb=_comparison_families(va,a),_comparison_families(vb,b)
    if ka.keys()!=kb.keys():return False
    if any(sorted(map(len,ka[key]))!=sorted(map(len,kb[key])) for key in ka):return False
    if not sa:return ka==kb
    keys=sorted(ka);ac,bc=_comparison_signatures(va,a,keys),_comparison_signatures(vb,b,keys)
    choices=[[j for j,ty in enumerate(sb) if ty==left and ac[column]==bc[j]]
             for column,left in enumerate(sa)]
    if any(not choice for choice in choices):return False
    order=sorted(range(len(sa)),key=lambda column:len(choices[column]));mapping={}
    def projected(family,columns):
        return frozenset(frozenset(tuple(row[column] for column in columns) for row in model)
                         for model in family)
    def visit(depth):
        if depth==len(sa):return True
        column=order[depth]
        for target in choices[column]:
            if target in mapping.values():continue
            mapping[column]=target;left=order[:depth+1];right=[mapping[c] for c in left]
            if all(projected(ka[key],left)==projected(kb[key],right) for key in keys) and visit(depth+1):return True
            del mapping[column]
        return False
    return visit(0)


def recovery(g,gi,m,mi,report,ntrain):
    sg,gr,_=rows_at(g,gi);sm,mr,_=rows_at(m,mi)
    evidence=[]
    if not report.get('kept_assignments'):return dict(status='unknown',reject=False,reason='no kept gold FITS assignment')
    for index,assignment in enumerate(report['kept_assignments']):
        fixed={a['relation']:tuple(tuple(r) for r in a['rows']) for a in assignment}
        def families(rows):
            # The engine appends exactly one native body model at each kept
            # assignment, in report order, separately for each example. The
            # view rewrites DET slots, so its numeric names must not be
            # matched to the original program's slot spellings.
            by_example=defaultdict(list)
            for r in rows:by_example[r['example']].append(r)
            selected={};native_assignments={}
            for (kind,ex),entries in by_example.items():
                if len(entries)!=len(report['kept_assignments']):
                    raise ValueError('kept native entries do not match FITS assignment count')
                entry=entries[index]
                native_assignments[str((kind,ex))]=entry['assignment']
                if kind==0:
                    for train in range(ntrain):selected[train]=entry['rows']
                elif kind==1:selected[ex]=entry['rows']
            return [selected],native_assignments
        (gs,ga),(ms,ma)=families(gr),families(mr)
        witnesses=[]
        if not gs or not ms:raise ValueError('kept assignment has no native entries')
        for grow in gs:
            for mrow in ms:
                if any(i not in grow or i not in mrow for i in range(ntrain)):raise ValueError('missing train entry')
                gp=(tuple(t for t,f in sg),tuple(grow[i] for i in range(ntrain)))
                mp=(tuple(t for t,f in sm),tuple(mrow[i] for i in range(ntrain)))
                w=table_witness(gp,mp)
                if w.get('recoverable') and not verify_witness(gp,mp,w):raise ValueError('invalid recovery witness')
                witnesses.append(w)
        evidence.append(dict(kept_assignment=index,assignment=assignment,native_gold_assignments=ga,native_mutant_assignments=ma,witnesses=witnesses,
                             recoverable=all(w.get('recoverable') for w in witnesses)))
    return dict(status='complete',reject=all(e['recoverable'] for e in evidence),evidence=evidence,
                definition='one typed equality selection and projection per kept DET assignment, shared across every train input')


def align_ident_namespace(pair_gold,full_gold):
    """Prove cross-session Ident correspondences from unique native row anchors.

Only equal, unchanged gold relation tables are anchors. Ambiguous IDs remain
unmapped and make a comparison unknown; interning order is never assumed.
"""
    mapping={};inverse={};pairs=[]
    for pi,form in enumerate(pair_gold['tables']['form']):
        if pair_gold['tables']['point'][pi] not in (0,2):continue
        matches=[fi for fi,f in enumerate(full_gold['tables']['form']) if f==form and
                 full_gold['tables']['point'][fi]==pair_gold['tables']['point'][pi] and
                 full_gold['tables']['column_types'][fi]==pair_gold['tables']['column_types'][pi] and
                 full_gold['tables']['column_names'][fi]==pair_gold['tables']['column_names'][pi]]
        if not form:
            matches=[fi for fi in matches if full_gold['tables']['fact'][fi]==pair_gold['tables']['fact'][pi]]
        if len(matches)!=1:continue
        fi=matches[0]
        try:
            _,pr,_=rows_at(pair_gold,pi);_,fr,_=rows_at(full_gold,fi)
        except ValueError:continue
        types=pair_gold['tables']['column_types'][pi]
        if 'Ident' not in types:continue
        pairs.append((types,pr,fr))
    changed=True
    while changed:
        changed=False
        for types,pr,fr in pairs:
            def groups(rows,full):
                result=defaultdict(set)
                for entry in rows:
                    for row in entry['rows']:
                        key=tuple((c,cell if ty!='Ident' or not full else (mapping.get(cell[0]),)) for c,(ty,cell) in enumerate(zip(types,row))
                                  if ty!='Ident' or (full and cell[0] in mapping) or (not full and cell[0] in inverse))
                        result[(entry['example'],key)].add(row)
                return result
            pg,fg=groups(pr,False),groups(fr,True)
            for key,left in pg.items():
                right=fg.get(key,set())
                if len(left)!=1 or len(right)!=1:continue
                a,b=next(iter(left)),next(iter(right))
                for ty,av,bv in zip(types,a,b):
                    if ty!='Ident':continue
                    old,new=bv[0],av[0]
                    if old in mapping and mapping[old]!=new:raise ValueError('inconsistent Ident namespace anchors')
                    if new in inverse and inverse[new]!=old:raise ValueError('non-injective Ident namespace anchors')
                    if old not in mapping:mapping[old]=new;inverse[new]=old;changed=True
    return mapping
