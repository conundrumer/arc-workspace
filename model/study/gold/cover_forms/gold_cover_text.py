"""Writes current-text.json: each stem's concept case and its forms in gen-v3 as it stands, one write per 100 stems. A restart keeps the stems it holds, unless stems are named.

  <runtime python> gold_cover_text.py [STEM...]
"""
import hashlib, json, os, sys
from pathlib import Path
import numpy as np
import arclog
ROOT = Path('/Users/davidlu/code/arc-workspace')
GEN = str(ROOT / 'work/lm/data-study/gold/gen-v3-11f6a212c/corpus/gen')
OUT = 'current-text.json'


def concept(t):
    """The case name and forms of the stem's concept case."""
    sess = arclog.Session(arclog.Task.from_json((ROOT / 'data/tasks' / f'{t}.json').read_text(), arclog.World.Closed))
    s = next(x for x in arclog.corpus_streams(GEN, all_cases=True, task_ids=[t])[0] if x.concept)
    ids = np.frombuffer(s.ids, np.uint32).tolist()
    model = [int(m) for m in np.frombuffer(s.model, np.uint8).astype(bool).tolist()]
    return dict(case=s.case, lines=[x for x in arclog.StudyProgram.from_stream(sess, ids, model).sexp().splitlines() if x.strip()])


def save(got):
    with open(OUT + '.new', 'w') as f:
        json.dump(got, f)
    os.replace(OUT + '.new', OUT)


if __name__ == '__main__':
    got = json.load(open(OUT)) if os.path.exists(OUT) else {}
    named = sys.argv[1:]
    stems = named or [t for t in sorted(json.load(open('lines.json'))) if t not in got]
    for k, t in enumerate(stems):
        try:
            got[t] = concept(t)
        except Exception as e:  # noqa: BLE001
            got[t] = dict(error=repr(e)[:200])
            print(t, got[t], flush=True)
        if k % 100 == 99:
            save(got)
            print(k + 1, flush=True)
    save(got)
    print(len(got), 'stems', sum('error' in v for v in got.values()), 'errors', flush=True)
