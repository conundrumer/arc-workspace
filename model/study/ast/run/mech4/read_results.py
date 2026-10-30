"""Read-only lib facts and read-time normalization, including legacy journals."""
from .common import readonly,digest,decode_payload,resolve,pair_key,ONE_SHOT
from pathlib import Path
from judge3.framed_jsonl import JsonlReader
import json
import hashlib
from functools import lru_cache


def _source(locator,expected):
    path=Path(locator['corpus'])/locator['file']
    try:
        with JsonlReader(path) as reader:
            value=json.loads(reader.read_line(locator['line']))
    except IndexError as error:
        raise ValueError('source locator line absent') from error
    if digest(value)!=expected:raise ValueError('source record changed')
    return value


def _producer(db,code,config,legacy=None):
    if legacy and 'code_manifest' in legacy:
        manifest,settings=legacy['code_manifest'],legacy['config']
    else:
        row=db.execute('SELECT manifest_ref,settings_ref FROM producers WHERE code=? AND config=?',(code,config)).fetchone()
        if not row:raise ValueError('producer provenance absent')
        manifest,settings=resolve(db,row[0]),resolve(db,row[1])
    if digest(manifest)!=code or digest(settings)!=config:raise ValueError('producer provenance digest differs')
    # Recorded code is provenance. Reading facts never opens mutable code/prose.
    return manifest,settings


def _reference_row(db,path,ref):
    if Path(ref['database']).resolve()!=path or ref['table']!='records':raise ValueError('outside journal reference')
    row=db.execute('SELECT code_sha256,config_sha256,result_sha256,payload FROM records WHERE kind=? AND key=?',
                   (ref['kind'],ref['key'])).fetchone()
    if not row or tuple(row[:3])!=(ref['code_sha256'],ref['config_sha256'],ref['result_sha256']):
        raise ValueError('referenced result identity differs')
    return row


def _referenced(db,path,ref):
    row=_reference_row(db,path,ref)
    value=decode_payload(db,row[3])
    if digest(value)!=row[2]:raise ValueError('referenced result digest differs')
    return value


@lru_cache(maxsize=512)
def _observation_content_valid(path,identity,reference,payload_sha256):
    db=readonly(path)
    try:_referenced(db,Path(path),json.loads(reference))
    finally:db.close()
    return True


def _observation_valid(db,path,reference):
    # Check the actual reference row on every hit. Content-addressed objects
    # are INSERT OR IGNORE and completed observation references are immutable
    # under the supported writer. Unrelated append commits need not decode
    # the entire GOLD DAG again. This is a validated snapshot cache, not a
    # continuing attestation against unsupported in-place object mutation.
    row=_reference_row(db,path,reference)
    stat=path.stat()
    return _observation_content_valid(str(path),(stat.st_dev,stat.st_ino),
        json.dumps(reference,sort_keys=True,separators=(',',':')),
        hashlib.sha256(row[3]).hexdigest())


def load_result(database,pair_id,*,source_sha256,base_result_sha256,source_record=None,reads=ONE_SHOT):
    """Join owned facts and derive checked clauses; never persist grades.

    Original producer/configuration/evidence hashes are retained across storage
    changes. Legacy inline JSON and v2 content objects share this decoder. A
    valid bounded/unavailable attempt is a completed fact, never a negative.
    """
    db=None
    try:
        path=Path(database).resolve();db=reads.open(path);db.execute('BEGIN')
        key=digest(dict(pair=pair_id,target='G'))
        row=db.execute('SELECT code_sha256,config_sha256,result_sha256,payload FROM records WHERE kind=? AND key=?',
                       ('pair',key)).fetchone()
        if not row:return dict(status='open',valid=False,reason='no G-lib result')
        facts=decode_payload(db,row[3])
        if facts.get('schema') not in ('mech4-lib-result-v1','mech4-lib-facts-v2'):
            raise ValueError('unsupported lib fact schema')
        if facts.get('search_status')=='not_eligible_current':
            raise ValueError('legacy routing snapshot is not a completed search')
        if (digest(facts)!=row[2] or facts['pair_id']!=pair_id or facts['source_sha256']!=source_sha256):
            raise ValueError('pair/source/base/result identity differs')
        manifest,settings=_producer(db,row[0],row[1],facts)
        state=facts.get('stop',{}).get('state')
        if facts.get('interrupted') or state=='interrupted':raise ValueError('interrupted attempt')
        if facts.get('gold_ref'):_observation_valid(db,path,facts['gold_ref'])
        candidates=facts.get('candidates',[])
        if not candidates:
            # Older journals attached references only to normalized clauses.
            candidates=[c['receipt_ref'] for c in facts.get('mechanical_clauses',[])]
        clauses=[]
        task_ref=facts.get('task_receipt') or facts.get('inputs',{}).get('task_receipt')
        task=None
        if task_ref:
            task_bytes=Path(task_ref['path']).read_bytes();task=json.loads(task_bytes)
            if task_ref.get('inputs_sha256'):
                if digest(task)!=task_ref['inputs_sha256']:raise ValueError('task inputs changed')
            else:
                if hashlib.sha256(task_bytes).hexdigest()!=task_ref['sha256']:raise ValueError('task inputs changed')
        if candidates:
            record=source_record if source_record is not None else _source(facts['source'],source_sha256)
            if digest(record)!=source_sha256 or digest(pair_key(record))!=pair_id:raise ValueError('source binding differs')
            if task is None:raise ValueError('task input reference absent')
            from clause_evidence import clause_evidence
            for ref in candidates:
                if ref['kind']!='candidate':raise ValueError('unexpected candidate record kind')
                raw=_referenced(db,path,ref)
                if raw.get('source_sha256')!=source_sha256 or raw.get('target_id')!='G':
                    raise ValueError('candidate source/target differs')
                clauses.append(clause_evidence(raw,record,ref,ntrain=len(task['train']),ntest=len(task['test'])))
        found=any(c['outcome']=='recovery verified' for c in clauses)
        unavailable=state=='unavailable' or facts.get('search_status')=='unavailable'
        status='recovery_verified' if found else 'unavailable' if unavailable else 'bound_unknown'
        joined=dict(facts,code_manifest=manifest,code_sha256=row[0],config=settings,config_sha256=row[1],
            mechanical_clauses=clauses,found_recovery=found,search_status=status,full_space_covered=False)
        return dict(status='done',valid=True,record=joined,result_sha256=row[2],
            base_reference_matches=facts['base_result_ref']['result_sha256']==base_result_sha256,
            reference=dict(database=str(path),table='records',kind='pair',key=key,
                result_sha256=row[2],code_sha256=row[0],config_sha256=row[1]),
            mechanical_clauses=clauses,found_recovery=found,search_status=status,admission_authenticated=False)
    except Exception as error:return dict(status='open',valid=False,reason=str(error),error_type=type(error).__name__)
    finally:
        if db is not None:reads.done(db)
