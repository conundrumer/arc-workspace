"""Dump case texts and faults, one resumable JSON file per generated solver.

Run with the engine runtime's Python and -I -B. Reuse an output directory to
resume; use a fresh directory for each engine build being compared. Each engine
process has a 60-second timeout.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from arclog_convert.readback import read_checked  # noqa: E402  the corpus is a gen/ directory


def dump(task, corpus):
    import arclog

    data = corpus / (task + '.arcdata')
    try:
        cases = arclog.case_files(task, read_checked(corpus / (task + '.arclog')),
                                 read_checked(data) if data.exists() else '', str(corpus))
        return {'task': task, 'cases': [
            {field: getattr(case, field) for field in
             ('case', 'file', 'concept', 'arclog', 'arcdata', 'fault')}
            for case in cases]}
    except Exception as error:
        return {'task': task, 'error': str(error)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--corpus', type=Path, default=ROOT / 'work/arclog/gen')
    parser.add_argument('--task', action='append', help='limit to task id; repeatable')
    parser.add_argument('--worker', help=argparse.SUPPRESS)
    args = parser.parse_args()
    corpus = args.corpus.resolve()
    if args.worker:
        print(json.dumps(dump(args.worker, corpus), ensure_ascii=False, sort_keys=True))
        return
    args.output.mkdir(parents=True, exist_ok=True)
    tasks = sorted(args.task or [p.stem for p in corpus.glob('*.arclog')])
    start = time.monotonic()
    done = 0
    skipped = sum((args.output / (task + '.json')).exists() for task in tasks)
    print(f'{len(tasks)} tasks, {skipped} already finished', flush=True)
    unfinished = 0
    for task in tasks:
        target = args.output / (task + '.json')
        if target.exists():
            continue
        command = ['timeout', '60', sys.executable, '-I', '-B', str(Path(__file__).resolve()),
                   str(args.output), '--corpus', str(corpus), '--worker', task]
        run = subprocess.run(command, capture_output=True, text=True)
        if run.returncode:
            # Leave unfinished tasks available to retry on the next run.
            unfinished += 1
            print(f'{task}: unfinished (exit {run.returncode}): {run.stderr.strip()}', flush=True)
            continue
        result = json.loads(run.stdout)
        temporary = target.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + '\n')
        os.replace(temporary, target)
        done += 1
        cases = result.get('cases', [])
        faults = sum(case['arclog'] is None for case in cases)
        print(f'{task}: {len(cases)} cases, {faults} refused; '
              f'{done / (time.monotonic() - start):.2f} tasks/s', flush=True)
    print(f'{skipped + done}/{len(tasks)} finished, {unfinished} unfinished', flush=True)
    if unfinished:
        sys.exit(1)


if __name__ == '__main__':
    main()
