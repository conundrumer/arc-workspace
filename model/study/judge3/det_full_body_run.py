#!/usr/bin/env python3
"""Stream the frozen DET full-BODY refresh, publishing complete immutable points.

Acquisition and semantic validation belong to det_full_body/export_pairs.
This driver only resumes results, hashes public files and publishes discovery.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
import fcntl
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT
sys.path[:0] = [str(CODE_ROOT / 'judgetool'), str(CODE_ROOT / 'judge3')]
from dataset_format import write_json

LAYOUT = 'det-full-body-train-v1'
PUBLICATION = 'study-det-full-body-publication-v1'


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def append(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


@contextmanager
def exclusive(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('another DET publisher owns this output; use the running job')
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def read(path, default=None):
    return json.loads(path.read_text()) if path.is_file() else default


def inside(path, root):
    path = Path(path).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError('artifact path escapes its publication root')
    return path


def relative(path):
    return str(inside(path, DATA_ROOT).relative_to(DATA_ROOT.resolve()))


def manifest_for(root):
    """Bounded hashing; no table JSON load or typed-cell interpretation."""
    return {str(p.relative_to(root)): dict(sha256=file_sha(p), bytes=p.stat().st_size)
            for p in sorted(root.rglob('*')) if p.is_file() and p.name != 'artifact-manifest.json'}


def verify_manifest(root, manifest):
    actual = {str(p.relative_to(root)) for p in root.rglob('*')
              if p.is_file() and p.name != 'artifact-manifest.json'}
    if actual != set(manifest):
        raise ValueError('published point file inventory changed')
    for name, ref in manifest.items():
        p = inside(root / name, root)
        if p.stat().st_size != ref['bytes'] or file_sha(p) != ref['sha256']:
            raise ValueError('published point bytes changed: ' + name)


def archive_unreferenced_work(root, group, operator):
    """Never expose interrupted .building outputs in an immutable generation."""
    expected = {'pairs': {p['pair_id'] for p in group['pairs']},
                'points': {group['point_id']}}
    for folder, names in expected.items():
        directory = root / folder
        if not directory.exists():
            continue
        for path in directory.iterdir():
            if path.name in names:
                continue
            destination = operator / 'unpublished-work' / group['point_id'] / folder / (path.name + '-' + str(time.time_ns()))
            destination.parent.mkdir(parents=True, exist_ok=True)
            path.rename(destination)


def publication_record(group, root, manifest_path):
    return dict(schema=PUBLICATION, contract=LAYOUT, status='complete',
        point_id=group['point_id'], task=group['task'], case=group['case'],
        body_path=group['body_path'], generation=relative(root),
        point_json=relative(root / 'points' / group['point_id'] / 'point.json'),
        pairs={p['pair_id']: relative(root / 'pairs' / p['pair_id'] / 'pair.json')
               for p in group['pairs']}, unavailable_pairs=[],
        artifact_manifest=dict(path=relative(manifest_path), sha256=file_sha(manifest_path)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=DATA_ROOT / 'feat-exp/det-full-body-v1')
    parser.add_argument('--cache', type=Path, default=DATA_ROOT / 'feat-exp/case-cache')
    parser.add_argument('--deadline', type=float, default=30)
    args = parser.parse_args()
    for path in (args.selection, args.runtime, args.output, args.cache):
        inside(path, DATA_ROOT)
    selection = read(args.selection)
    if (selection.get('schema') != 'study-det-full-body-selection-v1'
            or selection['pair_count'] != 5460 or selection['point_count'] != 973):
        raise ValueError('use the frozen5460-pair/973-point selection')
    groups = selection['groups']
    ids = [p['pair_id'] for g in groups for p in g['pairs']]
    if len(groups) != 973 or len(ids) != 5460 or len(set(ids)) != 5460:
        raise ValueError('selection contains missing or duplicate point/pair identities')
    runtime = read(args.runtime / 'ready.json')
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=CODE_ROOT, text=True).strip()
    for component in ('engine', 'scripts/build_study_runtime.py', 'scripts/study', 'scripts/check_study_pair_corpus.py'):
        objects = [subprocess.check_output(['git', 'rev-parse', r + ':' + component],
            cwd=CODE_ROOT, text=True).strip() for r in (runtime['revision'], revision)]
        if objects[0] != objects[1]:
            raise ValueError('runtime native input differs from selected source: ' + component)
    if Path(sys.executable).resolve() != Path(runtime['python']).resolve():
        raise ValueError('run using the selected runtime interpreter')
    from evaluator import ReplayEvaluator
    from export_by_pair_id import export_pairs
    from det_full_body import validate_det_full_body_export
    signature = inspect.signature(export_pairs)
    if not {'det_full_body', 'existing_points'} <= set(signature.parameters):
        raise ValueError('selected source lacks the approved full-DET exporter API')
    selection_sha = file_sha(args.selection)
    attempt = digest(dict(source_revision=revision, runtime=runtime,
        selection_sha256=selection_sha, deadline=args.deadline, driver_sha256=file_sha(__file__)))
    operator = args.output / 'operator'
    public = args.output / 'published-points'
    generation_root = args.output / 'generations' / selection_sha[:16]
    args.cache.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    counts = Counter()
    with exclusive(operator / 'publisher.lock'):
        write_json(operator / 'latest-attempt.json', dict(attempt=attempt, source_revision=revision,
            runtime=runtime, selection=str(args.selection), selection_sha256=selection_sha,
            policy=LAYOUT, deadline=args.deadline), compact=True)
        ev = None
        try:
            for number, group in enumerate(groups, 1):
                root = generation_root / group['point_id']
                discovery = public / (group['point_id'] + '.json')
                existing = read(discovery)
                if existing:
                    if (existing.get('schema') != PUBLICATION or existing.get('contract') != LAYOUT
                            or set(existing.get('pairs', {})) != {p['pair_id'] for p in group['pairs']}):
                        raise ValueError('existing point publication has a different contract or selection')
                    manifest_path = inside(DATA_ROOT / existing['artifact_manifest']['path'], DATA_ROOT)
                    if file_sha(manifest_path) != existing['artifact_manifest']['sha256']:
                        raise ValueError('published artifact manifest changed')
                    verify_manifest(DATA_ROOT / existing['generation'], read(manifest_path)['files'])
                    counts['reused_points'] += 1
                    counts['reused_pairs'] += len(group['pairs'])
                else:
                    root.mkdir(parents=True, exist_ok=True)
                    state_path = operator / 'points' / (group['point_id'] + '.json')
                    state = read(state_path, dict(schema='study-det-full-body-point-run-v1', results={}))
                    point_dir = root / 'points' / group['point_id']
                    private = operator / 'private' / group['point_id']
                    pending = []
                    for item in group['pairs']:
                        pair = item['pair_id']
                        prior = state['results'].get(pair)
                        destination = root / 'pairs' / pair
                        if destination.exists() and (prior is None or prior.get('status') == 'exported'):
                            # A completed acquisition may precede its durable log line.
                            # Validator authenticates native authority/receipts; driver
                            # never reconstructs columns, rowsets, scopes or frames.
                            ref = prior.get('det_full_body_receipt') if prior else None
                            try:
                                verified = validate_det_full_body_export(destination, ref, private=private)
                                state['results'][pair] = dict(prior or {}, pair_id=pair, status='exported',
                                    attestation=verified, attempt=attempt)
                                counts['reused_staged_pairs'] += 1
                                continue
                            except Exception as error:
                                state['results'][pair] = dict(pair_id=pair, status='failed',
                                    reason='saved artifact validation: ' + str(error), attempt=attempt)
                                # Preserve completed-but-refused artifacts, never silently
                                # replace them by evaluating a candidate again.
                                continue
                        if prior and prior.get('attempt') == attempt:
                            continue  # Terminal failure under unchanged implementation.
                        pending.append(pair)
                    write_json(state_path, state, compact=True)
                    if pending:
                        if ev is None:
                            ev = ReplayEvaluator(deadline=args.deadline)
                            # Reuse the canonical actual-wheel/native-binary
                            # authenticator; interpreter symlinks alone cannot
                            # prove which extension was imported.
                            sys.path.insert(0, str(CODE_ROOT / 'ast/run'))
                            from provenance import load_build
                            load_build(ev.arclog, SimpleNamespace(build_receipt=None,
                                engine_commit=runtime['revision'], wheel=Path(runtime['wheel'])))
                        old_roots = {str(Path(group['old_point']).parent)}
                        if len(old_roots) != 1:
                            raise ValueError('point has ambiguous inherited store root')
                        for result in export_pairs(ev, pending, root / 'pairs', args.cache, private,
                                root / 'points', include_det=True, det_full_body=True,
                                current_native_names=True, existing_points=Path(next(iter(old_roots)))):
                            pair = result['pair_id']
                            result = dict(result, attempt=attempt)
                            if result.get('status') == 'exported':
                                try:
                                    result['attestation'] = validate_det_full_body_export(
                                        root / 'pairs' / pair, result.get('det_full_body_receipt'), private=private)
                                except Exception as error:
                                    result.update(status='failed', reason='export attestation: ' + str(error))
                            state['results'][pair] = result
                            append(operator / 'pair-events.jsonl', result)
                            write_json(state_path, state, compact=True)
                            print(json.dumps(dict(event='pair', point=group['point_id'], **result)), flush=True)
                    failures = [state['results'].get(p['pair_id'], dict(pair_id=p['pair_id'],
                        status='failed', reason='exporter emitted no terminal result'))
                        for p in group['pairs'] if state['results'].get(p['pair_id'], {}).get('status') != 'exported']
                    if failures:
                        counts['unavailable_points'] += 1
                        counts['unavailable_pairs'] += len(failures)
                        write_json(operator / 'unavailable' / (group['point_id'] + '.json'),
                            dict(point_id=group['point_id'], failures=failures), compact=True)
                    else:
                        if not (point_dir / 'point.json').is_file():
                            raise ValueError('validated pairs have no shared point artifact')
                        archive_unreferenced_work(root, group, operator)
                        manifest_path = root / 'artifact-manifest.json'
                        write_json(manifest_path, dict(schema='study-det-full-body-artifacts-v1',
                            contract=LAYOUT, point_id=group['point_id'], files=manifest_for(root)), compact=True)
                        record = publication_record(group, root, manifest_path)
                        write_json(discovery, record, compact=True)  # Sole publication event.
                        append(args.output / 'manifest.jsonl', record)
                        counts['published_points'] += 1
                        counts['published_pairs'] += len(group['pairs'])
                elapsed = time.monotonic() - started
                progress = dict(event='point', done=number, total=len(groups), point_id=group['point_id'],
                    elapsed=round(elapsed, 3), rate=number / max(elapsed, .001), counts=dict(counts))
                append(operator / 'progress.jsonl', progress)
                print(json.dumps(progress), flush=True)
            summary = dict(schema='study-det-full-body-run-v1', attempt=attempt,
                source_revision=revision, runtime=runtime['revision'], selection_sha256=selection_sha,
                total_pairs=5460, total_points=973, counts=dict(counts), seconds=time.monotonic() - started,
                published_index=relative(public), event_log=relative(args.output / 'manifest.jsonl'))
            write_json(operator / 'summary.json', summary, compact=True)
            return int(bool(counts['unavailable_points']))
        finally:
            if ev is not None:
                ev.close()


if __name__ == '__main__':
    raise SystemExit(main())
