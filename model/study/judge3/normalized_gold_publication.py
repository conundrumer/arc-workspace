#!/usr/bin/env python3
"""Manifest-driven normalized-gold publication through the canonical provider.

No program editing, path arithmetic, table matching or row decoding lives here.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT
sys.path[:0] = [str(CODE_ROOT / 'judgetool'), str(CODE_ROOT / 'judge3')]
from dataset_format import write_json
# Reuse the existing point publisher's bounded hashing, locking and journals.
from det_full_body_run import (file_sha, digest, append, exclusive, read, inside,
                              relative, manifest_for, verify_manifest)

POLICY = 'normalized-gold-view-v1'


def overlay_snapshot(operation):
    lookup = operation.get('overlay_publication_lookup', {})
    if not lookup.get('path'):
        raise ValueError('mapper lacks explicit overlay lookup')
    path = inside(lookup['path'], DATA_ROOT)
    actual = file_sha(path) if path.is_file() else None
    expected = lookup.get('sha256') if lookup.get('present_at_snapshot') else None
    if actual != expected:
        raise ValueError('source overlay changed since mapper snapshot; preserve it and remap this point')
    return actual


def publication_layouts(validated, generation, expected_pairs):
    """Keep provider-authenticated layout choices; never infer pair layout."""
    variants = validated['layout_variants']
    pairs = validated['per_pair_source_generations']
    if 'base' not in variants or set(pairs) != expected_pairs:
        raise ValueError('validated layout receipt lacks exact point/pair coverage')
    public_files = validated['public_files']
    for variant in variants.values():
        name = variant['point_json']
        if Path(name).is_absolute() or name not in public_files:
            raise ValueError('layout point is not a validated generation artifact')
        if not inside(generation / name, generation).is_file():
            raise ValueError('validated layout point file is missing')
    for pair in pairs.values():
        variant = variants[pair['layout']]
        if (pair['point_json'] != variant['point_json']
                or pair['source_generation'] != variant['source_generation']):
            raise ValueError('pair layout provenance differs from its declared variant')
    # Paths in these two receipt fields remain relative to record.generation.
    return dict(layout_variants=variants, per_pair_source_generations=pairs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=DATA_ROOT / 'feat-exp/normalized-gold-v1')
    parser.add_argument('--cache', type=Path, default=DATA_ROOT / 'feat-exp/case-cache')
    parser.add_argument('--deadline', type=float, default=30)
    args = parser.parse_args()
    for path in (args.manifest, args.runtime, args.output, args.cache):
        inside(path, DATA_ROOT)
    if file_sha(args.manifest) != args.manifest_sha256:
        raise ValueError('dependency manifest differs from pinned SHA')
    manifest = read(args.manifest)
    if manifest.get('schema') != 'normalized-gold-publication-dependencies-v1':
        raise ValueError('unsupported dependency manifest schema')
    for filename, wanted in manifest['artifacts'].items():
        # Frozen evidence may live elsewhere under DATA_ROOT. Relative keys
        # remain relative to this manifest; both forms retain exact SHA checks.
        candidate = Path(filename)
        path = candidate if candidate.is_absolute() else args.manifest.parent / candidate
        if file_sha(inside(path, DATA_ROOT)) != wanted:
            raise ValueError('mapper dependency bytes changed: ' + filename)
    runtime = read(args.runtime / 'ready.json')
    manifest_ref = dict(path=str(args.manifest.resolve()), sha256=args.manifest_sha256)
    try:
        from normalized_gold import export_normalized_gold_point, validate_normalized_gold_export
    except ImportError as error:
        raise SystemExit('Actual source dependency missing: CODE_ROOT/normalized_gold.py and its native correspondence helper; no old-export fallback. ' + str(error))
    from evaluator import ReplayEvaluator
    sys.path.insert(0, str(CODE_ROOT / 'ast/run'))
    from provenance import load_build
    code_files = [Path(__file__), CODE_ROOT / 'normalized_gold.py', CODE_ROOT / 'native_correspondence.py']
    code = {str(p): file_sha(p) for p in code_files}
    attempt = digest(dict(code=code, runtime=runtime, manifest=manifest_ref, deadline=args.deadline))
    operator = args.output / 'operator'
    counters = Counter()
    started = time.monotonic()
    ev = None
    with exclusive(operator / 'publisher.lock'):
        write_json(operator / 'latest-attempt.json', dict(attempt=attempt, code=code,
            runtime=runtime, manifest=manifest_ref, policy=POLICY), compact=True)
        try:
            with Path(manifest['points_path']).open() as stream:
                for number, line in enumerate(stream, 1):
                    operation = json.loads(line)
                    point_id = operation['point_id']
                    if Path(point_id).name != point_id:
                        raise ValueError('unsafe point identity')
                    generation = args.output / 'generations' / args.manifest_sha256[:16] / point_id
                    private = operator / 'private' / point_id
                    state_path = operator / 'points' / (point_id + '.json')
                    state = read(state_path, {})
                    index = args.output / 'published-points' / (point_id + '.json')
                    expected_pairs = set(operation['published_pairs'])
                    try:
                        overlay_before = overlay_snapshot(operation)
                        existing = read(index)
                        if existing:
                            if (existing.get('policy') != POLICY or existing.get('manifest') != manifest_ref
                                    or set(existing.get('pairs', {})) != expected_pairs):
                                raise ValueError('existing normalized publication has a different operation')
                            artifact_path = DATA_ROOT / existing['artifact_manifest']['path']
                            if file_sha(artifact_path) != existing['artifact_manifest']['sha256']:
                                raise ValueError('published normalized manifest bytes changed')
                            verify_manifest(DATA_ROOT / existing['generation'], read(artifact_path)['files'])
                            counters['reused_points'] += 1
                            counters['reused_pairs'] += len(expected_pairs)
                            continue
                        if (not generation.exists() and state.get('attempt') == attempt
                                and state.get('status') == 'failed'):
                            counters['terminal_failed_points'] += 1
                            continue
                        result = state.get('result')
                        validated = None
                        # Recover a complete prior acquisition even if its result
                        # line was lost. A bad receipt never becomes a row proof.
                        if generation.exists():
                            try:
                                validated = validate_normalized_gold_export(generation,
                                    None if result is None else result.get('normalized_gold_receipt'),
                                    private=private, point_id=point_id)
                            except Exception:
                                if state.get('attempt') == attempt and state.get('status') == 'failed':
                                    counters['terminal_failed_points'] += 1
                                    continue
                        if validated is None:
                            if ev is None:
                                ev = ReplayEvaluator(deadline=args.deadline)
                                load_build(ev.arclog, SimpleNamespace(build_receipt=None,
                                    engine_commit=runtime['revision'], wheel=Path(runtime['wheel'])))
                            # Exact mapper operation is passed unchanged. The
                            # provider authenticates old/new handles and decides
                            # normalized acquisition vs inherited original bytes.
                            result = export_normalized_gold_point(ev, manifest_ref, operation,
                                generation, args.cache, private)
                            validated = validate_normalized_gold_export(generation,
                                result.get('normalized_gold_receipt'), private=private, point_id=point_id)
                        if not isinstance(validated, dict) or not validated:
                            raise ValueError('provider returned no validated normalized attestation')
                        if {str(p): file_sha(p) for p in code_files} != code:
                            raise ValueError('source changed during acquisition; do not publish this attempt')
                        if overlay_snapshot(operation) != overlay_before:
                            raise ValueError('overlay changed during acquisition; remap this point')
                        point_json = generation / 'points' / point_id / 'point.json'
                        pairs = {pair: generation / 'pairs' / pair / 'pair.json' for pair in expected_pairs}
                        if not point_json.is_file() or any(not p.is_file() for p in pairs.values()):
                            raise ValueError('validated normalized point lacks declared point/pair files')
                        layouts = publication_layouts(validated, generation, expected_pairs)
                        artifact_path = generation / 'artifact-manifest.json'
                        write_json(artifact_path, dict(schema='study-normalized-gold-artifacts-v1',
                            point_id=point_id, policy=POLICY, files=manifest_for(generation)), compact=True)
                        record = dict(schema='study-normalized-gold-publication-v1', policy=POLICY,
                            status='complete', point_id=point_id, task=operation['task'], case=operation['case'],
                            manifest=manifest_ref, source_layout_policy=operation['source_layout_policy'],
                            source_generation=operation['source_generation'], generation=relative(generation),
                            point_json=relative(point_json), pairs={k: relative(v) for k, v in pairs.items()},
                            artifact_manifest=dict(path=relative(artifact_path), sha256=file_sha(artifact_path)))
                        record.update(layouts)
                        write_json(index, record, compact=True)
                        append(args.output / 'manifest.jsonl', record)
                        write_json(state_path, dict(status='published', attempt=attempt,
                            result=result, attestation=validated, publication=record), compact=True)
                        counters['published_points'] += 1
                        counters['published_pairs'] += len(expected_pairs)
                    except Exception as error:
                        failure = dict(status='failed', attempt=attempt, point_id=point_id,
                            reason=f'{type(error).__name__}: {error}', operation_sha256=digest(operation))
                        write_json(state_path, failure, compact=True)
                        append(operator / 'failures.jsonl', failure)
                        counters['failed_points'] += 1
                    finally:
                        progress = dict(done=number, total=manifest['counts']['published_points'],
                            point_id=point_id, elapsed=round(time.monotonic() - started, 3), counts=dict(counters))
                        append(operator / 'progress.jsonl', progress)
                        print(json.dumps(progress), flush=True)
            summary = dict(policy=POLICY, attempt=attempt, manifest=manifest_ref, runtime=runtime['revision'],
                counts=dict(counters), seconds=time.monotonic() - started,
                point_index=relative(args.output / 'published-points'))
            write_json(operator / 'summary.json', summary, compact=True)
            return int(bool(counters['failed_points'] or counters['terminal_failed_points']))
        finally:
            if ev is not None:
                ev.close()


if __name__ == '__main__':
    raise SystemExit(main())
