"""Task-local read-only indexes and conservative comparison obstructions.

These indexes are transient views of observed facts, never durable label data.
A failed selector comparison does not exclude computed libraries or unions.
"""
from types import FunctionType
from collections import OrderedDict


class TargetIndexes:
    def __init__(self):
        self.decoded={};self.indexes=OrderedDict();self.schemas={};self.source=None;self.projections=OrderedDict();self.points={}

    def decode(self,value):
        from case_collector import decode_grouped
        key=id(value)
        if key not in self.decoded:self.decoded[key]=(value,decode_grouped(value))
        return self.decoded[key][1]

    def select(self,bundles,record,adapter,*,ev):
        from case_collector import select_pair
        from run import digest
        # Canonical scope/projection policy and function bytecode are unchanged.
        # Shared grouped data are never mutated; select_pair adds references to
        # a new outer dict. Cache only the lossless decoding of stable bundles.
        namespace=dict(select_pair.__globals__)
        namespace['decode_grouped']=self.decode
        original_sha=namespace['sha'];record_sha=digest(record)
        namespace['sha']=lambda value:record_sha if value is record else original_sha(value)
        project=namespace['_project_body'];scope=dict(project.__globals__)
        scope.update(decode_grouped=self.decode,sha=namespace['sha'])
        original_project=scope['projected_rows']
        def projected_rows(legacy,rows,indices):
            key=(rows,tuple(indices))
            if key not in self.projections:
                self.projections[key]=frozenset(original_project(legacy,rows,indices))
                while len(self.projections)>512:self.projections.popitem(last=False)
            self.projections.move_to_end(key)
            return self.projections[key]
        scope['projected_rows']=projected_rows
        canonical_project=FunctionType(project.__code__,scope,project.__name__,
            project.__defaults__,project.__closure__)
        def project_body(owner,bundle,source,metadata):
            grouped,fields,ref,receipt=canonical_project(owner,bundle,source,metadata)
            key=(id(bundle),tuple(ref['body_path']),tuple(receipt['projection']))
            if key not in self.points:self.points[key]=(bundle,grouped['groups'])
            grouped=dict(grouped,groups=self.points[key][1])
            return grouped,fields,ref,receipt
        namespace['_project_body']=project_body
        bound=FunctionType(select_pair.__code__,namespace,select_pair.__name__,
            select_pair.__defaults__,select_pair.__closure__)
        bound.__kwdefaults__=select_pair.__kwdefaults__
        return bound(bundles,record,adapter,ev=ev)

    def index(self,grouped):
        groups=grouped['groups'];key=id(groups)
        if key not in self.indexes:
            self.indexes[key]=(groups,{k:frozenset(len(rows) for rows in family) for k,family in groups.items()})
            while len(self.indexes)>512:self.indexes.popitem(last=False)
        self.indexes.move_to_end(key)
        return self.indexes[key][1]

    def schema(self,columns,fields):
        from tables import comparison_type
        names=tuple(c[0] for c in columns);types=tuple(comparison_type(c[1]) for c in columns)
        tn=tuple(f.get('field_name',f.get('name')) for f in fields)
        tt=tuple(comparison_type(f['type']) for f in fields)
        key=(names,types,tn,tt)
        if key in self.schemas:return self.schemas[key]
        valid=lambda c:all(types[i]==t for i,t in zip(c,tt))
        by_name=tuple(names.index(n) for n in tn) if all(n in names for n in tn) else None
        if by_name is not None and valid(by_name):
            result=(True,len(set(by_name))==len(by_name),by_name==tuple(range(len(columns))))
        else:
            domains=[tuple(i for i,t in enumerate(types) if t==w and (n not in names or i==names.index(n)))
                for n,w in zip(tn,tt)]
            # Bipartite matching determines whether any fixed injective typed
            # map exists, without enumerating its permutations.
            matched={}
            def augment(column,seen):
                for i in domains[column]:
                    if i in seen:continue
                    seen.add(i)
                    if i not in matched or augment(matched[i],seen):matched[i]=column;return True
                return False
            possible=all(augment(j,set()) for j in range(len(domains)))
            identity=(len(columns)==len(fields) and all(i in domain for i,domain in enumerate(domains)))
            result=(possible,True,identity)
        self.schemas[key]=result
        return result

    def obstruction(self,source,columns,target,*,relation):
        grouped,fields,ref,receipt=target
        possible,injective,identity=self.schema(columns,fields)
        if relation=='equal' and len(columns)!=len(fields):return 'whole output arity differs'
        if not possible:return 'no fixed name/type-compatible column map'
        if self.source is None or self.source[0] is not source['groups']:
            self.source=(source['groups'],{k:frozenset(len(rows) for rows in family) for k,family in source['groups'].items()})
        xs=self.source[1];gs=self.index(grouped)
        other=ref.get('role')=='other_case'
        assignments={k[0] for k in xs}
        relevant=[g for g in gs if relation!='contains' or g[1]==1]
        if any((a,g[1],g[2]) not in xs for g in relevant for a in (assignments if other else [g[0]])):
            return None
        for g,counts in gs.items():
            if relation=='contains' and g[1]!=1:continue
            keys=[(a,g[1],g[2]) for a in assignments] if other else [g]
            for x in keys:
                sizes=xs.get(x)
                if not sizes or not counts:continue # coverage is checked separately
                if relation=='equal' and injective:
                    if sizes!=counts:return 'model row-count families differ under every admissible projection'
                # Projection and filtering cannot create additional rows. Both
                # family quantifiers must hold; no model ordinal alignment.
                elif min(sizes)<min(counts) or max(sizes)<max(counts):
                    return 'target model row count exceeds possible source support'
        return None
