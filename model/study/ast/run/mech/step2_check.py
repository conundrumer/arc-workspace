#!/usr/bin/env python3
"""Step 2: reuse stored test results, apply only untested train witnesses.

No recovery search or mutant replay. The base remains read-only. Every witness
result commits before its pair grade, so interruption never loses a done check.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[3]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse
from collections import Counter
import fcntl
import gzip
import hashlib
import json
from pathlib import Path
import signal
import sqlite3
import sys
import time

from grade_store import GradeStore
from run import canonical,digest,pair_key
from witness_test import Checker,stored_result,train_witness

HERE=Path(__file__).resolve().parent
STUDY=HERE.parents[2]
STOP=False


def stop(*_):
    global STOP
    STOP=True


def valid_base(row):
    pair,source,code,config,result,payload=row
    record=json.loads(payload)
    if (record['pair_id']!=pair or record['source_sha256']!=source or digest(record)!=result
            or digest(record['code_manifest'])!=code or record['code_sha256']!=code
            or digest(record['config'])!=config or record['config_sha256']!=config):
        raise ValueError('base integrity differs: '+pair)
    return record


class Pass:
    def __init__(self,args,ev):
        self.args=args;self.ev=ev;self.start=time.monotonic();self.last=0
        self.base=sqlite3.connect(args.base.resolve().as_uri()+'?mode=ro',uri=True)
        self.base.execute('BEGIN')
        files=set(HERE/n for n in ('step2_check.py','witness_test.py','step1_reduce.py',
            'grade_store.py','grades.py','admission.py','clause_evidence.py','outcomes.py','run.py'))
        files.update((STUDY/'judgetool').glob('*.py'))
        files.update(STUDY/n for n in ('judge2/render2/headers.py','judge2/render2/body.py',
            'ast/run/next_revision/family_recovery.py','ast/run/filters.py',
            'ast/run/recovery.py','ast/run/native_storage.py','ast/run/native_tables.py',
            'ref/progsynth-relabel/engine_verify.py','ref/progsynth-relabel/verify_recovery.py',
            'codex-adm/briefs/judge-decisions.md'))
        files.add(CODE_ROOT / 'study_paths.py')
        files.add(Path(ev.runtime['binary']))
        self.manifest={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
        self.file_stats={name:self.signature(Path(name)) for name in self.manifest}
        config=dict(schema='mech-step2-config-v1',base=str(args.base.resolve()),
            spec_sha256=hashlib.sha256((STUDY/'codex-adm/briefs/judge-decisions.md').read_bytes()).hexdigest(),
            evaluator=ev.receipt,verification_seconds=args.verify_seconds,
            reuse='per-assignment bool; generalizes bool/0/1 on assignment 0',
            target='fresh raw gold BODY; public INIT point admission remains step 3',
            policy='one application per missing witness; no search or mutant replay',
            compatible_boolean_producers=sorted(args.compatible_boolean_producer))
        self.store=GradeStore(args.output,self.manifest,config);self.db=self.store.db
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS witness_tests(
            pair_id TEXT NOT NULL,assignment INTEGER NOT NULL,witness_sha256 TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,base_result_sha256 TEXT NOT NULL,
            code_sha256 TEXT NOT NULL,config_sha256 TEXT NOT NULL,
            result_sha256 TEXT NOT NULL,payload TEXT NOT NULL,
            PRIMARY KEY(pair_id,assignment));
          CREATE TABLE IF NOT EXISTS step2_pairs(
            pair_id TEXT PRIMARY KEY,base_result_sha256 TEXT NOT NULL,
            code_sha256 TEXT NOT NULL,config_sha256 TEXT NOT NULL,
            evidence_sha256 TEXT NOT NULL,grade_sha256 TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS step2_work(
            pair_id TEXT PRIMARY KEY,corpus TEXT NOT NULL,file TEXT NOT NULL,line INTEGER NOT NULL);
        ''')
        self.db.execute('DELETE FROM step2_work');self.db.commit()
        self.checker=Checker(ev,verify_seconds=args.verify_seconds)
        self.counts=Counter();self.tasks={};self.total=self.base.execute('SELECT count(*) FROM pairs').fetchone()[0]
        self.compatible={tuple(value.split(':',1)) for value in args.compatible_boolean_producer}
        self.retry_unknown=set()
        if args.retry_unknown:
            for pair,assignment,payload in self.db.execute('SELECT pair_id,assignment,payload FROM witness_tests'):
                if json.loads(payload).get('test_verified') is None:self.retry_unknown.add((pair,assignment))
        self.retry_pairs={pair for pair,assignment in self.retry_unknown}


    def progress(self,phase,done,total,force=False):
        elapsed=time.monotonic()-self.start
        if force or elapsed-self.last>=5:
            rate=done/max(elapsed,.001)
            eta=(total-done)/rate if rate else None
            print(f'phase={phase} done={done}/{total} elapsed={elapsed:.1f}s rate={rate:.2f}/s '
                  f'ETA={eta if eta is not None else "unknown"}s counters={dict(self.counts)}',file=sys.stderr,flush=True)
            self.last=elapsed

    def guard(self):
        # Fail before applying more code if an owner replaces a dependency.
        for name,expected in self.manifest.items():
            path=Path(name);signature=self.signature(path)
            if signature==self.file_stats[name]:continue
            if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                raise RuntimeError('dependency changed during step 2; restart: '+name)
            self.file_stats[name]=signature

    @staticmethod
    def signature(path):
        s=path.stat()
        return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)

    def journal(self,base,item):
        row=self.db.execute('SELECT witness_sha256,source_sha256,base_result_sha256,code_sha256,'
            'config_sha256,result_sha256,payload FROM witness_tests WHERE pair_id=? AND assignment=?',
            (base['pair_id'],item['assignment'])).fetchone()
        expected=(digest(item['witness']),base['source_sha256'],digest(base),self.store.code,self.store.config_hash)
        if row and tuple(row[:3])==expected[:3] and digest(json.loads(row[6]))==row[5]:
            result=json.loads(row[6]);producer=tuple(row[3:5])
            if type(result.get('test_verified')) is bool and producer in self.compatible:
                # Explicit predecessor acceptance applies ONLY to unchanged
                # boolean payloads with exact pair/source/base/witness identity.
                return result
            if tuple(row[:5])==expected and (base['pair_id'],item['assignment']) not in self.retry_unknown:
                return result
        return None

    def save_check(self,base,item,result):
        # The small completed record is durable independently of the pair.
        result=dict(result,pair_id=base['pair_id'],assignment=item['assignment'],
            witness_sha256=digest(item['witness']),source_sha256=base['source_sha256'],
            base_result_sha256=digest(base))
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO witness_tests VALUES (?,?,?,?,?,?,?,?,?)',
                (base['pair_id'],item['assignment'],digest(item['witness']),base['source_sha256'],
                 digest(base),self.store.code,self.store.config_hash,digest(result),canonical(result)))
        self.retry_unknown.discard((base['pair_id'],item['assignment']))
        return result

    def completed(self,base):
        if base['pair_id'] in self.retry_pairs:return False
        row=self.db.execute('SELECT base_result_sha256,code_sha256,config_sha256,evidence_sha256,'
            'grade_sha256 FROM step2_pairs WHERE pair_id=?',(base['pair_id'],)).fetchone()
        if not row or tuple(row[:3])!=(digest(base),self.store.code,self.store.config_hash):return False
        e=self.db.execute('SELECT result_sha256,payload FROM evidence WHERE pair_id=?',(base['pair_id'],)).fetchone()
        g=self.db.execute('SELECT result_sha256,record_json FROM grades WHERE pair_id=?',(base['pair_id'],)).fetchone()
        return bool(e and g and e[0]==row[3] and g[0]==row[4]
                    and digest(json.loads(e[1]))==e[0] and digest(json.loads(g[1]))==g[0])

    def finish_pair(self,base):
        items=[i for i in base.get('per_assignment',[]) if train_witness(i)]
        checks=[self.journal(base,i) for i in items]
        if not items or any(c is None for c in checks):raise ValueError('unfinished witness journal')
        row=self.db.execute('SELECT result_sha256,payload FROM evidence WHERE pair_id=?',(base['pair_id'],)).fetchone()
        if not row or digest(json.loads(row[1]))!=row[0]:raise ValueError('step 1 evidence missing/changed')
        evidence=json.loads(row[1]);ref=evidence['base_result_ref']
        if evidence.get('step',1)>2:raise ValueError('refusing to replace evidence from a later step')
        if ref['result_sha256']!=digest(base):raise ValueError('step 1 references another base result')
        evidence['step']=2
        evidence['mechanical_clauses']=[]
        references=[dict(database=str(self.args.output.resolve()),table='witness_tests',pair_id=base['pair_id'],
            assignment=c['assignment'],result_sha256=digest(c)) for c in checks]
        evidence['witness_tests']=dict(schema='mech-pair-tests-v1',checks=references,
            compatible_boolean_producers=sorted(self.args.compatible_boolean_producer),
            verified=sum(c['test_verified'] is True for c in checks),
            mismatch=sum(c['test_verified'] is False for c in checks),
            unknown=sum(c['test_verified'] is None for c in checks))
        missing=[s for s in evidence['missing_steps'] if s!='step_2_witness_test_check']
        if any(c['test_verified'] is None for c in checks):missing.append('step_2_witness_test_check')
        all_assignments=(not base.get('error') and len(items)==len(base['per_assignment'])
                         and sorted(i['assignment'] for i in items)==list(range(len(items))))
        all_pass=all_assignments and all(c['test_verified'] is True for c in checks)
        # Raw BODY witnesses are the existing pass's grammar. INIT public inputs
        # and DNF union provenance need settled admission in step 3; a successful
        # raw test does not fabricate those distinct facts.
        ordinary=(str(base['kind']).lower()=='rule'
                  and all(len(i['witness'].get('selection_any',[]))<=1 for i in items))
        if all_pass and ordinary and base.get('label')!='equivalent':
            evidence['mechanical_clauses']=[dict(outcome='recovery verified',purpose='answer',
                check=dict(train=True,test=True,complete=True,kept_contexts_complete=True,
                           test_target='gold_full_replay',receipt_ref=references),
                provenance=dict(target_columns='X_or_single_row_lib_from_X',lib_single_row_per_X=True,
                                restrictions_only=True,union=False),receipt_ref=references,
                source='stored train witness plus step 2 test journal')]
        elif all_pass and not ordinary:
            missing.append('step_3_point_projection_and_witness_admission')
        evidence['missing_steps']=list(dict.fromkeys(missing))
        evidence_hash=digest(evidence)
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO evidence VALUES (?,?,?,?,?,?,?)',
                (base['pair_id'],base['source_sha256'],self.store.code,self.store.config_hash,
                 digest(base),evidence_hash,canonical(evidence)))
            grade,_=self.store.save(evidence,inputs_authenticated=False)
            self.db.execute('INSERT OR REPLACE INTO step2_pairs VALUES (?,?,?,?,?,?)',
                (base['pair_id'],digest(base),self.store.code,self.store.config_hash,evidence_hash,digest(grade)))
        self.retry_pairs.discard(base['pair_id'])
        self.counts['pairs_done']+=1

    def prepare(self):
        cursor=self.base.execute('SELECT pair_id,source_sha256,code_sha256,config_sha256,result_sha256,'
                                 'record_json FROM pairs ORDER BY pair_id')
        for done,row in enumerate(cursor,1):
            if STOP:return False
            base=valid_base(row);items=[i for i in base.get('per_assignment',[]) if train_witness(i)]
            if not items:
                self.counts['pairs_without_train_witness']+=1
            elif self.completed(base):self.counts['pairs_resumed']+=1
            else:
                pending=False;self.counts['train_witnesses']+=len(items)
                for item in items:
                    result=self.journal(base,item)
                    if result is not None:self.counts['witnesses_resumed']+=1;continue
                    value,origin=stored_result(base,item)
                    if value is None:pending=True;continue
                    self.save_check(base,item,dict(schema='mech-witness-test-v1',test_verified=value,
                        status='verified' if value else 'mismatch',origin=origin,
                        test_target='stored gold test result (coordinator-authorized reuse)',
                        evaluations=0,seconds=0))
                    self.counts['reused_true' if value else 'reused_false']+=1
                if pending:
                    src=base['source'];corpus=str(Path(src['corpus']).resolve())
                    with self.db:self.db.execute('INSERT OR REPLACE INTO step2_work VALUES (?,?,?,?)',
                        (base['pair_id'],corpus,base['task']+'/'+src['file'],src['line']))
                    self.counts['pairs_queued']+=1
                else:self.finish_pair(base)
            self.progress('stored',done,self.total)
        self.progress('stored',self.total,self.total,True)
        return True

    def get_base(self,pair):
        return valid_base(self.base.execute('SELECT pair_id,source_sha256,code_sha256,config_sha256,'
            'result_sha256,record_json FROM pairs WHERE pair_id=?',(pair,)).fetchone())

    def task(self,name):
        if name not in self.tasks:
            path=(Path(self.ev.cfg['tasks'])/(name+'.json')).resolve()
            raw=path.read_bytes();task=json.loads(raw)
            self.tasks[name]=(len(task['train']),len(task['test']),dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest()))
        return self.tasks[name]

    def evaluate_pair(self,pair,record,error=None):
        base=self.get_base(pair)
        if record is not None and (digest(record)!=base['source_sha256'] or digest(pair_key(record))!=pair):
            error=ValueError('current source identity differs from base');record=None
        for item in base.get('per_assignment',[]):
            if not train_witness(item) or self.journal(base,item) is not None:continue
            if STOP:return False
            self.guard()
            if record is None:
                result=dict(schema='mech-witness-test-v1',test_verified=None,status='unknown',
                            reason=str(error),origin='source unavailable',evaluations=0)
            else:
                try:
                    ntrain,ntest,task_receipt=self.task(base['task'])
                    result=self.checker.check(record,item,native_base=Path(base['source']['corpus']).resolve()/base['task'],
                                              ntrain=ntrain,ntest=ntest)
                    result['task_receipt']=task_receipt
                except Exception as exc:
                    result=dict(schema='mech-witness-test-v1',test_verified=None,status='unknown',reason=str(exc),
                                error_type=type(exc).__name__,origin='test preparation unavailable',evaluations=0)
            self.guard()
            self.save_check(base,item,result)
            self.counts['new_'+('true' if result['test_verified'] is True else
                               'false' if result['test_verified'] is False else 'unknown')]+=1
        self.finish_pair(base)
        return True

    def evaluate(self):
        # One sequential gzip scan per source; never decompress from the start
        # separately for every selected pair. Only queued lines are JSON-decoded.
        work=self.db.execute('SELECT pair_id,corpus,file,line FROM step2_work ORDER BY corpus,file,line,pair_id').fetchall()
        stream=None;path=None;lineno=0;failed=None;last_record=None
        try:
            for done,(pair,corpus,filename,wanted) in enumerate(work,1):
                if STOP:return False
                current=Path(corpus)/filename
                if current!=path:
                    if stream is not None:stream.close()
                    stream=None;path=current;lineno=0;failed=None;last_record=None
                    try:stream=gzip.open(current,'rt')
                    except (OSError,ValueError) as exc:failed=exc
                if failed is None:
                    try:
                        while lineno<wanted:
                            line=next(stream);lineno+=1
                            if lineno==wanted:last_record=json.loads(line)
                        if lineno!=wanted:raise ValueError('source line order differs')
                    except (OSError,EOFError,ValueError,StopIteration) as exc:
                        failed=ValueError(f'{current}: source line {lineno}, wanted {wanted}: {type(exc).__name__}: {exc}')
                        last_record=None
                if not self.evaluate_pair(pair,last_record,failed):return False
                self.progress('missing-tests',done,len(work))
            self.progress('missing-tests',len(work),len(work),True)
            return True
        finally:
            if stream is not None:stream.close()

    def summary(self,complete):
        counts=Counter();missing=Counter()
        for payload, in self.db.execute('SELECT record_json FROM grades'):
            grade=json.loads(payload);counts[grade['grade']]+=1;missing.update(grade.get('missing_steps',[]))
        summary=dict(schema='mech-step-summary-v1',step=2,complete=complete,total=self.total,
            grade_counts=dict(counts),missing_step_counts=dict(missing),counters=dict(self.counts),
            new_witness_applications=self.checker.evaluations,new_gold_replays=self.checker.gold_replays,
            base=str(self.args.base.resolve()),output=str(self.args.output.resolve()),
            code_sha256=self.store.code,config_sha256=self.store.config_hash,
            elapsed_seconds=time.monotonic()-self.start)
        self.args.summary.write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps(summary,sort_keys=True),file=sys.stderr,flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=DATA_ROOT / 'ast/run/mech/labels.sqlite3')
    ap.add_argument('--output',type=Path,default=DATA_ROOT / 'ast/run/mech/settled.sqlite3')
    ap.add_argument('--summary',type=Path,default=DATA_ROOT / 'ast/run/mech/step2-summary.json')
    ap.add_argument('--retry-unknown',action='store_true',help='retry null/missing checks; never rerun completed booleans')
    ap.add_argument('--compatible-boolean-producer',action='append',default=[],metavar='CODE_SHA:CONFIG_SHA',
                    help='accept byte-identical boolean results from this explicit predecessor')
    ap.add_argument('--deadline',type=float,default=30)
    ap.add_argument('--verify-seconds',type=float,default=5)
    ap.add_argument('--artifacts',type=Path,default=DATA_ROOT / 'judgetool/mech-step2')
    args=ap.parse_args()
    for value in args.compatible_boolean_producer:
        parts=value.split(':')
        if len(parts)!=2 or any(len(p)!=64 or any(c not in '0123456789abcdef' for c in p) for p in parts):
            ap.error('expected CODE_SHA:CONFIG_SHA for compatible boolean producer')
    if args.base.resolve()==args.output.resolve():ap.error('base and output must differ')
    if not args.output.exists():ap.error('step 1 settled database is required')
    if args.deadline<=0 or args.verify_seconds<=0:ap.error('bounds must be positive')
    sys.path[:0]=[str(STUDY/'judgetool'),str(STUDY/'ast/run')]
    # Refuse an incomplete shared-helper deployment before opening the journal.
    # Missing repair APIs must not turn thousands of pairs into unknown records.
    import tables
    required=('comparison_type','decode_kept','compatible_kept')
    missing=[name for name in required if not callable(getattr(tables,name,None))]
    if not callable(getattr(tables.TargetStore,'selector_snapshot',None)):
        missing.append('TargetStore.selector_snapshot')
    if missing:ap.error('shared test-check repairs must be merged first: '+', '.join(missing))
    lock=args.output.with_suffix('.postprocess.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    from evaluator import ReplayEvaluator
    ev=ReplayEvaluator(deadline=args.deadline,artifacts=args.artifacts)
    worker=None
    try:
        worker=Pass(args,ev)
        complete=worker.prepare() and worker.evaluate()
        worker.guard();worker.summary(complete)
    finally:
        if worker is not None:worker.store.close();worker.base.close()
        ev.close();lock.close()
    if not complete:raise SystemExit(130)


if __name__=='__main__':main()
