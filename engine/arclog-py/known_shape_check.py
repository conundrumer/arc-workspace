"""Checks the binding's ShapeVector against known values: known_check.py KNOWN.jsonl MUTANTS.json.zst [--repo DIR]

KNOWN.jsonl holds, for one table of a task's solver, each shape's text with the expected greatest least, mean and most over the train examples
(`known_values.py`). MUTANTS.json.zst is the task's file of the feature corpus (`all-merged/<set>/mutants/<task>.json.zst`), whose field `gold` is the
standalone gold program. The program is decoded on a closed-world session of the task, `step_tables` is called at each model step, and the
`ShapeVector` of each distinct table (by TableHash) is compared with the expected values of assignment 0 in `values[:, 0:3]`, in the full vector and
with `only=` the known shapes. A table's row is not named by the spelling of its relation, so the table that holds the known shapes is the one with
the most equal values. Prints counts only: equal, differ, missing and stopped, for the full vector and for the list.
Run it with the runtime python of the engine, which has its `arclog` module and `zstandard`.
"""
import argparse
import json
import os

import numpy as np
import zstandard

import arclog


def same_as(vector, want):
    """The per-shape equality of `values[:, 0:3]` of a list vector with `want`, and whether each shape is present."""
    values = np.frombuffer(vector.values, np.float64).reshape(-1, 6)[:, :3]
    present = np.frombuffer(vector.present, np.uint8) == 1
    return np.isclose(values, want, rtol=1e-9, atol=0, equal_nan=True).all(axis=1) & present, present


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('known')
    ap.add_argument('mutants')
    ap.add_argument('--repo', default=os.environ.get('ARC_ROOT', '/Users/davidlu/code/arc-workspace'))
    a = ap.parse_args()
    known = json.loads(open(a.known).readline())
    task = known['task']
    texts = list(known['shapes'])
    want = np.array([known['shapes'][t] for t in texts], np.float64)
    hashes = [arclog.shape_hash(t) for t in texts]
    selection = arclog.ShapeSelection(hashes)
    gold = json.load(zstandard.ZstdDecompressor().stream_reader(open(a.mutants, 'rb')))['gold']
    text = open(os.path.join(a.repo, 'data', 'tasks', task + '.json')).read()
    sess = arclog.Session(arclog.Task.from_json(text, arclog.World.Closed), arclog.DecodeSettings(table_work_cap=1 << 20))
    ids, model, _ = arclog.StudyProgram.from_sexp(gold, sess.settings).decode_stream()
    dec = sess.decoder()
    before, seen, best, stepped = None, set(), None, 0
    try:
        for token, written in zip(ids, model):
            if not written:
                continue
            dec.step(token)
            before = arclog.step_tables(dec, task, 'solver', False, before, True, False)
            stepped += 1
            column = bytes(memoryview(before.tables['hash']))
            for row in range(len(before.tables['form'])):
                shapes = before.shapes(row)
                key = column[row * 16:(row + 1) * 16]
                if shapes is None or key in seen:
                    continue
                seen.add(key)
                # The list walk first: it covers the known shapes alone, and picks the table that holds them.
                same, present = same_as(shapes.vector(only=selection), want)
                if best is None or same.sum() > best[0]:
                    best = (int(same.sum()), int(present.sum()), row, stepped, shapes)
    except Exception as error:  # the closing forms end the stepping
        print('stepping ended:', type(error).__name__)
    if best is None:
        print('no table with shapes')
        return
    equal, held, row, step, shapes = best
    print(f'tables checked {len(seen)}, best table at step {step} row {row}')
    print(f'list: equal {equal}, differ {held - equal}, missing {len(hashes) - held}')
    full = shapes.vector()
    at = dict(zip(np.frombuffer(full.hashes, np.uint64).tolist(), range(full.count)))
    values = np.frombuffer(full.values, np.float64).reshape(-1, 6)
    have = [at.get(h) for h in hashes]
    got = np.array([values[i, :3] if i is not None else [np.nan] * 3 for i in have])
    same = np.isclose(got, want, rtol=1e-9, atol=0, equal_nan=True).all(axis=1) & np.array([i is not None for i in have])
    missing = sum(i is None for i in have)
    print(f'full vector: equal {int(same.sum())}, differ {len(have) - missing - int(same.sum())}, missing {missing}, stopped {full.stopped}, shapes {full.count}')
    print('counts', arclog.table_shape_counts())


if __name__ == '__main__':
    main()
