"""Durable derived-DET facts; input keys, never current code-file validity."""
import hashlib
import json
from pathlib import Path
import sqlite3

SCHEMA = 'det-later-fit-v1'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def inputs(source_sha256, task_sha256):
    # The evaluator consumes the complete original record and task evidence.
    # This key can be checked before reopening the source gzip on resume.
    return dict(mode=SCHEMA, source_sha256=source_sha256, task_sha256=task_sha256)


def validate(result):
    if result.get('schema') != 'evaluator-det-later-fit-v1':
        raise ValueError('shared evaluator DET result schema mismatch')
    if result.get('status') not in ('complete', 'unknown'):
        raise ValueError('shared evaluator DET status invalid')
    for field in ('fits_train', 'fits_test'):
        if result.get(field) is not None and type(result[field]) is not bool:
            raise ValueError('shared evaluator ' + field + ' must be bool/null')
    if not isinstance(result.get('receipt'), dict):
        raise ValueError('shared evaluator omitted receipt')
    if not isinstance(result.get('train_fit_assignments'), list):
        raise ValueError('shared evaluator omitted train assignment evidence')
    if result.get('status') == 'unknown' and not result.get('reason'):
        raise ValueError('shared evaluator unknown requires reason')


class Store:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.db = sqlite3.connect(self.path, timeout=30)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
          CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS pairs(pair_id TEXT PRIMARY KEY,
            input_sha256 TEXT NOT NULL,source_sha256 TEXT NOT NULL,
            result_sha256 TEXT NOT NULL,result_json TEXT NOT NULL);
        ''')
        previous = self.db.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()
        if previous and previous[0] != SCHEMA:
            raise ValueError('DET fact database schema differs')
        self.db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)', ('schema', SCHEMA))
        self.db.commit()

    def load(self, pair_id, input_sha256):
        row = self.db.execute('SELECT result_sha256,result_json FROM pairs '
                              'WHERE pair_id=? AND input_sha256=?', (pair_id, input_sha256)).fetchone()
        if row is None:
            return None
        result = json.loads(row[1])
        if digest(result) != row[0]:
            raise ValueError('stored DET result integrity failure: ' + pair_id)
        validate(result)
        return result

    def write(self, pair_id, input_sha256, source_sha256, result):
        validate(result)
        self.db.execute('INSERT OR REPLACE INTO pairs VALUES (?,?,?,?,?)',
                        (pair_id, input_sha256, source_sha256, digest(result), canonical(result)))
        self.db.commit()

    def close(self):
        self.db.close()


def semantic_facts(result):
    """Parity view of outcomes and axes, excluding execution provenance."""
    difference = result.get('first_later_difference')
    return dict(status=result['status'], fits_train=result['fits_train'],
        fits_test=result['fits_test'], reason=result.get('reason'),
        first_later_difference=None if difference is None else
            {k:difference.get(k) for k in ('relation', 'form', 'reason', 'empty_axes')},
        train_fit_assignments=[dict(fits_train=a.get('fits_train'), fits_test=a.get('fits_test'),
            test_complete=a.get('test_complete'),
            test=[{k:t.get(k) for k in ('example', 'models', 'fits', 'complete', 'required_axis')}
                  for t in a.get('test', [])]) for a in result['train_fit_assignments']])
