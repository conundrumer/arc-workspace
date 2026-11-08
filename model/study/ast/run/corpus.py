#!/usr/bin/env python3
"""Stream a parallel, task-atomic AST mutation corpus. No tests or token mutation."""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[2]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

ROOT=Path(__file__).resolve().parent

def verify_sources(path):
    blob=path.read_bytes()
    receipt=json.loads(blob)
    if receipt.get('schema')!='arclog-production-corpus-sources-v1':
        raise ValueError('unknown production source receipt')
    for name,expected in receipt['sha256'].items():
        actual=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
        if actual!=expected:raise ValueError('production source differs from receipt: '+name)
    return hashlib.sha256(blob).hexdigest()


# Authenticate project source bytes before imports execute their module bodies.
_source_parser=argparse.ArgumentParser(add_help=False)
_source_parser.add_argument('--source-receipt',type=Path,default=Path(__file__).with_name('SOURCES.repository.json'))
_source_args,_=_source_parser.parse_known_args()
_VALIDATED_SOURCE_RECEIPT_SHA256=verify_sources(_source_args.source_receipt)

# Both entry names refer to one operation/cache state in either import order.
_self=sys.modules[__name__]
for _entry_name in ('corpus','arc_study.corpus'):
    _prior=sys.modules.get(_entry_name)
    if _prior is not None and _prior is not _self:
        raise ImportError('conflicting canonical corpus module: '+_entry_name)
    sys.modules[_entry_name]=_self

sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT.parent))
from check_stage1_all import inventory
# The live raw-first filter is pinned by the source receipt.
from filters import native, graph, rows_at, equal_tables, empty_table
from next_revision import family_recovery
from native_storage import NativeStore, raw_native
from disk_guard import DiskGuard, DiskSpaceStop, directory_bytes
from provenance import select_runtime

FILTERS=('empty_mutant','equal_gold','equal_available','equal_later_gold','recoverable_gold','no_dependency_path')
RECORD_FORMAT='ast-study-pair-v6-family1'
ACTIVE_GUARD=None
ACTIVE_BUILD=None

class GoldObservations:
    """Restore standalone reports from native compact references, losslessly."""
    def __init__(self):self.observations={}
    def expand(self,report):
        ref=report.get('gold_observation_ref')
        if ref is None:return report
        if 'gold_assignments' in report and 'kept_assignments' in report:
            self.observations[ref]=(report['gold_assignments'],report['kept_assignments'],
                                    {o['assignment']:o['gold_train'] for o in report['outputs']})
        elif ref in self.observations:
            assignments,kept,train=self.observations[ref]
            report['gold_assignments']=assignments;report['kept_assignments']=kept
            for output in report['outputs']:output['gold_train']=train[output['assignment']]
        else:raise ValueError('compact report has no matching gold observation')
        return report

def write(out,row):
    if ACTIVE_BUILD:
        row.setdefault('engine_commit',ACTIVE_BUILD['engine_commit'])
        row.setdefault('wheel_sha256',ACTIVE_BUILD['wheel_sha256'])
    write_line(out,json.dumps(row,separators=(',',':'),check_circular=False)+'\n')

def write_line(out,line):
    if ACTIVE_GUARD is None:out.write(line);out.flush();return
    with ACTIVE_GUARD.permit(len(line.encode('utf-8'))+256):out.write(line);out.flush()

def progress(label,done,total,start,**extra):
    elapsed=time.monotonic()-start;rate=(done-extra.pop('initial_done',0))/max(elapsed,1e-9)
    print(json.dumps(dict(event='progress',scope=label,done=done,total=total,elapsed=round(elapsed,2),
                         rate=round(rate,3),eta=round((total-done)/rate,2) if rate else (0 if done==total else None),**extra)),flush=True)

def outcome(fn):
    try:
        result=fn()
        return result if isinstance(result,dict) else dict(status='complete',reject=bool(result))
    except Exception as exc:return dict(status='unknown',reject=False,reason=f'{type(exc).__name__}: {exc}')

class GoldRelations:
    """One full gold observation per case, in the pair evaluator's session."""
    def __init__(self,evaluator,gold,temp,index,dep,store):
        self.evaluator,self.gold,self.temp,self.index,self.dep=evaluator,gold,temp,index,dep
        self.tables=None;self.reference=None;self.candidates=None;self.store=store
        self.kept_tables=None;self.kept_reference=None
        self.render=None;self.out_binding=None;self.roles={}

    def final_role(self,point):
        key=tuple(point.body_path)
        if key not in self.roles:
            if self.render is None:
                self.render=json.loads(self.gold.render_json())
                self.out_binding=json.loads(self.gold.out_bindings_json())
            self.roles[key]=family_recovery.final_definition(self.render,list(key),self.out_binding)
        return self.roles[key]

    def get_kept(self,mutant,report):
        expected=report['kept_assignments']
        if (self.kept_tables is None)!=(self.kept_reference is None):
            self.kept_tables=None;self.kept_reference=None
        if self.kept_reference is not None and (self.kept_reference['evaluation']['kept_assignments']!=expected or
                self.kept_reference['evaluation'].get('gold_observation_ref')!=report.get('gold_observation_ref')):
            self.kept_tables=None;self.kept_reference=None
        if self.kept_tables is None:
            import arclog
            text,obj,_=arclog.study_component_tables(self.evaluator,self.gold,mutant,expected_kept_json=json.dumps(expected))
            info=json.loads(text)
            if info.get('kept_assignments')!=expected or info.get('gold_observation_ref')!=report.get('gold_observation_ref'):
                raise ValueError('gold component tables differ from exact kept observation')
            payload=raw_native(obj)
            tables=native(payload)
            tables['_kept_context_key']=json.dumps(dict(gold_observation_ref=info['gold_observation_ref'],kept_assignments=expected),sort_keys=True,separators=(',',':'))
            # Cached mutant fields describe only the first mutant. Persist a
            # gold-only receipt that is truthful for every pair reusing it.
            fields=('schema','gold_observation_ref','full_choice_extents','kept_assignments',
                    'gold_observation_stop','gold_status','gold_collection','gold_assignment_map','assignment_contract','bound_scope')
            gold_info={key:info[key] for key in fields if key in info}
            gold_info['scope']='gold-only'
            reference=dict(gold=self.store.put_raw(payload),evaluation=gold_info,
                           scope='gold_full_kept',ident_namespace='shared task evaluator session')
            self.kept_tables,self.kept_reference=tables,reference
        return self.kept_tables,self.kept_reference


    def get(self):
        if self.tables is None:
            tick=time.monotonic()
            text,obj=self.evaluator.gold_tables(self.gold)
            report=json.loads(text)
            payload=raw_native(obj)
            reference=self.store.put_raw(payload)
            self.tables=native(payload)
            self.reference=dict(gold=reference,evaluation=report,seconds=time.monotonic()-tick,
                                ident_namespace='shared task evaluator session')
        return self.tables,self.reference


def recover_gold(point,report,g,m,ntrain,gold_relations,mutant):
    """A bounded comparison search must not starve available-table witnesses."""
    try:
        role=gold_relations.final_role(point)
        ix=report['table_indices']
        proof=family_recovery.recovery(g,ix['gold_kept'],m,ix['mutant_kept'],report,ntrain,rows_at,
                                       final_output=role['final_output'])
        proof['final_definition']=role
        if proof.get('reject'):
            if not proof.get('verified'):raise ValueError('unverified recovery cannot code-label a pair')
            return proof
        if proof.get('nonrecoverable_proof') or proof.get('reason_code')=='evidence_incomplete':
            return proof
        fg,reference=gold_relations.get_kept(mutant,report)
        available,incomplete=family_recovery.available_tables(fg,reference['evaluation'].get('gold_assignment_map',[]),report['kept_assignments'],ntrain,point,gold_relations.dep,rows_at)
        proof=family_recovery.recovery(g,ix['gold_kept'],m,ix['mutant_kept'],report,ntrain,rows_at,available,
                                       final_output=role['final_output'])
        proof.update(final_definition=role,available_evidence=reference,available_incomplete=incomplete)
        if proof.get('reject') and not proof.get('verified'):
            raise ValueError('unverified recovery cannot code-label a pair')
        collection=reference['evaluation'].get('gold_collection',{})
        if not proof['reject'] and not proof.get('nonrecoverable_proof') and (incomplete or not collection.get('materialization_complete',False)):
            proof.update(status='unknown',reason='available-table recovery search scope incomplete',
                         reason_code='evidence_incomplete',judge_eligible=None)
        return proof
    except Exception as exc:
        return dict(status='unknown',reject=False,reason=f'{type(exc).__name__}: {exc}',
                    reason_code='evidence_incomplete',verified=False,code_label=None,judge_eligible=None)


def classification_fields(proof,retained):
    label=proof.get('code_label')
    if label is not None:
        if label not in ('DETOUR','WRONG') or not (proof.get('reject') and proof.get('verified') and proof.get('status')=='complete'):
            raise ValueError('code label lacks a verified complete recovery witness')
        return dict(code_label=label,judge_eligible=False,
                    code_label_evidence=dict(verified=True,record_path=['filters','recoverable_gold']))
    return dict(code_label=None,judge_eligible=bool(retained),code_label_evidence=None)


def apply_filters(point,dep,report,g,m,ntrain,gold_relations,mutant):
    filters={name:dict(status='unknown',reject=False,reason='pair evaluation unavailable') for name in FILTERS}
    top=point.body_path[0]
    filters['no_dependency_path']=dict(status='complete',reject=top not in dep['ancestors'][dep['out']],
                                      clause_form=top,out_form=dep['out'],out_ancestors=sorted(dep['ancestors'][dep['out']]))
    ix=report.get('table_indices')
    if not ix:return filters,None
    def empty():
        return empty_table(m,ix['mutant_kept'],kept_maps=report['mutant_kept_assignment_map'],
                           nkept=len(report['kept_assignments']),ntrain=ntrain)
    filters['empty_mutant']=outcome(empty)
    filters['equal_gold']=outcome(lambda:equal_tables(g,ix['gold_all'],m,ix['mutant_all']))
    filters['recoverable_gold']=recover_gold(point,report,g,m,ntrain,gold_relations,mutant)
    extra=None
    try:
        fg,extra=gold_relations.get_kept(mutant,report)
        candidates={'equal_available':[], 'equal_later_gold':[]}
        for i,form in enumerate(fg['tables']['form']):
            if not form:
                if fg['tables']['fact'][i]=='ex_input':candidates['equal_available'].append(i)
                continue
            if fg['tables']['point'][i]!=0:continue
            f=int(form.split('.')[0])
            if f<top or (f!=top and f!=dep['out'] and dep['ancestors'].get(f,set())<=set(range(top))):
                candidates['equal_available'].append(i)
            if f>top:candidates['equal_later_gold'].append(i)
        covered={int(form.split('.')[0]) for i,form in enumerate(fg['tables']['form']) if form and fg['tables']['point'][i]==0}
        absent=set(dep['dependencies'])-{dep['out']}-covered
        for name,indices in candidates.items():
            def compare():
                relevant=[f for f in absent if (f>top if name=='equal_later_gold' else
                          f<top or (f!=top and dep['ancestors'].get(f,set())<=set(range(top))))]
                unknown=[dict(form=f,reason='complete gold relation missing from full evaluation') for f in sorted(relevant)]
                for i in indices:
                    result=outcome(lambda:equal_tables(fg,i,m,ix['mutant_kept'],
                        amaps=extra['evaluation']['gold_assignment_map'],bmaps=report['mutant_kept_assignment_map'],
                        nkept=len(report['kept_assignments']),ntrain=ntrain,a_fact=not bool(fg['tables']['form'][i])))
                    if result['reject']:return dict(status='complete',reject=True,gold_table=i,gold_form=fg['tables']['form'][i])
                    if result['status']!='complete':unknown.append(dict(table=i,reason=result['reason']))
                collection=extra['evaluation'].get('gold_collection',{})
                if not collection.get('materialization_complete',False):unknown.append(dict(reason='gold kept relation collection incomplete'))
                return dict(status='unknown' if unknown else 'complete',reject=False,candidates=indices,incomplete=unknown)
            filters[name]=outcome(compare)
    except Exception as exc:
        for name in ('equal_available','equal_later_gold'):
            filters[name]=dict(status='unknown',reject=False,reason=f'{type(exc).__name__}: {exc}')
    return filters,extra


def draw_incrementally(args,gold,point,k,operation,task,case,ctx,events,counts):
    """Extend one deterministic without-replacement prefix only when needed.

    Closing this generator at quota performs no further native draw calls.
    Exponential extensions bound repeated certification to <3x the final prefix
    while preserving the original seed/order and 100-unique-spec upper bound.
    """
    previous=[];requested=min(args.draws,args.quota)
    while True:
        tick=time.monotonic()
        try:
            specs,text=gold.draw_specs(point,k,requested,args.seed,source_revision=args.export.name,
                                      task=task,case=case,operation=operation)
        except Exception as exc:
            counts['rejections']['draw_fault']+=1
            write(events,dict(event='draw_fault',**ctx,reason=f'{type(exc).__name__}: {exc}'))
            return
        elapsed=time.monotonic()-tick
        counts['timings']['draw']+=elapsed
        stats=json.loads(text);identities=[spec.identity_json for spec in specs]
        if len(set(identities))!=len(identities):raise ValueError('duplicate drawn edit identity')
        overlap=min(len(identities),len(previous))
        if identities[:overlap]!=previous[:overlap]:raise ValueError('incremental draw changed its deterministic prefix')
        bounded=any(key.startswith('domain_search_stopped:') and value for key,value in stats['counts'].items())
        if len(identities)<len(previous) and not bounded:raise ValueError('incremental draw shortened its prefix without a native bound')
        write(events,dict(event='draw',**ctx,requested=requested,produced=len(specs),
                          prefix_reused=len(previous),new_specs=len(specs)-len(previous),seconds=elapsed,stats=stats))
        counts['draw_reasons'].update(stats['counts'])
        if any(key.startswith('domain_search_stopped:') and value for key,value in stats['counts'].items()):
            counts['statuses']['draw_stopped']+=1;counts['rejections']['draw_domain_stopped']+=1;return
        for spec in specs[len(previous):]:yield spec
        if len(specs)<requested or requested>=args.draws:return
        previous=identities
        requested=min(args.draws,max(requested+1,requested*2))


def observe_constructed(row, evaluator, gold, point, mutant, ntrain, dep, gold_relations,
                        native_store, gold_observations, gold_filter_tables, gold_payload_cache):
    """Canonical observation/filter path, also used by stored populations.

    Caller owns certified construction and durable storage. No drawing or quota.
    """
    phase_timings={}
    evaluate_started=time.monotonic()
    text,gobj,mobj=evaluator.evaluate_pair(gold,point,mutant)
    phase_timings['evaluate']=time.monotonic()-evaluate_started
    decode_started=time.monotonic()
    report=gold_observations.expand(json.loads(text))
    phase_timings['report_expand']=time.monotonic()-decode_started
    capture_started=time.monotonic()
    gold_payload,mutant_payload=raw_native(gobj),raw_native(mobj)
    phase_timings['native_capture']=time.monotonic()-capture_started
    store_started=time.monotonic()
    row.update(evaluation=report,native=dict(gold=native_store.put_raw(gold_payload,gold_payload_cache),mutant=native_store.put_raw(mutant_payload)))
    phase_timings['native_store']=time.monotonic()-store_started
    view_started=time.monotonic()
    body_key=tuple(point.body_path)
    if body_key not in gold_filter_tables:gold_filter_tables[body_key]=native(gold_payload)
    g,m=gold_filter_tables[body_key],native(mutant_payload)
    phase_timings['native_filter_view']=time.monotonic()-view_started
    phase_timings['native_decode']=time.monotonic()-decode_started
    filter_started=time.monotonic()
    fs,full=apply_filters(point,dep,report,g,m,ntrain,gold_relations,mutant)
    phase_timings['filters']=time.monotonic()-filter_started
    row.update(full_replay=full,filters=fs)
    reasons=[name for name in FILTERS if fs[name]['reject']]
    unknown=[name for name in FILTERS if name!='recoverable_gold' and fs[name]['status']!='complete']
    if report['status']!='complete':reasons.insert(0,'evaluation_'+report['status'])
    if report.get('gold_fits') is not True:reasons.append('gold_not_fits' if report.get('gold_fits') is False else 'gold_fits_unknown')
    if unknown:reasons.append('filter_unknown')
    survivor=not reasons
    row.update(status=report['status'],retained=survivor,post_filter_survivor=survivor,rejection_reasons=reasons)
    row.update(classification_fields(fs['recoverable_gold'],survivor))
    return row, phase_timings, unknown


def worker(args):
    for key in ('ARCLOG_THREADS','RAYON_NUM_THREADS','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):os.environ[key]='1'
    global ACTIVE_GUARD
    ACTIVE_GUARD=DiskGuard(args.output,args.min_free_gb)
    ACTIVE_GUARD.check()
    import arclog
    require_evaluator(arclog)
    task=args.worker;final=args.output/task
    if final.is_dir():return
    temp=args.output/('.'+task+'.tmp')
    # Parent holds a task lock; only incomplete staging is replaced.
    if temp.exists():shutil.rmtree(temp)
    temp.mkdir(parents=True)
    start=time.monotonic(); counts={k:Counter() for k in ('filters','filter_outcomes','filter_unknown_reasons','statuses','status_reasons','rejections','draw_reasons','timings','totals','code_labels')}
    state=dict(done=0,total=0,pairs=0,cursor='inventory');stop=threading.Event()
    def heartbeat():
        while not stop.wait(2):progress(task,state['done'],state['total'],start,pairs=state['pairs'],cursor=state['cursor'],phase_seconds=dict(counts['timings']))
    thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
    complete=False
    try:
        names,offsets,ids,flags=inventory(args.export,task,True);names=names[:args.case_limit]
        state['total']=len(names)
        tasktext=(args.tasks/(task+'.json')).read_text();ntrain=len(json.loads(tasktext)['train'])
        settings=arclog.DecodeSettings(table_work_cap=args.work_cap,rule_tests=False)
        evaluator=arclog.StudyTaskEvaluator(task,str(args.tasks),settings,session_bytes=args.session_mib*1024*1024,compact=True)
        gold_observations=GoldObservations()
        source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.glob('*.py')}
        source_hashes.update(json.loads(args.source_receipt.read_text())['sha256'])
        source_hashes.update({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).resolve().parent.glob('*.py')})
        binary_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(arclog.__file__).parent.glob('*.so')}
        meta=dict(provenance=args._provenance,record_format=RECORD_FORMAT,source_hashes=source_hashes,binary_hashes=binary_hashes,config=config(args),task=task,cases=names,streams_digest=arclog.streams_digest(),mutation_policy=arclog.StudyProgram.mutation_policy())
        (temp/'manifest.json').write_text(json.dumps(meta,indent=2)+'\n')
        with NativeStore(temp,ACTIVE_GUARD) as native_store, gzip.open(temp/'pairs.jsonl.gz','wt',compresslevel=1) as pairs, gzip.open(temp/'recoverable.jsonl.gz','wt',compresslevel=1) as recovered, (temp/'retained.jsonl').open('w',buffering=1) as retained_pairs, (temp/'events.jsonl').open('w',buffering=1) as events:
            for ci,case in enumerate(names):
                state['cursor']=dict(case=case,phase='ingest')
                try:
                    lo,hi=offsets[ci:ci+2]
                    gold=evaluator.from_stream(ids[lo:hi],list(map(int,flags[lo:hi])))
                    relation_source_names=json.loads(gold.relation_source_names_json(str(MAIN_ROOT / 'work/arclog/gen'),task,case))
                    sexp=gold.sexp();dep=graph(sexp)
                    gold_relations=GoldRelations(evaluator,gold,temp,ci,dep,native_store)
                    points=gold.points()[:args.point_limit]
                    for point in points:
                        # Only this point is revisited across K/operations.
                        # Release its decoded prefix before advancing so Python
                        # memory does not grow as points x program-prefix size.
                        gold_filter_tables={}
                        gold_payload_cache={}
                        # Native draws are unique within a bucket. Keep the
                        # point unique across K/operation requests as well.
                        point_texts=set()
                        for k in (1,2,3):
                            for op in ('substitute','delete'):
                                ctx=dict(task=task,case=case,point=list(point.body_path),clause=list(point.clause_path),kind=point.kind,K=k,operation=op)
                                state['cursor']=dict(**ctx,phase='draw')
                                retained=0;drawn=0
                                specs=draw_incrementally(args,gold,point,k,op,task,case,ctx,events,counts)
                                for spec in specs:
                                    ACTIVE_GUARD.check()
                                    drawn+=1
                                    state['cursor']=dict(**ctx,phase='evaluate');tick=time.monotonic()
                                    phase_timings={}
                                    row=dict(type='pair',record_format=RECORD_FORMAT,engine_commit=args._provenance['engine_commit'],wheel_sha256=args._provenance['wheel_sha256'],native_binary_sha256=args._provenance['native_binary_sha256'],**ctx,identity=json.loads(spec.identity_json),relation_source_names=relation_source_names,programs=dict(gold=sexp,mutant=None),gold_sexp=sexp,mutant_sexp=None,mutant_stream=None,code_label=None,judge_eligible=False,code_label_evidence=None)
                                    try:
                                        mutant=gold.construct(spec)
                                        mutant_text=mutant.sexp()
                                        if mutant_text in point_texts:
                                            counts['totals']['duplicate_text_excluded']+=1
                                            write(events,dict(event='duplicate_mutant_text',**ctx,identity=json.loads(spec.identity_json)))
                                            continue
                                        point_texts.add(mutant_text)
                                        ms=mutant.decode_stream()
                                        audit=json.loads(mutant.audit_json())
                                        if audit['changed_atoms']!=k:raise ValueError('constructed mutant does not have exact K edits')
                                        row.update(mutant_sexp=mutant_text,mutant_stream=dict(ids=ms[0],model=list(ms[1]),paths=ms[2]),audit=audit)
                                        row['programs']['mutant']=row['mutant_sexp']
                                        phase_timings['construct']=time.monotonic()-tick
                                        row,new_timings,unknown=observe_constructed(row,evaluator,gold,point,mutant,ntrain,dep,gold_relations,native_store,gold_observations,gold_filter_tables,gold_payload_cache)
                                        phase_timings.update(new_timings)
                                        report=row['evaluation'];fs=row['filters'];survivor=row['post_filter_survivor']
                                        reasons=row['rejection_reasons']
                                        if survivor and retained>=args.quota:reasons.append('post_filter_quota')
                                        keep=not reasons
                                        if keep:retained+=1
                                        row.update(retained=keep)
                                        row.update(classification_fields(fs['recoverable_gold'],keep))
                                        if row['code_label']:counts['code_labels'][row['code_label']]+=1
                                        counts['statuses'][report['status']]+=1
                                        if report.get('reason'):counts['status_reasons'][report['status']+':'+report['reason']]+=1
                                        for name in unknown:
                                            detail=fs[name]
                                            reasons_detail=[detail['reason']] if detail.get('reason') else [x['reason'] for x in detail.get('incomplete',[])]
                                            counts['filter_unknown_reasons'].update(name+':'+reason for reason in reasons_detail)
                                        counts['filter_outcomes'].update(name+':'+('reject' if fs[name]['reject'] else 'pass' if fs[name]['status']=='complete' else 'unknown') for name in FILTERS)
                                        counts['filters'].update(name for name in FILTERS if fs[name]['reject'])
                                        counts['totals']['survivors']+=survivor;counts['totals']['retained']+=keep
                                    except Exception as exc:
                                        reason=f'{type(exc).__name__}: {exc}'
                                        row.update(status='fault',retained=False,rejection_reasons=['pair_fault'],reason=reason,
                                                   evaluation=row.get('evaluation',dict(status='fault',reason=reason)),
                                                   filters=row.get('filters',{name:dict(status='unknown',reject=False,reason='pair construction/evaluation failed') for name in FILTERS}))
                                        counts['statuses']['fault']+=1
                                        counts['status_reasons']['fault:'+row['reason']]+=1
                                    row['seconds']=time.monotonic()-tick
                                    row['timings']=phase_timings
                                    counts['timings'].update(phase_timings)
                                    counts['rejections'].update(row['rejection_reasons']);counts['totals']['pairs']+=1
                                    write_started=time.monotonic()
                                    line=json.dumps(row,separators=(',',':'),check_circular=False)+'\n'
                                    if row['retained']:write_line(retained_pairs,line)
                                    if row['filters']['recoverable_gold']['reject']:write_line(recovered,line)
                                    state['pairs']+=1;write_line(pairs,line)
                                    counts['timings']['record_write']+=time.monotonic()-write_started
                                    state['cursor']=dict(**ctx,phase='draw')
                                    if retained>=args.quota:break
                                specs.close()
                                write(events,dict(event='coverage',**ctx,evaluated=drawn,retained=retained,quota=args.quota,
                                                  stopped_at_quota=retained>=args.quota,draw_budget=args.draws))
                    write(events,dict(event='case',task=task,case=case,status='complete',points=len(points)))
                    counts['totals']['cases_complete']+=1
                    from recovery import table_witness
                    table_witness.cache_clear()
                except Exception as exc:
                    counts['statuses']['case_fault']+=1;counts['rejections']['case_fault']+=1
                    write(events,dict(event='case',task=task,case=case,status='fault',reason=f'{type(exc).__name__}: {exc}'))
                finally:
                    evaluator.finish_case()
                    gold_observations.observations.clear()
                state['done']+=1;progress(task,state['done'],state['total'],start,pairs=state['pairs'])
        summary=dict(task=task,provenance=args._provenance,storage=dict(**directory_bytes(temp),native=native_store.stats),counts={k:dict(v) for k,v in counts.items()},seconds=time.monotonic()-start,completed=True)
        (temp/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        os.rename(temp,final);complete=True
    finally:
        stop.set();thread.join()
        if not complete:
            (temp/'interrupted.json').write_text(json.dumps(dict(completed=False,done=state['done'],pairs=state['pairs'],provenance=args._provenance))+'\n')
        progress(task,state['done'],state['total'],start,pairs=state['pairs'],completed=complete,
                 storage=directory_bytes(final if complete else temp))

def require_evaluator(arclog):
    if arclog.StudyProgram.mutation_policy()!='complete-domain-unique-text-gold-names-v7':
        raise RuntimeError('corpus requires the reviewed v7 unique-text/gold-names mutation policy')
    if not hasattr(arclog.StudyProgram,'relation_source_names_json') or not hasattr(arclog,'study_component_tables'):
        raise RuntimeError('fresh runtime with source names, kept maps and component tables required')
    cls=getattr(arclog,'StudyTaskEvaluator',None)
    if cls is None or not all(hasattr(cls,name) for name in ('gold_tables','finish_case','replay')):
        raise RuntimeError('merged wheel required: StudyTaskEvaluator with gold_tables, finish_case and replay')


def config(args):
    return dict(source_receipt_sha256=_VALIDATED_SOURCE_RECEIPT_SHA256,record_format=RECORD_FORMAT,engine_commit=args._provenance['engine_commit'],wheel_sha256=args._provenance['wheel_sha256'],native_binary_sha256=args._provenance['native_binary_sha256'],**{k:str(v) if isinstance(v,Path) else v for k,v in vars(args).items() if k not in ('worker','jobs','only','engine_commit') and not k.startswith('_')})

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--export',type=Path,default=MAIN_ROOT / 'work/lm/data-full-9fac8128')
    p.add_argument('--tasks',type=Path,default=DATA_ROOT / 'ast/engine/data/tasks')
    p.add_argument('--output',type=Path,default=DATA_ROOT / 'ast/run/corpus-v9')
    p.add_argument('--jobs',type=int,default=4);p.add_argument('--draws',type=int,default=100);p.add_argument('--quota',type=int,default=10)
    p.add_argument('--deadline',type=float,default=1);p.add_argument('--work-cap',type=int,default=1<<20)
    p.add_argument('--session-mib',type=int,help='session budget in MiB; default: authenticated runtime STUDY_SESSION_BYTES');p.add_argument('--seed',type=int,default=4231)
    p.add_argument('--only',nargs='+');p.add_argument('--case-limit',type=int);p.add_argument('--point-limit',type=int)
    p.add_argument('--current',type=Path,default=DATA_ROOT / 'ast/run/CURRENT.json')
    p.add_argument('--runtime-manifest',type=Path,help='explicit immutable candidate receipt; does not change CURRENT')
    p.add_argument('--source-receipt',type=Path,default=Path(__file__).with_name('SOURCES.repository.json'))
    p.add_argument('--min-free-gb',type=float,default=30)
    p.add_argument('--worker',help=argparse.SUPPRESS)
    global ACTIVE_GUARD,ACTIVE_BUILD
    args=p.parse_args()
    args.current=args.current.resolve()
    if args.runtime_manifest is not None:args.runtime_manifest=args.runtime_manifest.resolve()
    args.source_receipt=args.source_receipt.resolve()
    # Tasks parallelize across processes; do not multiply native worker pools.
    for name in ('ARCLOG_THREADS','RAYON_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
        os.environ[name]='1'
    try:selected=select_runtime(args.current,args.runtime_manifest)
    except Exception as exc:p.error(str(exc))
    args._provenance=selected['build']
    import arclog
    require_evaluator(arclog)
    if args.session_mib is None:
        session_bytes=getattr(arclog,'STUDY_SESSION_BYTES',None)
        if type(session_bytes) is not int or session_bytes<=0 or session_bytes%(1024*1024):
            p.error('runtime STUDY_SESSION_BYTES must be a positive whole-MiB integer; otherwise provide --session-mib explicitly')
        # Resolve once in the authenticated parent; launch() forwards the exact
        # effective value to every worker and config() records it for resumes.
        args.session_mib=session_bytes//(1024*1024)
    ACTIVE_BUILD=args._provenance
    if min(args.jobs,args.draws,args.quota,args.session_mib)<=0 or args.deadline<=0 or args.min_free_gb<=0:p.error('positive jobs, draws, quota, session-mib and deadline required')
    args.output=args.output.resolve();args.output.mkdir(parents=True,exist_ok=True)
    ACTIVE_GUARD=DiskGuard(args.output,args.min_free_gb)
    if args.worker:
        expected=json.loads((args.output/'run.json').read_text())
        if expected!=config(args):p.error('worker build/config differs from parent')
        try:worker(args)
        except DiskSpaceStop as exc:
            print(json.dumps(dict(event='disk_guard_stop',task=args.worker,reason=str(exc))),flush=True)
            sys.exit(75)
        return
    try:ACTIVE_GUARD.resume()
    except DiskSpaceStop as exc:
        print(json.dumps(dict(event='disk_guard_stop',reason=str(exc))),flush=True);sys.exit(75)
    all_tasks=args.only or sorted(d.name for d in (args.export/'tasks').iterdir() if (d/'cases.npz').exists())
    pending=[t for t in all_tasks if not (args.output/t).is_dir()]
    manifest=args.output/'run.json';cfg=config(args)
    if manifest.exists() and json.loads(manifest.read_text())!=cfg:p.error('output configuration differs; use a new output directory')
    manifest.write_text(json.dumps(cfg,indent=2)+'\n')
    (args.output/'build.json').write_text(json.dumps(args._provenance,indent=2)+'\n')
    initial_done=len(all_tasks)-len(pending)
    start=time.monotonic();state={'done':initial_done};stop=threading.Event();disk_stopped=threading.Event();failures=[]
    def heartbeat():
        while not stop.wait(1):
            try:free=ACTIVE_GUARD.check()
            except DiskSpaceStop:disk_stopped.set();free=shutil.disk_usage(args.output).free
            progress('tasks',state['done'],len(all_tasks),start,initial_done=initial_done,free_bytes=free,disk_stopped=disk_stopped.is_set())
    def launch(task):
        try:ACTIVE_GUARD.check()
        except DiskSpaceStop:return task,'disk_guard'
        import fcntl
        with (args.output/('.'+task+'.lock')).open('w') as lock:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:return task,'locked by another run'
            if (args.output/task).is_dir():return task,None
            command=[sys.executable,'-B','-u',str(Path(__file__).resolve())]
            for key,value in vars(args).items():
                if key in ('worker','only','jobs') or key.startswith('_') or value is None:continue
                command += ['--'+key.replace('_','-'),str(value)]
            command += ['--worker',task]
            result=subprocess.run(command)
            if result.returncode==75:return task,'disk_guard'
            return task,None if result.returncode==0 and (args.output/task).is_dir() else f'worker exit {result.returncode}'
    progress('tasks',state['done'],len(all_tasks),start,initial_done=initial_done)
    thread=threading.Thread(target=heartbeat,daemon=True);thread.start()
    try:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            todo=iter(pending);jobs={}
            def fill():
                while len(jobs)<args.jobs and not disk_stopped.is_set():
                    try:ACTIVE_GUARD.check()
                    except DiskSpaceStop:disk_stopped.set();break
                    task=next(todo,None)
                    if task is None:break
                    jobs[pool.submit(launch,task)]=task
            fill()
            while jobs:
                done,_=wait(jobs,timeout=1,return_when=FIRST_COMPLETED)
                for future in done:
                    jobs.pop(future)
                    task,error=future.result()
                    if error=='disk_guard':disk_stopped.set()
                    elif error:failures.append(dict(task=task,reason=error));print(json.dumps(failures[-1]),flush=True)
                    else:state['done']+=1
                    progress('tasks',state['done'],len(all_tasks),start,initial_done=initial_done,disk_stopped=disk_stopped.is_set())
                fill()
    finally:stop.set();thread.join()
    totals={k:Counter() for k in ('filters','filter_outcomes','filter_unknown_reasons','statuses','status_reasons','rejections','draw_reasons','timings','totals','code_labels')}
    for task in all_tasks:
        if not (args.output/task/'summary.json').exists():continue
        s=json.loads((args.output/task/'summary.json').read_text())
        for key in totals:totals[key].update(s['counts'].get(key,{}))
    summary=dict(provenance=args._provenance,disk_stopped=disk_stopped.is_set(),storage=directory_bytes(args.output),done=state['done'],total=len(all_tasks),failures=failures,counts={k:dict(v) for k,v in totals.items()},seconds=time.monotonic()-start)
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary),flush=True)
    if disk_stopped.is_set():sys.exit(75)
    if failures:sys.exit(1)

if __name__=='__main__':main()
