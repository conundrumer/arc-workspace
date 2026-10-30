"""Read authenticated host submissions; no runner, evaluator or grade copies."""
import hashlib
import importlib
from pathlib import Path

from study_paths import DATA_ROOT
from clause_evidence import clause_evidence_from_identity


def data_file(path):
    path=Path(path)
    root=DATA_ROOT.resolve()
    if path.is_absolute():
        result=path.resolve();result.relative_to(root)
    else:
        if '..' in path.parts:raise ValueError('noncanonical DATA-relative path')
        result=(root/path).resolve()
        if result.relative_to(root).as_posix()!=path.as_posix():
            raise ValueError('noncanonical DATA-relative path')
    return result


def submission_loader():
    """The host owner alone authenticates its native journal and final reply."""
    module=importlib.import_module('judge3.judge_workflows')
    loader=getattr(module,'load_submission',None)
    if not callable(loader):raise ValueError('merge runner read-only load_submission first')
    return loader


def submission_reference(path):
    path=data_file(path)
    return dict(path=path.relative_to(DATA_ROOT.resolve()).as_posix(),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def _axis_set(values):
    if not isinstance(values,list):raise ValueError('native axes absent')
    axes=[]
    for value in values:
        if (not isinstance(value,list) or len(value)!=3
                or any(type(x) is not int for x in value)
                or value[0]<0 or value[1] not in (1,2) or value[2]<0):
            raise ValueError('native axis shape invalid')
        axes.append(tuple(value))
    if len(set(axes))!=len(axes):raise ValueError('duplicate native axes')
    return set(axes)


def _complete_axes(receipt,expected=None):
    if not isinstance(receipt,dict):raise ValueError('native axis receipt absent')
    required=_axis_set(receipt.get('required_axes'))
    present=_axis_set(receipt.get('present_axes'))
    missing=_axis_set(receipt.get('missing_axes'))
    if (not required or present!=required or missing
            or {k[1] for k in required}!={1,2}
            or (expected is not None and required!=expected)):
        raise ValueError('native TRAIN/TEST axes incomplete or different')
    return required


def _source_axes(envelope,kept_count):
    expected=envelope.get('expected_axes',{})
    train=_axis_set(expected.get('train'));test=_axis_set(expected.get('test'))
    if not train or not test or any(k[1]!=1 for k in train) or any(k[1]!=2 for k in test):
        raise ValueError('source TRAIN/TEST axes absent or different')
    if {k[0] for k in train|test}!=set(range(kept_count)):
        raise ValueError('source kept assignment axes differ')
    scopes=[]
    for kind,axes in ((1,train),(2,test)):
        examples={k[2] for k in axes}
        if examples!=set(range(len(examples))):raise ValueError('source example axes are not dense')
        if any({k[2] for k in axes if k[0]==assignment}!=examples for assignment in range(kept_count)):
            raise ValueError('source example axes incomplete at a kept assignment')
        scopes.append(len(examples))
    return train|test,scopes[0],scopes[1]


def _clause(envelope,selected,base,reference):
    if (envelope.get('status')!='available'
            or envelope.get('pair_id')!=base['pair_id']
            or envelope.get('source_sha256')!=base['source_sha256']):
        raise ValueError('checked result unavailable or source binding differs')
    kind=selected.get('submitted_kind')
    result=envelope['checked']
    if (kind not in ('recovery','alternative') or envelope.get('submitted_kind')!=kind
            or envelope.get('operation')!=('check' if kind=='recovery' else 'alternative')
            or result.get('kind')!=kind or selected.get('outcome')!=result.get('outcome')
            or envelope['identities']['public']!={k:selected[k] for k in ('path','sha256')}):
        raise ValueError('selected clause/result identity, kind or outcome differs')
    role='continuation' if kind=='alternative' else 'recovery'
    kept_count=len(base.get('per_assignment',[]))
    expected,ntrain,ntest=_source_axes(envelope,kept_count)
    ref=dict(reference,checked_identities=envelope['identities'])
    answer=clause_evidence_from_identity(result,base['source_sha256'],kept_count,
        ref,purpose='answer',role=role,ntrain=ntrain,ntest=ntest)
    answer['submitted_kind']=kind
    # Validate actual native groups. Counts and Cartesian comparison expansion
    # never stand in for the source/selected target's own native axes.
    if result.get('outcome')!='refused by the engine':
        try:
            _complete_axes(envelope.get('native_axes',{}).get('candidate'),expected)
            if result.get('outcome') in ('recovery verified','partial source verified'):
                _complete_axes(envelope.get('native_axes',{}).get('target'))
        except ValueError as error:
            answer.update(outcome='unknown',judgment_complete=False,reason=str(error))
            if answer.get('check'):answer['check']['kept_contexts_complete']=False
    return answer


def load_submission_reference(reference,base):
    """Resolve host-owned proof, then normalize outcomes through one adapter.

    Availability is deliberately false until the runner's read-only loader is
    deployed. Producer hashes/current source files never invalidate executions.
    """
    unavailable=dict(status='unavailable',clauses=[],judge_run={})
    try:
        path=data_file(reference['path'])
        if submission_reference(path)!=reference:raise ValueError('submission artifact identity differs')
        loaded=submission_loader()(path,expected_pair_id=base['pair_id'],
                                   expected_source_sha256=base['source_sha256'])
        if loaded.get('status')!='available':
            raise ValueError(loaded.get('reason','host submission unavailable'))
        value=loaded['submission'];selected=value.get('selected_results')
        if (value.get('schema')!='judge-submission-v1'
                or value.get('pair_id')!=base['pair_id']
                or value.get('source_sha256')!=base['source_sha256']
                or not isinstance(value.get('session_id'),str) or not value['session_id']
                or value.get('host_completion_status') not in ('completed','interrupted','failed')
                or not isinstance(selected,list)
                or type(value.get('no_clause_found')) is not bool
                or value['no_clause_found']!=(not selected)):
            raise ValueError('host submission shape or source/session binding differs')
        if (value['host_completion_status']=='completed'
                and loaded.get('host_completion_authenticated') is not True):
            raise ValueError('actual host completion is not authenticated')
        checked=loaded.get('checked_results')
        if not isinstance(checked,list) or len(checked)!=len(selected):
            raise ValueError('selected checked result coverage differs')
        identities=loaded.get('identities')
        if not isinstance(identities,dict) or not identities:raise ValueError('host identities absent')
        ref=dict(submission=reference,host_identities=identities,session_id=value['session_id'])
        answers=[_clause(envelope,item,base,dict(ref,result_index=i))
                 for i,(item,envelope) in enumerate(zip(selected,checked))]
        complete=(value['host_completion_status']=='completed'
                  and loaded.get('host_completion_authenticated') is True
                  and all(a.get('judgment_complete') is True for a in answers))
        # One known failed clause cannot stand in for an unresolved answer in
        # the same session. Canonical mechanical admission is applied at reduce.
        if not complete:
            for answer in answers:answer['judgment_complete']=False
        return dict(status='available',clauses=answers,
            judge_run=dict(complete=complete,answered=value['host_completion_status']=='completed',
                no_clause_found=value['no_clause_found'],requires_admission=True,
                receipt_ref=ref,host_completion_status=value['host_completion_status']))
    except Exception as error:
        return dict(unavailable,reason=f'{type(error).__name__}: {error}')
