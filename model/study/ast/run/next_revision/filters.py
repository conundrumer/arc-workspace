"""Compatibility import for the single canonical native-row filter policy."""
import importlib.util
from pathlib import Path
import sys

_path=Path(__file__).resolve().parents[1]/'filters.py'
_name='arc_study.filters'
_module=sys.modules.get(_name)
_bare=sys.modules.get('filters')
if _module is None:
    if _bare is not None and Path(_bare.__file__).resolve()==_path:
        _module=_bare
    else:
        if _bare is not None and _bare is not sys.modules.get(__name__):
            raise ImportError('filters entry name has conflicting source path')
        _spec=importlib.util.spec_from_file_location(_name,_path)
        _module=importlib.util.module_from_spec(_spec)
        sys.modules[_name]=_module
        sys.modules['filters']=_module
        _spec.loader.exec_module(_module)
    sys.modules[_name]=_module
elif Path(_module.__file__).resolve()!=_path:
    raise ImportError('canonical filters module has conflicting source path')
sys.modules['filters']=_module
for _key in dir(_module):
    if not _key.startswith('__'):
        globals()[_key]=getattr(_module,_key)
