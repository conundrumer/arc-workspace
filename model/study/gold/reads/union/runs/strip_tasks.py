"""Removes the lines of some tasks from the shard files of a union folder, so that the stages take those tasks again and a merge finds no older line of them.

  .venv/bin/python strip_tasks.py DIR [--kinds union,keys,fits,graph] [--tasks-file FILE] [TASK ...]

The shard files are `union-SET-K`, `union-keys-SET-K`, `fits-SET-K` and `graph-(tasks|tables|prods)-SET-K`, each plain or a zstd stream (study_zst.py names the file by its logical name and rewrites it in the form it has). The default kinds are union, keys and fits; add `graph` to take the graph shard files of a batch again (the graph stage skips a task that a shard of its batch has). FILE holds one task per line.
Each file with a line to remove is written to a `.part` file and renamed over the file, so a folder that holds hard links to another folder's files leaves those files as they were. The removed lines go to DIR/strip-removed.jsonl.zst, one `{"file", "line"}` each. A rerun finds nothing more to remove. Prints each file it changed.

A merge (`gold_union.py merge`, `gold_union_keys.py merge`, `gold_union_fits.py merge`) takes, for each task, the line of the last shard file by name, and the shard names sort as text (`union-train-240` sorts before `union-train-27`), so a task line left in an older shard can win over a new line.
"""
import json, os, re, sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[4]))  # model/study
import study_zst as Z  # noqa: E402

SETS = 'train|dev|held-out'
KINDS = {
    'union': r'union-(%s)-\d+\.jsonl$' % SETS,
    'keys': r'union-keys-(%s)-\d+\.jsonl$' % SETS,
    'fits': r'fits-(%s)-\d+\.jsonl$' % SETS,
    'graph': r'graph-(tasks|tables|prods)-(%s)-\d+\.jsonl$' % SETS,
}
TASK = re.compile(r'\{"(?:task|stem)": "([0-9a-f]{8})"')


def strip(folder, tasks, kinds):
    folder = folder.rstrip('/') + '/'
    pats = [re.compile(KINDS[k]) for k in kinds]
    removed = 0
    log = None
    for path in Z.glob(folder + '*.jsonl'):
        name = os.path.basename(path)
        if not any(p.fullmatch(name) for p in pats):
            continue
        keep, drop = [], []
        with Z.open_text(path) as f:
            for l in f:
                m = TASK.match(l)
                (drop if m and m[1] in tasks and l.endswith('\n') else keep).append(l)
        if not drop:
            continue
        if log is None:
            log = Z.open_text(folder + 'strip-removed.jsonl', 'a', line_buffering=True)
        log.write(''.join(json.dumps(dict(file=name, line=l)) + '\n' for l in drop))
        with Z.rewrite(path) as out:
            out.writelines(keep)
        removed += len(drop)
        print(name, 'removed', len(drop), 'kept', len(keep), flush=True)
    if log is not None:
        log.close()
    print(removed, 'lines removed', flush=True)


if __name__ == '__main__':
    a = sys.argv[1:]
    kinds = ['union', 'keys', 'fits']
    tasks = set()
    folder = a.pop(0)
    while a:
        x = a.pop(0)
        if x == '--kinds':
            kinds = a.pop(0).split(',')
        elif x == '--tasks-file':
            tasks |= {l.split()[0] for l in open(a.pop(0)) if l.strip() and not l.startswith('#')}
        else:
            tasks.add(x)
    strip(folder, tasks, kinds)
