"""One existing-bindings replay evaluator for judgetool and mechanical callers.

Normal replay returns assignment-labelled entries. We postfilter those entries;
we do not install saved values, and absence of compatible entries is unknown.
Historical adapters/comparator are imported read-only from P, not reimplemented.
"""
from __future__ import annotations
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
S = HERE.parent
P = S/'ref/progsynth-relabel'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def sha(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def read_json(path):
    path = Path(path)
    if path.suffix == '.gz':
        with gzip.open(path, 'rt') as stream:
            return json.load(stream)
    return json.loads(path.read_text())


def legacy_helpers(run=S/'ast/run', reference=P):
    os.environ['STUDY_RUN'] = str(run)
    sys.path[:0] = [str(run), str(reference)]
    key = '_judgetool_historical_adapter'
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, reference/'engine_verify.py')
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
    return sys.modules[key]


def open_source(path, *, expected_sha256=None):
    """Open an exact JSON/gzip record; source identity uses decoded canonical JSON."""
    record = read_json(path)
    digest = sha(record)
    if expected_sha256 is not None and digest != expected_sha256:
        raise ValueError('source record canonical hash differs')
    return record, dict(path=str(Path(path).resolve()), sha256=digest)


class ReplayEvaluator:
    """Reuse one native task evaluator; callers close/finish between source cases.

    No native endpoint/session API is used. Limits reset for each native
    gold_tables operation, exactly as in P's calibration. They are not a
    cumulative search budget. A mechanical search must bound its own total
    candidate work and retain every per-operation native receipt.
    """
    def __init__(self, *, run=S/'ast/run', config=None, deadline=30,
                 artifacts=DATA_ROOT / 'judgetool/replays', reference=P):
        self.run, self.reference = Path(run), Path(reference)
        self.cfg = read_json(config or DATA_ROOT/'ast/run/corpus-v11/run.json')
        self.cfg['tasks'] = str(Path(self.cfg['tasks']).resolve())
        self.legacy = legacy_helpers(self.run, self.reference)
        self.arclog = self.legacy.arclog
        self.deadline = deadline if deadline is not None else self.cfg['deadline']
        self.work_cap = self.cfg['work_cap'] * (64 if deadline is not None else 1)
        self.settings = self.arclog.DecodeSettings(deadline_seconds=self.deadline,
                                                   table_work_cap=self.work_cap, rule_tests=False)
        self.artifacts = Path(artifacts).resolve()
        roots=(DATA_ROOT/'judgetool',DATA_ROOT/'ast/run/mech4',DATA_ROOT/'ast/run/mech5')
        if not any(self.artifacts.is_relative_to(root.resolve()) for root in roots):
            raise ValueError('replay artifacts must stay in judgetool, ast/run/mech4 or ast/run/mech5')
        self.artifacts.mkdir(parents=True, exist_ok=True)
        self.task = None
        self.ev = None
        self.captures = []
        self.target_cache = {}
        self.target_store = None
        self._point_gold = None
        self._point_kept = None
        binary = importlib.util.find_spec('arclog.arclog').origin
        self.runtime = dict(python=str(Path(sys.executable).resolve()), binary=str(Path(binary).resolve()),
                            binary_sha256=hashlib.sha256(Path(binary).read_bytes()).hexdigest())
        self.receipt = dict(schema='judgetool-replay-settings-v1', runtime=self.runtime,
                            config_sha256=sha(self.cfg), deadline_seconds=self.deadline,
                            table_work_cap=self.work_cap, rule_tests=False,
                            session_bytes=self.cfg['session_mib']*1024*1024,
                            budget_scope='one gold_tables operation, not entire candidate search',
                            reference_sha256=hashlib.sha256((self.reference/'engine_verify.py').read_bytes()).hexdigest(),
                            implementation_sha256=sha({name:hashlib.sha256((HERE/name).read_bytes()).hexdigest()
                                for name in ('../study_paths.py','evaluator.py','surface.py','tables.py','checks.py','catalog.py','registry.py','live_targets.py','candidate_train.py','raw_body.py','target_view.py','judge_view.py','judge_tool.py')}))

    def task_evaluator(self, task):
        if self.task != task:
            self.close()
            self.task = task
            self.ev = self.arclog.StudyTaskEvaluator(task, self.cfg['tasks'], self.settings,
                session_bytes=self.cfg['session_mib']*1024*1024, compact=True)
        return self.ev

    def finish_case(self):
        if self.ev is not None:
            self.ev.finish_case()

    def close(self):
        self.finish_case()
        self.ev, self.task = None, None
        if hasattr(self,'target_cache'):self.target_cache.clear()
        self.target_store=None
        self._point_gold=None
        self._point_kept=None

    def gold_tables(self, program):
        """Shared native execution path, also passed as P verifier's evaluator proxy."""
        status, tables = self.ev.gold_tables(program)
        report = json.loads(status) if isinstance(status, str) else status
        native = self.legacy.native(tables)
        self.captures.append(dict(program=program.sexp(), report=report, native=native))
        return status, tables

    def _artifact(self, record, candidate, result):
        key = sha(dict(source=sha(record), candidate=candidate, settings=self.receipt))
        folder = self.artifacts/key
        folder.mkdir(exist_ok=True)
        (folder/'result.json').write_text(json.dumps(result, indent=2, ensure_ascii=False)+'\n')
        (folder/'receipt.json').write_text(json.dumps(dict(source_sha256=sha(record),
            candidate_sha256=sha(candidate), settings=self.receipt), indent=2)+'\n')
        for i, capture in enumerate(self.captures):
            (folder/f'program-{i}.arclog').write_text(capture['program']+'\n')
            (folder/f'engine-{i}.json').write_text(json.dumps(capture['report'], indent=2)+'\n')
            n = capture['native']
            reader = n['_native_reader']
            tables = n['tables']
            # The full returned assignment entries are retained, including other
            # assignments and test entries. They are internal artifacts, not judge output.
            selected_form = result.get('form', int(record['point'][0])+1)
            retained_forms=result.get('retain_forms')
            selected_forms={str(f) for f in retained_forms} if retained_forms is not None else {str(selected_form)}
            with gzip.open(folder/f'entries-{i}.jsonl.gz', 'wt') as stream:
                for t in (t for t, form in enumerate(tables['form']) if result.get('retain_all')
                          or str(form) in selected_forms):
                    for e in reader.bytable[t]:
                        try:
                            entry = reader.entry(e, with_extents=True, projection_stop=False)
                            row = dict(table=t, form=tables['form'][t],
                                       columns=tables['column_names'][t], types=tables['column_types'][t], entry=entry)
                        except Exception as error:
                            row = dict(table=t, entry=e, status='unavailable', reason=str(error))
                        stream.write(canonical(row)+'\n')
        return str(folder)

    def historical(self, record, clause, tables, *, allow_det=False):
        """Reproduce P's exact adapter/comparison, not final policy certification.

        Only the explicit historical reproduction may include changed DETs.
        Legacy OR canonicalization / RULE-to-DET / INIT witness inlining are
        recorded in inserted programs. Normal tool mode must not silently use
        this profile to claim exact submitted-syntax or projected-INIT proof.
        """
        self.task_evaluator(record['task'])
        self.captures = []
        changed = self.legacy.parse(self.legacy.split_forms(record['mutant_sexp'])[int(record['point'][0])])
        start = time.monotonic()
        if changed[0] == 'DET' and not allow_det:
            return dict(engine='excluded', verified=False, reason='DET-kind pairs stay out')
        try:
            result = self.legacy.verify_pair(self, self.settings, record, clause, tables)
        except Exception as error:
            result = dict(engine='error', verified=False, reason=f'{type(error).__name__}: {error}')
        result['seconds'] = round(time.monotonic()-start, 3)
        result['form'] = int(record['point'][0])+1
        result['profile'] = 'historical-P-calibration'
        result['assignment_scope'] = 'normal replay, postfiltered by saved dependency-slot values; not forced intervention'
        if self.captures and self.captures[-1]['report'].get('status') == 'complete':
            result['kept_coverage'] = self._coverage(record, self.captures[-1], result.get('inserted'))
        result['artifact'] = self._artifact(record, dict(clause=clause, profile=result['profile']), result)
        return result

    def _coverage(self, record, capture, inserted=None, form=None):
        n = capture['native']; ts = n['tables']
        if form is None:
            form = int(record['point'][0])+1
        indices = [t for t, f in enumerate(ts['form']) if str(f) == str(form)]
        if not indices:
            return dict(status='unknown', reason='inserted form has no returned table')
        t = indices[0]
        _, train_entries, _ = self.legacy.rows_at(n, t)
        entries = list(train_entries)
        reader = n['_native_reader']
        # filters.rows_at deliberately omits test inputs. Decode those through
        # that same lossless reader; they participate in every current check.
        for index in reader.bytable[t]:
            if reader.entries['example_kind'][index] != 2:
                continue
            raw = reader.entry(index, with_extents=False, projection_stop=False)
            entries.append(dict(entry=index,example=(2,raw['example_index']),model=raw['model'],
                assignment=tuple(sorted((d['relation'],tuple(tuple(r) for r in d['rows'])) for d in raw['assignment'])),
                rows=tuple(sorted({tuple(tuple(c['value']) for c in row) for row in raw['rows']}))))
        from tables import decode_kept,compatible_kept
        saved = [decode_kept(self.legacy, k, ts['det_relations'][t], ts['det_types'][t])
                 for k in record['evaluation']['kept_assignments']]
        slots = set(ts['det_relations'][t])
        groups = []
        other = []
        for a, want in enumerate(saved):
            missing = sorted(slots-set(want))
            for e in entries:
                if not missing and compatible_kept(self.legacy,e['assignment'],want,
                                                    ts['det_relations'][t],ts['det_types'][t]):
                    groups.append(dict(kept_assignment=a, **e))
        selected = {g['entry'] for g in groups}
        other = [e['entry'] for e in entries if e['entry'] not in selected]
        return dict(status='complete' if groups else 'unknown', table=t,
                    det_relations=ts['det_relations'][t], groups=groups,
                    other_assignment_entries=other,
                    rule='saved values on every table dependency slot; absent compatible entry is unknown')

    def replay_program(self, record, program, form, *, candidate=None,retain_all=False,retain_forms=None):
        """Canonical low-level API for tool and n-mech, no copied evaluator.

        Caller supplies the whole generated program including OUT and the
        inserted table's form index. Returns all matched groups; stores ALL
        returned tables/assignments internally. No policy/target claim implied.
        """
        if retain_forms is not None:
            count=len(self.legacy.split_forms(program))
            if (retain_all or not isinstance(retain_forms,(list,tuple))
                    or len(retain_forms)>count
                    or any(type(f) is not int or not 0<=f<count for f in retain_forms)):
                raise ValueError('retain_forms must be bounded original form indices, without retain_all')
            retain_forms=sorted(set(retain_forms))
        self.task_evaluator(record['task'])
        self.captures = []
        start = time.monotonic()
        result = dict(schema='judgetool-replay-v1', verified=False,retain_all=retain_all)
        if retain_forms is not None:result['retain_forms']=retain_forms
        try:
            checked = self.arclog.StudyProgram.from_sexp(program, self.settings)
        except Exception as error:
            result.update(engine='refused', reason=f'{type(error).__name__}: {error}')
        else:
            try:
                self.gold_tables(checked)
                report = self.captures[-1]['report']
                result['engine_report'] = report
                if report.get('status') != 'complete':
                    result.update(engine='incomplete', reason=report.get('reason', report.get('status')))
                else:
                    result.update(engine='ran', kept_coverage=self._coverage(record, self.captures[-1], form=form))
                    if result['kept_coverage']['status'] == 'unknown':
                        result['unknown'] = True
            except Exception as error:
                result.update(engine='incomplete', reason=f'{type(error).__name__}: {error}')
        result['seconds'] = round(time.monotonic()-start, 3)
        result['form'] = form
        result['receipt'] = self.receipt
        result['artifact'] = self._artifact(record, candidate or dict(program=program, form=form), result)
        return result

    def registry_interfaces(self,record):
        from registry import registry_interfaces
        return registry_interfaces(self,record)

    def gold_point_body(self,record):
        """One bounded existing evaluate_pair call; retain only GOLD evidence.

        The certified historical mutant is necessarily evaluated by that API.
        Its verdict and rows are not consumed or written as labeling evidence.
        Native full-gold FITS/Held body evaluation retains recursive owner scope.
        """
        self.task_evaluator(record['task']);self.captures=[]
        start=time.monotonic()
        catalogue=Path(self.cfg['export']).resolve()/'tasks'/record['task']/'cases.npz'
        key=sha(dict(program=record['gold_sexp'],case=record['case'],catalogue=str(catalogue)))
        result=dict(schema='judgetool-gold-point-v1',engine='incomplete',verified=False,
            form=int(record['point'][0]),source_sha256=sha(record),
            route='existing_certified_pair_gold_BODY',receipt=self.receipt,
            native_pair_calls=0,mutant_verdicts_used=False,base_label_writes=0)
        try:
            if self._point_gold is None or self._point_gold[0]!=key:
                sys.path.insert(0,str(CODE_ROOT/'ast'))
                from check_stage1_all import inventory
                names,offsets,ids,flags=inventory(Path(self.cfg['export']).resolve(),record['task'],True)
                case=names.index(record['case']);lo,hi=offsets[case:case+2]
                gold=self.ev.from_stream(ids[lo:hi],[int(flag) for flag in flags[lo:hi]])
                gold_forms = [self.legacy.parse(form) for form in self.legacy.split_forms(gold.sexp())]
                source_forms = [self.legacy.parse(form) for form in self.legacy.split_forms(record['gold_sexp'])]
                if gold_forms != source_forms:
                    raise ValueError('canonical catalogue gold differs from recorded source program')
                self._point_gold=(key,gold)
                self._point_kept=None
            gold=self._point_gold[1]
            point,mutant=self.ev.replay(gold,canonical(record['identity']))
            if list(point.body_path)!=record['point']:
                raise ValueError('certified point differs from requested gold BODY')
            result['native_pair_calls']=1
            report,gobj,mobj=self.ev.evaluate_pair(gold,point,mutant)
            report=json.loads(report) if isinstance(report,str) else report
            del mobj  # Never decode or retain mutant-side rows.
            if 'kept_assignments' in report:
                self._point_kept=report['kept_assignments']
            safe={name:report[name] for name in ('gold_fits','gold_assignments','gold_tables',
                'gold_kept_assignment_map','gold_observation_ref','gold_observation_cached',
                'kept_assignment_count','timings','cache') if name in report}
            safe['kept_assignments']=self._point_kept
            safe['gold_source']=dict(catalogue=str(catalogue),case=record['case'],
                catalogue_sha256=hashlib.sha256(catalogue.read_bytes()).hexdigest(),program_sha256=sha(gold.sexp()))
            safe['gold_train']=[dict(assignment=o['assignment'],train=o['gold_train'])
                               for o in report.get('outputs',[]) if 'gold_train' in o]
            safe['table_indices']={k:v for k,v in report.get('table_indices',{}).items() if k.startswith('gold_')}
            safe['full_det_schemas']=json.loads(gold.choice_evidence_json('[]'))['dets']
            views=json.loads(gold.render_json())['body_views']
            selected=[view for view in views if view['body_path']==record['point']]
            if len(selected)!=1:raise ValueError('native gold point BODY metadata is ambiguous')
            safe['body_view']=selected[0]
            native=self.legacy.native(gobj)
            self.captures.append(dict(program=record['gold_sexp'],report=safe,native=native))
            result.update(gold_report=safe,native_pair_status=report.get('status'),
                gold_OUT_FITS_evaluations=0 if report.get('gold_observation_cached') else 1,
                mutant_OUT_assignment_calls=len(report.get('outputs',[])),
                mutant_BODY_work_included='mutant_clause' in report.get('timings',{}),
                budget_scope='one evaluate_pair native operation, including gold and historical mutant work')
            if (safe.get('gold_tables',{}).get('status')=='complete'
                    and safe.get('gold_fits') is True and self._point_kept is not None
                    and 'gold_kept' in safe['table_indices']):
                result['engine']='ran'
            else:result['reason']='native gold point collection stopped, faulted, or has no full-gold FITS context'
        except Exception as error:
            result['reason']=f'{type(error).__name__}: {error}'
        result['seconds']=round(time.monotonic()-start,3)
        result['artifact']=self._artifact(record,dict(kind='original-gold-point-BODY',identity=record.get('identity')),result)
        return result

    def evaluate(self,record,clause,target,columns=None,compatibility=False,*,explore=False,row_limit=100):
        """Shared checked clause API for tool and n-mech. No grade is produced."""
        if compatibility:return self.historical(record,clause,target['tables'])
        from checks import evaluate
        result=evaluate(self,record,clause,target,columns,explore=explore,row_limit=row_limit)
        if explore:
            result.pop('outcome',None);result.pop('verified',None);result['graded']=False
        return result
