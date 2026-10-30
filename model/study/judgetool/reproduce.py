#!/usr/bin/env python3
"""Requested real calibration replay, not a synthetic test suite."""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse
import collections
import json
from pathlib import Path
import sys
import time
sys.dont_write_bytecode = True
from evaluator import ReplayEvaluator, HERE, P, S, read_json, canonical
from judge3.framed_jsonl import JsonlWriter, iter_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, default=P)
    parser.add_argument('--records', type=Path, default=DATA_ROOT / 'judge3/calibration2-v2/records')
    parser.add_argument('--out', type=Path, default=DATA_ROOT / 'judgetool/reproduction')
    parser.add_argument('--deadline', type=float, default=30)
    args = parser.parse_args()
    output = args.out.resolve()
    if not output.is_relative_to(DATA_ROOT / 'judgetool'):
        parser.error('output must stay under judgetool')
    output.mkdir(exist_ok=True)
    evaluator = ReplayEvaluator(deadline=args.deadline, artifacts=output/'artifacts', reference=args.reference)
    start = time.monotonic()
    summaries = {}
    for name in ('engine-final', 'engine-neg'):
        expected = list(iter_json(args.reference/(name+'.jsonl')))
        counts = collections.Counter(); differences = []
        destination=output/(name+'.jsonl.zst')
        if not destination.exists() and any((output/(name+suffix)).exists()
                for suffix in ('.jsonl','.jsonl.gz')):
            parser.error('existing reproduction JSONL must be converted by the coordinator before restart')
        with JsonlWriter(destination) as out:
            committed=out.committed_lines
            if committed>len(expected):raise ValueError('reproduction has more committed rows than reference')
            saved=iter(iter_json(destination))
            for done, old in enumerate(expected, 1):
                pid = old['pair_id']
                if done<=committed:
                    row=next(saved)
                    if row['pair_id']!=pid:raise ValueError('committed reproduction pair differs from reference')
                    result=row
                else:
                    record = read_json(args.records/(pid+'.json.gz'))
                    tables = read_json(args.reference/'calib2'/pid/'tables.json')
                    print(f'{name} start {done}/{len(expected)} {pid[:8]}', file=sys.stderr, flush=True)
                    # Historical baseline includes DET only to reproduce the requested
                    # historical totals. Routine tool/mechanical use excludes them.
                    result = evaluator.historical(record, old['recovery'], tables, allow_det=True)
                    row = dict(pair_id=pid, task=record['task'], **result)
                    out.write_line((canonical(row)+'\n').encode('utf-8')); out.flush()
                counts[result['engine']] += 1
                counts['verified'] += bool(result.get('verified'))
                if (result['engine'], bool(result.get('verified'))) != (old['engine'], bool(old.get('verified'))):
                    differences.append(dict(pair_id=pid, expected=[old['engine'],bool(old.get('verified'))],
                                            actual=[result['engine'],bool(result.get('verified'))]))
                elapsed = time.monotonic()-start
                print(f'{name} {done}/{len(expected)} elapsed={elapsed:.1f}s '
                      f'rate={done/max(elapsed,.001):.2f}/s {pid[:8]} '
                      f'{result["engine"]} verified={result.get("verified")} {result["seconds"]}s',
                      file=sys.stderr, flush=True)
        summaries[name] = dict(total=len(expected), counts=dict(counts), differences=differences)
        (output/'summary.json').write_text(json.dumps(dict(settings=evaluator.receipt,
            runs=summaries, elapsed=time.monotonic()-start), indent=2)+'\n')
    evaluator.close()
    print(json.dumps(summaries, indent=2), flush=True)


if __name__ == '__main__':
    main()
