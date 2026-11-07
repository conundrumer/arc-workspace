"""The union stages of a few tasks of a published round, one phase at a time, in GOLD_UNION_DIR. It runs the commands of `regen_run.py`'s batch, split into phases, so that each phase is a command of its own and the row store of the tasks can be built between the keys and the graph.

  python3 regen_tasks.py cases BATCH TASK...      per split of the tasks: cases-SPLIT.jsonl (the whole split)
  python3 regen_tasks.py fits BATCH TASK...       the fits of each task, one process a task, at most FITS_PROCS at once, in fits-SPLIT-<BATCH * 100 + n>.jsonl; each program that a fits file of GOLD_UNION_DIR (or FITS_REUSE, files separated by commas) already fitted is not run again
  python3 regen_tasks.py union BATCH TASK...      per split of the tasks: the fits merge, the union rows and the union keys, each followed by its merge
  python3 regen_tasks.py graph BATCH TASK...      per split of the tasks: graph-*-SPLIT-BATCH.jsonl, then graph-*-SPLIT.jsonl made as `regen_run.py` makes it (a later batch's line of a task replaces an earlier one's). It needs the row store of each task (ARC_SAMPLE_OUT/SPLIT/rows/TASK.jsonl.gz).
  python3 regen_tasks.py walks                    the walks of every split that has a graph-tasks file

BATCH is the number of the shard files, above every number in GOLD_UNION_DIR. A task's lines in the shard files of the union, the union keys and the fits must be gone first, as the stages skip a task that a shard holds. A task in the union phase with no fits row gets the union row `no fits row`.
Each step logs to LOG/<step>.log, LOG being REGEN_LOG (default GOLD_UNION_DIR/regen), and runs through run_heavy.py with one CPU. A rerun takes up where the stages' own restart rules take it.
Environment: SITE (the engine), GOLD_UNION_DIR, ROWS_VERSION, ARC_SAMPLE_OUT (the samples folder that holds the row stores), SAMPLER_LIVE_TRY (see gold_union_fits.py), FITS_CAP (default 300), FITS_PROCS (default 2).
"""
import glob, json, os, subprocess, sys, threading, time

CODE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../../..')) + '/'  # the checkout that holds this file
DATA = '/Users/davidlu/code/arc-workspace/'  # the main checkout: .venv and the data
U = CODE + 'model/study/gold/reads/union/'
E = CODE + 'model/study/gold/cover_forms/gold_union_env.sh'
G = os.environ['GOLD_UNION_DIR'].rstrip('/') + '/'
LOG = os.environ.get('REGEN_LOG', G + 'regen') + '/'
sys.path.insert(0, U)
from gold_union_fits import set_of  # noqa: E402

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
    reuse = ','.join(sorted(glob.glob(G + 'fits-*.jsonl')) + [x for x in os.environ.get('FITS_REUSE', '').split(',') if x])
    threads = [threading.Thread(target=fits_one, args=(set_of(t), b, i, t, reuse)) for i, t in enumerate(tasks)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()


def union_phase(b, tasks):
    for split, ts in by_split(tasks).items():
        tag = '%s-%d' % (split, b)
        names = ' '.join(ts)
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
        for f in ('tables', 'prods', 'tasks'):
            parts = sorted(glob.glob(G + 'graph-%s-%s-[0-9]*.jsonl' % (f, split)), key=lambda p: int(p.rsplit('-', 1)[1].split('.')[0]))
            last = {}
            for p in parts:  # a later batch's line for a task replaces an earlier one
                for l in open(p):
                    last.setdefault(json.loads(l)['task'], {})[p] = None
            keep = {t: list(ps)[-1] for t, ps in last.items()}
            with open(G + 'graph-%s-%s.jsonl.part' % (f, split), 'w') as out:
                for p in parts:
                    out.writelines(l for l in open(p) if keep[json.loads(l)['task']] == p)
            os.replace(G + 'graph-%s-%s.jsonl.part' % (f, split), G + 'graph-%s-%s.jsonl' % (f, split))
            subprocess.run(['python3', U + 'gold_union_code.py', 'concat', G + 'graph-%s-%s.jsonl' % (f, split)] + parts, check=True)


def walks_phase():
    for split in ('train', 'dev', 'held-out'):
        if os.path.exists(G + 'graph-tasks-%s.jsonl' % split):
            say(split, 'walks')
            sh('walks-' + split, ['python3', U + 'gold_union_walks.py', split])


if __name__ == '__main__':
    phase = sys.argv[1]
    if phase == 'walks':
        walks_phase()
    else:
        {'cases': cases_phase, 'fits': fits_phase, 'union': union_phase, 'graph': graph_phase}[phase](int(sys.argv[2]), sys.argv[3:])
    say(phase, 'done')
