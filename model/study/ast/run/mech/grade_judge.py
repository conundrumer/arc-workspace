#!/usr/bin/env python3
"""Index checked tool final artifacts; no grades or copied evidence are stored.

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


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('jobs',type=Path)
    ap.add_argument('--output',type=Path,default=DATA_ROOT/'ast/run/mech/judge.sqlite3');a=ap.parse_args()
    sys.path.insert(0,str(CODE_ROOT/'judgetool'))
    from judge_tool import load_pair
    db=sqlite3.connect(a.output);db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL')
    db.execute('CREATE TABLE IF NOT EXISTS judge_sessions(pair_id TEXT,session_sha256 TEXT,payload TEXT,PRIMARY KEY(pair_id,session_sha256))')
    try:
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
