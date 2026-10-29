#!/usr/bin/env python3
"""Pack existing pair-data calls; adapted from judge2/make_batches.py.

No corpus selection, labels, rendering or native evaluation. Outputs DATA_ROOT
only. Each input line is {"pair_dir": <absolute complete dataset directory>}.
"""
import argparse
import json
import os
from pathlib import Path
import sys
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from study_paths import DATA_ROOT


def save(path,state):
    """Original atomic checkpoint boundary from judge2/make_batches.save."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+f'.{os.getpid()}.tmp')
    try:
        with temp.open('w') as f:
            json.dump(state,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:temp.unlink(missing_ok=True)


def data_path(path):
    path=Path(path).resolve()
    if not path.is_relative_to(DATA_ROOT.resolve()):raise ValueError('output/input data must stay under DATA_ROOT: '+str(path))
    return path


def calls(path):
    """Explicit files replace retired rendered-publication/label selection."""
    seen=set()
    with data_path(path).open() as stream:
        for line in stream:
            if not line.strip():continue
            item=json.loads(line)
            if not isinstance(item,dict) or set(item)!={'pair_dir'}:raise ValueError('call needs only pair_dir')
            directory=data_path(item['pair_dir']);index=json.loads((directory/'pair.json').read_text())
            pair=index['pair_id']
            if pair in seen:raise ValueError('duplicate pair in calls: '+pair)
            seen.add(pair)
            yield dict(pair_id=pair,pair_dir=str(directory))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--calls',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--batch-size',type=int,default=3)
    a=p.parse_args()
    if a.batch_size<1:p.error('batch size must be positive')
    root=data_path(a.output);root.mkdir(parents=True,exist_ok=False);group=[];number=0
    def publish():
        nonlocal number
        number+=1;path=root/f'calls-{number:04d}.jsonl'
        path.write_text(''.join(json.dumps(dict(pair_dir=x['pair_dir']))+'\n' for x in group))
        print(json.dumps(dict(path=str(path),pairs=len(group))),flush=True)
    for item in calls(a.calls):
        group.append(item)
        if len(group)==a.batch_size:publish();group=[]
    if group:publish()


if __name__=='__main__':main()
