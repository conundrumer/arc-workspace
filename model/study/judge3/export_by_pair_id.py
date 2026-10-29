#!/usr/bin/env python3
"""Export pair data directories by mechanical pair_id, for any base label.

Reads the base-label store read-only, locates each pair's corpus record, builds
its adapter with the mechanical pipeline's metadata producer, and writes the
directory through `export_dataset.export_target`. DET pairs require both
`--features` and `--include-det`; they remain excluded from judge exports.

With `--features`, a branch point (task, case, point) is a directory under
`--points` that holds, once, G, the available tables, train.json, the gold
program and libraries.json. Each pair directory then holds X, the mutant
program and a pair.json whose `point` is the relative path of that directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT
sys.path.insert(0, str(CODE_ROOT / 'ast/run'))
sys.path.insert(0, str(CODE_ROOT / 'judgetool'))
from export_dataset import export_target

RUN = DATA_ROOT / 'ast/run'
FEATURE_ROOT = DATA_ROOT / 'feat-exp'


class PairSource:
    """pair_id -> (record, target) with one metadata producer per corpus."""

    def __init__(self, ev, labels=RUN / 'mech/labels.sqlite3'):
        import mech5._paths  # puts the mechanical pipeline's modules on sys.path
        from mech5.metadata import produce
        from source_read import SourceReader
        from tables import TargetStore
        self.ev, self.produce = ev, produce
        self.labels = sqlite3.connect(Path(labels).resolve().as_uri() + '?mode=ro', uri=True, timeout=30)
        self.sources = SourceReader(CODE_ROOT)
        self.store = TargetStore(ev.legacy, CODE_ROOT)
        self.producers = {}

    def close(self):
        self.labels.close()
        self.sources.close()

    def base(self, pair_id):
        row = self.labels.execute('SELECT record_json FROM pairs WHERE pair_id=?', (pair_id,)).fetchone()
        if row is None:
            raise KeyError('pair_id absent from the base label store')
        base = json.loads(row[0])
        # Stored corpus paths may name a session scratch alias of the data root.
        corpus = RUN / Path(base['source']['corpus']).name
        return dict(base, source=dict(base['source'], corpus=str(corpus)))

    def load(self, pair_id, *, include_det=False):
        """Return source-bound metadata; DET is an explicit feature-only opt-in."""
        from run import digest, pair_key
        base = self.base(pair_id)
        if base['kind'].casefold() == 'det' and not include_det:
            raise ValueError('DET pairs are not judged')
        record = self.sources.record(base)
        if digest(pair_key(record)) != pair_id:
            raise ValueError('corpus record does not give this pair_id')
        corpus = Path(base['source']['corpus'])
        if base['kind'].casefold() == 'det':
            from evaluator_train import prepare_det_metadata
            adapter = prepare_det_metadata(self.ev, record, native_base=corpus / record['task'])
        else:
            producer, adapter = self.produce(self.ev, self.store, record, corpus,
                                             producer=self.producers.get(corpus), kind=base['kind'])
            self.producers[corpus] = producer
        task_path = (Path(self.ev.cfg['tasks']) / (record['task'] + '.json')).resolve()
        task = json.loads(task_path.read_text())
        adapter = dict(adapter, source=dict(adapter['source'], task_path=str(task_path)))
        return base, record, dict(adapter=adapter, ntrain=len(task['train']), ntest=len(task['test']))


def point_directory(points, record):
    """The shared directory of the branch point that a pair belongs to."""
    key = hashlib.sha256(json.dumps([record['case'], record['point']]).encode()).hexdigest()[:12]
    return points / (record['task'] + '-' + key)


def export_pairs(ev, pair_ids, output, cache, private, points=None, *, include_det=False):
    """Export each pair; yield one result dict per pair, with its seconds and status.

    With `points`, export the features layout: see the module docstring.
    """
    if include_det and points is None:
        raise ValueError('include_det requires features mode')
    source = PairSource(ev)
    try:
        for pair_id in pair_ids:
            started = time.monotonic()
            result = dict(pair_id=pair_id)
            destination = output / pair_id
            try:
                if destination.exists():
                    result.update(status='exists', reason='output directory exists; left unchanged')
                else:
                    base, record, target = source.load(pair_id, include_det=include_det)
                    done = export_target(ev, pair_id, record, target, destination, cache,
                                         source='base label store: ' + pair_id, private=private,
                                         features=None if points is None else point_directory(points, record))
                    fresh = done.pop('fresh_cases')
                    result.update(status='exported', label=base['label'], kind=base['kind'],
                                  tables=done['tables'], output=done['output'],
                                  cases_new=sorted(c for c, new in fresh.items() if new),
                                  cases_cached=sorted(c for c, new in fresh.items() if not new))
            except Exception as error:
                shutil.rmtree(destination.with_name(destination.name + '.building'), ignore_errors=True)
                if points is not None:
                    for stale in points.glob(f'*.building-{os.getpid()}'):
                        shutil.rmtree(stale, ignore_errors=True)
                skipped = str(error) == 'DET pairs are not judged'
                result.update(status='skipped' if skipped else 'failed',
                              reason=str(error) if skipped else f'{type(error).__name__}: {error}')
            result['seconds'] = round(time.monotonic() - started, 2)
            yield result
    finally:
        source.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pair_id', nargs='*', help='mechanical pair_id')
    parser.add_argument('--pair-ids-file', type=Path, help='file with one pair_id per line')
    parser.add_argument('--output', type=Path, default=FEATURE_ROOT / 'pairs',
                        help='directory that receives <pair_id>/ (default: %(default)s)')
    parser.add_argument('--cache', type=Path, default=FEATURE_ROOT / 'case-cache')
    parser.add_argument('--private', type=Path, default=FEATURE_ROOT / 'private',
                        help='where contexts and receipts go (default: %(default)s)')
    parser.add_argument('--features', action='store_true',
                        help='write only what the features study reads, with the files shared by a branch point '
                             'written once under --points')
    parser.add_argument('--include-det', action='store_true',
                        help='with --features only, include certified noncallable DET reader fields')
    parser.add_argument('--points', type=Path, default=FEATURE_ROOT / 'points',
                        help='with --features, directory that receives <task>-<point key>/ (default: %(default)s)')
    parser.add_argument('--deadline', type=float, default=30)
    args = parser.parse_args()
    if args.include_det and not args.features:
        parser.error('--include-det requires --features')
    pair_ids = list(args.pair_id)
    if args.pair_ids_file:
        pair_ids += [line.strip() for line in args.pair_ids_file.read_text().splitlines() if line.strip()]
    if not pair_ids:
        parser.error('give at least one pair_id')
    for path in (args.output, args.cache, args.private, args.points):
        if not path.resolve().is_relative_to(DATA_ROOT.resolve()):
            parser.error('every output directory must stay under the study data root')
    args.cache.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    if args.features:
        args.points.mkdir(parents=True, exist_ok=True)
    from evaluator import ReplayEvaluator
    ev = ReplayEvaluator(deadline=args.deadline)
    start = time.monotonic()
    counts = {}
    try:
        for i, result in enumerate(export_pairs(ev, pair_ids, args.output, args.cache, args.private,
                                                        args.points if args.features else None,
                                                        include_det=args.include_det), 1):
            counts[result['status']] = counts.get(result['status'], 0) + 1
            print(json.dumps(result), flush=True)
            elapsed = time.monotonic() - start
            print(f'{i}/{len(pair_ids)} elapsed={elapsed:.1f}s rate={i/elapsed:.3f}/s '
                  f'ETA={elapsed/i*(len(pair_ids)-i):.1f}s {counts}', file=sys.stderr, flush=True)
    finally:
        ev.close()
    return 1 if counts.get('failed') else 0


if __name__ == '__main__':
    raise SystemExit(main())
