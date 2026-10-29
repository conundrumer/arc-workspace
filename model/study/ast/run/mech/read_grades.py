"""Canonical read-only settled grade validity for study consumers.

A valid Unknown is a finished reduction with named evidence owed. Open means
missing or stale grade/evidence; never turn open into a negative class. Default
source validity is against the CURRENT base receipt; source_record optionally
checks newly acquired canonical corpus content too. No native execution.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
from functools import lru_cache
from run import digest

HERE=Path(__file__).resolve().parent
STUDY=HERE.parents[2]


@lru_cache(maxsize=256)
def _hash(path,signature):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def file_hash(path):
    path=Path(path).resolve();s=path.stat()
    return _hash(str(path),(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns))


def load_grade(database,pair_id,*,source_record=None):
    """Return status done/open, valid, record?, reason; opens all DBs read-only."""
    db=None;base=None
    try:
        db=sqlite3.connect(Path(database).resolve().as_uri()+'?mode=ro',uri=True);db.execute('BEGIN')
        row=db.execute('SELECT evidence_sha256,code_sha256,config_sha256,result_sha256,record_json FROM grades WHERE pair_id=?',(pair_id,)).fetchone()
        if not row:return dict(status='open',valid=False,reason='no grade row')
        grade=json.loads(row[4]);cfg=grade['config'];codes=grade['code_manifest']
        if digest(grade)!=row[3] or digest(codes)!=row[1] or digest(cfg)!=row[2]:raise ValueError('grade/config/code receipt digest differs')
        for name,expected in codes.items():
            path=Path(name) if Path(name).is_absolute() else HERE/name
            if file_hash(path)!=expected:raise ValueError('grading code changed: '+str(path))
        if cfg.get('spec_sha256')!=file_hash(STUDY/'codex-adm/briefs/judge-decisions.md'):raise ValueError('specification changed')
        proof=db.execute('SELECT result_sha256,payload FROM evidence WHERE pair_id=?',(pair_id,)).fetchone()
        if not proof or digest(json.loads(proof[1]))!=proof[0] or proof[0]!=row[0]:raise ValueError('grade evidence missing/changed')
        evidence=json.loads(proof[1]);ref=evidence['base_result_ref']
        base=sqlite3.connect(Path(ref['database']).resolve().as_uri()+'?mode=ro',uri=True);base.execute('BEGIN')
        prior=base.execute('SELECT source_sha256,code_sha256,config_sha256,result_sha256,record_json FROM pairs WHERE pair_id=?',(pair_id,)).fetchone()
        if (not prior or prior[0]!=grade['source_sha256'] or prior[1]!=ref['code_sha256']
                or prior[2]!=ref['config_sha256'] or prior[3]!=ref['result_sha256']
                or digest(json.loads(prior[4]))!=prior[3]):raise ValueError('base source/code/config/result changed')
        if source_record is not None and digest(source_record)!=grade['source_sha256']:raise ValueError('fresh corpus source changed')
        return dict(status='done',valid=True,record=grade,grade=grade['grade'],
                    source_check='fresh-source' if source_record is not None else 'current-base-receipt',
                    result_sha256=row[3],evidence_sha256=row[0])
    except Exception as error:return dict(status='open',valid=False,reason=str(error),error_type=type(error).__name__)
    finally:
        if base is not None:base.close()
        if db is not None:db.close()
