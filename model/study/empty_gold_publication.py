#!/usr/bin/env python3
"""Task-atomic publication transport for native exhaustive empty-gold filtering.

The native operation owns enumeration, editing, source maps and OUT comparison.
This module cannot infer emptiness from sampled or gold-kept tables.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from study_paths import MAIN_ROOT, CODE_ROOT
sys.path.append(str(MAIN_ROOT / '.venv/lib/python3.12/site-packages'))
from judge3.framed_jsonl import JsonlReader, JsonlWriter, iter_json

SCHEMA = 'empty-gold-publication-v1'
NATIVE_SCHEMA = 'arclog-empty-gold-v1'
POLICY = 'all-train-test-inputs-all-assignments-empty-closure-v1'


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

    The native entry owns all semantic checks and returns original for the
    whole task when any condition fails. Provenance is our outer envelope.
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
        if not all(isinstance(case[name], str) for name in ('original_program', 'filtered_program')):
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
        report = row['result']
        if report['selection'] != 'filtered':
            fallbacks[task] = report['reason']
            continue
        for case in report['cases']:
            for clause in case['removed_clauses']:
                value = dict(clause, task=task, case=case['case'])
                removed[clause_key(value)] = value
    expected_by_key = {clause_key(row): row for row in expected}
    report = dict(schema='empty-gold-check-set-audit-v1',
        check_sets=snapshots, check_lines=len(expected),
        publication=file_ref(publication),
        listed_removed=[v for v in expected if clause_key(v) in removed],
        listed_kept=[dict(v, reason=fallbacks.get(v['task'], 'no matching removed source clause'))
                     for v in expected if clause_key(v) not in removed and v['task'] in selected],
        listed_not_processed=[v for v in expected if v['task'] not in selected],
        removed_not_listed=[v for k, v in removed.items() if k not in expected_by_key])
    Path(destination).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report


def lint_records(result, request):
    """Forward the report-only native lint without imposing proof fields."""
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


def publish(args):
    import arclog
    # A real native dependency: existing gold_kept/gold_tables are insufficient.
    native = getattr(arclog, 'empty_gold_json', None)
    if native is None:
        raise SystemExit('native exhaustive empty-gold operation not installed; '
                         'requires empty_gold_json(corpus, tasks, task, deadline_seconds=None). No kept-table fallback.')
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
                           deadline_seconds=args.deadline_seconds,
                           source=source_ref(corpus, tasks, task), runtime=runtime)
            # Checkout location is provenance, not a result dependency. Identical
            # code in a newly pinned worktree must reuse committed tasks.
            key = digest(dict(request=request, publisher_sha256=implementation['sha256']))
            if prior.get(task, {}).get('resume_key') == key:
                commit_lint(lint_out, seen_lint, prior[task]['result'], request)
                reused += 1
                continue
            try:
                result = validate_report(json.loads(native(
                    str(corpus), str(tasks), task, deadline_seconds=args.deadline_seconds)), request)
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
    run.add_argument('--deadline-seconds', type=float, default=None,
                     help='Per-native-evaluation deadline; default is no deadline')
    run.add_argument('--check-set', type=Path, action='append')
    run.add_argument('--audit-output', type=Path)
    check = commands.add_parser('audit')
    check.add_argument('--publication', type=Path, required=True)
    check.add_argument('--check-set', type=Path, action='append', required=True)
    check.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'audit':
        audit_check_set(args.publication, args.check_set, args.output)
    else:
        if args.deadline_seconds is not None and args.deadline_seconds <= 0:
            parser.error('--deadline-seconds must be positive')
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
    main()
