#!/usr/bin/env python3
"""Step 2: reuse stored test results, apply only untested train witnesses.

No recovery search or base relabeling. Shared gold acquisition may use the
canonical native point fallback; each actual operation is receipted. Every
witness result commits immediately, independently of every other pair.
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

from grade_store import PassStore
from fact_objects import FactObjects,unpack
from run import canonical,digest,pair_key
from witness_test import Checker,stored_result,train_witness,witness_inputs

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
        self.phase=None;self.phase_start=self.start
        self.base=sqlite3.connect(args.base.resolve().as_uri()+'?mode=ro',uri=True)
        self.base.execute('BEGIN')
        files=set(HERE/n for n in ('step2_check.py','witness_test.py','fact_objects.py',
            'grade_store.py','run.py','source_read.py','source_bindings.py'))
        files.update(STUDY/'judgetool'/n for n in ('evaluator.py','raw_body.py','tables.py',
            'checks.py','surface.py','case_collector.py','catalog.py'))
        files.add(STUDY/'ast/check_stage1_all.py')
        files.update(STUDY/n for n in ('judge2/render2/headers.py','judge2/render2/body.py',
            'ast/run/next_revision/family_recovery.py','ast/run/filters.py',
            'ast/run/recovery.py','ast/run/native_storage.py','ast/run/native_tables.py',
            'ref/progsynth-relabel/engine_verify.py','ref/progsynth-relabel/verify_recovery.py'))
        files.add(CODE_ROOT / 'study_paths.py')
        files.add(CODE_ROOT / 'judge3/framed_jsonl.py')
        files.add(Path(ev.runtime['binary']))
        self.manifest={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
        self.file_stats={name:self.signature(Path(name)) for name in self.manifest}
        config=dict(schema='mech-step2-config-v1',base=str(args.base.resolve()),
            evaluator=ev.receipt,verification_seconds=args.verify_seconds,
            reuse='per-assignment bool; generalizes bool/0/1 on assignment 0',
            target='fresh raw gold BODY; public INIT point admission remains step 3',
            policy='one application per missing witness; no search or base relabeling',
            compatible_boolean_producers=sorted(args.compatible_boolean_producer),
            reuse_completed_booleans=args.reuse_completed_booleans)
        self.store=PassStore(args.output,self.manifest,config);self.db=self.store.db
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS witness_tests(
            pair_id TEXT NOT NULL,assignment INTEGER NOT NULL,witness_sha256 TEXT NOT NULL,
            source_sha256 TEXT NOT NULL,base_result_sha256 TEXT NOT NULL,
            code_sha256 TEXT NOT NULL,config_sha256 TEXT NOT NULL,
            result_sha256 TEXT NOT NULL,payload TEXT NOT NULL,
            PRIMARY KEY(pair_id,assignment));
        ''')
        self.objects=FactObjects(self.db);self.db.commit()
        self.work=[]
        self.checker=Checker(ev,verify_seconds=args.verify_seconds)
        self.counts=Counter();self.tasks={};self.base_hashes={};self.journal_pair=None;self.journal_values={};self.receipt_cache={};self.total=self.base.execute('SELECT count(*) FROM pairs').fetchone()[0]
        self.compatible={tuple(value.split(':',1)) for value in args.compatible_boolean_producer}
        self.retry_unknown=set()
        if args.retry_unknown:
            for pair,assignment,payload in self.db.execute('SELECT pair_id,assignment,payload FROM witness_tests'):
                if json.loads(payload).get('test_verified') is None:self.retry_unknown.add((pair,assignment))
        self.retry_pairs={pair for pair,assignment in self.retry_unknown}


    def progress(self,phase,done,total,force=False):
        now=time.monotonic()
        if phase!=self.phase:self.phase=phase;self.phase_start=now
        elapsed=now-self.start;phase_elapsed=now-self.phase_start
        if force or elapsed-self.last>=5:
            rate=done/max(phase_elapsed,.001)
            eta=(total-done)/rate if rate else None
            print(f'phase={phase} done={done}/{total} elapsed={elapsed:.1f}s phase_elapsed={phase_elapsed:.1f}s rate={rate:.2f}/s '
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

    def base_sha(self,base):
        pair=base['pair_id']
        if pair not in self.base_hashes:self.base_hashes[pair]=digest(base)
        return self.base_hashes[pair]

    def journal(self,base,item):
        pair=base['pair_id'];assignment=item['assignment']
        if pair!=self.journal_pair:self.journal_pair=pair;self.journal_values={}
        if assignment in self.journal_values:return self.journal_values[assignment]
        row=self.db.execute('SELECT witness_sha256,source_sha256,base_result_sha256,code_sha256,'
            'config_sha256,result_sha256,payload FROM witness_tests WHERE pair_id=? AND assignment=?',
            (pair,assignment)).fetchone()
        expected=(digest(item['witness']),base['source_sha256'],self.base_sha(base),self.store.code,self.store.config_hash)
        result=None
        packed=json.loads(row[6]) if row else None
        from source_bindings import witness_source
        prior_base,prior_item=witness_source(base,item)
        expected_witness=digest(prior_item['witness'])
        applications={(expected_witness,prior_base['source_sha256']),(digest(item['witness']),base['source_sha256'])}
        if row and tuple(row[:2]) in applications and digest(packed)==row[5]:
            # Resume needs the fact and its actual application inputs, not
            # the full native report/comparison trees. Those remain stored
            # and are authenticated by the analysis reader when consumed.
            if len(self.receipt_cache)>256:self.receipt_cache.clear()
            value={key:unpack(self.db,packed[key],self.receipt_cache)
                   for key in ('test_verified','input_sha256','task_receipt') if key in packed}
            # Code/config hashes are provenance, not resume keys. Only an
            # explicit retry revisits an input-bound unknown result.
            reuse=(type(value.get('test_verified')) is bool or (pair,assignment) not in self.retry_unknown)
            if value.get('input_sha256') and value['input_sha256']!=witness_inputs(base,item):reuse=False
            task=value.get('task_receipt')
            if task and task.get('sha256')!=self.task(base['task'])[2]['sha256']:reuse=False
            if reuse:result=dict(value,pair_id=pair,assignment=assignment)
        # Base test facts are already stored once in the base. Reuse virtually,
        # rather than copying them into a second durable journal.
        if result is None:
            value,origin=stored_result(base,item)
            if value is not None:result=dict(schema='mech-witness-test-v1',test_verified=value,origin=origin,
                pair_id=pair,assignment=assignment,test_target='stored gold test result (coordinator-authorized reuse)',evaluations=0)
        self.journal_values[assignment]=result
        return result

    def save_check(self,base,item,result):
        # Identity is already in the row columns; keep only this pass's fact in
        # the payload. Readers accept the old inline v1 schema without reruns.
        result=dict(result,schema='mech-witness-test-fact-v2',input_sha256=witness_inputs(base,item))
        for key in ('pair_id','assignment','witness_sha256','source_sha256','base_result_sha256'):result.pop(key,None)
        with self.db:
            packed=self.objects.pack(result,root=True)
            self.db.execute('INSERT OR REPLACE INTO witness_tests VALUES (?,?,?,?,?,?,?,?,?)',
                (base['pair_id'],item['assignment'],digest(item['witness']),base['source_sha256'],
                 self.base_sha(base),self.store.code,self.store.config_hash,digest(packed),canonical(packed)))
        self.retry_unknown.discard((base['pair_id'],item['assignment']))
        expanded=dict(result,pair_id=base['pair_id'],assignment=item['assignment'])
        self.journal_pair=base['pair_id'];self.journal_values[item['assignment']]=expanded
        return expanded

    def completed(self,base):
        if base['pair_id'] in self.retry_pairs:return False
        items=[i for i in base.get('per_assignment',[]) if train_witness(i)]
        return bool(items) and all(self.journal(base,i) is not None for i in items)

    def finish_pair(self,base):
        # Only witness_tests are durable facts. Pair completion and grade are
        # derivable from this journal and are never materialized.
        if not all(self.journal(base,i) is not None for i in base.get('per_assignment',[]) if train_witness(i)):
            raise ValueError('unfinished witness journal')
        self.retry_pairs.discard(base['pair_id'])
        self.counts['pairs_done']+=1

    def prepare(self):
        cursor=self.base.execute('SELECT pair_id,source_sha256,code_sha256,config_sha256,result_sha256,'
                                 'record_json FROM pairs ORDER BY rowid')
        for done,row in enumerate(cursor,1):
            if STOP:return False
            base=valid_base(row);self.base_hashes[base['pair_id']]=row[4];items=[i for i in base.get('per_assignment',[]) if train_witness(i)]
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
                    self.work.append((base['pair_id'],corpus,base['task']+'/'+src['file'],src['line']))
                    self.counts['pairs_queued']+=1
                else:self.finish_pair(base)
            self.progress('stored',done,self.total)
        self.progress('stored',self.total,self.total,True)
        return True

    def get_base(self,pair):
        row=self.base.execute('SELECT pair_id,source_sha256,code_sha256,config_sha256,'
            'result_sha256,record_json FROM pairs WHERE pair_id=?',(pair,)).fetchone()
        value=valid_base(row);self.base_hashes[pair]=row[4];return value

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
                    check_start=time.monotonic()
                    result=self.checker.check(record,item,native_base=Path(base['source']['corpus']).resolve()/base['task'],
                                              ntrain=ntrain,ntest=ntest)
                    self.counts['check_seconds']+=round(time.monotonic()-check_start,6)
                    result['task_receipt']=task_receipt
                except Exception as exc:
                    result=dict(schema='mech-witness-test-v1',test_verified=None,status='unknown',reason=str(exc),
                                error_type=type(exc).__name__,origin='test preparation unavailable',evaluations=0)
            self.guard()
            save_start=time.monotonic()
            self.save_check(base,item,result)
            self.counts['save_seconds']+=round(time.monotonic()-save_start,6)
            self.counts['new_'+('true' if result['test_verified'] is True else
                               'false' if result['test_verified'] is False else 'unknown')]+=1
        self.finish_pair(base)
        return True

    def evaluate(self):
        # One sequential gzip scan per source; never decompress from the start
        # separately for every selected pair. Only queued lines are JSON-decoded.
        work=sorted(self.work,key=lambda row:(row[1],row[2],row[3],row[0]))
        self.phase='missing-tests';self.phase_start=time.monotonic()
        from source_read import SourceReader
        sources=SourceReader(self.ev.run.parent.parent if hasattr(self, 'ev') else CODE_ROOT)
        try:
            for done,(pair,corpus,filename,wanted) in enumerate(work,1):
                if STOP:return False
                row=self.base.execute('SELECT record_json FROM pairs WHERE pair_id=?',(pair,)).fetchone()
                failed=None;last_record=None
                try:last_record=sources.record(json.loads(row[0]))
                except (OSError,EOFError,ValueError,KeyError,StopIteration) as exc:failed=exc
                if not self.evaluate_pair(pair,last_record,failed):return False
                self.progress('missing-tests',done,len(work))
            self.progress('missing-tests',len(work),len(work),True)
            return True
        finally:sources.close()

    def summary(self,complete):
        # Only transient own-work statistics. Grade counts belong to analysis.
        summary=dict(step=2,complete=complete,total=self.total,counters=dict(self.counts),
            new_witness_applications=self.checker.evaluations,new_gold_replays=self.checker.gold_replays,
            binding_cache_hits=self.checker.binding_hits,target_cache_hits=self.checker.target_hits,
            base=str(self.args.base.resolve()),output=str(self.args.output.resolve()),
            code_sha256=self.store.code,config_sha256=self.store.config_hash,
            elapsed_seconds=time.monotonic()-self.start)
        print(json.dumps(summary,sort_keys=True),file=sys.stderr,flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=DATA_ROOT / 'ast/run/mech/labels.sqlite3')
    ap.add_argument('--output',type=Path,default=DATA_ROOT / 'ast/run/mech/settled.sqlite3')
    ap.add_argument('--summary',type=Path,default=DATA_ROOT / 'ast/run/mech/step2-summary.json')
    ap.add_argument('--reuse-completed-booleans',action='store_true',help='compatibility option: input-bound completed results are always reused')
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
    if not args.output.exists():ap.error('existing witness journal is required')
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
    import inspect
    point_method=getattr(type(ev),'gold_point_body',None)
    if point_method is None:
        ev.close();ap.error('merge the shared gold point BODY acquisition before restarting')
    point_source=inspect.getsource(point_method)
    if 'legacy.parse(gold.sexp())' in point_source or "legacy.parse(record['gold_sexp'])" in point_source:
        ev.close();ap.error('merge n-eval full-program parity repair before restarting witness checks')
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
