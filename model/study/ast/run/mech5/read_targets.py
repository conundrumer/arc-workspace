"""Read-only validity for all-target overlays. No replay or comparison.

A durable Unknown is done. Missing, stale or corrupt inputs/evidence are open.
Caller supplies the currently authenticated source and base-result identities.
"""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sqlite3
import zlib
from ._paths import CODE_ROOT
from run import digest


def signature(path):
    s=Path(path).stat()
    return s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns


@lru_cache(maxsize=2048)
def _file_hash(path,stamp):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def file_hash(path):
    path=Path(path).resolve()
    return _file_hash(str(path),signature(path))


def _refs(value):
    if isinstance(value,dict):
        if value.get('table')=='entries' and all(k in value for k in ('kind','key','result_sha256')):
            yield value
        else:
            for child in value.values():yield from _refs(child)
    elif isinstance(value,list):
        for child in value:yield from _refs(child)


def _db_stamp(path):
    return (signature(path),signature(str(path)+'-wal') if Path(str(path)+'-wal').exists() else None)


@lru_cache(maxsize=256)
def _verify_child(path,stamp,kind,key,sha,code,config):
    """Cache only validation, keyed by DB+WAL stat and complete reference."""
    db=sqlite3.connect(Path(path).as_uri()+'?mode=ro',uri=True)
    try:
        row=db.execute('SELECT code,config,result_sha256,payload FROM entries WHERE kind=? AND key=?',(kind,key)).fetchone()
        if not row or tuple(row[:3])!=(code,config,sha):raise ValueError('child journal identity differs: '+kind+'/'+key)
        payload=json.loads(zlib.decompress(row[3]))
        if digest(payload)!=sha:raise ValueError('child journal payload differs: '+kind+'/'+key)
        return tuple((r['database'],r['kind'],r['key'],r['result_sha256'],r['code_sha256'],r['config_sha256'])
                     for r in _refs(payload))
    finally:db.close()


def _validate_refs(value,path,code,config,seen):
    for ref in _refs(value):
        if Path(ref['database']).resolve()!=path:raise ValueError('child reference uses another database')
        if (ref['code_sha256'],ref['config_sha256'])!=(code,config):raise ValueError('child producer differs')
        key=(ref['kind'],ref['key'],ref['result_sha256'])
        if key in seen:continue
        seen.add(key)
        children=_verify_child(str(path),_db_stamp(path),*key,code,config)
        _validate_refs([dict(database=d,table='entries',kind=k,key=i,result_sha256=s,
                            code_sha256=c,config_sha256=f) for d,k,i,s,c,f in children],path,code,config,seen)


def load_targets(database,pair_id,*,source_sha256,base_result_sha256):
    """Return done/open, valid, record?, durable reference and result SHA.

    Validity checks producer files/config, current base row and every referenced
    case/comparison/search/candidate payload. Paths in code manifests are study
    relative, so merging unchanged tracked files preserves validity.
    """
    db=None;base=None
    try:
        path=Path(database).resolve()
        db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True);db.execute('BEGIN')
        row=db.execute("SELECT inputs,code,config,result_sha256,payload FROM entries WHERE kind='pair' AND key=?",(pair_id,)).fetchone()
        if not row:return dict(status='open',valid=False,reason='no target result')
        value=json.loads(zlib.decompress(row[4]));code,config=row[1:3]
        inputs=dict(pair_id=pair_id,source_sha256=source_sha256,base_result_sha256=base_result_sha256)
        if row[0]!=digest(inputs) or digest(value)!=row[3]:raise ValueError('source/base/result digest differs')
        if value.get('schema')!='mech-target-pair-v1':raise ValueError('unsupported target schema')
        if any(value.get(k)!=v for k,v in inputs.items()):raise ValueError('record source/base identity differs')
        producer=db.execute('SELECT manifest,settings FROM producers WHERE code=? AND config=?',(code,config)).fetchone()
        if not producer:raise ValueError('producer manifest unavailable')
        manifest,settings=map(json.loads,producer)
        if digest(manifest)!=code or digest(settings)!=config:raise ValueError('producer code/config digest differs')
        for name,expected in manifest.items():
            file=Path(name) if Path(name).is_absolute() else CODE_ROOT/name
            if file_hash(file)!=expected:raise ValueError('target producer changed: '+str(file))
        if value.get('task_receipt') and file_hash(value['task_receipt']['path'])!=value['task_receipt']['sha256']:
            raise ValueError('task train/test inputs changed')
        ref=value['base_result_ref']
        base=sqlite3.connect(Path(ref['database']).resolve().as_uri()+'?mode=ro',uri=True);base.execute('BEGIN')
        prior=base.execute('SELECT source_sha256,code_sha256,config_sha256,result_sha256,record_json FROM pairs WHERE pair_id=?',(pair_id,)).fetchone()
        if (not prior or tuple(prior[:4])!=(source_sha256,ref['code_sha256'],ref['config_sha256'],base_result_sha256)
                or digest(json.loads(prior[4]))!=base_result_sha256):raise ValueError('current base receipt differs')
        _validate_refs(value,path,code,config,set())
        reference=dict(database=str(path),table='entries',kind='pair',key=pair_id,
                       result_sha256=row[3],code_sha256=code,config_sha256=config)
        return dict(status='done',valid=True,record=value,reference=reference,result_sha256=row[3],
                    outcome=value['outcome'],kind=value['kind'],table_only=value['table_only'])
    except Exception as error:
        return dict(status='open',valid=False,reason=str(error),error_type=type(error).__name__)
    finally:
        if base is not None:base.close()
        if db is not None:db.close()
