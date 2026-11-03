"""The stage cut step of a regold round: cuts the crossing clauses of the round's stems under the bar, and rebuilds the split revision. A clause whose text differs from the one the census read stays unsplit.

  <runtime python> gold_stage_round.py ROUND STEM...
Rows go to round-out/rows-<round>.jsonl. A later row of a stem replaces its earlier row in the view.
"""
import json, os, subprocess, sys
from pathlib import Path
import numpy as np
import arclog
ROOT = Path('/Users/davidlu/code/arc-workspace')
GEN = str(ROOT / 'work/lm/data-study/gold/gen-v3-11f6a212c/corpus/gen')
here = os.path.dirname(os.path.abspath(__file__))
n, stems = sys.argv[1], sys.argv[2:]


def concept_lines(t):
    """The forms of the task's concept case."""
    sess = arclog.Session(arclog.Task.from_json((ROOT / 'data/tasks' / f'{t}.json').read_text(), arclog.World.Closed))
    s = next(x for x in arclog.corpus_streams(GEN, all_cases=True, task_ids=[t])[0] if x.concept)
    ids = np.frombuffer(s.ids, np.uint32).tolist()
    model = [int(m) for m in np.frombuffer(s.model, np.uint8).astype(bool).tolist()]
    return [x for x in arclog.StudyProgram.from_stream(sess, ids, model).sexp().splitlines() if x.strip()]


old_lines, crossing = json.load(open(here + '/lines.json')), json.load(open(here + '/crossing.json'))
os.makedirs(here + '/round-out', exist_ok=True)
lines, cuts = {}, {}
for t in stems:
    lines[t] = concept_lines(t)
    cuts[t] = [c for c in crossing.get(t, []) if c['line'] < min(len(lines[t]), len(old_lines.get(t, []))) and lines[t][c['line']] == old_lines[t][c['line']]]
lp, cp = f'{here}/round-out/lines-{n}.json', f'{here}/round-out/crossing-{n}.json'
json.dump(lines, open(lp, 'w'))
json.dump(cuts, open(cp, 'w'))
with open(f'{here}/round-out/rows-{n}.jsonl', 'a') as out:
    for t in stems:
        if not cuts[t]:
            row = dict(task=t, clauses=0, applied=[], failed=[], lost=len(crossing.get(t, [])))
        else:
            p = subprocess.run([sys.executable, '-u', here + '/gold_helper_one.py', t, lp, cp], capture_output=True, text=True, timeout=900, cwd=here)
            rows = [l for l in p.stdout.splitlines() if l.startswith('{"task"')]
            row = json.loads(rows[-1]) if rows else dict(task=t, error=p.stderr[-300:])
            row['lost'] = len(crossing.get(t, [])) - len(cuts[t])
        out.write(json.dumps(row) + '\n')
        out.flush()
        print({k: v for k, v in row.items() if k != 'program'}, flush=True)
