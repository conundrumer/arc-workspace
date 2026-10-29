#!/usr/bin/env python3
"""Build settled mechanical observations/grades for shared pair directories."""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[3]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import fcntl
from base_evidence import build
from grade_store import GradeStore
from review_metadata import load_review_metadata
from run import digest,pair_key,canonical

HERE=Path(__file__).resolve().parent
STUDY=HERE.parents[2]


def code_manifest():
    own=('base_pass.py','base_evidence.py','grade_store.py','grades.py','admission.py','clause_evidence.py',
         'review_metadata.py','corpus_index.py','outcomes.py','run.py')
    shared=('evaluator.py','checks.py','tables.py','surface.py','catalog.py','registry.py')
    files=[HERE/n for n in own]+[STUDY/'judgetool'/n for n in shared]
    files += [HERE.parent/n for n in ('native_storage.py','native_tables.py','filters.py')]
    files.append(CODE_ROOT / 'study_paths.py')
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('pairs',type=Path,help='JSONL {pair_directory}')
    ap.add_argument('--output',type=Path,default=DATA_ROOT / 'ast/run/mech/settled.sqlite3')
    ap.add_argument('--candidate-seconds',type=float,default=.5);ap.add_argument('--baseline-limit',type=int,default=32)
    a=ap.parse_args()
    if a.candidate_seconds<=0 or a.baseline_limit<0:ap.error('positive seconds and nonnegative baseline limit required')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    lock=a.output.with_suffix(a.output.suffix+'.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    sys.path.insert(0,str(STUDY/'judgetool'))
    from judge_tool import load_pair
    from evaluator import ReplayEvaluator
    ev=ReplayEvaluator(deadline=a.candidate_seconds,artifacts=DATA_ROOT / 'judgetool/replays/mech-base')
    code=code_manifest();spec=STUDY/'codex-adm/briefs/judge-decisions.md'
    config=dict(schema='mech-base-config-v1',spec_sha256=hashlib.sha256(spec.read_bytes()).hexdigest(),
                evaluator=ev.receipt,baseline_limit=a.baseline_limit)
    store=GradeStore(a.output,code,config);db=store.db
    db.execute('CREATE TABLE IF NOT EXISTS evidence(pair_id TEXT PRIMARY KEY,source TEXT,code TEXT,config TEXT,metadata TEXT,result_sha256 TEXT,payload TEXT)')
    db.execute('CREATE TABLE IF NOT EXISTS evidence_events(seq INTEGER PRIMARY KEY AUTOINCREMENT,pair_id TEXT,result_sha256 TEXT,UNIQUE(pair_id,result_sha256))')
    with db:db.execute('INSERT OR IGNORE INTO evidence_events(pair_id,result_sha256) SELECT pair_id,result_sha256 FROM evidence')
    with a.pairs.open() as src:total=sum(1 for line in src if line.strip())
    start=time.monotonic();done=0;skip=0
    try:
        with a.pairs.open() as src:
            for line_number,line in enumerate(src,1):
                if not line.strip():continue
                try:
                    directory=Path(json.loads(line)['pair_directory']).resolve()
                    manifest,record,target=load_pair(directory)
                    pair_id=digest(pair_key(record));source=digest(record)
                    metadata=load_review_metadata(directory/'manifest.json',record)
                    metadata_hash=digest(metadata)
                    row=db.execute('SELECT source,code,config,metadata,result_sha256,payload FROM evidence WHERE pair_id=?',(pair_id,)).fetchone()
                    expected=(source,store.code,store.config_hash,metadata_hash)
                    if row and tuple(row[:4])==expected and digest(json.loads(row[5]))==row[4]:
                        evidence=json.loads(row[5]);skip+=1
                    else:
                        ref=dict(database=str(a.output.resolve()),table='evidence',pair_id=pair_id)
                        evidence=build(ev,record,metadata,ntrain=target['ntrain'],ntest=target['ntest'],
                                       receipt_ref=ref,baseline_limit=a.baseline_limit)
                        evidence['source_metadata']=dict(manifest_ref=metadata['manifest_ref'],
                                                        source_receipt=metadata['source_receipt'])
                        if code_manifest()!=code:raise RuntimeError('labeling source changed; restart to avoid stale code receipt')
                        with db:
                            db.execute('INSERT OR REPLACE INTO evidence VALUES (?,?,?,?,?,?,?)',
                                       (pair_id,*expected,digest(evidence),canonical(evidence)))
                            db.execute('INSERT OR IGNORE INTO evidence_events(pair_id,result_sha256) VALUES (?,?)',(pair_id,digest(evidence)))
                    result,_=store.save(evidence,inputs_authenticated=True)
                    done+=1;elapsed=time.monotonic()-start;rate=done/max(elapsed,.001)
                    print(f'done={done}/{total} elapsed={elapsed:.1f}s rate={rate:.3f}/s ETA={(total-done)/max(rate,.001):.1f}s skip={skip} grade={result["grade"]}',file=sys.stderr,flush=True)
                    ev.finish_case()
                except Exception as error:raise RuntimeError(f'{a.pairs}:{line_number}: {error}') from error
    finally:ev.close();store.close();lock.close()


if __name__=='__main__':main()
