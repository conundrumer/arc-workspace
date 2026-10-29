#!/usr/bin/env python3
"""Step 4: fits/extension split with shared whole-program TEST replay.

Reuses stored TRAIN fit and reader tables. Missing TEST evidence is acquired
through the shared evaluator, using fresh full gold replay as the authority.
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
from types import SimpleNamespace
import sqlite3
import sys
import time

sys.dont_write_bytecode=True
from common import CODE_ROOT,DATA_ROOT,OUTPUT_ROOT,HERE,canonical,digest
from fit_contract import stored_program_fit
from observations import original_groups,compare_readers
from reader_projection import pair_readers
from store import Store,GoldCache
from step2_check import valid_base
from run import pair_key

STOP=False


def stop(*_):
    global STOP
    STOP=True


class Worker:
    def __init__(self,args):
        from evaluator import ReplayEvaluator
        from tables import TargetStore,comparison_type
        from nonrender_metadata import MetadataProducer
        import importlib.util
        self.args=args;self.start=time.monotonic();self.last=0;self.counts=Counter();self.reader_counts=Counter()
        self.tasks={};self.current=None;self.producer=None;self.producer_class=MetadataProducer
        self.cfg=json.loads((DATA_ROOT/'ast/run/corpus-v11/run.json').read_text())
        self.ev=ReplayEvaluator(run=CODE_ROOT/'ast/run',deadline=args.deadline,
            artifacts=DATA_ROOT/'judgetool/mech3-fit-replays',reference=CODE_ROOT/'ref/progsynth-relabel')
        self.legacy=self.ev.legacy;self.settings=self.ev.settings
        self.gold_task=None
        self.context=SimpleNamespace(arclog=self.legacy.arclog,legacy=self.legacy,settings=self.settings)
        self.native=TargetStore(self.legacy,CODE_ROOT)
        binary=Path(importlib.util.find_spec('arclog.arclog').origin).resolve()
        files=list(HERE.glob('*.py'))
        files.extend(CODE_ROOT/p for p in ('study_paths.py','ast/run/mech/algorithm.py','ast/run/mech/run.py',
            'ast/run/mech/step2_check.py','ast/run/mech/witness_test.py','ast/run/mech/grades.py',
            'ast/run/mech/read_grades.py','ast/run/next_revision/family_recovery.py',
            'ast/run/filters.py','ast/run/native_tables.py','ast/run/native_storage.py','ast/run/recovery.py',
            'judgetool/evaluator.py','judgetool/tables.py','judgetool/raw_body.py',
            'judge3/nonrender_metadata.py','judge3/definition_binding.py','judge3/render_pair.py','judge3/catalog.py',
            'judge2/render2/headers.py','judge2/render2/body.py','judge2/render2/column_paths.py',
            'judge2/render2/structured.py','ref/progsynth-relabel/engine_verify.py',
            'ref/progsynth-relabel/verify_recovery.py','codex-adm/briefs/judge-decisions.md'))
        files.extend((CODE_ROOT/'judgetool').glob('*.py'))
        files.append(binary)
        self.manifest={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        self.signatures={p:self.signature(Path(p)) for p in self.manifest}
        config=dict(schema='mech3-step4-config-v1',base=str(args.base.resolve()),compare_seconds=args.compare_seconds,
            scope='base label fits, nonDET; per-reader joint projections',
            program_fit='stored TRAIN+TEST proof first; missing TEST uses shared whole mutant and full gold OUT replay',
            spec_sha256=self.manifest[str((CODE_ROOT/'codex-adm/briefs/judge-decisions.md').resolve())],
            runtime=dict(python=str(Path(sys.executable).resolve()),binary=str(binary)),deadline=args.deadline)
        self.output=Store(args.output,self.manifest,config)
        self.gold_cache=GoldCache(self.output)
        self.program_code=digest({p:sha for p,sha in self.manifest.items() if not Path(p).is_relative_to(HERE)})
        self.base=sqlite3.connect(args.base.resolve().as_uri()+'?mode=ro',uri=True);self.base.execute('BEGIN')
        self.scope="(json_extract(record_json,'$.label')='fits' AND upper(json_extract(record_json,'$.kind'))!='DET')"
        self.total=self.base.execute('SELECT count(*) FROM pairs WHERE '+self.scope).fetchone()[0]

    @staticmethod
    def signature(path):
        s=path.stat();return s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns

    def guard(self):
        for name,sha in self.manifest.items():
            p=Path(name);sig=self.signature(p)
            if sig==self.signatures[name]:continue
            if hashlib.sha256(p.read_bytes()).hexdigest()!=sha:
                raise RuntimeError('step 4 dependency changed; restart: '+name)
            self.signatures[name]=sig

    def task(self,task):
        if task not in self.tasks:
            path=(Path(self.cfg['tasks']).resolve()/(task+'.json')).resolve();raw=path.read_bytes();data=json.loads(raw)
            self.tasks[task]=(len(data['train']),len(data['test']),dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest()))
        return self.tasks[task]

    def metadata(self,record,corpus):
        from raw_body import binding
        # Metadata-only context: no ReplayEvaluator instance/artifact directory
        # and no task evaluator are constructed by this pass.
        if self.current!=(record['task'],str(corpus)):
            self.native.cache.clear();self.current=(record['task'],str(corpus))
            self.producer=self.producer_class(engine=self.legacy.arclog,
                read_native=lambda ref,base:self.native.snapshot(ref,base)['_native_reader'],
                corpus=corpus,settings=self.settings,case_inventory=dict(cases=[]))
        exports={s:self.producer.programs.load(record[s+'_sexp'],record if s=='gold' else None)[1]
                 for s in ('gold','mutant')}
        kind=next(v['kind'] for v in exports['gold']['body_views'] if v['body_path']==record['point'])
        if kind.startswith('INIT'):
            adapter=self.producer.produce(record,native_base=corpus/record['task'])
            bindings=adapter['bindings'];policies=adapter['policies']
        else:
            bindings={};policies=[]
            for side in ('gold','mutant'):
                # The shared raw binder is only provenance for the columns
                # selected by actual readers, never a DET all-BODY comparison.
                own=dict(record,gold_sexp=record[side+'_sexp'],
                    native=dict(record['native'],gold=record['native'][side]),
                    evaluation=dict(record['evaluation'],table_indices=dict(record['evaluation']['table_indices'],
                        gold_all=record['evaluation']['table_indices'][side+'_kept'])))
                if side=='mutant':own.pop('relation_source_names',None)
                layout,receipt=binding(self.context,own,native_base=corpus/record['task'])
                bindings[side]=layout;policies.append(dict(side=side,receipt=receipt,
                    original_source_sha256=digest(record),adaptation='side-native BODY schema provenance only'))
        projection=pair_readers(record,exports,bindings)
        projection['metadata_policies']=policies
        projection['source_selectors']={s:bindings[s]['native_selector'] for s in bindings}
        projection['graph_binding']='judge3.definition_binding.definition_node; same-export ids only'
        if kind.casefold()=='det':
            from det_receipt import receipt
            projection['det_transport']=receipt(record,exports,bindings)
        return projection

    def process(self,base,record):
        if digest(record)!=base['source_sha256'] or digest(pair_key(record))!=base['pair_id']:
            raise ValueError('fresh source differs from base receipt')
        ntrain,ntest,task_receipt=self.task(base['task'])
        program=stored_program_fit(record,ntrain,ntest)
        test_evaluations=0;test_reused=False
        if program['fits_test'] is None:
            from out_fit import check
            if self.gold_task!=record['task']:
                self.gold_cache.clear();self.gold_task=record['task']
            cache_key=digest(dict(schema='mech3-program-test-cache-v1',source=base['source_sha256'],base=digest(base),code=self.program_code,
                                 task=task_receipt,deadline=self.args.deadline,ntrain=ntrain,ntest=ntest))
            tested=self.output.load_program(base['pair_id'],cache_key)
            test_reused=tested is not None
            if tested is None:
                tested=check(self.ev,record,ntrain=ntrain,ntest=ntest,gold_cache=self.gold_cache)
                self.output.save_program(base['pair_id'],cache_key,tested)
                counts=tested.get('evaluations',{})
                test_evaluations=sum(counts.values()) if isinstance(counts,dict) else counts
            program['test_check']=tested
            program['test_cache_key']=cache_key
            if tested.get('complete') is True and type(tested.get('fits_test')) is bool:
                program['fits_test']=tested['fits_test']
                program['missing']=[m for m in program.get('missing',[]) if 'test' not in m.lower()]
            program['complete']=all(type(program[k]) is bool for k in ('fits_train','fits_test'))
        value=dict(schema='mech3-step4-record-v1',pair_id=base['pair_id'],source_sha256=base['source_sha256'],
            base_result_sha256=digest(base),program=program,task_receipt=task_receipt,kind=base['kind'],
            reader_difference=dict(complete=False,read_difference=None),
            evaluations=test_evaluations,test_evidence_reused=test_reused)
        try:
            corpus=Path(base['source']['corpus']).resolve();projection=self.metadata(record,corpus)
            value['projection']=projection
            if base['kind'].upper()=='DET':
                value.update(reader_difference=dict(complete=False,read_difference=None,applicable=False,
                    reason='DET is table-only; per-reader mappings supplied to canonical target projector'),
                    grade='Unknown',reader_class='not applicable (DET)',conditional_fit_grade='not applicable (DET)',
                    status='unavailable',missing_steps=['step_3_det_table_regrade'],
                    det_table=dict(projection=projection['det_transport'],
                        stored_train_witnesses=[dict(assignment=a['assignment'],witness_sha256=digest(a['witness']))
                            for a in base.get('per_assignment',[]) if a.get('witness',{}).get('verified') is True],
                        reason='reuse stored witnesses; await qualified shared all-target comparison/recovery evidence'))
                self.native.cache.clear()
                return value
            if not projection['readers']:
                read=dict(complete=True,read_difference=False,reader_count=0,
                          reason='complete native inventory has no reader of changed relation')
            else:
                groups={s:original_groups(record,s,self.native.snapshot(record['native'][s],corpus/record['task']),ntrain,ntest,
                                         self.legacy,projection['source_selectors'][s])
                        for s in ('gold','mutant')}
                read=compare_readers(projection,groups,self.legacy,seconds=self.args.compare_seconds)
            value['reader_difference']=read
        except (OSError,ValueError,KeyError,IndexError,TypeError) as error:
            value['reader_difference'].update(reason=str(error),error_type=type(error).__name__)
        different=value['reader_difference']['read_difference']
        if base['kind'].upper()=='DET':
            value.update(grade='Unknown',reader_class='not applicable (DET)',conditional_fit_grade='not applicable (DET)',
                         status='unavailable',missing_steps=['step_4_det_projection','step_3_det_table_regrade'])
            self.native.cache.clear()
            return value
        value['reader_class']='read difference' if different is True else 'unread difference' if different is False else 'Unknown'
        value['conditional_fit_grade']='fits' if different is True else 'extension' if different is False else 'Unknown'
        value['missing_steps']=[]
        if not program['complete']:value['missing_steps'].append('step_4_test_program_fit_proof')
        if program['complete'] and (program['fits_train'] is False or program['fits_test'] is False):
            value['missing_steps'].append('step_3_nonfitting_target_grade')
        if different is None:value['missing_steps'].append('step_4_reader_projection_or_rows')
        value['grade']=value['conditional_fit_grade'] if program['fits_train'] is True and program['fits_test'] is True else 'Unknown'
        value['status']='complete' if not value['missing_steps'] else 'unavailable'
        self.native.cache.clear()
        return value

    def run(self):
        rows=self.base.execute("SELECT pair_id,source_sha256,code_sha256,config_sha256,result_sha256,record_json FROM pairs "
            'WHERE '+self.scope+" ORDER BY json_extract(record_json,'$.task'),"
            "json_extract(record_json,'$.source.corpus'),json_extract(record_json,'$.source.file'),json_extract(record_json,'$.source.line')")
        stream=None;path=None;line_number=0;record=None;failed=None
        try:
            for done,row in enumerate(rows,1):
                if STOP:return False
                base=valid_base(row);saved=self.output.load(base['pair_id'],base['source_sha256'],row[4])
                ntrain,ntest,task_receipt=self.task(base['task'])
                if saved is not None and saved.get('task_receipt')!=task_receipt:saved=None
                if saved is not None and saved.get('task_receipt')==task_receipt:
                    value=saved;self.counts['resumed']+=1
                else:
                    source=base['source'];current=Path(source['corpus']).resolve()/base['task']/source['file'];wanted=source['line']
                    if path!=current or wanted<line_number:
                        if stream is not None:stream.close()
                        path=current;stream=None;line_number=0;failed=None
                        try:stream=gzip.open(current,'rt')
                        except OSError as error:failed=error
                    if failed is None:
                        try:
                            while line_number<wanted:
                                line=next(stream);line_number+=1
                                if line_number==wanted:record=json.loads(line)
                            if line_number!=wanted:raise ValueError('source line order differs')
                        except (OSError,EOFError,ValueError,StopIteration) as error:
                            failed=ValueError(f'{path}: wanted line {wanted}, reached {line_number}: {type(error).__name__}: {error}')
                    self.guard()
                    try:
                        if failed:raise failed
                        value=self.process(base,record)
                    except (OSError,ValueError,KeyError,IndexError,TypeError) as error:
                        value=dict(schema='mech3-step4-record-v1',pair_id=base['pair_id'],source_sha256=base['source_sha256'],
                            base_result_sha256=row[4],grade='Unknown',reader_class='Unknown',conditional_fit_grade='Unknown',
                            status='unavailable',task_receipt=task_receipt,evaluations=0,kind=base['kind'],
                            program=dict(complete=False,fits_train=None,fits_test=None),
                            reader_difference=dict(complete=False,read_difference=None,reason=str(error)),
                            missing_steps=['step_4_source_or_adapter'],reason=str(error))
                    finally:
                        self.native.cache.clear()
                    self.guard();value=self.output.save(value);self.counts['writes']+=1
                self.counts['grade:'+value['grade']]+=1
                self.counts['evaluations']+=value.get('evaluations',0) if saved is None else 0
                self.counts['test_fit:'+str(value.get('program',{}).get('fits_test'))]+=1
                if base['kind'].upper()=='DET':self.counts['det_grade:'+value['grade']]+=1
                self.reader_counts[value['conditional_fit_grade']]+=1
                self.counts.update('owed:'+s for s in value['missing_steps'])
                elapsed=time.monotonic()-self.start
                if elapsed-self.last>=5:
                    rate=done/max(elapsed,.001)
                    print(f'done={done}/{self.total} elapsed={elapsed:.1f}s rate={rate:.2f}/s '
                          f'ETA={(self.total-done)/max(rate,.001):.1f}s counts={dict(self.counts)}',file=sys.stderr,flush=True)
                    self.last=elapsed
            return True
        finally:
            if stream is not None:stream.close()

    def summary(self,complete):
        value=dict(schema='mech3-step4-summary-v1',complete=complete,total=self.total,counts=dict(self.counts),
            conditional_fit_counts=dict(self.reader_counts),elapsed_seconds=time.monotonic()-self.start,
            output=str(self.args.output.resolve()),code_sha256=self.output.code,config_sha256=self.output.config_hash,
            evaluations=self.counts['evaluations'],grade_scope='nonDET base fits pairs; stronger grades merged by shared reducer',
            blocked=['DET final table grades await qualified n-mech5 comparison/recovery evidence'])
        self.args.summary.write_text(json.dumps(value,indent=2)+'\n')
        print(json.dumps(value,sort_keys=True),file=sys.stderr,flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=DATA_ROOT/'ast/run/mech/labels.sqlite3')
    ap.add_argument('--output',type=Path,default=OUTPUT_ROOT/'step4.sqlite3')
    ap.add_argument('--summary',type=Path,default=OUTPUT_ROOT/'step4-summary.json')
    ap.add_argument('--compare-seconds',type=float,default=1)
    ap.add_argument('--deadline',type=float,default=30)
    args=ap.parse_args()
    if args.compare_seconds<=0:ap.error('positive comparison bound required')
    if args.deadline<=0:ap.error('positive replay deadline required')
    if args.base.resolve()==args.output.resolve():ap.error('base must remain read-only')
    if not args.output.resolve().is_relative_to(OUTPUT_ROOT.resolve()):ap.error('outputs must stay under mech3 data root')
    if not args.summary.resolve().is_relative_to(OUTPUT_ROOT.resolve()):ap.error('summary must stay under mech3 data root')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.summary.parent.mkdir(parents=True,exist_ok=True)
    lock=args.output.with_suffix('.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    os.environ['STUDY_RUN']=str(CODE_ROOT/'ast/run')
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    worker=None
    try:
        worker=Worker(args);complete=worker.run();worker.guard();worker.summary(complete)
    finally:
        if worker is not None:worker.ev.close();worker.output.close();worker.base.close()
        lock.close()
    if not complete:raise SystemExit(130)


if __name__=='__main__':main()
