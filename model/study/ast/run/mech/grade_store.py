"""One durable per-pair grade writer for reducer and checked-judge ingestion."""
import json
from pathlib import Path
import sqlite3
from admission import admission
from clause_evidence import digest
from grades import reduce_grade,judge_eligible
from outcomes import canonical


class GradeStore:
    def __init__(self,path,code_manifest,config):
        self.path=Path(path).resolve();self.path.parent.mkdir(parents=True,exist_ok=True)
        self.code_manifest=code_manifest;self.code=digest(code_manifest)
        self.config=config;self.config_hash=digest(config)
        self.db=sqlite3.connect(self.path);self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('CREATE TABLE IF NOT EXISTS grades(pair_id TEXT PRIMARY KEY,evidence_sha256 TEXT NOT NULL,'
                        'code_sha256 TEXT NOT NULL,config_sha256 TEXT NOT NULL,result_sha256 TEXT NOT NULL,record_json TEXT NOT NULL)')

    def save(self,evidence,*,inputs_authenticated=False):
        pair_id=evidence['pair_id'];source=evidence['source_sha256'];input_hash=digest(evidence)
        for value in (pair_id,source):
            if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
                raise ValueError('expected canonical sha256 pair/source identities')
        row=self.db.execute('SELECT evidence_sha256,code_sha256,config_sha256,result_sha256,record_json FROM grades WHERE pair_id=?',(pair_id,)).fetchone()
        if (row and tuple(row[:3])==(input_hash,self.code,self.config_hash)
                and digest(json.loads(row[4]))==row[3]
                and json.loads(row[4]).get('admission',{}).get('receipt_authenticated') is inputs_authenticated):
            return json.loads(row[4]),True
        result=dict(schema='mech-grade-record-v1',pair_id=pair_id,source_sha256=source,
                    evidence_sha256=input_hash,code_sha256=self.code,code_manifest=self.code_manifest,
                    config_sha256=self.config_hash,config=self.config,**reduce_grade(evidence))
        result['judge_eligible']=judge_eligible(evidence)
        result['source']=evidence.get('source')
        result['status']='unknown' if result['grade']=='Unknown' else 'graded'
        result['step']=evidence.get('step')
        result['base_result_ref']=evidence.get('base_result_ref')
        result['admission']=admission(evidence,dict(database=str(self.path),table='grades',pair_id=pair_id),
                                      inputs_authenticated=inputs_authenticated)
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO grades VALUES (?,?,?,?,?,?)',
                            (pair_id,input_hash,self.code,self.config_hash,digest(result),canonical(result)))
        return result,False

    def close(self):
        self.db.close()
