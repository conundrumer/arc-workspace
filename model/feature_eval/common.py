"""What the tests of docs/feature-spec/evaluation-protocol.md share: the tasks, the
encoder's values on grids, and the statistics over claims."""
import ast
import glob
import io
import json
import os
import pickle
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import zstandard

ROOT = Path(os.environ.get('ARC_MAIN', '/Users/davidlu/code/arc-workspace'))
SPEC = ROOT / 'work/feature-spec'
RESULTS = SPEC / 'results'


def data_path(path):
    """The file that stands for a path: the path itself, or the path with `.zst`."""
    path = Path(path)
    if path.exists():
        return path
    packed = Path(str(path) + '.zst')
    return packed if packed.exists() else path


def data_exists(path):
    return data_path(path).exists()


def open_text(path, mode='r'):
    """A text stream over a file, as zstd where its path says so. A reader takes a path with or
    without `.zst`, and reads each frame of a file that runs appended to."""
    if 'r' in mode:
        path = data_path(path)
        if str(path).endswith('.zst'):
            return io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(open(path, 'rb'), read_across_frames=True, closefd=True), encoding='utf-8')
        return open(path, encoding='utf-8')
    if str(path).endswith('.zst'):
        raw = open(path, 'ab' if 'a' in mode else 'wb')
        return io.TextIOWrapper(zstandard.ZstdCompressor(level=3).stream_writer(raw, closefd=True), encoding='utf-8')
    return open(path, mode, encoding='utf-8')


def read_bytes(path):
    path = data_path(path)
    if str(path).endswith('.zst'):
        with zstandard.ZstdDecompressor().stream_reader(open(path, 'rb'), read_across_frames=True, closefd=True) as reader:
            return reader.read()
    return Path(path).read_bytes()


def read_pickle(path):
    """A pickled value from a file that a path stands for, with or without `.zst`."""
    return pickle.loads(read_bytes(path))


def write_pickle(path, value):
    """A pickled value as a zstd stream at the path with `.zst`, which stands only once it is complete."""
    target = Path(str(path) + '.zst')
    temporary = Path(str(target) + '.tmp')
    with temporary.open('wb') as raw, zstandard.ZstdCompressor(level=3).stream_writer(raw) as sink:
        pickle.dump(value, sink, protocol=4)
    temporary.rename(target)


def read_json(path):
    with open_text(path) as lines:
        return json.load(lines)


def glob_data(pattern):
    """The files of a pattern, plain or as zstd, each once."""
    held = {}
    for found in glob.glob(str(pattern) + '.zst') + glob.glob(str(pattern)):
        held.setdefault(found[:-4] if found.endswith('.zst') else found, found)
    return sorted(held.values())

NO_VALUE = '-'


def eval_tasks(first=60):
    return (SPEC / 'eval-tasks.txt').read_text().split()[:first]


def task_json(task):
    return json.load(open(ROOT / f'data/tasks/{task}.json'))


def corpus_records(task):
    path = ROOT / f'model/contracts/corpus/{task}.jsonl.zst'
    with open(path, 'rb') as raw:
        reader = zstandard.ZstdDecompressor().stream_reader(raw)
        return [json.loads(line) for line in io.TextIOWrapper(reader)]


def mutator():
    """`run.mutate` and what it reads, from the source of model/contracts/dev/run.py: that
    module's own imports need the engine's runtime, which the generator does not read."""
    source = (ROOT / 'model/contracts/dev/run.py').read_text()
    tree = ast.parse(source)
    wanted = {'CELL_OPS', 'OBJECT_OPS', 'objects', 'place', 'object_op', 'mutate'}
    kept = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            kept.append(node)
        elif isinstance(node, ast.Assign) and any(getattr(t, 'id', None) in wanted for t in node.targets):
            kept.append(node)
    from collections import Counter
    space = {'Counter': Counter, 'random': random}
    exec(compile(ast.Module(body=kept, type_ignores=[]), 'run.py', 'exec'), space)
    return space['mutate']


def grids_values(grids_path, out_path, encoder, rule, size, log=None, work_cap=1 << 20, cpus=1, native=False):
    """Runs the encoder on a file of grids; a restart skips the roots the file holds. With `native`, the
    roots are the generated shapes over the base tables."""
    command = [str(ROOT / 'scripts/run_heavy.py'), '--cpus', str(cpus), '--need', 'soon', str(encoder), 'grid-vectors' if native else 'grid-values', str(grids_path),
               '--rule' if rule else '--scene', '--size', str(size), '--work-cap', str(work_cap), '--out', str(out_path)]
    with open(log or os.devnull, 'a') as stderr:
        subprocess.run(command, check=True, stderr=stderr, stdout=stderr)


def read_values(path, max_size):
    """The roots of a values file up to `max_size`: their names, their sizes, and a matrix
    with a row per root and a column per grid, of words, with 0 for no value."""
    names, sizes, rows = [], [], []
    with open_text(path) as lines:
        for line in lines:
            parts = line.rstrip('\n').split('\t')
            if len(parts) != 3:
                continue
            size = int(parts[1])
            if size > max_size:
                continue
            names.append(parts[0])
            sizes.append(size)
            rows.append([0 if v == NO_VALUE else int(v, 16) for v in parts[2].split(' ')])
    matrix = np.array(rows, dtype=np.uint64) if rows else np.zeros((0, 0), dtype=np.uint64)
    return names, np.array(sizes, dtype=np.int32), matrix


def claims_of(matrix, others):
    """The roots with one value at every grid of `others`: a mask, and each claim's value."""
    if len(others) == 0 or matrix.shape[0] == 0:
        return np.zeros(matrix.shape[0], dtype=bool), np.zeros(matrix.shape[0], dtype=np.uint64)
    first = matrix[:, others[0]]
    # A generated shape's default has the word 1, and a claim of it is no active claim.
    same = np.all(matrix[:, others] == first[:, None], axis=1) & (first != 1)
    return same, first


def violation(matrix, mask, value, at):
    """The share of the claims in `mask` whose value at the grids `at` differs from it."""
    count = int(mask.sum())
    if count == 0:
        return np.zeros(len(at))
    return (matrix[mask][:, at] != value[mask][:, None]).sum(axis=0) / count


def auc_of(true_v, others):
    """P(V(true) < V(m)) + 0.5 P(V(true) = V(m)) over `others`."""
    if len(others) == 0:
        return None
    return float((np.mean(true_v < others) + 0.5 * np.mean(true_v == others)))


def classes(matrix):
    """The number of classes of roots with an equal value vector."""
    if matrix.shape[0] == 0:
        return 0
    return len(np.unique(matrix, axis=0))


def item_statistics(held, unique, others, true_place, places):
    """What an item's statistics read, by class and by root. `held` has a row per root, `unique`
    a row per class of roots with an equal value vector over the task's instances; `others` are
    the places that the claims come from, `places` the places compared with `true_place`."""
    out = {}
    for tag, matrix in (('', unique), ('_root', held)):
        mask, value = claims_of(matrix, others)
        v_true = float(violation(matrix, mask, value, [true_place])[0]) if len(matrix) else 0.0
        v_other = violation(matrix, mask, value, places) if len(places) else np.zeros(0)
        out['claims' + tag] = int(mask.sum())
        out['v_true' + tag] = v_true
        out['v_other' + tag] = v_other
        out['auc' + tag] = auc_of(v_true, v_other)
    return out


def write_json_atomic(path, value):
    """Writes a whole value as zstd, under the path with `.zst`."""
    path = Path(str(path) if str(path).endswith('.zst') else str(path) + '.zst')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(str(path)[:-4] + '.tmp.zst')
    with open_text(temporary, 'w') as sink:
        sink.write(json.dumps(value))
    temporary.replace(path)


def flush_print(*args):
    print(*args, flush=True)
    sys.stdout.flush()
