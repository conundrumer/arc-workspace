#!/usr/bin/env python3
"""Index host submissions or legacy finals; no grades or evidence copies.

Jobs: pair_directory, base_evidence path, final_result path. The final artifact
remains the authoritative clause outcome store; only authenticated locators are
indexed here for the read-time join.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from study_paths import CODE_ROOT,DATA_ROOT
import argparse
import hashlib
import json
import sqlite3
from run import digest,pair_key,canonical


def index_submissions(db,base,paths):
    from judge_submission import submission_loader,submission_reference,load_submission_reference,data_file
    submission_loader()  # reject an incomplete runner deployment before work
    for path in paths:
        path=data_file(path);value=json.loads(path.read_text());pair=value['pair_id']
        row=base.execute('SELECT source_sha256,result_sha256,record_json FROM pairs WHERE pair_id=?',(pair,)).fetchone()
        if row is None:raise ValueError('judge pair absent from base: '+pair)
        record=json.loads(row[2])
        if record['pair_id']!=pair or record['source_sha256']!=row[0] or digest(record)!=row[1]:
            raise ValueError('judge base/source integrity differs')
        reference=submission_reference(path)
        checked=load_submission_reference(reference,record)
        if checked.get('status')!='available':raise ValueError(checked.get('reason','submission unavailable'))
        # Store only artifact locators/identities. Native outcomes, completion
        # proofs and the answer remain in their original host/tool artifacts.
        with db:db.execute('INSERT OR IGNORE INTO judge_submissions VALUES (?,?,?,?)',
            (pair,row[0],reference['path'],reference['sha256']))
        print(json.dumps(dict(pair_id=pair,status='indexed',submission=reference)),flush=True)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('jobs',type=Path,nargs='?',help='legacy final-v3 jobs JSONL')
    ap.add_argument('--submissions',type=Path,nargs='+',help='judge-submission-v1 artifact paths')
    ap.add_argument('--base',type=Path,default=DATA_ROOT/'ast/run/mech/labels.sqlite3')
    ap.add_argument('--output',type=Path,default=DATA_ROOT/'ast/run/mech/judge.sqlite3');a=ap.parse_args()
    if not a.jobs and not a.submissions:ap.error('provide --submissions or legacy jobs')
    if a.output.resolve() in (a.base.resolve(),(DATA_ROOT/'ast/run/mech/settled.sqlite3').resolve()):
        ap.error('judge artifact index must be separate from base/witness stores')
    if a.submissions:
        from judge_submission import submission_loader
        submission_loader()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(a.output);db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL')
    db.execute('CREATE TABLE IF NOT EXISTS judge_sessions(pair_id TEXT,session_sha256 TEXT,payload TEXT,PRIMARY KEY(pair_id,session_sha256))')
    db.execute('CREATE TABLE IF NOT EXISTS judge_submissions(pair_id TEXT,source_sha256 TEXT,path TEXT,sha256 TEXT,PRIMARY KEY(pair_id,sha256))')
    db.commit()
    try:
        if a.submissions:
            base=sqlite3.connect(a.base.resolve().as_uri()+'?mode=ro',uri=True)
            try:index_submissions(db,base,a.submissions)
            finally:base.close()
        if not a.jobs:return
        sys.path.insert(0,str(CODE_ROOT/'judgetool'))
        from judge_tool import load_pair
        with a.jobs.open() as stream:
            for line in stream:
                if not line.strip():continue
                job=json.loads(line);manifest,record,target=load_pair(job['pair_directory'])
                base=json.loads(Path(job['base_evidence']).read_text())
                if base['pair_id']!=digest(pair_key(record)) or base['source_sha256']!=digest(record):raise ValueError('judge source/base binding differs')
                final_path=Path(job['final_result']).resolve();final=json.loads(final_path.read_bytes())
                if final.get('schema')!='judge-tool-final-v3' or final.get('source_sha256')!=digest(record):raise ValueError('checked final binding differs')
                record_path=Path(target['adapter']['source']['record_path']).resolve()
                manifest_path=Path(job['pair_directory']).resolve()/'manifest.json'
                value=dict(source_sha256=digest(record),base_result_sha256=base['base_result_ref']['result_sha256'],
                    final_path=str(final_path),final_sha256=hashlib.sha256(final_path.read_bytes()).hexdigest(),
                    record_path=str(record_path),record_sha256=hashlib.sha256(record_path.read_bytes()).hexdigest(),
                    manifest_path=str(manifest_path),manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                    ntrain=target['ntrain'],ntest=target['ntest'])
                with db:db.execute('INSERT OR IGNORE INTO judge_sessions VALUES (?,?,?)',(base['pair_id'],digest(value),canonical(value)))
    finally:db.close()


if __name__=='__main__':main()
