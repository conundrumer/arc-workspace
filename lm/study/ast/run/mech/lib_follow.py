#!/usr/bin/env python3
"""Follow committed settled evidence; run eligible pairs through lib_pass.py.

Event cursor advances only after durable candidate/pair output. Restart reuses
that output and never turns a missing row into a negative. No live producer edit.
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[3]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse
import json
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
import fcntl
from grades import judge_eligible
from run import digest,canonical

HERE=Path(__file__).resolve().parent
STOP=False
CHILD=None


def stop(signum,frame):
    global STOP
    STOP=True
    if CHILD is not None:CHILD.terminate()


def main():
    global CHILD
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=DATA_ROOT / 'ast/run/mech/settled.sqlite3')
    ap.add_argument('--output',type=Path,default=DATA_ROOT / 'ast/run/mech/lib.sqlite3')
    ap.add_argument('--state',type=Path,default=DATA_ROOT / 'ast/run/mech/lib-follower.sqlite3')
    ap.add_argument('--batch',type=int,default=32);ap.add_argument('--once',action='store_true')
    ap.add_argument('--limit',type=int,default=0)
    ap.add_argument('--seconds',type=float,default=30);ap.add_argument('--candidate-seconds',type=float,default=.5)
    ap.add_argument('--max-candidates',type=int,default=128)
    a=ap.parse_args()
    if a.batch<1 or a.limit<0:ap.error('positive batch and nonnegative limit required')
    a.state.parent.mkdir(parents=True,exist_ok=True)
    lock=a.state.with_suffix('.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    state=sqlite3.connect(a.state);state.execute('PRAGMA journal_mode=WAL');state.execute('PRAGMA synchronous=FULL')
    state.execute('CREATE TABLE IF NOT EXISTS cursors_v2(scope TEXT PRIMARY KEY,seq INTEGER)')
    from lib_pass import manifest as search_manifest
    scope=digest(dict(base=str(a.base.resolve()),output=str(a.output.resolve()),
                      code=search_manifest(),follower_sha256=__import__('hashlib').sha256(Path(__file__).read_bytes()).hexdigest(),
                      python=sys.executable,seconds=a.seconds,candidate_seconds=a.candidate_seconds,max_candidates=a.max_candidates))
    row=state.execute('SELECT seq FROM cursors_v2 WHERE scope=?',(scope,)).fetchone();cursor=row[0] if row else 0
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    start=time.monotonic();done=0;eligible=0
    try:
        while not STOP:
            if not a.base.exists():
                print('done=0/unknown elapsed=0 rate=0/s ETA=unknown waiting=base-publication',file=sys.stderr,flush=True)
                if a.once:break
                time.sleep(5);continue
            db=sqlite3.connect(a.base.resolve().as_uri()+'?mode=ro',uri=True);db.execute('BEGIN')
            if not db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='evidence_events'").fetchone():
                db.close()
                print('done=0/unknown elapsed=0 rate=0/s ETA=unknown waiting=base-schema',file=sys.stderr,flush=True)
                if a.once:break
                time.sleep(5);continue
            total=db.execute('SELECT count(*) FROM evidence_events WHERE seq>?',(cursor,)).fetchone()[0]
            events=db.execute('SELECT seq,pair_id,result_sha256 FROM evidence_events WHERE seq>? ORDER BY seq LIMIT ?',(cursor,a.batch)).fetchall()
            jobs=[];last=cursor;processed=0
            for seq,pair_id,event_hash in events:
                last=seq;processed+=1
                row=db.execute('SELECT result_sha256,payload FROM evidence WHERE pair_id=?',(pair_id,)).fetchone()
                if not row or row[0]!=event_hash:continue
                evidence=json.loads(row[1])
                if digest(evidence)!=event_hash:raise ValueError('base evidence digest differs')
                if not judge_eligible(evidence):continue
                manifest_path=Path(evidence['source_metadata']['manifest_ref']['path']).resolve()
                manifest=json.loads(manifest_path.read_text());adapter=manifest['adapter']
                task=json.loads(Path(adapter['source']['task_path']).read_text())
                jobs.append(dict(record_path=adapter['source']['record_path'],source_sha256=evidence['source_sha256'],
                    manifest_path=str(manifest_path),base_evidence=evidence,ntrain=len(task['train']),ntest=len(task['test']),
                    plan=dict(schema='mech-lib-plan-v1',registry=True,max_registry_atoms=256,per_relation=32)))
                if a.limit and eligible+len(jobs)>=a.limit:break
            db.close()
            if not events:
                elapsed=time.monotonic()-start
                print(f'done={done}/{done} elapsed={elapsed:.1f}s rate={done/max(elapsed,.001):.3f}/s ETA=unknown waiting=new-commits eligible={eligible}',file=sys.stderr,flush=True)
                if a.once:break
                time.sleep(5);continue
            if jobs:
                batch=a.state.with_suffix('.jobs.jsonl')
                with batch.open('w') as stream:
                    for job in jobs:stream.write(canonical(job)+'\n')
                    stream.flush()
                    __import__('os').fsync(stream.fileno())
                command=[sys.executable,'-B',str(HERE/'lib_pass.py'),str(batch),'--output',str(a.output.resolve()),
                         '--seconds',str(a.seconds),'--candidate-seconds',str(a.candidate_seconds),'--max-candidates',str(a.max_candidates)]
                CHILD=subprocess.Popen(command);status=CHILD.wait();CHILD=None
                if STOP:break
                if status:raise RuntimeError('lib pass failed, cursor unchanged: '+str(status))
            with state:state.execute('INSERT OR REPLACE INTO cursors_v2 VALUES (?,?)',(scope,last))
            cursor=last;done+=processed;eligible+=len(jobs)
            elapsed=time.monotonic()-start;rate=done/max(elapsed,.001)
            print(f'done={done}/{done+max(total-processed,0)} elapsed={elapsed:.1f}s rate={rate:.3f}/s ETA={max(total-processed,0)/max(rate,.001):.1f}s eligible={eligible}',file=sys.stderr,flush=True)
            if a.limit and eligible>=a.limit:break
    finally:
        if CHILD is not None:CHILD.terminate();CHILD.wait()
        state.close();lock.close()


if __name__=='__main__':main()
