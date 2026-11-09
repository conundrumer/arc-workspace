#!/usr/bin/env python3
"""Set up the blind reader's two folders for a list of tasks.

The blind reader is a test of whether an ARC task can be solved from features alone. An arclog agent, the tester,
writes arclog queries for a task and sees only the features of the tables those queries make. It never sees a grid, a
table row or the task's id. Each thing the tester must work around points at a feature that is missing.

  uv run python scripts/blind_reader_setup.py --tester DIR --internal DIR [--encoder FILE] [--runtime DIR] TASK_ID...

TASK_ID names a file `TASK_ID.json` under `--tasks` (default `data/tasks`). The tasks get the aliases T1, T2, ... in the
order given. A second run on the same folders replaces the first run's tasks.

The two folders are made if they are missing, and neither is inside the repo or inside the other.

  --tester DIR    What the tester may see. It holds
                    arclog.py          The command the tester runs. It has the interface of `scripts/arclog.py`.
                    setting            The path of the internal folder, and nothing else.
                    T1/program.arclog  A starting program for each alias.
  --internal DIR  What the tester must not see. It holds
                    tasks/T1.json      A copy of the task with an alias in place of its id, with no `source` field and
                                       with a one-cell grid in place of each test output (the engine refuses a test pair
                                       that has no output field).
                    map.json           Each alias and the task id of it.
                    config.json        The repo's path, the encoder and the runtime.
                    feature-encoder    A copy of `--encoder`.
                    run/               The files that a run writes.
  --encoder FILE  The `feature-encoder` binary (see `engine/arclog-encoder`). Build it at the commit that the runtime is
                  built at, with `scripts/engine_build.sh SHA NAME encoder` through `scripts/run_heavy.py`, which puts it in
                  `work/engine-builds/bin/feature-encoder-NAME`. Without this option, a binary already in the internal
                  folder stays in use.
  --runtime DIR   The engine runtime for `scripts/arclog.py --runtime`, as `scripts/build_study_runtime.py` builds one. Build
                  it at the commit of the encoder. The default is the runtime that `scripts/arclog.py` takes without the
                  option.

A task of the ARC-AGI-2 evaluation set is refused. Which task ids to use is the caller's choice, and this script prints
the aliases only, never an id.

To run the test, give the tester the tester folder's path, and see `scripts/blind_reader.py` for the commands.
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# The engine's evaluator reads an `output` of each test pair, to judge a solver with, and refuses a pair that has none.
# A test pair's output is no feature's input, so a one-cell grid stands in for it.
PLACEHOLDER = [[0]]
START = '(RULE &cells (input *P *Col))\n\n(OUT (&cells ^P ^Col))\n'
LAUNCHER = '''#!/usr/bin/env python3
"""The blind reader's command. Run it with --help."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
os.execv(sys.executable, [sys.executable, %r, '--setting', HERE + '/setting', *sys.argv[1:]])
'''


def inside(path, folder):
    return path == folder or folder in path.parents


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--tester', type=Path, required=True)
    ap.add_argument('--internal', type=Path, required=True)
    ap.add_argument('--encoder', type=Path)
    ap.add_argument('--runtime', type=Path)
    ap.add_argument('--tasks', type=Path, default=ROOT / 'data/tasks')
    ap.add_argument('ids', nargs='+', metavar='TASK_ID')
    a = ap.parse_args()
    tester, internal = a.tester.resolve(), a.internal.resolve()
    for folder in (tester, internal):
        if inside(folder, ROOT):
            sys.exit('%s is inside the repo' % folder)
    if inside(tester, internal) or inside(internal, tester):
        sys.exit('the two folders must be apart')
    if len(set(a.ids)) != len(a.ids):
        sys.exit('a task id is given twice')
    tasks = {}
    for i, task in enumerate(a.ids, 1):
        path = a.tasks / (task + '.json')
        if not path.exists():
            sys.exit('no task file %s' % path)
        data = json.loads(path.read_text())
        if any(s.get('dataset') == 'arc-agi-2' and s.get('split') == 'evaluation' for s in data.get('source', [])):
            sys.exit('a task is in the ARC-AGI-2 evaluation set: %s' % task)
        tasks['T%d' % i] = {
            'train': [{'input': p['input'], 'output': p['output']} for p in data['train']],
            'test': [{'input': p['input'], 'output': PLACEHOLDER} for p in data['test']],
        }
    runtime = a.runtime.resolve() if a.runtime else None
    if runtime and not (runtime / 'ready.json').exists():
        sys.exit('no built runtime at %s' % runtime)
    (internal / 'tasks').mkdir(parents=True, exist_ok=True)
    (internal / 'run').mkdir(exist_ok=True)
    tester.mkdir(parents=True, exist_ok=True)
    for old in (internal / 'tasks').glob('*.json'):
        old.unlink()
    shutil.rmtree(internal / 'run')
    (internal / 'run').mkdir()
    for alias, task in tasks.items():
        (internal / 'tasks' / (alias + '.json')).write_text(json.dumps(task))
        (tester / alias).mkdir(exist_ok=True)
        (tester / alias / 'program.arclog').write_text(START)
    (internal / 'map.json').write_text(json.dumps(dict(zip(tasks, a.ids))))
    if a.encoder:
        shutil.copy2(a.encoder, internal / 'feature-encoder')
    if not (internal / 'feature-encoder').exists():
        sys.exit('no encoder: give --encoder')
    (internal / 'config.json').write_text(json.dumps({'repo': str(ROOT), 'encoder': str(internal / 'feature-encoder'), 'runtime': str(runtime) if runtime else None}))
    (tester / 'setting').write_text(str(internal) + '\n')
    (tester / 'arclog.py').write_text(LAUNCHER % str(ROOT / 'scripts/blind_reader.py'))
    print('aliases: ' + ' '.join(tasks))
    print('tester folder: %s' % tester)


main()
