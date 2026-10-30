#!/usr/bin/env python3
"""Run and check one judge clause through the shared existing-bindings evaluator."""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

sys.dont_write_bytecode=True
from evaluator import ReplayEvaluator,HERE,read_json,open_source,canonical,sha


def load_pair(directory):
    directory=Path(directory).resolve(); manifest=read_json(directory/'manifest.json');adapter=manifest['adapter']
    path=Path(adapter['source']['record_path']).resolve()
    raw=gzip.open(path,'rb').read() if path.suffix=='.gz' else path.read_bytes()
    # Renderer hashes the original decoded JSONL line (including its newline),
    # separately from the canonical source digest used by mechanical consumers.
    expected=adapter['source'].get('record_sha256')
    if expected and hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError('render source raw JSON hash mismatch')
    record,source=open_source(path)
    taskpath=Path(adapter['source']['task_path']).resolve();task=read_json(taskpath)
    return manifest,record,dict(adapter=adapter,source=dict(source,source_sha256=source['sha256']),
        target_id='G',ntrain=len(task['train']),ntest=len(task['test']),
        catalog_complete=adapter.get('target_catalog',{}).get('complete') is True)


def check_answer(ev,manifest,record,target,answer,row_limit):
    if not isinstance(answer,dict) or set(answer)-{'schema','pair_id','render_version','clauses'}:
        raise ValueError('answer contains unsupported fields; do not supply a label or grade')
    if answer.get('schema')!='judge-tool-answer-v3' or answer.get('pair_id')!=manifest['pair_id'] or answer.get('render_version')!=manifest['render_version']:
        raise ValueError('answer schema/pair/version mismatch')
    if not isinstance(answer.get('clauses'),list):raise ValueError('clauses must be a list (empty if none found)')
    outcomes=[]
    for item in answer['clauses']:
        if set(item)-{'kind','clause','columns','reasons'} or item.get('kind') not in ('recovery','alternative'):
            raise ValueError('each answer clause requires kind recovery or alternative')
        reasons=item.get('reasons')
        if not isinstance(reasons,list) or not 1<=len(reasons)<=2 or any(not isinstance(r,str) or not r.strip() for r in reasons):
            raise ValueError('each clause requires one or two evidence reasons')
        try:
            outcome=ev.evaluate(record,item['clause'],dict(target,mode=item['kind']),item.get('columns'),row_limit=row_limit)
        except Exception as error:
            outcome=dict(outcome='unknown',verified=False,submitted_clause=item['clause'],
                         source_sha256=sha(record),reason=f'{type(error).__name__}: {error}')
        outcomes.append(dict(outcome,kind=item['kind'],reasons=reasons))
    admission=target['adapter'].get('admission',{})
    admitted=admission.get('eligible') is True and admission.get('receipt_authenticated') is True
    return dict(schema='judge-tool-final-v3',pair_id=manifest['pair_id'],render_version=manifest['render_version'],
                no_clause_found=not bool(outcomes),outcomes=outcomes,
                source_sha256=sha(record),adapter_sha256=sha(target['adapter']),
                judge_run=dict(completed=admitted and all(o.get('outcome')!='unknown' for o in outcomes),
                               clauses_checked=True,admission_authenticated=admitted,
                               no_kept_entry=any(o.get('missing_contexts') for o in outcomes)),
                instruction='labeler assigns the grade from checked evidence; no judge label or grade')


def main():
    # The public judge interface is data-only. Keep load_pair/check_answer above
    # as compatibility imports for existing stored-result consumers.
    sys.path.insert(0, str(CODE_ROOT / 'judge3'))
    from clause_command import main as data_main
    return data_main()


if __name__=='__main__':raise SystemExit(main())
