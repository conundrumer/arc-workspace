"""Paths, identities and durable transport for the G-only library pass."""
import sys
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from study_paths import CODE_ROOT,DATA_ROOT,MAIN_ROOT

HERE=Path(__file__).resolve().parent
OUTPUT=DATA_ROOT/'ast/run/mech4'
MECH=CODE_ROOT/'ast/run/mech'
sys.path[:0]=[str(MECH),str(CODE_ROOT/'judgetool'),str(CODE_ROOT/'judge3'),str(CODE_ROOT/'ast/run')]

import hashlib
import json
import sqlite3
import zlib
from run import canonical,digest,pair_key


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)


def base_record(row):
    pair,source,code,config,result,payload=row
    value=json.loads(payload)
    if (value['pair_id']!=pair or value['source_sha256']!=source or digest(value)!=result
            or digest(value['code_manifest'])!=code or value['code_sha256']!=code
            or digest(value['config'])!=config or value['config_sha256']!=config):
        raise ValueError('base source/code/config/result integrity differs: '+pair)
    return value


def queue_hint(record):
    """Owner-approved shortlist only; NOT final grade, admission or coverage."""
    if record.get('error') or record.get('fits') is True:return False
    items=record.get('per_assignment',[])
    witnessed=any(i.get('witness',{}).get('recoverable') is True
                  and i.get('witness',{}).get('verified') is True for i in items)
    bounded=any(i.get('witness',{}).get('reason_code')=='search_bound' for i in items)
    return (record.get('label')=='overapproximation' and not witnessed) or bounded


def source_locator(base):
    src=base['source']
    return dict(schema='mech-source-v1',corpus=str(Path(src['corpus']).resolve()),
        file=base['task']+'/'+src['file'],line=src['line'],source_sha256=base['source_sha256'],
        mechanical_pair_id=base['pair_id'],pool_pair_id=base['pool_pair_id'],stream=src['stream'])


def manifest():
    paths=set(HERE.glob('*.py'))
    paths.update(MECH/n for n in ('registry_plan.py','read_grades.py','run.py','clause_evidence.py','grades.py','outcomes.py'))
    paths.update((CODE_ROOT/'judgetool').glob('*.py'))
    paths.update(CODE_ROOT/n for n in ('study_paths.py','judge3/nonrender_metadata.py','judge3/render_pair.py',
        'judge3/catalog.py','judge2/render2/headers.py','judge2/render2/body.py','judge2/render2/column_paths.py',
        'judge2/render2/structured.py','ast/run/next_revision/family_recovery.py','ast/run/filters.py',
        'ast/run/native_storage.py','ast/run/native_tables.py','ast/run/recovery.py',
        'ast/run/disk_guard.py',
        'ref/progsynth-relabel/engine_verify.py','ref/progsynth-relabel/verify_recovery.py'))
    return {str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


class Guard:
    def __init__(self,files,disk=None):
        self.files=files;self.disk=disk;self.stats={p:self.signature(Path(p)) for p in files}
    @staticmethod
    def signature(path):
        s=path.stat();return s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns
    def check(self):
        if self.disk is not None:self.disk.check()
        for name,expected in self.files.items():
            path=Path(name);sig=self.signature(path)
            if sig==self.stats[name]:continue
            if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                raise RuntimeError('source changed during lib pass; restart: '+name)
            self.stats[name]=sig


class Journal:
    def __init__(self,path,code=None,config=None):
        self.path=Path(path).resolve();self.path.parent.mkdir(parents=True,exist_ok=True)
        self.code=code;self.config=config
        self.db=sqlite3.connect(self.path);self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS records(kind TEXT,key TEXT,inputs_sha256 TEXT,code_sha256 TEXT,
            config_sha256 TEXT,result_sha256 TEXT,payload BLOB,PRIMARY KEY(kind,key));
          CREATE TABLE IF NOT EXISTS objects(sha256 TEXT PRIMARY KEY,kind TEXT,payload BLOB);
          CREATE TABLE IF NOT EXISTS producers(code TEXT,config TEXT,manifest_ref TEXT,settings_ref TEXT,PRIMARY KEY(code,config));
          CREATE TABLE IF NOT EXISTS operations(id INTEGER PRIMARY KEY,pair_id TEXT,scope TEXT,
            phase TEXT,identity TEXT,charge REAL,status TEXT,payload TEXT);
          CREATE INDEX IF NOT EXISTS operations_pair_scope ON operations(pair_id,scope,id);
        ''')
        self.db.commit()
    def register(self,manifest,settings):
        if digest(manifest)!=self.code or digest(settings)!=self.config:raise ValueError('producer digest differs')
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO producers VALUES (?,?,?,?)',
                (self.code,self.config,intern(self.db,manifest),intern(self.db,settings)))
    def get(self,kind,key,inputs):
        row=self.db.execute('SELECT inputs_sha256,code_sha256,config_sha256,result_sha256,payload FROM records '
                            'WHERE kind=? AND key=?',(kind,key)).fetchone()
        if not row or row[0]!=digest(inputs):return None
        result=decode_payload(self.db,row[4])
        if digest(result)!=row[3]:raise ValueError('journal result digest differs: '+kind+'/'+key)
        return result
    def put(self,kind,key,inputs,result):
        if kind not in ('gold_case','candidate','pair'):raise ValueError('not an owned durable fact kind')
        with self.db:
            payload=zlib.compress(canonical({'mech4_object':intern(self.db,result)}).encode(),3)
            self.db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?,?,?,?,?)',
                (kind,key,digest(inputs),self.code,self.config,digest(result),payload))
        return result
    def ref(self,kind,key,result):
        sha=digest(result)
        row=self.db.execute('SELECT code_sha256,config_sha256,result_sha256 FROM records WHERE kind=? AND key=?',
                            (kind,key)).fetchone()
        if not row or row[2]!=sha:raise ValueError('reference result differs from stored fact')
        return dict(database=str(self.path),table='records',kind=kind,key=key,result_sha256=sha,
                    code_sha256=row[0],config_sha256=row[1])
    def close(self):self.db.close()


# Structured values are content-addressed once; repeated receipts are references.
def intern(db,value,known=None):
    known=set() if known is None else known
    sha=digest(value)
    if sha in known:return sha
    if db.execute('SELECT 1 FROM objects WHERE sha256=?',(sha,)).fetchone():
        known.add(sha);return sha
    if isinstance(value,dict):kind='dict';payload={k:intern(db,v,known) for k,v in value.items()}
    elif isinstance(value,list):kind='list';payload=[intern(db,v,known) for v in value]
    else:kind='scalar';payload=value
    db.execute('INSERT OR IGNORE INTO objects VALUES (?,?,?)',
        (sha,kind,zlib.compress(canonical(payload).encode(),3)))
    known.add(sha)
    return sha


def resolve(db,sha,cache=None):
    cache={} if cache is None else cache
    if sha in cache:return cache[sha]
    row=db.execute('SELECT kind,payload FROM objects WHERE sha256=?',(sha,)).fetchone()
    if not row:raise ValueError('missing content object: '+sha)
    raw=json.loads(zlib.decompress(row[1]))
    if row[0]=='dict':value={k:resolve(db,v,cache) for k,v in raw.items()}
    elif row[0]=='list':value=[resolve(db,v,cache) for v in raw]
    elif row[0]=='scalar':value=raw
    else:raise ValueError('unknown content object kind')
    if digest(value)!=sha:raise ValueError('content object digest differs')
    cache[sha]=value
    return value


def decode_payload(db,payload):
    value=json.loads(zlib.decompress(payload))
    return resolve(db,value['mech4_object']) if set(value)=={'mech4_object'} else value


class ScreenCache:
    """Screen comparisons and failed-batch caches are recomputed in memory."""
    def __init__(self):self.cache={};self.comparison_hits=0
    def recall(self,kind,key,inputs):return self.cache.get((kind,key,digest(inputs)))
    def remember(self,kind,key,inputs,result):
        self.cache[kind,key,digest(inputs)]=result
        return result
