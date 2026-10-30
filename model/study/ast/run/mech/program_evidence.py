"""Pure adapters for existing corpus program checks; no replay or writes."""
from run import digest,pair_key


def stored_train_nonfit(record,*,pair_id,source_sha256,source_ref):
    """A native TRAIN counterexample at EVERY kept assignment rules out fit.

    The base's aggregate fits=False is insufficient: it also covers missing
    evidence and mixed assignment results. Consume original native output
    checks instead. TEST remains unknown; this certifies nonfit only.
    """
    if digest(record)!=source_sha256 or digest(pair_key(record))!=pair_id:
        raise ValueError('program check source identity differs')
    evaluation=record.get('evaluation',{})
    kept=evaluation.get('kept_assignments',[]);outputs=evaluation.get('outputs',[])
    unavailable=dict(valid=False,reason='complete native train nonfit evidence unavailable')
    if (evaluation.get('status')!='complete' or not kept or len(outputs)!=len(kept)
            or evaluation.get('kept_assignment_count',len(kept))!=len(kept)):
        return unavailable
    assignments=[o.get('assignment') for o in outputs]
    if (any(type(a) is not int for a in assignments)
            or sorted(assignments)!=list(range(len(kept)))):
        return unavailable
    failures=[]
    for index,output in enumerate(outputs):
        mutant=output.get('mutant',{})
        if mutant.get('status')!='complete':return unavailable
        failed=None
        for example_index,example in enumerate(mutant.get('train',[])):
            models=example.get('models',[])
            if (example.get('fit_comparison')=='native_closed_candidate_set'
                    and example.get('fits') is False
                    and example.get('output_set_defined') is True
                    and type(example.get('example')) is int and example['example']>=0
                    and models and all(m.get('status')=='complete' for m in models)):
                failed=dict(assignment=output['assignment'],example=example['example'],
                    pointer=f'/evaluation/outputs/{index}/mutant/train/{example_index}')
                break
        if failed is None:return unavailable
        failures.append(failed)
    return dict(valid=True,schema='mech-stored-train-nonfit-v1',pair_id=pair_id,
        source_sha256=source_sha256,fits_train=False,train_nonfit_complete=True,
        train_nonfit_receipt=dict(source_ref,source_sha256=source_sha256,
            field='/evaluation/outputs',kept_assignments=len(kept),failures=failures,
            comparison='native_closed_candidate_set',scope='every kept assignment'))
