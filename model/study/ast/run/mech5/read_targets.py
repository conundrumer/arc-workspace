"""Read-only target facts and ephemeral evidence views; no replay or writes."""
from collections import OrderedDict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import sqlite3
import zlib
from ._paths import DATA_ROOT
from run import digest,ONE_SHOT


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
    try:stamp=signature(path);path=str(path)
    except OSError:path=Path(path).resolve();stamp=signature(path);path=str(path)  # the same error, naming the resolved path
    return _file_hash(path,stamp)


def _refs(value):
    """The journal references of a decoded payload, in depth-first order."""
    found=[];pending=[value]
    while pending:
        item=pending.pop()
        if type(item) is dict:
            if item.get('table')=='entries' and all(k in item for k in ('kind','key','result_sha256')):found.append(item)
            else:pending.extend([c for c in reversed(list(item.values())) if type(c) in (dict,list)])
        elif type(item) is list:pending.extend([c for c in reversed(item) if type(c) in (dict,list)])
    return found


# Cache validated hashes/references. Journal facts retain their input identity
# across producer versions; this is not a disk-bitrot scan. The decoded payloads
# of the kinds in _SHARED are read by every pair of a case, so a bounded number
# of them (by payload bytes) stays decoded, under the same validation. They are
# read-only: a caller that keeps part of one copies it. Any other validated
# payload is kept as its JSON text (a bounded number of them) and decoded anew.
_VALIDATED=OrderedDict()
_TASK_INPUTS={}
_VALUES=OrderedDict()
_TEXTS=OrderedDict()
_SHARED=('axis','case')
_VALUES_BYTES=16*1024*1024
_TEXT_COUNT=2048
# Producers are content-addressed (code and config are the digests of what they
# name), so a producer that was verified once stays verified. _KNOWN holds the
# entries that were validated before, whose payloads a read need not fetch.
_PRODUCERS={}
_KNOWN=set()


def load_targets(database,pair_id,*,source_sha256,base_result_sha256=None,source_groups=None,derive=True,reads=ONE_SHOT):
    """Join pair_id to source-bound facts using one read-only WAL snapshot.

    facts/reference/result_sha256 bind the stored payload. record is a derived
    legacy-shaped view for apply_targets, never written. Historical code/config
    hashes are provenance, not current-file validity gates. A bounded completed
    attempt is done; absent, changed-input or corrupt facts are open.
    """
    db=None;base_db=None
    try:
        from .paused_archive import ensure_database
        ensure_database(database)
        path=Path(database).resolve()
        db=reads.open(path);db.execute('BEGIN')
        resolved={};seen=set();inside={};rows={}
        def producer(code,config):
            key=(str(path),code,config)
            if key in _PRODUCERS:return _PRODUCERS[key]
            row=db.execute('SELECT manifest,settings FROM producers WHERE code=? AND config=?',key[1:]).fetchone()
            if not row:raise ValueError('producer provenance missing')
            manifest,settings=map(json.loads,row)
            if digest(manifest)!=code or digest(settings)!=config:raise ValueError('producer provenance digest differs')
            # Legacy spec hashes stay readable; no document or source file read.
            _PRODUCERS[key]=settings
            return settings
        def fetch(wanted):
            """Read the rows of these (kind,key) entries together, with the payloads of those not validated before."""
            wanted=[w for w in dict.fromkeys(wanted) if w not in rows]
            for fresh in (True,False):
                group=[w for w in wanted if ((str(path),)+w not in _KNOWN)==fresh]
                for start in range(0,len(group),400):
                    chunk=group[start:start+400]
                    for kind,key,code,config,sha,payload in db.execute(
                            'SELECT kind,key,code,config,result_sha256,'+('payload' if fresh else 'NULL')
                            +' FROM entries WHERE (kind,key) IN (VALUES '+','.join(['(?,?)']*len(chunk))+')',
                            [part for w in chunk for part in w]):
                        rows[kind,key]=code,config,sha,payload
        def entry(kind,key,expected=None,need_value=True):
            fetch([(kind,key)])
            if (kind,key) not in rows:raise ValueError('journal entry absent: '+kind+'/'+key)
            code,config,sha,payload=rows[kind,key];producer(code,config)
            ref=dict(database=str(path),table='entries',kind=kind,key=key,result_sha256=sha,
                code_sha256=code,config_sha256=config)
            if expected and any(ref[k]!=expected[k] for k in ('result_sha256','code_sha256','config_sha256')):
                raise ValueError('journal reference changed: '+kind+'/'+key)
            cache_key=(str(path),kind,key,sha,code,config)
            value=None
            if need_value and cache_key in _VALUES and cache_key in _VALIDATED:
                value=_VALUES[cache_key][0]
                _VALUES.move_to_end(cache_key);_VALIDATED.move_to_end(cache_key)
            elif need_value or cache_key not in _VALIDATED:
                text=_TEXTS.get(cache_key) if cache_key in _VALIDATED else None
                if text is None:
                    if payload is None:payload=db.execute('SELECT payload FROM entries WHERE kind=? AND key=?',(kind,key)).fetchone()[0]
                    text=zlib.decompress(payload)
                    value=json.loads(text)
                    if digest(value)!=sha:raise ValueError('journal payload digest differs: '+kind+'/'+key)
                    if kind not in _SHARED:
                        _TEXTS[cache_key]=text
                        while len(_TEXTS)>_TEXT_COUNT:_TEXTS.popitem(last=False)
                else:
                    value=json.loads(text);_TEXTS.move_to_end(cache_key)
                if cache_key not in _VALIDATED:
                    _VALIDATED[cache_key]=tuple(_refs(value))
                    if value.get('caller_task_inputs'):_TASK_INPUTS[cache_key]=value['caller_task_inputs']
                    if len(_KNOWN)>=200000:_KNOWN.clear()
                    _KNOWN.add((str(path),kind,key))
                _VALIDATED.move_to_end(cache_key)
                while len(_VALIDATED)>4096:
                    expired,_=_VALIDATED.popitem(last=False);_TASK_INPUTS.pop(expired,None);_VALUES.pop(expired,None);_TEXTS.pop(expired,None)
                if kind in _SHARED:
                    _VALUES[cache_key]=value,len(text)
                    while len(_VALUES)>1 and sum(size for _,size in _VALUES.values())>_VALUES_BYTES:_VALUES.popitem(last=False)
            if cache_key in _TASK_INPUTS:
                task=_TASK_INPUTS[cache_key]
                if file_hash(task['path'])!=task['sha256']:raise ValueError('task train/test inputs changed')
            refs=_VALIDATED[cache_key]
            token=(kind,key,sha)
            if token not in seen:
                seen.add(token)
                fetch([(child['kind'],child['key']) for child in refs])
                for child in refs:
                    if child['database'] not in inside:inside[child['database']]=Path(child['database']).resolve()==path
                    if not inside[child['database']]:raise ValueError('cross-database child reference')
                    entry(child['kind'],child['key'],child,need_value=False)
            if value is not None:resolved[token]=value,ref
            return value,ref
        fetch([('pair',pair_id)])
        if ('pair',pair_id) not in rows:return dict(status='open',valid=False,reason='no target facts (DET may be pending)')
        facts,ref=entry('pair',pair_id)
        if facts.get('source_sha256')!=source_sha256:raise ValueError('pair input changed')
        if facts.get('schema') not in ('mech-target-pair-v1','mech-target-facts-v2'):
            raise ValueError('unsupported target fact schema')
        settings=producer(ref['code_sha256'],ref['config_sha256'])
        base_path=Path(settings.get('base') or facts.get('base_result_ref',{}).get('database')
                       or DATA_ROOT/'ast/run/mech/labels.sqlite3').resolve()
        base_db=reads.open(base_path);base_db.execute('BEGIN')
        prior=base_db.execute('SELECT source_sha256,result_sha256,record_json FROM pairs WHERE pair_id=?',(pair_id,)).fetchone()
        if not prior or prior[0]!=source_sha256 or digest(json.loads(prior[2]))!=prior[1]:
            raise ValueError('canonical base input/result receipt differs')
        if base_result_sha256 is not None and prior[1]!=base_result_sha256:
            raise ValueError('caller base result is no longer current')
        base=json.loads(prior[2])
        def resolve(child):
            token=(child['kind'],child['key'],child['result_sha256'])
            if token not in resolved:entry(child['kind'],child['key'],child)
            value,ref=resolved[token]
            if any(ref[k]!=child[k] for k in ('result_sha256','code_sha256','config_sha256')):
                raise ValueError('journal reference changed: '+child['kind']+'/'+child['key'])
            return value
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
        if base_db is not None:reads.done(base_db)
        if db is not None:reads.done(db)
