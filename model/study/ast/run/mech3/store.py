"""Durable reader and TEST facts with input-keyed resume."""
import json
import gzip
from pathlib import Path
import sqlite3
if __package__:
    from .common import canonical,digest,ONE_SHOT
    from . import raw_store
else:
    from common import canonical,digest,ONE_SHOT
    import raw_store


def evidence_current(value):
    from mech.read_grades import file_hash
    for artifact in value.get('program',{}).get('test_check',{}).get('evidence_files',[]):
        if file_hash(artifact['path'])!=artifact['sha256']:
            return False
    return True


class GoldCache:
    """Memory cache with read-only access to historical durable transports."""
    def __init__(self,store):self.store=store;self.memory={}
    def clear(self):self.memory.clear()
    def get(self,key):
        if key in self.memory:return self.memory[key]
        row=self.store.db.execute('SELECT result_sha256,payload FROM gold_out_cache WHERE cache_key=?',(key,)).fetchone()
        if row is None:return None
        value=json.loads(gzip.decompress(row[1]))
        if digest(value)!=row[0]:raise ValueError('gold OUT cache payload differs')
        try:
            if not evidence_current(dict(program=dict(test_check=value.get('receipt',{})))):return None
        except OSError:return None
        self.memory[key]=value
        return value
    def __setitem__(self,key,value):
        # New gold observations already live in canonical replay artifacts.
        # Keep legacy durable transports readable, without writing new copies.
        self.memory[key]=value


class Store:
    def __init__(self,path,manifest,config):
        self.path=Path(path).resolve();self.path.parent.mkdir(parents=True,exist_ok=True)
        self.manifest=manifest;self.code=digest(manifest);self.config=config;self.config_hash=digest(config)
        self.db=sqlite3.connect(self.path,timeout=60)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS records(pair_id TEXT PRIMARY KEY,source_sha256 TEXT,'
            'base_result_sha256 TEXT,code_sha256 TEXT,config_sha256 TEXT,result_sha256 TEXT,record_json TEXT)')
        self.db.execute('CREATE TABLE IF NOT EXISTS program_checks(pair_id TEXT,cache_key TEXT,'
            'result_sha256 TEXT,record_json TEXT,PRIMARY KEY(pair_id,cache_key))')
        self.db.execute('CREATE TABLE IF NOT EXISTS gold_out_cache(cache_key TEXT PRIMARY KEY,result_sha256 TEXT,payload BLOB)')
        self.db.commit()
        raw_store.initialize(self.db,manifest,config)

    def load(self,pair,source,base,task_sha256=None):
        current=load_step4(self.path,pair,source_sha256=source,base_result_sha256=base,task_sha256=task_sha256)
        if current.get('valid') is True:
            return current['record']
        return None

    def save(self,value):
        return raw_store.save_reader(self,value)

    def load_program(self,pair,key):
        try:normalized=raw_store.load_test(self.db,pair,key)
        except (OSError,ValueError):normalized=None
        if normalized is not None:return normalized
        row=self.db.execute('SELECT result_sha256,record_json FROM program_checks WHERE pair_id=? AND cache_key=?',
                            (pair,key)).fetchone()
        if row is None:return None
        value=json.loads(row[1])
        if digest(value)!=row[0]:raise ValueError('TEST replay cache payload differs')
        try:
            if not evidence_current(dict(program=dict(test_check=value))):return None
        except OSError:return None
        return value

    def save_program(self,pair,key,value):
        return raw_store.save_test(self,pair,key,value)

    def compatible_program(self,pair,source,settings,task_receipt):
        """Reuse a TEST proof stored under another cache key, matched by source and task input."""
        try:normalized=raw_store.load_test(self.db,pair)
        except (OSError,ValueError):normalized=None
        if (normalized is not None and normalized['source_sha256']==source
                and normalized['receipt']['task'].get('sha256')==task_receipt['sha256']):return normalized
        for sha,text in self.db.execute('SELECT result_sha256,record_json FROM program_checks WHERE pair_id=? ORDER BY rowid DESC',(pair,)):
            value=json.loads(text);receipt=value.get('receipt',{})
            if digest(value)!=sha:raise ValueError('TEST replay cache payload differs')
            if (value.get('source_sha256')!=source or receipt.get('source_sha256')!=source
                    or receipt.get('task',{}).get('sha256')!=task_receipt['sha256']):continue
            try:
                if not evidence_current(dict(program=dict(test_check=value))):continue
            except OSError:continue
            return value
        return None

    def close(self):self.db.close()


def _load_legacy_step4(database,pair_id,*,source_sha256,base_result_sha256,task_sha256=None,reads=ONE_SHOT):
    """Read-only consumer: done valid Unknown is distinct from open/stale."""
    from mech.read_grades import file_hash
    db=None
    try:
        db=reads.open(database)
        row=db.execute('SELECT result_sha256,record_json FROM records WHERE pair_id=?',(pair_id,)).fetchone()
        if not row:return dict(status='open',valid=False,reason='no step 4 record')
        value=json.loads(row[1])
        if digest(value)!=row[0] or value['pair_id']!=pair_id:raise ValueError('step 4 digest/identity differs')
        if (value['source_sha256'],value['base_result_sha256'])!=(source_sha256,base_result_sha256):
            raise ValueError('current base/source receipt differs')
        if digest(value['code_manifest'])!=value['code_sha256'] or digest(value['config'])!=value['config_sha256']:
            raise ValueError('step 4 code/config digest differs')
        task=value.get('task_receipt')
        if task_sha256 is not None and (not task or task['sha256']!=task_sha256):raise ValueError('task inputs changed')
        for artifact in value.get('program',{}).get('test_check',{}).get('evidence_files',[]):
            if file_hash(artifact['path'])!=artifact['sha256']:
                raise ValueError('step 4 TEST replay evidence changed: '+artifact['path'])
        return dict(status='done',valid=True,record=value,result_sha256=row[0],
            reference=dict(database=str(Path(database).resolve()),table='records',pair_id=pair_id,result_sha256=row[0]))
    except Exception as error:return dict(status='open',valid=False,reason=str(error))
    finally:
        if db is not None:reads.done(db)


def load_step4(database,pair_id,*,source_sha256,base_result_sha256,task_sha256=None,reads=ONE_SHOT):
    return raw_store.load_step4(database,pair_id,source_sha256=source_sha256,
        base_result_sha256=base_result_sha256,task_sha256=task_sha256,legacy_loader=_load_legacy_step4,reads=reads)
