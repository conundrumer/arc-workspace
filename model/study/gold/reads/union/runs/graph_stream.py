"""Build the union graph of each task of the splits as soon as its row store is written or rewritten, on the engine SITE, in the folder OUT_DIR.

  SITE=<site> ROWS_VERSION=<versions> GOLD_UNION_DIR=<union folder> OUT_DIR=<graph folder> python3 graph_stream.py [SPLIT ...]

- OUT_DIR holds links to union-SPLIT.jsonl and union-keys-SPLIT.jsonl of GOLD_UNION_DIR, so the graph reads the current union.
- Every 30 seconds, the tasks of a split whose row store (work/lm/data-study/samples/SPLIT/rows/<task>.jsonl.gz) is newer than the task's last graph, and that have a union-keys line, form a batch. gold_union_graph.py runs on the batch (UNION_TASKS), 50 tasks a process, into graph-*-SPLIT-<n>.jsonl, and graph-*-SPLIT.jsonl is then the latest batch's lines of each task, with its .code.json. Then gold_union_walks.py writes the split's walks there.
- A task whose union-keys line changes is built again too.
- With STREAM_TASKS (tasks separated by spaces), only those tasks are built. With STREAM_SINCE (seconds since the epoch), only stores written after that time are built.
- It stops when the file OUT_DIR/STOP exists, or after IDLE seconds (default 3600) with no new store. It prints a line with the clock time for each batch.
"""
import glob, hashlib, json, os, subprocess, sys, time

R = '/Users/davidlu/code/arc-workspace/'
U = R + 'model/study/gold/reads/union/'
E = R + 'model/study/gold/cover_forms/gold_union_env.sh'
SAMPLES = R + 'work/lm/data-study/samples/'
G = os.environ['GOLD_UNION_DIR'] + '/'
O = os.environ['OUT_DIR'] + '/'
SPLITS = sys.argv[1:] or ['train', 'dev', 'held-out']
IDLE = float(os.environ.get('IDLE', 3600))
ONLY = set(os.environ['STREAM_TASKS'].split()) if os.environ.get('STREAM_TASKS') else None
SINCE = float(os.environ.get('STREAM_SINCE', 0))


def say(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def keys_of(split):
    """{task: digest of its union-keys lines}."""
    got = {}
    p = G + 'union-keys-%s.jsonl' % split
    if os.path.exists(p):
        for l in open(p):
            if l.endswith('\n'):
                got.setdefault(json.loads(l)['task'], hashlib.sha256()).update(l.encode())
    return {t: h.hexdigest() for t, h in got.items()}


def concat(split):
    for f in ('tables', 'prods', 'tasks'):
        parts = sorted(glob.glob(O + 'graph-%s-%s-[0-9]*.jsonl' % (f, split)), key=lambda p: int(p.rsplit('-', 1)[1].split('.')[0]))
        last = {}
        for p in parts:  # a later batch's lines for a task replace an earlier batch's
            for l in open(p):
                last[json.loads(l)['task']] = p
        with open(O + 'graph-%s-%s.jsonl.part' % (f, split), 'w') as out:
            for p in parts:
                out.writelines(l for l in open(p) if last[json.loads(l)['task']] == p)
        os.replace(O + 'graph-%s-%s.jsonl.part' % (f, split), O + 'graph-%s-%s.jsonl' % (f, split))
        subprocess.run(['python3', U + 'gold_union_code.py', 'concat', O + 'graph-%s-%s.jsonl' % (f, split)] + parts, check=True)


def main():
    os.makedirs(O, exist_ok=True)
    for s in SPLITS:
        for name in ('union-%s.jsonl' % s, 'union-keys-%s.jsonl' % s):
            if not os.path.lexists(O + name):
                os.symlink(G + name, O + name)
    built = {}  # (split, task) -> (store mtime, keys digest) of its last graph
    b = 1 + max([int(p.rsplit('-', 1)[1].split('.')[0]) for p in glob.glob(O + 'graph-tasks-*-[0-9]*.jsonl')] or [-1])
    last_new = time.time()
    while not os.path.exists(O + 'STOP') and time.time() - last_new < IDLE:
        for s in SPLITS:
            keys = keys_of(s)
            todo = []
            for p in glob.glob(SAMPLES + '%s/rows/*.jsonl.gz' % s):
                t = os.path.basename(p)[:-len('.jsonl.gz')]
                if t in keys and (ONLY is None or t in ONLY) and os.path.getmtime(p) > SINCE:
                    now = (os.path.getmtime(p), keys[t])
                    if built.get((s, t)) != now and time.time() - now[0] > 10:  # a store still being written waits
                        todo.append((t, now))
            if todo:
                last_new = time.time()
                say(s, 'batch', b, len(todo), 'tasks')
                procs = []
                for i in range(0, len(todo), 50):  # 50 tasks a process, all at once; run_heavy admits them by load
                    env = dict(os.environ, GOLD_UNION_DIR=O[:-1], UNION_TASKS=' '.join(t for t, _ in todo[i:i + 50]))
                    procs.append(subprocess.Popen([R + 'scripts/run_heavy.py', '--need', 'soon', E, U + 'gold_union_graph.py', s, str(b), '1000'], cwd=R, env=env,
                                                  stdout=open(O + 'graph-%s-%d.log' % (s, b), 'w'), stderr=subprocess.STDOUT))
                    b += 1
                codes = [p.wait() for p in procs]
                for t, now in todo:  # a task of a failed process is not tried again until its store or keys change
                    built[s, t] = now
                concat(s)
                subprocess.run(['python3', U + 'gold_union_walks.py', s], env=dict(os.environ, GOLD_UNION_DIR=O[:-1]), stdout=open(O + 'walks-%s.log' % s, 'w'), stderr=subprocess.STDOUT)
                say(s, 'done', len(todo), 'tasks; failed processes', sum(c != 0 for c in codes))
        time.sleep(30)
    say('stopped')


if __name__ == '__main__':
    main()
