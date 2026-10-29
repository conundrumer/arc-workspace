#!/usr/bin/env python3
"""Durably grade checked judge finals together with mechanical evidence.

Jobs JSONL: pair_directory, base_evidence (JSON path), final_result (JSON path).
Inputs are checked tool artifacts, NOT judge answers. Native evidence authority
for admission is not invented here; unknown input receipts stay unavailable.
"""
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
from grade_store import GradeStore
from judge_merge import merge_final
from clause_evidence import digest

HERE=Path(__file__).resolve().parent
STUDY=HERE.parents[2]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('jobs',type=Path)
    ap.add_argument('--output',type=Path,default=DATA_ROOT / 'ast/run/mech/grades.sqlite3');a=ap.parse_args()
    sys.path.insert(0,str(STUDY/'judgetool'))
    from judge_tool import load_pair
    paths=[HERE/n for n in ('grade_judge.py','grade_store.py','judge_merge.py','grades.py','admission.py','clause_evidence.py','outcomes.py','run.py')]
    paths += [STUDY/'judgetool'/n for n in ('judge_tool.py','evaluator.py')]
    paths.append(CODE_ROOT / 'study_paths.py')
    code={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    spec=STUDY/'codex-adm/briefs/judge-decisions.md';spec_hash=hashlib.sha256(spec.read_bytes()).hexdigest()
    store=GradeStore(a.output,code,dict(schema='mech-judge-grade-config-v1',spec_sha256=spec_hash))
    with a.jobs.open() as src:total=sum(1 for line in src if line.strip())
    start=time.monotonic();last=0;done=0;skip=0
    try:
        with a.jobs.open() as src:
            for lineno,line in enumerate(src,1):
                if not line.strip():continue
                try:
                    job=json.loads(line)
                    manifest,record,target=load_pair(job['pair_directory'])
                    base=json.loads(Path(job['base_evidence']).read_text())
                    path=Path(job['final_result']).resolve();raw=path.read_bytes();final=json.loads(raw)
                    if final.get('specification_sha256')!=spec_hash:
                        raise ValueError('checked final specification hash differs; rerun tool final')
                    ref=dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),canonical_sha256=digest(final))
                    evidence,_=merge_final(record,manifest,target,base,final,ref)
                    # Persist combined evidence first, in the same durable DB;
                    # grade receipts remain inspectable and source-bound.
                    db=store.db
                    db.execute('CREATE TABLE IF NOT EXISTS merged_evidence(pair_id TEXT PRIMARY KEY,result_sha256 TEXT,payload TEXT)')
                    from outcomes import canonical
                    with db:db.execute('INSERT OR REPLACE INTO merged_evidence VALUES (?,?,?)',
                                       (evidence['pair_id'],digest(evidence),canonical(evidence)))
                    _,was_skip=store.save(evidence,inputs_authenticated=False)
                    skip+=was_skip;done+=1
                except Exception as error:
                    raise RuntimeError(f'{a.jobs}:{lineno}: {error}') from error
                elapsed=time.monotonic()-start
                if elapsed-last>=5:
                    rate=done/max(elapsed,.001)
                    print(f'done={done}/{total} elapsed={elapsed:.1f}s rate={rate:.2f}/s ETA={(total-done)/max(rate,.001):.1f}s skip={skip}',file=sys.stderr,flush=True);last=elapsed
    finally:store.close()
    elapsed=time.monotonic()-start
    print(f'done={done}/{total} elapsed={elapsed:.1f}s rate={done/max(elapsed,.001):.2f}/s ETA=0s skip={skip}',file=sys.stderr,flush=True)


if __name__=='__main__':main()
