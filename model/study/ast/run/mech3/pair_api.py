"""Sequential population step4 calls using the existing worker and raw store."""
from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace

from .common import CODE_ROOT, DATA_ROOT
from .step4 import Worker
from .store import load_step4
from mech.source_read import SourceReader
from mech.step2_check import valid_base


class PairLabeler:
    """Reuse one evaluator across samples; each call reads a fresh base row.

    The caller commits its base pair before calling label_pair. This class owns
    only step4 facts, and never writes a grade or changes a source record.
    """
    def __init__(self, *, base, population_passes, config, source_reader=None,
                 deadline=30, compare_seconds=1, artifacts=None):
        base = Path(base).resolve()
        if isinstance(population_passes, Mapping):
            output = Path(population_passes['fit_split']).resolve()
        else:
            output = (Path(population_passes) / 'fits.sqlite3').resolve()
        if base == output:
            raise ValueError('base must remain read-only')
        if not output.is_relative_to(DATA_ROOT.resolve()):
            raise ValueError('population pass outputs must stay under DATA_ROOT')
        if deadline <= 0 or compare_seconds <= 0:
            raise ValueError('positive replay and comparison bounds required')
        args = SimpleNamespace(base=base, output=output, deadline=deadline,
            compare_seconds=compare_seconds, workers=1, task_ids=[],
            rerun_reader=False, rerun_test=False, retry_reader_unknown=False,
            retry_reader_reason=[], retry_test_unknown=False, retry_test_reason=[])
        self.worker = Worker(args, config=config, artifacts=artifacts, streaming=True)
        self.sources = source_reader if source_reader is not None else SourceReader(CODE_ROOT)
        self.owns_sources = source_reader is None
        self.closed = False

    def label_pair(self, pair_id, *, relabel=False):
        """Commit/resume this pair's step4 facts; return the owner's read view.

        Missing base rows return open; out-of-scope rows return not_applicable.
        A completed Unknown resumes normally. relabel is an explicit retry.
        Native replay is requested only by the existing Worker.process policy.
        """
        if self.closed:
            raise RuntimeError('pair labeler is closed')
        worker = self.worker
        row = worker.base.execute(
            'SELECT pair_id,source_sha256,code_sha256,config_sha256,result_sha256,record_json '
            'FROM pairs WHERE pair_id=?', (pair_id,)).fetchone()
        if row is None:
            return dict(status='open', valid=False, pair_id=pair_id, reason='base result missing')
        base = valid_base(row)
        if base.get('label') != 'fits' or base.get('kind', '').upper() == 'DET':
            return dict(status='not_applicable', pair_id=pair_id,
                reason='step4 applies to non-DET base fits pairs')
        _, _, task_receipt = worker.task(base['task'])
        existing = worker.output.load(pair_id, base['source_sha256'], row[4], task_receipt['sha256'])
        bindings = dict(source_sha256=base['source_sha256'], base_result_sha256=row[4],
                        task_sha256=task_receipt['sha256'])
        if existing is not None and not relabel:
            return dict(load_step4(worker.output.path, pair_id, **bindings),
                        resumed=True, evaluations=0)
        old_reader, old_test = worker.args.rerun_reader, worker.args.rerun_test
        worker.args.rerun_reader = worker.args.rerun_test = bool(relabel)
        try:
            try:
                record = self.sources.record(base)
                value = worker.process(base, record, existing)
            except (worker.legacy.arclog.Refusal, OSError, EOFError, ValueError, KeyError, IndexError, TypeError, StopIteration) as error:
                value = dict(pair_id=pair_id, source_sha256=base['source_sha256'],
                    base_result_sha256=row[4], task_receipt=task_receipt, evaluations=0,
                    reader_difference=dict(read_difference=None, reason=str(error),
                                           error_type=type(error).__name__))
            worker.output.save(value)
            return dict(load_step4(worker.output.path, pair_id, **bindings),
                        resumed=False, evaluations=value.get('evaluations', 0))
        finally:
            worker.args.rerun_reader, worker.args.rerun_test = old_reader, old_test

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.owns_sources:
                self.sources.close()
        finally:
            try:
                self.worker.ev.close()
            finally:
                try:
                    self.worker.output.close()
                finally:
                    self.worker.base.close()

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()
