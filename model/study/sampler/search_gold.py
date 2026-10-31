#!/usr/bin/env python
"""Paired test of Sampler.search against independent Sampler.clause draws: the CPU seconds each takes to find gold's clause.

  <runtime python> search_gold.py run    [--stems FILE] [--out DIR] [--budget 60] [--jobs 2] [--limit N] [--every K] [--job-timeout S]
  <runtime python> search_gold.py report [--out DIR] [--budget 60]
  <runtime python> search_gold.py job TASK CASE POINT ARM [--out DIR] [--budget 60]    (one job, in this process)

A job is a point (a task, a case and a point [clause index, 0] of gold's program in the point store) and an arm, 'draw' or 'search'.
The scope is gold's forms before the clause, and the target is gold's clause: a clause hits where its clause_key equals the target's, so
the order of atoms and the names of labels do not matter. Both arms start their CPU clock (time.process_time) after the session and the
Sampler load, so each pays for the scope's replay; each stops at its first hit or at the budget. A job writes its result file when it ends,
and `run` skips the jobs that have one, runs `--jobs` processes at once, each through scripts/run_heavy.py, and prints a rate and an ETA.

The point store is SAMPLER_FSTORE (default: the store of the run that made the stems file). draw: seeds 0, 1, 2, ... each to Sampler.clause.
search: Sampler.search in chunks of CHUNK seconds of wall time, which exercises its continuing.
"""
import argparse
import collections
import gzip
import hashlib
import json
import os
import resource
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
FSTORE = os.environ.setdefault('SAMPLER_FSTORE', '/Users/davidlu/code/arc-workspace/work/lm/data-study/feat-exp/fstore-gen3/points-t/')
import sampler_paths as P  # noqa: E402

STEMS = P.SAMPLER_DATA + '/runs/runF_r4t.stems'
OUT = P.SAMPLER_DATA + '/runs/bestfirst'
CHUNK = 2.0  # seconds of wall time in one call of Sampler.search
ARMS = 'draw', 'search'


def points(stems):
    """[(task, case, point)] of the stems file, in its order."""
    out = []
    for line in open(stems):
        if line.strip():
            task, case, point = line.rstrip('\n').split('\t')
            out.append((task, case, json.loads(point)))
    return out


def gold_of(task, case, point):
    """Gold's program of the point, as its lines."""
    path = P.SAMPLER_DATA + '/fstore_index-%s.json.gz' % hashlib.sha256(FSTORE.encode()).hexdigest()[:8]
    with gzip.open(path, 'rt') as f:
        idx = json.load(f)
    for d, e in idx['points'].items():
        if d.startswith(task + '-') and e[0] == case and e[1] == point:
            return d, [x for x in idx['golds'][e[2]].splitlines() if x.strip()]
    raise KeyError((task, case, point))


def result_path(out, arm, task, case, point):
    return os.path.join(out, arm, '%s.%s.%s.json' % (task, case.replace(' ', '_').replace('$', ''), '-'.join(map(str, point))))


def job(task, case, point, arm, out, budget):
    import live
    import live_try
    import search
    t0 = time.process_time()
    d, lines = gold_of(task, case, point)
    scope, target = lines[:point[0]], lines[point[0]]
    tk = search.clause_key(target)
    sampler = live.Sampler(P.SAMPLER_DATA + '/models')
    sess, task_json, _ = live_try.session_of(task)
    res = dict(task=task, case=case, point=point, arm=arm, budget=budget, target=target, forms=len(scope), setup_cpu=round(time.process_time() - t0, 2), hit=False)
    c0 = time.process_time()
    cpu = lambda: time.process_time() - c0  # noqa: E731
    seen = set()
    if arm == 'draw':
        calls = ok = 0
        while cpu() < budget:
            c = sampler.clause(sess, calls, time.monotonic() + 30, task_json, scope, 'RULE')
            calls += 1
            if c is None:
                continue
            ok += 1
            key = search.clause_key(c.text)
            seen.add(key)
            if key == tk:
                res.update(hit=True, hit_cpu=round(cpu(), 3), draws_to_hit=calls, text=c.text)
                break
        res.update(tried=calls, clauses=ok, distinct=len(seen), counts={k: v for k, v in sampler.run.c.items() if not k.startswith('scope')} if sampler.run else {})
    else:
        emitted, gen = 0, [None]
        se = sampler.search(sess, 0, time.monotonic() + CHUNK, task_json, scope, 'RULE')

        def on_leaf(key):
            if key == tk and gen[0] is None:
                gen[0] = cpu()
        se.on_leaf = on_leaf
        while cpu() < budget and not res['hit']:
            for c in se:
                emitted += 1
                if c.key == tk:
                    res.update(hit=True, hit_cpu=round(cpu(), 3), emitted_to_hit=emitted, logq_bits=round(c.logq / -0.6931471805599453, 2), text=c.text)
                    break
            if se.exhausted or not se.heap:
                break
            se = sampler.search(sess, 0, time.monotonic() + CHUNK, task_json, scope, 'RULE')
            se.on_leaf = on_leaf
        res.update(tried=se.stats['runs'], clauses=emitted, distinct=emitted, gen_cpu=None if gen[0] is None else round(gen[0], 3),
                   counts=dict(se.stats) | {k: v for k, v in se.run.c.items() if not k.startswith('scope')}, frontier=len(se.heap), dropped_bits=None if se.dropped == -float('inf') else round(se.dropped / -0.6931471805599453, 2))
    res.update(cpu=round(cpu(), 2), maxrss_mib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20))
    os.makedirs(os.path.dirname(result_path(out, arm, task, case, point)), exist_ok=True)
    tmp = result_path(out, arm, task, case, point) + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(res, f)
    os.replace(tmp, result_path(out, arm, task, case, point))
    return res


def run(a):
    pts = points(a.stems)[::a.every][:a.limit]
    todo = [(p, arm) for p in pts for arm in ARMS if not os.path.exists(result_path(a.out, arm, *p))]
    print('%d points, %d jobs left' % (len(pts), len(todo)), flush=True)
    heavy = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), 'scripts', 'run_heavy.py')
    running, t0, done = [], time.time(), 0
    n = len(todo)
    while todo or running:
        while todo and len(running) < a.jobs:
            (task, case, point), arm = todo.pop(0)
            cmd = ['timeout', str(a.job_timeout), heavy, '--cpus', '1', '--need', 'soon', sys.executable, '-u', os.path.abspath(__file__), 'job', task, case, json.dumps(point), arm,
                   '--out', a.out, '--budget', str(a.budget)]
            running.append((subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=dict(os.environ, RAYON_NUM_THREADS='1')), task, case, point, arm))
        time.sleep(0.5)
        for r in running[:]:
            if r[0].poll() is not None:
                running.remove(r)
                done += 1
                text = r[0].stdout.read()
                p = result_path(a.out, r[4], *r[1:4])
                if os.path.exists(p):
                    v = json.load(open(p))
                    msg = 'hit %.1fs' % v['hit_cpu'] if v['hit'] else 'no hit, tried %d' % v['tried']
                else:
                    msg = 'FAILED %d: %s' % (r[0].returncode, text.strip().splitlines()[-1][:200] if text.strip() else '')
                el = time.time() - t0
                print('[%d/%d %ds eta %ds] %s %s %s %s: %s' % (done, n, el, el / done * (n - done), r[1], r[2], r[3], r[4], msg), flush=True)


def report(a):
    rows = collections.defaultdict(dict)
    for arm in ARMS:
        d = os.path.join(a.out, arm)
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else ():
            if f.endswith('.json'):
                v = json.load(open(os.path.join(d, f)))
                rows[(v['task'], v['case'], tuple(v['point']))][arm] = v
    both = {k: v for k, v in rows.items() if len(v) == 2}
    print('%d points with both arms (%d with one)' % (len(both), len(rows) - len(both)))
    if not both:
        return
    for arm in ARMS:
        vs = [v[arm] for v in both.values()]
        row = ['%s' % arm]
        for t in (15, 30, 60):
            if t <= a.budget:
                row.append('hit by %ds: %d/%d' % (t, sum(x['hit'] and x['hit_cpu'] <= t for x in vs), len(vs)))
        cpu = sum(x['cpu'] for x in vs)
        row.append('clauses tried per CPU s: %.1f' % (sum(x['tried'] for x in vs) / max(cpu, 1e-9)))
        row.append('distinct clauses per CPU s: %.1f' % (sum(x['distinct'] for x in vs) / max(cpu, 1e-9)))
        row.append('peak RSS MiB: %d' % max(x['maxrss_mib'] for x in vs))
        print('  '.join(row))
    hit = [v for v in both.values() if v['draw']['hit'] and v['search']['hit']]
    if hit:
        print('points both hit: %d, median CPU draw %.1fs search %.1fs, median search/draw %.2f' % (
            len(hit), statistics.median(v['draw']['hit_cpu'] for v in hit), statistics.median(v['search']['hit_cpu'] for v in hit),
            statistics.median(v['search']['hit_cpu'] / v['draw']['hit_cpu'] for v in hit)))
    only = [(k, 'draw' if v['draw']['hit'] else 'search') for k, v in both.items() if v['draw']['hit'] != v['search']['hit']]
    print('only one hit: %d (%s)' % (len(only), ', '.join('%s %s' % (k[0], w) for k, w in only)))
    for k, v in sorted(both.items()):
        f = lambda x: '%6.1f' % x['hit_cpu'] if x['hit'] else '    --'  # noqa: E731
        print('  %s %-14s %-9s draw %s  search %s (generated at %s)  setup %.1fs' % (k[0], k[1][:14], k[2], f(v['draw']), f(v['search']), v['search'].get('gen_cpu'), v['draw']['setup_cpu']))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['run', 'report', 'job'])
    ap.add_argument('args', nargs='*')
    ap.add_argument('--stems', default=STEMS)
    ap.add_argument('--out', default=OUT)
    ap.add_argument('--budget', type=float, default=60)
    ap.add_argument('--jobs', type=int, default=2)
    ap.add_argument('--limit', type=int, default=None)
    ap.add_argument('--every', type=int, default=1)
    ap.add_argument('--job-timeout', type=int, default=None)
    a = ap.parse_args()
    a.job_timeout = a.job_timeout or int(2 * a.budget + 60)
    if a.cmd == 'job':
        task, case, point, arm = a.args
        r = job(task, case, json.loads(point), arm, a.out, a.budget)
        print(task, case, point, arm, 'hit' if r['hit'] else 'no hit', r.get('hit_cpu'), 'cpu', r['cpu'], 'tried', r['tried'])
    elif a.cmd == 'run':
        run(a)
    else:
        report(a)


if __name__ == '__main__':
    main()
