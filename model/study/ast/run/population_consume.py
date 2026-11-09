#!/usr/bin/env python3
"""Input-resumable population membership, historical reuse, and missing observations.

No draws, stored grades, or all-target pass. Each phase has one exclusive writer.
"""
import argparse
from functools import lru_cache
from collections import Counter
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import uuid

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE/'mech'),str(HERE),str(HERE.parents[1])]
from study_paths import DATA_ROOT
from run import canonical,digest,pair_key,SCHEMA
from judge3.framed_jsonl import JsonlReader,JsonlWriter,iter_json


def intact(row,source):
    """Input-bound completed diagnostics are facts too; retries are explicit."""
    if not row:return False
    try:
        value=json.loads(row[2])
        if digest(value)!=row[1] or value['source_sha256']!=row[0] or value['schema']!=SCHEMA:return False
        from source_bindings import scope_equal
        return scope_equal(value['pair_id'],row[0],source,'base')
    except (ValueError,KeyError,TypeError):return False


def member_inputs(member):
    # Producer/check receipts and object locations are provenance, not inputs.
    value={k:member[k] for k in ('task','case','point','clause','kind','K','operation','task_sha256')}
    value.update(gold_sha256=member['gold']['sha256'],program_sha256=member['program']['sha256'])
    identity=member.get('identity')
    value['construction']={k:identity[k] for k in ('body','clause','edits')} if identity else member['construction']
    return digest(value)


def ro(path):return sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
def connect(path):
    path=Path(path).resolve();path.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path,timeout=120)
    db.executescript('''PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL;
      CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);
      CREATE TABLE IF NOT EXISTS members(pair_id TEXT PRIMARY KEY,input_sha256 TEXT,payload TEXT);
      CREATE TABLE IF NOT EXISTS observations(pair_id TEXT PRIMARY KEY,source_sha256 TEXT,locator TEXT);
      CREATE TABLE IF NOT EXISTS scans(path TEXT PRIMARY KEY,signature TEXT,line INTEGER,complete INTEGER);
      CREATE TABLE IF NOT EXISTS attempts(pair_id TEXT PRIMARY KEY,input_sha256 TEXT,payload TEXT);
    ''')
    return db


def emit(start,done,total,**counts):
    elapsed=time.monotonic()-start;rate=done/max(elapsed,.001)
    print(f'done={done}/{total} elapsed={elapsed:.1f}s rate={rate:.3f}/s ETA={(total-done)/rate if rate else 0:.1f}s '+canonical(counts),flush=True)


@lru_cache(maxsize=4)
def _view(path):
    from substitute_incremental import View
    return View(path)


def object_value(ref):
    if 'population' in ref:
        return _view(ref['population']).object(ref['sha256'])
    value=json.loads(Path(ref['path']).read_text())
    if digest(value)!=ref['sha256']:raise ValueError('sampler object integrity mismatch')
    return value


def candidates(population,stream):
    if population:
        from substitute_incremental import View
        v=View(population)
        try:
            chain={};p=v
            while p:chain[str(p.path)]=p;p=p.parent
            for _,occ in v.rows():
                for path,key in occ['candidate_refs']:
                    ir,pr=chain[path].db.execute('SELECT identity_ref,program_ref FROM candidates WHERE key=?',(key,)).fetchone()
                    identity=v.object(ir)
                    yield dict(task=occ['task'],case=occ['case'],point=identity['body'],clause=identity['clause'],kind='Rule',K=len(identity['edits']),operation='substitute',identity=identity,
                        gold=dict(population=str(v.path),sha256=occ['gold_ref']),program=dict(population=str(v.path),sha256=pr),construction=dict(kind='native_edit_identity',identity=identity))
        finally:v.close()
    if stream:
        stream=Path(stream).resolve()
        with JsonlReader(stream) as reader:
            for line in reader.iter_lines():
                if not line.endswith(b'\n'):raise ValueError('incomplete sampler tail; finish or truncate before importing')
                env=json.loads(line)
                if env['schema']!='study-candidate-v1':raise ValueError('unknown candidate stream')
                def ref(sha):return dict(path=str(stream.parent/'objects'/(sha+'.json')),sha256=sha)
                source=env['source'];gold=ref(source['gold_ref']);program=ref(env['program_ref']);construction=object_value(ref(env['construction_ref']))
                expected=digest({k:source[k] for k in ('task','case','point','clause')}|dict(gold_ref=source['gold_ref'],program_ref=env['program_ref']))
                if expected!=env['candidate_id']:raise ValueError('sampler candidate identity mismatch')
                identity=construction.get('identity')
                yield {k:source[k] for k in ('task','case','point','clause','kind')}|dict(K=len(identity['edits']) if identity else 1,operation='substitute',identity=identity,gold=gold,program=program,construction=construction,sampler=env)


def read_source(locator):
    from source_bindings import locator_record
    return locator_record(locator,locator['source_sha256'])


def observation(db,pair):
    row=db.execute('SELECT source_sha256,locator FROM observations WHERE pair_id=?',(pair,)).fetchone()
    if not row:return None
    loc=json.loads(row[1]);loc['source_sha256']=row[0]
    return loc


@lru_cache(maxsize=2)
def _identity_gold(task,case,gold_ref,tasks):
    """Pure native reconstruction, never task evaluation or mutation drawing."""
    import arclog
    ref=json.loads(gold_ref);source=object_value(ref)
    settings=arclog.DecodeSettings(rule_tests=False)
    ev=arclog.StudyTaskEvaluator(task,tasks,settings,session_bytes=128<<20,compact=True)
    gold=ev.from_stream(source['stream']['ids'],source['stream']['model'])
    if gold.sexp()!=source['text']:raise ValueError('gold reconstruction differs')
    return ev,gold


def construct_body(member,tasks):
    """The native ValidMutant of a body_replacement member. Native checks the whole candidate program and that only
    the body at member['point'] differs from gold; their reasons start with 'body_replacement:'."""
    _,gold=_identity_gold(member['task'],member['case'],canonical(member['gold']),str(tasks))
    c=member['construction'];program=object_value(member['program'])
    text=program['text'] if isinstance(program,dict) else program
    return gold.construct_body_replacement(member['point'],text,canonical(c['body_stream']) if c.get('body_stream') else None,
        source_revision=c['source_revision'],task=member['task'],case=member['case'])


def _same_native_program(member,rec,tasks):
    """Only text mismatches need this check (e.g. repaired writer names)."""
    if not member.get('identity') or not rec.get('mutant_stream'):return False
    import arclog
    try:
        _,gold=_identity_gold(member['task'],member['case'],canonical(member['gold']),str(tasks))
        mutant=gold.construct_identity(canonical(member['identity']))
        ids,model,paths=mutant.decode_stream();old=rec['mutant_stream']
        return ids==old['ids'] and list(model)==old['model'] and paths==old['paths']
    except (arclog.Refusal,ValueError,KeyError,TypeError,RuntimeError):return False


def accept(db,pair,member,rec,locator):
    # Exact original/candidate programs, exact native edit identity. Never match
    # a display fragment, task/point alone, or another assignment's table rows.
    if rec.get('status')=='fault' or not rec.get('native') or not rec.get('evaluation'):return False
    gold=object_value(member['gold']);program=object_value(member['program'])
    text=program['text'] if isinstance(program,dict) else program
    if rec.get('gold_sexp')!=gold['text']:return False
    if digest(pair_key(rec))!=pair:return False
    run_file=Path(locator['corpus'])/'run.json'
    if not run_file.exists():return False
    task_root=Path(json.loads(run_file.read_text())['tasks']).resolve()
    task_file=task_root/(rec['task']+'.json')
    if not task_file.exists() or hashlib.sha256(task_file.read_bytes()).hexdigest()!=member['task_sha256']:return False
    if rec.get('mutant_sexp')!=text and not _same_native_program(member,rec,task_root):return False
    loc=dict(locator,corpus=str(Path(locator['corpus']).resolve()),task=rec['task'],source_sha256=digest(rec))
    with db:db.execute('INSERT OR IGNORE INTO observations VALUES (?,?,?)',(pair,loc['source_sha256'],canonical(loc)))
    return True


def plan(a,db):
    start=time.monotonic();counts=Counter()
    with db:
        for k,v in dict(base=str(a.base.resolve()),labels=str(a.output.parent/'labels.sqlite3'),tasks=str(a.tasks.resolve())).items():
            old=db.execute('SELECT value FROM metadata WHERE key=?',(k,)).fetchone()
            if old and old[0]!=v:raise ValueError('population input location changed: '+k)
            db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)',(k,v))
    for member in candidates(a.population,a.candidate_stream):
        if member['identity']:
            pair=digest(pair_key(member))
        else:pair=digest(dict(schema='whole-body-candidate-v1',candidate_id=member['sampler']['candidate_id']))
        member['task_sha256']=hashlib.sha256((a.tasks/(member['task']+'.json')).read_bytes()).hexdigest()
        if member.get('sampler',{}).get('source',{}).get('task_sha256',member['task_sha256'])!=member['task_sha256']:raise ValueError('sampler task input differs')
        identity=member.get('identity')
        if identity:
            if identity['body']!=member['point'] or identity['clause']!=member['clause']:raise ValueError('candidate point binding differs')
            for k in ('task','case'):
                if identity.get('source',{}).get(k,member[k])!=member[k]:raise ValueError('candidate source binding differs')
        source=object_value(member['gold'])
        if source['task']!=member['task'] or source['case']!=member['case']:raise ValueError('gold source binding differs')
        sha=member_inputs(member);old=db.execute('SELECT input_sha256 FROM members WHERE pair_id=?',(pair,)).fetchone()
        if old and old[0]!=sha:raise ValueError('conflicting candidate inputs for '+pair)
        with db:db.execute('INSERT OR IGNORE INTO members VALUES (?,?,?)',(pair,sha,canonical(member)))
        counts['members']+=1
    wanted={p:json.loads(v) for p,v in db.execute('SELECT pair_id,payload FROM members') if observation(db,p) is None}
    # Indexed existing labels locate their raw records without a historical scan.
    old=ro(a.base)
    located={}
    for pair,member in wanted.items():
        row=old.execute('SELECT source_sha256,result_sha256,record_json FROM pairs WHERE pair_id=?',(pair,)).fetchone()
        if row and intact(row,row[0]):
            result=json.loads(row[2]);src=result['source'];path=Path(src['corpus'])/member['task']/src['file']
            located.setdefault(path,{})[src['line']]=(pair,member,src)
    old.close()
    for path,lines in located.items():
        last_line=max(lines)
        with gzip.open(path,'rt') as f:
            for n,raw in enumerate(f,1):
                if n in lines:
                    pair,member,src=lines[n]
                    if accept(db,pair,member,json.loads(raw),src):wanted.pop(pair,None);counts['reused_labeled']+=1
                if n>=last_line:break
        emit(start,counts['members']-len(wanted),counts['members'],**counts)
    # Only historical edit kinds can exist in the old corpus. New typed/block
    # alternatives cannot match it and therefore never trigger a wasted scan.
    legacy={'argument','relation','comparison','delete'}
    pending={p:m for p,m in wanted.items() if m['identity'] and all(e['kind'] in legacy for e in m['identity']['edits'])}
    universes={}
    for pair,text in db.execute('SELECT pair_id,payload FROM members'):
        m=json.loads(text)
        if m.get('identity') and all(e['kind'] in legacy for e in m['identity']['edits']):universes.setdefault(m['task'],[]).append(pair)
    universes={task:digest(sorted(pairs)) for task,pairs in universes.items()}
    from mutant_names import source_header
    for root in a.corpus:
        root=root.resolve()
        tasks={m['task'] for m in pending.values()}
        for task in sorted(tasks):
            path=root/task/'pairs.jsonl.gz'
            if not path.exists():continue
            stat=path.stat()
            sig=canonical([stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,universes[task]])
            previous=db.execute('SELECT signature,line,complete FROM scans WHERE path=?',(str(path),)).fetchone()
            if previous and previous[0]==sig and previous[2]:continue
            after=previous[1] if previous and previous[0]==sig else 0
            n=0
            with gzip.open(path,'rt') as f:
                for n,raw in enumerate(f,1):
                    if n<=after:continue
                    try:head=source_header(raw);pair=digest(pair_key(head))
                    except (ValueError,KeyError,TypeError):
                        counts['unreadable_historical_headers']+=1
                        continue
                    if pair in pending and accept(db,pair,pending[pair],json.loads(raw),dict(corpus=str(root),file=path.name,line=n,stream='kept')):
                        pending.pop(pair);counts['reused_raw']+=1
                    if n%1000==0:
                        with db:db.execute('INSERT OR REPLACE INTO scans VALUES (?,?,?,0)',(str(path),sig,n))
                        emit(start,counts['members']-len(pending),counts['members'],**counts)
            with db:db.execute('INSERT OR REPLACE INTO scans VALUES (?,?,?,1)',(str(path),sig,n))
    counts['observations']=db.execute('SELECT count(*) FROM observations').fetchone()[0]
    counts['members']=db.execute('SELECT count(*) FROM members').fetchone()[0]
    counts['missing_observations']=counts['members']-counts['observations']
    emit(start,counts['members'],counts['members'],**counts)


class MaterializeSession:
    """Sequential per-worker native state; reuse across members, close at end.

    args is the existing CLI settings namespace; database is the population
    membership connection. No task evaluation happens in the constructor.
    """
    def __init__(self,args,database):
        self.a=args;self.db=database;self.current=None;self.store=None;self.task_hashes={}
        self.ev=self.gold=self.dep=self.relations=self.observations=None
        self.filter_cache=self.payload_cache=self.task_data=None
        a=args;db=database
        import arclog
        import corpus as c
        from native_storage import NativeStore
        from filters import graph
        producer=dict(consumer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            native_binary_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(arclog.__file__).parent.glob('*.so')},
            settings=dict(seconds=a.seconds,work_cap=a.work_cap,session_mib=a.session_mib))
        producer_sha=digest(producer)
        with db:db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)',('producer:'+producer_sha,canonical(producer)))
        settings=arclog.DecodeSettings(table_work_cap=a.work_cap,rule_tests=False)
        self.settings=settings;self.producer_sha=producer_sha;self.producer=producer

    def task_manifest(self,task,case):
        """The corpus manifest of the export that the population's gold streams come from, with this producer."""
        import arclog
        import corpus as c
        config=json.loads((DATA_ROOT/'ast/run/corpus-v12-body-full/run.json').read_text())
        config['tasks']=str(self.a.tasks.resolve())
        # The keys of the manifest that corpus.py writes beside each task's pairs file.
        return dict(provenance=dict(producer_ref=self.producer_sha),record_format=c.RECORD_FORMAT,source_hashes=dict(consumer_sha256=self.producer['consumer_sha256']),
            binary_hashes=self.producer['native_binary_sha256'],config=config,task=task,cases=[case],
            streams_digest=arclog.streams_digest(),mutation_policy=arclog.StudyProgram.mutation_policy())

    def close(self):
        if self.store:self.store.close();self.store=None


def _member_pair(member):
    if member.get('identity'):return digest(pair_key(member))
    return digest(dict(schema='whole-body-candidate-v1',candidate_id=member['sampler']['candidate_id']))


def materialize_one(member,session,*,pair_id=None,input_sha256=None):
    """Materialize one member durably, or resume its observation/diagnostic."""
    a=session.a;db=session.db;pair=pair_id or _member_pair(member);task=member['task']
    inputs=input_sha256 or member_inputs(member)
    existing=observation(db,pair)
    if existing is not None:
        known=db.execute('SELECT input_sha256 FROM members WHERE pair_id=?',(pair,)).fetchone()
        if known and known[0]!=inputs:raise ValueError('population member inputs changed: '+pair)
        # Observations published before manifests were written get theirs here, without evaluation.
        manifest=Path(existing['corpus'])/existing['task']/'manifest.json'
        if Path(existing['corpus']).is_relative_to(a.output.parent/'observations') and not manifest.exists():
            tmp=manifest.with_suffix('.tmp');tmp.write_text(json.dumps(session.task_manifest(existing['task'],member['case']),indent=2)+'\n');os.replace(tmp,manifest)
        return dict(status='resumed_observation',pair_id=pair,locator=existing)
    import arclog
    import corpus as c
    from native_storage import NativeStore
    from filters import graph
    settings=session.settings;producer_sha=session.producer_sha
    current=session.current;store=session.store;ev=session.ev;gold=session.gold
    dep=session.dep;relations=session.relations;observations=session.observations
    filter_cache=session.filter_cache;payload_cache=session.payload_cache;task_data=session.task_data
    counts=Counter()
    class AbsoluteStore(NativeStore):
        def block(self,*args,**kwargs):
            ref=super().block(*args,**kwargs);ref['path']=str(self.root/'native/tables.pack');return ref
    try:
        # Recover a source atomically published just before a process died
        # between file publication and SQLite commit. Never replay it.
        orphan_root=a.output.parent/'observations'/pair
        orphan=orphan_root/member['task']/'pairs.jsonl'
        if any(Path(str(orphan)+suffix).exists() for suffix in ('','.zst','.gz')):
            try:
                with JsonlReader(orphan) as reader:
                    saved=json.loads(reader.read_line(1));orphan=reader.path
                if saved.get('population_inputs')==inputs and digest(pair_key(saved))==pair:
                    loc=dict(corpus=str(orphan_root),task=member['task'],file=orphan.name,line=1,stream='kept',source_sha256=digest(saved))
                    with db:db.execute('INSERT OR REPLACE INTO observations VALUES (?,?,?)',(pair,loc['source_sha256'],canonical(loc)))
                    counts['recovered_publication']+=1
                    return dict(status='recovered_publication',pair_id=pair,locator=observation(db,pair))
            except (OSError,EOFError,ValueError,KeyError,StopIteration):pass
        prior=db.execute('SELECT input_sha256 FROM attempts WHERE pair_id=?',(pair,)).fetchone()
        if prior and prior[0]==inputs and not a.retry_failures:
            counts['resumed_unavailable']+=1
            return dict(status='resumed_unavailable',pair_id=pair)
        try:
            task_path=a.tasks/(task+'.json');stat=task_path.stat()
            signature=(stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)
            cached=session.task_hashes.get(task)
            if cached is None or cached[0]!=signature:
                cached=(signature,hashlib.sha256(task_path.read_bytes()).hexdigest());session.task_hashes[task]=cached
            if cached[1]!=member['task_sha256']:raise ValueError('task input changed; create new population membership')
            construction=member['construction']
            if construction['kind'] not in ('native_edit_identity','body_replacement'):raise ValueError('unknown construction kind: '+str(construction['kind']))
            if not construction.get('identity'):raise ValueError('member has no native identity')
            gold_object=object_value(member['gold']);key=(member['task'],member['case'],member['gold']['sha256'])
            if key!=current:
                if store:store.close()
                current=None;store=None
                task=member['task'];task_data=json.loads((a.tasks/(task+'.json')).read_text())
                ev=arclog.StudyTaskEvaluator(task,str(a.tasks),settings,session_bytes=a.session_mib*1024*1024,compact=True)
                gold=ev.from_stream(gold_object['stream']['ids'],gold_object['stream']['model'])
                if gold.sexp()!=gold_object['text']:raise ValueError('stored gold reconstruction differs')
                packroot=a.output.parent/'packs'/uuid.uuid4().hex;store=AbsoluteStore(packroot)
                dep=graph(gold.sexp());relations=c.GoldRelations(ev,gold,packroot,0,dep,store)
                observations=c.GoldObservations();filter_cache={};payload_cache={};current=key
            point=next(p for p in gold.points() if list(p.body_path)==member['point'] and list(p.clause_path)==member['clause'])
            if point.kind!=member['kind']:raise ValueError('point kind differs')
            mutant=gold.construct_identity(canonical(construction['identity']))
            program=object_value(member['program']);expected=program['text'] if isinstance(program,dict) else program
            if mutant.sexp()!=expected:raise ValueError('candidate reconstruction differs')
            ms=mutant.decode_stream();audit=json.loads(mutant.audit_json())
            if isinstance(program,dict) and (ms[0]!=program['stream']['ids'] or list(ms[1])!=program['stream']['model']):raise ValueError('sampler native program stream differs')
            if construction['kind']=='body_replacement':
                if mutant.k!=member['K'] or audit.get('changed_bodies')!=1 or audit.get('outside_body_unchanged') is not True:raise ValueError('candidate body audit differs')
            elif audit['changed_atoms']!=member['K']:raise ValueError('candidate edit count differs')
            row={k:member[k] for k in ('task','case','point','clause','kind','K','operation','identity')}
            row.update(type='pair',record_format=c.RECORD_FORMAT,programs=dict(gold=gold.sexp(),mutant=mutant.sexp()),gold_sexp=gold.sexp(),mutant_sexp=mutant.sexp(),mutant_stream=dict(ids=ms[0],model=list(ms[1]),paths=ms[2]),audit=audit,
                relation_source_names=json.loads(gold.relation_source_names_json(str(c.MAIN_ROOT/'programs/arclog'),task,member['case'])),producer_ref=producer_sha,population_inputs=inputs)
            row,timings,_=c.observe_constructed(row,ev,gold,point,mutant,len(task_data['train']),dep,relations,store,observations,filter_cache,payload_cache)
            row['timings']=timings
            store.pack.flush();os.fsync(store.pack.fileno())
            root=a.output.parent/'observations'/pair;destination=root/task;destination.mkdir(parents=True,exist_ok=True)
            # Canonical source layout permits every existing pass to read
            # this record, with absolute immutable native-pack references.
            with (root/'run.json').open('w') as f:
                f.write(canonical(dict(tasks=str(a.tasks.resolve()))));f.flush();os.fsync(f.fileno())
            with (destination/'manifest.json').open('w') as f:
                f.write(json.dumps(session.task_manifest(task,member['case']),indent=2)+'\n');f.flush();os.fsync(f.fileno())
            path=destination/'pairs.jsonl.zst'
            with JsonlWriter(path) as out:
                if out.committed_lines!=0:raise ValueError('published observation differs; preserve existing source')
                out.write(row)
            for directory_path in (destination,root,root.parent,store.root/'native',store.root,store.root.parent,a.output.parent):
                directory=os.open(directory_path,os.O_RDONLY)
                try:os.fsync(directory)
                finally:os.close(directory)
            locator=dict(corpus=str(root),task=task,file=path.name,line=1,stream='kept',source_sha256=digest(row))
            with db:db.execute('INSERT OR REPLACE INTO observations VALUES (?,?,?)',(pair,digest(row),canonical(locator)))
            counts['written']+=1
        except Exception as error:
            with db:db.execute('INSERT OR REPLACE INTO attempts VALUES (?,?,?)',(pair,inputs,canonical(dict(reason=str(error),error_type=type(error).__name__))))
            counts['unavailable']+=1
    finally:
        for name in ('current','store','ev','gold','dep','relations','observations',
                     'filter_cache','payload_cache','task_data'):
            setattr(session,name,locals()[name])
    status=next(iter(counts),'unavailable')
    return dict(status=status,pair_id=pair,locator=observation(db,pair))


def materialize(a,db):
    pending=list(db.execute("SELECT pair_id,input_sha256,payload FROM members WHERE pair_id NOT IN (SELECT pair_id FROM observations) ORDER BY json_extract(payload,'$.task'),json_extract(payload,'$.case')"))
    start=time.monotonic();counts=Counter();session=MaterializeSession(a,db)
    try:
        for done,(pair,inputs,payload) in enumerate(pending,1):
            result=materialize_one(json.loads(payload),session,pair_id=pair,input_sha256=inputs)
            counts[result['status']]+=1;emit(start,done,len(pending),**counts)
    finally:session.close()


class LabelSession:
    """One sequential base labeler per process; owns the canonical run globals."""
    def __init__(self,args,database):
        import run as r
        from threading import Event
        class Events:
            def put(self,value):pass
        self.a=args;self.db=database;self.r=r
        manifest=r.code_manifest(HERE,HERE/'mech/algorithm.py')
        output=args.output.parent/'labels.sqlite3';r.setup(output)
        r.initialize(str(HERE),manifest,str(output),dict(seconds=args.seconds,baseline_seconds=.5,semantics=r.SEMANTICS),False,Events(),Event())
        self.old=ro(args.base)

    def close(self):
        self.old.close();self.r.DB.close()


def label_one(pair,session):
    """Label/resume one published population observation. No population scan."""
    a=session.a;db=session.db;r=session.r
    row=db.execute('SELECT source_sha256,locator FROM observations WHERE pair_id=?',(pair,)).fetchone()
    if row is None:return dict(status='observation_unavailable',pair_id=pair)
    sha,text=row
    prior=session.old.execute('SELECT source_sha256,result_sha256,record_json FROM pairs WHERE pair_id=?',(pair,)).fetchone()
    if intact(prior,sha):return dict(status='reused_base',pair_id=pair,result=json.loads(prior[2]))
    own=r.DB.execute('SELECT source_sha256,result_sha256,record_json FROM pairs WHERE pair_id=?',(pair,)).fetchone()
    if intact(own,sha) and not (a.retry_failures and json.loads(own[2]).get('error')):
        return dict(status='resumed_own',pair_id=pair,result=json.loads(own[2]))
    loc=json.loads(text);rec=read_source(loc)
    if set(rec.get('rejection_reasons',[]))-{'post_filter_quota','recoverable_gold'}:
        return dict(status='filtered',pair_id=pair)
    r.label_record(rec,Path(loc['corpus'])/rec['task'],loc['stream'],loc['file'],loc['line'])
    result=r.DB.execute('SELECT record_json FROM pairs WHERE pair_id=?',(pair,)).fetchone()
    return dict(status='label_members',pair_id=pair,result=json.loads(result[0]))


def label(a,db):
    session=LabelSession(a,db);start=time.monotonic();counts=Counter()
    rows=list(db.execute('SELECT pair_id FROM observations'))
    try:
        for done,(pair,) in enumerate(rows,1):
            result=label_one(pair,session);counts[result['status']]+=1
            emit(start,done,len(rows),**counts)
    finally:session.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('phase',choices=['plan','materialize','label']);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--population',type=Path);p.add_argument('--candidate-stream',type=Path)
    p.add_argument('--base',type=Path,default=DATA_ROOT/'ast/run/mech/labels.sqlite3')
    p.add_argument('--corpus',type=Path,nargs='*',default=[DATA_ROOT/'ast/run/corpus-v12-body-full'])
    p.add_argument('--tasks',type=Path,required=True);p.add_argument('--seconds',type=float,default=1);p.add_argument('--work-cap',type=int,default=67108864);p.add_argument('--session-mib',type=int,default=2048);p.add_argument('--retry-failures',action='store_true')
    a=p.parse_args();a.output=a.output.resolve();a.output.parent.mkdir(parents=True,exist_ok=True)
    if a.phase=='plan' and not (a.population or a.candidate_stream):p.error('plan requires --population or --candidate-stream')
    if a.seconds<=0 or a.work_cap<=0 or a.session_mib<=0:p.error('limits must be positive')
    with open(str(a.output)+'.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        db=connect(a.output)
        try:globals()[a.phase](a,db)
        finally:db.close()
if __name__=='__main__':main()
