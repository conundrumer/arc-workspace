"""Read-only validity adapter; a valid bounded result is never a negative."""
from .common import readonly,digest
from pathlib import Path
from functools import lru_cache
import hashlib
import json
import zlib


@lru_cache(maxsize=512)
def _hash(path,signature):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def file_hash(path):
    path=Path(path);s=path.stat()
    return _hash(str(path),(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns))


def load_result(database,pair_id,*,source_sha256,base_result_sha256):
    """Return status done/open, valid, checked mechanical clauses and search status.

    Caller supplies CURRENT source and immutable base-result digests. Candidate
    rows are authenticated by their durable producer receipts. No evaluation or
    final grade/admission policy is run here. Unknown/unavailable stays open to
    other searches even when this attempt has a valid completed record.
    """
    db=None
    try:
        path=Path(database).resolve();db=readonly(path);db.execute('BEGIN')
        key=digest(dict(pair=pair_id,target='G'))
        row=db.execute('SELECT code_sha256,config_sha256,result_sha256,payload FROM records '
                       'WHERE kind=? AND key=?',('pair',key)).fetchone()
        if not row:return dict(status='open',valid=False,reason='no G-lib result')
        result=json.loads(zlib.decompress(row[3]))
        if (digest(result)!=row[2] or result['pair_id']!=pair_id or result['source_sha256']!=source_sha256
                or result['base_result_ref']['result_sha256']!=base_result_sha256
                or digest(result['code_manifest'])!=row[0] or result['code_sha256']!=row[0]
                or digest(result['config'])!=row[1] or result['config_sha256']!=row[1]):
            raise ValueError('pair/source/base/code/config/result receipt differs')
        if result.get('interrupted'):raise ValueError('pair was interrupted before completion')
        for name,expected in result['code_manifest'].items():
            # Older manifests included the prose specification. Preserve its
            # stored digest without consulting the removed/mutable document.
            if Path(name).parts[-3:]==('codex-adm','briefs','judge-decisions.md'):continue
            if file_hash(name)!=expected:raise ValueError('producer dependency changed: '+name)
        for clause in result.get('mechanical_clauses',[]):
            ref=clause['receipt_ref']
            if Path(ref['database']).resolve()!=path or ref['table']!='records' or ref['kind']!='candidate':
                raise ValueError('candidate reference is outside this journal')
            candidate=db.execute('SELECT code_sha256,config_sha256,result_sha256,payload FROM records '
                'WHERE kind=? AND key=?',('candidate',ref['key'])).fetchone()
            if not candidate or tuple(candidate[:3])!=(row[0],row[1],ref['result_sha256']):
                raise ValueError('candidate producer receipt differs')
            raw=json.loads(zlib.decompress(candidate[3]))
            if (digest(raw)!=candidate[2] or raw.get('source_sha256')!=source_sha256
                    or raw.get('target_id')!='G' or clause['tool_result_sha256']!=candidate[2]):
                raise ValueError('candidate source/target/result differs')
        found=any(c.get('outcome')=='recovery verified' for c in result.get('mechanical_clauses',[]))
        if result.get('found_recovery') is not found:
            raise ValueError('recovery summary differs from checked clauses')
        if any(c.get('target_id')!='G' for c in result.get('mechanical_clauses',[])):
            raise ValueError('checked clause outside G scope')
        return dict(status='done',valid=True,search_status=result['search_status'],record=result,
                    found_recovery=result.get('found_recovery') is True,
                    mechanical_clauses=result.get('mechanical_clauses',[]),result_sha256=row[2],
                    final_grade=None,admission_authenticated=False)
    except Exception as error:return dict(status='open',valid=False,reason=str(error),error_type=type(error).__name__)
    finally:
        if db is not None:db.close()
