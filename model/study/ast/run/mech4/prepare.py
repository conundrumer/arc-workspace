#!/usr/bin/env python3
"""Snapshot G-open queue hints from stored base/grades; no native execution."""
from common import *
import argparse
from collections import Counter
import fcntl
import time
from read_grades import load_grade


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=DATA_ROOT/'ast/run/mech/labels.sqlite3')
    ap.add_argument('--grades',type=Path,default=DATA_ROOT/'ast/run/mech/settled.sqlite3')
    ap.add_argument('--normal',type=Path,default=NORMAL_DATABASE)
    ap.add_argument('--output',type=Path,default=OUTPUT/'lib.sqlite3')
    ap.add_argument('--limit',type=int,default=0)
    a=ap.parse_args()
    if a.limit<0:ap.error('limit must be nonnegative')
    if not a.output.resolve().is_relative_to(OUTPUT.resolve()):ap.error('outputs must stay under mech4 data root')
    if a.output.resolve() in (a.base.resolve(),a.grades.resolve()):ap.error('output must be independent')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    lock=a.output.with_suffix('.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    base=readonly(a.base);base.execute('BEGIN');store=Journal(a.output)
    with store.db:
        store.db.execute('DELETE FROM queue')
        store.db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('queue',canonical(dict(ready=False))))
    total=base.execute('SELECT count(*) FROM pairs').fetchone()[0]
    counts=Counter();start=time.monotonic();last=0;done=0
    try:
        for done,row in enumerate(base.execute('SELECT pair_id,source_sha256,code_sha256,config_sha256,'
                 'result_sha256,record_json FROM pairs ORDER BY pair_id'),1):
            value=base_record(row)
            normal=normal_evidence(a.normal,value['pair_id'],value['source_sha256'],row[4])
            if normal.get('normal') is not True:
                counts['normal_excluded']+=1
                counts['non_normal' if normal.get('normal') is False else 'normal_unavailable']+=1
            elif queue_hint(value):
                availability=load_grade(a.grades,value['pair_id'])
                if availability['valid'] and availability['grade']!='Unknown':counts['already_graded']+=1
                else:
                    job=dict(schema='mech4-G-queue-v1',pair_id=value['pair_id'],task=value['task'],kind=value['kind'],
                        source=source_locator(value),base_result_ref=dict(database=str(a.base.resolve()),table='pairs',
                            pair_id=value['pair_id'],result_sha256=row[4],code_sha256=row[2],config_sha256=row[3]),
                        source_sha256=value['source_sha256'],normal_database=str(a.normal.resolve()),normal=normal,grade_database=str(a.grades.resolve()),
                        grade_availability={k:v for k,v in availability.items() if k!='record'},admission_authenticated=False,
                        scope='G only; base hint, not row-support proof or judge admission',
                        hint=dict(label=value.get('label'),operation=value.get('operation'),
                            bounded=any(i.get('witness',{}).get('reason_code')=='search_bound' for i in value.get('per_assignment',[]))))
                    inputs=dict(source_sha256=value['source_sha256'],base_result_sha256=row[4],hint=job['hint'])
                    with store.db:
                        store.db.execute('INSERT OR REPLACE INTO queue VALUES (?,?,?,?)',
                            (value['pair_id'],digest(inputs),digest(job),canonical(job)))
                    counts['queued']+=1
            elapsed=time.monotonic()-start
            if elapsed-last>=5:
                rate=done/max(elapsed,.001)
                print(f'done={done}/{total} elapsed={elapsed:.1f}s rate={rate:.2f}/s ETA={(total-done)/rate:.1f}s '
                      f'absent_normal={counts["normal_excluded"]} counts={dict(counts)}',file=sys.stderr,flush=True);last=elapsed
            if a.limit and counts['queued']>=a.limit:break
        summary=dict(schema='mech4-preparation-v1',done=done,total=total,counts=dict(counts),
            elapsed_seconds=time.monotonic()-start,output=str(a.output.resolve()),scope='G only; unauthenticated queue hints',
            normal_excluded=counts['normal_excluded'],non_normal=counts['non_normal'],
            normal_unavailable=counts['normal_unavailable'],normal_database=str(a.normal.resolve()),evaluations=0)
        a.output.with_suffix('.prepare-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        with store.db:
            store.db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('queue',canonical(dict(
                ready=True,base=str(a.base.resolve()),grades=str(a.grades.resolve()),summary=summary))))
        print(canonical(summary),file=sys.stderr,flush=True)
    finally:base.close();store.close();lock.close()


if __name__=='__main__':main()
