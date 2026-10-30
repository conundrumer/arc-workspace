"""Source-name/X projection adapter; all predicates execute in arclog.

INIT layout is supplied by judge3's native projected binding, not inferred
from a variable spelling. P's existing INIT expansion and OR rewrite are reused.
"""
import json


class InvalidSubmission(ValueError):
    """Authored clause syntax is invalid, independently of source context."""


def parse_submission(L, clause):
    instruction = 'Submit one complete clause: (RULE &fix (&X ...) ...), or (DET &fix ...).'
    try:
        fix = L.parse(clause)
    except (ValueError, IndexError) as error:
        raise InvalidSubmission('Cannot parse the submitted clause: '+str(error)+'. '+instruction) from error
    if (not isinstance(fix,list) or len(fix)<3
            or not isinstance(fix[0],str) or fix[0] not in ('RULE','DET')
            or fix[1]!='&fix'):
        raise InvalidSubmission('Missing or invalid clause header. '+instruction)
    return fix


def tokens(node):
    if isinstance(node,str):
        yield node
    elif isinstance(node,list):
        for child in node:
            yield from tokens(child)


def atoms(body):
    for atom in body:
        if not isinstance(atom,list) or not atom:
            continue
        if atom[0]=='OR':
            for branch in atom[1:]:
                yield from atoms(branch)
        elif atom[0]=='NOT':
            yield from atoms(atom[1:])
        else:
            yield atom


def site_bindings(L, atom, template):
    result={}
    def match(want, have):
        expected={s[0]:s for s in want if isinstance(s,list)}
        positional=[s for s in want if isinstance(s,str)]
        at=0
        for site in have:
            if isinstance(site,str):
                if positional:
                    if at>=len(positional):
                        raise ValueError('too many positional callable arguments')
                    spec=positional[at];at+=1
                    if not (spec.startswith('*V') and spec[2:].isdigit()):
                        raise ValueError('unsupported positional callable field')
                    index=int(spec[2:])
                    if index in result:
                        raise ValueError('callable field bound more than once')
                    result[index]=site
                    continue
                site=[':'+site.lstrip('*^'),site]
            if not isinstance(site,list) or not site or site[0] not in expected:
                raise ValueError('site not in callable template for '+atom[0])
            spec=expected[site[0]]
            if len(spec)!=len(site):
                raise ValueError('site arity differs from callable template')
            match(spec[1:],site[1:])
    match(L.parse(template)[1:],atom[1:])
    return result


def output_projection(names, labels, aliases):
    """Resolve logical output aliases to exact native physical columns.

    Repeated physical indices preserve distinct declared logical fields.
    Only the canonical preparation proof supplies aliases; no name inference.
    """
    result=[]
    for label in labels:
        source=label;seen=set()
        while source in aliases:
            if source in seen:raise ValueError('cyclic native output alias')
            seen.add(source);source=aliases[source]
        if names.count(source)!=1:
            raise ValueError('native output alias source absent or ambiguous: '+str(source))
        result.append(names.index(source))
    return result


def explicit_key_fields(node):
    """Keep authored key field identities explicit before alpha-renaming."""
    if not isinstance(node,list):return node
    if node and node[0]==':key':
        return [node[0]]+([[':'+v.lstrip('*^'),v] if isinstance(v,str) and v!='0' else explicit_key_fields(v) for v in node[1:]])
    return [explicit_key_fields(v) for v in node]


def native_body_labels(nodes,node):
    """Authenticate a copied BODY's spellings against native label-node IDs."""
    path=tuple(node['path']);names={}
    for at,label in nodes.items():
        if at[:len(path)]!=path or label['kind']!='label':continue
        identity=label['data'].get('label_id')
        if identity is None:continue
        name=label['sexp'].strip().lstrip('*^')
        if name in names and names[name]!=identity:
            raise ValueError('nested BODY spellings need a path-aware scoped label adapter')
        names[name]=identity
    return names


def native_body_atoms(L,node,names,output_names,*,given=()):
    """Copy native BODY text with ID-based alpha names and explicit key fields."""
    def rename(label):
        if label=='0':return label
        identity=names.get(label.lstrip('*^'))
        if identity is None:raise ValueError('BODY label has no native scoped identity')
        name=output_names.get(identity,'RawLocal'+str(identity))
        make=label[:1] in ('*','^') and identity not in given
        return ('*' if make else '')+name
    return L.rename_labels(explicit_key_fields(L.parse(node['sexp'])),rename)


def prepare(L,record,clause,adapter):
    fix=parse_submission(L,clause)
    forms=L.split_forms(record['mutant_sexp']); k=int(record['point'][0]); changed=L.parse(forms[k])
    if changed[0]=='DET':
        raise ValueError('DET-kind pairs are not judged')
    inverse={v:k for k,v in adapter['relation_tokens'].items()}
    binding=adapter['input']['binding']; fields=binding['projected_schema']
    body_labels=[c['native_label_identity']['source_label_spelling'] for c in binding['source_body_schema']]
    reads=[]; private=0; aliases={}; unmake=set()
    def names(node):
        if not isinstance(node,list):
            return node
        out=[names(x) for x in node]
        if out and isinstance(out[0],str):
            out[0]=inverse.get(out[0],out[0])
        return out
    def expand(body):
        nonlocal private
        out=[]
        for atom in body:
            if not isinstance(atom,list) or not atom:
                raise ValueError('malformed atom')
            if atom[0]=='&X':
                spec=site_bindings(L,atom,binding['callable_template'])
                reads.append(dict(atom=atom,labels={v.lstrip('*^') for v in spec.values() if v!='0'}))
                read=[changed[1]]; source_terms={}
                for i,term in spec.items():
                    field=fields[i]
                    if field['source_body_column'] is None:
                        raise ValueError('explicit inserted Unit site not supported; omit that X site')
                    source=field['source_body_column']
                    if source in source_terms:
                        previous=source_terms[source]
                        if previous.lstrip('*^')==term.lstrip('*^'):continue
                        if any(a[0]=='OR' for a in atoms(canonical[2:])):
                            raise ValueError('duplicate physical-source bindings inside OR require scoped alias support')
                        if previous=='0' or term=='0':
                            raise ValueError('duplicate physical-source zero/variable alias requires scoped constant support')
                        if term.startswith(('*','^')):
                            aliases[term.lstrip('*^')]=previous.lstrip('*^')
                        elif previous.startswith(('*','^')):
                            aliases[previous.lstrip('*^')]=term.lstrip('*^');unmake.add(previous.lstrip('*^'))
                        else:out.append(['=',previous,term])
                        continue
                    source_terms[source]=term
                    read.append([':'+field['native_label_identity']['source_label_spelling'],term])
                if changed[0]!='INIT':
                    out.append(read); continue
                selected=json.loads(json.dumps(changed))
                if binding['kind']=='INIT key':
                    selected=selected[:3]+[['key',selected[3][1]]]
                else:
                    port=binding['input_port']
                    if selected[3][0]=='key':
                        selected[3]=selected[3][:2]+[p for p in selected[3][2:] if p[0]==port]
                        selected=selected[:4]+[p for p in selected[4:] if p[0]==port]
                    else:
                        selected=selected[:3]+[p for p in selected[3:] if p[0]==port]
                private+=1
                selected=explicit_key_fields(selected)
                old=L.FRESH
                # Choose alpha names disjoint from the complete source/submission.
                suffix='JudgePrivate'+str(private)
                occupied=set(tokens(fix))|set(tokens(selected))
                while any(label+suffix in occupied or '*'+label+suffix in occupied for label in body_labels):
                    suffix+='Q'
                L.FRESH=suffix
                try:
                    selection_labels=({t.lstrip('*^') for t in tokens(selected[3][1]) if t.startswith('^')}
                                      if binding['kind']=='INIT key' else body_labels)
                    if binding['kind']!='INIT key':
                        inputs=selected[3][2:] if selected[3][0]=='key' else selected[3:]
                        if len(inputs)!=1 or inputs[0][0]!=binding['input_port']:
                            raise ValueError('exact selected INIT input is absent or ambiguous')
                        key_atoms=selected[3][1] if selected[3][0]=='key' else []
                        # Port identity was fixed by native metadata above.
                        # The historical inliner selects by every source-local
                        # label, rather than the public BODY's projected labels.
                        key_exports={label for label in L.labels_of(key_atoms)
                                     if '^'+label in json.dumps(key_atoms)}
                        selection_labels=key_exports|L.labels_of(inputs[0][2:])
                    out.extend(L.inline_init(['RULE','&fix',read],selected,selection_labels)[2:])
                finally:
                    L.FRESH=old
            elif atom[0]=='OR':
                out.append(['OR']+[expand(branch) for branch in atom[1:]])
            elif atom[0]=='NOT':
                out.append(['NOT']+expand(atom[1:]))
            elif atom[0] in ('ALL','IF'):
                out.append([atom[0]]+[expand(branch) for branch in atom[1:]])
            else:
                out.append(names(atom))
        return out
    canonical=L.canonical_or(fix)
    executed=[canonical[0],canonical[1]]+expand(canonical[2:])
    def resolve(label):
        mark=label[:1] if label[:1] in ('*','^') else ''
        base=label.lstrip('*^');seen=set()
        if base in unmake:mark=''
        while base in aliases:
            if base in seen:raise ValueError('cyclic projected-source alias')
            seen.add(base);base=aliases[base]
        return mark+base
    if aliases:executed=L.rename_labels(executed,resolve)
    text=L.unparse(executed)
    # Source programs require declarations before their readers. Independent
    # later gold relations are permitted inputs, so leave the mutant intact
    # and insert after the latest actually-read declaration (always after X).
    # Written relation identities and saved DET slot names are unchanged.
    owners={L.parse(f)[1]:i for i,f in enumerate(forms) if L.parse(f)[0] not in ('OUT',) and len(L.parse(f))>1}
    needed={a[0].split('.')[0] for a in atoms(executed[2:]) if isinstance(a[0],str) and a[0].startswith('&')}
    after=max([k]+[owners[name] for name in needed if name in owners])
    return '\n'.join(forms[:after+1]+[text]+forms[after+1:]),after+1,dict(
        submitted=fix,canonical=canonical,expanded=executed,inserted=text,x_reads=reads,
        output_aliases={name:resolve(name) for name in aliases},
        changed_relation=changed[1],or_rewritten=fix!=canonical,inserted_after=after,changed_form=k)
