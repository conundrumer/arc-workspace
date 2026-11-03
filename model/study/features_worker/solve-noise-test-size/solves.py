"""Per-run, per-task candidate and right-on-test fields that the runs wrote, and 2 by 2 counts for control pairs.

Sources, read as written by each run:
- worker path: <arm>/<task>/supervisor.log, last line 'task T lives L candidates C done'; no right field.
- direct path: <out>/<task>.done.json, fields 'candidates' and 'right'.
- read-fresh.txt of sampler-pool-fold-seeds-600s: the 'right [...]' lists, written by that run's read_fresh.py.
No test output is opened. Exits 75 when RSS passes 3 GiB.
"""
import glob, json, os, re, resource, sys

D = '/Users/davidlu/code/arc-workspace/work/lm/data-study/'
SW = D + 'sampler/search-worker/runs/'
SA = D + 'sampler/sampler-worker/'
LIMIT = 3 * 1024 ** 3


def guard():
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # bytes on macOS
    if rss > LIMIT:
        print('RSS past 3 GiB', file=sys.stderr)
        sys.exit(75)


RAMP = set(open(SA + 'held/ramp-fold.txt').read().split())
H37 = set(open(SA + 'held/tasks.txt').read().split())
END = re.compile(r' task (\w+) lives (\d+) candidates (\d+) done')


def worker(arm_dir):
    out = {}
    for log in sorted(glob.glob(arm_dir + '/*/supervisor.log')):
        task = os.path.basename(os.path.dirname(log))
        with open(log, errors='replace') as f:
            for line in f:
                m = END.search(line)
                if m and m[1] == task:
                    out[task] = dict(cand=int(m[3]), right=None)
        guard()
    return out


def direct(out_dir):
    out = {}
    for p in sorted(glob.glob(out_dir + '/*.done.json')):
        with open(p) as f:
            e = json.load(f)
        out[e['task']] = dict(cand=int(e['candidates']), right=int(e['right']))
        guard()
    return out


def fresh_right():
    lists = {}
    sec = None
    for line in open(SA + 'sampler-pool-fold-seeds-600s/read-fresh.txt'):
        if line.startswith('=='):
            sec = line.split()[1]
            continue
        m = re.match(r"(\w+) tasks (\d+) covered \d+ whole \d+ with candidate (\d+) right \[(.*)\]", line)
        if m and sec == 'fold':
            lists[m[1]] = (int(m[2]), int(m[3]), set(re.findall(r"'(\w+)'", m[4])))
    return lists


RUNS = {
    'r1 bundle_s0': ('w', SW + 'search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943/out/bundle_s0'),
    'r1 bundle_s1': ('w', SW + 'search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943/out/bundle_s1'),
    'r1 refit_s0': ('w', SW + 'search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943/out/refit_s0'),
    'r1 refit_s1': ('w', SW + 'search-refit-r1-heldout37-ramp22-2seeds-600s-0729e4943/out/refit_s1'),
    'pass bundle_s0': ('w', SW + 'search-pass-r1-heldout37-ramp22-2seeds-600s-0729e4943/out/bundle_s0'),
    'pass bundle_s1': ('w', SW + 'search-pass-r1-heldout37-ramp22-2seeds-600s-0729e4943/out/bundle_s1'),
    'pass pass_s0': ('w', SW + 'search-pass-r1-heldout37-ramp22-2seeds-600s-0729e4943/out/pass_s0'),
    'pass pass_s1': ('w', SW + 'search-pass-r1-heldout37-ramp22-2seeds-600s-0729e4943/out/pass_s1'),
    'ext_s0': ('w', SA + 'sampler-pool-refit-ext-ramp-600s/out/ext_s0'),
    'ext_s1': ('w', SA + 'sampler-pool-refit-ext-ramp-600s/out/ext_s1'),
    'coverf_s0': ('w', SA + 'sampler-pool-cover-fold-600s/out/coverf_s0'),
    'coverf_s1': ('w', SA + 'sampler-pool-cover-fold-600s/out/coverf_s1'),
    'fresh_2000': ('w', SA + 'sampler-pool-fold-seeds-600s/out/fresh_2000'),
    'fresh_3000': ('w', SA + 'sampler-pool-fold-seeds-600s/out/fresh_3000'),
    'fresh_4000': ('w', SA + 'sampler-pool-fold-seeds-600s/out/fresh_4000'),
    'fresh_5000': ('w', SA + 'sampler-pool-fold-seeds-600s/out/fresh_5000'),
    'hour_s0': ('w', SA + 'sampler-pool-fold-hour-3600s/out/hour_s0'),
    'hour_s1': ('w', SA + 'sampler-pool-fold-hour-3600s/out/hour_s1'),
    'N600 nodes_s0': ('w', SA + 'sampler-pool-dag-nodes-train50-600s/out/nodes_s0'),
    'R120 train': ('d', SA + 'sampler-cover-clauses-train-120s-c87cf482a/out'),
    'R120 train20': ('d', SA + 'sampler-cover-clauses-train20-120s-c87cf482a/out'),
    'S120': ('d', D + 'features-worker/results/features-corpus-pool-seed1-120s-ship7/level1_search'),
}

PAIRS = [
    ('r1 bundle_s0', 'r1 bundle_s1'), ('r1 refit_s0', 'r1 refit_s1'),
    ('pass bundle_s0', 'pass bundle_s1'), ('pass pass_s0', 'pass pass_s1'),
    ('r1 bundle_s0', 'pass bundle_s0'), ('r1 bundle_s1', 'pass bundle_s1'),
    ('r1 bundle_s0', 'pass bundle_s1'), ('r1 bundle_s1', 'pass bundle_s0'),
    ('ext_s0', 'ext_s1'), ('hour_s0', 'hour_s1'),
] + [(a, b) for i, a in enumerate(['coverf_s0', 'coverf_s1', 'fresh_2000', 'fresh_3000', 'fresh_4000', 'fresh_5000'])
     for b in ['coverf_s0', 'coverf_s1', 'fresh_2000', 'fresh_3000', 'fresh_4000', 'fresh_5000'][i + 1:]]


def part(t):
    return 'ramp22' if t in RAMP else 'the37' if t in H37 else 'training'


def main():
    R = {}
    for name, (kind, path) in RUNS.items():
        R[name] = worker(path) if kind == 'w' else direct(path)
    fr = fresh_right()
    for name, (n, c, right) in fr.items():
        if name in R:
            for t in R[name]:
                if part(t) == 'ramp22':
                    R[name][t]['right'] = int(t in right)
    print('== per run: set, tasks ended, tasks with a candidate (judge right or candidate), tasks right (judge right on test)')
    for name, v in R.items():
        by = {}
        for t, x in v.items():
            by.setdefault(part(t), []).append((t, x))
        for s in ['ramp22', 'the37', 'training']:
            if s not in by:
                continue
            xs = by[s]
            cand = sorted(t for t, x in xs if x['cand'] > 0)
            rk = [x['right'] for t, x in xs]
            right = 'not written' if any(r is None for r in rk) else str(sorted(t for t, x in xs if x['right'] > 0))
            print('%-15s %-8s tasks %4d  cand %3d %s  right %s' % (name, s, len(xs), len(cand), cand if len(cand) <= 12 else '', right))
    print('== pairs: set, judge, tasks in both runs, both, only first, only second, neither, difference')
    for a, b in PAIRS:
        for s in ['ramp22', 'the37']:
            ts = sorted(t for t in R[a] if t in R[b] and part(t) == s)
            if not ts:
                continue
            for judge in ['cand', 'right']:
                if any(R[a][t]['right'] is None or R[b][t]['right'] is None for t in ts) and judge == 'right':
                    print('%-15s %-15s %-7s right: not written' % (a, b, s))
                    continue
                A = {t for t in ts if R[a][t][judge] > 0}
                B = {t for t in ts if R[b][t][judge] > 0}
                print('%-15s %-15s %-7s %-5s n %2d  both %d  only1 %d %s  only2 %d %s  neither %d  diff %+d' % (
                    a, b, s, judge, len(ts), len(A & B), len(A - B), sorted(A - B), len(B - A), sorted(B - A), len(ts) - len(A | B), len(A) - len(B)))
    print('max RSS MiB', resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 2 ** 20)


if __name__ == '__main__':
    main()
