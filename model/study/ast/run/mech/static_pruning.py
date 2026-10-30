"""Native sample-time pruning at the one joined study read boundary.

The optional read-only cache is an acquisition receipt, not pair labels or a
second pair reader. Missing evidence never proves a static match.
"""
from collections import Counter, OrderedDict
import hashlib
import json
from pathlib import Path
import sys
from run import digest
from judge3.framed_jsonl import JsonlReader, JsonlWriter, iter_json
from prune_jsonl import receipt_path

POLICY='native-stored-edited-sites-v2'
CLASSES=frozenset(('unsatisfiable','valid','alias','constant'))


def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda:stream.read(1024*1024),b''):h.update(part)
    return h.hexdigest()


class Pruner:
    def __init__(self,cache_path,*,runtime=None,audit_path=None,survey=False):
        self.cache_path=Path(cache_path);self.runtime_path=Path(runtime) if runtime else None
        self.cache=None;self.cache_error=None;self.gold=OrderedDict();self.arclog=None
        self.counts=Counter();self.rules=Counter();self.primary_rules=Counter();self.kinds=Counter();self.unavailable=Counter()
        self.audit=None;self.audit_rows={}
        if audit_path:
            audit_path=Path(audit_path)
            if not str(audit_path).endswith('.jsonl.zst'):raise ValueError('new pruning audit requires a .jsonl.zst output; keep old runs unchanged')
            try:
                with JsonlReader(self.cache_path) as source:self.cache_path=source.path
            except FileNotFoundError:pass
            identity=dict(policy=POLICY,runtime_ready_sha256=file_sha(self.runtime_path) if self.runtime_path else None,
                cache_path=str(self.cache_path.resolve()),
                cache_sha256=file_sha(self.cache_path) if self.cache_path.is_file() else None)
            source_path=Path(str(audit_path)+'.source.json')
            self.audit=JsonlWriter(audit_path)
            if source_path.exists():
                if json.loads(source_path.read_text())!=identity:
                    self.audit.close();raise ValueError('pruning audit source/config changed; use a new output')
            elif self.audit.committed_lines:
                self.audit.close();raise ValueError('committed pruning audit lacks its source/config receipt')
            else:source_path.write_text(json.dumps(identity,sort_keys=True)+'\n')
            with JsonlReader(audit_path) as source:
                for raw in source.iter_lines(stop_line=self.audit.committed_lines+1):
                    row=json.loads(raw)
                    self.audit_rows[tuple(row[k] for k in ('pair_id','source_sha256','base_result_sha256'))]=row
        self.runtime=None;self.survey=survey;self.survey_counts=Counter();self.seen_text={};self.seen_canonical={}

    def close(self):
        if self.audit:self.audit.close()
        self.gold.clear()

    def _cache(self):
        if self.cache is not None:return
        self.cache={}
        try:
            with JsonlReader(self.cache_path) as source:self.cache_path=source.path
        except FileNotFoundError:return
        except Exception as error:
            self.cache_error=str(error);return
        try:
            receipt=json.loads(receipt_path(self.cache_path).read_text())
            if receipt['policy']!=POLICY or file_sha(self.cache_path)!=receipt['sha256']:
                raise ValueError('static pruning cache receipt differs')
            if receipt['reader_sha256']!=file_sha(__file__):raise ValueError('static pruning cache reader changed')
            for row in iter_json(self.cache_path):
                key=row['pair_id']
                if key in self.cache:raise ValueError('duplicate static pruning acquisition')
                self.cache[key]=row
            if len(self.cache)!=receipt['rows']:raise ValueError('static pruning acquisition coverage differs')
            self.runtime=receipt['runtime']
        except Exception as error:
            self.cache={};self.cache_error=str(error)

    def _native(self,base,record):
        if self.arclog is None:
            import arclog
            if self.runtime_path is None:
                raise ValueError('native static pruning acquisition requires exact ready.json; publish cache for native-free readers')
            ready=json.loads(self.runtime_path.read_text())
            binary=Path(sys.modules['arclog.arclog'].__file__).resolve()
            if Path(sys.executable).resolve()!=Path(ready['python']).resolve():
                raise ValueError('native pruning interpreter differs from selected build')
            # The build receipt and installed binary are retained by content;
            # every acquisition below binds full source and base result SHA.
            from provenance import load_build
            from types import SimpleNamespace
            build=load_build(arclog,SimpleNamespace(build_receipt=None,engine_commit=ready['revision'],wheel=Path(ready['wheel'])))
            self.runtime=dict(build,ready=str(self.runtime_path.resolve()),ready_sha256=file_sha(self.runtime_path),
                revision=ready['revision'],binary=str(binary),binary_sha256=file_sha(binary))
            self.arclog=arclog
        arclog=self.arclog;text=record['programs']['gold']
        gold=self.gold.pop(text,None)
        if gold is None:gold=arclog.StudyProgram.from_sexp(text,arclog.DecodeSettings.corpus())
        self.gold[text]=gold
        while len(self.gold)>32:self.gold.popitem(last=False)
        try:
            stored=arclog.StudyProgram.from_sexp(record['programs']['mutant'],arclog.DecodeSettings.corpus())
        except Exception as error:
            raise ValueError('stored_parse: '+str(error)) from error
        if not hasattr(stored,'stored_static_prune_json'):
            raise ValueError('runtime lacks native stored-form static classifier v2')
        result=json.loads(stored.stored_static_prune_json(gold,json.dumps(record['identity'])))
        if (result.get('schema')!='arclog-static-prune-v1' or
                result.get('acquisition_schema')!='arclog-stored-static-prune-v2'):
            raise ValueError('unknown native stored pruning schema')
        matches=result['matches']
        if any(m['class'] not in CLASSES or not m['original_atom_paths'] for m in matches):
            raise ValueError('incomplete native changed-site conclusion')
        answer=dict(status='matched' if matches else 'unmatched',matches=matches,
                    acquisition_schema=result['acquisition_schema'],changed_sites=result['changed_sites'])
        if self.survey:
            # Survey is optional and is not an acquisition/admission condition.
            answer['survey']=dict(status='unavailable',reason='stored-form canonical survey deferred')
        return answer

    def check(self,base,base_sha,sources,source_record=None):
        self._cache();self.counts['read']+=1
        identity=dict(pair_id=base['pair_id'],source_sha256=base['source_sha256'],base_result_sha256=base_sha)
        try:
            row=self.cache.get(base['pair_id'])
            if row is not None:
                if any(row.get(k)!=v for k,v in identity.items()):raise ValueError('static acquisition source/result changed')
                result={k:row[k] for k in ('status','matches')}
                if result['status'] not in ('matched','unmatched'):raise ValueError('cached static acquisition is unavailable')
            else:
                if self.cache_error:raise ValueError(self.cache_error)
                record=source_record if source_record is not None else sources.record(base)
                if digest(record)!=base['source_sha256']:raise ValueError('static pruning source changed')
                result=self._native(base,record)
        except Exception as error:
            result=dict(status='unavailable',matches=[],reason=str(error),error_type=type(error).__name__)
            self.unavailable[result['reason']]+=1
        if result['status'] in ('matched','unmatched'):
            if not isinstance(result['matches'],list) or bool(result['matches']) != (result['status']=='matched') or any(
                    not isinstance(m,dict) or m.get('class') not in CLASSES or not m.get('rule') or not m.get('original_atom_paths') for m in result['matches']):
                result=dict(status='unavailable',matches=[],reason='invalid static pruning acquisition')
                self.unavailable[result['reason']]+=1
        self.counts[result['status']]+=1
        self.kinds[(str(base['kind']),result['status'])]+=1
        for rule in {m['rule'] for m in result['matches']}:self.rules[rule]+=1
        if result['matches']:self.primary_rules[result['matches'][0]['rule']]+=1
        if self.audit and tuple(identity[k] for k in ('pair_id','source_sha256','base_result_sha256')) not in self.audit_rows:
            row=dict(identity,**result);self.audit.write(row)
            self.audit_rows[tuple(identity[k] for k in ('pair_id','source_sha256','base_result_sha256'))]=row
        return result
