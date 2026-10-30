"""Normal pass facts and their source/code validity bindings."""
import hashlib
import json
from pathlib import Path

SCHEMA = 'normal-facts-v2'
LEGACY_CLASSIFIER = 'e46ba454df570b640b3b85bbc9d96361f2f4621bbd0dfc46d6c1b721344bdaf3'
EXTRACTED_POLICY = '0302ddf3a7c7c98aa90d56834d94ce3aa6749ba9e2a0a42cc5dbf47fbfd6427c'


def reviewed_storage_rewrite(file, expected):
    return (Path(file).name == 'classify_normal.py' and expected == LEGACY_CLASSIFIER and
            hashlib.sha256(Path(__file__).with_name('normal_policy.py').read_bytes()).hexdigest()
            == EXTRACTED_POLICY)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def initialize(db):
    statements = '''
      CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
      CREATE TABLE producers(code_sha256 TEXT PRIMARY KEY,manifest_json TEXT NOT NULL);
      CREATE TABLE gold_points(
        point_id TEXT PRIMARY KEY,origin_pair_id TEXT NOT NULL,source_sha256 TEXT NOT NULL,
        code_sha256 TEXT NOT NULL REFERENCES producers,normal INTEGER,
        diagnostics_json TEXT NOT NULL,fact_sha256 TEXT NOT NULL);
      CREATE TABLE pairs(
        pair_id TEXT PRIMARY KEY,source_sha256 TEXT NOT NULL,
        code_sha256 TEXT NOT NULL REFERENCES producers,gold_point_id TEXT NOT NULL REFERENCES gold_points,
        normal INTEGER,diagnostics_json TEXT NOT NULL,fact_sha256 TEXT NOT NULL);
    '''
    for statement in statements.split(';'):
        if statement.strip():
            db.execute(statement)
    db.execute('INSERT INTO metadata VALUES (?,?)', ('schema', SCHEMA))


def classification(result):
    """Retain this check's outcomes and failures; source metadata stays upstream."""
    normal, writer_pass = result['normal'], result.get('writer_pass')
    if any(value is not None and type(value) is not bool for value in (normal, writer_pass)):
        raise ValueError('normal/ writer_pass must be boolean or null')
    diagnostics = {}
    if result.get('reason'):
        diagnostics['reason'] = result['reason']
    unavailable = []
    for probe in result.get('unavailable', []):
        item = {k:probe[k] for k in ('relation', 'sites', 'head', 'reasons', 'reason') if k in probe}
        if item and item not in unavailable:
            unavailable.append(item)
    if unavailable:
        diagnostics['unavailable'] = unavailable
    derived = None if normal is None and diagnostics.get('reason') else normal is True
    if writer_pass is not derived:
        raise ValueError('writer result needs independent evidence; cannot compact losslessly')
    return normal, canonical(diagnostics)


def payload(kind, row):
    """Canonical SQL fact payload, excluding its integrity hash."""
    fields = (('point_id', 'origin_pair_id', 'source_sha256', 'code_sha256')
              if kind == 'gold_points' else
              ('pair_id', 'source_sha256', 'code_sha256', 'gold_point_id'))
    return dict(zip(fields + ('normal', 'diagnostics'),
                    tuple(row[:4]) + (None if row[4] is None else bool(row[4]),
                                     json.loads(row[5]))))


def validate(kind, row):
    if row[4] not in (None, 0, 1):
        raise ValueError('invalid normal boolean')
    if digest(payload(kind, row)) != row[6]:
        raise ValueError('normal fact hash mismatch')


def insert(db, kind, identity, result):
    if kind not in ('pairs', 'gold_points'):
        raise ValueError(kind)
    row = tuple(identity) + classification(result)
    db.execute('INSERT OR REPLACE INTO ' + kind + ' VALUES (?,?,?,?,?,?,?)',
               row + (digest(payload(kind, row)),))


def outcome(row):
    """Reconstruct the public result; statuses are derived by the reader."""
    normal = None if row[4] is None else bool(row[4])
    diagnostics = json.loads(row[5])
    return dict(normal=normal,
                writer_pass=None if normal is None and diagnostics.get('reason') else normal is True,
                **diagnostics)
