"""Pinned shared CaseTables reader; renderer admission policy only."""
import hashlib
from pathlib import Path
import sys
import types

_ROOT=str(Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:sys.path.append(_ROOT)
from published_code import data_root

SOURCE_SHA256='f156c2ea9ef6e371c292acdc02e8f056e42451b0e48346162d1d26ab3e1588e7'
SOURCE=(data_root().parent/'ast/run/native-readers'/SOURCE_SHA256/'native_tables.py').resolve()
MODULE='arc_study.native_tables'


def _capture():
    existing=sys.modules.get(MODULE)
    if existing is not None:
        if getattr(existing,'__source_sha256__',None)!=SOURCE_SHA256 or Path(existing.__file__).resolve()!=SOURCE:
            raise ValueError('loaded canonical native reader differs from pinned source')
        return existing
    content=SOURCE.read_bytes()
    if hashlib.sha256(content).hexdigest()!=SOURCE_SHA256:
        raise ValueError('canonical native reader source differs from pinned SHA256')
    module=types.ModuleType(MODULE)
    module.__file__=str(SOURCE)
    module.__source_sha256__=SOURCE_SHA256
    sys.modules[MODULE]=module
    try:
        exec(compile(content,str(SOURCE),'exec'),module.__dict__)
        if module.SCHEMA!='arclog-native-tables-v1':
            raise ValueError('unsupported canonical native reader schema')
    except BaseException:
        sys.modules.pop(MODULE,None)
        raise
    parent=sys.modules.setdefault('arc_study',types.ModuleType('arc_study'))
    parent.native_tables=module
    return module


_READER=_capture()
PARTS=_READER.PARTS
FORMATS=_READER.FORMATS
WIDE=_READER.WIDE
SCHEMA=_READER.SCHEMA
ENTRY_DIAGNOSTIC_SCHEMA=_READER.ENTRY_DIAGNOSTIC_SCHEMA
VALUE_KINDS=_READER.VALUE_KINDS
EntryUnavailable=_READER.EntryUnavailable
require=_READER.require
blob=_READER.blob
width=_READER.width
case_payload=_READER.case_payload


class Native(_READER.Native):
    """Retain the renderer's explicit compatibility policy for older records."""
    def __init__(self,payload,**policy):
        if not {'missing_extent_status','legacy_status'}.intersection(policy):
            policy['missing_extent_status']='infer'
        super().__init__(payload,**policy)


def reader_metadata():
    return dict(schema=SCHEMA,qualified_module=MODULE,source=str(SOURCE),sha256=SOURCE_SHA256,
                entry_diagnostic_schema=ENTRY_DIAGNOSTIC_SCHEMA,
                default_missing_extent_status='infer',default_entry_projection_stop=True)
