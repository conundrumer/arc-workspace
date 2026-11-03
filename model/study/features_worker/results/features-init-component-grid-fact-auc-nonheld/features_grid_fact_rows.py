#!/usr/bin/env python3
"""Stream one row per task: the grid observables, their cost, and the INIT components of the task's gold program.

Each row lands in the rows file as soon as it exists. A rerun skips the tasks that already have a row.
An observable reads train inputs, train outputs and test inputs. `load` drops the test outputs, and an observable
receives only what `load` returns. The gold program is read apart from the grids, for the label columns only.

Usage: <python> features_grid_fact_rows.py [--seconds N] [--limit N]
"""
import argparse
import hashlib
import json
import math
import pathlib
import re
import sys
import time

import numpy as np
from scipy import ndimage

ROOT = pathlib.Path('/Users/davidlu/code/arc-workspace')
TASKS = ROOT / 'data/tasks'
GOLD = ROOT / 'work/lm/data-study/gold/gen-v3-11f6a212c/corpus/gen'
EVAL = ROOT / 'work/lm/data-study/features-worker/arm/eval-tasks.txt'
HERE = pathlib.Path('/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-init-component-grid-fact-auc-nonheld')  # the data folder
ROWS = HERE / 'grid-fact-rows-nonheld1044.jsonl'
PARTIAL = HERE / 'partial.md'
READ_MARK = '<!-- read -->'


def eval_tasks():
    return {line.strip() for line in EVAL.read_text().splitlines() if line.strip()}


def task_ids():
    """The tasks with a gold program, without the 99, in the order of their hash."""
    gold = {p.stem for p in GOLD.glob('*.arclog')}
    held = eval_tasks()
    ids = gold - held
    assert not ids & held
    return sorted(ids, key=digest)


def digest(task):
    return hashlib.sha256(task.encode()).hexdigest()


def half(task):
    """0 is the pick half, 1 is the read half. The sort key is the whole digest and the half is its last hex digit."""
    return int(digest(task)[-1], 16) % 2


def load(task):
    """The grids that the search has. The test outputs stay out of the return value."""
    d = json.loads((TASKS / f'{task}.json').read_text())
    return {'train': [(p['input'], p['output']) for p in d['train']], 'test': [p['input'] for p in d['test']]}


def gold_components(task):
    """The component of each INIT form, as a count per component."""
    text, out, in_str, i = (GOLD / f'{task}.arclog').read_text(), [], False, 0
    while i < len(text):  # comments and string contents go out, so a word in either cannot count as a form
        ch = text[i]
        if in_str:
            if ch == '\\':
                i += 1
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == ';':
            while i < len(text) and text[i] != '\n':
                i += 1
            continue
        else:
            out.append(ch)
        i += 1
    code = ''.join(out)
    names = re.findall(r'\(\s*INIT\s+&\S+\s+([A-Z]\w*)', code)
    assert len(names) == len(re.findall(r'\(\s*INIT\b', code)), task
    counts = {}
    for n in names:
        counts[n] = counts.get(n, 0) + 1
    return counts


class Task:
    """The grids of one task. `memo` holds what the facts share, and the timing loop clears it for each observable."""

    def __init__(self, raw):
        self.raw = raw
        self.memo = {}

    def cached(self, key, fn):
        if key not in self.memo:
            self.memo[key] = fn()
        return self.memo[key]

    def pairs(self):
        return self.cached('pairs', lambda: [(np.array(a, dtype=np.uint8), np.array(b, dtype=np.uint8)) for a, b in self.raw['train']])

    def inputs(self):
        return self.cached('inputs', lambda: [a for a, _ in self.pairs()] + [np.array(g, dtype=np.uint8) for g in self.raw['test']])

    def outputs(self):
        return [b for _, b in self.pairs()]

    def same_shape_pairs(self):
        return [(a, b) for a, b in self.pairs() if a.shape == b.shape]

    def bg(self, g):
        return self.cached(('bg', id(g)), lambda: int(np.bincount(g.ravel(), minlength=10).argmax()))

    def objects(self, g):
        return self.cached(('objects', id(g)), lambda: _objects(g, self.bg(g)))

    def blobs(self, g):
        return self.cached(('blobs', id(g)), lambda: _blobs(g, self.bg(g)))

    def enclosed(self, g):
        return self.cached(('enclosed', id(g)), lambda: _enclosed(g, self.bg(g)))


S8 = np.ones((3, 3), dtype=int)


def _objects(g, bg):
    """8-connected same-colour regions of non-background cells: (cells, top, left, height, width, shape key, mask)."""
    out = []
    for col in np.unique(g):
        if col == bg:
            continue
        lab, _ = ndimage.label(g == col, structure=S8)
        for i, sl in enumerate(ndimage.find_objects(lab), 1):
            m = lab[sl] == i
            out.append((int(m.sum()), sl[0].start, sl[1].start, m.shape[0], m.shape[1], (m.shape, m.tobytes()), m))
    return out


def _blobs(g, bg):
    """The count of colours of each 8-connected region of non-background cells, of any colours."""
    lab, n = ndimage.label(g != bg, structure=S8)
    return [len(np.unique(g[lab == i])) for i in range(1, n + 1)]


def _enclosed(g, bg):
    """The cell count of each enclosure, and the count of background cells of the grid."""
    mask = g == bg
    lab, n = ndimage.label(mask)
    edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    sizes = np.bincount(lab.ravel(), minlength=n + 1)
    return [int(sizes[i]) for i in range(1, n + 1) if i not in edge], int(mask.sum())


def mean(xs):
    xs = list(xs)
    return sum(xs) / len(xs) if xs else 0.0


def share(xs):
    return mean(1.0 if x else 0.0 for x in xs)


def is_mirror(g):
    return np.array_equal(g, g[:, ::-1]) or np.array_equal(g, g[::-1])


def has_period(g):
    """Some shift of at most half the height or width maps the grid onto itself."""
    h, w = g.shape
    return any(np.array_equal(g[p:], g[:-p]) for p in range(1, h // 2 + 1)) or any(np.array_equal(g[:, q:], g[:, :-q]) for q in range(1, w // 2 + 1))


def in_output_as_crop(a, b):
    if b.shape[0] > a.shape[0] or b.shape[1] > a.shape[1]:
        return False
    return bool((np.lib.stride_tricks.sliding_window_view(a, b.shape) == b).all(axis=(2, 3)).any())


def full_lines(t, g):
    bg = t.bg(g)
    return int(((g == g[:, [0]]).all(axis=1) & (g[:, 0] != bg)).sum() + ((g == g[[0], :]).all(axis=0) & (g[0, :] != bg)).sum())


def monotone(sizes):
    d = [b - a for a, b in zip(sizes, sizes[1:])]
    return any(d) and (all(x >= 0 for x in d) or all(x <= 0 for x in d))


def changed_only_bg(t, a, b):
    ch = a != b
    return not ch.any() or bool((a[ch] == t.bg(a)).all())


def same_mask(t, a, b):
    return bool(((a != t.bg(a)) == (b != t.bg(b))).all())


def object_share(t, test):
    """The mean over input grids of the share of a grid's objects that pass `test`. A grid with no object gives 0."""
    return mean(mean(1.0 if test(o) else 0.0 for o in t.objects(g)) for g in t.inputs())


def mean_or_sentinel(t, fn):
    """The mean of `fn` over same-shape train pairs, or -1 where the task has none."""
    ps = t.same_shape_pairs()
    return mean(fn(a, b) for a, b in ps) if ps else -1.0


def in_diagonal(o):
    n, _, _, h, w, _, m = o
    return n >= 3 and h == w == n and (np.array_equal(m, np.eye(n, dtype=bool)) or np.array_equal(m[::-1], np.eye(n, dtype=bool)))


DEFS = {}  # name -> (function, one-line definition)


def fact(name, definition):
    def reg(fn):
        DEFS[name] = (fn, definition)
        return fn
    return reg


# I is train inputs and test inputs; T is train pairs; O is train outputs. Background is a grid's most common colour.
@fact('in_cells', 'mean cell count of I')
def f(t): return mean(g.size for g in t.inputs())
@fact('in_shape_varies', '1 where I holds over one shape')
def f(t): return float(len({g.shape for g in t.inputs()}) > 1)
@fact('same_shape', 'share of T with the output shape equal to the input shape')
def f(t): return share(a.shape == b.shape for a, b in t.pairs())
@fact('area_log_ratio', 'mean over T of log2(output cells / input cells)')
def f(t): return mean(math.log2(b.size / a.size) for a, b in t.pairs())
@fact('upscale', 'share of T where output height and width are integer multiples of the input, not both 1x')
def f(t): return share(a.shape != b.shape and b.shape[0] % a.shape[0] == 0 and b.shape[1] % a.shape[1] == 0 for a, b in t.pairs())
@fact('downscale', 'share of T where input height and width are integer multiples of the output, not both 1x')
def f(t): return share(a.shape != b.shape and a.shape[0] % b.shape[0] == 0 and a.shape[1] % b.shape[1] == 0 for a, b in t.pairs())
@fact('out_shape_const', '1 where all of O has one shape')
def f(t): return float(len({b.shape for b in t.outputs()}) == 1)
@fact('out_is_crop', 'share of T whose output is a contiguous subgrid of its input')
def f(t): return share(in_output_as_crop(a, b) for a, b in t.pairs())
@fact('in_colors', 'mean count of colours per grid of I')
def f(t): return mean(len(np.unique(g)) for g in t.inputs())
@fact('out_colors', 'mean count of colours per grid of O')
def f(t): return mean(len(np.unique(g)) for g in t.outputs())
@fact('new_colors', 'mean over T of the count of output colours absent from its input')
def f(t): return mean(len(set(np.unique(b).tolist()) - set(np.unique(a).tolist())) for a, b in t.pairs())
@fact('lost_colors', 'mean over T of the count of input colours absent from its output')
def f(t): return mean(len(set(np.unique(a).tolist()) - set(np.unique(b).tolist())) for a, b in t.pairs())
@fact('bg_zero', 'share of I whose background is colour 0')
def f(t): return share(t.bg(g) == 0 for g in t.inputs())
@fact('bg_share', 'mean over I of the share of cells that are background')
def f(t): return mean(float((g == t.bg(g)).mean()) for g in t.inputs())
@fact('changed_share', 'mean over same-shape T of the share of cells that change; -1 with no same-shape pair')
def f(t): return mean_or_sentinel(t, lambda a, b: float((a != b).mean()))
@fact('add_only', 'share of same-shape T where each changed cell was background in the input; -1 with no same-shape pair')
def f(t): return mean_or_sentinel(t, lambda a, b: float(changed_only_bg(t, a, b)))
@fact('changed_colors', 'mean over same-shape T of the count of output colours on changed cells; -1 with no same-shape pair')
def f(t): return mean_or_sentinel(t, lambda a, b: float(len(np.unique(b[a != b]))))
@fact('recolor_only', 'share of same-shape T where the non-background cells are the same cells in input and output; -1 with no same-shape pair')
def f(t): return mean_or_sentinel(t, lambda a, b: float(same_mask(t, a, b)))
@fact('has_components', 'director-named. Share of I with at least 2 objects. An object (connected component) is an 8-connected same-colour region of non-background cells')
def f(t): return share(len(t.objects(g)) >= 2 for g in t.inputs())
@fact('n_objects', 'mean object count per grid of I')
def f(t): return mean(len(t.objects(g)) for g in t.inputs())
@fact('object_size', 'mean over I of the mean cell count of a grid\'s objects')
def f(t): return mean(mean(o[0] for o in t.objects(g)) for g in t.inputs())
@fact('singleton_share', 'mean over I of the share of objects with one cell')
def f(t): return object_share(t, lambda o: o[0] == 1)
@fact('rect_share', 'mean over I of the share of objects of over one cell that fill their bounding box')
def f(t): return object_share(t, lambda o: o[0] > 1 and o[0] == o[3] * o[4])
@fact('multicolor_share', 'mean over I of the share of 8-connected non-background regions, of any colours, with over one colour')
def f(t): return mean(mean(1.0 if n > 1 else 0.0 for n in t.blobs(g)) for g in t.inputs())
@fact('repeated_shape', 'share of I where two objects have the same shape up to translation')
def f(t): return share(len({o[5] for o in t.objects(g)}) < len(t.objects(g)) for g in t.inputs())
@fact('distinct_shapes', 'mean over I of the count of object shapes up to translation')
def f(t): return mean(len({o[5] for o in t.objects(g)}) for g in t.inputs())
@fact('object_delta', 'mean over T of output object count minus input object count')
def f(t): return mean(len(t.objects(b)) - len(t.objects(a)) for a, b in t.pairs())
@fact('line_share', 'mean over I of the share of objects that are straight horizontal or vertical lines of at least 3 cells')
def f(t): return object_share(t, lambda o: o[0] >= 3 and min(o[3], o[4]) == 1)
@fact('diagonal_share', 'mean over I of the share of objects that are straight diagonal lines of at least 3 cells')
def f(t): return object_share(t, in_diagonal)
@fact('has_enclosure', 'director-named. Share of I with an enclosure. An enclosure is a 4-connected background region that does not touch the grid edge')
def f(t): return share(t.enclosed(g)[0] for g in t.inputs())
@fact('n_enclosures', 'mean enclosure count per grid of I')
def f(t): return mean(len(t.enclosed(g)[0]) for g in t.inputs())
@fact('enclosed_share', 'mean over I of the share of background cells inside enclosures')
def f(t): return mean(sum(t.enclosed(g)[0]) / t.enclosed(g)[1] for g in t.inputs())
@fact('has_order', 'director-named. Share of I with at least 2 objects, all of different cell counts, so object size gives a strict order')
def f(t): return share(len(t.objects(g)) >= 2 and len({o[0] for o in t.objects(g)}) == len(t.objects(g)) for g in t.inputs())
@fact('monotone_sizes', 'share of I with at least 3 objects whose cell counts rise or fall, not all equal, when sorted by top row or by left column')
def f(t):
    def yes(os):
        return len(os) >= 3 and (monotone([o[0] for o in sorted(os, key=lambda o: (o[1], o[2]))]) or monotone([o[0] for o in sorted(os, key=lambda o: (o[2], o[1]))]))
    return share(yes(t.objects(g)) for g in t.inputs())
@fact('divider_lines', 'mean over I of the count of whole rows and columns of one non-background colour')
def f(t): return mean(full_lines(t, g) for g in t.inputs())
@fact('symmetric_in', 'share of I equal to their left-right or up-down mirror image')
def f(t): return share(is_mirror(g) for g in t.inputs())
@fact('periodic_in', 'share of I that a shift of at most half the height or width maps onto itself')
def f(t): return share(has_period(g) for g in t.inputs())
@fact('symmetric_out', 'share of O equal to their left-right or up-down mirror image')
def f(t): return share(is_mirror(g) for g in t.outputs())
@fact('periodic_out', 'share of O that a shift of at most half the height or width maps onto itself')
def f(t): return share(has_period(g) for g in t.outputs())

NAMES = list(DEFS)
assert len(NAMES) < 40


def row(task):
    t0 = time.perf_counter_ns()
    raw = load(task)
    json_ms = (time.perf_counter_ns() - t0) / 1e6
    obs, ms = {}, {}
    t = Task(raw)
    for name in NAMES:
        t.memo.clear()  # each observable pays for what it shares with the others, as if it ran alone
        a = time.perf_counter_ns()
        v = DEFS[name][0](t)
        ms[name] = round((time.perf_counter_ns() - a) / 1e6, 4)
        obs[name] = round(float(v), 6)
    return {'task': task, 'half': half(task), 'components': gold_components(task), 'obs': obs, 'ms': ms, 'json_ms': round(json_ms, 4)}


def finished():
    """Task ids with a whole row. A torn last line goes out of the file, so an append starts on a new line."""
    if not ROWS.exists():
        return set()
    data = ROWS.read_bytes()
    if data and not data.endswith(b'\n'):
        data = data[:data.rfind(b'\n') + 1]
        ROWS.write_bytes(data)
    return {json.loads(line)['task'] for line in data.splitlines()}


def progress(done, total, rate, eta):
    head = f'# Partial: grid facts and INIT components\n\nRows {done} of {total}. Rate {rate:.1f} tasks/s. ETA {eta:.0f} s.\n'
    tail = ''
    if PARTIAL.exists() and READ_MARK in (old := PARTIAL.read_text()):
        tail = old[old.index(READ_MARK):]
    PARTIAL.write_text(head + '\n' + tail)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--seconds', type=float, default=25, help='stop at a row boundary after this many seconds')
    ap.add_argument('--limit', type=int, default=0, help='stop after this many rows in this run')
    a = ap.parse_args()
    ids = task_ids()
    have = finished()
    todo = [t for t in ids if t not in have]
    print(f'{len(ids)} tasks, {len(have)} with rows, {len(todo)} to do', flush=True)
    start, n = time.time(), 0
    with ROWS.open('a') as out:
        for task in todo:
            out.write(json.dumps(row(task)) + '\n')
            out.flush()
            n += 1
            spent = time.time() - start
            rate = n / spent
            eta = (len(todo) - n) / rate
            if n % 25 == 0 or n == len(todo):
                print(f'{len(have) + n}/{len(ids)} rate {rate:.1f} tasks/s eta {eta:.0f}s', flush=True)
                progress(len(have) + n, len(ids), rate, eta)
            if spent > a.seconds or n == a.limit:
                progress(len(have) + n, len(ids), rate, eta)
                print(f'stopped at {len(have) + n}/{len(ids)} rate {rate:.1f} tasks/s eta {eta:.0f}s', flush=True)
                return
    print('done', flush=True)


if __name__ == '__main__':
    main()
