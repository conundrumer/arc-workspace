"""Normalized pass facts; grades and joined evidence exist only when read."""
import json
from pathlib import Path
import sqlite3

if __package__:
    from .common import canonical,digest,ONE_SHOT
else:
    from common import canonical,digest,ONE_SHOT


def initialize(db,manifest,config):
    db.execute('CREATE TABLE IF NOT EXISTS producers(code TEXT,config TEXT,manifest TEXT,settings TEXT,PRIMARY KEY(code,config))')
    db.execute('CREATE TABLE IF NOT EXISTS objects(id TEXT PRIMARY KEY,payload TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS test_facts(pair_id TEXT,cache_key TEXT,source TEXT,producer TEXT,task TEXT,result_sha256 TEXT,payload TEXT,PRIMARY KEY(pair_id,cache_key))')
    db.execute('INSERT OR IGNORE INTO producers VALUES (?,?,?,?)',
               (digest(manifest),digest(config),canonical(manifest),canonical(config)))
    db.commit()


def put_object(db,value):
    key=digest(value)
    db.execute('INSERT OR IGNORE INTO objects VALUES (?,?)',(key,canonical(value)))
    return key


def get_object(db,key):
    row=db.execute('SELECT payload FROM objects WHERE id=?',(key,)).fetchone()
    if row is None:raise ValueError('fact reference absent: '+key)
    value=json.loads(row[0])
    if digest(value)!=key:raise ValueError('fact reference digest differs')
    return value


def reader_hash(pair,source,base,code,config,fact):
    return digest([pair,source,base,code,config,fact])


def save_reader(store,value):
    reader=value['reader_difference'];different=reader.get('read_difference')
    fact=dict(schema='mech3-reader-fact-v2',read_difference=different)
    if different is None:
        fact['problem']={k:reader[k] for k in ('reason','error_type','stage','origin') if k in reader}
        if reader.get('gaps'):fact['problem']['gaps']=reader['gaps']
    elif different:
        fact['witness_readers']=[d['reader_path'] for d in reader.get('differences',[])]
    pair=value['pair_id'];source=value['source_sha256'];base=value['base_result_sha256']
    with store.db:
        if value.get('task_receipt'):fact['task']=put_object(store.db,value['task_receipt'])
        sha=reader_hash(pair,source,base,store.code,store.config_hash,fact)
        store.db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?,?,?,?,?)',
                         (pair,source,base,store.code,store.config_hash,sha,canonical(fact)))
    return value


def save_test(store,pair,key,value):
    receipt=value.get('receipt',{});source=value.get('source_sha256')
    fitted=value.get('fits_test') if value.get('complete') is True else None
    fact=dict(schema='mech3-test-fact-v2',fits_test=fitted)
    if fact['fits_test'] is None:fact['problem']=value.get('reason') or 'TEST evidence unavailable'
    files={}
    for entry in value.get('evidence_files',[]):
        files.setdefault(str(Path(entry['path']).parent),[]).append(entry)
    with store.db:
        producer=put_object(store.db,dict(schema='mech3-test-producer-v1',settings=receipt.get('settings',{}),
            code=receipt.get('code',{})))
        task=put_object(store.db,receipt.get('task',{}))
        fact['observations']=[put_object(store.db,dict(schema='mech3-replay-reference-v1',artifact=folder,
            files=sorted(entries,key=lambda e:e['path']))) for folder,entries in sorted(files.items())]
        sha=digest([pair,key,source,producer,task,fact])
        store.db.execute('INSERT OR REPLACE INTO test_facts VALUES (?,?,?,?,?,?,?)',
                         (pair,key,source,producer,task,sha,canonical(fact)))
    return value


def test_row(db,row,*,validate_files=True):
    from mech.read_grades import file_hash
    pair,key,source,producer_id,task_id,sha,text=row;fact=json.loads(text)
    if digest([pair,key,source,producer_id,task_id,fact])!=sha:raise ValueError('TEST fact digest differs')
    producer=get_object(db,producer_id);task=get_object(db,task_id);files=[]
    for ref in fact.get('observations',[]):files.extend(get_object(db,ref)['files'])
    if validate_files:
        for f in files:
            if file_hash(f['path'])!=f['sha256']:raise ValueError('TEST observation changed: '+f['path'])
    reference=dict(table='test_facts',pair_id=pair,cache_key=key,result_sha256=sha)
    # Compatibility view for the existing shared check caller; none of these
    # reconstructed aliases/counters is stored as a second fact.
    return dict(schema='judgetool-out-fit-v1',source_sha256=source,fits_test=fact['fits_test'],
        complete=type(fact['fits_test']) is bool,reason=fact.get('problem'),evidence_files=files,
        evaluations={},receipt=dict(source_sha256=source,settings=producer['settings'],code=producer['code'],
            code_sha256=digest(producer['code']),task=task),fact_reference=reference)


def load_test(db,pair,key=None):
    sql='SELECT pair_id,cache_key,source,producer,task,result_sha256,payload FROM test_facts WHERE pair_id=?'
    params=[pair]
    if key is not None:sql+=' AND cache_key=?';params.append(key)
    sql+=' ORDER BY rowid DESC'
    row=db.execute(sql,params).fetchone()
    return None if row is None else test_row(db,row)


def tables(db):
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def raw_legacy(value):
    reader=value.get('reader_difference',{})
    out=dict(schema='mech3-step4-facts-view-v2',pair_id=value['pair_id'],source_sha256=value['source_sha256'],
        base_result_sha256=value['base_result_sha256'],read_difference=reader.get('read_difference'),
        fits_test=value.get('program',{}).get('fits_test'))
    if out['read_difference'] is None:out['reader_problem']={k:reader[k] for k in ('reason','error_type','stage','gaps') if k in reader}
    if out['fits_test'] is None:
        out['test_problem']=value.get('program',{}).get('test_check',{}).get('reason')
    return out


def load_normalized(db,row,database,task_sha256=None):
    pair,source,base,code,config,sha,text=row;fact=json.loads(text)
    if reader_hash(pair,source,base,code,config,fact)!=sha:raise ValueError('reader fact digest differs')
    producer=db.execute('SELECT manifest,settings FROM producers WHERE code=? AND config=?',(code,config)).fetchone()
    if producer is None:raise ValueError('reader producer absent')
    manifest,settings=map(json.loads,producer)
    if digest(manifest)!=code or digest(settings)!=config:raise ValueError('reader producer digest differs')
    if task_sha256 is not None and get_object(db,fact['task'])['sha256']!=task_sha256:
        raise ValueError('reader task inputs changed')
    out=dict(schema='mech3-step4-facts-view-v2',pair_id=pair,source_sha256=source,base_result_sha256=base,
             read_difference=fact['read_difference'],fits_test=None)
    if 'problem' in fact:out['reader_problem']=fact['problem']
    if 'witness_readers' in fact:out['witness_readers']=fact['witness_readers']
    tested=load_test(db,pair) if 'test_facts' in tables(db) else None
    test_ref=None
    if (tested is not None and tested['source_sha256']==source
            and (task_sha256 is None or tested['receipt']['task'].get('sha256')==task_sha256)):
        out['fits_test']=tested['fits_test'];test_ref=dict(tested['fact_reference'],database=str(database))
        if tested.get('reason'):out['test_problem']=tested['reason']
    elif 'program_checks' in tables(db):
        for legacy_sha,legacy_text in db.execute('SELECT result_sha256,record_json FROM program_checks WHERE pair_id=? ORDER BY rowid DESC',(pair,)):
            tested=json.loads(legacy_text)
            if digest(tested)!=legacy_sha:raise ValueError('legacy TEST fact digest differs')
            if (tested.get('source_sha256')==source and (task_sha256 is None
                    or tested.get('receipt',{}).get('task',{}).get('sha256')==task_sha256)):
                from mech.read_grades import file_hash
                for f in tested.get('evidence_files',[]):
                    if file_hash(f['path'])!=f['sha256']:raise ValueError('legacy TEST observation changed')
                out['fits_test']=tested.get('fits_test')
                test_ref=dict(database=str(database),table='program_checks',pair_id=pair,result_sha256=legacy_sha)
                break
    return dict(status='done',valid=True,record=out,result_sha256=sha,
        facts=[pair,source,base,code,config,fact],
        reference=dict(database=str(database),table='records',pair_id=pair,result_sha256=sha,
                       code_sha256=code,config_sha256=config),test_reference=test_ref)


def load_step4(database,pair_id,*,source_sha256,base_result_sha256,legacy_loader,task_sha256=None,reads=ONE_SHOT):
    db=None
    try:
        path=Path(database).resolve();db=reads.open(path);db.execute('BEGIN')
        row=db.execute('SELECT pair_id,source_sha256,base_result_sha256,code_sha256,config_sha256,result_sha256,record_json FROM records WHERE pair_id=?',(pair_id,)).fetchone()
        if row is None:return dict(status='open',valid=False,reason='no reader fact')
        if row[1:3]!=(source_sha256,base_result_sha256):raise ValueError('reader source/base changed')
        if json.loads(row[6]).get('schema')=='mech3-reader-fact-v2':return load_normalized(db,row,path,task_sha256)
        old=legacy_loader(database,pair_id,source_sha256=source_sha256,base_result_sha256=base_result_sha256,task_sha256=task_sha256,reads=reads)
        if old.get('valid') is True:
            prior=old['record'];old=dict(old,facts=prior,record=raw_legacy(prior))
            if prior.get('program',{}).get('test_check') or type(prior.get('program',{}).get('fits_test')) is bool:
                old['test_reference']=dict(old['reference'],field='program.test_check')
        return old
    except Exception as error:return dict(status='open',valid=False,reason=str(error))
    finally:
        if db is not None:reads.done(db)
