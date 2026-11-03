"""Walks each gold program for seeds 0 to K-1. No engine.

  tw_walks.py --set corpus|held --seeds K [--limit N]

Appends to R/walks/<set>.jsonl one line per step (the step record of walk.md, with g, the tower facts, the place, shape, pattern and walk_bits)
and one {"rec": "walk", task, seed, steps} line per finished walk. A rerun skips the walks done. Corpus shapes and holds come from
IB/corpus/rows-*.jsonl, held shapes from R/shapes/T.json; a held task without that file waits (run tw_shapes_all.sh, then this again).
"""
import argparse
import json
import os
import sys
import time

import tw_lib as T

L = T.L


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--set', required=True, choices=('corpus', 'held'))
    ap.add_argument('--seeds', type=int, required=True)
    ap.add_argument('--limit', type=int)
    a = ap.parse_args()
    T.setup(engine=False)
    D = T.dago()
    os.makedirs(T.R + '/walks', exist_ok=True)
    out = '%s/walks/%s.jsonl' % (T.R, a.set)
    done = {(x['task'], x['seed']) for x in T.read_lines(out) if x.get('rec') == 'walk'}
    tasks = T.tasks_of('corpus' if a.set == 'corpus' else 'held')
    corpus_rows = T.corpus_shape_rows() if a.set == 'corpus' else None
    todo = [t for t in tasks if any((t, s) not in done for s in range(a.seeds))]
    if a.limit:
        todo = todo[:a.limit]
    print('%s: %d tasks, %d walks done, %d tasks to do' % (a.set, len(tasks), len(done), len(todo)), flush=True)
    fh = open(out, 'a')
    t0, n_steps, waiting, errors = time.time(), 0, [], []
    for c, task in enumerate(todo):
        t1 = time.time()
        rows = corpus_rows.get(task, {}) if a.set == 'corpus' else T.held_shape_rows(task)
        if rows is None:
            waiting.append(task)
            continue
        try:
            forms = T.gold_forms(task)
            dag = D.ProgramDag(forms)
            gof = {T.head_of(f): g for g, f in enumerate(forms)}
            assert len(gof) == len(forms), 'duplicate heads'
            assert all(L.parse(f)['head'] == T.head_of(f) for f in forms), 'head disagree'
            holds = {k: bool(rows[g][2]) if g in rows else False for k, g in gof.items()}
            recs_by_seed = {s: T.annotate(dag, T.walk(forms, s, task=task, dag=dag), holds) for s in range(a.seeds) if (task, s) not in done}
        except Exception as e:  # noqa: BLE001
            errors.append(task)
            print('[%d/%d] %s ERROR %s: %s' % (c + 1, len(todo), task, type(e).__name__, str(e)[:100]), flush=True)
            continue
        st = L.set_of(task)
        for s, recs in recs_by_seed.items():
            lines = []
            for r in recs:
                g = gof[r['key_f']]
                r.update(g=g, set=st, shape=rows[g][1] if g in rows else None)
                lines.append(json.dumps(r, separators=(',', ':')))
            lines.append(json.dumps(dict(rec='walk', task=task, seed=s, steps=len(recs)), separators=(',', ':')))
            fh.write('\n'.join(lines) + '\n')
            n_steps += len(recs)
        fh.flush()
        el = time.time() - t0
        k = c + 1 - len(waiting) - len(errors)
        print('[%d/%d] %s %d forms, %d seeds, %.2f s | %.3f s a task, ETA %.0f s' % (
            c + 1, len(todo), task, len(forms), len(recs_by_seed), time.time() - t1, el / max(k, 1), el / max(k, 1) * (len(todo) - c - 1)), flush=True)
    print('%s: %d steps written, %d s' % (a.set, n_steps, time.time() - t0))
    if waiting:
        print('WAITING for shapes (run tw_shapes_all.sh, then this again): %d tasks, %s ...' % (len(waiting), ' '.join(waiting[:5])))
    if errors:
        print('ERRORS: %s' % ' '.join(errors))
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
