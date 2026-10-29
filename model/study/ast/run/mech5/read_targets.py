"""Read-only target facts and ephemeral evidence views; no replay or writes."""
from collections import OrderedDict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sqlite3
import zlib
from ._paths import DATA_ROOT
from run import digest


def signature(path):
    s=Path(path).stat()
    return s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns


@lru_cache(maxsize=512)
def _file_hash(path,stamp):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def file_hash(path):
    path=Path(path).resolve()
    return _file_hash(str(path),signature(path))


def _refs(value):
    if isinstance(value,dict):
        if value.get('table')=='entries' and all(k in value for k in ('kind','key','result_sha256')):yield value
        else:
            for child in value.values():yield from _refs(child)
    elif isinstance(value,list):
        for child in value:yield from _refs(child)


# Cache only validated hashes/references, never tables. Journal facts retain
# their input identity across producer versions; this is not a disk-bitrot scan.
_VALIDATED=OrderedDict()
_TASK_INPUTS={}


def load_targets(database,pair_id,*,source_sha256,base_result_sha256=None,source_groups=None,derive=True):
    """Join pair_id to source-bound facts using one read-only WAL snapshot.

    facts/reference/result_sha256 bind the stored payload. record is a derived
    legacy-shaped view for apply_targets, never written. Historical code/config
    hashes are provenance, not current-file validity gates. A bounded completed
    attempt is done; absent, changed-input or corrupt facts are open.
    """
    db=None;base_db=None
    try:
        path=Path(database).resolve()
        db=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True);db.execute('BEGIN')
        producers={};resolved={};seen=set()
        def producer(code,config):
            key=(code,config)
            if key in producers:return producers[key]
            row=db.execute('SELECT manifest,settings FROM producers WHERE code=? AND config=?',key).fetchone()
            if not row:raise ValueError('producer provenance missing')
            manifest,settings=map(json.loads,row)
            if digest(manifest)!=code or digest(settings)!=config:raise ValueError('producer provenance digest differs')
            # Legacy spec hashes stay readable; no document or source file read.
            producers[key]=settings
            return settings
        def entry(kind,key,expected=None,need_value=True):
            row=db.execute('SELECT code,config,result_sha256 FROM entries WHERE kind=? AND key=?',(kind,key)).fetchone()
            if not row:raise ValueError('journal entry absent: '+kind+'/'+key)
            code,config,sha=row;producer(code,config)
            ref=dict(database=str(path),table='entries',kind=kind,key=key,result_sha256=sha,
                code_sha256=code,config_sha256=config)
            if expected and any(ref[k]!=expected[k] for k in ('result_sha256','code_sha256','config_sha256')):
                raise ValueError('journal reference changed: '+kind+'/'+key)
            cache_key=(str(path),kind,key,sha,code,config)
            value=None
            if need_value or cache_key not in _VALIDATED:
                payload=db.execute('SELECT payload FROM entries WHERE kind=? AND key=?',(kind,key)).fetchone()[0]
                value=json.loads(zlib.decompress(payload))
                if digest(value)!=sha:raise ValueError('journal payload digest differs: '+kind+'/'+key)
                _VALIDATED[cache_key]=tuple(_refs(value))
                if value.get('caller_task_inputs'):_TASK_INPUTS[cache_key]=value['caller_task_inputs']
                _VALIDATED.move_to_end(cache_key)
                while len(_VALIDATED)>4096:
                    expired,_=_VALIDATED.popitem(last=False);_TASK_INPUTS.pop(expired,None)
            if cache_key in _TASK_INPUTS:
                task=_TASK_INPUTS[cache_key]
                if file_hash(task['path'])!=task['sha256']:raise ValueError('task train/test inputs changed')
            refs=_VALIDATED[cache_key]
            token=(kind,key,sha)
            if token not in seen:
                seen.add(token)
                for child in refs:
                    if Path(child['database']).resolve()!=path:raise ValueError('cross-database child reference')
                    entry(child['kind'],child['key'],child,need_value=False)
            if need_value:resolved[(kind,key,sha)]=value
            return value,ref
        row=db.execute("SELECT 1 FROM entries WHERE kind='pair' AND key=?",(pair_id,)).fetchone()
        if not row:return dict(status='open',valid=False,reason='no target facts (DET may be pending)')
        facts,ref=entry('pair',pair_id)
        if facts.get('source_sha256')!=source_sha256:raise ValueError('pair input changed')
        if facts.get('schema') not in ('mech-target-pair-v1','mech-target-facts-v2'):
            raise ValueError('unsupported target fact schema')
        settings=producer(ref['code_sha256'],ref['config_sha256'])
        base_path=Path(settings.get('base') or facts.get('base_result_ref',{}).get('database')
                       or DATA_ROOT/'ast/run/mech/labels.sqlite3').resolve()
        base_db=sqlite3.connect(base_path.as_uri()+'?mode=ro',uri=True);base_db.execute('BEGIN')
        prior=base_db.execute('SELECT source_sha256,result_sha256,record_json FROM pairs WHERE pair_id=?',(pair_id,)).fetchone()
        if not prior or prior[0]!=source_sha256 or digest(json.loads(prior[2]))!=prior[1]:
            raise ValueError('canonical base input/result receipt differs')
        if base_result_sha256 is not None and prior[1]!=base_result_sha256:
            raise ValueError('caller base result is no longer current')
        base=json.loads(prior[2])
        def resolve(child):
            token=(child['kind'],child['key'],child['result_sha256'])
            if token not in resolved:entry(child['kind'],child['key'],child)
            return resolved[token]
        from .views import pair_view
        view=pair_view(facts,base,resolve,source_groups=source_groups) if derive else dict(
            pair_id=pair_id,source_sha256=source_sha256,base_result_sha256=prior[1],kind=base['kind'],
            table_only=base['kind'].casefold()=='det')
        view['base_result_ref']=dict(database=str(base_path),pair_id=pair_id,
            source_sha256=source_sha256,code_sha256=base['code_sha256'],
            config_sha256=base['config_sha256'],result_sha256=prior[1])
        return dict(status='done',valid=True,facts=facts,record=view,reference=ref,
            result_sha256=ref['result_sha256'],kind=base['kind'],table_only=base['kind'].casefold()=='det')
    except Exception as error:
        return dict(status='open',valid=False,reason=str(error),error_type=type(error).__name__)
    finally:
        if base_db is not None:base_db.close()
        if db is not None:db.close()
