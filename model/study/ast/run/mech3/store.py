"""One durable per-pair Step 4 record, exact dependency/config/base receipts."""
import json
from pathlib import Path
import sqlite3
from common import canonical,digest


class Store:
    def __init__(self,path,manifest,config):
        self.path=Path(path).resolve();self.path.parent.mkdir(parents=True,exist_ok=True)
        self.manifest=manifest;self.code=digest(manifest);self.config=config;self.config_hash=digest(config)
        self.db=sqlite3.connect(self.path)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS records(pair_id TEXT PRIMARY KEY,source_sha256 TEXT,'
            'base_result_sha256 TEXT,code_sha256 TEXT,config_sha256 TEXT,result_sha256 TEXT,record_json TEXT)')
        self.db.commit()

    def load(self,pair,source,base):
        row=self.db.execute('SELECT source_sha256,base_result_sha256,code_sha256,config_sha256,'
                            'result_sha256,record_json FROM records WHERE pair_id=?',(pair,)).fetchone()
        if not row or tuple(row[:4])!=(source,base,self.code,self.config_hash):return None
        value=json.loads(row[5])
        if digest(value)!=row[4]:raise ValueError('step 4 record payload digest differs')
        return value

    def save(self,value):
        value=dict(value,code_sha256=self.code,code_manifest=self.manifest,
                   config_sha256=self.config_hash,config=self.config)
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?,?,?,?,?)',
                (value['pair_id'],value['source_sha256'],value['base_result_sha256'],self.code,
                 self.config_hash,digest(value),canonical(value)))
        return value

    def close(self):self.db.close()


def load_step4(database,pair_id,*,source_sha256,base_result_sha256):
    """Read-only consumer: done valid Unknown is distinct from open/stale."""
    from read_grades import file_hash
    db=None
    try:
        db=sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True)
        row=db.execute('SELECT result_sha256,record_json FROM records WHERE pair_id=?',(pair_id,)).fetchone()
        if not row:return dict(status='open',valid=False,reason='no step 4 record')
        value=json.loads(row[1])
        if digest(value)!=row[0] or value['pair_id']!=pair_id:raise ValueError('step 4 digest/identity differs')
        if (value['source_sha256'],value['base_result_sha256'])!=(source_sha256,base_result_sha256):
            raise ValueError('current base/source receipt differs')
        if digest(value['code_manifest'])!=value['code_sha256'] or digest(value['config'])!=value['config_sha256']:
            raise ValueError('step 4 code/config digest differs')
        for name,sha in value['code_manifest'].items():
            if file_hash(name)!=sha:raise ValueError('step 4 dependency changed: '+name)
        task=value.get('task_receipt')
        if task and file_hash(task['path'])!=task['sha256']:
            raise ValueError('task input/expected-axis receipt changed')
        return dict(status='done',valid=True,record=value,result_sha256=row[0],
            reference=dict(database=str(Path(database).resolve()),table='records',pair_id=pair_id,result_sha256=row[0]))
    except Exception as error:return dict(status='open',valid=False,reason=str(error))
    finally:
        if db is not None:db.close()
