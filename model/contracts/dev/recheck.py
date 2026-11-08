"""Dev labeling layer: whether each input variant keeps the task's stored values, streamed to out/<task>.stored.jsonl.

    <runtime python> -I -B recheck.py TASK

An input variant is appended as a test input, and a proposer that reads every input can then offer other values. The status of a variant is
`same` where the stored values that solve the train pairs are the task's, `changed` where other stored values solve them, and `unsolved` where
none do. Only a variant of status `same` tests a table. A restart skips the variants already written.
"""
import copy
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'features'))
import engine as E  # noqa: E402

OUT = Path(__file__).parent / 'out'


def status(s, tj, base):
    try:
        tb = s.run_engine(tj)
    except E.AssignmentUnavailable as error:
        return 'error' if error.selection['dropped_assignments'] or error.selection.get('enumeration_stop') else 'unsolved'
    except RuntimeError:
        return 'error'
    best = s.solving_key(tb, tj)
    if best is None:
        return 'unsolved'
    return 'same' if {rel: rows for rel, rows, _ in best} == base else 'changed'


def main(task):
    path = OUT / (task + '.stored.jsonl')
    done = {json.loads(l)['id'] for l in path.open() if l.strip()} if path.exists() else set()
    s = E.Solver(task)
    bj = json.load(open(E.ROOT / 'data/tasks' / (task + '.json')))
    s.tables(bj)
    base = s.stored
    todo = [r for r in map(json.loads, open(OUT / (task + '.variants.jsonl'))) if 'grid' in r and r['id'] not in done]
    t0 = time.time()
    with path.open('a') as fo:
        for n, r in enumerate(todo, 1):
            tj = copy.deepcopy(bj)
            tj['test'] = tj['test'] + [{'input': r['grid'], 'output': [list(x) for x in r['grid']]}]
            fo.write(json.dumps(dict(id=r['id'], stored=status(s, tj, base))) + '\n')
            fo.flush()
            if n % 200 == 0 or n == len(todo):
                el = time.time() - t0
                print('%s %d/%d  %.1f/s  eta %.0fs' % (task, n, len(todo), n / el, (len(todo) - n) * el / n), flush=True)


if __name__ == '__main__':
    main(sys.argv[1])
