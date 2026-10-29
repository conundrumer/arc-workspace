"""Durable JSON journals for Step 3; no evaluation or table policy."""
import json
from pathlib import Path
import sqlite3
import zlib
from run import canonical,digest


class Journal:
    def __init__(self,path,code,config):
        self.path=Path(path).resolve();self.path.parent.mkdir(parents=True,exist_ok=True)
        self.code=code;self.config=config
        self.db=sqlite3.connect(self.path)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS entries('
            'kind TEXT,key TEXT,inputs TEXT,code TEXT,config TEXT,result_sha256 TEXT,payload BLOB,'
            'PRIMARY KEY(kind,key))')
        self.db.execute('CREATE TABLE IF NOT EXISTS producers(code TEXT,config TEXT,manifest TEXT,settings TEXT,PRIMARY KEY(code,config))')
        self.db.commit()

    def register(self,manifest,settings):
        if digest(manifest)!=self.code or digest(settings)!=self.config:
            raise ValueError('producer manifest/config digest differs')
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO producers VALUES (?,?,?,?)',
                (self.code,self.config,canonical(manifest),canonical(settings)))

    def load(self,kind,key,inputs):
        row=self.db.execute('SELECT inputs,code,config,result_sha256,payload FROM entries WHERE kind=? AND key=?',
                            (kind,key)).fetchone()
        if not row or tuple(row[:3])!=(digest(inputs),self.code,self.config):return None
        value=json.loads(zlib.decompress(row[4]))
        if digest(value)!=row[3]:raise ValueError('step 3 journal payload digest differs: '+kind+'/'+key)
        return value

    def save(self,kind,key,inputs,value):
        payload=zlib.compress(canonical(value).encode(),3)
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO entries VALUES (?,?,?,?,?,?,?)',
                (kind,key,digest(inputs),self.code,self.config,digest(value),payload))
        return value

    def reference(self,kind,key,value):
        return dict(database=str(self.path),table='entries',kind=kind,key=key,result_sha256=digest(value),
                    code_sha256=self.code,config_sha256=self.config)

    def close(self):self.db.close()
