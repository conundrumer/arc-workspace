"""Pinned native-study evidence validation and GIVEN/FITS presentation.

Only the selected committed runtime owns schema validation. This adapter does
not judge candidate sets or infer FITS from a model's GIVEN comparison.
"""
import hashlib
import json
import os
import sys
from pathlib import Path
import types
from published_code import data_root,resolve_runtime

if __name__!='render2.execution':
    raise ImportError('import the shared adapter as render2.execution')

_DEFAULT=resolve_runtime(os.environ.get('JUDGE_WHEEL_ENV',str(data_root().parent/'ast/run/CURRENT.json')))
_module=None
_wheel=None
_metadata=None


def configure(wheel=None):
    """Pin the archived canonical helper before any evidence is validated."""
    global _module,_wheel,_metadata
    selected,reason=resolve_runtime(wheel) if wheel is not None else _DEFAULT
    if selected is None:raise ValueError('execution evidence validator unavailable: '+str(reason))
    selected=Path(selected).resolve()
    runtime=selected.parent
    receipt_path=runtime/'ready.json'
    if not receipt_path.exists():raise ValueError('execution evidence requires committed runtime receipt: '+str(receipt_path))
    receipt=json.loads(receipt_path.read_text())
    if Path(receipt['python']).parent.parent.resolve()!=selected:
        raise ValueError('execution helper receipt python differs from selected environment')
    if _module is not None:
        if selected!=_wheel or receipt['revision']!=_metadata['engine_revision']:
            raise ValueError('execution evidence runtime cannot change after pinning')
        return dict(_metadata)
    dependency=receipt.get('execution_evidence')
    if not isinstance(dependency,dict):raise ValueError('execution evidence dependency absent from selected runtime receipt')
    source=Path(dependency['path']).resolve()
    if source!=(Path(receipt['checks'])/'execution_evidence.py').resolve():
        raise ValueError('execution evidence receipt path differs from archived checks')
    if not source.is_relative_to(runtime):raise ValueError('execution evidence helper is outside its immutable runtime')
    if not source.is_file():raise ValueError('execution evidence validator unavailable in selected runtime: '+str(source))
    content=source.read_bytes()
    digest=hashlib.sha256(content).hexdigest()
    if digest!=dependency['sha256']:raise ValueError('execution evidence source differs from committed runtime receipt')
    module=types.ModuleType('_pinned_study_execution_evidence');module.__file__=str(source)
    sys.modules[module.__name__]=module
    try:
        exec(compile(content,str(source),'exec'),module.__dict__)
        if getattr(module,'SCHEMA',None)!='study-execution-evidence-v1':raise ValueError('unknown execution evidence validator schema')
        for name in ('validate_train_example','example_fit'):
            if not callable(getattr(module,name,None)):raise ValueError('canonical execution helper lacks '+name)
    except BaseException:
        sys.modules.pop(module.__name__,None)
        raise
    _wheel=selected;_module=module
    _metadata=dict(schema=module.SCHEMA,source=str(source),sha256=digest,engine_revision=receipt['revision'])
    return dict(_metadata)


def validate_train_example(example,context='train example'):
    if _module is None:configure()
    return _module.validate_train_example(example,context=context)


def example_fit(example,context='train example'):
    if _module is None:configure()
    return _module.example_fit(example,context=context)


def given_text(model):
    """Caption an already validated per-model GIVEN diagnostic."""
    if model['status']!='complete':text=model['status']
    elif model['equals']:text='equals GIVEN train output'
    else:text=str(model['differing_cells'])+' differing/missing cells from GIVEN train output'
    return text+('; '+str(model['reason']) if model.get('reason') else '')



def fit_text(example):
    """Present the native example judgement; never solve a candidate set."""
    fit=example_fit(example)
    parts=['native accepted-set FITS unavailable (not reported)' if fit is None else 'native accepted-set FITS: '+('yes' if fit else 'no')]
    if 'distinct_output_grids' in example:parts.append(str(example['distinct_output_grids'])+' distinct valid output grids')
    if 'output_set_defined' in example:parts.append('complete output set '+('defined' if example['output_set_defined'] else 'undefined'))
    if 'accepted_candidate_sizes' in example:parts.append('accepted candidate set sizes: '+' / '.join(map(str,example['accepted_candidate_sizes'])))
    return '; '.join(parts)
