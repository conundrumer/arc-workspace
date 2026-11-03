"""Gold table shapes of the S120 corpus pools (920 training tasks, 120 s, seeded to a third of depth), one task per line of s120.jsonl. Resumable.
  python -I s120.py [BUDGET_SECONDS]
A gold form gets the shapes of the nodes that its cover events name (seeded nodes have cover events at draw 0). Gold text is view-final's.
A task is left out where the run's gold count differs from view-final's form count, or where a covering node's kind differs from its gold form's kind.
Left out by task: the 37 held-out tasks, the 22 ramp tasks and the 99 evaluation tasks.
"""
import json, gzip, os, re, subprocess, sys, time
sys.dont_write_bytecode = True
HERE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/set-pick'
sys.path.insert(0, HERE)
import shapes as S
sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/refit-tools')
import search_node_score_read as R

DS = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
SRC = DS + 'features-worker/results/features-corpus-pool-seed1-120s-ship7/level1_search/'
VIEW = DS + 'gold/gold-v3-combined-cut/view-final/'
W = DS + 'sampler/sampler-worker/'
OUT = HERE + '/s120.jsonl'


def excluded():
    s = set()
    for p in (W + 'held/tasks.txt', W + 'held/ramp-fold.txt', DS + 'features-worker/arm/eval-tasks.txt'):
        s |= set(open(p).read().split())
    return s


def one(t):
    gp = VIEW + t + '/pairs.jsonl.gz'
    if not os.path.exists(gp):
        return dict(task=t, skip='no view-final gold')
    sexp = json.loads(gzip.open(gp, 'rt').readline())['gold_sexp']
    info = R.gold_info(sexp)
    lines = [x for x in sexp.strip().split('\n') if x.strip() and not x.startswith('(OUT')]
    done = json.load(open(SRC + t + '.done.json'))
    if done.get('gold') != len(lines):
        return dict(task=t, skip='gold count %s against %d' % (done.get('gold'), len(lines)))
    cov = {}
    for l in open(SRC + t + '.events.jsonl'):
        if '"cover"' in l:
            e = json.loads(l)
            if e.get('event') == 'cover':
                cov.setdefault(str(e['node']), set()).add(e['gold'])
    p = subprocess.run(['zstd', '-dcq', SRC + t + '.nodes.jsonl.zst'], capture_output=True, text=True)
    shapes = {}
    for l in p.stdout.splitlines():
        m = re.match(r'\{"token":"(\d+)"', l)
        if not m or m[1] not in cov:
            continue
        d = json.loads(l)
        kind = d['clause'][1:d['clause'].index(' ')]
        for g in cov[m[1]]:
            if kind != info['kinds'][g]:
                return dict(task=t, skip='kind %s of node %s against gold %d %s' % (kind, m[1], g, info['kinds'][g]))
            shapes.setdefault(g, set()).add((S.levels(kind, d['table_types'], S.key_sig(kind, d['clause'])), 'Ident' in d['table_types']))
    return dict(task=t, reads=info['reads'], kinds=info['kinds'], shapes={g: sorted([list(a), b] for a, b in v) for g, v in shapes.items()})


def main():
    budget = float(sys.argv[1]) if len(sys.argv) > 1 else 15
    t0 = time.time()
    ex = excluded()
    tasks = sorted({f[:8] for f in os.listdir(SRC) if f.endswith('.done.json')} - ex)
    have = set()
    if os.path.exists(OUT):
        for l in open(OUT):
            try:
                have.add(json.loads(l)['task'])
            except ValueError:
                pass
    todo = [t for t in tasks if t not in have]
    n = 0
    with open(OUT, 'a') as f:
        for t in todo:
            if time.time() - t0 > budget:
                break
            f.write(json.dumps(one(t)) + '\n')
            f.flush()
            n += 1
    print('tasks', len(tasks), 'had', len(have), 'wrote', n, 'left', len(todo) - n, 'seconds %.1f' % (time.time() - t0))


main()
