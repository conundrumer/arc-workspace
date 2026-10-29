"""Canonical public X/G metadata and durable fresh GOLD data, G scope only."""
from common import *
from collections import Counter,OrderedDict
import copy


class SnapshotCache(OrderedDict):
    """Two immutable published snapshots: warm gold plus current mutant.

    Canonical TargetStore still owns exact ref/base keys and validates misses.
    Hits reuse read-only views, not a continuing disk-integrity attestation.
    """
    def __getitem__(self,key):
        value=super().__getitem__(key);self.move_to_end(key);return value
    def __setitem__(self,key,value):
        super().__setitem__(key,value);self.move_to_end(key)
        while len(self)>2:self.popitem(last=False)


def g_inventory(case):
    # Explicitly NOT an all-case catalogue/admission certificate. No other
    # case values or stored target rows are needed for this first pass.
    return dict(scope='G only',catalogue_path=None,catalogue_sha256=None,
        catalogue_status='not requested: G-only mechanical library pass',cases=[dict(name=case)])


def require_axes(selection,record,ntrain,ntest):
    point=selection.get('point')
    if point is None:raise ValueError('fresh G point unavailable')
    grouped,fields,reference,receipt=point
    required={(a,kind,i) for a in range(len(record['evaluation']['kept_assignments']))
              for kind,count in ((1,ntrain),(2,ntest)) for i in range(count)}
    if ntrain<1 or ntest<1 or not required:raise ValueError('required TRAIN+TEST input axis unavailable')
    if grouped['required']!=required or set(grouped['groups'])!=required or grouped['missing']:
        raise ValueError('fresh G lacks the exact required kept TRAIN+TEST axis')
    if any(not family for family in grouped['groups'].values()):raise ValueError('fresh G model family unavailable')
    if (receipt.get('source')!='gold_full_replay' or receipt.get('train_complete') is not True
            or receipt.get('test_complete') is not True or not receipt.get('observer_program_sha256')
            or receipt.get('original_source_sha256')!=digest(record)
            or receipt.get('gold_program_sha256')!=digest(record['gold_sexp'])
            or receipt.get('kept_context_sha256')!=digest(record['evaluation']['kept_assignments'])
            or receipt.get('layout_sha256')!=digest(fields)):
        raise ValueError('fresh G source/program/kept/layout receipt incomplete')
    if reference.get('target_id')!='G':raise ValueError('unexpected target outside G-only scope')


class Contexts:
    def __init__(self,screen_ev,gold_ev,journal,config,guard):
        from tables import TargetStore
        self.screen=screen_ev;self.gold=gold_ev;self.journal=journal;self.config=config;self.guard=guard
        self.store=TargetStore(screen_ev.legacy,CODE_ROOT);self.store.cache=SnapshotCache();self.producers={};self.cache=OrderedDict();self.stats=Counter()
    def clear(self):
        from case_collector import clear_cache
        clear_cache(self.gold);self.gold.close();self.gold.captures=[]
        self.store.cache.clear();self.producers.clear();self.cache.clear()
    def acquire(self,record,job):
        from nonrender_metadata import MetadataProducer
        from case_collector import acquire_case,select_pair,clear_cache
        task_path=(Path(self.screen.cfg['tasks'])/(record['task']+'.json')).resolve()
        raw=task_path.read_bytes();task=json.loads(raw);ntrain=len(task['train']);ntest=len(task['test'])
        key=(record['task'],record['case'],job['source']['corpus'])
        if key not in self.producers:
            self.producers[key]=MetadataProducer(engine=self.screen.arclog,
                read_native=lambda ref,base:self.store.snapshot(ref,base)['_native_reader'],
                corpus=Path(job['source']['corpus']),settings=self.screen.settings,
                case_inventory=g_inventory(record['case']))
        adapter=self.producers[key].produce(record,native_base=Path(job['source']['corpus'])/record['task'])
        inputs=dict(task=record['task'],case=record['case'],program_sha256=digest(record['gold_sexp']),
            kept_context_sha256=digest(record['evaluation']['kept_assignments']),ntrain=ntrain,ntest=ntest,
            task_inputs_sha256=digest(task))
        case_key=digest(inputs);bundle=self.cache.get(case_key)
        if bundle is None:
            bundle=self.journal.get('gold_case',case_key,inputs)
            if bundle is None:
                self.guard.check()
                bundle=acquire_case(self.gold,record,dict(case=record['case'],gold_sexp=record['gold_sexp'],
                    kept_assignments=record['evaluation']['kept_assignments'],
                    relation_source_names=record.get('relation_source_names')),ntrain,ntest)
                self.guard.check()
                bundle={k:v for k,v in bundle.items() if k not in ('export','complete')}
                self.journal.put('gold_case',case_key,inputs,bundle)
                self.stats['gold_replays']+=1
            else:self.stats['gold_journal_hits']+=1
            # The caller owns the bounded cache; never retain a second growing
            # per-evaluator cache of every task/case in the study.
            clear_cache(self.gold);self.gold.finish_case();self.gold.captures=[]
            self.cache[case_key]=bundle
            while len(self.cache)>self.config['case_cache_entries']:self.cache.popitem(last=False)
        else:
            self.cache.move_to_end(case_key);self.stats['gold_memory_hits']+=1
        gold_ref=self.journal.ref('gold_case',case_key,bundle)
        # AST export is recomputed by the canonical metadata producer, never
        # copied into the observation store. This performs no table replay.
        selected_bundle=dict(bundle,export=self.producers[key]._export(record['gold_sexp'],record))
        selection=select_pair(selected_bundle,record,adapter,ev=self.screen)
        require_axes(selection,record,ntrain,ntest)
        from judge3.catalog import matches
        bindings=[];binding_gaps=[]
        for offered in adapter['availability']['definitions']:
            definition=offered['definition']
            tables=[t for t in bundle['tables'] if matches({k:[v] for k,v in t['selector'].items()},0,
                                                           definition['native_selector'])]
            if len(tables)!=1:
                binding_gaps.append(dict(source=definition['display_name'],reason='no unique fresh native schema'))
                continue
            try:
                bound=self.producers[key].callable_definition(definition,tables[0]['native_schema'])
                bindings.append(dict(definition=definition,callable_atom=bound['callable_atom'],
                    fields=bound['schema'],receipt=tables[0]['receipt'],graph_node=offered['graph_node']))
            except (ValueError,KeyError,IndexError,TypeError) as error:
                binding_gaps.append(dict(source=definition['display_name'],reason=str(error)))
        # This pass cannot accidentally gain a later/other-case target through
        # checks.evaluate's ordinary target iteration. Case collection/scope
        # receipts remain intact; only requested comparisons are narrowed.
        selection=dict(selection,targets=[],available=[],gaps=[],complete=True,scope='G only')
        return dict(adapter=adapter,selection=selection,ntrain=ntrain,ntest=ntest,
            available_bindings=bindings,available_binding_gaps=binding_gaps,
            gold_ref=gold_ref,
            task_receipt=dict(path=str(task_path),sha256=hashlib.sha256(raw).hexdigest(),inputs_sha256=digest(task)))
