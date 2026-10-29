#!/usr/bin/env python3
"""All-target contribution: durable gold cases, comparisons and new witnesses.

Imports shared mechanical checking; never changes the base or settled grades. Never labels the base again, runs a baseline, or
searches main G again. New gold values come from ONE shared replay per case.
"""
import argparse
from collections import Counter
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import signal
import sqlite3
import sys
import time

from ._paths import HERE,CODE_ROOT,DATA_ROOT,DATA
from .metadata import produce
from .read_targets import load_targets,file_hash
from run import canonical,digest,pair_key
from step2_check import valid_base
from .target_store import Journal
from .target_compare import compare
from .target_search import propose,clause

STOP=False


def stop(*_):
    global STOP
    STOP=True


def selector_matches(selector,definition):
    return all(str(selector.get(k))==str(v) for k,v in definition['native_selector'].items()
               if k in ('form','point','relation','fact'))


class Pass:
    def __init__(self,args,ev):
        from tables import TargetStore
        self.a=args;self.ev=ev;self.start=time.monotonic();self.last=0;self.counts=Counter()
        self.source_store=TargetStore(ev.legacy,CODE_ROOT)
        self.base=sqlite3.connect(args.base.resolve().as_uri()+'?mode=ro',uri=True);self.base.execute('BEGIN')
        files=set(HERE/n for n in ('targets.py','target_store.py','target_compare.py','target_search.py','metadata.py',
            'read_targets.py','evidence.py','_paths.py','certificates.py','preflight.py'))
        files.update((CODE_ROOT/'judgetool').glob('*.py'))
        files.update((CODE_ROOT/'judge3').glob('*.py'))
        files.update(CODE_ROOT/'ast/run/mech3'/n for n in ('common.py','det_receipt.py','reader_projection.py'))
        files.update(CODE_ROOT/'ast/run/mech'/n for n in ('algorithm.py','step2_check.py','run.py','clause_evidence.py','outcomes.py','grades.py'))
        files.add(CODE_ROOT/'study_paths.py')
        files.update((CODE_ROOT/'judge2/render2').glob('*.py'))
        files.update(CODE_ROOT/n for n in ('judge3/nonrender_metadata.py','judge3/render_pair.py','judge3/catalog.py',
            'judge2/render2/headers.py','judge2/render2/body.py','judge2/render2/column_paths.py',
            'judge2/render2/structured.py','ast/check_stage1_all.py','ast/run/native_storage.py',
            'ast/run/native_tables.py','ast/run/filters.py','ast/run/recovery.py',
            'ast/run/next_revision/family_recovery.py','ref/progsynth-relabel/engine_verify.py',
            'ref/progsynth-relabel/verify_recovery.py','codex-adm/briefs/judge-decisions.md'))
        files.add(Path(ev.runtime['binary']))
        self.manifest={(str(p.resolve().relative_to(CODE_ROOT)) if p.resolve().is_relative_to(CODE_ROOT) else str(p.resolve())):
                       hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
        self.signatures={name:self.signature(self.code_path(name)) for name in self.manifest}
        config=dict(schema='mech-target-config-v1',base=str(args.base.resolve()),
            evaluator=ev.receipt,compare_seconds=args.compare_seconds,search_seconds=args.search_seconds,
            max_targets=args.max_search_targets,max_candidates=args.max_candidates,
            search='bounded nonlib proposals; shared TRAIN+TEST verification; no settled-space negative',
            gold='once per case/program/own-kept/settings; durable case JSON; no stored gold target rows')
        self.journal=Journal(args.output,digest(self.manifest),digest(config))
        self.journal.register(self.manifest,config)
        self.total=self.base.execute('SELECT count(*) FROM pairs').fetchone()[0]
        self.done=0
        self.producers={};self.case_cache={};self.current_task=None;self.tasks={}

    @staticmethod
    def code_path(name):
        return Path(name) if Path(name).is_absolute() else CODE_ROOT/name

    @staticmethod
    def signature(path):
        s=path.stat();return s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns

    def guard(self):
        for name,expected in self.manifest.items():
            path=self.code_path(name);sig=self.signature(path)
            if sig==self.signatures[name]:continue
            if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
                raise RuntimeError('dependency changed during step 3; restart: '+name)
            self.signatures[name]=sig

    def progress(self,done,phase='pairs',force=False):
        elapsed=time.monotonic()-self.start
        if force or elapsed-self.last>=5:
            rate=done/max(elapsed,.001);eta=(self.total-done)/rate if rate else 'unknown'
            print(f'phase={phase} done={done}/{self.total} elapsed={elapsed:.1f}s rate={rate:.2f}/s '
                  f'ETA={eta}s counters={dict(self.counts)}',file=sys.stderr,flush=True)
            self.last=elapsed

    def pair_inputs(self,base):
        return dict(pair_id=base['pair_id'],source_sha256=base['source_sha256'],base_result_sha256=digest(base))

    def save_pair(self,base,result):
        result.update(self.pair_inputs(base),schema='mech-target-pair-v1',kind=base['kind'],
            table_only=base['kind'].casefold()=='det',base_label=base.get('label'),source=base['source'],
            base_result_ref=dict(database=str(self.a.base.resolve()),pair_id=base['pair_id'],
                source_sha256=base['source_sha256'],code_sha256=base['code_sha256'],
                config_sha256=base['config_sha256'],result_sha256=digest(base)))
        positive=any(c.get('complete') is True and c.get('equal') is True for c in result.get('grade_comparisons',[]))
        recovery=any(c.get('outcome')=='recovery verified' for c in result.get('mechanical_clauses',[]))
        partial=any(c.get('outcome')=='partial source verified' for c in result.get('mechanical_clauses',[]))
        result['outcome']='equivalent' if positive else 'Recovery' if recovery else 'Partial source' if partial else 'Unknown'
        result['missing_steps']=[]
        if not result.get('complete'):result['missing_steps'].append('step_3_incomplete_target_catalog')
        if result.get('gaps'):result['missing_steps'].append('step_3_incomplete_comparison_or_search')
        if result['outcome']=='Unknown':result['missing_steps'].append('step_5_lib_or_step_6_judge_search')
        if result['outcome']!='Unknown':result['missing_steps']=[]
        self.journal.save('pair',base['pair_id'],self.pair_inputs(base),result)

    def task(self,task):
        if task in self.tasks and file_hash(self.tasks[task][2]['path'])!=self.tasks[task][2]['sha256']:
            raise RuntimeError('task inputs changed during target pass: '+task)
        if task not in self.tasks:
            path=(Path(self.ev.cfg['tasks'])/(task+'.json')).resolve();raw=path.read_bytes();value=json.loads(raw)
            self.tasks[task]=(len(value['train']),len(value['test']),dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest()))
        return self.tasks[task]

    def metadata(self,record,corpus):
        key=str(corpus)
        producer=self.producers.get(key)
        producer,adapter=produce(self.ev,self.source_store,record,corpus,producer=producer)
        self.producers[key]=producer
        return producer,adapter

    def bundles(self,record,adapter,ntrain,ntest):
        from case_collector import acquire_case
        result=[];gaps=[];references=[]
        inventory=adapter['all_case_targets']
        for case in inventory['cases']:
            context=dict(case,catalogue_path=inventory['catalogue_path'])
            source_record=case.get('source_record_data') or {}
            if source_record.get('relation_source_names') is not None:
                context['relation_source_names']=source_record['relation_source_names']
            # Use the source record's own program/kept namespace for its case.
            if case['name']==record['case']:
                context.update(gold_sexp=record['gold_sexp'],kept_assignments=record['evaluation']['kept_assignments'],
                               relation_source_names=record.get('relation_source_names'))
            text=context.get('gold_sexp') or context.get('source_program')
            kept=context.get('kept_assignments')
            if kept is None:kept=(context.get('reference') or {}).get('evaluation',{}).get('kept_assignments')
            # The metadata inventory contains a representative source record,
            # which varies with each mutant at its own case. It is NOT part of
            # a case's data identity: exclude pair/point/mutation from this key.
            inputs=dict(task=record['task'],case=case['name'],program_sha256=digest(text),
                kept_context_sha256=digest(kept),
                catalogue_sha256=inventory['catalogue_sha256'],task_inputs_sha256=self.task(record['task'])[2]['sha256'],ntrain=ntrain,ntest=ntest)
            key=digest(inputs)
            try:
                bundle=self.case_cache.get(key)
                if bundle is None:
                    bundle=self.journal.load('case',key,inputs)
                    if bundle is None:
                        self.progress(self.done,phase='gold_case:'+case['name'],force=True)
                        self.guard();bundle=acquire_case(self.ev,record,context,ntrain,ntest);self.guard()
                        self.journal.save('case',key,inputs,bundle)
                        self.counts['gold_case_replays']+=1
                    else:self.counts['gold_cases_resumed']+=1
                    self.case_cache[key]=bundle
                result.append(bundle);references.append(self.journal.reference('case',key,bundle))
            except (ValueError,KeyError,IndexError,OSError,TypeError) as error:
                gaps.append(dict(case=case['name'],reason=str(error),stage='case acquisition'))
        return result,gaps,references

    def callable_metadata(self,producer,adapter,bundles,record):
        own=[b for b in bundles if b['case']==record['case']]
        if len(own)!=1:return
        for offered in adapter['availability']['definitions']:
            definition=offered['definition']
            tables=[t for t in own[0]['tables'] if selector_matches(t['selector'],definition)]
            if len(tables)!=1:continue
            try:
                bound=producer.callable_definition(definition,tables[0]['native_schema'])
                offered['table_receipt']=dict(callable_atom=bound['callable_atom'],schema=bound['schema'])
            except (ValueError,KeyError,IndexError,TypeError):pass

    def checked_candidate(self,record,adapter,selection,candidate,inputs):
        from case_collector import evaluate_cached
        from clause_evidence import clause_evidence
        # Verification checks every cached target, so its identity is independent
        # of which target suggested the clause. Repeated proposals reuse it.
        inputs=dict(source_sha256=digest(record),adapter_sha256=digest(adapter),
                    case_refs=inputs['case_refs'],candidate=candidate,max_mutant_replays=1)
        key=digest(dict(pair=digest(pair_key(record)),inputs=inputs))
        result=self.journal.load('candidate',key,inputs)
        if adapter['input']['binding'].get('kind','').casefold()=='det':
            raise ValueError('mechanical DET candidate checker unavailable; judge DET path is excluded')
        if result is None:
            self.guard()
            target=dict(adapter=adapter,source=dict(source_sha256=digest(record)),
                ntrain=selection['ntrain'],ntest=selection['ntest'],mode='recovery')
            try:
                result=evaluate_cached(self.ev,record,candidate['clause'],target,candidate['columns'],selection,
                    row_limit=0,max_mutant_replays=1)
            except (ValueError,KeyError,IndexError,TypeError) as error:
                result=dict(outcome='unknown',reason=str(error))
            self.guard();self.journal.save('candidate',key,inputs,result)
            self.counts['candidate_mutant_replays']+=result.get('cached_case_verification',{}).get('mutant_replays',0)
        else:self.counts['candidates_resumed']+=1
        ref=self.journal.reference('candidate',key,result)
        checked=clause_evidence(result,record,ref,ntrain=selection['ntrain'],ntest=selection['ntest'])
        return checked,ref,result

    def process(self,base,record):
        from case_collector import select_pair
        self.guard()
        result=dict(schema='mech-step3-pair-v1',pair_id=base['pair_id'],source_sha256=base['source_sha256'],
            complete=False,gaps=[],grade_comparisons=[],mechanical_clauses=[],searches=[],bounded=False)
        if base.get('error') and ('edb3e4ef' in base['pair_id'] or 'native/tables.pack' in str(base['error'])):
            result['gaps'].append(dict(stage='step_7_move_retry',reason='specified failed base pair is reserved for step 7'))
            return result
        if digest(record)!=base['source_sha256'] or digest(pair_key(record))!=base['pair_id']:
            raise ValueError('current source differs from the base source receipt')
        corpus=Path(base['source']['corpus']).resolve()
        ntrain,ntest,task_receipt=self.task(record['task']);result['task_receipt']=task_receipt
        producer,adapter=self.metadata(record,corpus)
        bundles,gaps,refs=self.bundles(record,adapter,ntrain,ntest)
        self.callable_metadata(producer,adapter,bundles,record)
        selection=select_pair(bundles,record,adapter,ev=self.ev)
        selection['gaps'].extend(gaps);selection['complete']&=not gaps
        source,fields=self.source_store.mutant_input(record,adapter,ntrain,ntest)
        targets=([selection['point']] if selection['point'] is not None else [])+selection['targets']
        result.update(complete=selection['complete'],gaps=selection['gaps'],case_refs=refs,
                      adapter_sha256=digest(adapter),point_binding=adapter['comparison_target']['binding'],
                      X_binding=adapter['input']['binding'])
        comparisons=[];possible=[];computed=False
        for target in targets:
            grouped,target_fields,reference,receipt=target
            if STOP:raise InterruptedError('stopping before next target')
            self.progress(self.done,phase='target:'+reference['target_id'])
            target_key=digest(dict(reference=reference,receipt=receipt))
            inputs=dict(source_sha256=base['source_sha256'],base_result_sha256=digest(base),
                        adapter_sha256=digest(adapter),case_refs=refs,target_key=target_key)
            key=digest(dict(pair=base['pair_id'],target=target_key))
            comparison=self.journal.load('comparison',key,inputs)
            if comparison is None:
                comparison=compare(source,fields,target,seconds=self.a.compare_seconds)
                self.journal.save('comparison',key,inputs,comparison);self.counts['target_comparisons']+=1
            else:self.counts['comparisons_resumed']+=1
            proof_ref=self.journal.reference('comparison',key,comparison)
            eq=comparison['equality'];include=comparison['containment'];row=comparison['row_obstruction']
            comparisons.append((target,comparison,proof_ref))
            result['grade_comparisons'].append(dict(target_id=reference['target_id'],equal=eq['status']=='equal',
                train=eq.get('train')=='equal',test=eq.get('test')=='equal',complete=eq['status']=='equal',
                kept_contexts_complete=not source['missing'] and not grouped['missing'],
                test_target='gold_full_replay',receipt_ref=proof_ref,comparison=eq))
            if include['status']=='contains' and reference.get('role')!='point':possible.append((target,inputs))
            if include['status']=='mismatch':computed=True
            if reference.get('role')=='point':
                result['point']=dict(complete=include['status']!='unknown',
                    X_holds_every_gold_row=True if include['status']=='contains' else False if include['status']=='mismatch' else None,
                    receipt_ref=proof_ref,comparison=include)
        complete=selection['complete'] and bool(comparisons)
        result['support']=dict(complete=complete,all_targets_lossy=None,
            raw_all_targets_lack_rows=complete and all(c['containment']['status']=='mismatch' for t,c,r in comparisons),
            row_count_all_targets_branch_obstructed=complete and all(c['row_obstruction']['impossible'] is True for t,c,r in comparisons),
            any_target_contains=any(c['containment']['status']=='contains' for t,c,r in comparisons),
            requires_computed_columns=computed,negative_policy='raw/count misses are diagnostic only; computed libs and needed-row unions remain')
        if any(c['equality']['status']=='unknown' or c['containment']['status']=='unknown' for t,c,r in comparisons):
            result['gaps'].append(dict(stage='comparison',reason='missing or bounded target comparison'))
        from .certificates import no_x_rows
        result['no_recovery_certificate']=no_x_rows(source,targets,complete=complete,
            inputs=self.pair_inputs(base),case_refs=refs,ntrain=ntrain,ntest=ntest,
            assignment_count=len(record['evaluation']['kept_assignments']))
        # A native equality is already the strongest possible target outcome.
        already=any(c['equal'] and c['complete'] for c in result['grade_comparisons'])
        candidates=0
        if not already:
            for index,(target,inputs) in enumerate(possible):
                if STOP:raise InterruptedError('stopping after current durable target')
                if index>=self.a.max_search_targets or candidates>=self.a.max_candidates:
                    result['bounded']=True;break
                self.progress(self.done,phase='other_target_search')
                reference=target[2];key=digest(dict(pair=base['pair_id'],target=inputs['target_key'],phase='search'))
                search=self.journal.load('search',key,inputs)
                if search is None:
                    try:
                        proof,bindings,receipt=propose(source,fields,target,reference,selection,adapter,seconds=self.a.search_seconds)
                        search=dict(proof=proof,receipt=receipt,status='proposal' if proof.get('recoverable') else 'not_covered')
                        if proof.get('recoverable'):
                            candidate=clause(self.ev.legacy,proof,adapter['input']['binding'],bindings)
                            checked,ref,raw=self.checked_candidate(record,adapter,selection,candidate,dict(inputs,candidate=candidate))
                            search.update(checked=checked,candidate_ref=ref,candidate=candidate)
                    except (ValueError,KeyError,IndexError,TypeError) as error:
                        search=dict(status='unknown',reason=str(error))
                    self.guard();self.journal.save('search',key,inputs,search)
                    self.counts['other_target_searches']+=1
                else:self.counts['searches_resumed']+=1
                candidates+=bool(search.get('candidate_ref'))
                search_ref=self.journal.reference('search',key,search)
                result['searches'].append(search_ref)
                if search.get('proof',{}).get('reason_code')=='search_bound':result['bounded']=True
                if search.get('checked'):
                    result['mechanical_clauses'].append(search['checked'])
                    if search['checked']['outcome']=='recovery verified':already=True;break
                if search.get('status')=='unknown' or search.get('checked',{}).get('outcome')=='unknown':
                    result['gaps'].append(dict(stage='other_target_search',target_id=reference['target_id'],
                        reason=search.get('reason') or search.get('checked',{}).get('reason','candidate check unavailable')))
        result['still_possible']=not already
        result['candidates_checked']=candidates
        return result

    def run(self):
        from case_collector import clear_cache
        sql=('SELECT pair_id,source_sha256,code_sha256,config_sha256,result_sha256,record_json FROM pairs '
             "ORDER BY json_extract(record_json,'$.task'),json_extract(record_json,'$.source.corpus'),"
             "json_extract(record_json,'$.source.file'),json_extract(record_json,'$.source.line'),pair_id")
        stream=None;path=None;lineno=0;record=None;failed=None
        try:
            for done,row in enumerate(self.base.execute(sql),1):
                if STOP:return False
                base=valid_base(row);inputs=self.pair_inputs(base);self.done=done
                if self.a.task and base['task'] not in self.a.task:continue
                if self.a.limit and self.counts['pairs_done']>=self.a.limit:break
                saved=self.journal.load('pair',base['pair_id'],inputs)
                if saved is not None:
                    checked=load_targets(self.a.output,base['pair_id'],source_sha256=base['source_sha256'],base_result_sha256=digest(base))
                    if checked['valid']:
                        self.counts['pairs_resumed']+=1;self.progress(done);continue
                    self.counts['stale_pair_results']+=1
                if self.current_task!=base['task']:
                    self.ev.close();clear_cache(self.ev);self.source_store.cache.clear()
                    self.case_cache.clear();self.producers.clear();self.current_task=base['task']
                src=base['source'];current=Path(src['corpus']).resolve()/base['task']/src['file'];wanted=src['line']
                if current!=path:
                    if stream is not None:stream.close()
                    path=current;lineno=0;record=None;failed=None;stream=None
                    try:stream=gzip.open(current,'rt')
                    except OSError as error:failed=error
                if failed is None:
                    try:
                        while lineno<wanted:
                            line=next(stream);lineno+=1
                            if lineno==wanted:record=json.loads(line)
                        if lineno!=wanted:raise ValueError('source line order differs')
                    except (OSError,EOFError,StopIteration,ValueError) as error:
                        failed=ValueError(f'{path}: near line {lineno}, wanted {wanted}: {type(error).__name__}: {error}')
                try:
                    if failed:raise failed
                    result=self.process(base,record)
                except InterruptedError:return False
                except (ValueError,KeyError,IndexError,OSError,TypeError) as error:
                    result=dict(schema='mech-step3-pair-v1',pair_id=base['pair_id'],source_sha256=base['source_sha256'],
                        complete=False,gaps=[dict(stage='pair unavailable',reason=str(error),error_type=type(error).__name__)])
                    self.counts['pairs_unavailable']+=1
                self.guard();self.save_pair(base,result);self.source_store.cache.clear()
                self.counts['pairs_done']+=1;self.progress(done)
            self.progress(self.done,force=True)
            return not bool(self.a.task or self.a.limit)
        finally:
            if stream is not None:stream.close()

    def summary(self,complete):
        import zlib
        outcomes=Counter();groups=Counter();gaps=Counter()
        for payload, in self.journal.db.execute("SELECT payload FROM entries WHERE kind='pair' AND code=? AND config=?",(self.journal.code,self.journal.config)):
            value=json.loads(zlib.decompress(payload));outcomes[value['outcome']]+=1
            groups[(value.get('base_label'),value.get('kind'),value['outcome'])]+=1
            gaps.update(g.get('reason','unspecified') for g in value.get('gaps',[]))
        summary=dict(schema='mech-target-summary-v1',complete=complete,total=self.total,
            outcome_counts=dict(outcomes),by_base_label_kind=[dict(base_label=b,kind=k,outcome=o,count=n)
                for (b,k,o),n in sorted(groups.items(),key=lambda item:str(item[0]))],
            gap_counts=dict(gaps),counters=dict(self.counts),elapsed_seconds=time.monotonic()-self.start,
            code_sha256=self.journal.code,config_sha256=self.journal.config,output=str(self.a.output.resolve()),
            grade_scope='target contribution only; central reducer preserves program/reader/judge evidence')
        self.a.summary.write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps(summary,sort_keys=True),file=sys.stderr,flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=DATA_ROOT/'ast/run/mech/labels.sqlite3')
    ap.add_argument('--output',type=Path,default=DATA/'targets.sqlite3')
    ap.add_argument('--summary',type=Path,default=DATA/'summary.json')
    ap.add_argument('--deadline',type=float,default=30)
    ap.add_argument('--compare-seconds',type=float,default=1)
    ap.add_argument('--search-seconds',type=float,default=1)
    ap.add_argument('--max-search-targets',type=int,default=32)
    ap.add_argument('--max-candidates',type=int,default=16)
    ap.add_argument('--task',action='append')
    ap.add_argument('--limit',type=int)
    a=ap.parse_args()
    for path in (a.output,a.summary):
        if not path.resolve().is_relative_to(DATA):ap.error('outputs must stay under '+str(DATA))
    if a.base.resolve()==a.output.resolve():ap.error('base is read-only')
    if min(a.deadline,a.compare_seconds,a.search_seconds,a.max_search_targets,a.max_candidates)<=0:
        ap.error('bounds must be positive')
    if a.limit is not None and a.limit<=0:ap.error('--limit must be positive')
    # Shared repair capabilities must land before this driver is launched.
    from .preflight import require_shared
    require_shared()
    DATA.mkdir(parents=True,exist_ok=True)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.summary.parent.mkdir(parents=True,exist_ok=True)
    lock=a.output.with_suffix('.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    os.environ['STUDY_RUN']=str(CODE_ROOT/'ast/run')
    from evaluator import ReplayEvaluator
    ev=ReplayEvaluator(run=CODE_ROOT/'ast/run',config=DATA_ROOT/'ast/run/corpus-v11/run.json',
                       deadline=a.deadline,artifacts=DATA/'replays')
    worker=None;complete=False
    try:
        worker=Pass(a,ev);complete=worker.run();worker.guard();worker.summary(complete)
    finally:
        if worker is not None:worker.journal.close();worker.base.close()
        ev.close();lock.close()
    if STOP:raise SystemExit(130)


if __name__=='__main__':main()
