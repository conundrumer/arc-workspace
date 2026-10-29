"""Durable JSON journals for Step 3; no evaluation or table policy."""
import json
from pathlib import Path
import sqlite3
import zlib
import time
from contextlib import contextmanager
from run import canonical,digest
from .fact_codec import compact


class Journal:
    def __init__(self,path,code,config,*,counters=None):
        self.path=Path(path).resolve();self.path.parent.mkdir(parents=True,exist_ok=True)
        self.code=code;self.config=config;self.counters=counters;self._transaction=False;self._producers={}
        self.db=sqlite3.connect(self.path)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS entries('
            'kind TEXT,key TEXT,inputs TEXT,code TEXT,config TEXT,result_sha256 TEXT,payload BLOB,'
            'PRIMARY KEY(kind,key))')
        self.db.execute('CREATE TABLE IF NOT EXISTS producers(code TEXT,config TEXT,manifest TEXT,settings TEXT,PRIMARY KEY(code,config))')
        self.db.commit()

    @contextmanager
    def transaction(self):
        """Group cheap comparison writes; never spans native replay/search."""
        if self._transaction:
            yield
            return
        self._transaction=True
        try:
            self.db.execute('BEGIN IMMEDIATE')
            yield
            started=time.monotonic();self.db.commit()
            if self.counters is not None:
                self.counters['journal_commits']+=1
                self.counters['seconds_journal_commit']+=round(time.monotonic()-started,6)
        except BaseException:
            self.db.rollback()
            raise
        finally:self._transaction=False

    def register(self,manifest,settings):
        if digest(manifest)!=self.code or digest(settings)!=self.config:
            raise ValueError('producer manifest/config digest differs')
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO producers VALUES (?,?,?,?)',
                (self.code,self.config,canonical(manifest),canonical(settings)))

    def load(self,kind,key,inputs):
        row=self.db.execute('SELECT inputs,code,config,result_sha256,payload FROM entries WHERE kind=? AND key=?',
                            (kind,key)).fetchone()
        if not row:return None
        if row[0]!=digest(inputs):
            if kind!='pair':return None
            prior=json.loads(zlib.decompress(row[4]))
            if prior.get('source_sha256')!=inputs['source_sha256']:return None
        # Completed facts retain their producer version; adding DET capability
        # does not invalidate already completed non-DET observations.
        producer=self.db.execute('SELECT manifest,settings FROM producers WHERE code=? AND config=?',row[1:3]).fetchone()
        identity=tuple(row[1:3])
        if producer is None:raise ValueError('journal producer provenance missing')
        if self._producers.get(identity)!=producer:
            if not producer or digest(json.loads(producer[0]))!=row[1] or digest(json.loads(producer[1]))!=row[2]:
                raise ValueError('journal producer provenance differs')
            self._producers[identity]=producer
        value=json.loads(zlib.decompress(row[4]))
        if digest(value)!=row[3]:raise ValueError('step 3 journal payload digest differs: '+kind+'/'+key)
        return value

    def save(self,kind,key,inputs,value):
        started=time.monotonic()
        stored=compact(kind,value)
        if kind=='case' and stored.get('schema')=='mech-case-observations-v2':
            axis=stored.pop('axis')
            key_axis=digest(dict(case=key,axis=axis))
            self.save('axis',key_axis,inputs,dict(schema='mech-case-axis-v1',axis=axis))
            stored['axis_ref']=self.reference('axis',key_axis)
            value=dict(value,_axis_ref=stored['axis_ref'])
        payload=zlib.compress(canonical(stored).encode(),3)
        with self.transaction():
            self.db.execute('INSERT OR REPLACE INTO entries VALUES (?,?,?,?,?,?,?)',
                (kind,key,digest(inputs),self.code,self.config,digest(stored),payload))
        if self.counters is not None:self.counters['seconds_journal_save']+=round(time.monotonic()-started,6)
        return value

    def reference(self,kind,key,value=None):
        row=self.db.execute('SELECT code,config,result_sha256 FROM entries WHERE kind=? AND key=?',(kind,key)).fetchone()
        if not row:raise ValueError('journal reference missing')
        return dict(database=str(self.path),table='entries',kind=kind,key=key,result_sha256=row[2],
                    code_sha256=row[0],config_sha256=row[1])

    def read_reference(self,ref):
        row=self.db.execute('SELECT result_sha256,payload FROM entries WHERE kind=? AND key=?',(ref['kind'],ref['key'])).fetchone()
        if not row or row[0]!=ref['result_sha256']:raise ValueError('journal reference changed')
        value=json.loads(zlib.decompress(row[1]))
        if digest(value)!=row[0]:raise ValueError('journal payload changed')
        return value

    def close(self):self.db.close()
