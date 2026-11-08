#!/usr/bin/env python3
"""All-target contribution: durable gold cases, comparisons and new witnesses.

Imports shared mechanical checking; never changes the base or settled grades. Never labels the base again, runs a baseline, or
searches main G again. New gold values come from ONE shared replay per case.
"""
import argparse
from collections import Counter,OrderedDict
from contextlib import contextmanager
import fcntl
import gzip
import hashlib
import inspect
import json
import os
from pathlib import Path
import signal
import sqlite3
import sys
import time

from ._paths import HERE,CODE_ROOT,DATA_ROOT,DATA
from judge3.framed_jsonl import JsonlReader
from .metadata import produce
from .fact_codec import expand_case,target_identity
from .read_targets import load_targets,file_hash
from run import canonical,digest,pair_key
from step2_check import valid_base
from .target_store import Journal
from .target_compare import compare
from .target_search import propose,clause
from .target_index import TargetIndexes
from .runtime_cache import TaskNativeStore

STOP=False


class PairUnavailable(ValueError):
    def __init__(self,result,error):
        super().__init__(str(error))
        self.result=result
        result.setdefault('gaps',[]).append(dict(stage='pair unavailable',reason=str(error),error_type=type(error).__name__))


def unavailable(facts):
    """Explicit retry scope; bounded comparisons/searches stay completed."""
    if isinstance(facts.get('stopped'),dict):return False
    return bool(facts.get('case_failure_refs') or any(g.get('stage')=='pair unavailable'
        for g in facts.get('gaps',[])))


def read_selection(path):
    """Explicit pair inputs to retry; neither code nor result hashes are keys."""
    if path is None:return None
    result={}
    with JsonlReader(path) as stream:
        for number,line in enumerate(stream.iter_lines(),1):
            if not line.strip():continue
            value=json.loads(line);pair=value['pair_id'];source=value['source_sha256']
            if any(not isinstance(v,str) or len(v)!=64 or any(c not in '0123456789abcdef' for c in v)
                   for v in (pair,source)):
                raise ValueError(f'{path}:{number}: invalid pair/source SHA256')
            if pair in result:raise ValueError(f'{path}:{number}: duplicate selected pair')
            result[pair]=source
    if not result:raise ValueError('pair input selection is empty')
    return result


def stop(*_):
    global STOP
    STOP=True


def selector_matches(selector,definition):
    return all(str(selector.get(k))==str(v) for k,v in definition['native_selector'].items()
               if k in ('form','point','relation','fact'))


class Pass:
    def __init__(self,args,ev,*,event=None):
        self.event=event;self.active_pair=None;self.active_target=None;self.active_phase=None
        self.a=args;self.ev=ev;self.start=time.monotonic();self.last=0;self.counts=Counter()
        from case_collector import evaluate_cached
        # Table presentation is discarded by candidate compaction. Older
        # evaluator snapshots keep their existing call signature and behavior.
        self.candidate_options=({'include_table':False}
            if 'include_table' in inspect.signature(evaluate_cached).parameters else {})
        self.source_store=TaskNativeStore(ev.legacy,CODE_ROOT,counters=self.counts)
        self.base=sqlite3.connect(args.base.resolve().as_uri()+'?mode=ro',uri=True)
        self.base.execute('PRAGMA temp_store=MEMORY');self.base.execute('BEGIN')
        files=set(HERE/n for n in ('targets.py','target_store.py','target_compare.py','target_search.py','metadata.py',
            'read_targets.py','evidence.py','_paths.py','certificates.py','preflight.py','fact_codec.py','views.py','negative.py','target_index.py','runtime_cache.py','supervisor.py','paused_archive.py'))
        files.update((CODE_ROOT/'judgetool').glob('*.py'))
        files.update((CODE_ROOT/'judge3').glob('*.py'))
        files.update(CODE_ROOT/'ast/run/mech'/n for n in ('algorithm.py','step2_check.py','run.py','clause_evidence.py','outcomes.py','grades.py'))
        files.add(CODE_ROOT/'study_paths.py')
        files.add(CODE_ROOT/'ast/run/mech4/paused_archive.py')
        files.update((CODE_ROOT/'judge2/render2').glob('*.py'))
        files.update(CODE_ROOT/n for n in ('judge3/nonrender_metadata.py','judge3/render_pair.py','judge3/catalog.py',
            'judge2/render2/headers.py','judge2/render2/body.py','judge2/render2/column_paths.py',
            'judge2/render2/structured.py','ast/check_stage1_all.py','ast/run/native_storage.py',
            'ast/run/native_tables.py','ast/run/filters.py','ast/run/recovery.py',
            'ast/run/next_revision/family_recovery.py','ref/progsynth-relabel/engine_verify.py',
            'ref/progsynth-relabel/verify_recovery.py'))
        files.add(Path(ev.runtime['binary']))
        self.manifest={(str(p.resolve().relative_to(CODE_ROOT)) if p.resolve().is_relative_to(CODE_ROOT) else str(p.resolve())):
                       hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}
        self.signatures={name:self.signature(self.code_path(name)) for name in self.manifest}
        config=dict(schema='mech-target-config-v2',fact_contract='mech-target-facts-v2',base=str(args.base.resolve()),
            evaluator=ev.receipt,compare_seconds=args.compare_seconds,search_seconds=args.search_seconds,
            max_targets=args.max_search_targets,max_candidates=args.max_candidates,pair_seconds=args.pair_seconds,
            search='bounded nonlib proposals; shared TRAIN+TEST verification; no settled-space negative',
            gold='once per case/program/own-kept/settings; durable case JSON; no stored gold target rows')
        self.journal=Journal(args.output,digest(self.manifest),digest(config),counters=self.counts)
        self.journal.register(self.manifest,config)
        if args.selection is None:
            self.total=self.base.execute('SELECT count(*) FROM pairs').fetchone()[0]
        else:
            # TEMP lives only in this read-only connection. CROSS JOIN below
            # drives indexed base lookups from the selected IDs, not a scan of
            # every source record. No main-table writes or copied labels.
            self.base.execute('CREATE TEMP TABLE target_selection(pair_id TEXT PRIMARY KEY,source_sha256 TEXT)')
            self.base.executemany('INSERT INTO target_selection VALUES (?,?)',args.selection.items())
            bad=self.base.execute('SELECT s.pair_id FROM target_selection s LEFT JOIN pairs p ON p.pair_id=s.pair_id '
                'WHERE p.pair_id IS NULL OR p.source_sha256!=s.source_sha256 LIMIT 1').fetchone()
            if bad:raise ValueError('selected pair input absent or changed: '+bad[0])
            self.total=len(args.selection)
        self.done=0
        self.target_indexes=TargetIndexes(counters=self.counts);self.proposal_cache=OrderedDict()
        self.producers={};self.case_cache={};self.case_refs={};self.resolved_case_programs={};self.case_failures={};self.current_task=None;self.tasks={}

    def set_phase(self,phase,target_id=None):
        if phase.startswith('target:'):phase,target_id='comparison',phase[len('target:'):]
        if (phase,target_id)==(self.active_phase,self.active_target):return
        self.active_phase,self.active_target=phase,target_id
        if self.event is not None and self.active_pair is not None:
            self.event(dict(event='phase',pair_id=self.active_pair,phase=phase,target_id=target_id))

    @contextmanager
    def timed(self,phase):
        self.set_phase(phase,self.active_target)
        started=time.monotonic()
        try:yield
        finally:self.counts['seconds_'+phase]+=round(time.monotonic()-started,6)

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

    def progress(self,done,phase='pairs',force=False,target_id=None):
        self.set_phase(phase,target_id if target_id is not None else self.active_target)
        elapsed=time.monotonic()-self.start
        if force or elapsed-self.last>=5:
            rate=(done-getattr(self.a,'start_after',0))/max(elapsed,.001);eta=(self.total-done)/rate if rate else 'unknown'
            print(f'phase={phase} done={done}/{self.total} elapsed={elapsed:.1f}s rate={rate:.2f}/s '
                  f'ETA={eta}s pair_id={self.active_pair} target_id={json.dumps(self.active_target)} counters={dict(self.counts)}',file=sys.stderr,flush=True)
            self.last=elapsed

    def pair_inputs(self,base):
        return dict(pair_id=base['pair_id'],source_sha256=base['source_sha256'])

    def save_pair(self,base,result):
        result.update(self.pair_inputs(base),base_result_sha256=digest(base))
        self.journal.save('pair',base['pair_id'],self.pair_inputs(base),result)

    def task(self,task):
        if task in self.tasks and file_hash(self.tasks[task][2]['path'])!=self.tasks[task][2]['sha256']:
            raise RuntimeError('task inputs changed during target pass: '+task)
        if task not in self.tasks:
            path=(Path(self.ev.cfg['tasks'])/(task+'.json')).resolve();raw=path.read_bytes();value=json.loads(raw)
            self.tasks[task]=(len(value['train']),len(value['test']),dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest()))
        return self.tasks[task]

    def metadata(self,record,corpus,kind):
        key=str(corpus)
        producer=self.producers.get(key)
        producer,adapter=produce(self.ev,self.source_store,record,corpus,producer=producer,kind=kind)
        self.producers[key]=producer
        return producer,adapter

    def bundles(self,record,adapter,ntrain,ntest):
        from case_collector import acquire_case,_context
        result=[];gaps=[];references=[];failures=[]
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
            key=digest(inputs);legacy_inputs=inputs;legacy_key=key
            if key in self.case_failures:
                failures.append(self.case_failures[key]);self.counts['case_failures_reused']+=1
                continue
            try:
                # Resolve catalogue-backed programs before assigning a case
                # identity. The same case can first appear as another case
                # without source text, then as its own pair with explicit text.
                # Both must reuse one observation and the same own kept axes.
                if text is None or kept is None:
                    program_key=(record['task'],case['name'],inventory['catalogue_sha256'])
                    known=self.resolved_case_programs.get(program_key)
                    if text is None and known is not None:
                        context=dict(context,gold_sexp=known[0])
                        if known[1] is not None:context['relation_source_names']=known[1]
                    _,text,kept,names=_context(self.ev,record,context)
                    self.resolved_case_programs[program_key]=(text,names)
                    context=dict(context,gold_sexp=text,kept_assignments=kept)
                    if names is not None:context['relation_source_names']=names
                    inputs=dict(inputs,program_sha256=digest(text),kept_context_sha256=digest(kept))
                    key=digest(inputs)
                if key in self.case_failures:
                    failures.append(self.case_failures[key]);self.counts['case_failures_reused']+=1
                    continue
                bundle=self.case_cache.get(key)
                if bundle is None:
                    entry_key=key
                    bundle=self.journal.load('case',key,inputs)
                    if bundle is None and legacy_key!=key:
                        bundle=self.journal.load('case',legacy_key,legacy_inputs)
                        if bundle is not None:
                            entry_key=legacy_key;self.counts['legacy_case_identities_reused']+=1
                    if bundle is None:
                        self.progress(self.done,phase='gold_case:'+case['name'],force=True)
                        self.guard();bundle=acquire_case(self.ev,record,context,ntrain,ntest);self.guard()
                        bundle=dict(bundle,caller_task_inputs=self.task(record['task'])[2])
                        bundle=self.journal.save('case',key,inputs,bundle)
                        self.counts['gold_case_collections']+=1
                    else:self.counts['gold_cases_resumed']+=1
                    self.case_refs[key]=self.journal.reference('case',entry_key)
                    if bundle.get('axis_ref'):
                        bundle=dict(bundle,axis=self.journal.read_reference(bundle['axis_ref'])['axis'],_axis_ref=bundle['axis_ref'])
                    bundle=expand_case(bundle,self.ev,record,context)
                    self.case_cache[key]=bundle
                result.append(bundle);references.append(self.case_refs[key])
            except (self.ev.arclog.Refusal,ValueError,KeyError,IndexError,OSError,TypeError) as error:
                failure=dict(schema='mech-case-preparation-failure-v1',case=case['name'],
                    reason=str(error),error_type=type(error).__name__,stage='case acquisition')
                # One failure fact per case inputs/attempt, shared by all affected
                # pairs. Successful observations keep their independent identity.
                failure_key=digest(dict(case_inputs=inputs,failure=failure))
                if self.journal.load('case_failure',failure_key,inputs) is None:
                    self.journal.save('case_failure',failure_key,inputs,failure)
                ref=self.journal.reference('case_failure',failure_key)
                self.case_failures[key]=ref;failures.append(ref)
                self.counts['case_preparation_failures']+=1
        return result,gaps,references,failures

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
        inputs=dict(source_sha256=inputs['source_sha256'],case_refs=inputs['case_refs'],
                    clause=candidate['clause'],columns=candidate['columns'],max_mutant_replays=1)
        key=digest(dict(pair=digest(pair_key(record)),inputs=inputs))
        result=self.journal.load('candidate',key,inputs)
        if adapter['input']['binding'].get('kind','').casefold()=='det':
            raise ValueError('mechanical DET candidate checker unavailable; judge DET path is excluded')
        if result is None:
            self.guard()
            target=dict(adapter=adapter,source=dict(source_sha256=inputs['source_sha256']),
                ntrain=selection['ntrain'],ntest=selection['ntest'],mode='recovery')
            try:
                result=evaluate_cached(self.ev,record,candidate['clause'],target,candidate['columns'],selection,
                    row_limit=0,max_mutant_replays=1,**self.candidate_options)
            except (ValueError,KeyError,IndexError,TypeError) as error:
                result=dict(outcome='unknown',reason=str(error))
            result=dict(result,requested_output_columns=candidate['columns'])
            result.setdefault('submitted_clause',candidate['clause'])
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
        if digest(record)!=base['source_sha256'] or digest(pair_key(record))!=base['pair_id']:
            raise ValueError('current source differs from the base source receipt')
        corpus=Path(base['source']['corpus']).resolve()
        ntrain,ntest,task_receipt=self.task(record['task']);result['task_receipt']=task_receipt
        with self.timed('metadata'):
            producer,adapter=self.metadata(record,corpus,base['kind'])
        # Authenticate stored X before any fresh gold preparation/replay.
        with self.timed('stored_X'):
            source,fields=self.source_store.mutant_input(record,adapter,ntrain,ntest)
        with self.timed('case_acquisition'):
            bundles,gaps,refs,failures=self.bundles(record,adapter,ntrain,ntest)
        result.update(case_refs=refs,case_failure_refs=failures,gaps=gaps)
        own=[b for b in bundles if b['case']==record['case']]
        if own and own[0].get('_axis_ref'):result['axis_ref']=own[0]['_axis_ref']
        self.callable_metadata(producer,adapter,bundles,record)
        try:
            with self.timed('selection'):
                selection=self.target_indexes.select(bundles,record,adapter,ev=self.ev)
        except (ValueError,KeyError,IndexError,OSError,TypeError) as error:
            # The case failure already records the precise native refusal.
            if failures:return result
            raise PairUnavailable(result,error) from error
        selection['gaps'].extend(gaps)
        selection['complete']&=not (gaps or failures)
        targets=([selection['point']] if selection['point'] is not None else [])+selection['targets']
        result.update(complete=selection['complete'],gaps=selection['gaps'],case_refs=refs)
        comparisons=[];possible=[]
        # One durable transaction for this pair's cheap table observations;
        # expensive candidate results still commit separately as soon as done.
        with self.journal.transaction():
            for target in targets:
                grouped,target_fields,reference,receipt=target
                if STOP:raise InterruptedError('stopping before next target')
                self.progress(self.done,phase='target:'+reference['target_id'])
                target_key=digest(dict(reference=reference,receipt=receipt))
                inputs=dict(source_sha256=base['source_sha256'],case_refs=refs,target_key=target_key)
                key=digest(dict(pair=base['pair_id'],target=target_key))
                comparison=self.journal.load('comparison',key,inputs)
                if comparison is None:
                    with self.timed('comparison'):
                        comparison=compare(source,fields,target,seconds=self.a.compare_seconds,indexes=self.target_indexes)
                    self.journal.save('comparison',key,inputs,comparison);self.counts['target_comparisons']+=1
                else:self.counts['comparisons_resumed']+=1
                proof_ref=self.journal.reference('comparison',key,comparison)
                eq=comparison['equality'];include=comparison['containment']
                for relation,outcome in (('equal',eq),('contains',include)):
                    if outcome['status']=='unknown':
                        print(json.dumps(dict(event='target_unknown',pair_id=base['pair_id'],
                            target_id=reference['target_id'],phase=outcome.get('phase','comparison'),
                            relation=relation,reason=outcome.get('reason','comparison unavailable')),
                            sort_keys=True),file=sys.stderr,flush=True)
                comparisons.append((target,comparison,proof_ref))
                result.setdefault('comparison_refs',[]).append(dict(reference=proof_ref,target=target_identity(reference)))
                result['grade_comparisons'].append(dict(target_id=reference['target_id'],equal=eq['status']=='equal',
                    train=eq.get('train')=='equal',test=eq.get('test')=='equal',complete=eq['status']=='equal',
                    kept_contexts_complete=not source['missing'] and not grouped['missing'],
                    test_target='gold_full_replay',receipt_ref=proof_ref,comparison=eq))
                if include['status']=='contains' and reference.get('role')!='point':possible.append((target,inputs))
                if reference.get('role')=='point':
                    result['point']=dict(complete=include['status']!='unknown',
                        X_holds_every_gold_row=True if include['status']=='contains' else False if include['status']=='mismatch' else None,
                        receipt_ref=proof_ref,comparison=include)
        if any(c['equality']['status']=='unknown' or c['containment']['status']=='unknown' for t,c,r in comparisons):
            result['gaps'].append(dict(stage='comparison',reason='missing or bounded target comparison'))
        # A native equality is already the strongest possible target outcome.
        already=any(c['equal'] and c['complete'] for c in result['grade_comparisons'])
        candidates=0
        if not already:
            for index,(target,inputs) in enumerate(possible):
                if STOP:raise InterruptedError('stopping after current durable target')
                if index>=self.a.max_search_targets or candidates>=self.a.max_candidates:
                    result['bounded']=True;result['work_stop']='candidate_or_target_limit';break
                reference=target[2]
                self.progress(self.done,phase='other_target_search',target_id=reference['target_id'])
                key=digest(dict(pair=base['pair_id'],target=inputs['target_key'],phase='search'))
                search=self.journal.load('search',key,inputs)
                if search is None:
                    try:
                        with self.timed('proposal'):
                            proof,bindings,receipt=propose(source,fields,target,reference,selection,adapter,seconds=self.a.search_seconds,cache=self.proposal_cache,counters=self.counts)
                        search=dict(proof=proof,receipt=receipt,status='proposal' if proof.get('recoverable') else 'not_covered')
                        if proof.get('recoverable'):
                            candidate=clause(self.ev.legacy,proof,adapter['input']['binding'],bindings)
                            with self.timed('candidate_check'):
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
                if search.get('candidate_ref') and not search.get('checked'):
                    raw=self.journal.read_reference(search['candidate_ref'])
                    from clause_evidence import clause_evidence
                    search=dict(search,checked=clause_evidence(raw,record,search['candidate_ref'],
                        ntrain=ntrain,ntest=ntest))
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
        selected=self.a.selection is not None
        source=('target_selection s CROSS JOIN pairs p ON p.pair_id=s.pair_id' if selected else 'pairs p')
        sql=('SELECT p.pair_id,p.source_sha256,p.code_sha256,p.config_sha256,p.result_sha256,p.record_json FROM '+source+
             " ORDER BY json_extract(p.record_json,'$.task'),json_extract(p.record_json,'$.source.corpus'),"
             "json_extract(p.record_json,'$.source.file'),json_extract(p.record_json,'$.source.line'),p.pair_id")
        after=getattr(self.a,'start_after',0)
        if after:sql+=' LIMIT -1 OFFSET '+str(int(after))
        stream=None;path=None;lineno=0;record=None;failed=None
        try:
            for done,row in enumerate(self.base.execute(sql),after+1):
                if STOP:return False
                base=valid_base(row);inputs=self.pair_inputs(base);self.done=done
                from source_bindings import scope_equal
                if selected and not scope_equal(base['pair_id'],self.a.selection[base['pair_id']],base['source_sha256'],'targets'):
                    raise ValueError('selected pair input changed: '+base['pair_id'])
                if self.a.task and base['task'] not in self.a.task:continue
                from .preflight import det_available
                if base['kind'].casefold()=='det' and (not self.a.include_det or not det_available()):
                    self.counts['DET_left_open']+=1;self.progress(done,phase='DET_pending');continue
                if self.a.limit and self.counts['pairs_done']>=self.a.limit:break
                saved=self.journal.load('pair',base['pair_id'],inputs)
                if saved is not None:
                    checked=load_targets(self.a.output,base['pair_id'],source_sha256=base['source_sha256'],base_result_sha256=digest(base),derive=False)
                    if checked['valid'] and not ((self.a.retry_unavailable and unavailable(saved))
                            or (self.a.retry_stopped and isinstance(saved.get('stopped'),dict))):
                        self.counts['pairs_resumed']+=1;self.progress(done);continue
                    if checked['valid']:self.counts['unavailable_pairs_retried']+=1
                    else:self.counts['stale_pair_results']+=1
                self.active_pair=base['pair_id'];self.active_target=None;self.active_phase='pair_setup'
                if self.event is not None:
                    prior=self.journal.db.execute("SELECT rowid FROM entries WHERE kind='pair' AND key=?",(base['pair_id'],)).fetchone()
                    self.event(dict(event='pair_started',pair_id=base['pair_id'],source_sha256=base['source_sha256'],
                        base_result_sha256=digest(base),done=done,prior_rowid=prior[0] if prior else None,
                        phase='pair_setup',target_id=None))
                if self.current_task!=base['task']:
                    self.ev.close();clear_cache(self.ev);self.source_store.clear()
                    self.target_indexes=TargetIndexes(counters=self.counts);self.proposal_cache.clear()
                    self.case_cache.clear();self.case_refs.clear();self.resolved_case_programs.clear()
                    self.case_failures.clear();self.producers.clear();self.current_task=base['task']
                self.set_phase('source_record')
                from source_read import SourceReader
                if not hasattr(self,'moved_sources'):self.moved_sources=SourceReader(CODE_ROOT)
                failed=None
                try:record=self.moved_sources.record(base)
                except (OSError,ValueError,KeyError,StopIteration) as error:failed=error
                try:
                    if failed:raise failed
                    result=self.process(base,record)
                except InterruptedError:return False
                except PairUnavailable as error:
                    result=error.result;self.counts['pairs_unavailable']+=1
                except (self.ev.arclog.Refusal,ValueError,KeyError,IndexError,OSError,TypeError) as error:
                    result=dict(schema='mech-step3-pair-v1',pair_id=base['pair_id'],source_sha256=base['source_sha256'],
                        complete=False,gaps=[dict(stage='pair unavailable',reason=str(error),error_type=type(error).__name__)])
                    self.counts['pairs_unavailable']+=1
                if result.get('case_failure_refs'):self.counts['pairs_case_unavailable']+=1
                self.set_phase('pair_commit',self.active_target)
                self.guard();self.save_pair(base,result)
                self.counts['pairs_done']+=1;self.progress(done)
                if self.event is not None:self.event(dict(event='pair_done',pair_id=base['pair_id'],done=done))
                self.active_pair=None
            self.progress(self.done,force=True)
            return not bool(self.a.task or self.a.limit)
        finally:
            if hasattr(self,'moved_sources'):self.moved_sources.close()
            if stream is not None:stream.close()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=DATA_ROOT/'ast/run/mech/labels.sqlite3')
    ap.add_argument('--output',type=Path,default=DATA/'targets.sqlite3')
    ap.add_argument('--deadline',type=float,default=30)
    ap.add_argument('--pair-seconds',type=float,default=600,help='supervised wall budget per new pair attempt')
    ap.add_argument('--retry-stopped',action='store_true',help='explicitly retry wall-budget/worker stopped pairs')
    ap.add_argument('--compare-seconds',type=float,default=1)
    ap.add_argument('--search-seconds',type=float,default=1)
    ap.add_argument('--max-search-targets',type=int,default=32)
    ap.add_argument('--max-candidates',type=int,default=16)
    ap.add_argument('--task',action='append')
    ap.add_argument('--limit',type=int)
    ap.add_argument('--retry-unavailable',action='store_true',help='retry failed pair/case acquisition; reuse completed child facts')
    ap.add_argument('--pairs-from',type=Path,help='JSONL of exact pair_id/source_sha256 inputs; no other pairs visited')
    ap.add_argument('--wait-for-writer',action='store_true',help='wait without evaluation for the output writer lock')
    ap.add_argument('--include-det',action='store_true',help='requires the future mechanical DET capability')
    a=ap.parse_args()
    try:a.selection=read_selection(a.pairs_from)
    except (ValueError,KeyError,OSError,TypeError) as error:ap.error(str(error))
    if a.pairs_from and a.task:ap.error('--pairs-from cannot be combined with --task')
    for path in (a.output,):
        if not path.resolve().is_relative_to(DATA):ap.error('outputs must stay under '+str(DATA))
    if a.base.resolve()==a.output.resolve():ap.error('base is read-only')
    if min(a.pair_seconds,a.deadline,a.compare_seconds,a.search_seconds,a.max_search_targets,a.max_candidates)<=0:
        ap.error('bounds must be positive')
    if a.limit is not None and a.limit<=0:ap.error('--limit must be positive')
    # Shared repair capabilities must land before this driver is launched.
    from .preflight import require_shared
    require_shared(include_det=a.include_det)
    DATA.mkdir(parents=True,exist_ok=True)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    lock=a.output.with_suffix('.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        if not a.wait_for_writer:
            lock.close();raise
        print('phase=waiting_for_writer output='+str(a.output.resolve())+
              ' selected='+str(len(a.selection) if a.selection is not None else 'all')+
              ' no pair evaluation before lock acquisition',file=sys.stderr,flush=True)
        fcntl.flock(lock,fcntl.LOCK_EX)
        print('phase=writer_acquired output='+str(a.output.resolve()),file=sys.stderr,flush=True)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    os.environ['STUDY_RUN']=str(CODE_ROOT/'ast/run')
    from .supervisor import supervise
    try:supervise(a,lock=lock,stopping=lambda:STOP)
    finally:lock.close()
    if STOP:raise SystemExit(130)


if __name__=='__main__':main()
