"""The held-out split by task: the rule, the guard that every stage of the sample build calls, and the file that records it.

A task is held-out where its data/tasks/<id>.json `source` has arc-agi-2/evaluation (120 tasks). Any other task has u = first 16 hex digits
of sha256("1533:<id>") / 16**16, and is train where u < 0.85, else dev. The stratum of a train or dev task is
`<depth bin>/<size bin>`, and `-` for a held-out task:
- depth bin: `goal_depth` of the task's row in gold-union/graph-tasks-{training,ramp,37}.jsonl (a later file's row replaces an earlier one's):
  d1-4, d5-7, d8+; `none` for a task with no row, an `error` row, or goal_depth inf.
- size bin: `same` where every train pair's output has its input's height and width, else `diff`.
The design is docs/sample-build/split.md; its split_design/split2.tsv is what `--check` compares against.

  python3 split.py            writes OUTD/split.tsv (task, split, stratum)
  python3 split.py --check    exits 1 where OUTD/split.tsv differs from split2.tsv
"""
from pathlib import Path as _StudyPath
import sys as _study_sys
_study_sys.path.insert(0, str(_StudyPath(__file__).resolve().parents[1]))
from study_paths import CODE_ROOT, DATA_ROOT, MAIN_ROOT, REPO_ROOT, data_path
import argparse, functools, hashlib, json, os, sys, tempfile
from collections.abc import Iterable
from pathlib import Path

TASKS = MAIN_ROOT / 'data/tasks'
GRAPHS = DATA_ROOT / 'gold/gold-union'
OUTD = Path(os.environ.get('ARC_SAMPLE_OUT') or DATA_ROOT / 'samples')  # ARC_SAMPLE_OUT: another samples folder, such as one for a rebuild of some tasks
DESIGN = Path(__file__).resolve().parent / 'split_design/split2.tsv'
SALT = 1533
CUT = 0.85
HELD_OUT_SOURCE = {'dataset': 'arc-agi-2', 'split': 'evaluation'}
HELD_OUT = 'held-out'
OLD_HELD_OUT = 'held'  # the name that files written before the rename carry in a split field
type Split = str  # 'train', 'dev' or 'held-out'


@functools.cache
def task_file(task: str) -> dict:
    return json.loads((TASKS / f'{task}.json').read_text())


def u(task: str) -> float:
    return int(hashlib.sha256(f'{SALT}:{task}'.encode()).hexdigest()[:16], 16) / 16 ** 16


def split_of(task: str) -> Split:
    if any(s['dataset'] == HELD_OUT_SOURCE['dataset'] and s['split'] == HELD_OUT_SOURCE['split'] for s in task_file(task)['source']):
        return HELD_OUT
    return 'train' if u(task) < CUT else 'dev'


# The tasks out of scope, which no fit and no score reads: one line per task, {task, set, reason}; the union's gold_union_scope.py writes it.
OUT_OF_SCOPE = Path(os.environ.get('ARC_OUT_OF_SCOPE', str(DATA_ROOT / 'gold/gold-union-exp46/out-of-scope.jsonl')))


@functools.cache
def out_of_scope() -> dict[str, str]:
    """{task: reason} of OUT_OF_SCOPE; a missing file is an error, so that no task enters a fit for want of the file."""
    return {r['task']: r['reason'] for r in map(json.loads, OUT_OF_SCOPE.read_text().splitlines()) if r}


def is_held_out(split: str) -> bool:
    """True for the held-out split under its name and under the name that older files carry. A reader of a split field asks this, so that no held-out task enters a fit by its old name."""
    return split in (HELD_OUT, OLD_HELD_OUT)


def guard(task: str, allowed: Iterable[Split]) -> None:
    """Exits with status 2, before the caller writes, where the task's split is not in `allowed`. A stage that writes for a fit passes ('train', 'dev')."""
    split = split_of(task)
    if split not in set(allowed):
        print(f'task {task} is {split}; the stage may write only for {sorted(set(allowed))}', file=sys.stderr)
        sys.exit(2)


@functools.cache
def goal_depths() -> dict[str, float | None]:
    got: dict[str, float | None] = {}
    for name in ('training', 'ramp', '37'):
        for line in (GRAPHS / f'graph-tasks-{name}.jsonl').read_text().splitlines():
            r = json.loads(line)
            got[r['task']] = None if 'error' in r else r['goal_depth']
    return got


def stratum(task: str) -> str:
    if split_of(task) == HELD_OUT:
        return '-'
    d = goal_depths().get(task)
    depth = 'none' if d is None or d == float('inf') else 'd1-4' if d <= 4 else 'd5-7' if d <= 7 else 'd8+'
    same = all(len(x['input']) == len(x['output']) and len(x['input'][0]) == len(x['output'][0]) for x in task_file(task)['train'])
    return f'{depth}/{"same" if same else "diff"}'


def rows() -> list[tuple[str, Split, str]]:
    return [(p.stem, split_of(p.stem), stratum(p.stem)) for p in sorted(TASKS.glob('*.json'))]


def write() -> None:
    OUTD.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=OUTD, prefix='split.tsv.')
    with os.fdopen(fd, 'w') as f:
        f.write('task\tsplit\tstratum\n')
        for t, sp, st in rows():
            f.write(f'{t}\t{sp}\t{st}\n')
    os.replace(tmp, OUTD / 'split.tsv')


def table(path: Path, cols: tuple[int, int, int]) -> dict[str, tuple[str, str]]:
    lines = [l.split('\t') for l in path.read_text().splitlines()[1:]]
    return {l[cols[0]]: (HELD_OUT if is_held_out(l[cols[1]]) else l[cols[1]], l[cols[2]]) for l in lines}  # a split.tsv written before the rename holds the old name


def check() -> int:
    mine, design = table(OUTD / 'split.tsv', (0, 1, 2)), table(DESIGN, (0, 3, 2))
    bad = sorted(t for t in mine.keys() | design.keys() if mine.get(t) != design.get(t))
    for t in bad:
        print(f'{t}\tsplit.tsv {mine.get(t)}\tsplit2.tsv {design.get(t)}')
    print(f'{len(mine)} tasks in split.tsv, {len(design)} in split2.tsv, {len(bad)} differ')
    return 1 if bad else 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=(__doc__ or '').split('\n')[0])
    ap.add_argument('--check', action='store_true', help='compare OUTD/split.tsv with split2.tsv; exit 1 on a difference')
    sys.exit(check() if ap.parse_args().check else write())
