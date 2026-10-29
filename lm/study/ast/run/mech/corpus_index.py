#!/usr/bin/env python3
"""Index all published retained AND filtered sources, without replaying pairs."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import time
from run import published_task,records,pair_key,digest,canonical

FILTERS=('empty_mutant','equal_gold','equal_available','equal_later_gold','no_dependency_path')


def filter_labels(record):
    filters=record.get('filters',{})
    classes=[k for k in FILTERS if filters.get(k,{}).get('status')=='complete'
             and filters[k].get('reject') is True]
    incomplete=[k for k in FILTERS if filters.get(k,{}).get('status')!='complete']
    return dict(filter_class=classes[0] if classes else 'unknown' if incomplete else None,
                filter_classes=classes,filter_incomplete=incomplete,
                filter_authority='stored corpus filter; not settled target/test grade')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('corpora',type=Path,nargs='+');p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(a.output);db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL')
    db.execute('CREATE TABLE IF NOT EXISTS sources(pair_id TEXT,source_sha256 TEXT,result_sha256 TEXT,payload TEXT,PRIMARY KEY(pair_id,source_sha256))')
    code=hashlib.sha256(Path(__file__).read_bytes()+(Path(__file__).parent/'run.py').read_bytes()).hexdigest()
    tasks=[task for corpus in a.corpora for task in sorted(corpus.resolve().iterdir()) if published_task(task)]
    start=time.monotonic();last=0;done=0;pairs=0;skip=0
    for task in tasks:
        for stream,file,line,record in records(task,('kept','recovered'),include_filtered=True):
            pair_id=digest(pair_key(record));source=digest(record)
            result=dict(schema='mech-source-index-v1',pair_id=pair_id,source_sha256=source,
                        code_sha256=code,key=pair_key(record),kind=record['kind'],
                        source=dict(corpus=str(task.parent),file=task.name+'/'+file,line=line,stream=stream),
                        retained=record.get('retained'),**filter_labels(record))
            old=db.execute('SELECT result_sha256,payload FROM sources WHERE pair_id=? AND source_sha256=?',(pair_id,source)).fetchone()
            if old and digest(json.loads(old[1]))==old[0] and json.loads(old[1]).get('code_sha256')==code:
                skip+=1
            else:
                with db:db.execute('INSERT OR REPLACE INTO sources VALUES (?,?,?,?)',(pair_id,source,digest(result),canonical(result)))
            pairs+=1
            elapsed=time.monotonic()-start
            if elapsed-last>=5:
                rate=done/max(elapsed,.001)
                print(f'tasks done={done}/{len(tasks)} elapsed={elapsed:.1f}s rate={rate:.3f}/s '
                      f'ETA={(len(tasks)-done)/rate if rate else float("inf"):.1f}s pairs={pairs} skip={skip}',file=sys.stderr,flush=True)
                last=elapsed
        done+=1
    elapsed=time.monotonic()-start
    print(f'tasks done={done}/{len(tasks)} elapsed={elapsed:.1f}s rate={done/max(elapsed,.001):.3f}/s ETA=0s pairs={pairs} skip={skip}',file=sys.stderr,flush=True)
    db.close()


if __name__=='__main__':main()
