"""What the tests of work/feature-spec/evaluation-protocol.md share: the tasks, the
encoder's values on grids, and the statistics over claims."""
import ast
import json
import os
import random
import subprocess
import sys
from pathlib import Path

import numpy as np
import zstandard

ROOT = Path(os.environ.get('ARC_MAIN', '/Users/davidlu/code/arc-workspace'))
SPEC = ROOT / 'work/feature-spec'
RESULTS = SPEC / 'results'
NO_VALUE = '-'


def eval_tasks(first=60):
    return (SPEC / 'eval-tasks.txt').read_text().split()[:first]


def task_json(task):
    return json.load(open(ROOT / f'data/tasks/{task}.json'))


def corpus_records(task):
    path = ROOT / f'model/contracts/corpus/{task}.jsonl.zst'
    with open(path, 'rb') as raw:
        import io
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


def grids_values(grids_path, out_path, encoder, rule, size, log=None, work_cap=1 << 20, cpus=1):
    """Runs the encoder on a file of grids; a restart skips the roots the file holds."""
    command = [str(ROOT / 'scripts/run_heavy.py'), '--cpus', str(cpus), '--need', 'soon', str(encoder), 'grid-values', str(grids_path),
               '--rule' if rule else '--scene', '--size', str(size), '--work-cap', str(work_cap), '--out', str(out_path)]
    with open(log or os.devnull, 'a') as stderr:
        subprocess.run(command, check=True, stderr=stderr, stdout=stderr)


def read_values(path, max_size):
    """The roots of a values file up to `max_size`: their names, their sizes, and a matrix
    with a row per root and a column per grid, of int64 digests, with 0 for no value."""
    names, sizes, rows = [], [], []
    with open(path) as lines:
        for line in lines:
            parts = line.rstrip('\n').split('\t')
            if len(parts) != 3:
                continue
            size = int(parts[1])
            if size > max_size:
                continue
            names.append(parts[0])
            sizes.append(size)
            rows.append([0 if v == NO_VALUE else int(v, 16) >> 1 | 1 for v in parts[2].split(' ')])
    matrix = np.array(rows, dtype=np.int64) if rows else np.zeros((0, 0), dtype=np.int64)
    return names, np.array(sizes, dtype=np.int32), matrix


def claims_of(matrix, others):
    """The roots with one value at every grid of `others`: a mask, and each claim's value."""
    if len(others) == 0 or matrix.shape[0] == 0:
        return np.zeros(matrix.shape[0], dtype=bool), np.zeros(matrix.shape[0], dtype=np.int64)
    first = matrix[:, others[0]]
    same = np.all(matrix[:, others] == first[:, None], axis=1)
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


def write_json_atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value))
    temporary.replace(path)


def flush_print(*args):
    print(*args, flush=True)
    sys.stdout.flush()
