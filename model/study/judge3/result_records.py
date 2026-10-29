"""Private, read-only-resolvable bindings for public judge command results.

No native imports, replay, grade, prose-specification identity or judge-run
completion inference. An authenticated unknown/refusal is still only one
command's stored result; it does not establish a completed negative search.
"""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from study_paths import DATA_ROOT
if __package__:
    from .dataset_format import FORMAT,write_json
else:
    from dataset_format import FORMAT,write_json

SCHEMA='judge-checked-envelope-v1'
INDEX_SCHEMA='judge-result-index-v1'


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _json_digest(value):
    return _digest(json.dumps(value,ensure_ascii=False,sort_keys=True,
                              separators=(',',':'),allow_nan=False).encode())


def _relative(path):
    resolved=Path(path).resolve()
    return resolved.relative_to(DATA_ROOT.resolve()).as_posix()


def _resolve(relative):
    path=Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('identity path is not canonical DATA-relative')
    result=(DATA_ROOT/path).resolve()
    if _relative(result)!=relative:
        raise ValueError('identity path is not canonical DATA-relative')
    return result


def _identity(path):
    return dict(path=_relative(path),sha256=_digest(Path(path).read_bytes()))


def _read(identity):
    path=_resolve(identity['path']);raw=path.read_bytes()
    if _digest(raw)!=identity['sha256']:
        raise ValueError('stored file identity differs: '+identity['path'])
    return json.loads(raw),path


def _index_path(public_path):
    key=_digest(_relative(public_path).encode())
    return DATA_ROOT/'judgetool/dataset-result-index'/(key+'.json')


def _kind(operation):
    if operation not in ('run','check','alternative'):
        raise ValueError('unsupported operation')
    return None if operation=='run' else 'alternative' if operation=='alternative' else 'recovery'


def publish_checked_result(public_path,private_path,*,checked,pair_id,
                           source_sha256,source_record_path,operation,columns,
                           expected_axes):
    """Called by the command after writing its public result, commits index last."""
    kind=_kind(operation)
    public=_identity(public_path)
    document=json.loads(Path(public_path).read_text())
    public_table=None
    if document.get('table') is not None:
        table=Path(document['table'])
        if table.is_absolute() or '..' in table.parts:
            raise ValueError('public table path must be relative to its result directory')
        public_table=_identity(Path(public_path).parent/table)
    source=_identity(source_record_path)
    envelope=dict(schema=SCHEMA,pair_id=pair_id,source_sha256=source_sha256,
        operation=operation,submitted_kind=kind,columns=deepcopy(columns),
        expected_axes=deepcopy(expected_axes),public=public,public_table=public_table,source_record=source,
        checked=deepcopy(checked))
    if checked.get('source_sha256')!=source_sha256:
        raise ValueError('checked/source identity mismatch')
    write_json(private_path,envelope)
    index=dict(schema=INDEX_SCHEMA,record_complete=True,pair_id=pair_id,
        source_sha256=source_sha256,operation=operation,submitted_kind=kind,
        public=public,public_table=public_table,private=_identity(private_path),source_record=source,
        producer=dict(path=str(Path(__file__).resolve()),sha256=_digest(Path(__file__).read_bytes())))
    write_json(_index_path(public_path),index)
    return index


def _validate_axes(receipt):
    """Validate serialized receipt shape, without deriving observed axes/counts."""
    keys=('required_axes','present_axes','missing_axes')
    if not isinstance(receipt,dict) or any(k not in receipt for k in keys):
        raise ValueError('native axis receipt is missing')
    for name in keys:
        axes=receipt[name]
        if not isinstance(axes,list) or any(not isinstance(a,list) or len(a)!=3
                or any(type(v) is not int for v in a) or a[0]<0 or a[1] not in (1,2)
                or a[2]<0 for a in axes):
            raise ValueError('native axis receipt shape differs')
    return {k:deepcopy(receipt[k]) for k in keys}


def load_checked_result(path,*,expected_pair_id=None,expected_source_sha256=None):
    """Resolve one stored result; missing/incomplete/tampered bindings unavailable.

    Returns the unnormalized native checked result plus exact stored native
    axes when supplied. It never infers session completion from this outcome.
    A separate authenticated submission/runner completion is required by the
    labeler even for a refused or did-not-verify clause.
    """
    try:
        public_path=Path(path)
        public_path=public_path.resolve() if public_path.is_absolute() else _resolve(public_path.as_posix())
        index_path=_index_path(public_path)
        index=json.loads(index_path.read_text())
        if not isinstance(index,dict) or index.get('schema')!=INDEX_SCHEMA or index.get('record_complete') is not True:
            raise ValueError('result index is incomplete or unsupported')
        if index['public']['path']!=_relative(public_path):
            raise ValueError('public path differs from indexed identity')
        if not index['private']['path'].startswith('judgetool/dataset-runs/'):
            raise ValueError('private result is outside the checked-record store')
        public,_=_read(index['public']);envelope,_=_read(index['private'])
        if not isinstance(envelope,dict) or envelope.get('schema')!=SCHEMA:
            raise ValueError('checked envelope schema differs')
        for key in ('pair_id','source_sha256','operation','submitted_kind','public','public_table','source_record'):
            if index[key]!=envelope[key]:
                raise ValueError('stored '+key+' binding differs')
        if expected_pair_id is not None and envelope['pair_id']!=expected_pair_id:
            raise ValueError('pair identity differs from requested pair')
        if expected_source_sha256 is not None and envelope['source_sha256']!=expected_source_sha256:
            raise ValueError('source identity differs from requested source')
        operation=envelope['operation'];kind=_kind(operation)
        if kind!=envelope['submitted_kind']:
            raise ValueError('operation/submitted-kind binding differs')
        if (not isinstance(public,dict) or public.get('format')!=FORMAT or public.get('kind')!='result'
                or public.get('pair_id')!=envelope['pair_id'] or public.get('command')!=operation):
            raise ValueError('public result binding differs')
        if public.get('table') is not None:
            table=Path(public['table'])
            if table.is_absolute() or '..' in table.parts or index['public_table'] is None:
                raise ValueError('public table binding is missing or outside its result directory')
            if _relative(public_path.parent/table)!=index['public_table']['path']:
                raise ValueError('public table path differs from indexed identity')
            table_document,_=_read(index['public_table'])
            if not isinstance(table_document,dict) or table_document.get('format')!=FORMAT or table_document.get('kind')!='table':
                raise ValueError('public table format differs')
        elif index['public_table'] is not None:
            raise ValueError('unexpected indexed public table')
        source_path=_resolve(index['source_record']['path'])
        source_raw=source_path.read_bytes()
        if _digest(source_raw)!=index['source_record']['sha256']:
            raise ValueError('source record file identity differs')
        source=json.loads(gzip.decompress(source_raw) if source_path.suffix=='.gz' else source_raw)
        if _json_digest(source)!=envelope['source_sha256']:
            raise ValueError('source record canonical identity differs')
        checked=envelope['checked']
        if (not isinstance(checked,dict) or checked.get('source_sha256')!=envelope['source_sha256'] or
                checked.get('kind')!=(kind or 'recovery')):
            raise ValueError('native source/submitted-kind binding differs')
        clause=checked.get('submitted_clause')
        candidate=_json_digest(dict(kind=kind or 'recovery',clause=clause,columns=envelope['columns']))
        if not isinstance(clause,str) or candidate!=checked.get('candidate_sha256'):
            raise ValueError('submitted candidate identity differs')
        if operation!='run' and public.get('outcome')!=checked.get('outcome'):
            raise ValueError('public/native outcome binding differs')
        expected=envelope['expected_axes']
        if not isinstance(expected,dict) or set(expected)!= {'train','test'}:
            raise ValueError('source-bound expected axes are missing')
        for name,kind_number in (('train',1),('test',2)):
            axes=expected[name]
            _validate_axes(dict(required_axes=axes,present_axes=[],missing_axes=[]))
            if any(a[1]!=kind_number for a in axes):
                raise ValueError('source-bound train/test axis kinds differ')
        native_axes={}
        for name,key in (('candidate','context_receipt'),('target','target_receipt')):
            receipt=checked.get(key)
            if isinstance(receipt,dict) and any(k in receipt for k in ('required_axes','present_axes','missing_axes')):
                native_axes[name]=_validate_axes(receipt)
        if 'candidate' in native_axes and sorted(native_axes['candidate']['required_axes'])!=sorted(expected['train']+expected['test']):
            raise ValueError('native candidate axes differ from source-bound expected axes')
        if checked.get('outcome') in ('recovery verified','partial source verified','continuation passed'):
            if 'candidate' not in native_axes:
                raise ValueError('positive result lacks its native candidate axis receipt')
            if checked['outcome']!='continuation passed' and 'target' not in native_axes:
                raise ValueError('recovery lacks its native selected-target axis receipt')
        return dict(schema=SCHEMA,status='available',pair_id=envelope['pair_id'],
            source_sha256=envelope['source_sha256'],operation=operation,submitted_kind=kind,
            columns=deepcopy(envelope['columns']),expected_axes=deepcopy(expected),
            native_axes=native_axes,checked=checked,
            identities=dict(public=index['public'],public_table=index['public_table'],private=index['private'],source_record=index['source_record'],
                            index=_identity(index_path)))
    except (OSError,EOFError,ValueError,TypeError,KeyError) as error:
        return dict(schema=SCHEMA,status='unavailable',reason=f'{type(error).__name__}: {error}')
