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

POLICY='native-edited-sites-v1'
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
        self.audit=Path(audit_path).open('w') if audit_path else None
        self.runtime=None;self.survey=survey;self.survey_counts=Counter();self.seen_text={};self.seen_canonical={}

    def close(self):
        if self.audit:self.audit.close()
        self.gold.clear()

    def _cache(self):
        if self.cache is not None:return
        self.cache={}
        if not self.cache_path.exists():return
        try:
            receipt=json.loads(self.cache_path.with_suffix('.receipt.json').read_text())
            if receipt['policy']!=POLICY or file_sha(self.cache_path)!=receipt['sha256']:
                raise ValueError('static pruning cache receipt differs')
            if receipt['reader_sha256']!=file_sha(__file__):raise ValueError('static pruning cache reader changed')
            for raw in self.cache_path.read_text().splitlines():
                row=json.loads(raw);key=row['pair_id']
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
        mutant=gold.construct_identity(json.dumps(record['identity']))
        stored=arclog.StudyProgram.from_sexp(record['programs']['mutant'],arclog.DecodeSettings.corpus())
        if mutant.decode_stream()!=stored.decode_stream():
            raise ValueError('stored mutant differs from exact native mutation stream')
        if hasattr(mutant,'static_prune_json'):
            result=json.loads(mutant.static_prune_json(survey=self.survey))
        else:
            # Older static-prune runtimes already export both the classifier
            # and the editor's complete original->mutant path correspondence.
            # Join those native keys; do not reconstruct a path or a law.
            result=json.loads(mutant.as_program().static_prune_json())
            exported=json.loads(mutant.render_json())
            edited={tuple(e['at']) for e in record['identity']['edits'] if e['replacement'] is not None}
            mapped={tuple(row['after_path']):row['before_path']
                    for row in exported['source_path_correspondence']
                    if row['status']=='replaced' and tuple(row['before_path']) in edited and row['after_path'] is not None}
            result['matches']=[dict(m,original_atom_paths=[mapped[tuple(m['path'])]])
                               for m in result['matches'] if tuple(m['path']) in mapped]
        if result.get('schema')!='arclog-static-prune-v1':raise ValueError('unknown native pruning schema')
        matches=result['matches']
        if any(m['class'] not in CLASSES or not m['original_atom_paths'] for m in matches):
            raise ValueError('incomplete native changed-site conclusion')
        answer=dict(status='matched' if matches else 'unmatched',matches=matches)
        if self.survey:
            context=(base['task'],base['case'],json.dumps(base['point']),hashlib.sha256(text.encode()).hexdigest())
            exact=(context,record['programs']['mutant'])
            duplicate=self.seen_text.get(exact)
            self.seen_text.setdefault(exact,base['pair_id'])
            self.survey_counts['text_checked']+=1;self.survey_counts['text_duplicates']+=duplicate is not None
            view=result.get('survey',{});g=view.get('gold',{});m=view.get('candidate',{})
            evidence=dict(exact_text_duplicate_of=duplicate,canonical_status='unavailable')
            if g.get('status')==m.get('status')=='complete':
                # Compare the full native canonical AST, not just its hash.
                current=json.dumps(m['rendering'],sort_keys=True,separators=(',',':'))
                canonical=(context,current)
                previous=self.seen_canonical.get(canonical)
                self.seen_canonical.setdefault(canonical,base['pair_id'])
                equal_gold=g['rendering']==m['rendering']
                self.survey_counts['canonical_checked']+=1
                self.survey_counts['canonical_duplicates']+=previous is not None
                self.survey_counts['canonical_equal_gold']+=equal_gold
                evidence.update(canonical_status='complete',canonical_duplicate_of=previous,canonical_equal_gold=equal_gold)
            else:self.survey_counts['canonical_unavailable']+=1
            answer['survey']=evidence
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
        if self.audit:
            self.audit.write(json.dumps(dict(identity,**result),sort_keys=True,separators=(',',':'))+'\n');self.audit.flush()
        return result
