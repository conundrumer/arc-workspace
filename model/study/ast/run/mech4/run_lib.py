#!/usr/bin/env python3
"""Resumable G-only library pass; canonical native screening AND verification."""
from common import *
import argparse
from collections import Counter
import fcntl
import gzip
import itertools
import signal
import time
from budget import Budget,Bound,ReplayProxy
from context import Contexts,require_axes
from planner import atomic,combined
from screen import execute
from read_grades import load_grade
from clause_evidence import clause_evidence

STOP=False


def stop(*_):
    global STOP
    STOP=True


class Sources:
    """One forward scan per sorted gzip source; no per-pair decompression."""
    def __init__(self):self.path=None;self.stream=None;self.line=0;self.record=None
    def get(self,job):
        locator=job['source'];path=Path(locator['corpus'])/locator['file'];line=locator['line']
        if self.path!=path or line<self.line:
            self.close();self.stream=gzip.open(path,'rt');self.path=path;self.line=0
        while self.line<line:
            raw=next(self.stream);self.line+=1
            if self.line==line:self.record=json.loads(raw)
        record=self.record
        if digest(record)!=job['source_sha256'] or digest(pair_key(record))!=job['pair_id']:
            raise ValueError('current source record differs from immutable base receipt')
        return record
    def close(self):
        if self.stream:self.stream.close()
        self.path=None;self.stream=None;self.line=0;self.record=None


class Worker:
    def __init__(self,args):
        self.a=args;self.counts=Counter();self.started=time.monotonic();self.last=0;self.task=None
        # Fail before any execution when required shared source is unmerged.
        import registry_plan
        if not all(callable(getattr(registry_plan,n,None)) for n in ('registry_atoms','available_atoms')):
            raise RuntimeError('merge n-mech registry_atoms + available_atoms patches before running (DATA_ROOT/ast/run/mech4/patches/)')
        from nonrender_metadata import MetadataProducer
        from case_collector import acquire_case,select_pair,evaluate_cached,clear_cache
        from evaluator import ReplayEvaluator
        import inspect
        import importlib.util
        if 'retain_forms' not in inspect.signature(ReplayEvaluator.replay_program).parameters:
            raise RuntimeError('merge shared evaluator retain_forms support before running')
        self.files=manifest()
        binary=Path(importlib.util.find_spec('arclog.arclog').origin).resolve()
        self.files[str(binary)]=hashlib.sha256(binary.read_bytes()).hexdigest()
        # A configuration owns its artifact directory. A later version cannot
        # overwrite the native artifacts backing an earlier durable record.
        artifact_scope=digest(dict(code=digest(self.files),runtime=self.files[str(binary)],
            arguments={k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items() if k!='limit'}))
        artifacts=OUTPUT/'artifacts'/artifact_scope
        self.screen_ev=ReplayEvaluator(run=CODE_ROOT/'ast/run',deadline=args.native_seconds,
            artifacts=artifacts/'train')
        self.verify_ev=ReplayEvaluator(run=CODE_ROOT/'ast/run',deadline=args.verify_seconds,
            artifacts=artifacts/'verify')
        self.gold_ev=ReplayEvaluator(run=CODE_ROOT/'ast/run',deadline=args.gold_seconds,
            artifacts=artifacts/'gold')
        self.config=dict(schema='mech4-config-v1',target='G',pair_seconds=args.pair_seconds,
            max_native_calls=args.max_native_calls,batch_size=args.batch_size,max_atomic=args.max_atomic,
            max_combined=args.max_combined,per_predicate=args.per_predicate,per_mode=args.per_mode,
            max_useful=args.max_useful,max_projections=args.max_projections,compare_seconds=args.compare_seconds,
            max_verify_replays=args.max_verify_replays,case_cache_entries=args.case_cache_entries,artifact_scope=artifact_scope,
            min_free_gb=args.min_free_gb,
            screen_evaluator=self.screen_ev.receipt,verification_evaluator=self.verify_ev.receipt,
            gold_evaluator=self.gold_ev.receipt,scope='G only; no other-target admission',
            coverage='finite one-computation/two-restriction layer; never full-space negative')
        from disk_guard import DiskGuard
        disk=DiskGuard(args.output.parent,min_free_gb=args.min_free_gb);disk.resume()
        self.guard=Guard(self.files,disk=disk)
        self.journal=Journal(args.output,digest(self.files),digest(self.config))
        queue=self.journal.db.execute('SELECT payload FROM metadata WHERE key=?',('queue',)).fetchone()
        if not queue or json.loads(queue[0]).get('ready') is not True:raise ValueError('run prepare.py first; queue snapshot is not ready')
        self.queue_meta=json.loads(queue[0]);self.base=readonly(self.queue_meta['base']);self.sources=Sources()
        self.contexts=Contexts(self.screen_ev,self.gold_ev,self.journal,self.config,self.guard)

    def report(self,done,total,phase='pairs',force=False):
        elapsed=time.monotonic()-self.started
        if force or elapsed-self.last>=5:
            rate=done/max(elapsed,.001);eta=f'{(total-done)/rate:.1f}s' if rate else 'unknown'
            print(f'phase={phase} done={done}/{total} elapsed={elapsed:.1f}s rate={rate:.3f}/s ETA={eta} '
                  f'absent_normal={self.queue_meta["summary"].get("normal_excluded",0)+self.counts["normal_excluded"]} '
                  f'counts={dict(self.counts)} gold={dict(self.contexts.stats)}',file=sys.stderr,flush=True)
            self.last=elapsed

    def verify(self,record,job,context,candidate,columns,inputs,budget):
        from case_collector import evaluate_cached
        checked_candidate=dict(candidate,columns=columns)
        key=digest(dict(pair=job['pair_id'],candidate=checked_candidate))
        raw=self.journal.get('candidate',key,dict(inputs,candidate=checked_candidate))
        if raw is None:
            self.guard.check();require_axes(context['selection'],record,context['ntrain'],context['ntest'])
            target=dict(adapter=context['adapter'],source=dict(source_sha256=job['source_sha256']),
                        mode='recovery',target_id='G',ntrain=context['ntrain'],ntest=context['ntest'])
            raw=evaluate_cached(ReplayProxy(self.verify_ev,budget),record,candidate['clause'],target,columns,
                context['selection'],row_limit=0,max_mutant_replays=self.config['max_verify_replays'])
            self.guard.check();self.journal.put('candidate',key,dict(inputs,candidate=checked_candidate),raw)
            self.counts['candidate_checks']+=1
        else:self.counts['candidate_checks_resumed']+=1
        ref=self.journal.ref('candidate',key,raw)
        proof=clause_evidence(raw,record,ref,ntrain=context['ntrain'],ntest=context['ntest'])
        # Checked candidates in this pass may succeed ONLY against G. A later
        # target's result is not silently imported ahead of step 3.
        if raw.get('target_id')!='G':proof=dict(proof,outcome='unknown',reason='out-of-scope target')
        return proof,ref

    def process(self,job,base):
        record=self.sources.get(job)
        context=self.contexts.acquire(record,job)
        info=self.screen_ev.registry_interfaces(record)
        if info.get('source_sha256')!=job['source_sha256']:raise ValueError('registry source binding differs')
        registry_inputs=dict(registry_sha256=info['registry_sha256'],runtime=info['runtime'])
        registry=dict(registry=info['registry'],entries=info['entries'])
        if self.journal.get('registry',info['registry_sha256'],registry_inputs) is None:
            self.journal.put('registry',info['registry_sha256'],registry_inputs,registry)
        registry_ref=self.journal.ref('registry',info['registry_sha256'],registry)
        inputs=dict(pair_id=job['pair_id'],source_sha256=job['source_sha256'],
            base_result_sha256=job['base_result_ref']['result_sha256'],adapter_sha256=digest(context['adapter']),
            gold_ref=context['gold_ref'],registry_ref=registry_ref,task_receipt=context['task_receipt'])
        context_record=dict(adapter=context['adapter'],source_sha256=job['source_sha256'],
                            available_binding_gaps=context['available_binding_gaps'],gold_ref=context['gold_ref'])
        context_key=digest(dict(pair=job['pair_id'],adapter=inputs['adapter_sha256']))
        if self.journal.get('context',context_key,inputs) is None:self.journal.put('context',context_key,inputs,context_record)
        inputs['context_ref']=self.journal.ref('context',context_key,context_record)
        scope=digest(dict(inputs=inputs,code=self.journal.code,config=self.journal.config))
        budget=Budget(self.journal,job['pair_id'],scope,self.config,lambda:STOP,self.guard.check)
        result=dict(schema='mech4-lib-result-v1',pair_id=job['pair_id'],source_sha256=job['source_sha256'],
            target_id='G',source=job['source'],base_result_ref=job['base_result_ref'],
            admission_authenticated=False,queue_hint=job['hint'],inputs=inputs,scope='G only',
            mechanical_clauses=[],candidates=[],screens=[],found_recovery=False,search_status='bound_unknown',
            full_space_covered=False,plan_exhausted=False,uncovered=['other targets','multiple computed libs',
                'deeper conjunctions','unions','structured/polymorphic registry sites','unvisited registry groundings'])
        useful=[];seen=set();staged=[];atomic_count=0;combined_count=0;unsupported=0
        def process_batch(batch):
            gold=context['selection']['point'][0]
            for candidate,screen,resumed in execute(self.screen_ev,record,context['adapter'],batch,gold,
                context['ntrain'],context['ntest'],self.config,budget,self.journal,inputs,self.guard):
                self.counts['screens_resumed' if resumed else 'screens']+=1
                key=digest(dict(pair=job['pair_id'],candidate=candidate['candidate_id']))
                result['screens'].append(self.journal.ref('screen',key,screen))
                if screen.get('useful'):
                    useful.append((screen.get('rank',0),candidate['candidate_id'],candidate))
                    # Keep selector/computation beams separately. A selector
                    # need not contain G BEFORE the computation maps columns.
                    useful.sort(key=lambda item:(item[0],item[1]))
                    selectors=[x for x in useful if not x[2]['computed_fields']][:self.config['max_useful']]
                    computations=[x for x in useful if x[2]['computed_fields']][:self.config['max_useful']]
                    useful[:]=selectors+computations
                if screen.get('status')=='train_match':
                    proof,ref=self.verify(record,job,context,candidate,screen['columns'],inputs,budget)
                    result['mechanical_clauses'].append(proof);result['candidates'].append(ref)
                    if proof['outcome']=='recovery verified':
                        result.update(found_recovery=True,search_status='recovery_verified')
                        return True
            return False
        start=time.monotonic()
        try:
            generated=atomic(self.screen_ev.legacy,info,context['adapter'],maximum=self.config['max_atomic'],
                per_predicate=self.config['per_predicate'],per_mode=self.config['per_mode'],bindings=context['available_bindings'])
            for candidate in generated:
                budget.check()
                if candidate['kind']=='unsupported':unsupported+=1;continue
                atomic_count+=1
                if candidate['candidate_id'] in seen:continue
                seen.add(candidate['candidate_id']);staged.append(candidate)
                if len(staged)>=self.config['batch_size']:
                    if process_batch(staged):break
                    staged=[]
            else:
                if staged:process_batch(staged)
            if not result['found_recovery']:
                staged=[]
                for candidate in combined(self.screen_ev.legacy,context['adapter'],[item[2] for item in useful],
                                          maximum=self.config['max_combined']):
                    budget.check();combined_count+=1
                    if candidate['candidate_id'] in seen:continue
                    seen.add(candidate['candidate_id']);staged.append(candidate)
                    if len(staged)>=self.config['batch_size']:
                        if process_batch(staged):break
                        staged=[]
                else:
                    if staged:process_batch(staged)
                result['plan_exhausted']=not result['found_recovery']
            result['reason']='verified G recovery' if result['found_recovery'] else 'finite plan visited; settled space remains uncovered'
        except Bound as error:
            result['reason']=str(error);result['interrupted']=STOP
        result.update(native_operations=budget.ledger(),atomic_candidates=atomic_count,combined_candidates=combined_count,
            unsupported_registry_entries=unsupported,search_seconds=time.monotonic()-start,
            registry_receipt={k:v for k,v in info.items() if k not in ('registry','entries','typed_sites','readers')})
        return result

    def run(self):
        rows=self.journal.db.execute("SELECT inputs_sha256,result_sha256,payload FROM queue ORDER BY json_extract(payload,'$.task'),"
            "json_extract(payload,'$.source.corpus'),json_extract(payload,'$.source.file'),json_extract(payload,'$.source.line')").fetchall()
        total=min(len(rows),self.a.limit) if self.a.limit else len(rows)
        done=0;self.report(0,total,force=True)
        for queue_inputs_sha,queue_result_sha,payload in rows[:total]:
            if STOP:break
            job=json.loads(payload)
            queue_inputs=dict(source_sha256=job['source_sha256'],
                base_result_sha256=job['base_result_ref']['result_sha256'],hint=job['hint'])
            if digest(job)!=queue_result_sha or digest(queue_inputs)!=queue_inputs_sha:
                raise ValueError('queue source/base/result digest differs; prepare again')
            base_row=self.base.execute('SELECT pair_id,source_sha256,code_sha256,config_sha256,result_sha256,record_json '
                                      'FROM pairs WHERE pair_id=?',(job['pair_id'],)).fetchone()
            base=base_record(base_row)
            if digest(base)!=job['base_result_ref']['result_sha256']:raise ValueError('queue base result changed; prepare again')
            current=load_grade(Path(job['grade_database']),job['pair_id'])
            availability={k:v for k,v in current.items() if k!='record'}
            pair_inputs=dict(source_sha256=job['source_sha256'],base_result_sha256=digest(base),
                             availability=availability,hint=job['hint'])
            normal=normal_evidence(Path(job.get('normal_database',NORMAL_DATABASE)),job['pair_id'],
                job['source_sha256'],job['base_result_ref']['result_sha256'])
            if normal.get('normal') is not True:
                self.counts['normal_excluded']+=1
                self.counts['non_normal' if normal.get('normal') is False else 'normal_unavailable']+=1
                done+=1;self.report(done,total);continue
            pair_inputs['normal']=normal
            key=digest(dict(pair=job['pair_id'],target='G'))
            result=self.journal.get('pair',key,pair_inputs)
            if result is not None and result.get('interrupted') is not True:
                self.counts['pairs_resumed']+=1
            else:
                if self.task!=job['task']:
                    self.contexts.clear();self.screen_ev.close();self.verify_ev.close();self.task=job['task']
                self.guard.check();started=time.monotonic()
                if not queue_hint(base) or current['valid'] and current['grade']!='Unknown':
                    result=dict(schema='mech4-lib-result-v1',pair_id=job['pair_id'],target_id='G',
                        source_sha256=job['source_sha256'],source=job['source'],base_result_ref=job['base_result_ref'],
                        search_status='not_eligible_current',reason='queue hint or current grade no longer open',
                        admission_authenticated=False,found_recovery=False,mechanical_clauses=[])
                else:
                    try:result=self.process(job,base)
                    except (ValueError,KeyError,IndexError,OSError,EOFError,StopIteration,TypeError) as error:
                        result=dict(schema='mech4-lib-result-v1',pair_id=job['pair_id'],target_id='G',
                            source_sha256=job['source_sha256'],source=job['source'],base_result_ref=job['base_result_ref'],
                            search_status='unavailable',reason=str(error),error_type=type(error).__name__,
                            admission_authenticated=False,found_recovery=False,mechanical_clauses=[])
                result.update(code_sha256=self.journal.code,code_manifest=self.files,config_sha256=self.journal.config,
                    config=self.config,grade_availability=availability,normal=normal,
                    normal_database=job.get('normal_database',str(NORMAL_DATABASE)),elapsed_seconds=time.monotonic()-started)
                self.guard.check();self.journal.put('pair',key,pair_inputs,result);self.counts['pairs_written']+=1
                self.contexts.store.cache.clear()
            self.counts[result['search_status']]+=1;done+=1
            self.report(done,total)
        self.report(done,total,force=True)
        summary=dict(schema='mech4-summary-v1',scope='G only',complete=done==total and not STOP,done=done,total=total,
            queued_total=len(rows),requested_limit=self.a.limit,scope_complete=done==len(rows) and not STOP,
            counts=dict(self.counts),
            normal_excluded=self.queue_meta['summary'].get('normal_excluded',0)+self.counts['normal_excluded'],
            non_normal=self.queue_meta['summary'].get('non_normal',0)+self.counts['non_normal'],
            normal_unavailable=self.queue_meta['summary'].get('normal_unavailable',0)+self.counts['normal_unavailable'],
            preparation_normal_excluded=self.queue_meta['summary'].get('normal_excluded',0),gold=dict(self.contexts.stats),elapsed_seconds=time.monotonic()-self.started,
            database=str(self.a.output.resolve()),code_sha256=self.journal.code,config_sha256=self.journal.config,
            final_grades='owned by n-mech; this database supplies checked G candidates only')
        self.a.output.with_suffix('.summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(canonical(summary),file=sys.stderr,flush=True)
        return summary

    def close(self):
        self.sources.close();self.contexts.clear()
        self.screen_ev.close();self.verify_ev.close();self.gold_ev.close()
        self.base.close();self.journal.close()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=OUTPUT/'lib.sqlite3')
    ap.add_argument('--limit',type=int,default=0)
    ap.add_argument('--pair-seconds',type=float,default=30)
    ap.add_argument('--native-seconds',type=float,default=2)
    ap.add_argument('--verify-seconds',type=float,default=5)
    ap.add_argument('--gold-seconds',type=float,default=30)
    ap.add_argument('--compare-seconds',type=float,default=.25)
    ap.add_argument('--max-native-calls',type=int,default=24)
    ap.add_argument('--max-verify-replays',type=int,default=3)
    ap.add_argument('--batch-size',type=int,default=8)
    ap.add_argument('--max-atomic',type=int,default=256)
    ap.add_argument('--max-combined',type=int,default=96)
    ap.add_argument('--per-predicate',type=int,default=12)
    ap.add_argument('--per-mode',type=int,default=12)
    ap.add_argument('--max-useful',type=int,default=12)
    ap.add_argument('--max-projections',type=int,default=32)
    ap.add_argument('--case-cache-entries',type=int,default=2)
    ap.add_argument('--min-free-gb',type=float,default=30)
    a=ap.parse_args()
    if a.limit<0 or min(v for k,v in vars(a).items() if k not in ('output','limit'))<=0:ap.error('positive bounds required')
    if not a.output.resolve().is_relative_to(OUTPUT.resolve()):ap.error('outputs must stay under mech4 data root')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    lock=a.output.with_suffix('.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    worker=None
    try:
        worker=Worker(a);summary=worker.run()
    finally:
        if worker is not None:worker.close()
        lock.close()
    if not summary['complete']:raise SystemExit(130)


if __name__=='__main__':main()
