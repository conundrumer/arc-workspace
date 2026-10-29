"""Read stored normal attributes for study counts and fits, without evaluation."""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import threading

try:
    from . import facts
except ImportError:
    import facts


def _digest(value):
    text = json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def _default_database(area, name):
    study = str(Path(__file__).resolve().parents[3])
    if study not in sys.path:
        sys.path.insert(0, study)
    from study_paths import DATA_ROOT
    return DATA_ROOT / 'ast/run' / area / name


def _signature(path):
    stat = path.stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


def _open(reason):
    return dict(status='open', normal=None, eligible=False,
                absence_reason='normal_unavailable', reason=reason)


class _Database:
    """Short read snapshots; never retain a transaction between pair reads."""

    def __init__(self, path, lock):
        self.path, self.lock = Path(path).resolve(), Path(lock).resolve()
        self.connection = None
        self.identity = None

    def close(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    @contextmanager
    def snapshot(self):
        guard = None
        immutable = False
        try:
            # Final WAL databases may have no shm file. Immutable reads are safe
            # only while the producer's lock proves it cannot publish changes.
            try:
                guard = self.lock.open('rb')
                fcntl.flock(guard, fcntl.LOCK_SH | fcntl.LOCK_NB)
                wal = Path(str(self.path) + '-wal')
                immutable = not wal.exists() or wal.stat().st_size == 0
            except OSError:
                if guard is not None:
                    guard.close()
                    guard = None
            identity = (os.getpid(), immutable, _signature(self.path))
            if identity != self.identity or self.connection is None:
                self.close()
                suffix = '?mode=ro' + ('&immutable=1' if immutable else '')
                self.connection = sqlite3.connect(
                    self.path.as_uri() + suffix, uri=True, isolation_level=None,
                    timeout=0.5)
                self.identity = identity
            self.connection.execute('BEGIN')
            try:
                yield self.connection
            finally:
                self.connection.execute('ROLLBACK')
        finally:
            try:
                # An immutable handle must not outlive the producer lock.
                if immutable:
                    self.close()
            finally:
                if guard is not None:
                    guard.close()


class NormalReader:
    """Reusable, worker-local read-only reader; use close() or a with statement.

    Each call reads a fresh database snapshot. Validity binds the original
    pair input and stored fact integrity. Producer code is provenance; later
    source-file edits do not invalidate completed facts. The legacy base-result
    argument is accepted without making base labels a normal dependency.
    """

    def __init__(self, database=None, *, base_database=None):
        path = Path(database if database is not None else
                    _default_database('mech2', 'normal.sqlite3')).resolve()
        self.database = path
        self.base_database = base_database
        self._normal = _Database(path, path.with_suffix('.lock'))
        self._base = None

    def close(self):
        self._normal.close()
        if self._base is not None:
            self._base.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _bindings(self, pair_id):
        if self._base is None:
            path = Path(self.base_database if self.base_database is not None else
                        _default_database('mech', 'labels.sqlite3')).resolve()
            self._base = _Database(path, str(path) + '.lock')
        with self._base.snapshot() as db:
            return db.execute('SELECT source_sha256,result_sha256 FROM pairs '
                              'WHERE pair_id=?', (pair_id,)).fetchone()

    def _load_facts(self, db, pair_id, source_sha256, base_result_sha256):
        row = db.execute('SELECT * FROM pairs WHERE pair_id=?', (pair_id,)).fetchone()
        if row is None:
            return _open('normal receipt absent')
        facts.validate('pairs', row)
        if row[1] != source_sha256:
            return _open('normal source binding stale')
        gold = db.execute('SELECT * FROM gold_points WHERE point_id=?', (row[3],)).fetchone()
        if gold is None:
            return _open('gold normal receipt absent')
        facts.validate('gold_points', gold)
        for producer in {row[2], gold[3]}:
            item = db.execute('SELECT manifest_json FROM producers WHERE code_sha256=?',
                              (producer,)).fetchone()
            if item is None:
                return _open('normal producer absent')
            manifest = json.loads(item[0])
            if _digest(manifest) != producer:
                return _open('normal producer receipt invalid')
        origin = self._bindings(gold[1])
        if origin is None or origin[0] != gold[2]:
            return _open('gold normal source binding stale')
        mutant = facts.outcome(row); gold_result = facts.outcome(gold)
        value = mutant['normal']
        reference = dict(database=str(self.database), table='pairs', pair_id=pair_id,
                         result_sha256=row[6], source_sha256=row[1], code_sha256=row[2],
                         gold_point_id=row[3])
        return dict(status='unavailable' if value is None else 'classified',
                    normal=value, eligible=value is True,
                    absence_reason=None if value is True else
                        'non_normal' if value is False else 'normal_unavailable',
                    writer_pass=mutant['writer_pass'], gold=gold_result,
                    gold_point_id=row[3], reference=reference,
                    record=dict(schema=facts.SCHEMA, pair_id=pair_id,
                                source_sha256=row[1], code_sha256=row[2],
                                gold_point_id=row[3], mutant=mutant, gold=gold_result))

    def load_normal(self, pair_id, *, source_sha256=None, base_result_sha256=None):
        """Return status, tri-state normal, eligibility and a durable reference.

        Classified false has absence_reason=non_normal. Open/stale/missing and
        classified unavailable have absence_reason=normal_unavailable. Only a
        classified true result is eligible for scientific counts and fits.
        """
        try:
            if source_sha256 is None:
                binding = self._bindings(pair_id)
                if binding is None:
                    return _open('base receipt absent')
                source_sha256 = binding[0]
            with self._normal.snapshot() as db:
                schema = db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()
                if schema and schema[0] == facts.SCHEMA:
                    return self._load_facts(db, pair_id, source_sha256, base_result_sha256)
                row = db.execute(
                    'SELECT source_sha256,base_result_sha256,code_sha256,'
                    'result_sha256,normal,record_json FROM pairs WHERE pair_id=?',
                    (pair_id,)).fetchone()
                if row is None:
                    return _open('normal receipt absent')
                source, base, code, result, normal, text = row
                record = json.loads(text)
            if (source != source_sha256 or _digest(record) != result or
                    record['pair_id'] != pair_id or
                    record['source_sha256'] != source or
                    record['base_result_sha256'] != base or
                    record['code_sha256'] != code):
                return _open('normal receipt stale or invalid')
            value = record['mutant']['normal']
            if ((value is not None and type(value) is not bool) or
                    normal != (None if value is None else int(value))):
                return _open('normal attribute disagrees with receipt')
            return dict(
                status='unavailable' if value is None else 'classified',
                normal=value, eligible=value is True,
                absence_reason=None if value is True else
                    'non_normal' if value is False else 'normal_unavailable',
                writer_pass=record['mutant'].get('writer_pass'),
                gold=record['gold'], gold_point_id=record['gold_point_id'],
                reference=dict(database=str(self.database), table='pairs',
                               pair_id=pair_id, result_sha256=result,
                               source_sha256=source, base_result_sha256=base,
                               code_sha256=code),
                record=record)
        except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as exc:
            return _open(f'normal evidence unavailable: {type(exc).__name__}: {exc}')


_local = threading.local()


def _reader(database):
    path = Path(database if database is not None else
                _default_database('mech2', 'normal.sqlite3')).resolve()
    readers = getattr(_local, 'readers', None)
    if readers is None:
        readers = _local.readers = {}
    key = (os.getpid(), str(path))
    if key not in readers:
        readers[key] = NormalReader(path)
    return readers[key]


def load_normal(database, pair_id, *, source_sha256=None,
                base_result_sha256=None, reader=None):
    """Compatibility entry point; repeated calls reuse a thread-local reader."""
    current = reader if reader is not None else _reader(database)
    if database is not None and Path(database).resolve() != current.database:
        raise ValueError('reader database differs from requested database')
    return current.load_normal(pair_id, source_sha256=source_sha256,
                               base_result_sha256=base_result_sha256)


def is_normal(pair_id, *, source_sha256=None, base_result_sha256=None,
              database=None, reader=None):
    """True only for a valid normal mutant; intended for read-time study use."""
    return load_normal(database, pair_id, source_sha256=source_sha256,
                       base_result_sha256=base_result_sha256,
                       reader=reader)['eligible']
