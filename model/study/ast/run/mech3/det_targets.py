"""DET grade adapter over mech5's authenticated public target overlay.

No target acquisition, replay, search or comparison is implemented here. Import
mech5 only from the current checkout after its source and dependencies merge.
"""
from copy import deepcopy
from common import digest


def load_det_targets(database,pair_id,*,source_sha256,base_result_sha256):
    from mech5.read_targets import load_targets
    loaded=load_targets(database,pair_id,source_sha256=source_sha256,
                        base_result_sha256=base_result_sha256)
    if loaded.get('status')!='done' or loaded.get('valid') is not True:return loaded
    if loaded.get('kind','').upper()!='DET' or loaded.get('table_only') is not True:
        return dict(status='open',valid=False,reason='target result is not a table-only DET result')
    return loaded


def apply_det_targets(evidence,loaded):
    """Return evidence and central grade; never let held OUT imply DET fit.

    Caller must obtain loaded from load_det_targets. Its valid Unknown remains
    a completed attempt; missing or stale target evidence remains open.
    """
    from mech5.evidence import apply_targets
    from grades import reduce_grade
    if evidence.get('kind','').upper()!='DET':raise ValueError('DET evidence required')
    if (loaded.get('kind','').upper()!='DET' or loaded.get('table_only') is not True
            or loaded.get('record',{}).get('kind','').upper()!='DET'
            or loaded.get('record',{}).get('table_only') is not True):
        raise ValueError('authenticated table-only DET targets required')
    out=apply_targets(evidence,loaded)
    prior=deepcopy(out.get('program',{}))
    if not prior.get('table_only'):
        out.setdefault('legacy',{})['DET_held_OUT_program_evidence']=prior
    out['program']=dict(fits_train=None,fits_test=None,complete=False,
        applicable=False,table_only=True,receipt_ref=deepcopy(loaded['reference']),
        reason='DET is graded by its table; OUT holds the gold DET value')
    out['missing_steps']=list(dict.fromkeys(s for s in out.get('missing_steps',[])
                                          if not s.startswith('step_4_')))
    out['step4_det_ref']=deepcopy(loaded['reference'])
    out['step']=max(4,out.get('step',0))
    grade=reduce_grade(out)
    if grade['grade'] in ('fits','extension'):
        raise ValueError('central reducer assigned a forbidden DET fit grade')
    return out,grade


def result_identity(loaded):
    """Stable resume input for a future DET journal consumer."""
    if loaded.get('valid') is not True or loaded.get('status')!='done':
        raise ValueError('target result is open')
    if (digest(loaded['record'])!=loaded['result_sha256']
            or loaded['reference']['result_sha256']!=loaded['result_sha256']):
        raise ValueError('target result payload differs')
    return dict(reference=deepcopy(loaded['reference']),result_sha256=loaded['result_sha256'])
