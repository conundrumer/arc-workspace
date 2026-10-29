"""Orchestrate shared metadata and DET transport; no layout/graph policy."""
import importlib
from pathlib import Path
import sys
from ._paths import CODE_ROOT


def produce(ev,store,record,corpus,*,producer=None):
    from nonrender_metadata import MetadataProducer
    if producer is None:
        producer=MetadataProducer(engine=ev.arclog,
            read_native=lambda ref,base:store.snapshot(ref,base)['_native_reader'],
            corpus=corpus,settings=ev.settings)
    exports={side:producer.programs.load(record[side+'_sexp'],record if side=='gold' else None)[1]
             for side in ('gold','mutant')}
    views=[v for v in exports['gold']['body_views'] if v['body_path']==record['point']]
    if len(views)!=1:raise ValueError('changed native BODY metadata missing/ambiguous')
    if views[0]['kind'].casefold()!='det':
        return producer,producer.produce(record,native_base=corpus/record['task'])
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
        own=dict(record,gold_sexp=record[side+'_sexp'],
            native=dict(record['native'],gold=record['native'][side]),
            evaluation=dict(record['evaluation'],table_indices=dict(record['evaluation']['table_indices'],
                gold_all=record['evaluation']['table_indices'][side+'_kept'])))
        if side=='mutant':own.pop('relation_source_names',None)
        bindings[side]=binding(ev,own,native_base=corpus/record['task'])[0]
    projection=module.receipt(record,exports,bindings)
    return producer,producer.produce(record,native_base=corpus/record['task'],det_projection=projection)
