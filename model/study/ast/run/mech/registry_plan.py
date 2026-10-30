"""Bounded syntax grounding from native registry declarations, no lib evaluator.

Native modes/sites are used as candidate hints only. Every candidate is checked
by the shared evaluator; no omitted/malformed declaration proves impossibility.
The finite one-lib layer is intentionally not a full-space coverage certificate.
"""
import itertools


def nominal(ty):
    return 'Number' if ty == 'number' else ty


def compatible(actual, declared):
    # Conservative syntax candidates, not native type inference/admissibility.
    return nominal(actual) == nominal(declared) or (declared == 'Box' and actual in ('Box','Position','Offset'))


def unsupported_named_sites(tree):
    """Find native positional names incorrectly emitted as written sites.

    Inspect actual site heads, including nested keys. Canonical positional
    arguments without a colon remain supported; this is no grammar coverage
    or native admissibility proof.
    """
    found=set()
    def visit(node):
        if not isinstance(node,list):return
        if node and isinstance(node[0],str) and node[0].startswith(':'):
            name=node[0][1:]
            if not name or '[' in name or ']' in name or name.isdecimal():found.add(node[0])
        for child in node:visit(child)
    visit(tree)
    return sorted(found)


def registry_atoms(L, info, adapter, *, per_predicate=16, per_mode=16):
    """Finite native-site syntax plan, round robin across relations AND modes.

    No library is evaluated here. Required sites come from native declarations;
    a computed output's exactly-one-row property still requires engine evidence.
    Unsupported structured/polymorphic sites are reported, never called absent.
    Per-predicate and EACH per-mode budgets are independent.
    """
    from collections import deque
    import hashlib
    import json
    if info.get('schema') != 'judgetool-registry-interfaces-v1':
        raise ValueError('unsupported native registry interface')
    if per_predicate < 1 or per_mode < 1:
        raise ValueError('positive grounding budgets required')
    fields = adapter['input']['binding']['projected_schema']
    def identity(entry):
        return dict(entry_id=entry.get('id', entry.get('name')),
                    entry_sha256=hashlib.sha256(json.dumps(entry,sort_keys=True,
                        separators=(',', ':'),ensure_ascii=False).encode()).hexdigest())
    def one(entry):
        ident = identity(entry)
        if entry.get('kind') != 'relation':
            return
        declaration = L.parse(entry['declaration']['sexp'])
        sections = {s[0]:s[1:] for s in declaration[2:] if isinstance(s,list) and s}
        columns = sections.get('columns', [])
        if not columns or any(len(c)!=2 or not isinstance(c[1],str) for c in columns):
            yield dict(status='unsupported',reason='structured native sites require canonical adapter',**ident)
            return
        # Native positional names such as [1]/[2] are not written column
        # labels. The shared checker refuses :[1]; no legal native-to-written
        # mapping is exposed here, so do not spend a search call on this syntax.
        unsupported=[name for name,ty in columns if not isinstance(name,str)
                     or '[' in name or ']' in name or name.isdecimal()]
        if unsupported:
            yield dict(status='unsupported',
                reason='positional/bracket native sites require canonical written-name adapter',
                native_sites=unsupported,**ident)
            return
        domains = []
        for name,ty in columns:
            values = [f'V{i}' for i,f in enumerate(fields) if compatible(f['type'],ty)]
            if ty in ('number','Number','Box','Position','Offset'):
                values.append('0')
            domains.append(values)
        def predicates(negated):
            emitted = 0
            for values in itertools.product(*domains):
                if not any(v.startswith('V') for v in values):
                    continue
                atom = [entry['name']]+[[':'+c[0],v] for c,v in zip(columns,values)]
                yield dict(status='candidate',kind='antipredicate' if negated else 'predicate',
                    atom=['NOT',atom] if negated else atom,computed_fields=[],mode=None,**ident)
                emitted += 1
                if emitted >= per_predicate:
                    return
        def computation(mode):
            if not isinstance(mode,list) or any(not isinstance(n,str) for n in mode):
                return
            required = set(mode)
            if not required <= {c[0] for c in columns}:
                return
            inputs = [i for i,c in enumerate(columns) if c[0] in required]
            outputs = [i for i,c in enumerate(columns) if c[0] not in required]
            if not inputs or not outputs:
                return
            emitted = 0
            for values in itertools.product(*(domains[i] for i in inputs)):
                if not any(v.startswith('V') for v in values):
                    continue
                terms = dict(zip(inputs,values));computed = []
                for i in outputs:
                    label = 'MechLib'+ident['entry_sha256'][:12]+'C'+str(i)
                    terms[i] = '*'+label
                    computed.append(dict(type=nominal(columns[i][1]),_candidate_label=label,
                                         native_site=columns[i][0]))
                atom = [entry['name']]+[[':'+c[0],terms[i]] for i,c in enumerate(columns)]
                yield dict(status='candidate',kind='computation',atom=atom,
                    computed_fields=computed,mode=list(mode),**ident)
                emitted += 1
                if emitted >= per_mode:
                    return
        streams = deque(iter(computation(mode)) for mode in sections.get('modes', []))
        streams.extend([iter(predicates(False)),iter(predicates(True))])
        while streams:
            stream = streams.popleft()
            try:
                yield next(stream)
            except StopIteration:
                continue
            streams.append(stream)
    entries = sorted(info['entries'],key=lambda e:(str(e.get('id','')),str(e.get('name',''))))
    streams = deque(iter(one(entry)) for entry in entries)
    while streams:
        stream = streams.popleft()
        try:
            yield next(stream)
        except StopIteration:
            continue
        streams.append(stream)


def registry_candidates(L, info, adapter, *, max_atoms=256, per_relation=32):
    """Compatibility wrapper with EXPLICIT intended output columns.

    Projections are interleaved across a bounded pool of native atom plans.
    Atom plans, predicate groundings and modes no longer share one counter.
    """
    from collections import deque
    if max_atoms < 1:
        return
    binding = adapter['input']['binding'];fields = binding['projected_schema']
    target = adapter['comparison_target']['binding']['projected_schema']
    x = L.parse(binding['callable_template']);pool = deque()
    for planned in registry_atoms(L,info,adapter,per_predicate=per_relation,per_mode=per_relation):
        if planned['status'] != 'candidate':
            continue
        extended = list(fields)+planned['computed_fields']
        projections = iter(projection_labels(extended,target))
        try:
            first = next(projections)
        except StopIteration:
            continue
        candidate = dict(clause=L.unparse(['RULE','&fix',x,planned['atom']]),role='recovery',
                         registry_entry_id=planned['entry_id'],registry_mode=planned['mode'])
        pool.append((candidate,first,projections))
        if len(pool) >= max_atoms:
            break
    emitted = 0
    while pool and emitted < max_atoms:
        candidate,columns,projections = pool.popleft()
        yield dict(candidate,columns=columns)
        emitted += 1
        try:
            pool.append((candidate,next(projections),projections))
        except StopIteration:
            pass


def projection_labels(fields,target):
    domains=[[f.get('_candidate_label',f'V{i}') for i,f in enumerate(fields)
              if compatible(f['type'],g['type']) or (f['type']=='Box' and g['type']=='Position')]
             for g in target]
    for projection in itertools.product(*domains):yield list(projection)


def available_atoms(L, bindings, adapter, *, per_source=12, max_join=2):
    """Ground canonical callable tables admitted by the resolver metadata.

    bindings are caller-authenticated definition/template/schema receipts from
    MetadataProducer.callable_definition, not fabricated registry declarations.
    Fresh existential columns only restrict X; they are not computed outputs.
    """
    from collections import deque
    import hashlib
    import json
    if per_source < 1 or max_join < 1:
        raise ValueError('positive source grounding limits required')
    xfields = adapter['input']['binding']['projected_schema']
    def one(binding):
        fields = binding['fields'];template = L.parse(binding['callable_atom'])
        ident = hashlib.sha256(json.dumps(binding['definition'],sort_keys=True,
            separators=(',', ':'),ensure_ascii=False).encode()).hexdigest()
        unsupported=unsupported_named_sites(template)
        if unsupported:
            yield dict(status='unsupported',
                reason='positional/bracket callable sites require canonical written-name adapter',
                native_sites=unsupported,entry_id='available:'+ident,entry_sha256=ident,
                source_kind='available',source_receipt=binding.get('receipt'))
            return
        domains = [[f'V{i}' for i,x in enumerate(xfields) if compatible(x['type'],f['type'])]
                   + (['0'] if f['type'] in ('number','Number','Box','Position','Offset') else [])
                   for f in fields]
        def emit(joined,negated):
            def rename(value):
                name = value.lstrip('*^')
                if name == '0':
                    return value
                if not name.startswith('V') or not name[1:].isdigit():
                    raise ValueError('canonical available template has no physical-column site')
                index = int(name[1:])
                return joined.get(index,'*MechSource'+ident[:12]+'C'+str(index))
            atom = L.rename_labels(template,rename)
            return dict(status='candidate',kind='antipredicate' if negated else 'predicate',
                atom=['NOT',atom] if negated else atom,computed_fields=[],mode=sorted(joined),
                entry_id='available:'+ident,entry_sha256=ident,source_kind='available',
                source_receipt=binding.get('receipt'))
        def full(negated):
            for values in itertools.product(*domains):
                if not any(v.startswith('V') for v in values):
                    continue
                yield emit(dict(enumerate(values)),negated)
        def partial(width):
            for columns in itertools.combinations(range(len(fields)),width):
                for values in itertools.product(*(domains[i] for i in columns)):
                    if any(v.startswith('V') for v in values):
                        yield emit(dict(zip(columns,values)),False)
        streams = deque([iter(full(False)),iter(full(True))])
        streams.extend(iter(partial(width)) for width in range(1,min(max_join,len(fields))+1))
        emitted = 0
        while streams and emitted < per_source:
            stream = streams.popleft()
            try:
                yield next(stream)
            except StopIteration:
                continue
            emitted += 1;streams.append(stream)
    streams = deque(iter(one(binding)) for binding in bindings)
    while streams:
        stream = streams.popleft()
        try:
            yield next(stream)
        except StopIteration:
            continue
        streams.append(stream)
