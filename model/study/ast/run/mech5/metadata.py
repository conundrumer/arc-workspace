"""Orchestrate shared metadata and DET transport; no layout/graph policy."""
import importlib
import copy
from types import FunctionType,MethodType,SimpleNamespace
from pathlib import Path
import sys
from ._paths import CODE_ROOT


def bind_inventory_copy(producer):
    """Clone canonical case envelopes, share their read-only source leaves."""
    if getattr(producer,'_mech5_inventory_copy',False):return
    original=producer._inventory.__func__
    def deepcopy(value):
        memo={}
        for inventory in producer.case_cache.values():
            for case in inventory['cases']:
                for name in ('source_record_data','reference','source_record'):
                    leaf=case.get(name)
                    if leaf is not None:memo[id(leaf)]=leaf
        return copy.deepcopy(value,memo)
    scope=dict(original.__globals__)
    scope['copy']=SimpleNamespace(deepcopy=deepcopy)
    bound=FunctionType(original.__code__,scope,original.__name__,original.__defaults__,original.__closure__)
    producer._inventory=MethodType(bound,producer)
    producer._mech5_inventory_copy=True


def canonical_produce(producer,record,base):
    """Canonical metadata, with its repeated source hash computed once."""
    method=producer.produce.__func__;scope=dict(method.__globals__)
    original_sha=scope['_sha'];source_sha=original_sha(record)
    scope['_sha']=lambda value:source_sha if value is record else original_sha(value)
    bound=FunctionType(method.__code__,scope,method.__name__,method.__defaults__,method.__closure__)
    bound.__kwdefaults__=method.__kwdefaults__
    return bound(producer,record,native_base=base)


def produce(ev,store,record,corpus,*,producer=None,kind=None):
    from nonrender_metadata import MetadataProducer
    if producer is None:
        producer=MetadataProducer(engine=ev.arclog,
            read_native=lambda ref,base:store.snapshot(ref,base)['_native_reader'],
            corpus=corpus,settings=ev.settings)
    bind_inventory_copy(producer)
    if kind is not None and kind.casefold()!='det':
        # The canonical producer authenticates the native BODY kind itself.
        # Avoid exporting/deep-copying both programs again merely to route it.
        return producer,canonical_produce(producer,record,corpus/record['task'])
    exports={side:producer.programs.load(record[side+'_sexp'],record if side=='gold' else None)[1]
             for side in ('gold','mutant')}
    views=[v for v in exports['gold']['body_views'] if v['body_path']==record['point']]
    if len(views)!=1:raise ValueError('changed native BODY metadata missing/ambiguous')
    if views[0]['kind'].casefold()!='det':
        return producer,canonical_produce(producer,record,corpus/record['task'])
    # Canonical raw binder supplies provenance only. The public DET comparison
    # is selected by the shared reader/header mapper and metadata projector.
    from raw_body import binding
    path=CODE_ROOT/'ast/run/mech3'
    sys.path.append(str(path))
    module=importlib.import_module('det_receipt')
    if Path(module.__file__).resolve()!=path/'det_receipt.py':
        raise ValueError('DET transport imported outside tracked shared source')
    bindings={}
    for side in ('gold','mutant'):
        bindings[side]=binding(ev,record,native_base=corpus/record['task'],
            body_side=side,report_role=side+'_kept')[0]
    projection=module.receipt(record,exports,bindings)
    return producer,producer.produce(record,native_base=corpus/record['task'],det_projection=projection)
