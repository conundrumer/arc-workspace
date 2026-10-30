"""Test an EXISTING mechanical witness; no search, mutation or lib evaluator.

Predicates and model transformation are the study's canonical fr.verify. Only
its final family equality is bound to the shared native-table comparator so
fresh gold Ident namespaces compare up to renaming. No live globals are edited.
"""
import ast
from collections import OrderedDict
import hashlib
import inspect
from pathlib import Path
import time

from run import digest


def train_witness(item):
    witness=item.get('witness',{})
    return witness.get('recoverable') is True and witness.get('verified') is True


def stored_result(record,item):
    """False/0 is a stored result, never a reason to evaluate again."""
    value=item.get('test_verified')
    if type(value) in (bool,int) and value in (0,1):
        return bool(value),'base per_assignment.test_verified'
    if item['assignment']==0:
        value=record.get('generalizes')
        if type(value) in (bool,int) and value in (0,1):
            return bool(value),'base generalizes first assignment'
    return None,None


def witness_inputs(base,item):
    """Code-independent identity of the actual stored witness application."""
    from source_bindings import witness_source
    base,item=witness_source(base,item)
    witness=item['witness']
    atoms=[a for branch in witness.get('selection_any',[witness.get('selection',[])]) for a in branch]
    used=sorted({a['available'] for a in atoms if a['kind'] in ('semijoin','antijoin')})
    return digest(dict(source_sha256=base['source_sha256'],assignment=item['assignment'],
        witness=witness,selectors=[item.get('available_metadata',[])[i]
            if 0<=i<len(item.get('available_metadata',[])) else {'missing_available_metadata':i} for i in used]))


def native_equality_verifier(fr):
    """Source-bound canonical verifier with one final equality callback.

    This is an additive binding adapter, like the shared project's AST-extracted
    header/projector adapters. All predicate/application code comes from the
    installed study module. Reject unknown source shape rather than fork it.
    Prefer a canonical callback parameter when the helper owner supplies one.
    """
    if 'family_equal' in inspect.signature(fr.verify).parameters:
        return fr.verify,dict(route='canonical family_equal callback',source=str(Path(fr.__file__).resolve()))
    path=Path(fr.__file__).resolve();raw=path.read_bytes();tree=ast.parse(raw,str(path))
    function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='verify')
    matches=[]
    for node in ast.walk(function):
        if (isinstance(node,ast.Compare) and len(node.ops)==1 and isinstance(node.ops[0],ast.NotEq)
                and isinstance(node.left,ast.Call) and isinstance(node.left.func,ast.Name)
                and node.left.func.id=='frozenset' and len(node.left.args)==1
                and isinstance(node.left.args[0],ast.Name) and node.left.args[0].id=='transformed'
                and len(node.comparators)==1 and isinstance(node.comparators[0],ast.Name)
                and node.comparators[0].id=='gs'):
            matches.append(node)
    if len(matches)!=1:raise ValueError('canonical verifier final family comparison changed')
    old=matches[0]
    class Bind(ast.NodeTransformer):
        def visit_Compare(self,node):
            if node is old:
                return ast.copy_location(ast.UnaryOp(op=ast.Not(),operand=ast.Call(
                    func=ast.Name(id='family_equal',ctx=ast.Load()),args=[old.left,old.comparators[0]],keywords=[])),node)
            return self.generic_visit(node)
    function=Bind().visit(function);function.name='_verify_with_native_equality'
    function.args.kwonlyargs.append(ast.arg(arg='family_equal'));function.args.kw_defaults.append(None)
    module=ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[]))
    namespace=dict(fr.__dict__)
    exec(compile(module,str(path),'exec'),namespace)
    return namespace[function.name],dict(route='canonical verify AST; only final equality rebound',
        source=str(path),source_sha256=hashlib.sha256(raw).hexdigest())


class Checker:
    def __init__(self,ev,*,verify_seconds=5,cache_entries=32,cache_bytes=128*1024*1024):
        from next_revision import family_recovery as fr
        from tables import TargetStore
        self.ev=ev;self.fr=fr;self.verify,self.verifier_receipt=native_equality_verifier(fr)
        self.store=TargetStore(ev.legacy,ev.run.parent.parent)
        self.verify_seconds=verify_seconds;self.cache=OrderedDict();self.cache_charge=0
        self.cache_entries=cache_entries;self.cache_bytes=cache_bytes;self.case=None
        self.gold_replays=0;self.evaluations=0;self.binding_cache=OrderedDict();self.binding_hits=0;self.target_hits=0

    def _target(self,record,native_base,ntrain,ntest):
        from raw_body import binding,observe_gold_body
        # Full source identity + immutable native reference + exact table index
        # authenticate this binding. Reuse the canonical binder's output only
        # for those identical inputs, never on an inferred cross-record layout.
        binding_key=digest(dict(base=str(Path(native_base).resolve()),gold=record['gold_sexp'],
            point=record['point'],native=record['native']['gold'],
            table=record['evaluation']['table_indices']['gold_all'],settings=self.ev.receipt))
        if binding_key in self.binding_cache:
            layout,prior=self.binding_cache.pop(binding_key)
            proof=dict(prior,source_sha256=digest(record))
            self.binding_hits+=1
        else:layout,proof=binding(self.ev,record,native_base=native_base)
        self.binding_cache[binding_key]=(layout,proof)
        while len(self.binding_cache)>self.cache_entries:self.binding_cache.popitem(last=False)
        key=digest(dict(task=record['task'],case=record['case'],gold=record['gold_sexp'],
                        kept=record['evaluation']['kept_assignments'],point=record['point'],
                        layout=layout,ntrain=ntrain,ntest=ntest,settings=self.ev.receipt))
        if key in self.cache:
            grouped,receipt,charge=self.cache.pop(key);self.cache[key]=(grouped,receipt,charge);self.target_hits+=1
            return grouped,dict(receipt,current_source_sha256=digest(record),
                                current_binding_receipt=proof,gold_data_identity_sha256=key,reused_gold_replay=True)
        grouped,receipt=observe_gold_body(self.ev,record,native_base=native_base,ntrain=ntrain,ntest=ntest)
        self.gold_replays+=1
        # This caller owns the bounded cache. The generic tool's per-record
        # cache otherwise retains a second unbounded copy across all mutants.
        self.ev.target_cache.clear()
        # Bound retained Python rows, accounting containers/cells conservatively.
        charge=sum(256+sum(128+sum(64+16*len(cell) for cell in row) for row in model)
                   for family in grouped['groups'].values() for model in family)
        if charge<=self.cache_bytes:
            self.cache[key]=(grouped,receipt,charge);self.cache_charge+=charge
            while len(self.cache)>self.cache_entries or self.cache_charge>self.cache_bytes:
                _,(_,_,old)=self.cache.popitem(last=False);self.cache_charge-=old
        return grouped,dict(receipt,current_source_sha256=digest(record),
                            current_binding_receipt=proof,gold_data_identity_sha256=key,reused_gold_replay=False)

    def _available(self,record,native_base,item,ntrain,ntest):
        """Read only the old selector tables actually referenced by this witness."""
        from tables import kept_groups,comparison_type
        witness=item['witness'];atoms=[a for branch in witness.get('selection_any',[witness.get('selection',[])]) for a in branch]
        used={a['available'] for a in atoms if a['kind'] in ('semijoin','antijoin')}
        metadata=item.get('available_metadata',[]);tables=[None]*len(metadata);receipts=[]
        if not used:return tables,receipts
        # Certified input facts have no Ident columns and may come from
        # native.gold even when full replay is absent.
        needs_namespace=any(metadata[n]['identity'].get('proof')!='det_independent_native_fact' for n in used)
        if needs_namespace and record['full_replay'].get('ident_namespace')!='shared task evaluator session':
            raise ValueError('stored mutant/available namespace agreement unavailable')
        for number in sorted(used):
            meta=metadata[number];identity=meta['identity']
            native,table,selector_receipt=self.store.selector_snapshot(record,native_base,identity)
            grouped=kept_groups(self.ev.legacy,native,table,record,ntrain,ntest)
            fields=native['_native_reader'].schema(table);types=tuple(f['type'] for f in fields)
            local=identity.get('example_scope')=='train-local; leading Example removed'
            if local and (not types or types[0]!='Example'):raise ValueError('selector Example scope/type differs')
            actual=types[1:] if local else types
            if tuple(map(comparison_type,meta['types']))!=tuple(map(comparison_type,actual)):
                raise ValueError('stored selector physical schema differs after canonical comparison normalization')
            values=[]
            for test in range(ntest):
                family=grouped['groups'].get((item['assignment'],2,test))
                if family is None or len(family)!=1:
                    raise ValueError('selector test table has missing or nondeterministic compatible model')
                rows=next(iter(family))
                if local:
                    # Native Task::examples is train indices then test indices;
                    # the old train-local input adapter used train's E index.
                    rows=frozenset(row[1:] for row in rows if row[0]==(ntrain+test,))
                values.append(rows)
            tables[number]=dict(types=tuple(meta['types']),rows=tuple(values),identity=identity)
            receipts.append(dict(available=number,selector=selector_receipt,
                                 identity=identity,test_contexts=ntest,assignment=item['assignment']))
        return tables,receipts

    def check(self,record,item,*,native_base,ntrain,ntest):
        from tables import kept_groups,compare
        started=time.monotonic();assignment=item['assignment']
        result=dict(schema='mech-witness-test-v1',source_sha256=digest(record),assignment=assignment,
                    witness_sha256=digest(item['witness']),test_verified=None,status='unknown',
                    origin='new test application of stored witness',test_target='gold_full_replay')
        case=(record['task'],record['case'])
        if case!=self.case:
            self.ev.finish_case();self.ev.target_cache.clear()
            self.cache.clear();self.binding_cache.clear();self.cache_charge=0;self.store.cache.clear();self.case=case
        try:
            if ntest<1:raise ValueError('no test-input axis')
            mutant=self.store.snapshot(record['native']['mutant'],native_base)
            table=record['evaluation']['table_indices']['mutant_kept']
            source=kept_groups(self.ev.legacy,mutant,table,record,ntrain,ntest)
            types=tuple(f['type'] for f in mutant['_native_reader'].schema(table))
            available,available_receipts=self._available(record,native_base,item,ntrain,ntest)
            # Stored-input admission is cheap: do it before any fresh gold work.
            for test in range(ntest):
                if (assignment,2,test) not in source['groups']:
                    raise ValueError('stored X test input/kept context missing')
            target,target_receipt=self._target(record,native_base,ntrain,ntest)
            gold=[];x=[]
            for test in range(ntest):
                key=(assignment,2,test)
                if key not in target['groups'] or key not in source['groups']:
                    raise ValueError('fresh gold or stored X test input/kept context missing')
                gold.append(frozenset(target['groups'][key]));x.append(frozenset(source['groups'][key]))
            fields=target_receipt['fields']
            if len(fields)!=len(item['witness']['projection']):raise ValueError('fresh raw gold witness output layout differs')
            projected_types=[types[i] for i in item['witness']['projection']]
            columns=[(f'C{i}',ty) for i,ty in enumerate(projected_types)]
            equality=[];deadline=time.monotonic()+self.verify_seconds
            def budget():
                if time.monotonic()>deadline:raise self.fr.SearchBound('test application reached its verification bound')
            def equal(transformed,expected):
                budget()
                outcome=compare({(assignment,2,0):set(transformed)},columns,
                    {(assignment,2,0):set(expected)},fields,explicit=[c[0] for c in columns],
                    seconds=max(.001,deadline-time.monotonic()))
                equality.append(outcome)
                if outcome['status']=='unknown':raise self.fr.Incomplete(outcome.get('reason','test comparison unknown'))
                return outcome['status']=='equal'
            self.evaluations+=1
            verified=self.verify(tuple(gold),tuple(x),item['witness'],available,
                                  budget=budget,mutant_types=types,family_equal=equal)
            result.update(test_verified=bool(verified),status='verified' if verified else 'mismatch',
                          gold_receipt=target_receipt,selector_receipts=available_receipts,
                          source_native_ref=record['native']['mutant'],source_table=table,
                          verifier=self.verifier_receipt,comparisons=equality,
                          expected_test_inputs=ntest,transform_evaluations=1)
        except Exception as error:
            result.update(reason=str(error),error_type=type(error).__name__)
        # Snapshot keys include each mutant's native reference. Keep only the
        # current pair's views; reuse across its witnesses, release next pair.
        while len(self.store.cache)>8:self.store.cache.pop(next(iter(self.store.cache)))
        result['seconds']=time.monotonic()-started
        return result
