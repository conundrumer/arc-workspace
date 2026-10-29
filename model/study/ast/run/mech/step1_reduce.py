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
    source=record['source'];corpus=Path(source['corpus'])
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
    # Historical entrypoint retained as a read-only count, not a materialization.
    from read_grades import read_pairs
    ap=argparse.ArgumentParser(description='Read-time grade counts; writes no database')
    ap.add_argument('--base',type=Path,default=DATA_ROOT/'ast/run/mech/labels.sqlite3')
    ap.add_argument('--output',type=Path,default=DATA_ROOT/'ast/run/mech/settled.sqlite3',help='existing witness journal, read-only')
    a=ap.parse_args();counts=Counter();opened=0
    for row in read_pairs(paths=dict(base=a.base,witness_tests=a.output)):
        if row.get('valid'):counts[row['grade']]+=1
        else:opened+=1
    print(json.dumps(dict(grade_counts=dict(counts),open=opened,read_only=True),sort_keys=True))


if __name__=='__main__':main()
