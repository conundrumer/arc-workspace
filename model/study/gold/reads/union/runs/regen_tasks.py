"""The union stages of a few tasks of a published round, one phase at a time, in GOLD_UNION_DIR. It runs the commands of `regen_run.py`'s batch, split into phases, so that each phase is a command of its own and the row store of the tasks can be built between the keys and the graph.

  .venv/bin/python regen_tasks.py cases BATCH TASK...      per split of the tasks: cases-SPLIT.jsonl (the whole split)
  .venv/bin/python regen_tasks.py fits BATCH TASK...       the fits of each task, one process a task, at most FITS_PROCS at once, in fits-SPLIT-<BATCH * 100 + n>.jsonl; each program that a fits file of GOLD_UNION_DIR (or FITS_REUSE, files separated by commas) already fitted is not run again
  .venv/bin/python regen_tasks.py union BATCH TASK...      per split of the tasks: the fits merge, the union rows and the union keys, each followed by its merge
  .venv/bin/python regen_tasks.py graph BATCH TASK...      per split of the tasks: graph-*-SPLIT-BATCH.jsonl, then graph-*-SPLIT.jsonl made as `regen_run.py` makes it (a later batch's line of a task replaces an earlier one's, and a task whose latest graph-tasks line is an error has no line in graph-tables and graph-prods). It needs the row store of each task (ARC_SAMPLE_OUT/SPLIT/rows/TASK.jsonl.gz).
  .venv/bin/python regen_tasks.py walks                    the walks of every split that has a graph-tasks file

BATCH is the number of the shard files, above every number in GOLD_UNION_DIR. A task's lines in the shard files of the union, the union keys and the fits must be gone first (`strip_tasks.py` in this folder, add `--kinds union,keys,fits,graph` to take the graph shard files of a batch again), as the stages skip a task that a shard holds and a merge takes a task's line from the last shard file by name; the fits and union phases stop, naming the files, where an older shard holds a line of a task. A task in the union phase with no fits row gets the union row `no fits row`.
A Python with zstandard runs this file (`.venv/bin/python`); it stops at once where the Python has none.
Each step logs to LOG/<step>.log, LOG being REGEN_LOG (default GOLD_UNION_DIR/regen), and runs through run_heavy.py with one CPU. A rerun takes up where the stages' own restart rules take it.
Environment: SITE (the engine), GOLD_UNION_DIR, ROWS_VERSION, ARC_SAMPLE_OUT (the samples folder that holds the row stores), SAMPLER_LIVE_TRY (see gold_union_fits.py), FITS_CAP (default 300), FITS_PROCS (default 2).
"""
import glob, json, os, re, subprocess, sys, threading, time

CODE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../../../..')) + '/'  # the checkout that holds this file
DATA = '/Users/davidlu/code/arc-workspace/'  # the main checkout: .venv and the data
U = CODE + 'model/study/gold/reads/union/'
E = CODE + 'model/study/gold/cover_forms/gold_union_env.sh'
G = os.environ['GOLD_UNION_DIR'].rstrip('/') + '/'
LOG = os.environ.get('REGEN_LOG', G + 'regen') + '/'
sys.path.insert(0, U)
from gold_union_fits import set_of  # noqa: E402
import study_zst as Z  # noqa: E402  on the path since gold_union_fits is imported

try:
    import zstandard  # noqa: F401  the stages' files may be zstd streams, and the graph phase reads them in this process
except ImportError:
    sys.exit('regen_tasks.py needs a Python with zstandard (.venv/bin/python): %s has none' % sys.executable)

os.makedirs(LOG, exist_ok=True)
SLOTS = threading.Semaphore(int(os.environ.get('FITS_PROCS', '2')))


def say(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def sh(name, cmd, env=None):
    """Runs cmd through run_heavy with one CPU, its output in LOG/name.log; raises on failure."""
    with open(LOG + name + '.log', 'a') as f:
        subprocess.run([CODE + 'scripts/run_heavy.py', '--cpus', '1', '--need', 'soon'] + cmd, cwd=CODE, env=dict(os.environ, **(env or {})), stdout=f, stderr=subprocess.STDOUT, check=True)


def fits_py(args, env):
    return ['env', 'PYTHONPATH=' + os.environ['SITE'], 'ARCLOG_IDENT_SOURCE=value'] + ['%s=%s' % kv for kv in env.items()] + [DATA + '.venv/bin/python', U + 'gold_union_fits.py'] + args


TASK = re.compile(r'\{"(?:task|stem)": "([0-9a-f]{8})"')


def held_elsewhere(kind, split, b, tasks):
    """{shard file: [task]} of the shard files of the split, other than those of batch b, that hold a line of a task. kind is fits (shards b * 100 to b * 100 + 99), union or keys (shard b)."""
    pat = re.compile({'fits': r'fits-%s-(\d+)', 'union': r'union-%s-(\d+)', 'keys': r'union-keys-%s-(\d+)'}[kind] % re.escape(split) + r'\.jsonl')
    got = {}
    for p in Z.glob(G + '*-%s-*.jsonl' % split):
        m = pat.fullmatch(os.path.basename(p))
        if not m or (b * 100 <= int(m[1]) < b * 100 + 100 if kind == 'fits' else int(m[1]) == b):
            continue
        for l in Z.open_text(p):
            t = TASK.match(l)
            if t and t[1] in tasks and l.endswith('\n') and t[1] not in got.get(os.path.basename(p), []):
                got.setdefault(os.path.basename(p), []).append(t[1])
    return got


def refuse_held(kind, split, b, tasks):
    held = held_elsewhere(kind, split, b, set(tasks))
    if held:
        sys.exit('%s shard files hold lines of tasks that this batch takes again: %s\nRun: %s %s/strip_tasks.py %s %s' % (kind, '; '.join('%s: %s' % kv for kv in sorted(held.items())), sys.executable, os.path.dirname(os.path.abspath(__file__)), G, ' '.join(tasks)))


def by_split(tasks):
    got = {}
    for t in tasks:
        got.setdefault(set_of(t), []).append(t)
    return got


def cases_phase(b, tasks):
    for split in by_split(tasks):
        say(split, 'cases')
        sh('%s-%d-cases' % (split, b), [E, U + 'gold_union_cases.py', split])


def fits_one(split, b, n, task, reuse):
    with SLOTS:
        say(split, 'fits', task)
        sh('%s-%d-fits-%d' % (split, b, b * 100 + n), fits_py([split, str(b * 100 + n), '1'], dict(FITS_TASKS=task, FITS_REUSE=reuse, FITS_CAP=os.environ.get('FITS_CAP', '300'))))
        say(split, 'fits', task, 'done')


def fits_phase(b, tasks):
    for split, ts in by_split(tasks).items():
        refuse_held('fits', split, b, ts)
    reuse = ','.join(Z.glob(G + 'fits-*.jsonl') + [x for x in os.environ.get('FITS_REUSE', '').split(',') if x])
    threads = [threading.Thread(target=fits_one, args=(set_of(t), b, i, t, reuse)) for i, t in enumerate(tasks)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()


def union_phase(b, tasks):
    for split, ts in by_split(tasks).items():
        tag = '%s-%d' % (split, b)
        names = ' '.join(ts)
        refuse_held('union', split, b, ts)
        refuse_held('keys', split, b, ts)
        sh(tag + '-fits-merge', fits_py([split, 'merge'], {}))
        say(tag, 'union')
        sh(tag + '-union', [E, U + 'gold_union.py', 'run', str(b), '1000', split], dict(UNION_TASKS=names))
        sh(tag + '-union-merge', [E, U + 'gold_union.py', 'merge', split])
        say(tag, 'keys')
        sh(tag + '-keys', [E, U + 'gold_union_keys.py', split, str(b), '1000'], dict(UNION_TASKS=names))
        sh(tag + '-keys-merge', [E, U + 'gold_union_keys.py', split, 'merge'])


def graph_phase(b, tasks):
    for split, ts in by_split(tasks).items():
        tag = '%s-%d' % (split, b)
        say(tag, 'graph')
        sh(tag + '-graph', [E, U + 'gold_union_graph.py', split, str(b), '1000'], dict(UNION_TASKS=' '.join(ts)))
        failed = set()  # tasks whose latest graph-tasks line is an error: the merged tables and prods files hold no line of them
        for f in ('tasks', 'tables', 'prods'):
            parts = sorted(Z.glob(G + 'graph-%s-%s-[0-9]*.jsonl' % (f, split)), key=lambda p: int(p.rsplit('-', 1)[1].split('.')[0]))
            last = {}
            for p in parts:  # a later batch's line for a task replaces an earlier one
                for l in Z.open_text(p):
                    last.setdefault(json.loads(l)['task'], {})[p] = None
            keep = {t: list(ps)[-1] for t, ps in last.items()}
            if f == 'tasks':
                failed = {t for p in set(keep.values()) for l in Z.open_text(p) for r in [json.loads(l)] for t in [r['task']] if keep[t] == p and 'error' in r}
            keep = {t: p for t, p in keep.items() if t not in failed or f == 'tasks'}
            with Z.open_text(G + 'graph-%s-%s.jsonl' % (f, split), 'w', atomic=True) as out:
                for p in parts:
                    out.writelines(l for l in Z.open_text(p) if keep.get(json.loads(l)['task']) == p)
            subprocess.run([sys.executable, U + 'gold_union_code.py', 'concat', G + 'graph-%s-%s.jsonl' % (f, split)] + parts, check=True)


def walks_phase():
    for split in ('train', 'dev', 'held-out'):
        if Z.exists(G + 'graph-tasks-%s.jsonl' % split):
            say(split, 'walks')
            sh('walks-' + split, [DATA + '.venv/bin/python', U + 'gold_union_walks.py', split])


if __name__ == '__main__':
    phase = sys.argv[1]
    if phase == 'walks':
        walks_phase()
    else:
        {'cases': cases_phase, 'fits': fits_phase, 'union': union_phase, 'graph': graph_phase}[phase](int(sys.argv[2]), sys.argv[3:])
    say(phase, 'done')
