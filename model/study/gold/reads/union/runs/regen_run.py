"""Publish the gold of a converted corpus and stream each published task through the union stages of its split, in GOLD_UNION_DIR.

  .venv/bin/python regen_run.py CORPUS ROUND [P]    (a Python with zstandard: the stages' files may be zstd streams)

CORPUS is the gen folder of a conversion (it holds <task>.arclog, <task>.arcdata and cases/). ROUND is the new gold round folder, as work/lm/data-study/gold/gen-r63. P (default 6) is the number of publish processes.

- Publish: P processes of empty_gold_publication.py, each on every P-th task of CORPUS, write ROUND/publication-K/gold.jsonl.zst and log one line per task to ROUND/publish-K.log. A rerun reuses the tasks a publication has.
- Every 30 seconds, the tasks that the publish logs name since the last batch form a batch. Per split of the batch's tasks:
  - cases: gold_union_cases.py SPLIT (the whole split, written atomically);
  - fits: FITS_TASKS in shard file fits-SPLIT-<batch>.jsonl, one process per 10 tasks, with FITS_REUSE set to every fits file of GOLD_UNION_DIR, so a program already fitted is not run again; then the merge;
  - union rows (union-SPLIT-<batch>.jsonl), union keys (union-keys-SPLIT-<batch>.jsonl) and graph (graph-*-SPLIT-<batch>.jsonl), each with UNION_TASKS, each followed by its merge; the graph's merge concatenates the batch files into graph-*-SPLIT.jsonl.
  - The steps after the fits run one batch at a time per split, so no step reads a file that a merge is writing. Batches overlap in their fits.
- When publishing has ended and every batch is done, it writes the walks of each split.
- Environment: SITE (the engine), GOLD_UNION_DIR, ROWS_VERSION (the row store versions the graph accepts), RUNTIME (the publish runtime, with venv/bin/python and ready.json), FITS_CAP (default 300). Logs go to ROUND/regen/. FITS_PROCS (default 6) caps the fits processes at once. A publish process past PUBLISH_RSS_MB (default 1500) of memory is stopped and started again; publish reuses the tasks it has written. A restarted run takes up after the batches whose keys files exist.
- It prints a line with the clock time for each publish count and each batch step.
"""
import glob, json, os, signal, subprocess, sys, threading, time

R = '/Users/davidlu/code/arc-workspace/'
U = R + 'model/study/gold/reads/union/'
E = R + 'model/study/gold/cover_forms/gold_union_env.sh'
sys.path.insert(0, U)
from gold_union_fits import set_of  # noqa: E402
import study_zst as Z  # noqa: E402  on the path since gold_union_fits is imported

corpus, round_dir = sys.argv[1].rstrip('/'), sys.argv[2].rstrip('/')
P = int(sys.argv[3]) if len(sys.argv) > 3 else 6
G = os.environ['GOLD_UNION_DIR'] + '/'
RUNTIME = os.environ['RUNTIME']
LOG = round_dir + '/regen/'
os.makedirs(LOG, exist_ok=True)
locks = {}
FITS_SLOTS = threading.Semaphore(int(os.environ.get('FITS_PROCS', '6')))  # fits processes at once, over all batches
PUBLISH_RSS = int(os.environ.get('PUBLISH_RSS_MB', '1500'))  # a publish process past this many MB is stopped between tasks and started again


def say(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def sh(name, cmd, env=None):
    """Runs cmd through run_heavy, with its output in LOG/name.log; raises on failure."""
    with open(LOG + name + '.log', 'a') as f:
        subprocess.run([R + 'scripts/run_heavy.py', '--need', 'soon'] + cmd, cwd=R, env=dict(os.environ, **(env or {})), stdout=f, stderr=subprocess.STDOUT, check=True)


def published():
    """The tasks that the publish logs name."""
    done = set()
    for p in glob.glob(round_dir + '/publish-*.log'):
        for l in open(p):
            if l.startswith('{') and l.endswith('\n'):
                r = json.loads(l)
                if 'task' in r and 'done' in r:
                    done.add(r['task'])
    return done


def fits_slot(*a):
    with FITS_SLOTS:
        sh(*a)


def rss_mb(pid):
    """The resident memory of pid and its children, in MB."""
    out = subprocess.run(['ps', '-o', 'rss=,ppid=,pid=', '-A'], capture_output=True, text=True).stdout.split('\n')
    rows = [tuple(map(int, l.split())) for l in out if l.strip()]
    kids, todo, total = {}, [pid], 0
    for rss, ppid, p in rows:
        kids.setdefault(ppid, []).append((p, rss))
    seen = set()
    while todo:
        p = todo.pop()
        for c, rss in kids.get(p, []):
            if c not in seen:
                seen.add(c); total += rss; todo.append(c)
    return total // 1024


def fits_py(args, env):
    return ['env', 'PYTHONPATH=' + os.environ['SITE'], 'ARCLOG_IDENT_SOURCE=value'] + ['%s=%s' % kv for kv in env.items()] + [R + '.venv/bin/python', U + 'gold_union_fits.py'] + args


def batch(b, split, tasks):
    """The union stages of one batch of one split."""
    tag = '%s-%d' % (split, b)
    say(tag, 'cases', len(tasks), 'tasks')
    sh(tag + '-cases', [E, U + 'gold_union_cases.py', split])
    reuse = ','.join(Z.glob(G + 'fits-*.jsonl'))
    groups = [tasks[i:i + 10] for i in range(0, len(tasks), 10)]
    say(tag, 'fits', len(groups), 'processes')
    threads = [threading.Thread(target=fits_slot, args=('%s-fits-%d' % (tag, i), fits_py([split, str(b * 100 + i), '1'], dict(FITS_TASKS=' '.join(g), FITS_REUSE=reuse, FITS_CAP=os.environ.get('FITS_CAP', '300')))))
               for i, g in enumerate(groups)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with locks.setdefault(split, threading.Lock()):
        names = ' '.join(tasks)
        sh(tag + '-fits-merge', fits_py([split, 'merge'], {}))
        say(tag, 'union')
        sh(tag + '-union', [E, U + 'gold_union.py', 'run', str(b), '1000', split], dict(UNION_TASKS=names))
        sh(tag + '-union-merge', [E, U + 'gold_union.py', 'merge', split])
        say(tag, 'keys')
        sh(tag + '-keys', [E, U + 'gold_union_keys.py', split, str(b), '1000'], dict(UNION_TASKS=names))
        sh(tag + '-keys-merge', [E, U + 'gold_union_keys.py', split, 'merge'])
        say(tag, 'graph')
        sh(tag + '-graph', [E, U + 'gold_union_graph.py', split, str(b), '1000'], dict(UNION_TASKS=names))
        for f in ('tables', 'prods', 'tasks'):
            parts = sorted(Z.glob(G + 'graph-%s-%s-[0-9]*.jsonl' % (f, split)), key=lambda p: int(p.rsplit('-', 1)[1].split('.')[0]))
            last = {}
            for p in parts:  # a later batch's line for a task replaces an earlier one
                for l in Z.open_text(p):
                    last.setdefault(json.loads(l)['task'], {})[p] = None
            keep = {t: list(ps)[-1] for t, ps in last.items()}
            with Z.open_text(G + 'graph-%s-%s.jsonl' % (f, split), 'w', atomic=True) as out:
                for p in parts:
                    out.writelines(l for l in Z.open_text(p) if keep[json.loads(l)['task']] == p)
            subprocess.run(['python3', U + 'gold_union_code.py', 'concat', G + 'graph-%s-%s.jsonl' % (f, split)] + parts, check=True)
        say(tag, 'done')


def main():
    tasks = sorted(p[:-len('.arcdata')].rsplit('/', 1)[1] for p in glob.glob(corpus + '/*.arcdata'))
    say('publish', len(tasks), 'tasks in', P, 'processes')
    pubs, cmds = [], []
    for k in range(P):
        os.makedirs(round_dir + '/publication-%d' % k, exist_ok=True)
        cmd = [R + 'scripts/run_heavy.py', '--need', 'soon', RUNTIME + '/venv/bin/python', '-B', R + 'model/study/empty_gold_publication.py', 'publish',
               '--corpus', corpus, '--tasks', R + 'data/tasks', '--runtime', RUNTIME, '--output', round_dir + '/publication-%d/gold.jsonl.zst' % k,
               '--deadline-seconds', '240'] + [x for t in tasks[k::P] for x in ('--task', t)]
        cmds.append(cmd)
        pubs.append(subprocess.Popen(cmd, cwd=R, stdout=open(round_dir + '/publish-%d.log' % k, 'a'), stderr=subprocess.STDOUT, start_new_session=True))
    seen, b, running = set(), 0, []
    for split in ('train', 'dev', 'held-out'):  # a restart takes up where the batches of an earlier run stopped
        for p in Z.glob(G + 'union-keys-%s-[0-9]*.jsonl' % split):
            seen |= {json.loads(l)['task'] for l in Z.open_text(p) if l.endswith('\n')}
            b = max(b, int(p.rsplit('-', 1)[1].split('.')[0]) + 1)
    say('resumed', len(seen), 'tasks from earlier batches; next batch', b)
    while True:
        for k, p in enumerate(pubs):  # a publish process grows with the tasks it has done; a fresh one reuses the finished tasks
            if p.poll() is None and rss_mb(p.pid) > PUBLISH_RSS:
                os.killpg(p.pid, signal.SIGTERM); p.wait()
                say('publish', k, 'restarted past', PUBLISH_RSS, 'MB')
                pubs[k] = subprocess.Popen(cmds[k], cwd=R, stdout=open(round_dir + '/publish-%d.log' % k, 'a'), stderr=subprocess.STDOUT, start_new_session=True)
        ended = all(p.poll() is not None for p in pubs)
        new = sorted(published() - seen)
        if new:
            seen |= set(new)
            say('published', len(seen), 'of', len(tasks))
            by = {}
            for t in new:
                try:
                    by.setdefault(set_of(t), []).append(t)
                except KeyError:
                    say('no split for', t)
            for split, ts in by.items():
                th = threading.Thread(target=batch, args=(b, split, ts))
                th.start()
                running.append(th)
            b += 1
        if ended and not new:
            break
        time.sleep(30)
    say('publish ended', [p.returncode for p in pubs], 'tasks published', len(seen), 'of', len(tasks))
    for th in running:
        th.join()
    for split in ('train', 'dev', 'held-out'):
        if Z.exists(G + 'graph-tasks-%s.jsonl' % split):
            sh('walks-' + split, [R + '.venv/bin/python', U + 'gold_union_walks.py', split])
            say(split, 'walks')
    say('done')


if __name__ == '__main__':
    main()
