"""Input-proved corpus relocation. No grades, evaluation, or implicit reruns.

Old SHA identities remain real historical byte identities. Backward deltas restore
those exact records; native compressed blocks are borrowed by exact content SHA.
"""
from collections import OrderedDict
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import zlib

try:
    from .run import canonical,digest
except ImportError:
    from run import canonical,digest
from study_paths import DATA_ROOT

ROOT=DATA_ROOT/'ast/run/corpus-v12-body-full/migration'
DATABASE=ROOT/'bindings.sqlite3'
OLD=DATA_ROOT/'ast/run/corpus-v11'
CONNECTIONS={}
STREAMS=OrderedDict()


def database_path():return Path(os.environ.get('STUDY_SOURCE_BINDINGS',DATABASE)).resolve()

class _Rows:
    def __init__(self,rows):self.rows=rows
    def __iter__(self):return iter(self.rows)
    def fetchone(self):return self.rows[0] if self.rows else None
    def fetchall(self):return self.rows


class _Registry:
    """Use the shared short RO snapshot/lock protocol, including closed WALs."""
    def __init__(self,path,lock):
        from mech2.read_normal import _Database
        self.database=_Database(path,lock)
    def execute(self,sql,args=()):
        with self.database.snapshot() as db:return _Rows(db.execute(sql,args).fetchall())


def connection():
    path=database_path()
    if not path.exists():return None
    key=str(path),os.getpid()
    if key not in CONNECTIONS:CONNECTIONS[key]=_Registry(path,Path(str(path)+'.lock'))
    return CONNECTIONS[key]


def object_value(db,sha):
    row=db.execute('SELECT payload FROM objects WHERE sha256=?',(sha,)).fetchone()
    if not row:raise ValueError('migration object absent: '+sha)
    value=json.loads(zlib.decompress(row[0]))
    def expand(v):
        if isinstance(v,dict):
            if set(v)=={'$migration_object'}:return object_value(db,v['$migration_object'])
            return {k:expand(x) for k,x in v.items()}
        if isinstance(v,list):return [expand(x) for x in v]
        return v
    value=expand(value)
    if digest(value)!=sha:raise ValueError('migration object digest differs')
    return value


def reverse_patch(current,patch):
    value=deepcopy(current)
    for path,present,item in patch:
        owner=value
        for part in path[:-1]:owner=owner[part]
        if present:owner[path[-1]]=item
        else:owner.pop(path[-1],None)
    return value


def source_entry(source_sha):
    db=connection()
    if db is None:return None
    row=db.execute('SELECT pair_id,current_sha,current_locator,patch_ref,proof_ref FROM sources WHERE old_sha=?',(source_sha,)).fetchone()
    if row:return dict(old_sha=source_sha,pair_id=row[0],current_sha=row[1],locator=json.loads(row[2]),patch_ref=row[3],proof_ref=row[4])
    row=db.execute('SELECT s.old_sha,s.pair_id,s.current_sha,s.current_locator,s.patch_ref,s.proof_ref FROM sources s LEFT JOIN requests r ON s.old_sha=r.old_sha WHERE s.current_sha=? ORDER BY (r.base_result IS NULL),s.old_sha LIMIT 1',(source_sha,)).fetchone()
    if row:return dict(old_sha=row[0],pair_id=row[1],current_sha=row[2],locator=json.loads(row[3]),patch_ref=row[4],proof_ref=row[5])
    return None


def proof(entry):
    value=object_value(connection(),entry['proof_ref'])
    expected=dict(pair_id=entry['pair_id'],old_source_sha256=entry['old_sha'],current_source_sha256=entry['current_sha'],
                  current_locator_sha256=digest(entry['locator']))
    if any(value.get(k)!=v for k,v in expected.items()):raise ValueError('source binding receipt differs')
    return value


def _read_locator(locator,streams=None):
    from judge3.framed_jsonl import JsonlReader
    cache=STREAMS if streams is None else streams
    path=Path(locator['corpus'])/locator['task']/locator['file'];wanted=locator['line']
    def reader_path():
        return path.with_suffix('') if not path.exists() and path.suffix in ('.gz','.zst') else path
    previous=cache.pop(path,None)
    if previous is None:
        reader=JsonlReader(reader_path());previous=(reader,reader.iter_lines(),0,None)
    reader,stream,line,value=previous
    if reader.path.suffix=='.zst':
        try:value=json.loads(reader.read_line(wanted))
        except IndexError:
            # A published locator can follow a newly committed append frame.
            reader.close();reader=JsonlReader(reader_path());stream=reader.iter_lines()
            value=json.loads(reader.read_line(wanted))
        line=wanted
    else:
        if line>wanted:
            stream.close();stream=reader.iter_lines();line=0
        while line<wanted:
            raw=next(stream);line+=1
            if line==wanted:value=json.loads(raw)
    cache[path]=(reader,stream,line,value)
    while len(cache)>16:
        r,it,_,_=cache.popitem(last=False)[1];it.close();r.close()
    return value


def record(source_sha,*,current=False):
    entry=source_entry(source_sha)
    if entry is None:raise KeyError(source_sha)
    value=_read_locator(entry['locator'])
    if digest(value)!=entry['current_sha']:raise ValueError('current source bytes changed')
    if not current and source_sha==entry['old_sha'] and entry['old_sha']!=entry['current_sha']:
        value=reverse_patch(value,object_value(connection(),entry['patch_ref']))
        if digest(value)!=source_sha:raise ValueError('historical source delta differs')
    return value


def active():
    db=connection()
    return bool(db and db.execute("SELECT value FROM metadata WHERE key='active' AND value='true'").fetchone())


def legacy_path(path):
    path=Path(path).resolve()
    return path==OLD.resolve() or OLD.resolve() in path.parents or ROOT/'legacy' in path.parents


def read_native_bytes(ref,base):
    path=Path(base)/ref['path']
    if not legacy_path(path):return None
    db=connection()
    if db is None:return None
    row=db.execute('SELECT bytes,path,offset,payload FROM blocks WHERE sha256=?',(ref['sha256'],)).fetchone()
    if row:
        if row[0]!=ref['bytes']:raise ValueError('relocated native length differs')
        if row[3] is not None:return bytes(row[3])
        with Path(row[1]).open('rb') as f:f.seek(row[2]);return f.read(row[0])
    if active():raise ValueError('unmigrated v11 native dependency: '+str(path)+' '+ref['sha256'])
    return None


def relocated_file(path):
    path=Path(path).resolve()
    if path!=OLD.resolve() and OLD.resolve() not in path.parents:return path
    db=connection()
    if db:
        row=db.execute('SELECT destination FROM files WHERE original=?',(str(path),)).fetchone()
        if row:return Path(row[0])
        if active():raise ValueError('unmigrated v11 file dependency: '+str(path))
    return path


def scope_equal(pair_id,a,b,scope):
    if a==b:return True
    db=connection()
    if db is None:return False
    row=db.execute('SELECT proof_ref FROM sources WHERE pair_id=? AND ((old_sha=? AND current_sha=?) OR (old_sha=? AND current_sha=?))',
                   (pair_id,a,b,b,a)).fetchone()
    if not row:return False
    flags=object_value(db,row[0]).get('compatible',{})
    return flags.get(scope) is True


def equivalent_sources(a,b,scope):
    if a==b:return True
    db=connection()
    if db is None:return False
    row=db.execute('SELECT pair_id FROM sources WHERE (old_sha=? AND current_sha=?) OR (old_sha=? AND current_sha=?)',(a,b,b,a)).fetchone()
    return bool(row and scope_equal(row[0],a,b,scope))


def receipt_source(pair_id,current_sha,scope):
    db=connection()
    if db is None:return current_sha
    for old,ref in db.execute('SELECT s.old_sha,s.proof_ref FROM sources s LEFT JOIN requests r ON s.old_sha=r.old_sha WHERE s.pair_id=? AND s.current_sha=? ORDER BY (r.base_result IS NULL),s.old_sha',(pair_id,current_sha)):
        if object_value(db,ref).get('compatible',{}).get(scope) is True:return old
    return current_sha


def history_base(pair_id):
    db=connection()
    if db is None:return None
    row=db.execute('SELECT old_result,current_result,patch_ref FROM base_changes WHERE pair_id=? AND applied=1',(pair_id,)).fetchone()
    if not row:return None
    base=Path(dict(db.execute('SELECT key,value FROM metadata'))['base'])
    from mech2.read_normal import _Database
    live=_Database(base,Path(str(base)+'.lock'))
    try:
        with live.snapshot() as rows:r=rows.execute('SELECT result_sha256,record_json FROM pairs WHERE pair_id=?',(pair_id,)).fetchone()
    finally:live.close()
    if not r or r[0]!=row[1] or digest(json.loads(r[1]))!=r[0]:raise ValueError('migration base successor changed')
    value=reverse_patch(json.loads(r[1]),object_value(db,row[2]))
    if digest(value)!=row[0]:raise ValueError('migration historical base differs')
    return value


def legacy_identity(pair_id,source_sha,base_sha,scope):
    db=connection()
    if db is None:return source_sha,base_sha
    row=db.execute('SELECT s.old_sha,s.proof_ref FROM sources s LEFT JOIN requests r ON s.old_sha=r.old_sha WHERE s.pair_id=? AND s.current_sha=? ORDER BY (r.base_result IS NULL),s.old_sha LIMIT 1',(pair_id,source_sha)).fetchone()
    change=db.execute('SELECT old_result,current_result FROM base_changes WHERE pair_id=? AND applied=1',(pair_id,)).fetchone()
    if row and change and object_value(db,row[1]).get('compatible',{}).get(scope) is True:
        return row[0],change[0]
    return source_sha,base_sha


def receipt_base(base,scope,source_sha=None):
    prior=receipt_source(base['pair_id'],base['source_sha256'],scope) if source_sha is None else source_sha
    db=connection()
    if db is None:return base
    if source_sha is not None and source_sha==base['source_sha256']:return base
    entry=source_entry(base['source_sha256'])
    if entry is None or proof(entry).get('compatible',{}).get(scope) is not True:
        if source_sha is not None and source_sha!=base['source_sha256']:raise ValueError('source footprint changed: '+scope)
        return base
    changed=db.execute('SELECT old_result FROM base_changes WHERE pair_id=? AND applied=1',(base['pair_id'],)).fetchone()
    if changed is None:return base
    if not scope_equal(base['pair_id'],prior,base['source_sha256'],scope):raise ValueError('source footprint changed: '+scope)
    old=history_base(base['pair_id'])
    if old is None or old['source_sha256']!=prior:raise ValueError('historical base receipt absent')
    return old



def application_compatible(flags,assignment,witness):
    if flags.get('compatible',{}).get('tests') is True:return True
    per=flags.get('test_assignment_equal',[])
    branches=witness.get('selection_any',[witness.get('selection',[])])
    reads_available=any(a.get('kind') in ('semijoin','antijoin') for branch in branches for a in branch)
    return (assignment<len(per) and per[assignment] is True
            and (flags.get('manifest_equal',{}).get('full') or not reads_available))

def witness_source(base,item):
    entry=source_entry(base['source_sha256'])
    if entry is None or entry['old_sha']==base['source_sha256']:return base,item
    if not application_compatible(proof(entry),item['assignment'],item.get('witness',{})):return base,item
    old=history_base(base['pair_id'])
    if old is None:return base,item
    prior=next((a for a in old.get('per_assignment',[]) if a['assignment']==item['assignment']),None)
    db=connection()
    allowed=prior is not None and digest(prior.get('witness'))==digest(item.get('witness'))
    if not allowed and prior is not None and db:
        allowed=bool(db.execute('SELECT 1 FROM witness_aliases WHERE pair_id=? AND assignment=? AND old_sha=? AND new_sha=?',
            (base['pair_id'],item['assignment'],digest(prior.get('witness')),digest(item.get('witness')))).fetchone())
    return (old,prior) if allowed else (base,item)


def binding_reference(pair_id):
    db=connection()
    if db is None:return None
    row=db.execute('SELECT old_result,current_result FROM base_changes WHERE pair_id=? AND applied=1',(pair_id,)).fetchone()
    if not row:return None
    return dict(database=str(database_path()),table='base_changes',pair_id=pair_id,old_result_sha256=row[0],current_result_sha256=row[1])


def locator_record(locator,expected):
    entry=source_entry(expected)
    if entry is not None:return record(expected)
    source=dict(locator)
    if 'task' not in source:
        path=Path(source['file']);source['task']=path.parts[0];source['file']=str(Path(*path.parts[1:]))
    path=Path(source['corpus'])/source['task']/source['file']
    if active() and legacy_path(path):raise ValueError('unbound old source locator: '+str(path))
    value=_read_locator(source)
    if digest(value)!=expected:raise ValueError('source bytes differ')
    return value


def compatible_base(pair_id,a,b,scope):
    if a==b:return True
    db=connection()
    if db is None:return False
    row=db.execute('SELECT proof_ref FROM base_changes WHERE pair_id=? AND ((old_result=? AND current_result=?) OR (old_result=? AND current_result=?)) AND applied=1',(pair_id,a,b,b,a)).fetchone()
    if not row:return False
    return object_value(db,row[0]).get('compatible',{}).get(scope) is True


def current_corpus(path):
    """Metadata acquisition uses the published current corpus, not old paths."""
    path=Path(path).resolve()
    if path==OLD.resolve() and active():
        return Path(dict(connection().execute('SELECT key,value FROM metadata'))['new'])
    return path
