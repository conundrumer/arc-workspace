#!/usr/bin/env python
"""Rows of leave-one-atom-out, from gold's text, one JSON line per form. A rerun skips finished tasks.

  python features_ofree_rows.py fit     corpus-v3mix, tasks outside the 99 evaluation tasks: rows/fit.jsonl
  python features_ofree_rows.py held    the 37 held tasks at gold-v3-helper-forms-a036da074: rows/held.jsonl
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import features_ofree_text as T  # noqa: E402

ME = os.path.dirname(os.path.abspath(__file__)) + '/'


def main():
    which = sys.argv[1]
    reg = T.Registry()
    ev = set(T.read_tasks(T.EVAL))
    out = ME + 'rows/%s.jsonl' % which
    os.makedirs(ME + 'rows', exist_ok=True)
    if which == 'fit':
        lo = set(T.read_tasks(T.LEAVE_OUT))
        tasks = [t for t in sorted(os.listdir(T.CORPUS)) if t not in ev and t not in lo and os.path.exists(T.CORPUS + t + '/pairs.jsonl.gz')]
        src = T.corpus_lines
    else:
        tasks = T.read_tasks(T.HELD)
        pts = {x['task']: x['gold_sexp'] for x in json.load(open(T.POINTS))}
        src = lambda t: [x for x in pts[t].splitlines() if x.strip()]  # noqa: E731
    done = set()
    if os.path.exists(out):
        for x in open(out):
            done.add(json.loads(x)['task'])
    t0 = time.time()
    n = rows = 0
    todo = [t for t in tasks if t not in done]
    print(len(tasks), 'tasks,', len(done), 'done', flush=True)
    with open(out, 'a') as f:
        for i, t in enumerate(todo, 1):
            for r in T.records(t, src(t), reg):
                f.write(json.dumps(r, separators=(',', ':')) + '\n')
                n += 1
                rows += len(r['rows'])
            f.flush()
            if i % 200 == 0 or i == len(todo):
                r = i / max(time.time() - t0, 1e-6)
                print('%d of %d tasks, %d forms, %d rows, %.0f tasks per s, ETA %.0f s' % (i, len(todo), n, rows, r, (len(todo) - i) / r), flush=True)


if __name__ == '__main__':
    main()
