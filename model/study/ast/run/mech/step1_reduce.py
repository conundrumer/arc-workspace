#!/usr/bin/env python3
"""STEP 1: grade stored base evidence only; no native acquisition/evaluation.

Every row gets a durable grade. Evidence owed by subsequent steps is Unknown
with explicit missing step names. Original labels.sqlite3 is read-only.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[3]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
import fcntl

from grade_store import GradeStore
from run import canonical,digest

HERE=Path(__file__).resolve().parent
STUDY=HERE.parents[2]


def adapt(record,base_ref):
    label=record.get('label');assignments=record.get('per_assignment',[])
    train_witness=(not record.get('error') and bool(assignments)
                   and all(a.get('witness',{}).get('recoverable') is True
                           and a.get('witness',{}).get('verified') is True for a in assignments))
    # Some original records store verified directly on the assignment witness;
    # selection_found itself is retained as a queue hint, never proof of a grade.
    if not train_witness and record.get('selection_found') is True:
        train_witness=bool(assignments) and all(a.get('recoverable') is True for a in assignments)
    missing=[]
    if record.get('error'):
        missing.append('step_7_move_retry' if 'edb3e4ef' in record.get('pair_id','') or 'native/tables.pack' in str(record.get('error'))
                       else 'step_3_incomplete_base_evidence')
    elif label=='equivalent':missing.append('step_3_all_target_equality_and_test')
    elif train_witness:missing.append('step_2_witness_test_check')
    elif record.get('fits') is True:missing.append('step_4_program_fit_and_reader_difference')
    else:missing.append('step_3_all_target_comparison_and_search')
    # All classes are provisional until all-target policy is applied. This is
    # especially important for a G-only lossy result: it is NOT a Reject.
    if 'step_3_all_target_comparison_and_search' not in missing and label!='equivalent':
        missing.append('step_3_all_target_comparison_and_search')
    if record.get('fits') is True and 'step_4_program_fit_and_reader_difference' not in missing:
        missing.append('step_4_program_fit_and_reader_difference')
    source=record['source'];corpus=Path(source['corpus']).resolve()
    locator=dict(schema='mech-source-v1',corpus=str(corpus),file=record['task']+'/'+source['file'],
                 line=source['line'],stream=source['stream'],mechanical_pair_id=record['pair_id'],
                 pool_pair_id=record['pool_pair_id'],source_sha256=record['source_sha256'])
    bounds=any(a.get('witness',{}).get('reason_code')=='search_bound' for a in assignments)
    evidence=dict(schema='mech-grade-evidence-v1',step=1,pair_id=record['pair_id'],
                  source_sha256=record['source_sha256'],source=locator,kind=record['kind'],
                  base_result_ref=base_ref,missing_steps=missing,
                  program=dict(fits_train=True if record.get('fits') is True else None,
                               fits_test=None,complete=False,receipt_ref=base_ref),
                  comparisons=dict(point=dict(complete=False,receipt_ref=base_ref,
                      legacy_G_relation=record.get('table_relation'),legacy_G_missing=record.get('missing')),
                      targets=[],reader_difference={},recovery_support=dict(complete=False,all_targets_lossy=None)),
                  target_catalog=dict(complete=False,receipt_ref=None),
                  search=dict(status='bound_unknown' if bounds else 'not_covered',complete=False,
                              settled_space=False,unvisited=None,receipt_ref=base_ref),
                  redundant=record.get('redundant'),sibling=record.get('sibling'),
                  clauses=[],mechanical_clauses=[],
                  legacy=dict(label=label,search=record.get('search'),selection_found=record.get('selection_found'),
                              train_witness=train_witness,base_error=bool(record.get('error')),
                              attributes_scope='stored base training/available-table grammar'),
                  witnesses_ref=dict(**base_ref,field='per_assignment',test_verified=None),
                  filter_class=None)
    return evidence


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=DATA_ROOT / 'ast/run/mech/labels.sqlite3')
    ap.add_argument('--output',type=Path,default=DATA_ROOT / 'ast/run/mech/settled.sqlite3')
    ap.add_argument('--summary',type=Path,default=DATA_ROOT / 'ast/run/mech/step1-summary.json')
    a=ap.parse_args()
    if a.base.resolve()==a.output.resolve():ap.error('base and output must differ')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    lock=a.output.with_suffix('.step1.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    files=[HERE/n for n in ('step1_reduce.py','grades.py','grade_store.py','admission.py','clause_evidence.py','outcomes.py','run.py')]
    files.append(CODE_ROOT / 'study_paths.py')
    code={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    config=dict(schema='mech-step1-config-v1',base=str(a.base.resolve()),
                spec_sha256=hashlib.sha256((STUDY/'codex-adm/briefs/judge-decisions.md').read_bytes()).hexdigest(),
                policy='stored-only; all-target lossy; every positive awaits owed checks')
    base=sqlite3.connect(a.base.resolve().as_uri()+'?mode=ro',uri=True);base.execute('BEGIN')
    store=GradeStore(a.output,code,config);db=store.db
    db.execute('CREATE TABLE IF NOT EXISTS evidence(pair_id TEXT PRIMARY KEY,source TEXT,code TEXT,config TEXT,metadata TEXT,result_sha256 TEXT,payload TEXT)')
    total=base.execute('SELECT count(*) FROM pairs').fetchone()[0]
    counts=Counter();owed=Counter();labels=Counter();done=0;skipped=0;errors=0;last=0;start=time.monotonic()
    try:
        for pair_id,source,producer_code,producer_cfg,result_hash,payload in base.execute(
                'SELECT pair_id,source_sha256,code_sha256,config_sha256,result_sha256,record_json FROM pairs ORDER BY pair_id'):
            record=json.loads(payload)
            if (digest(record)!=result_hash or record['pair_id']!=pair_id or record['source_sha256']!=source
                    or record['code_sha256']!=producer_code or record['config_sha256']!=producer_cfg
                    or digest(record['code_manifest'])!=producer_code or digest(record['config'])!=producer_cfg):
                raise ValueError('base receipt integrity differs: '+pair_id)
            ref=dict(database=str(a.base.resolve()),table='pairs',pair_id=pair_id,
                     result_sha256=result_hash,code_sha256=producer_code,config_sha256=producer_cfg)
            evidence=adapt(record,ref)
            # Reusing the original base receipt is valid stored evidence, not a
            # new native admission/test receipt. No fake input authentication.
            evidence_hash=digest(evidence)
            with db:
                existing=db.execute('SELECT result_sha256,code,config FROM evidence WHERE pair_id=?',(pair_id,)).fetchone()
                if not existing or tuple(existing)!=(evidence_hash,store.code,store.config_hash):
                    db.execute('INSERT OR REPLACE INTO evidence VALUES (?,?,?,?,?,?,?)',
                        (pair_id,source,store.code,store.config_hash,result_hash,evidence_hash,canonical(evidence)))
                result,was_skip=store.save(evidence,inputs_authenticated=False)
            counts[result['grade']]+=1;owed.update(result.get('missing_steps',[]));labels[record.get('label')]+=1
            errors+=bool(record.get('error'));skipped+=was_skip;done+=1
            elapsed=time.monotonic()-start
            if elapsed-last>=5:
                rate=done/max(elapsed,.001)
                print(f'done={done}/{total} elapsed={elapsed:.1f}s rate={rate:.2f}/s ETA={(total-done)/rate:.1f}s write={done-skipped} skip={skipped} grades={dict(counts)}',file=sys.stderr,flush=True);last=elapsed
        elapsed=time.monotonic()-start
        summary=dict(schema='mech-step-summary-v1',step=1,base=str(a.base.resolve()),output=str(a.output.resolve()),
                     total=total,done=done,grade_counts=dict(counts),missing_step_counts=dict(owed),base_label_counts=dict(labels),
                     base_error_records=errors,writes=done-skipped,skips=skipped,elapsed_seconds=elapsed,
                     code_sha256=store.code,config_sha256=store.config_hash,evaluations=0)
        a.summary.write_text(json.dumps(summary,indent=2)+'\n')
        print(f'done={done}/{total} elapsed={elapsed:.1f}s rate={done/max(elapsed,.001):.2f}/s ETA=0s grades={dict(counts)} errors={errors} skip={skipped}',file=sys.stderr,flush=True)
    finally:store.close();base.close();lock.close()


if __name__=='__main__':main()
