#!/usr/bin/env python3
"""Stream explicitly migrated calibration clauses through the ONE evaluator."""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time
from evaluator import ReplayEvaluator,HERE,read_json,canonical
from judge_tool import load_pair
from judge3.framed_jsonl import JsonlWriter, iter_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--selection',required=True);p.add_argument('--labels',required=True)
    p.add_argument('--pairs',required=True);p.add_argument('--candidates',required=True)
    p.add_argument('--out',required=True);p.add_argument('--deadline',type=float,default=30)
    a=p.parse_args();out=Path(a.out).resolve()
    if not out.is_relative_to(DATA_ROOT / 'judgetool'):p.error('output must stay in judgetool')
    if not out.name.endswith('.jsonl.zst'):p.error('--out must end in .jsonl.zst; convert old output before resuming')
    if not out.exists() and any(Path(str(out)[:-4]+suffix).exists() for suffix in ('','.gz')):
        p.error('existing calibration JSONL must be converted by the coordinator before restart')
    selected=read_json(a.selection);candidates=read_json(a.candidates)
    counts=Counter();started=time.monotonic();ev=ReplayEvaluator(deadline=a.deadline)
    try:
        with JsonlWriter(out) as stream:
            committed=stream.committed_lines
            if committed>len(selected):raise ValueError('calibration has more committed rows than selection')
            saved=iter(iter_json(out))
            for i,item in enumerate(selected,1):
                pid=item['pair_id'];print(f'start {i}/{len(selected)} {pid[:8]}',file=sys.stderr,flush=True)
                if i<=committed:
                    row=next(saved)
                    if row['pair_id']!=pid:raise ValueError('committed calibration pair differs from selection')
                    counts[row['outcome']]+=1
                    continue
                row=dict(pair_id=pid,legacy_clause=read_json(Path(a.labels)/(pid+'.json')).get('recovery'))
                try:
                    candidate=candidates.get(pid)
                    if candidate is None:row.update(outcome='unknown',reason='explicit source-name/projected-input candidate required')
                    else:
                        manifest,record,target=load_pair(Path(a.pairs)/pid)
                        row.update(candidate=candidate,result=ev.evaluate(record,candidate['clause'],dict(target,mode=candidate.get('kind','recovery')),candidate.get('columns')))
                        row['outcome']=row['result']['outcome']
                except (ValueError,OSError,KeyError,TypeError) as error:row.update(outcome='unknown',reason=str(error))
                stream.write_line((canonical(row)+'\n').encode('utf-8'));stream.flush();counts[row['outcome']]+=1
                elapsed=time.monotonic()-started
                print(f'{i}/{len(selected)} elapsed={elapsed:.1f}s rate={i/max(elapsed,.001):.2f}/s {row["outcome"]}',file=sys.stderr,flush=True)
    finally:ev.close()
    print(json.dumps(dict(counts)),flush=True)

if __name__=='__main__':main()
