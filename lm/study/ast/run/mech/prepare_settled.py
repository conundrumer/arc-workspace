#!/usr/bin/env python3
"""Prepare source-bound pair-directory jobs; no evaluator runs or grade claims."""
import argparse
import json
from pathlib import Path
import sys
import time
from run import canonical


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('render_root',type=Path);ap.add_argument('output',type=Path)
    ap.add_argument('--limit',type=int,default=0);a=ap.parse_args()
    paths=sorted(a.render_root.resolve().glob('*/manifest.json'))
    start=time.monotonic();done=0;written=0
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('w') as stream:
        for path in paths:
            manifest=json.loads(path.read_text());done+=1
            adapter=manifest.get('adapter',{})
            if adapter.get('schema')=='judge3-review-evidence-v3' and adapter.get('source',{}).get('record_path'):
                stream.write(canonical(dict(pair_directory=str(path.parent)))+'\n');written+=1
                stream.flush()
            elapsed=time.monotonic()-start
            print(f'done={done}/{len(paths)} elapsed={elapsed:.1f}s rate={done/max(elapsed,.001):.2f}/s ETA={(len(paths)-done)*elapsed/done:.1f}s prepared={written}',file=sys.stderr,flush=True)
            if a.limit and written>=a.limit:break
    elapsed=time.monotonic()-start
    print(f'prepared={written} done={done}/{len(paths)} elapsed={elapsed:.1f}s rate={done/max(elapsed,.001):.2f}/s ETA=0s',file=sys.stderr,flush=True)


if __name__=='__main__':main()
