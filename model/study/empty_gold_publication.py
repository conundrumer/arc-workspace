#!/usr/bin/env python3
"""Task-atomic publication transport for native exhaustive empty-gold filtering.

The native operation owns enumeration, editing, source maps and OUT comparison.
This module cannot infer emptiness from sampled or gold-kept tables.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import time
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from study_paths import MAIN_ROOT, CODE_ROOT, REPO_ROOT
sys.path.append(str(MAIN_ROOT / '.venv/lib/python3.12/site-packages'))
from judge3.framed_jsonl import JsonlReader, JsonlWriter, iter_json

SCHEMA = 'empty-gold-publication-v1'
NATIVE_SCHEMA = 'arclog-empty-gold-v1'
POLICY = 'all-train-test-inputs-all-assignments-empty-closure-v1'


# A site whose only argument is a label spelled like its column, as the native
# printer of a program writes it: `(:P *P)`, `(:A A)`, `(:Col ^Col)`. The
# reader requires such a site, and a field site inside a record, bare.
SPELLED_SITE = re.compile(r'\(:([A-Za-z0-9_]+) ([*^]?)\1\)')


def bare_sites(program):
    """The program text with each spelled-out site written as its bare label.

    The case-file writer keeps the elision of the text it reads, so the text
    that it reads must already be bare."""
    return SPELLED_SITE.sub(lambda m: m.group(2) + m.group(1), program)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def file_ref(path):
    path = Path(path).resolve()
    h = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return dict(path=str(path), sha256=h.hexdigest())


def source_ref(corpus, tasks, task):
    paths = [corpus / (task + suffix) for suffix in ('.arclog', '.arcdata')]
    paths += [tasks / (task + '.json')]
    directory = corpus / 'cases' / task
    if directory.exists():
        paths += sorted(p for p in directory.rglob('*') if p.is_file())
    # Includes explicit case-file inventory, so additions/deletions invalidate it.
    return dict(task=task, corpus=str(corpus), tasks=str(tasks),
                files=[file_ref(p) for p in paths])


def validate_report(report, request):
    """Validate API shape, not invented native proof/runtime fields.

    The native entry owns all semantic checks. A case whose edit fails keeps
    its original program, with the case's reason; a case with no program text
    selects original for the whole task. Provenance is our outer envelope.
    """
    if report.get('schema') != NATIVE_SCHEMA or report.get('task') != request['task']:
        raise ValueError('native task report schema/task differs')
    if report.get('selection') not in ('filtered', 'original'):
        raise ValueError('native report lacks a whole-task selection')
    if report['selection'] == 'original' and not report.get('reason'):
        raise ValueError('original fallback lacks reason')
    cases = report['cases']
    if not isinstance(cases, list) or len({c['case'] for c in cases}) != len(cases):
        raise ValueError('native task case inventory duplicated or malformed')
    if not isinstance(report['skipped_cases'], list):
        raise ValueError('native skipped-case inventory missing')
    for case in cases:
        indices = case['old_to_new_clause_index']
        if (not isinstance(indices, list)
                or any(v is not None and (type(v) is not int or v < 0) for v in indices)):
            raise ValueError('native clause map malformed')
        # The native API returns null texts for an unreadable case, and
        # selects the whole original task.
        unreadable_original = (report['selection'] == 'original'
            and case['original_program'] is None and case['filtered_program'] is None)
        if not unreadable_original and not all(
                isinstance(case[name], str) for name in ('original_program', 'filtered_program')):
            raise ValueError('native program text missing')
        if not all(isinstance(case[name], list) for name in ('removed_clauses', 'edited_clauses')):
            raise ValueError('native edit inventory missing')
        if report['selection'] == 'original' and (
                case['filtered_program'] != case['original_program']
                or indices != list(range(len(indices)))
                or case['removed_clauses'] or case['edited_clauses']):
            raise ValueError('native original fallback changes the original task')
    return report


def clause_key(row):
    # Exact source namespace only; no relation-name, ordinal or AST-path guess.
    return (row['task'], row['case'], row['clause_index'], row['relation'], row['clause'])


def audit_check_set(publication, check_set, destination):
    inputs = [check_set] if isinstance(check_set, (str, Path)) else check_set
    expected = []; snapshots = []
    for filename in inputs:
        path = Path(filename).resolve()
        raw = path.read_bytes()
        rows = [json.loads(line) for line in raw.splitlines() if line]
        ref = dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), lines=len(rows))
        snapshots.append(ref)
        expected.extend(dict(row, check_set=ref) for row in rows)
    selected = {}
    for row in iter_json(publication):
        selected[row['task']] = row
    removed = {}
    fallbacks = {}
    for task, row in selected.items():
        # Readback audits also accept the owner's completed native JSONL.
        # This grants no runtime/source binding or publication-resume authority.
        report = row['result'] if row.get('schema') == SCHEMA else row
        if report.get('schema') != NATIVE_SCHEMA:
            raise ValueError('check audit input is not a native task result')
        if report['selection'] != 'filtered':
            fallbacks[task] = report['reason']
            continue
        for case in report['cases']:
            if case.get('reason'):
                fallbacks[(task, case['case'])] = case['reason']
            for clause in case['removed_clauses']:
                value = dict(clause, task=task, case=case['case'])
                removed[clause_key(value)] = value
    expected_by_key = {clause_key(row): row for row in expected}
    report = dict(schema='empty-gold-check-set-audit-v1',
        check_sets=snapshots, check_lines=len(expected),
        publication=file_ref(publication),
        listed_removed=[v for v in expected if clause_key(v) in removed],
        listed_kept=[dict(v, reason=fallbacks.get((v['task'], v['case']), fallbacks.get(v['task'], 'no matching removed source clause')))
                     for v in expected if clause_key(v) not in removed and v['task'] in selected],
        listed_not_processed=[v for v in expected if v['task'] not in selected],
        removed_not_listed=[v for k, v in removed.items() if k not in expected_by_key])
    Path(destination).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report


def lint_records(result, request):
    """Forward exactly the documented report-only native lint fields.

    Findings have task/case/clause_index/relation/labels, no atom_paths or proof.
    The native entry owns singleton/read validation; do not impose extra fields.
    """
    lint = result.get('singleton_double_read_lint', {})
    if lint.get('status') != 'complete':
        return [], dict(status='unavailable', reason=lint.get('reason', 'native lint not acquired'))
    records = []
    for finding_index, finding in enumerate(lint['findings']):
        if (finding['task'] != request['task'] or len(finding['labels']) != 2
                or not all(isinstance(label, str) for label in finding['labels'])
                or not finding['case'] or not isinstance(finding['relation'], str)
                or type(finding['clause_index']) is not int):
            return [], dict(status='unavailable', reason='native lint source identity malformed')
        identity = dict(request_sha256=digest(request), finding_index=finding_index, finding=finding)
        records.append(dict(finding, schema='gold-singleton-double-read-finding-v1',
                            finding_id=digest(identity), finding_index=finding_index, request_sha256=digest(request)))
    return records, dict(status='complete', findings=len(records))


def commit_lint(out, seen, result, request):
    try:
        records, status = lint_records(result, request)
    except (KeyError, TypeError, ValueError) as error:
        # Lint protocol failure is report-only, never a gold rewrite/veto.
        records, status = [], dict(status='unavailable', reason=f'{type(error).__name__}: {error}')
    for record in records:
        key = record['finding_id']
        if key not in seen:
            out.write(record)
            seen.add(key)
    # Commit all findings before the task completion record. A crash between
    # files resumes by finding_id and cannot duplicate or lose a finding.
    out.flush()
    return status


# Adding the materializer does not change native acquisition. Accept this
# exact predecessor's task receipts only under the identical request key.
PUBLISH_COMPATIBLE_PREDECESSORS = ('1ddb3cf79a1952c441f42212559da3e93701aded0aacf5f13a264018fc107415',)

MATERIALIZE_POLICY = 'empty-gold-case-overrides-v2'


def corpus_directory(path):
    path = Path(path).resolve()
    if (path / 'gen').is_dir() and not any(path.glob('*.arcdata')):
        path = path / 'gen'
    if not any(path.glob('*.arcdata')):
        raise ValueError('converted corpus has no task .arcdata files: ' + str(path))
    return path


def atomic_json(path, value):
    from judge3.dataset_format import write_json
    write_json(Path(path), value, compact=True)


def atomic_text(path, value):
    if path.exists() and path.read_text(encoding='utf-8') == value:
        return
    import os
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            out.write(value); out.flush(); os.fsync(out.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def materialize_sources(corpus, task):
    # Reuse the converter's authoritative representative/file dependency walk.
    # Case filenames themselves always come from native case_files below.
    source_path = str(REPO_ROOT / 'src')
    if source_path not in sys.path: sys.path.insert(0, source_path)
    from arclog_convert.train_replay import solver_files
    return {str(p.relative_to(corpus)): file_ref(p)['sha256']
            for p in solver_files(corpus, task) if p.is_file()}


def copy_exact(source, destination):
    """Publish one complete byte copy; never expose a partly written file."""
    import os
    import shutil
    import tempfile
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + destination.name + '-', dir=destination.parent)
    try:
        with os.fdopen(fd, 'wb') as output, Path(source).open('rb') as input_file:
            shutil.copyfileobj(input_file, output, 1024 * 1024)
            output.flush(); os.fsync(output.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def materialize_task(arclog, corpus, gen, control, row, build):
    import shutil
    task = row['task']
    if not task or Path(task).name != task or task in ('.', '..'):
        raise ValueError('unsafe task id')
    report = row['result'] if row.get('schema') == SCHEMA else row
    validate_report(report, dict(task=task))
    inputs = materialize_sources(corpus, task)
    if any(task + suffix not in inputs for suffix in ('.arclog', '.arcdata')):
        raise ValueError('input task file pair missing')
    key = digest(dict(policy=MATERIALIZE_POLICY, result=report, inputs=inputs,
                      native_build=build))
    marker = control / 'tasks' / (task + '.json')
    if marker.exists():
        receipt = json.loads(marker.read_bytes())
        if receipt['key'] != key:
            raise ValueError('completed task has changed inputs/result/build; use a new output version')
        for relative, wanted in receipt['files'].items():
            if file_ref(gen / relative)['sha256'] != wanted:
                raise ValueError('completed materialization bytes changed: ' + relative)
        return 'reused', receipt
    stage = control / 'staging' / (task + '-' + key)
    prepared = stage / 'prepared.json'
    stage_gen = stage / 'gen'
    if prepared.exists():
        receipt = json.loads(prepared.read_bytes())
        if receipt['key'] != key: raise ValueError('prepared task identity differs')
        for relative, wanted in receipt['files'].items():
            if file_ref(stage_gen / relative)['sha256'] != wanted:
                raise ValueError('prepared task bytes changed')
    else:
        # Only our own uncommitted task stage can be discarded/rebuilt.
        if stage.exists(): shutil.rmtree(stage)
        stage_gen.mkdir(parents=True)
        for relative in inputs:
            copy_exact(corpus / relative, stage_gen / relative)
        case_records = []
        if report['selection'] == 'filtered':
            catalog = arclog.case_files(task, (corpus / (task + '.arclog')).read_text(),
                                       (corpus / (task + '.arcdata')).read_text(), str(corpus))
            by_case = {c.case: c for c in catalog}
            if len(by_case) != len(catalog): raise ValueError('native case filename catalog duplicated')
            for case in report['cases']:
                name = case['case']; source = by_case[name]
                if Path(source.file).name != source.file or source.file in ('', '.', '..'):
                    raise ValueError('unsafe native case filename')
                original_data = corpus / 'cases' / task / (source.file + '.arcdata')
                data = original_data.read_text() if original_data.exists() else source.arcdata
                if data is None: raise ValueError('native case has no stored arcdata: ' + name)
                # Native case writer selects exactly the retained DET params;
                # Python does not trim param records or invent case filenames.
                # The publication's program text spells out the sites that the
                # reader requires bare; the writer keeps the text's elision.
                standalone = arclog.case_files(task, bare_sites(case['filtered_program']), data, str(corpus))
                if len(standalone) != 1 or standalone[0].fault is not None:
                    raise ValueError('filtered case files unavailable: ' + name)
                if SPELLED_SITE.search(standalone[0].arclog):
                    raise ValueError('filtered case file keeps a spelled-out site: ' + name)
                destination = stage_gen / 'cases' / task / source.file
                destination.parent.mkdir(parents=True, exist_ok=True)
                Path(str(destination) + '.arclog').write_text(standalone[0].arclog)
                Path(str(destination) + '.arcdata').write_text(standalone[0].arcdata)
                case_records.append(dict(case=name, file=source.file,
                    program_sha256=hashlib.sha256(case['filtered_program'].encode()).hexdigest()))
        if materialize_sources(corpus, task) != inputs:
            raise ValueError('input changed while materializing task')
        files = {str(p.relative_to(stage_gen)): file_ref(p)['sha256']
                 for p in sorted(stage_gen.rglob('*')) if p.is_file()}
        receipt = dict(schema='empty-gold-materialized-task-v1', key=key, task=task,
                       selection=report['selection'], reason=report.get('reason'),
                       result_sha256=digest(report), inputs=inputs, files=files,
                       cases=case_records, policy=MATERIALIZE_POLICY,
                       publication_record_sha256=digest(row), implementation=file_ref(__file__),
                       representative_support=sorted({Path(name).stem for name in inputs
                           if Path(name).parent == Path('.') and Path(name).stem != task}),
                       native_build=build)
        atomic_json(prepared, receipt)
    # Case overrides and support files first; the task pair/ready receipt last.
    # A crash resumes from prepared bytes, without compiling the task again.
    roots = [task + '.arcdata', task + '.arclog']
    order = [name for name in receipt['files'] if name not in roots] + roots
    for relative in order:
        destination = gen / relative
        if destination.exists():
            if file_ref(destination)['sha256'] == receipt['files'][relative]:
                continue
            raise ValueError('existing sampler corpus bytes differ; use a new output: ' + relative)
        copy_exact(stage_gen / relative, destination)
    atomic_json(marker, receipt)
    shutil.rmtree(stage)
    return 'written', receipt


def materialize(args):
    import fcntl
    import arclog
    from types import SimpleNamespace
    sys.path.insert(0, str(CODE_ROOT / 'ast/run'))
    from provenance import load_build
    ready = json.loads((args.runtime / 'ready.json').read_bytes())
    build = load_build(arclog, SimpleNamespace(build_receipt=None,
        engine_commit=ready['revision'], wheel=Path(ready['wheel'])))
    if not hasattr(arclog, 'case_files'):
        raise ValueError('native case-file metadata API missing')
    corpus = corpus_directory(args.corpus)
    output = args.output.resolve()
    if output == corpus or output.is_relative_to(corpus) or corpus.is_relative_to(output):
        raise ValueError('materialization must use a separate new output directory')
    control = output / '.empty-gold'
    gen = output / 'gen'
    config_file = control / 'config.json'
    if output.exists() and any(output.iterdir()) and not config_file.exists():
        raise ValueError('nonempty output is not a managed empty-gold materialization')
    control.mkdir(parents=True, exist_ok=True)
    with (control / 'writer.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        config = dict(schema='empty-gold-materialized-corpus-v1', policy=MATERIALIZE_POLICY,
                      corpus=str(corpus), publication=str(args.publication.resolve()), native_build=build)
        if config_file.exists() and json.loads(config_file.read_bytes()) != config:
            raise ValueError('materialization source/build/config differs; use a new output')
        atomic_json(config_file, config)
        gen.mkdir(exist_ok=True)
        selected = set(args.task or [])
        if args.task_ids: selected.update(args.task_ids.read_text().split())
        counts = dict(written=0, reused=0, failed=0); seen = set(); start = time.monotonic()
        ready_tasks = {p.stem for p in (control / 'tasks').glob('*.json')}
        # Input is a reader snapshot of tasks published so far. Rerun later to
        # add newly committed tasks; no completed task is regenerated.
        with JsonlWriter(control / 'materialize.jsonl.zst') as events:
            for row in iter_json(args.publication):
                task = row['task']
                if selected and task not in selected: continue
                if task in seen: raise ValueError('publication has multiple records for task ' + task)
                seen.add(task)
                try:
                    status, receipt = materialize_task(arclog, corpus, gen, control, row, build)
                    counts[status] += 1
                    ready_tasks.add(task)
                    # Representatives may be present solely as source support;
                    # expose only completed publication tasks to the sampler.
                    atomic_text(control / 'ready-tasks.txt', ''.join(t + '\n' for t in sorted(ready_tasks)))
                    if status == 'written':
                        events.write(dict(schema='empty-gold-materialize-event-v1', status=status,
                                          task=task, receipt=str(control / 'tasks' / (task + '.json')),
                                          key=receipt['key']))
                        events.flush()
                except Exception as error:
                    counts['failed'] += 1
                    events.write(dict(schema='empty-gold-materialize-event-v1',status='failed',task=task,
                        reason=f'{type(error).__name__}: {error}', traceback=traceback.format_exc()))
                    events.flush()
                print(json.dumps(dict(task=task, counts=counts,
                                      seconds=round(time.monotonic()-start, 3))), flush=True)
        pending = sorted(selected - seen)
        summary = dict(counts=counts, requested_not_published=pending, sampler_gen=str(gen),
                       journal_committed_lines=events.committed_lines,
                       ready_tasks=str(control / 'ready-tasks.txt'),
                       seconds=round(time.monotonic()-start, 3))
        atomic_json(control / 'summary.json', summary)
        print(json.dumps(summary), flush=True)
        return int(bool(counts['failed']))


def publish(args):
    import arclog
    # A real native dependency: existing gold_kept/gold_tables are insufficient.
    native = getattr(arclog, 'empty_gold_json', None)
    if native is None:
        raise SystemExit('native exhaustive empty-gold operation not installed; '
                         'requires empty_gold_json(corpus, tasks, task, request_work_cap=None). No kept-table fallback.')
    from types import SimpleNamespace
    sys.path.insert(0, str(CODE_ROOT / 'ast/run'))
    from provenance import load_build
    ready = json.loads((args.runtime / 'ready.json').read_bytes())
    actual_build = load_build(arclog, SimpleNamespace(build_receipt=None,
        engine_commit=ready['revision'], wheel=Path(ready['wheel'])))
    runtime = dict(ready=file_ref(args.runtime / 'ready.json'), build=actual_build)
    corpus = args.corpus.resolve(); tasks = args.tasks.resolve()
    chosen = args.task or sorted(p.stem for p in corpus.glob('*.arcdata'))
    implementation = file_ref(__file__)
    started = time.monotonic(); done = reused = failures = 0
    with JsonlWriter(args.output) as out, JsonlWriter(args.lint_output) as lint_out:
        prior = {}; seen_lint = set()
        with JsonlReader(args.lint_output) as source:
            for raw in source.iter_lines(stop_line=lint_out.committed_lines + 1):
                seen_lint.add(json.loads(raw)['finding_id'])
        with JsonlReader(args.output) as source:
            for raw in source.iter_lines(stop_line=out.committed_lines + 1):
                row = json.loads(raw)
                if row['schema'] != SCHEMA:
                    raise ValueError('publication schema differs')
                prior[row['task']] = row
        for task in chosen:
            request = dict(schema='arclog-empty-gold-request-v1', policy=POLICY, task=task,
                           deadline_seconds=None,
                           **({} if args.request_work_cap is None else dict(request_work_cap=args.request_work_cap)),
                           source=source_ref(corpus, tasks, task), runtime=runtime)
            # Checkout location is provenance, not a result dependency. Identical
            # code in a newly pinned worktree must reuse committed tasks.
            key = digest(dict(request=request, publisher_sha256=implementation['sha256']))
            compatible_keys = {key} | {digest(dict(request=request, publisher_sha256=old_sha))
                                       for old_sha in PUBLISH_COMPATIBLE_PREDECESSORS}
            if prior.get(task, {}).get('resume_key') in compatible_keys:
                commit_lint(lint_out, seen_lint, prior[task]['result'], request)
                reused += 1
                continue
            try:
                result = validate_report(json.loads(native(
                    str(corpus), str(tasks), task, request_work_cap=args.request_work_cap)), request)
            except Exception as error:
                # A transport/native failure keeps the entire original task;
                # no incomplete candidate can enter a downstream consumer.
                result = dict(schema=NATIVE_SCHEMA, task=task, selection='original',
                              reason=f'{type(error).__name__}: {error}',
                              cases=[], skipped_cases=[],
                              singleton_double_read_lint=dict(status='unavailable',
                                  reason='native call or result transport failed'),
                              transport_error=dict(traceback=traceback.format_exc()),
                              original_source=request['source'])
            if source_ref(corpus, tasks, task) != request['source']:
                raise ValueError('task source changed during native operation; no result committed')
            # A case whose selected program has no text gives no gold: it is
            # skipped with the filter's reason, and an error line names it.
            textless = [c for c in result['cases']
                        if not isinstance(c.get('filtered_program') or c.get('original_program'), str)
                        or not (c.get('filtered_program') or c.get('original_program')).strip()]
            if textless:
                result['cases'] = [c for c in result['cases'] if c not in textless]
                result['skipped_cases'] = result['skipped_cases'] + [
                    dict(case=c['case'], reason='no program text: %s' % (c.get('reason') or result.get('reason')))
                    for c in textless]
                print(json.dumps(dict(error='cases with no program text', task=task, cases=len(textless),
                                      reason=result.get('reason'))), flush=True)
            failures += result['selection'] == 'original'
            lint_status = commit_lint(lint_out, seen_lint, result, request)
            row = dict(schema=SCHEMA, policy=POLICY, task=task, resume_key=key,
                       singleton_double_read_lint=lint_status,
                       request=request, implementation=implementation, result=result)
            out.write(row); out.flush()  # one durable task immediately
            done += 1
            print(json.dumps(dict(done=done, reused=reused, total=len(chosen),
                                  original_fallbacks=failures, task=task,
                                  committed_lines=out.committed_lines,
                                  seconds=round(time.monotonic()-started, 3))), flush=True)
    if args.check_set:
        audit_check_set(args.output, args.check_set, args.audit_output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    run = commands.add_parser('publish')
    run.add_argument('--corpus', type=Path, required=True)
    run.add_argument('--tasks', type=Path, required=True)
    run.add_argument('--runtime', type=Path, required=True)
    run.add_argument('--output', type=Path, required=True)
    run.add_argument('--lint-output', type=Path, help='Framed finding journal; defaults beside gold output')
    run.add_argument('--task', action='append')
    run.add_argument('--request-work-cap', type=int, default=None,
                     help='Request work cap of each native evaluation request; default is the settings default')
    run.add_argument('--check-set', type=Path, action='append')
    run.add_argument('--audit-output', type=Path)
    check = commands.add_parser('audit')
    check.add_argument('--publication', type=Path, required=True)
    check.add_argument('--check-set', type=Path, action='append', required=True)
    check.add_argument('--output', type=Path, required=True)
    layout = commands.add_parser('materialize', help='Write a resumable SAMPLER_GEN corpus, without evaluation')
    layout.add_argument('--publication', type=Path, required=True)
    layout.add_argument('--corpus', type=Path, required=True, help='Converted corpus gen/ or its parent out/')
    layout.add_argument('--runtime', type=Path, required=True)
    layout.add_argument('--output', type=Path, required=True, help='New versioned directory; SAMPLER_GEN is its gen/')
    layout.add_argument('--task', action='append')
    layout.add_argument('--task-ids', type=Path, help='Whitespace-separated task IDs, e.g. the 118 holdout tasks')
    args = parser.parse_args()
    if args.command == 'materialize':
        return materialize(args)
    if args.command == 'audit':
        audit_check_set(args.publication, args.check_set, args.output)
    else:
        if args.request_work_cap is not None and args.request_work_cap <= 0:
            parser.error('--request-work-cap must be positive')
        if args.output.suffix != '.zst': parser.error('output must be .jsonl.zst')
        if args.check_set and args.audit_output is None: parser.error('--check-set requires --audit-output')
        if args.lint_output is None:
            args.lint_output = args.output.with_name('singleton-double-read-findings.jsonl.zst')
        if args.lint_output.suffix != '.zst': parser.error('lint output must be .jsonl.zst')
        if args.lint_output.resolve() == args.output.resolve(): parser.error('lint and gold outputs must differ')
        args.lint_output.parent.mkdir(parents=True, exist_ok=True)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        publish(args)


if __name__ == '__main__':
    raise SystemExit(main())
