#!/usr/bin/env python3
"""Step 4: fits/extension split with shared whole-program TEST replay.

Reuses stored TRAIN fit and reader tables. Missing TEST evidence is acquired
through the shared evaluator, using fresh full gold replay as the authority.
"""
import argparse
import concurrent.futures
from collections import Counter
import fcntl
import gzip
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import signal
import queue
from types import SimpleNamespace
import sqlite3
import sys
import time

sys.dont_write_bytecode=True
if __package__:
    from .common import CODE_ROOT,DATA_ROOT,OUTPUT_ROOT,HERE,canonical,digest
    from .fit_contract import stored_program_fit
    from .observations import original_groups,compare_readers
    from .reader_projection import pair_readers
    from .store import Store,GoldCache
else:
    from common import CODE_ROOT,DATA_ROOT,OUTPUT_ROOT,HERE,canonical,digest
    from fit_contract import stored_program_fit
    from observations import original_groups,compare_readers
    from reader_projection import pair_readers
    from store import Store,GoldCache
from mech.step2_check import valid_base
from mech.run import pair_key

STOP=False


def stop(*_):
    global STOP
    STOP=True


def retry_reader(args,existing):
    if existing is None or existing.get('read_difference') is not None:return False
    if args.retry_reader_unknown:return True
    problem=existing.get('reader_problem',{})
    reason=problem.get('reason') if isinstance(problem,dict) else problem
    return reason in args.retry_reader_reason


def retry_test(args,existing):
    if existing is None or existing.get('fits_test') is not None:return False
    if args.retry_test_unknown:return True
    problem=existing.get('test_problem')
    text=problem if isinstance(problem,str) else canonical(problem)
    return any(reason in text for reason in args.retry_test_reason)


class Worker:
    def __init__(self,args,events=None,worker_id=0,stop_event=None,*,config=None,artifacts=None,streaming=False):
        from evaluator import ReplayEvaluator
        from tables import TargetStore,comparison_type
        from nonrender_metadata import MetadataProducer
        import importlib.util
        self.args=args;self.start=time.monotonic();self.last=0;self.counts=Counter();self.reader_counts=Counter()
        self.events=events;self.worker_id=worker_id;self.stop_event=stop_event
        self.tasks={};self.current=None;self.producer=None;self.producer_class=MetadataProducer;self.group_cache={};self.reader_cache={}
        config_path=Path(config).resolve() if config is not None else DATA_ROOT/'ast/run/corpus-v12-body-full/run.json'
        self.cfg=json.loads(config_path.read_text())
        self.ev=ReplayEvaluator(run=CODE_ROOT/'ast/run',config=config_path,deadline=args.deadline,
            artifacts=artifacts if artifacts is not None else DATA_ROOT/'judgetool/mech3-fit-replays',
            reference=CODE_ROOT/'ref/progsynth-relabel')
        self.legacy=self.ev.legacy;self.settings=self.ev.settings
        self.gold_task=None
        self.context=SimpleNamespace(arclog=self.legacy.arclog,legacy=self.legacy,settings=self.settings)
        self.native=TargetStore(self.legacy,CODE_ROOT)
        binary=Path(importlib.util.find_spec('arclog.arclog').origin).resolve()
        files=list(HERE.glob('*.py'))
        files.extend(CODE_ROOT/p for p in ('study_paths.py','ast/run/mech/algorithm.py','ast/run/mech/run.py',
            'ast/run/mech/step2_check.py','ast/run/mech/witness_test.py','ast/run/mech/grades.py',
            'ast/run/mech/read_grades.py','ast/run/mech/source_read.py','ast/run/mech/source_bindings.py',
            'judge3/framed_jsonl.py','ast/run/next_revision/family_recovery.py',
            'ast/run/filters.py','ast/run/native_tables.py','ast/run/native_storage.py','ast/run/recovery.py',
            'judgetool/evaluator.py','judgetool/tables.py','judgetool/raw_body.py',
            'judge3/nonrender_metadata.py','judge3/definition_binding.py','judge3/render_pair.py','judge3/catalog.py',
            'judge2/render2/headers.py','judge2/render2/body.py','judge2/render2/column_paths.py',
            'judge2/render2/structured.py','ref/progsynth-relabel/engine_verify.py',
            'ref/progsynth-relabel/verify_recovery.py'))
        files.extend((CODE_ROOT/'judgetool').glob('*.py'))
        files.append(binary)
        self.manifest={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        config=dict(schema='mech3-step4-config-v1',base=str(args.base.resolve()),compare_seconds=args.compare_seconds,
            source_config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
            scope='base label fits, nonDET; per-reader joint projections',
            program_fit='stored TRAIN+TEST proof first; missing TEST uses shared whole mutant and full gold OUT replay',
            runtime=dict(python=str(Path(sys.executable).resolve()),binary=str(binary)),deadline=args.deadline)
        self.output=Store(args.output,self.manifest,config)
        self.gold_cache=GoldCache(self.output)
        self.base=sqlite3.connect(args.base.resolve().as_uri()+'?mode=ro',uri=True)
        if not streaming:self.base.execute('BEGIN')
        self.scope="(json_extract(record_json,'$.label')='fits' AND upper(json_extract(record_json,'$.kind'))!='DET')"
        self.scope_params=getattr(args,'task_ids',[])
        if self.scope_params:self.scope+=' AND json_extract(record_json,\'$.task\') IN ('+','.join('?' for _ in self.scope_params)+')'
        self.total=0 if streaming else self.base.execute('SELECT count(*) FROM pairs WHERE '+self.scope,self.scope_params).fetchone()[0]

    def task(self,task):
        if task not in self.tasks:
            path=(Path(self.cfg['tasks']).resolve()/(task+'.json')).resolve();raw=path.read_bytes();data=json.loads(raw)
            self.tasks[task]=(len(data['train']),len(data['test']),dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest()))
        return self.tasks[task]

    def metadata(self,record,corpus):
        # Metadata only: no replay or attribution of a mutant to the gold
        # source stream. The shared producer owns each side's native binding.
        if self.current!=(record['task'],str(corpus)):
            self.native.cache.clear();self.group_cache.clear();self.reader_cache.clear();self.current=(record['task'],str(corpus))
            self.producer=self.producer_class(engine=self.legacy.arclog,
                read_native=lambda ref,base:self.snapshot(ref,base)['_native_reader'],
                corpus=corpus,settings=self.settings,case_inventory=dict(cases=[]))
        program_record=dict(record)
        program_record.setdefault('programs',{s:record[s+'_sexp'] for s in ('gold','mutant')})
        exports={s:self.producer.programs.load(record[s+'_sexp'],program_record if s=='gold' else None,
                    mutant_record=program_record if s=='mutant' else None)[1]
                 for s in ('gold','mutant')}
        kind=next(v['kind'] for v in exports['gold']['body_views'] if v['body_path']==record['point'])
        if kind.casefold()=='det':raise ValueError('DET uses the separate table-only target pass')
        adapter=self.producer.produce(record,native_base=corpus/record['task'])
        bindings=adapter['bindings'];policies=adapter['policies']
        if any(binding['body_path']!=record['point'] for binding in bindings.values()):
            raise ValueError('canonical metadata selected a different BODY path')
        projection=pair_readers(record,exports,bindings,side_cache=self.reader_cache)
        projection['metadata_policies']=policies
        projection['source_selectors']={s:bindings[s]['native_selector'] for s in bindings}
        projection['graph_binding']='judge3.definition_binding.definition_node; same-export ids only'
        return projection

    def process(self,base,record,existing=None):
        if digest(record)!=base['source_sha256'] or digest(pair_key(record))!=base['pair_id']:
            raise ValueError('fresh source differs from base receipt')
        ntrain,ntest,task_receipt=self.task(base['task'])
        program=stored_program_fit(record,ntrain,ntest)
        value=dict(pair_id=base['pair_id'],source_sha256=base['source_sha256'],
            base_result_sha256=digest(base),program=program,task_receipt=task_receipt,kind=base['kind'],
            reader_difference=dict(read_difference=None),evaluations=0)
        # A missing reader tuple cannot produce this pass's usable evidence.
        # Resolve it before requesting any native TEST replay.
        try:
            if existing is not None and type(existing.get('read_difference')) is bool and not self.args.rerun_reader:
                value['reader_difference']=dict(read_difference=existing['read_difference'])
            else:
                value['reader_difference']=self.reader_check(base,record,ntrain,ntest)
        except (self.legacy.arclog.Refusal,OSError,ValueError,KeyError,IndexError,TypeError) as error:
            value['reader_difference'].update(reason=str(error),error_type=type(error).__name__)
            return value
        if value['reader_difference']['read_difference'] is None:return value
        force_test=self.args.rerun_test or retry_test(self.args,existing)
        if program['fits_test'] is None:
            from out_fit import check
            if self.gold_task!=record['task']:
                self.gold_cache.clear();self.gold_task=record['task']
            key=digest(dict(schema='mech3-program-test-cache-v1',source=base['source_sha256'],base=digest(base),
                task=task_receipt,deadline=self.args.deadline,ntrain=ntrain,ntest=ntest))
            tested=None if force_test else self.output.load_program(base['pair_id'],key)
            if tested is None and not force_test:tested=self.output.compatible_program(base['pair_id'],base['source_sha256'],self.ev.receipt,task_receipt)
            if tested is None:
                tested=check(self.ev,record,ntrain=ntrain,ntest=ntest,gold_cache=self.gold_cache)
                self.output.save_program(base['pair_id'],key,tested)
                counts=tested.get('evaluations',{})
                value['evaluations']=sum(counts.values()) if isinstance(counts,dict) else counts
            if tested.get('complete') is True:program['fits_test']=tested.get('fits_test')
        return value

    def reader_check(self,base,record,ntrain,ntest):
        corpus=Path(base['source']['corpus']).resolve();projection=self.metadata(record,corpus)
        if not projection['readers']:
            read=dict(read_difference=False)
        else:
            groups={side:self.original_groups(record,side,corpus,ntrain,ntest,projection['source_selectors'][side])
                    for side in ('gold','mutant')}
            read=compare_readers(projection,groups,self.legacy,seconds=self.args.compare_seconds)
        return read


    def snapshot(self,ref,base):
        key=(str(Path(base).resolve()),str(ref))
        value=self.native.snapshot(ref,base)
        self.native.cache.pop(key,None);self.native.cache[key]=value
        while len(self.native.cache)>4:self.native.cache.pop(next(iter(self.native.cache)))
        return value

    def original_groups(self,record,side,corpus,ntrain,ntest,selector):
        key=digest(dict(side=side,reference=record['native'][side],base=str(corpus/record['task']),
            table=record['evaluation']['table_indices'][side+'_kept'],kept=record['evaluation']['kept_assignments'],
            ntrain=ntrain,ntest=ntest,selector=selector))
        if key not in self.group_cache:
            self.group_cache[key]=original_groups(record,side,self.snapshot(record['native'][side],corpus/record['task']),
                ntrain,ntest,self.legacy,selector)
            while len(self.group_cache)>8:self.group_cache.pop(next(iter(self.group_cache)))
        return self.group_cache[key]

    def progress(self,done):
        self.scanned=done
        elapsed=time.monotonic()-self.start
        if elapsed-self.last>=5:
            if self.events is not None:
                self.events.put((self.worker_id,done,dict(self.counts)));self.last=elapsed;return
            rate=done/max(elapsed,.001)
            print(f'done={done}/{self.total} elapsed={elapsed:.1f}s rate={rate:.2f}/s '
                  f'ETA={(self.total-done)/max(rate,.001):.1f}s counts={dict(self.counts)}',
                  file=sys.stderr,flush=True)
            self.last=elapsed

    def run(self):
        rows=self.base.execute("SELECT pair_id,source_sha256,code_sha256,config_sha256,result_sha256,record_json FROM pairs "
            'WHERE '+self.scope+" ORDER BY json_extract(record_json,'$.task'),"
            "json_extract(record_json,'$.source.corpus'),json_extract(record_json,'$.source.file'),json_extract(record_json,'$.source.line')",self.scope_params)
        from source_read import SourceReader
        sources=SourceReader(CODE_ROOT)
        stream=None;path=None;line_number=0;record=None;failed=None
        try:
            for done,row in enumerate(rows,1):
                if STOP or (self.stop_event is not None and self.stop_event.is_set()):return False
                base=valid_base(row)
                ntrain,ntest,task_receipt=self.task(base['task'])
                existing=self.output.load(base['pair_id'],base['source_sha256'],row[4],task_receipt['sha256'])
                reader_retry=retry_reader(self.args,existing)
                retry=(self.args.rerun_reader or self.args.rerun_test or reader_retry or
                       retry_test(self.args,existing))
                if reader_retry:self.counts['reader_retries']+=1
                saved=None if retry else existing
                if saved is not None:
                    value=saved;self.counts['resumed']+=1
                else:
                    failed=None
                    try:record=sources.record(base)
                    except (OSError,ValueError,KeyError,StopIteration) as error:failed=error
                    try:
                        if failed:raise failed
                        value=self.process(base,record,existing)
                    except (self.legacy.arclog.Refusal,OSError,ValueError,KeyError,IndexError,TypeError) as error:
                        value=dict(schema='mech3-step4-record-v1',pair_id=base['pair_id'],source_sha256=base['source_sha256'],
                            base_result_sha256=row[4],
                            status='unavailable',task_receipt=task_receipt,evaluations=0,kind=base['kind'],
                            program=dict(complete=False,fits_train=None,fits_test=None),
                            reader_difference=dict(complete=False,read_difference=None,reason=str(error)),
                            missing_steps=['step_4_source_or_adapter'],reason=str(error))
                    value=self.output.save(value);self.counts['writes']+=1
                self.counts['evaluations']+=value.get('evaluations',0) if saved is None else 0
                read=value.get('read_difference',value.get('reader_difference',{}).get('read_difference'))
                test=value.get('fits_test',value.get('program',{}).get('fits_test'))
                self.counts['read_difference:'+str(read)]+=1
                self.counts['test_fit:'+str(test)]+=1
                self.progress(done)
            return True
        finally:
            sources.close()
            if stream is not None:stream.close()

    def finish(self):
        elapsed=time.monotonic()-self.start
        if self.events is not None:
            self.events.put((self.worker_id,getattr(self,'scanned',0),dict(self.counts)));return
        print(f"done={getattr(self,'scanned',0)}/{self.total} elapsed={elapsed:.1f}s counts={dict(self.counts)}",file=sys.stderr,flush=True)


def run_shard(args,tasks,index,events,stop_event):
    # Native sessions/globals are isolated by process. Total CPU entitlement is
    # shared between workers instead of multiplying native thread pools.
    threads=str(max(1,int(os.environ.get('ARC_HEAVY_CPUS',args.workers))//args.workers))
    for name in ('ARCLOG_THREADS','RAYON_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
        os.environ[name]=threads
    args.task_ids=tasks
    worker=Worker(args,events,index,stop_event)
    try:
        complete=worker.run();worker.finish();return complete
    finally:worker.ev.close();worker.output.close();worker.base.close()


def parallel(args):
    db=sqlite3.connect(args.base.resolve().as_uri()+'?mode=ro',uri=True)
    try:
        tasks=db.execute("SELECT json_extract(record_json,'$.task'),count(*) FROM pairs WHERE "
            "json_extract(record_json,'$.label')='fits' AND upper(json_extract(record_json,'$.kind'))!='DET' GROUP BY 1 ORDER BY 2 DESC").fetchall()
    finally:db.close()
    count=min(args.workers,len(tasks));shards=[[] for _ in range(count)];loads=[0]*count
    for task,size in tasks:
        index=min(range(count),key=lambda i:loads[i]);shards[index].append(task);loads[index]+=size
    if not count:return True
    context=multiprocessing.get_context('spawn');start=time.monotonic();total=sum(loads)
    with context.Manager() as manager:
        events=manager.Queue();stop_event=manager.Event();latest={};last=0
        with concurrent.futures.ProcessPoolExecutor(max_workers=count,mp_context=context) as pool:
            futures=[pool.submit(run_shard,args,tasks,i,events,stop_event) for i,tasks in enumerate(shards)]
            while any(not f.done() for f in futures):
                if STOP:stop_event.set()
                try:
                    i,done,counts=events.get(timeout=5);latest[i]=(done,counts)
                except queue.Empty:pass
                for f in futures:
                    if f.done() and f.exception() is not None:
                        stop_event.set();raise f.exception()
                elapsed=time.monotonic()-start
                if elapsed-last>=5:
                    done=sum(v[0] for v in latest.values());counts=Counter()
                    for _,values in latest.values():counts.update(values)
                    rate=done/max(elapsed,.001)
                    print(f'done={done}/{total} elapsed={elapsed:.1f}s rate={rate:.2f}/s ETA={(total-done)/max(rate,.001):.1f}s workers={count} counts={dict(counts)}',file=sys.stderr,flush=True);last=elapsed
            complete=all(f.result() for f in futures)
            # A successful shard enqueues its final progress before returning.
            # Drain without relying on Queue.empty() as a synchronization rule.
            while True:
                try:i,done,counts=events.get_nowait();latest[i]=(done,counts)
                except queue.Empty:break
            done=sum(v[0] for v in latest.values());counts=Counter()
            for _,values in latest.values():counts.update(values)
            elapsed=time.monotonic()-start;rate=done/max(elapsed,.001)
            print(f'done={done}/{total} elapsed={elapsed:.1f}s rate={rate:.2f}/s ETA={(total-done)/max(rate,.001):.1f}s workers={count} counts={dict(counts)}',file=sys.stderr,flush=True)
            return complete


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=DATA_ROOT/'ast/run/mech/labels.sqlite3')
    ap.add_argument('--output',type=Path,default=OUTPUT_ROOT/'step4.sqlite3')
    ap.add_argument('--summary',type=Path,help='deprecated; no derived summary is written')
    ap.add_argument('--compare-seconds',type=float,default=1)
    ap.add_argument('--deadline',type=float,default=30)
    ap.add_argument('--workers',type=int,default=1)
    ap.add_argument('--retry-reader-unknown',action='store_true',help='explicitly retry unresolved reader facts only')
    ap.add_argument('--retry-reader-reason',action='append',default=[],help='retry unresolved reader facts with this exact stored problem reason; repeatable')
    ap.add_argument('--retry-test-unknown',action='store_true',help='explicitly retry unresolved TEST facts only')
    ap.add_argument('--retry-test-reason',action='append',default=[],help='retry unresolved TEST facts whose stored problem contains this text; repeatable')
    ap.add_argument('--rerun-reader',action='store_true',help='explicit reader-policy invalidation')
    ap.add_argument('--rerun-test',action='store_true',help='explicit TEST-policy invalidation')
    args=ap.parse_args()
    if args.compare_seconds<=0:ap.error('positive comparison bound required')
    if args.deadline<=0:ap.error('positive replay deadline required')
    if args.workers<1:ap.error('positive worker count required')
    if args.base.resolve()==args.output.resolve():ap.error('base must remain read-only')
    if not args.output.resolve().is_relative_to(OUTPUT_ROOT.resolve()):ap.error('outputs must stay under mech3 data root')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    lock=args.output.with_suffix('.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    os.environ['STUDY_RUN']=str(CODE_ROOT/'ast/run')
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    worker=None
    try:
        if args.workers>1:complete=parallel(args)
        else:
            worker=Worker(args);complete=worker.run();worker.finish()
    finally:
        if worker is not None:worker.ev.close();worker.output.close();worker.base.close()
        lock.close()
    if not complete:raise SystemExit(130)


if __name__=='__main__':main()
