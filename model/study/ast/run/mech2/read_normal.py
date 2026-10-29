"""Read-only normal attribute adapter; missing/stale rows remain open."""
import hashlib
import json
from pathlib import Path
import sqlite3


def _digest(value):
    text=json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def load_normal(database, pair_id, *, source_sha256, base_result_sha256):
    """Return a valid stored attribute for the caller's current base receipt.

    status=open means missing/stale evidence; status=unavailable is a completed
    stored-data classification whose prefix/stream evidence could not decide.
    This reader never evaluates a program or writes to either database.
    """
    path=Path(database).resolve()
    if not path.exists():return dict(status='open',normal=None,reason='normal database absent')
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute('SELECT source_sha256,base_result_sha256,code_sha256,result_sha256,record_json FROM pairs WHERE pair_id=?',(pair_id,)).fetchone()
        meta=db.execute("SELECT value FROM metadata WHERE key='code_manifest'").fetchone()
    if not row or not meta:return dict(status='open',normal=None,reason='normal receipt absent')
    source,base,code,result,text=row;manifest=json.loads(meta[0]);record=json.loads(text)
    if (source!=source_sha256 or base!=base_result_sha256 or _digest(manifest)!=code or _digest(record)!=result):
        return dict(status='open',normal=None,reason='normal receipt stale or invalid')
    for file,expected in manifest['files'].items():
        try:actual=hashlib.sha256(Path(file).read_bytes()).hexdigest()
        except OSError:return dict(status='open',normal=None,reason='normal source unavailable: '+file)
        if actual!=expected:return dict(status='open',normal=None,reason='normal source changed: '+file)
    mutant=record['mutant']
    return dict(status='unavailable' if mutant['normal'] is None else 'classified',
                normal=mutant['normal'],writer_pass=mutant.get('writer_pass'),
                gold=record['gold'],gold_point_id=record['gold_point_id'],
                reference=dict(database=str(path),table='pairs',pair_id=pair_id,result_sha256=result),
                record=record)
