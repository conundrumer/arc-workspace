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


def registry_candidates(L, info, adapter, *, max_atoms=256, per_relation=32):
    if info.get('schema') != 'judgetool-registry-interfaces-v1':
        raise ValueError('unsupported native registry interface')
    binding=adapter['input']['binding'];fields=binding['projected_schema']
    target=adapter['comparison_target']['binding']['projected_schema']
    x=L.parse(binding['callable_template']);count=0
    for rindex,entry in enumerate(info['entries']):
        # Components/INIT and proposers are outside one-clause recovery syntax.
        # Macros/structured type parameters need their native site adapter;
        # this simple-column layer leaves them explicitly uncovered.
        if entry.get('kind')!='relation':continue
        declaration=L.parse(entry['declaration']['sexp'])
        sections={s[0]:s[1:] for s in declaration[2:] if isinstance(s,list) and s}
        columns=sections.get('columns',[])
        if not columns or any(len(c)!=2 or not isinstance(c[1],str) for c in columns):continue
        domains=[]
        for name,ty in columns:
            values=[f'V{i}' for i,f in enumerate(fields) if compatible(f['type'],ty)]
            if ty in ('number','Number','Box','Position','Offset'):values.append('0')
            domains.append(values)
        emitted=0
        # Fully bound library predicates can select or antiselect X. The native
        # checker alone decides whether NOT and literal sites are admitted.
        for values in itertools.product(*domains):
            if not any(v.startswith('V') for v in values):continue
            atom=[entry['name']]+[[':'+c[0],v] for c,v in zip(columns,values)]
            for body in ([x,atom],[x,['NOT',atom]]):
                if count>=max_atoms:return
                yield dict(clause=L.unparse(['RULE','&fix']+body),role='recovery')
                count+=1
            emitted+=1
            if emitted>=per_relation:break
        # Ground each native mode's required sites at X; unbound remaining sites
        # are computed. Exact one-row-per-X and output types are runtime proofs.
        modes=sections.get('modes',[[]])
        for mode in modes:
            if not isinstance(mode,list):continue
            required=set(mode)
            inputs=[i for i,c in enumerate(columns) if c[0] in required]
            outputs=[i for i,c in enumerate(columns) if c[0] not in required]
            if not inputs or not outputs:continue
            for values in itertools.product(*(domains[i] for i in inputs)):
                if not any(v.startswith('V') for v in values):continue
                terms=dict(zip(inputs,values));extended=list(fields)
                for i in outputs:
                    name=f'MechLib{rindex}C{i}'
                    terms[i]='*'+name
                    extended.append(dict(type=nominal(columns[i][1]),_candidate_label=name))
                atom=[entry['name']]+[[':'+c[0],terms[i]] for i,c in enumerate(columns)]
                if count>=max_atoms:return
                yield dict(clause=L.unparse(['RULE','&fix',x,atom]),role='recovery')
                count+=1
                emitted+=1
                if emitted>=per_relation:break


def projection_labels(fields,target):
    domains=[[f.get('_candidate_label',f'V{i}') for i,f in enumerate(fields)
              if compatible(f['type'],g['type']) or (f['type']=='Box' and g['type']=='Position')]
             for g in target]
    for projection in itertools.product(*domains):yield list(projection)
