#!/usr/bin/env python3
"""Acquire the approved common-prefix universe for all points and all stored Xs.

Canonical typed packets, not a replacement of the old kept-only feature store.
No row/model joins: every X names its actual native context and available cache.
"""
import argparse
from collections import Counter
import concurrent.futures
from concurrent.futures.process import BrokenProcessPool
import hashlib
import gc
import json
import multiprocessing
import os
from pathlib import Path
import re
import signal
import sqlite3
import subprocess
import sys
import time
from types import SimpleNamespace

sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT
sys.path[:0]=[str(CODE_ROOT/'judge3'),str(CODE_ROOT/'judgetool'),
    str(CODE_ROOT/'ast/run'),str(CODE_ROOT/'ast/run/mech')]
from dataset_format import write_json
from det_full_body_run import digest, file_sha, read, exclusive
from paused_storage import _write_gzip_chunks, compress_file
from prefix_dev_trial import opening_summary
from framed_jsonl import JsonlWriter, JsonlReader

POLICY='prefix-full-all-candidates-v1'
SCHEMA='study-prefix-full-run-v1'
_GLOBAL={}
_CHECKED={}


def write(path,value):
    write_json(path,value,compact=True)


def ref(path):
    path=Path(path)
    result=dict(path=str(path.resolve()),sha256=file_sha(path),bytes=path.stat().st_size)
    if path.suffix=='.gz':
        side=path.with_name(path.name+'.sha256')
        result['original_sha_ref']=dict(path=str(side.resolve()),sha256=file_sha(side),bytes=side.stat().st_size)
    return result


def valid_file(value):
    try:
        path=Path(value['path'])
        if not path.resolve().is_relative_to(DATA_ROOT.resolve()):return False
        st=path.stat();key=(str(path),st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
        wanted=value['sha256']
        if st.st_size!=value['bytes']:return False
        if _CHECKED.get(key)!=wanted:
            if file_sha(path)!=wanted:return False
            _CHECKED[key]=wanted
        side=value.get('original_sha_ref')
        return side is None or valid_file(side)
    except (OSError,KeyError,TypeError):return False


def normalize_code(receipt):
    out={}
    for name,value in receipt.items():
        path=Path(name)
        try:key=str(path.relative_to(CODE_ROOT))
        except ValueError:
            # Older persistent checkouts have a different prefix, not different
            # source identities. This is a path coordinate, never a name join.
            marker='/model/study/'
            key=str(path).split(marker,1)[1] if marker in str(path) else str(path)
        out[key]=value
    return out


def native_environment():
    # One CPU per native worker, not workers times an inherited Rayon pool.
    for name in ('ARCLOG_THREADS','RAYON_NUM_THREADS','OMP_NUM_THREADS','VECLIB_MAXIMUM_THREADS'):
        os.environ[name]='1'
    sys.path.append(str(MAIN_ROOT/'.venv/lib/python3.12/site-packages'))


def init_worker(options):
    # Typed-cell/wrapper graphs are large: automatic collection in their
    # construction loops repeatedly scans the live graph. Collect once per
    # point, after its evaluator and available cache have been released.
    gc.disable()
    native_environment()
    from source_read import SourceReader
    _GLOBAL.update(options=options,reader=SourceReader(CODE_ROOT),
        labels=sqlite3.connect(Path(options['labels']).resolve().as_uri()+'?mode=ro',uri=True,timeout=30))


def base(pair):
    from export_by_pair_id import PairSource
    return PairSource.base(SimpleNamespace(labels=_GLOBAL['labels']),pair)


def reason(value,phase):
    reasons=[]
    for table in value.get('tables',[]):
        if not table.get('complete'):reasons.append(table.get('reason') or table.get('status','incomplete'))
    text='; '.join(str(x) for x in reasons) or str(value.get('reason') or value.get('status') or 'incomplete')
    text=text[:2000]
    bound=re.search(r'\b(Deadline|TableWork|SessionBytes|AssignmentCount|Assignments|MaxAssignments)\b',text)
    kind=re.search(r'kind=(\d+)',text)
    normalized=re.sub(r'[0-9a-f]{16,}','<hash>',text)
    normalized=re.sub(r'\d+','N',normalized)
    normalized=re.sub(r'\s+',' ',normalized)
    tag=bound.group(1) if bound else ('kind'+kind.group(1) if kind else normalized[:240])
    return dict(status='unavailable',native_status=value.get('status'),phase=phase,
        reason=text,reason_class=phase+':'+tag)


def event(path,value):
    # One writer per point. Immediate fault frames preserve early-stop reporting;
    # ordinary progress batches, rather than fsyncing every successful pair.
    writers=_GLOBAL.setdefault('event_writers',{})
    out=writers.get(path)
    if out is None:
        out=writers[path]=JsonlWriter(path)
    out.write(value)
    if value.get('reason_class'):out.flush()


def close_events():
    for out in _GLOBAL.pop('event_writers',{}).values():out.close()


def event_lines(path):
    if not path.is_file():return 0
    if not path.stat().st_size and not path.with_name(path.name+'.idx.jsonl').is_file():return 0
    with JsonlReader(path) as source:
        return sum(frame['line_count'] for frame in source.frames)


def packet_json_chunks(value):
    """C-encode bounded row batches; never Python-walk individual cells."""
    encode=json.JSONEncoder(ensure_ascii=False,allow_nan=False,separators=(',',':')).encode
    yield from packet_object_chunks(value,encode)
    yield '\n'


def packet_object_chunks(value,encode):
    if not isinstance(value,dict):
        yield encode(value);return
    yield '{'
    for index,(key,item) in enumerate(value.items()):
        if index:yield ','
        yield encode(key);yield ':'
        if key in ('tables','entries') and isinstance(item,(list,tuple)):
            yield '['
            for offset,part in enumerate(item):
                if offset:yield ','
                yield from packet_object_chunks(part,encode)
            yield ']'
        elif key=='rows' and isinstance(item,(list,tuple)):
            yield '['
            for start in range(0,len(item),256):
                if start:yield ','
                # A shallow slice only. C JSON handles nested cells/scalars;
                # output is exactly the old compact JSON order/encoding.
                yield encode(item[start:start+256])[1:-1]
            yield ']'
        else:yield encode(item)
    yield '}'


def packet(path,value):
    # Reuse the sole atomic gzip/SHA/verification codec; codec source and every
    # declared acquisition dependency remain unchanged for stored-result reuse.
    _write_gzip_chunks(path,packet_json_chunks(value))
    return ref(path)


def compress_reports(folder):
    for path in folder.glob('*.json'):compress_file(path)
    return [ref(p) for p in sorted(folder.glob('*.json.gz'))]


def point_key(scope,operation):
    return digest(dict(scope=scope,point_id=operation['point_id'],body_path=operation['body_path'],
        task_input_sha256=operation['task_input_sha256']))


def pair_key(scope,operation,source):
    return digest(dict(policy=POLICY,scope=scope,point_id=operation['point_id'],
        body_path=operation['body_path'],task_input_sha256=operation['task_input_sha256'],
        source_sha256=source['source_sha256']))


def valid_saved(saved,key):
    return (isinstance(saved,dict) and saved.get('key')==key and
        all(valid_file(v) for v in saved.get('files',[])) and bool(saved.get('files')))


def persist_pair(options,operation,root,pair,value):
    destination=root/'pairs'/(pair+'.json')
    write(destination,value)
    # Small streamed discovery; available/G are context refs, not duplicated rows.
    write(Path(options['output'])/'published-pairs'/(pair+'.json'),dict(schema=SCHEMA,
        point_id=operation['point_id'],pair_id=pair,status=value['status'],result=ref(destination)))


def dev_match(options,operation,sources,ev):
    """Exact receipt equality only; never relabel an old runtime or Ident space."""
    from paused_storage import read_json
    from prefix_universe import dependency_receipt
    dev=Path(options['dev'])
    scope=read(dev/'scope.json',{})
    build=options['build']
    if scope.get('runtime')!=build or scope.get('deadline')!=options['deadline'] or scope.get('max_assignments')!=options['max_assignments']:
        return None,'runtime/settings differ'
    expected=normalize_code(dependency_receipt())
    for folder in sorted((dev/'points'/operation['point_id']).glob('*')):
        done=read(folder/'artifact-manifest.json',{})
        if not done or done.get('process',{}).get('returncode')!=0:continue
        acquisition=read(folder/'acquisition.json',{})
        pair=acquisition.get('point',{}).get('pair_id')
        if pair not in sources:continue
        source=sources[pair]
        if acquisition.get('source_sha256')!=source['source_sha256']:continue
        gold=acquisition.get('gold',{});mutant=acquisition.get('mutant',{})
        receipt=gold.get('receipt',{})
        if (gold.get('complete') is not True or mutant.get('complete') is not True
                or receipt.get('runtime')!=ev.receipt or normalize_code(receipt.get('implementation',{}))!=expected):continue
        # Validate original stored file hashes without decoding rows. Old JSON
        # and its losslessly compressed representation are both supported.
        okay=True;files=[]
        for name,wanted in done.get('files',{}).items():
            path=folder/name
            if path.is_file():
                actual=ref(path)
                if actual['sha256']!=wanted['sha256'] or actual['bytes']!=wanted['bytes']:okay=False;break
            else:
                from paused_storage import verified
                archive=path.with_name(path.name+'.gz')
                try:original=verified(archive)
                except (OSError,ValueError,KeyError):okay=False;break
                if original['sha256']!=wanted['sha256'] or original['uncompressed_bytes']!=wanted['bytes']:okay=False;break
                actual=ref(archive)
            files.append(actual)
        if not okay:continue
        refs={}
        for side,name in (('gold','gold'),('x','mutant')):
            path=folder/(name+'.json.gz')
            if not path.is_file():path=folder/(name+'.json')
            if not path.is_file():okay=False;break
            refs[side]=ref(path)
        if okay:return dict(schema='study-prefix-context-v1',scope=options['scope'],
            storage='legacy-complete-packets',point_id=operation['point_id'],
            pair_id=pair,universe=acquisition.get('opening_ref'),gold=refs['gold'],x=refs['x'],
            files=files,legacy_measurement=ref(folder/'artifact-manifest.json')),None
    return None,'no exact complete source/runtime/implementation receipt'


def start_point_profile(operation, pending_count):
    """Profile one small *new* point while doing required work, never a replay."""
    options=_GLOBAL['options'];claim=options.get('profile_claim')
    if not claim or pending_count>8:return
    path=Path(claim);path.parent.mkdir(parents=True,exist_ok=True)
    try:fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    except FileExistsError:return
    with os.fdopen(fd,'w') as stream:stream.write(operation['point_id']+'\n')
    import cProfile,resource
    _GLOBAL['point_profile']=dict(profiler=cProfile.Profile(),point_id=operation['point_id'],
        pending_pairs=pending_count,path=path.with_suffix(''),wall=time.monotonic(),
        cpu=time.process_time(),usage=resource.getrusage(resource.RUSAGE_SELF))
    _GLOBAL['point_profile']['profiler'].enable()


def finish_point_profile():
    active=_GLOBAL.pop('point_profile',None)
    if active is None:return
    import resource,io,pstats
    profiler=active['profiler'];profiler.disable()
    wall=time.monotonic()-active['wall'];cpu=time.process_time()-active['cpu']
    usage=resource.getrusage(resource.RUSAGE_SELF);before=active['usage']
    path=active['path'];profiler.dump_stats(str(path)+'.pstats')
    view=io.StringIO();pstats.Stats(profiler,stream=view).sort_stats('cumulative').print_stats(60)
    path.with_suffix('.txt').write_text(view.getvalue())
    write(path.with_suffix('.json'),dict(schema='prefix-point-profile-v1',point_id=active['point_id'],
        pending_pairs=active['pending_pairs'],wall_seconds=wall,process_cpu_seconds=cpu,
        cpu_wall_ratio=cpu/wall,voluntary_context_switches=usage.ru_nvcsw-before.ru_nvcsw,
        involuntary_context_switches=usage.ru_nivcsw-before.ru_nivcsw,
        profile=str(path)+'.pstats',scope='one new point in the actual run; no extra evaluation; boundary GC excluded'))


def run_point(operation):
    result=None
    try:
        result=_run_point(operation)
        return result
    finally:
        close_events()
        try:finish_point_profile()
        except Exception as error:
            print(json.dumps(dict(stage='profile_write_failed',reason=f'{type(error).__name__}: {error}')),file=sys.stderr,flush=True)
        started=time.monotonic()
        collected=gc.collect()
        if result is not None:
            result['between_point_gc_seconds']=time.monotonic()-started
            result['between_point_gc_collected']=collected


def _run_point(operation):
    options=_GLOBAL['options'];started=time.monotonic();reader=_GLOBAL['reader']
    output=Path(options['output']);scope=options['scope'];stop=output/'operator'/('stop-'+scope+'.json')
    root=output/'points'/operation['point_id']/point_key(scope,operation)
    events=root/'events.jsonl.zst';root.mkdir(parents=True,exist_ok=True)
    pairs=sorted([(p,base(p)) for p in operation['pair_ids']],key=lambda item:(str(item[1]['source']['corpus']),item[1]['source']['file'],item[1]['source']['line']))
    counts=Counter();pending=[];results=[]
    for pair,source in pairs:
        key=pair_key(scope,operation,source);path=root/'pairs'/(pair+'.json');saved=read(path)
        if valid_saved(saved,key):
            counts['reused']+=1;counts[saved['status']]+=1;results.append(dict(pair_id=pair,status=saved['status'],reason=saved.get('reason'),
                reason_class=saved.get('reason_class'),gold_problem=saved.get('gold_problem'),result=ref(path)))
        else:pending.append((pair,source,key))
    if not pending:return finish_point(options,operation,root,counts,results,started)
    if stop.exists():return dict(point_id=operation['point_id'],status='interrupted',counts=dict(counts))
    start_point_profile(operation,len(pending))
    from evaluator import ReplayEvaluator
    from prefix_universe import PrefixPoint
    from provenance import load_build
    ev=ReplayEvaluator(deadline=options['deadline'],artifacts=root/'replays')
    try:
        load_build(ev.arclog,SimpleNamespace(build_receipt=None,engine_commit=options['build']['revision'],wheel=Path(options['build']['wheel'])))
        representative,source=pairs[0]
        # DEV records can supply the representative G+X only within their exact
        # original native context; later candidates get their own context below.
        if pending and (Path(options['dev'])/'points'/operation['point_id']).is_dir():
            reused,why=dev_match(options,operation,{pair:src for pair,src,_ in pending},ev)
            write(root/'dev-reuse.json',dict(reused=reused is not None,reason=why))
            if reused:
                pair,src,key=next(row for row in pending if row[0]==reused['pair_id'])
                context=root/'contexts'/'dev-reused.json';write(context,reused)
                result=dict(schema=SCHEMA,key=key,scope=scope,pair_id=pair,point_id=operation['point_id'],status='complete',
                    source_sha256=src['source_sha256'],storage='legacy-complete-packets',context=ref(context),
                    acquisition=reused['x'],files=[ref(context),reused['legacy_measurement'],*reused['files']],reused_dev=True)
                persist_pair(options,operation,root,pair,result);pending=[row for row in pending if row[0]!=pair]
                results.append(dict(pair_id=pair,status='complete',result=ref(root/'pairs'/(pair+'.json'))));counts.update(complete=1,reused=1)
        if not pending:return finish_point(options,operation,root,counts,results,started)
        original=reader.record(source)
        if original['task']!=operation['task'] or original['case']!=operation['case'] or original['point']!=operation['body_path']:
            raise ValueError('source does not match frozen point identity')
        context_dir=root/'contexts'/str(time.time_ns());native=context_dir/'native'
        with PrefixPoint(ev,original,max_assignments=options['max_assignments'],artifacts=native) as point:
            if point.task_input_sha256!=operation['task_input_sha256']:
                raise ValueError('task inputs changed after the run scope was frozen')
            shared={};opening=opening_summary(point.report,point.opening_ref)
            opening_files=compress_reports(native)
            gold=point.acquire();gold_ref=packet(context_dir/'gold.json.gz',gold)
            for table in gold.get('tables',[]):
                if table.get('role')=='prefix_available' and table.get('complete'):
                    shared[table['table']]=point.available.get(table['table'],(None,))[0]
            context=dict(schema='study-prefix-context-v1',scope=scope,point_id=operation['point_id'],
                storage='body-plus-native-cached-available-refs',opening=opening,
                gold=gold_ref,files=[gold_ref,*opening_files],source_sha256=source['source_sha256'],
                universe_ref=point.report.get('universe_ref'),ident_namespace=point.report.get('ident_namespace'))
            # All private reports retain their original logical SHA references;
            # paused_storage.read_json resolves verified .gz siblings directly.
            if point.sequence:context['files']+=compress_reports(native/('acquisition-'+str(point.sequence).zfill(5)))
            context_ref_path=context_dir/'context.json';write(context_ref_path,context);context_ref=ref(context_ref_path)
            gold_problem=None if gold.get('complete') else reason(gold,'gold')
            blocked=(not point._opening_complete() or point._available_terminal is not None
                or any(t.get('role')=='prefix_available' and not t.get('complete') for t in gold.get('tables',[])))
            context_problem=reason(gold,'point') if blocked else None
            if gold_problem:event(events,dict(point_id=operation['point_id'],**gold_problem))
            del gold
            for pair,src,key in pending:
                if stop.exists():break
                if context_problem:
                    result=dict(schema=SCHEMA,key=key,scope=scope,pair_id=pair,point_id=operation['point_id'],
                        source_sha256=src['source_sha256'],context=context_ref,**context_problem,
                        files=[context_ref,*context['files']])
                else:
                    record=reader.record(src)
                    try:value=point.acquire(mutant_record=record)
                    except Exception as error:value=dict(status='unavailable',complete=False,reason=f'{type(error).__name__}: {error}',tables=[])
                    available_refs=[];tables=[]
                    for table in value.get('tables',[]):
                        if (table.get('role')=='prefix_available' and table['table'] in shared
                                and table.get('receipt',{}).get('reused_on_same_native_universe') is True
                                and point.available.get(table['table'],(None,))[0]==shared[table['table']]):
                            available_refs.append(dict(table=table['table'],role='prefix_available',
                                context=context_ref,packet=gold_ref,packet_table=table['table'],
                                certificate='native available_cached + canonical adapter exact fingerprint',
                                receipt=table['receipt']))
                        else:tables.append(table)
                    stored=dict(value,schema='study-prefix-compact-acquisition-v1',
                        native_packet_schema=value.get('schema'),tables=tables,available_refs=available_refs,context=context_ref)
                    acquisition=packet(context_dir/'pairs'/(pair+'.json.gz'),stored)
                    evidence=compress_reports(native/('acquisition-'+str(point.sequence).zfill(5))) if point.sequence else []
                    problem={} if value.get('complete') else reason(value,'candidate')
                    result=dict(schema=SCHEMA,key=key,scope=scope,pair_id=pair,point_id=operation['point_id'],
                        source_sha256=src['source_sha256'],context=context_ref,acquisition=acquisition,
                        native_seconds=value.get('receipt',{}).get('native_seconds'),
                        status='complete' if value.get('complete') else 'unavailable',
                        files=[context_ref,acquisition,*context['files'],*evidence])
                    result.update(problem)
                    if problem:event(events,dict(point_id=operation['point_id'],pair_id=pair,**problem))
                    del value,stored
                result['gold_problem']=gold_problem
                persist_pair(options,operation,root,pair,result)
                counts[result['status']]+=1;counts['acquired']+=1
                results.append(dict(pair_id=pair,status=result['status'],reason=result.get('reason'),
                    reason_class=result.get('reason_class'),gold_problem=result.get('gold_problem'),result=ref(root/'pairs'/(pair+'.json'))))
                event(events,dict(progress=True,point_id=operation['point_id'],pair_id=pair,status=result['status']))
        return finish_point(options,operation,root,counts,results,started)
    finally:ev.close()


def finish_point(options,operation,root,counts,results,started):
    done=len(results)==len(operation['pair_ids'])
    gold_unknown=[v['gold_problem'] for v in results if v.get('gold_problem')]
    summary=dict(schema=SCHEMA,point_id=operation['point_id'],scope=options['scope'],
        status='complete' if done and not counts['unavailable'] and not gold_unknown else ('unavailable' if done else 'interrupted'),
        coverage_complete=done,total_pairs=len(operation['pair_ids']),counts=dict(counts),pairs=results,
        reason_classes=dict(Counter(v['reason_class'] for v in results if v.get('reason_class'))+Counter(v['reason_class'] for v in gold_unknown)),
        reasons=list(dict.fromkeys([v['reason'] for v in results if v.get('reason')]+[v['reason'] for v in gold_unknown]))[:8],
        seconds=time.monotonic()-started,join='canonical-prefix-packets; requires features metadata/Tn join, not kept-store replacement')
    write(root/'result.json',summary)
    write(Path(options['output'])/'published-points'/(operation['point_id']+'.json'),
        dict(schema=SCHEMA,point_id=operation['point_id'],scope=options['scope'],status=summary['status'],
            coverage_complete=done,result=ref(root/'result.json')))
    return {k:v for k,v in summary.items() if k!='pairs'}


def source_scope(ev,build,args):
    from prefix_universe import dependency_receipt
    from case_cache_keys import implementation_names,signature
    import evaluator
    code=normalize_code(dependency_receipt())
    path=Path(evaluator.__file__)
    names=implementation_names(str(path),signature(path))
    if names is None:raise ValueError('cannot authenticate canonical evaluator source closure')
    code.update(normalize_code({str((path.parent/name).resolve()):file_sha(path.parent/name) for name in names}))
    code.update(normalize_code({str(CODE_ROOT/'ast/run/mech/source_read.py'):file_sha(CODE_ROOT/'ast/run/mech/source_read.py'),
        str(CODE_ROOT/'judge3/export_by_pair_id.py'):file_sha(CODE_ROOT/'judge3/export_by_pair_id.py')}))
    return dict(policy=POLICY,runtime=build,runtime_receipt=ev.receipt,code=code,
        deadline=args.deadline,max_assignments=args.max_assignments,
        worker_implementation=ref(Path(__file__)))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--selection',type=Path,default=DATA_ROOT/'codex-adm/n-featapi/prefix-assignment-design/store-inventory.json')
    p.add_argument('--runtime',type=Path,required=True)
    p.add_argument('--labels',type=Path,default=DATA_ROOT/'ast/run/mech/labels.sqlite3')
    p.add_argument('--output',type=Path,default=DATA_ROOT/'judgetool/prefix-full-v1')
    p.add_argument('--dev',type=Path,default=DATA_ROOT/'judgetool/prefix-dev-trial/9173dfe2')
    p.add_argument('--workers',type=int,default=int(os.environ.get('ARC_HEAVY_CPUS','1')))
    p.add_argument('--deadline',type=float,default=30)
    p.add_argument('--max-assignments',type=int,default=None)
    p.add_argument('--repeat-limit',type=int,default=3)
    p.add_argument('--continue-after-stop',action='store_true',help='explicit operator continuation after diagnosed repeated class')
    p.add_argument('--profile-one-new-point',action='store_true',help='cProfile one new point with at most8 pending pairs during normal work')
    args=p.parse_args();native_environment();started=time.monotonic()
    granted=int(os.environ.get('ARC_HEAVY_CPUS',str(args.workers)))
    if not 1<=args.workers<=granted:raise ValueError('workers must fit the run_heavy CPU grant')
    if args.repeat_limit<2:raise ValueError('repeat-limit must be at least2')
    for path in (args.output,args.runtime,args.dev,args.selection,args.labels):
        if not path.resolve().is_relative_to(DATA_ROOT.resolve()):raise ValueError('paths must stay under DATA_ROOT')
    selection=read(args.selection);operations=[]
    for group in selection['groups']:
        operations.append(dict(point_id=Path(group['path']).name,task=group['task'],case=group['case'],
            body_path=group['body_path'],kind=group['kind'],pair_ids=group['pair_ids']))
    if len(operations)!=6016 or sum(len(v['pair_ids']) for v in operations)!=75321:
        raise ValueError('selection is not the approved6016-point/75321-pair scope')
    if len({v['point_id'] for v in operations})!=len(operations):raise ValueError('duplicate point')
    ids=[pair for v in operations for pair in v['pair_ids']]
    if len(set(ids))!=len(ids):raise ValueError('duplicate pair')
    build=read(args.runtime/'ready.json')
    from evaluator import ReplayEvaluator
    ev=ReplayEvaluator(deadline=args.deadline,artifacts=args.output/'operator/replays')
    try:
        scope=source_scope(ev,build,args)
        task_inputs={}
        for operation in operations:
            task=operation['task']
            if task not in task_inputs:task_inputs[task]=file_sha(Path(ev.cfg['tasks'])/(task+'.json'))
            operation['task_input_sha256']=task_inputs[task]
    finally:ev.close()
    # Driver storage/provenance is retained but does not invalidate acquisitions.
    key_scope={k:v for k,v in scope.items() if k!='worker_implementation'};scope_key=digest(key_scope)
    options=dict(scope=scope_key,build=build,output=str(args.output),labels=str(args.labels),
        deadline=args.deadline,max_assignments=args.max_assignments,dev=str(args.dev),
        profile_claim=str(args.output/'operator'/'profiles'/(scope_key+'-'+str(time.time_ns())+'.claim'))
            if args.profile_one_new_point else None)
    operations.sort(key=lambda v:(v['task'],v['case'],v['body_path']))
    args.output.mkdir(parents=True,exist_ok=True)
    stop=args.output/'operator'/('stop-'+scope_key+'.json')
    with exclusive(args.output/'operator/run.lock'):
        if stop.exists() and not args.continue_after_stop:
            print(json.dumps(dict(status='stopped',reason='repeated class already recorded for this exact scope; diagnose or explicitly --continue-after-stop',stop=str(stop))),flush=True);return 2
        if stop.exists():
            stop.rename(stop.with_name(stop.stem+'-continued-'+str(time.time_ns())+'.json'))
        write(args.output/'operator'/('scope-'+scope_key+'.json'),dict(scope=scope,
            selection=ref(args.selection),workers=args.workers,repeat_limit=args.repeat_limit))
        seen={};reason_counts=Counter();results=[];progress=Counter();cursor={};active={}
        interrupted=False
        def halt(signum,frame):
            nonlocal interrupted
            interrupted=True
            if not stop.exists():write(stop,dict(status='interrupted',signal=signum,scope=scope_key))
        signal.signal(signal.SIGTERM,halt);signal.signal(signal.SIGINT,halt)
        def drain():
            for future,(operation,path) in list(active.items()):
                if not path.is_file() or not path.with_name(path.name+'.idx.jsonl').is_file():continue
                position=cursor.get(str(path),0)
                with JsonlReader(path) as stream:
                    for number,line in enumerate(stream.iter_lines(start_line=position+1),position+1):
                        value=json.loads(line)
                        if value.get('progress'):progress[value['status']]+=1
                        elif value.get('reason_class'):
                            identity=(scope_key,operation['point_id'],value.get('pair_id'),value['reason_class'])
                            if identity not in seen:
                                seen[identity]=True;reason_counts[value['reason_class']]+=1
                                print(json.dumps(dict(stage='unavailable',**value)),flush=True)
                                if reason_counts[value['reason_class']]>=args.repeat_limit and not stop.exists():
                                    write(stop,dict(status='stopped',scope=scope_key,reason_class=value['reason_class'],
                                        occurrences=reason_counts[value['reason_class']],last=value))
                        # Readers expose only committed frames; resume is by lines.
                        cursor[str(path)]=number
        ctx=multiprocessing.get_context('spawn');iterator=iter(operations)
        def submit(pool):
            while len(active)<args.workers and not stop.exists():
                try:op=next(iterator)
                except StopIteration:break
                log=args.output/'points'/op['point_id']/point_key(scope_key,op)/'events.jsonl.zst'
                # Historical events were already classified in their run. A
                # resume reuses terminal pairs; count only new observations.
                cursor[str(log)]=event_lines(log)
                active[pool.submit(run_point,op)]=(op,log)
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=ctx,
                initializer=init_worker,initargs=(options,)) as pool:
            submit(pool);last_print=0
            while active:
                concurrent.futures.wait(active,timeout=1,return_when=concurrent.futures.FIRST_COMPLETED)
                drain()
                for future in [f for f in active if f.done()]:
                    op,path=active.pop(future)
                    try:result=future.result()
                    except BaseException as error:
                        result=dict(point_id=op['point_id'],**reason(
                            dict(status='unavailable',reason=f'{type(error).__name__}: {error}'),
                            'worker:'+type(error).__name__))
                        reason_counts[result['reason_class']]+=1
                        failed=args.output/'operator'/'worker-failures'/(op['point_id']+'.json')
                        write(failed,result)
                        write(args.output/'published-points'/(op['point_id']+'.json'),dict(schema=SCHEMA,
                            scope=scope_key,point_id=op['point_id'],status='unavailable',coverage_complete=False,
                            reason=result['reason'],reason_class=result['reason_class'],result=ref(failed)))
                        # A broken native/process pool is systematic; stop now.
                        if isinstance(error,BrokenProcessPool) or reason_counts[result['reason_class']]>=args.repeat_limit:
                            write(stop,result)
                    results.append(result)
                submit(pool)
                if time.monotonic()-last_print>=10 or not active:
                    report=dict(schema=SCHEMA,scope=scope_key,done_points=len(results),total_points=len(operations),
                        active_points=len(active),seconds=time.monotonic()-started,counts=dict(Counter(v['status'] for v in results)),
                        pair_counts=dict(sum((Counter(v.get('counts',{})) for v in results),Counter())),
                        observed_pairs=dict(progress),unavailable_classes=dict(reason_counts),stopped=stop.exists(),
                        between_point_gc_seconds=sum(v.get('between_point_gc_seconds',0) for v in results),
                        acquisition_only=True,features_join='not yet applied; use exact canonical packet/context refs')
                    write(args.output/'summary.json',report);print(json.dumps(report),flush=True);last_print=time.monotonic()
        return 2 if stop.exists() or interrupted else 0


if __name__=='__main__':raise SystemExit(main())
