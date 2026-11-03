#!/usr/bin/env python
"""Per task and arm, the pool observables at 60, 300 and 600 s. No gold reaches a no-gold column, and no test output is read.

  features_signal_rows.py cheap OUT.jsonl [--limit N]
  features_signal_rows.py tables OUT.jsonl K N [--limit N]

`cheap` reads events, done files and worker logs: nodes, forms, proposals, and forms covered as a reference column.
`tables` reads node records and adds best_out (the largest `gain` of outfeat.out_features over the nodes) and shape_forms (forms whose table has each train output's cells).
One line per task and arm; a rerun skips finished items and prints a rate and an ETA.

How a pool is cut at S seconds:
- Flat runs (job 23, the gate arms): a visit event gives seconds, tries, new. Take the visits with seconds <= S. Their tries sum to D and their new sum to the forms. A node is in the cut when tags.draw <= D.
- Worker logs (the 3,600 s runs, the soak, Kaggle version 5): a line `rss ... at T s of B` counts T from the start of its generation, and B is the time left at that start, so the run's clock is B0 - B + T. Take the last line at or before S, which gives samples, forms and nodes. Log lines come about every 12 s. A node is in the cut when it is among the first `nodes` nodes of the task's records, in record order.
"""
import collections
import glob
import itertools
import json
import os
import re
import subprocess
import sys
import time

CUTS = 60, 300, 600
MAIN = '/Users/davidlu/code/arc-workspace/'
W = MAIN + 'work/'
RUNS = W + 'lm/data-study/sampler/search-worker/runs/'
JOB23 = RUNS + 'search-pool-factored-priors-heldout35-600s-ship7/'
GATE = RUNS + 'search-pool-gate-steers-out-heldout37-600s-c87cf482a/'
CTX = RUNS + 'search-pool-context-cover-vs-control-heldout37-3600s-c87cf482a/out/'
JOB17 = RUNS + 'search-pool-vs-sampling-heldout37-3600s-ship7/'
SOAK = W + 'synth-kaggle/kernel-soak-8a5ffec6-linux-23eval-23training-1800s/'
V5 = W + 'lm/data-study/sampler/runs/kaggle-v5/'
sys.path.insert(0, W + 'synth-kaggle/policy1')
from nodefeat import Pair  # noqa: E402
from outfeat import out_features, table  # noqa: E402

HEAD = re.compile(r'&[A-Za-z_0-9]+')
RSS = re.compile(r'^rss \d+ at (\d+) s of (\d+),(?: cpu (\d+) s,)? (\d+) samples, [\d.]+ samples/s, (\d+) forms, (\d+) nodes, generation (\d+)')
END = re.compile(r'^end: (\S+), (\d+) draws, (\d+) forms, (\d+) nodes, (\d+) candidates, (\d+) MiB, (\d+) s')


def items():
    """(run, arm, task, kind, paths) of every record."""
    out = []
    for run, base, arms in (('job23', JOB23, ('control_search', 'factored_search')), ('gate', GATE, ('control_search', 'gate_search'))):
        for arm in arms:
            for f in sorted(glob.glob(base + arm + '/*.done.json')):
                t = os.path.basename(f)[:8]
                out.append((run, arm, t, 'flat', dict(base=base + arm + '/' + t)))
            for f in sorted(glob.glob(base + arm + '/*.events.jsonl')):
                t = os.path.basename(f)[:8]
                if not os.path.exists(base + arm + '/' + t + '.done.json'):
                    out.append((run, arm, t, 'flat', dict(base=base + arm + '/' + t)))
    for run, base, arms in (('context', CTX, ('control', 'context_cover')), ('job17', JOB17, ('search', 'draws'))):
        for arm in arms:
            for e in sorted(os.scandir(base + arm), key=lambda e: e.name):
                out.append((run, arm, e.name, 'log', dict(log=f'{e.path}/work/{e.name}.log', cover=f'{e.path}/work/{e.name}.out.jsonl.cover', start=e.path + '/start', sup=e.path + '/supervisor.log')))
    for x in json.load(open(SOAK + 'manifest.json'))['task_set']:
        t, arm = x.split('.')
        out.append(('soak', arm, t, 'log', dict(log=f'{SOAK}work-logs/{x}.log', record=sorted(glob.glob(f'{SOAK}record/{x}.task.json.*.nodes.jsonl.zst'), key=gen_key))))
    for f in sorted(glob.glob(V5 + 'work/*.log')):
        t = os.path.basename(f)[:8]
        out.append(('kaggle-v5', 'draws', t, 'log', dict(log=f, record=sorted(glob.glob(f'{V5}record/{t}.task.json.*.nodes.jsonl.zst'), key=gen_key))))
    return out


def gen_key(p):
    m = re.search(r'\.task\.json\.(\d+)', p)
    return int(m[1]), p


def flat_cheap(base):
    ev = []
    for l in open(base + '.events.jsonl'):
        try:
            ev.append(json.loads(l))
        except ValueError:
            pass
    done = json.load(open(base + '.done.json')) if os.path.exists(base + '.done.json') else None
    vis = [e for e in ev if e['event'] == 'visit']
    cuts = {}
    for S in CUTS:
        v = [e for e in vis if e['seconds'] <= S]
        cuts[S] = dict(proposals=sum(e['tries'] for e in v), forms=sum(e['new'] for e in v), covered=len({e['gold'] for e in ev if e['event'] == 'cover' and e['seconds'] <= S}))
    end = done['seconds'] if done else (vis[-1]['seconds'] if vis else 0)
    c = (done or {}).get('counts', {})
    state = 'no done file' if done is None else 'deadline' if c.get('search:end deadline') or done['seconds'] >= 590 else 'ended early'
    return dict(cuts=cuts, end_seconds=end, end_state=state, cpu_seconds=c.get('cpu seconds grow'), gold_forms=(done or {}).get('gold'), peak_rss=(done or {}).get('peak_rss_mib'))


def log_cheap(p):
    L = []; ends = []; gens = 0; b0 = None
    for line in open(p['log'], errors='replace'):
        m = RSS.match(line)
        if m:
            b0 = b0 if b0 is not None else int(m[2])
            # `at T` counts from the generation's start and `of B` is the time left at that start, so the run's clock is b0 - B + T.
            L.append((b0 - int(m[2]) + int(m[1]), int(m[3]) if m[3] else None, int(m[4]), int(m[5]), int(m[6]), int(m[7])))
            gens = max(gens, int(m[7]))
        m = END.match(line)
        if m:
            ends.append((m[1], int(m[7])))
    cuts = {}
    for S in CUTS:
        v = [x for x in L if x[0] <= S]
        cuts[S] = dict(log_seconds=v[-1][0], cpu=v[-1][1], proposals=v[-1][2], forms=v[-1][3], nodes=v[-1][4]) if v else dict(log_seconds=None, cpu=None, proposals=0, forms=0, nodes=0)
    last = L[-1][0] if L else 0
    out = dict(cuts=cuts, end_seconds=last, budget=b0, generations=gens + 1, end_state=(ends[-1][0] or 'None') if len(ends) == gens + 1 else 'no end line in last generation', cpu_seconds=L[-1][1] if L else None)
    if os.path.exists(p.get('cover', '')):
        t0 = int(open(p['start']).read().split()[0])
        cov = [json.loads(l) for l in open(p['cover']) if l.strip()]
        for S in CUTS:
            cuts[S]['covered'] = len({c['gold'] for c in cov if c['time'] - t0 <= S})
    if 'sup' in p and os.path.exists(p['sup']):
        s = open(p['sup'], errors='replace').read()
        st = re.findall(r'deaths (\d+), kills (\d+)', s)
        if st:
            out['deaths'], out['kills'] = int(st[-1][0]), int(st[-1][1])
    return out


def has_shape(types, tab, pairs):
    """True when one Position column gives, on each train pair, exactly the cells of that pair's output grid."""
    if any(e not in tab for e in range(len(pairs))):
        return False
    for pi in (i for i, t in enumerate(types) if t == 'Position'):
        for e, p in enumerate(pairs):
            H, W_ = len(p.b), len(p.b[0])
            rows = tab[e]
            if len(rows) < H * W_:
                break
            S = {(r[pi][0], r[pi][2]) for r in rows}
            if len(S) != H * W_ or any(not (0 <= i < H and 0 <= j < W_) for i, j in S):
                break
        else:
            return True
    return False


def records(paths):
    for f in paths:
        p = subprocess.Popen(['zstd', '-dcq', f], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        for raw in p.stdout:
            try:
                yield json.loads(raw)
            except ValueError:
                continue
        p.wait()


def task_pairs(t):
    d = json.load(open(f'{MAIN}data/tasks/{t}.json'))
    return [Pair(x['input'], x['output']) for x in d['train']]


def tables(run, kind, p, t, cheap):
    pairs = task_pairs(t)
    cheap_cuts = cheap['cuts']
    if kind == 'flat':
        paths = [p['base'] + '.nodes.jsonl.zst']
    else:
        paths = p['record']
    best = None; shape = set(); seen = set(); n = 0; out = {}
    # A flat run cuts by draw, a log run by node count. Records are in creation order, so the scan stops past the last cut.
    limit = {S: cheap_cuts[str(S)]['proposals'] if kind == 'flat' else cheap_cuts[str(S)]['nodes'] for S in CUTS}
    todo = list(CUTS)

    def close(S):
        out[S] = dict(best_out=best, shape_forms=len(shape), table_nodes=n, table_forms=len(seen))

    capped = 0
    for r in records(paths):
        k = r['tags'].get('draw') if kind == 'flat' else n + 1
        k = k if k is not None else 0
        while todo and k > limit[todo[0]]:
            close(todo.pop(0))
        if not todo:
            break
        n += 1
        head = HEAD.search(r.get('clause') or '')
        h = head[0] if head else r['token']
        seen.add(h)
        d, s = out_features(r, pairs)
        if s['gain'] is not None and (best is None or s['gain'] > best):
            best = s['gain']
        types, tab = table(r, pairs)
        if h not in shape and has_shape(types, tab, pairs):
            shape.add(h)
    while todo:
        close(todo.pop(0))
    return out


def main():
    mode, out = sys.argv[1], sys.argv[2]
    lim = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else None
    rows = items()
    done = set()
    if os.path.exists(out):
        for l in open(out):
            r = json.loads(l)
            done.add((r['run'], r['arm'], r['task']))
    if mode == 'cheap':
        todo = rows
    else:
        K, N = int(sys.argv[3]), int(sys.argv[4])
        cheap = {(r['run'], r['arm'], r['task']): r for r in map(json.loads, open(os.path.dirname(os.path.abspath(out)) + '/signal-cheap.jsonl'))}
        todo = [x for x in rows if x[0] in ('job23', 'gate', 'soak', 'kaggle-v5')][K::N]
    todo = [x for x in todo if (x[0], x[1], x[2]) not in done]
    if lim:
        todo = todo[:lim]
    t0 = time.time()
    with open(out, 'a') as f:
        for i, (run, arm, t, kind, p) in enumerate(todo, 1):
            t1 = time.time()
            try:
                if mode == 'cheap':
                    r = flat_cheap(p['base']) if kind == 'flat' else log_cheap(p)
                else:
                    r = dict(cuts=tables(run, kind, p, t, cheap[run, arm, t]))
            except Exception as e:  # noqa: BLE001
                r = dict(error=repr(e)[:200])
            r.update(run=run, arm=arm, task=t, machine_read=kind)
            f.write(json.dumps(r) + '\n')
            f.flush()
            rate = i / (time.time() - t0)
            print(run, arm, t, kind, f'{time.time() - t1:.1f} s', r.get('error', ''), f'{i}/{len(todo)} {rate:.2f}/s ETA {(len(todo) - i) / rate:.0f} s', flush=True)


if __name__ == '__main__':
    main()
