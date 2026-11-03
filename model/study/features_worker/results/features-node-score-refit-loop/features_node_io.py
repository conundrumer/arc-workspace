"""Loaders shared by the scripts: task files without test outputs, node records of R120 and S120, paths."""
import json, os, subprocess

ROOT = '/Users/davidlu/code/arc-workspace/'
DS = ROOT + 'work/lm/data-study/'
W = DS + 'sampler/sampler-worker/'
F = DS + 'features-worker/results/'
TASKDIR = ROOT + 'data/tasks/'
R120 = [W + 'sampler-cover-clauses-train-120s-c87cf482a/out/', W + 'sampler-cover-clauses-train20-120s-c87cf482a/out/']
S120 = F + 'features-corpus-pool-seed1-120s-ship7/level1_search/'
S120_JOBS = F + 'features-corpus-pool-seed1-120s-ship7/features-corpus-pool-seed1-120s-jobs.txt'
EXCLUDE = [W + 'held/tasks.txt', W + 'held/ramp-fold.txt', DS + 'features-worker/arm/eval-tasks.txt']


def excluded():
    s = set()
    for p in EXCLUDE:
        s |= set(open(p).read().split())
    return s


def load_task(tid):
    """Task json with every test output removed."""
    t = json.load(open(TASKDIR + tid + '.json'))
    for x in t['test']:
        x.pop('output', None)
    return t


def read_nodes(path):
    out = []
    p = subprocess.run(['zstd', '-dcq', path], capture_output=True, text=True)
    for l in p.stdout.splitlines():
        try:
            out.append(json.loads(l))
        except ValueError:
            pass
    return out


def s120_tasks(n=200):
    """The first n tasks of the S120 job list, in its order, outside the exclusion lists, with a nodes file and a done file."""
    import re
    ex = excluded()
    got, seen = [], set()
    for l in open(S120_JOBS):
        m = re.search(r'superdag_search\.py (\w{8}) ', l)
        if not m:
            continue
        t = m[1]
        if t in seen or t in ex:
            continue
        seen.add(t)
        if os.path.exists(S120 + t + '.nodes.jsonl.zst') and os.path.exists(S120 + t + '.done.json'):
            got.append(t)
        if len(got) == n:
            break
    return got
