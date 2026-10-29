"""One read-only joined analysis entry point; grades exist only in memory.

read_pair(pair_id, paths=None) / read_pairs(paths=None) join by pair_id. Every
store is opened mode=ro; no native evaluation, schema changes, or write access
is needed. Optional missing/stale pass results remain visible as open inputs.
"""
from functools import lru_cache
import hashlib
import importlib
import json
from pathlib import Path
import sqlite3
import sys

HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parents[2]),str(HERE.parent)]
from study_paths import CODE_ROOT,DATA_ROOT
from run import digest
from result_grade import grade_results


@lru_cache(maxsize=1024)
def _hash(path,signature):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def file_hash(path):
    p=Path(path).resolve();s=p.stat()
    return _hash(str(p),(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns))


def default_paths():
    root=DATA_ROOT/'ast/run'
    return dict(base=root/'mech/labels.sqlite3',witness_tests=root/'mech/settled.sqlite3',
                normal=root/'mech2/normal.sqlite3',fit_split=root/'mech3/step4.sqlite3',
                lib_search=root/'mech4/lib.sqlite3',target_comparison=root/'mech5/targets.sqlite3',
                judge_outcomes=root/'mech/judge.sqlite3')


def _open(path):
    return sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True,timeout=30)




class StudyReader:
    def __init__(self,*,paths=None):
        self.paths=default_paths();self.paths.update(paths or {})
        self.base=_open(self.paths['base']);self.normal_reader=None
        from source_read import SourceReader
        self.sources=SourceReader(CODE_ROOT)
        try:
            from mech2.read_normal import NormalReader
            self.normal_reader=NormalReader(database=self.paths['normal'],base_database=self.paths['base'])
        except (ImportError,OSError,sqlite3.Error):pass

    def close(self):
        self.base.close();self.sources.close()
        if self.normal_reader is not None:self.normal_reader.close()
    def __enter__(self):return self
    def __exit__(self,*_):self.close()

    def _optional(self,name,module,function,base,sha):
        path=self.paths[name]
        if not Path(path).exists():return dict(status='open',valid=False,reason=name+' store absent')
        try:
            fn=getattr(importlib.import_module(module),function)
            return fn(path,base['pair_id'],source_sha256=base['source_sha256'],base_result_sha256=sha)
        except Exception as error:
            return dict(status='open',valid=False,reason=str(error),error_type=type(error).__name__)

    def _fit(self,base,sha):
        # Prefer the owner's current reader (supports normalized and old rows).
        loaded=self._optional('fit_split','mech3.store','load_step4',base,sha)
        if loaded.get('valid') or not Path(self.paths['fit_split']).exists():return loaded
        # Legacy module used standalone imports. Read its original stored record
        # directly until that reader is merged; no fit/reader policy is copied.
        db=None
        try:
            db=_open(self.paths['fit_split'])
            row=db.execute('SELECT result_sha256,record_json FROM records WHERE pair_id=?',(base['pair_id'],)).fetchone()
            if not row:return loaded
            value=json.loads(row[1])
            loaded=dict(loaded,record=value)  # inspectable even if stale
            if (digest(value)!=row[0] or value['source_sha256']!=base['source_sha256']
                    ):raise ValueError('fit source/result changed')
            if digest(value['code_manifest'])!=value['code_sha256'] or digest(value['config'])!=value['config_sha256']:
                raise ValueError('fit producer receipt changed')
            task=value.get('task_receipt')
            if task and file_hash(task['path'])!=task['sha256']:raise ValueError('fit task changed')
            return dict(status='done',valid=True,record=value,result_sha256=row[0],
                reference=dict(database=str(Path(self.paths['fit_split']).resolve()),table='records',pair_id=base['pair_id'],result_sha256=row[0]))
        except Exception as error:return dict(loaded,reason=str(error))
        finally:
            if db is not None:db.close()

    def _tests(self,base,sha):
        path=self.paths['witness_tests'];valid=[];issues=[]
        if not Path(path).exists():return valid,['witness test store absent']
        db=None
        try:
            db=_open(path)
            items={i['assignment']:i for i in base.get('per_assignment',[])}
            rows=db.execute('SELECT assignment,witness_sha256,source_sha256,base_result_sha256,result_sha256,payload FROM witness_tests WHERE pair_id=?',(base['pair_id'],))
            for assignment,witness,source,prior,result,payload in rows:
                packed=json.loads(payload)
                if (assignment not in items or witness!=digest(items[assignment]['witness'])
                        or source!=base['source_sha256'] or digest(packed)!=result):
                    issues.append('stale witness assignment '+str(assignment));continue
                from fact_objects import unpack
                value=unpack(db,packed)
                from witness_test import witness_inputs
                if value.get('input_sha256') and value['input_sha256']!=witness_inputs(base,items[assignment]):
                    issues.append('witness selector inputs changed');continue
                task=value.get('task_receipt')
                if task and file_hash(task['path'])!=task['sha256']:
                    issues.append('witness task input changed');continue
                valid.append(dict(value,pair_id=base['pair_id'],assignment=assignment,reference=dict(database=str(Path(path).resolve()),table='witness_tests',pair_id=base['pair_id'],assignment=assignment,result_sha256=result)))
        except Exception as error:issues.append(str(error))
        finally:
            if db is not None:db.close()
        return valid,issues

    def _judges(self,base,sha):
        path=self.paths['judge_outcomes'];out=[];issues=[];db=None
        if not Path(path).exists():return out,issues
        try:
            db=_open(path)
            for payload, in db.execute('SELECT payload FROM judge_sessions WHERE pair_id=?',(base['pair_id'],)):
                item=json.loads(payload)
                if item['source_sha256']!=base['source_sha256'] or item['base_result_sha256']!=sha:continue
                final_path=Path(item['final_path']);manifest_path=Path(item['manifest_path']);record_path=Path(item['record_path'])
                for p,h in ((final_path,item['final_sha256']),(manifest_path,item['manifest_sha256']),(record_path,item['record_sha256'])):
                    if file_hash(p)!=h:raise ValueError('judge artifact changed: '+str(p))
                final=json.loads(final_path.read_text());manifest=json.loads(manifest_path.read_text())
                import gzip
                with (gzip.open(record_path,'rt') if record_path.suffix=='.gz' else record_path.open()) as stream:record=json.load(stream)
                if digest(record)!=base['source_sha256']:raise ValueError('judge source differs')
                from judge_merge import merge_final
                from step1_reduce import adapt
                target=dict(adapter=manifest['adapter'],ntrain=item['ntrain'],ntest=item['ntest'])
                merged=merge_final(record,manifest,target,adapt(base,dict(result_sha256=sha)),final,
                    dict(path=str(final_path),sha256=item['final_sha256']))
                out.append(dict(clauses=merged['clauses'],judge_run=merged['judge_run']))
        except Exception as error:issues.append(str(error))
        finally:
            if db is not None:db.close()
        return out,issues

    def _pair(self,row,source_record=None):
        pair,source,code,config,sha,payload=row
        try:
            base=json.loads(payload)
            if (digest(base)!=sha or base['pair_id']!=pair or base['source_sha256']!=source
                    or digest(base['code_manifest'])!=code or digest(base['config'])!=config):
                raise ValueError('base source/code/config/result receipt differs')
            if source_record is not None and digest(source_record)!=source:raise ValueError('source changed')
            reference=dict(database=str(Path(self.paths['base']).resolve()),table='pairs',pair_id=pair,
                           result_sha256=sha,code_sha256=code,config_sha256=config)
            tests,issues=self._tests(base,sha)
            fits=self._fit(base,sha)
            targets=self._optional('target_comparison','mech5.read_targets','load_targets',base,sha)
            # Retained corpus pairs already passed its nonempty TRAIN filter,
            # so globally empty TRAIN+TEST X is ruled out without reading rows.
            # Filtered/recovered pairs need the authoritative original X groups.
            if targets.get('valid') and base.get('retained') is not True:
                try:
                    groups=self.sources.groups(base,source_record)
                    load=importlib.import_module('mech5.read_targets').load_targets
                    import inspect
                    if 'source_groups' in inspect.signature(load).parameters:
                        targets=load(self.paths['target_comparison'],pair,source_sha256=source,
                                     base_result_sha256=sha,source_groups=groups)
                    targets=dict(targets,_source_groups=groups)
                except Exception as error:
                    issues.append('original X empty check unavailable: '+str(error))
                    targets=dict(targets,_source_error=str(error))
            lib=self._optional('lib_search','mech4.read_results','load_result',base,sha)
            normal=(self.normal_reader.load_normal(pair,source_sha256=source,base_result_sha256=sha)
                    if self.normal_reader is not None else self._optional('normal','mech2.read_normal','load_normal',base,sha))
            judges,judge_issues=self._judges(base,sha)
            graded=grade_results(base,witness_tests=tests,fit_split=fits,lib_search=lib,
                target_comparison=targets,judge_outcomes=judges,base_reference=reference)
            program_result=None
            from grades import judge_candidate,program_nonfit
            if (base.get('fits') is False and judge_candidate(graded['evidence'])
                    and not program_nonfit(graded['evidence'].get('program',{}))):
                # Only open judge routes need this source read. A legacy
                # fits=False is a hint, never itself the nonfit certificate.
                try:
                    original=source_record if source_record is not None else self.sources.record(base)
                    from program_evidence import stored_train_nonfit
                    src=base['source']
                    program_result=stored_train_nonfit(original,pair_id=pair,source_sha256=source,
                        source_ref=dict(corpus=str(Path(src['corpus']).resolve()),
                            file=base['task']+'/'+src['file'],line=src['line'],stream=src['stream']))
                    if program_result.get('valid'):
                        graded=grade_results(base,witness_tests=tests,fit_split=fits,lib_search=lib,
                            target_comparison=targets,judge_outcomes=judges,base_reference=reference,
                            program_result=program_result)
                except Exception as error:issues.append('stored program nonfit proof unavailable: '+str(error))
            evidence=graded.pop('evidence')
            targets.pop('_source_groups',None)
            record=dict(pair_id=pair,source_sha256=source,source=base.get('source'),base_result_ref=reference,
                        **{k:base[k] for k in ('task','case','point','operation','K','kind')},**graded)
            results=dict(base=base,witness_tests=tests,fit_split=fits,target_comparison=targets,
                         lib_search=lib,judge_outcomes=judges,normal=normal,program_check=program_result)
            return dict(status='done',valid=True,pair_id=pair,facts={k:record[k] for k in ('task','case','point','operation','K','kind')},
                results=results,normal=normal.get('normal') if normal.get('status') in ('classified','done') else None,
                **graded,record=record,source_sha256=source,base_result_sha256=sha,
                evidence=evidence,evidence_sha256=digest(evidence),result_sha256=digest(record),issues=issues+judge_issues)
        except Exception as error:return dict(status='open',valid=False,pair_id=pair,reason=str(error),error_type=type(error).__name__)

    def read_pair(self,pair_id,*,source_record=None):
        row=self.base.execute('SELECT pair_id,source_sha256,code_sha256,config_sha256,result_sha256,record_json FROM pairs WHERE pair_id=?',(pair_id,)).fetchone()
        return self._pair(row,source_record) if row else dict(status='open',valid=False,pair_id=pair_id,reason='base result absent')

    def read_pairs(self):
        cursor=self.base.execute('SELECT pair_id,source_sha256,code_sha256,config_sha256,result_sha256,record_json FROM pairs ORDER BY rowid')
        for row in cursor:yield self._pair(row)


def read_pair(pair_id,*,paths=None,source_record=None):
    with StudyReader(paths=paths) as reader:return reader.read_pair(pair_id,source_record=source_record)


def read_pairs(*,paths=None):
    with StudyReader(paths=paths) as reader:yield from reader.read_pairs()


def load_grade(database,pair_id,*,source_record=None):
    """Backward-compatible call; database is now the witness journal, not grades."""
    return read_pair(pair_id,paths=dict(witness_tests=database),source_record=source_record)
