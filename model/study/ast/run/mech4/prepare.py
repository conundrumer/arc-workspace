#!/usr/bin/env python3
"""Preview the G-open population from authoritative stores; writes no queue."""
from common import *
import argparse
from collections import Counter
import time


class RoutingReader:
    """Reuse the owner's bulk join when available; never copy grade policy."""
    def __init__(self,base,grades,lib=None):
        import read_grades
        self.module=read_grades;self.reader=None;self.grades=grades
        if hasattr(read_grades,'StudyReader'):
            paths=dict(base=base,witness_tests=grades)
            if lib is not None:paths['lib_search']=lib
            self.reader=read_grades.StudyReader(paths=paths)
    def read(self,pair_id,source_record=None):
        if self.reader is not None:return self.reader.read_pair(pair_id,source_record=source_record)
        return self.module.load_grade(self.grades,pair_id,source_record=source_record)
    def close(self):
        if self.reader is not None:self.reader.close()


def jobs(base_database,grades_database,*,progress=None,limit=0,lib_database=None,defer_routing=False):
    db=readonly(base_database);db.execute('BEGIN')
    routing=None if defer_routing else RoutingReader(base_database,grades_database,lib_database)
    counts=Counter();total=db.execute('SELECT count(*) FROM pairs').fetchone()[0]
    try:
        for done,row in enumerate(db.execute('SELECT pair_id,source_sha256,code_sha256,config_sha256,'
                'result_sha256,record_json FROM pairs ORDER BY pair_id'),1):
            value=base_record(row)
            if queue_hint(value):
                current=routing.read(value['pair_id']) if routing is not None else None
                if current is not None and current['valid'] and current['grade']!='Unknown':counts['routing_skipped']+=1
                else:
                    counts['queued']+=1
                    yield dict(pair_id=value['pair_id'],task=value['task'],source=source_locator(value),
                        source_sha256=value['source_sha256'],grade_database=str(Path(grades_database).resolve()),
                        base_result_ref=dict(database=str(Path(base_database).resolve()),table='pairs',
                            pair_id=value['pair_id'],result_sha256=row[4],code_sha256=row[2],config_sha256=row[3]))
            if progress:progress(done,total,counts)
            if limit and counts['queued']>=limit:break
    finally:
        if routing is not None:routing.close()
        db.close()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=DATA_ROOT/'ast/run/mech/labels.sqlite3')
    ap.add_argument('--grades',type=Path,default=DATA_ROOT/'ast/run/mech/settled.sqlite3')
    ap.add_argument('--limit',type=int,default=0)
    a=ap.parse_args()
    if a.limit<0:ap.error('limit must be nonnegative')
    start=time.monotonic();last=0
    def progress(done,total,counts):
        nonlocal last
        elapsed=time.monotonic()-start
        if elapsed-last>=5 or done==total:
            rate=done/max(elapsed,.001)
            print(f'done={done}/{total} elapsed={elapsed:.1f}s rate={rate:.2f}/s ETA={(total-done)/rate:.1f}s '
                  f'counts={dict(counts)}',file=sys.stderr,flush=True);last=elapsed
    count=sum(1 for _ in jobs(a.base,a.grades,progress=progress,limit=a.limit))
    print(f'eligible={count} elapsed={time.monotonic()-start:.1f}s evaluations=0 writes=0',flush=True)


if __name__=='__main__':main()
