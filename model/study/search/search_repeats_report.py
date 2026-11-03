#!/usr/bin/env python
"""Counts of repeat proposals in the pool search, from run records. No job runs.

    <python with zstandard> search_repeats_report.py RUNS_FOLDER [section ...] [--points=KIT/points-eval.json]

RUNS_FOLDER is work/lm/data-study/sampler/search-worker/runs. With no section, all sections print. Sections are the keys of SECTIONS at the end of this file.
With --points, a last section reads the right cell. With REPEATS_CACHE set to a folder, the Searches that the sections read stay there, so a second call takes seconds. No job runs.

A proposal is one clause that the search gives to try_clause: one `draws`. Each share is over proposals.
"""
import collections
import glob
import io
import json
import os
import pickle
import re
import sys

import numpy as np
import zstandard

S_LOW, S_MID, S_HIGH = 0.23, 0.47, 0.76  # same-clause share of equal: the low and middle of section split, and the ceiling of section rankmatch
END_MS = 6.0  # the END table: the mean step_tables call of section costs
MEMO_LEAF_MS, MEMO_STOP_MS = 0.0002, 0.01  # a set lookup, and that with the rename of &r names at a stop: reckoned, not measured
MEM = 'search-memory-fixes-heldout37-2seeds-600s-c87cf482a'
EVICT = 'search-evict-heldout37-2seeds-600s-c87cf482a'
GATE = 'search-pool-gate-steers-out-heldout37-600s-c87cf482a'
SIDES = 'search-rate-sides-6tasks-600s-c87cf482a'
FORM = re.compile(r'&f(\d+)')


def pct(a, b):
    return '%.1f%%' % (100 * a / b) if b else '-'


def table(head, rows):
    print('| ' + ' | '.join(head) + ' |')
    print('|' + '---|' * len(head))
    for r in rows:
        print('| ' + ' | '.join(str(x) for x in r) + ' |')
    print()


def job_logs(run):
    """{(arm, task): log path} of a worker run."""
    got = {}
    for p in glob.glob('%s/out/*/*/work/*.log' % run):
        parts = p.split('/')
        got[parts[-4], parts[-3]] = p
    return got


def prof_lines(path):
    out, gen = [], None
    with open(path, errors='replace') as f:
        for line in f:
            if line.startswith('prof '):
                try:
                    out.append(json.loads(line[5:]))
                except ValueError:
                    pass
    return out


def job_totals(path):
    """Sums of one job: a process's `equal` and `notable` start at 0 in each process, and `draws`, `forms` and `dup` carry over in the bank. `cpu` carries over at an execv and restarts in a new
    worker. The tail after a process's last prof line is not in the counts."""
    rows = prof_lines(path)
    if not rows:
        return None
    t = collections.Counter()
    t['gens'] = len({(r['gen']) for r in rows})
    by = []
    for r in rows:
        if by and r['gen'] == by[-1][-1]['gen'] and r['cpu'] >= by[-1][-1]['cpu'] and r['draws'] >= by[-1][-1]['draws']:
            by[-1].append(r)
        else:
            by.append([r])
    cpu = 0.0
    for i, g in enumerate(by):
        last = g[-1]
        t['equal'] += last.get('equal', 0)
        t['notable'] += last.get('notable', 0)
        if i and last['cpu'] < by[i - 1][-1]['cpu']:
            cpu += by[i - 1][-1]['cpu']
    last = rows[-1]
    t['cpu'] = cpu + last['cpu']
    t['draws'], t['forms'], t['nodes'], t['dup'], t['same'] = last['draws'], last['forms'], last['nodes'], last.get('dup', 0), last.get('same', 0)
    t['visits'] = sum(g[-1]['visits'] for g in by)
    for k in ('setup', 'nxt', 'take', 'test'):
        t[k] = sum(g[-1][k] for g in by)
    return t


def worker_arms(run):
    arms = collections.defaultdict(collections.Counter)
    for (arm, task), p in sorted(job_logs(run).items()):
        t = job_totals(p)
        if t:
            arms[arm].update(t)
            arms[arm]['jobs'] += 1
    return arms


def direct_arm(folder):
    """The sums of the done files of an arm, and the number of files read."""
    t, n, tasks = collections.Counter(), 0, {}
    for f in sorted(glob.glob(folder + '/*.done.json')):
        try:
            j = json.load(open(f))
        except ValueError:
            continue
        n += 1
        tasks[os.path.basename(f).split('.')[0]] = j
        for k, v in j['counts'].items():
            if isinstance(v, (int, float)):
                t[k] += v
        t['forms'] += j['forms']
        t['covered'] += j['covered']
        t['gold'] += j['gold']
    t['kept'] = sum(v for k, v in t.items() if k.startswith('kept:'))
    return t, n, tasks


def nodes_of(path):
    """Each record of a nodes file."""
    with open(path, 'rb') as f:
        for line in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f), encoding='utf-8', errors='replace'):
            try:
                yield json.loads(line)
            except ValueError:
                return


def events_of(path):
    with open(path) as f:
        for line in f:
            try:
                yield json.loads(line)
            except ValueError:
                return


def span_totals(run):
    """{arm: counts}, summed over spans: a span is the stretch between neighbouring prof lines of one process, so draws and equal cover one stretch. The stretch before a process's first prof
    line and after its last are out."""
    arms = collections.defaultdict(collections.Counter)
    for (arm, task), p in sorted(job_logs(run).items()):
        if arm.startswith('probe'):
            continue
        arms[arm]['jobs'] += 1
        prev = None
        for r in prof_lines(p):
            if prev is not None and r['gen'] == prev['gen'] and r['t'] > prev['t'] and r['draws'] >= prev['draws'] and r['cpu'] >= prev['cpu']:
                c = arms[arm]
                for k in ('draws', 'forms', 'equal', 'notable', 'dup'):
                    c[k] += r.get(k, 0) - prev.get(k, 0)
                c['cpu'] += r['cpu'] - prev['cpu']
                for k in ('setup', 'nxt', 'take', 'test'):
                    c[k] += r[k] - prev[k]
            prev = r
    return arms


def s_shares(R):
    print('## Outcome of a proposal, worker path\n')
    print('Run %s: 37 held-out tasks, seeds 1 and 101, 600 s wall, 148 jobs, EPYC 9654 pods, wheel c87cf482a. `new` is forms less dup, dup is a repeat of a table an older process had, `failed` is the remainder of draws. Sums over spans between prof lines.\n' % MEM)
    arms = span_totals(R + '/' + MEM)
    rows = []
    for arm in ('base_s1', 'base_s101', 'both_s1', 'both_s101'):
        t = arms[arm]
        new = t['forms'] - t['dup']
        failed = t['draws'] - t['forms'] - t['equal'] - t['notable']
        rows.append((arm, t['jobs'], t['draws'], '%.0f' % t['cpu'], '%.2f' % (t['draws'] / t['cpu']), pct(new, t['draws']), pct(t['dup'], t['draws']), pct(t['equal'], t['draws']), pct(t['notable'], t['draws']), pct(failed, t['draws']),
                     pct(t['draws'] - new, t['draws']), '%.2f' % (new / t['cpu'])))
    table(['arm', 'jobs', 'proposals', 'CPU s', 'proposals/CPU s', 'new table', 'repeat, older process (dup)', 'repeat, this process (equal)', 'no table', 'failed', 'all not new', 'new/CPU s'], rows)
    b, o = collections.Counter(), collections.Counter()
    for arm in ('base_s1', 'base_s101'):
        b.update(arms[arm])
    for arm in ('both_s1', 'both_s101'):
        o.update(arms[arm])
    print('Pooled shares. base: new %s, dup %s, equal %s, no table %s, failed %s. both: new %s, dup %s, equal %s, no table %s, failed %s.\n' % (
        pct(b['forms'] - b['dup'], b['draws']), pct(b['dup'], b['draws']), pct(b['equal'], b['draws']), pct(b['notable'], b['draws']), pct(b['draws'] - b['forms'] - b['equal'] - b['notable'], b['draws']),
        pct(o['forms'] - o['dup'], o['draws']), pct(o['dup'], o['draws']), pct(o['equal'], o['draws']), pct(o['notable'], o['draws']), pct(o['draws'] - o['forms'] - o['equal'] - o['notable'], o['draws'])))
    print('A renewal moves repeats: base less both, dup +%.1f points, equal %.1f points, all not new %+.1f points.\n' % (
        100 * (b['dup'] / b['draws'] - o['dup'] / o['draws']), 100 * (b['equal'] / b['draws'] - o['equal'] / o['draws']), 100 * ((1 - (b['forms'] - b['dup']) / b['draws']) - (1 - (o['forms'] - o['dup']) / o['draws']))))
    return arms


def s_age(R):
    print('## The same shares by process age, both arms and base arms\n')
    rows = collections.defaultdict(collections.Counter)
    bands = [(0, 60), (60, 120), (120, 240), (240, 360), (360, 480), (480, 700)]
    for (arm, task), p in sorted(job_logs(R + '/' + MEM).items()):
        if arm.startswith('probe'):
            continue
        prev = None
        for r in prof_lines(p):
            if prev is not None and r['gen'] == prev['gen'] and r['t'] > prev['t'] and r['draws'] >= prev['draws']:
                band = next((b for b in bands if b[0] <= r['t'] < b[1]), None)
                if band:
                    c = rows[arm.split('_')[0], band]
                    for k in ('draws', 'forms', 'equal', 'notable', 'dup'):
                        c[k] += r.get(k, 0) - prev.get(k, 0)
                    c['cpu'] += r['cpu'] - prev['cpu']
            prev = r
    out = []
    for (arm, band), c in sorted(rows.items()):
        failed = c['draws'] - c['forms'] - c['equal'] - c['notable']
        out.append((arm, '%d-%d' % band, c['draws'], '%.0f' % c['cpu'], pct(c['forms'] - c['dup'], c['draws']), pct(c['dup'], c['draws']), pct(c['equal'], c['draws']), pct(c['notable'], c['draws']), pct(failed, c['draws'])))
    table(['arm', 'process age s', 'proposals', 'CPU s', 'new', 'dup', 'equal', 'no table', 'failed'], out)


def s_direct(R):
    print('## Direct arms: one process, no renewal, so `equal` is every repeat of a table\n')
    names = [
        ('%s/control_search' % GATE, '37, seed 0, 600 s, 3 cpu3g pods'),
        ('search-pool-vs-sampling-heldout37-600s-f257c002/long_search', '37, 600 s'),
        ('search-pool-read-pick-heldout37-300s-f257c002/d_search', '37, 300 s'),
        ('search-pool-context-size-pass-bars-heldout37-60s-f257c002/a_search', '37, 60 s, k 6'),
        ('search-pool-context-size-pass-bars-heldout37-60s-f257c002/a_k3', '37, 60 s, k 3'),
        ('search-pool-context-size-pass-bars-heldout37-60s-f257c002/a_k1', '37, 60 s, k 1'),
        ('search-pool-scope-k-heldout37-300s-ship7/k12plain1_search', '35 ended, 300 s, k 12'),
        ('search-pool-scope-k-heldout37-300s-ship7/k3plain1_search', '35 ended, 300 s, k 3'),
        ('search-pool-oracle-mixed-heldout37-300s-ship7/plain1_search', '35 ended, 300 s, k 6'),
        ('search-pool-oracle-context-heldout37-300s-ship7/oracle1_search', '35 ended, 300 s, gold scopes'),
    ]
    rows = []
    for name, note in names:
        t, n, _ = direct_arm(R + '/' + name)
        d = t['draws'] or 1
        free, reads = t['search:equal scope-free'], t['search:equal reads scope']
        rows.append((name.split('/')[-1], name.split('/')[0][12:40], note, d, pct(t['kept'], d), pct(t['node:equal'], d), pct(free, d), pct(reads, d), pct(free, free + reads), pct(t['node:no table'], d), pct(t['search:failed tries'], d)))
    table(['arm', 'run', 'tasks, budget', 'proposals', 'new', 'equal', 'equal, reads no scope form', 'equal, reads a scope form', 'scope-free share of equal', 'no table', 'failed'], rows)


def s_kinds(R):
    print('## By kind, control_search of %s: 37 held-out tasks, seed 0, 600 s wall, 3 cpu3g pods\n' % GATE)
    t, n, tasks = direct_arm(R + '/' + GATE + '/control_search')
    rows = []
    for k in ('INIT', 'RULE', 'DET'):
        e, kept = t['search:equal ' + k], t['kept:' + k]
        rows.append((k, kept, e, pct(e, e + kept), pct(e, t['node:equal'])))
    table(['kind', 'kept', 'equal', 'equal over equal + kept', 'share of equal'], rows)
    print('tasks %d, proposals %d, cpu seconds grow %.0f, new-scope visits %d, resume visits %d, ends: patience %d, seconds %d, exhausted %d\n' % (
        n, t['draws'], t['cpu seconds grow'], t['search:new scope'], t['search:resume'], t['search:end patience'], t['search:end seconds'], t['search:end exhausted']))


def s_within(R):
    print('## The same clause inside one Search\n')
    print('`Search.emitted` stops a repeat at the leaf, `search.dup clause`. `Run.seen` stops the path at the stop coin first, `search.dead:atoms`. Neither is a proposal. Cost is process seconds in `execute`.\n')
    rows = []
    for name in ('%s/control_search' % GATE, 'search-pool-vs-sampling-heldout37-600s-f257c002/long_search', 'search-pool-read-pick-heldout37-300s-f257c002/d_search', 'search-pool-context-size-pass-bars-heldout37-60s-f257c002/a_search'):
        t, n, _ = direct_arm(R + '/' + name)
        runs = t['search.runs'] or 1
        rows.append((name.split('/')[-1], n, t['search.runs'], t['search.clauses'], t['search.dead'], t['search.dup clause'], t['search.dead:atoms'], pct(t['search.dead:atoms'], runs), '%.1f' % (1000 * t['search.seconds dead:atoms'] / max(t['search.dead:atoms'], 1)),
                     pct(t['search.seconds dead:atoms'], t['search.seconds']), pct(t['search.seconds dead'], t['search.seconds']), '%.1f' % (1000 * t['search.seconds clause'] / max(t['search.clauses'], 1)), '%.1f' % (1000 * t['search.seconds dead'] / max(t['search.dead'], 1))))
    table(['arm', 'tasks', 'runs', 'clauses given', 'dead', 'dup clause', 'dead:atoms', 'dead:atoms over runs', 'ms per dead:atoms', 'its share of search seconds', 'all dead, share of search seconds', 'ms per run that gives a clause', 'ms per dead run'], rows)


def s_fails(R):
    print('## What fails, control_search of %s\n' % GATE)
    t, n, _ = direct_arm(R + '/' + GATE + '/control_search')
    d = t['draws']
    print('failed tries %d (%s of proposals), no table %d (%s). A failed try raises in Pool.take or Pool.test, `drop:table:` where the table has an entry that did not finish.\n' % (t['search:failed tries'], pct(t['search:failed tries'], d), t['node:no table'], pct(t['node:no table'], d)))
    rows = [(k, v, pct(v, t['search:failed tries'])) for k, v in sorted(t.items(), key=lambda x: -x[1]) if k.startswith(('drop:', 'error'))]
    table(['count', 'tries', 'share of failed tries'], rows[:14])
    p = R + '/search-pool-stop-kinds-heldout37-600s-c87cf482a/stop-kinds.txt'
    if os.path.exists(p):
        print('Stop kinds of tables, per 1,000 proposals, search-pool-stop-kinds-heldout37-600s-c87cf482a:\n')
        print('```')
        for line in open(p):
            if line.startswith(('tasks', 'table:')):
                print(line.rstrip())
        print('```\n')


def s_bars(R):
    print('## Arms that bar repeats: direct runs, 37 held-out tasks, each arm beside its control of one run\n')
    pairs = [
        ('search-pool-table-bar-heldout37-60s-3d796f2b', 'base_search', 'new_search', 'known-table check at the stop (SEARCH_NEW_TABLE), 60 s'),
        ('search-pool-table-bar-heldout37-60s-3d796f2b', 'base_search', 'newgate_search', 'that, with the kernel gate, 60 s'),
        ('search-pool-readscope-bar-heldout37-60s-3d796f2b', 'base_search', 'gate_search', 'read a scope form (SEARCH_READ_SCOPE), 60 s'),
        ('search-pool-read-pick-heldout37-300s-f257c002', 'd_search', 'd_pick', 'read a pick (SEARCH_READ_PICK), 300 s'),
        ('search-pool-context-size-pass-bars-heldout37-60s-f257c002', 'a_search', 'a_bars', 'both bars, a_bars, 60 s'),
    ]
    rows = []
    for run, a, b, note in pairs:
        for arm in (a, b):
            t, n, _ = direct_arm('%s/%s/%s' % (R, run, arm))
            d = t['draws'] or 1
            rows.append((note if arm == b else 'control of the row below', arm, n, d, t['kept'], pct(t['kept'], d), pct(t['node:equal'], d), pct(t['search:equal scope-free'], d), pct(t['search:equal reads scope'], d), pct(t['search:failed tries'], d), t['covered'], t['search:end patience'], t['search:visits'],
                         '%.0f' % t['sr:new table:stop barred'], '%.1f' % t['sr:new table:cpu'] if t['sr:new table:cpu'] else '-', t['new table:prefix key is a node'], t['new table:prefix key is no node'],
                         t['search:equal INIT'], t['search:equal RULE'], t['search:equal DET']))
    table(['arm note', 'arm', 'tasks', 'proposals', 'kept', 'new', 'equal', 'equal free', 'equal reads', 'failed', 'gold covered', 'patience ends', 'visits', 'stops barred', 'check CPU s', 'prefix key is a node', 'is no node', 'equal INIT', 'equal RULE', 'equal DET'], rows)


def s_evict(R):
    print('## The newest arms: %s\n' % EVICT)
    print('37 held-out tasks, seeds 1 and 101, 600 s wall, EPYC 9654 pods. `both` runs the kit wheel c87cf482a, `evict` the study wheel with evict.patch. Sums over spans between prof lines.\n')
    arms = span_totals(R + '/' + EVICT)
    rows = []
    for arm in sorted(arms):
        t = arms[arm]
        new = t['forms'] - t['dup']
        failed = t['draws'] - t['forms'] - t['equal'] - t['notable']
        d = t['draws']
        rows.append((arm, t['jobs'], d, '%.0f' % t['cpu'], '%.2f' % (d / t['cpu']), pct(new, d), pct(t['dup'], d), pct(t['equal'], d), pct(t['notable'], d), pct(failed, d), '%.2f' % (new / t['cpu']),
                     '%.0f' % (1000 * t['cpu'] / d), '%.1f' % (1000 * t['setup'] / d), '%.1f' % (1000 * t['nxt'] / d), '%.1f' % (1000 * (t['take'] - t['test']) / d), '%.1f' % (1000 * t['test'] / d)))
    table(['arm', 'jobs', 'proposals', 'CPU s', 'proposals/CPU s', 'new', 'dup', 'equal', 'no table', 'failed', 'new/CPU s', 'CPU ms/try', 'setup ms', 'nxt ms (wall)', 'take less test ms (wall)', 'test ms (wall)'], rows)
    return arms


def s_costs(R):
    print('## What a part of a try costs\n')
    print('Profile: `side_profile` of %s, 3 held-out tasks, seed 0, cProfile over the first 300 s, EPYC 9654 pod. Seconds are own time. Engine calls take cProfile\'s cost per call only.\n' % SIDES)
    rows, names = [], ("<built-in method arclog.arclog.step_tables>", "<method 'step' of 'arclog.Decoder' objects>", "<method 'admits' of 'arclog.Decoder' objects>", 'parse_table', 'body_table', 'close', 'table_key')
    sums = collections.defaultdict(lambda: [0.0, 0])
    per_task = {}
    for t in ('5961cc34', 'aa4ec2a5', 'dbff022c'):
        p = '%s/%s/out/side_profile/%s/work/%s.log' % (R, SIDES, t, t)
        top, draws, keep = None, 0, None
        for line in open(p, errors='replace'):
            if line.startswith('profile ') and top is None:
                top = json.loads(line[8:])['top']
                draws = keep
            elif line.startswith('prof ') and top is None:
                keep = json.loads(line[5:])['draws']
        per_task[t] = draws
        for sec, calls, side, name in top:
            if name in names:
                sums[name][0] += sec
                sums[name][1] += calls
    for name in names:
        s, c = sums[name]
        rows.append((name, '%.1f' % s, c, '%.2f' % (1000 * s / max(c, 1))))
    table(['call', 'seconds, 3 tasks', 'calls', 'ms per call'], rows)
    print('Proposals in the profiled 300 s: %s.\n' % per_task)
    t, n, _ = direct_arm(R + '/search-pool-table-bar-heldout37-60s-3d796f2b/new_search')
    print('Cost of a merge key at a stop: `new table:cpu` %.1f s over %d runs is %.2f ms per run, 37 tasks, 60 s, new_search, %.1f%% of 2,220 CPU s.\n' % (t['sr:new table:cpu'], t['search.runs'], 1000 * t['sr:new table:cpu'] / t['search.runs'], 100 * t['sr:new table:cpu'] / 2220))
    print('Digests on the worker path, `dig_s` over forms counted, from the last prof line of each job of %s:\n' % MEM)
    c = collections.Counter()
    for (arm, task), p in job_logs(R + '/' + MEM).items():
        rows_ = prof_lines(p)
        if rows_ and not arm.startswith('probe'):
            c[arm.split('_')[0] + ' s'] += rows_[-1].get('dig_s', 0)
            c[arm.split('_')[0] + ' forms'] += rows_[-1]['forms']
            c[arm.split('_')[0] + ' same'] += rows_[-1].get('same', 0)
            c[arm.split('_')[0] + ' dup'] += rows_[-1].get('dup', 0)
            c[arm.split('_')[0] + ' dig_failed'] += rows_[-1].get('dig_failed', 0)
    print('base %.3f ms per form, both %.3f ms per form; same %d and %d, dup %d and %d, failed %d and %d.\n' % (1000 * c['base s'] / c['base forms'], 1000 * c['both s'] / c['both forms'], c['base same'], c['both same'], c['base dup'], c['both dup'], c['base dig_failed'], c['both dig_failed']))


# ---------------------------------------------------------------- Searches, from visit events and kept clauses

def reads_of(text):
    """The numbers of the forms a clause reads: its &fN, less its head."""
    got = FORM.findall(text)
    return set(got[1:]) - {got[0]} if got else set()


LOADED = {}


def searches(R, name):
    """{task: (Searches in order of first visit, proposals, {node: form})}. Each Search has its scope, kind, tries, kept forms as (rank in the Search, draw, reads, clause), and its visits as
    (draws before it, tries, new). A kept form is the first node record of its draw. The reading takes about a minute a run; with REPEATS_CACHE set to a folder, it stays there."""
    if name in LOADED:
        return LOADED[name]
    cache = os.environ.get('REPEATS_CACHE')
    path = cache and '%s/%s.pkl' % (cache, name.replace('/', '_'))
    if path and os.path.exists(path):
        with open(path, 'rb') as f:
            LOADED[name] = pickle.load(f)
        return LOADED[name]
    out = {}
    folder = '%s/%s' % (R, name)
    for f in sorted(glob.glob(folder + '/*.events.jsonl')):
        task = os.path.basename(f).split('.')[0]
        forms, node_form = {}, {}
        for r in nodes_of('%s/%s.nodes.jsonl.zst' % (folder, task)):
            d = r['tags']['draw']
            head = FORM.search(r['clause'])
            if head:
                node_form[int(r['token'])] = int(head[1])
            if d not in forms:
                forms[d] = r['clause'], reads_of(r['clause'])
        slots, draw, covers = collections.OrderedDict(), 0, {}
        for e in events_of(f):
            if e.get('event') == 'cover':
                covers.setdefault(e['gold'], (e['node'], e['draw']))
            if e.get('event') != 'visit':
                continue
            key = tuple(e['fids']), e['kind']
            s = slots.get(key)
            if s is None:
                s = slots[key] = dict(fids=set(e['fids']), kind=e['kind'], tries=0, kept=[], first_draw=draw + 1, visits=[])
            for d in range(draw + 1, draw + e['tries'] + 1):
                if d in forms:
                    s['kept'].append((s['tries'] + d - draw, d, forms[d][1], forms[d][0]))
            s['visits'].append((draw, e['tries'], e['new']))
            s['tries'] += e['tries']
            draw += e['tries']
        out[task] = list(slots.values()), draw, node_form, covers
    LOADED[name] = out
    if path:
        os.makedirs(cache, exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump(out, f)
    return out


RUNS2 = (('search-pool-oracle-mixed-heldout37-300s-ship7/plain1_search', '37 held-out tasks (35 ended), 300 s wall, ship7, no table 2.5%'), ('%s/control_search' % GATE, '37 held-out tasks, seed 0, 600 s wall, 3 cpu3g pods, c87cf482a, no table 24.7%'))
BANDS = [(1, 4), (5, 8), (9, 16), (17, 32), (33, 64), (65, 128), (129, 10 ** 6)]


def half(d, draws):
    return 'first' if d <= draws / 2 else 'second'


def s_ranks(R):
    print('## Yield by rank in a Search\n')
    print('A first Search is the first Search of its kind in a task, with all its visits, so no earlier Search of the kind can have given its clauses. A later Search is any other. Yield is kept forms over tries. Past rank 8 a Search has passed patience, so those rows are a selected set. Run half is by the draw of the Search\'s first visit.\n')
    for name, note in RUNS2:
        print('`%s`, %s.\n' % (name, note))
        rows = collections.defaultdict(collections.Counter)
        for task, (slots, draws, _, _) in searches(R, name).items():
            seen = set()
            for s in slots:
                what = 'later' if s['kind'] in seen else 'first'
                seen.add(s['kind'])
                kept, free = collections.Counter(), collections.Counter()
                for r, d, reads, text in s['kept']:
                    b = next(x for x in BANDS if x[0] <= r <= x[1])
                    kept[b] += 1
                    free[b] += not reads
                for b in BANDS:
                    if s['tries'] >= b[0]:
                        c = rows[what, half(s['first_draw'], draws), b]
                        c['tries'] += min(s['tries'], b[1]) - b[0] + 1
                        c['kept'] += kept[b]
                        c['free'] += free[b]
        table(['Search', 'run half', 'rank', 'tries', 'kept', 'yield', 'kept that read no scope form'],
              [(w, a, '%d-%d' % b if b[1] < 10 ** 6 else '%d+' % b[0], c['tries'], c['kept'], '%.3f' % (c['kept'] / c['tries']), pct(c['free'], c['kept'])) for (w, a, b), c in sorted(rows.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])) if c['tries']])


def fresh_count(R, name):
    """Kept forms by what they read: nothing, a form no earlier same-kind scope held, or only forms some earlier same-kind scope held."""
    c = collections.Counter()
    for task, (slots, draws, _, _) in searches(R, name).items():
        held = collections.defaultdict(set)
        for s in slots:
            for r, d, reads, text in s['kept']:
                ids = {int(x) for x in reads}
                c['free' if not ids else 'reads a fresh form' if ids - held[s['kind']] else 'reads old forms only'] += 1
            held[s['kind']] |= s['fids']
    return c


def split_inputs(R, name):
    """Counts for the bounds: kept and tries of first and later Searches."""
    t, n, _ = direct_arm('%s/%s' % (R, name))
    c = collections.Counter()
    for task, (slots, draws, _, _) in searches(R, name).items():
        seen = set()
        for s in slots:
            w = 'later ' if s['kind'] in seen else 'first '
            seen.add(s['kind'])
            c[w + 'tries'] += s['tries']
            for r, d, reads, text in s['kept']:
                c[w + ('kept reads' if reads else 'kept free')] += 1
    return t, c


def pairs_of(R, name, scales):
    """{scale: Counter}. A pair is a kept clause of an earlier same-kind Search and a later Search whose scope holds the clause's read forms, where the rank of the clause in its Search, times the
    scale, is within the tries of the later Search. So a pair is a place where the later Search may give that clause again."""
    res = collections.defaultdict(collections.Counter)
    for task, (slots, draws, _, _) in searches(R, name).items():
        seen = collections.defaultdict(list)
        for s in slots:
            for a in seen[s['kind']]:
                for r, d, reads, text in a['kept']:
                    if d < s['first_draw'] and all(int(x) in s['fids'] for x in reads):
                        for lam in scales:
                            if r * lam <= s['tries']:
                                res[lam]['reads' if reads else 'free'] += 1
            seen[s['kind']].append(s)
    return res


def same_of(p, kept, tried):
    """Same-clause repeats among `tried` tries that keep `kept`, where `p` is the pairs: a repeat of a kept clause is p, and the distinct clauses are tried less the repeats, each as likely to repeat
    as a kept one: same = p x tried / (kept + p)."""
    return p * tried / (kept + p) if kept + p else 0.0


def s_split(R):
    print('## Same clause against different clause, inside equal\n')
    print('No record has the text of an equal try, so this section bounds the split. Inside one Search no clause repeats, so in a first Search every equal is a different clause. y is the yield on clauses seen for the first time. Distinct clauses are kept / y, and same-clause repeats are tries less distinct, on tries that finished (kept + equal).\n')
    print('The rows take y at the first-Search yield and at two lower figures. Section rankmatch gives the higher y of the ranks that later Searches try. The smallest y on reads-scope clauses is kept over tries, which is no same-clause repeat at all.\n')
    out = {}
    for name, note in RUNS2:
        t, c = split_inputs(R, name)
        fe, re_ = t['search:equal scope-free'], t['search:equal reads scope']
        kf, kr = c['first kept free'] + c['later kept free'], c['first kept reads'] + c['later kept reads']
        y1 = (c['first kept free'] + c['first kept reads']) / c['first tries']
        nf, nr = fe + kf, re_ + kr
        print('`%s`, %s. Equal free %d, equal reads %d, kept free %d, kept reads %d, first-Search yield %.3f. A scope-free try after the first Search yields at most %.3f (%d kept in %d).\n' % (name, note, fe, re_, kf, kr, y1, c['later kept free'] / (fe + c['later kept free']), c['later kept free'], fe + c['later kept free']))
        print('Kept forms by what they read: %s.\n' % dict(fresh_count(R, name)))
        rows = []
        for y in (y1, 0.4, 0.3):
            sf, sr = nf - kf / y, max(nr - kr / y, 0)
            rows.append(('%.3f' % y, '%.0f' % sf, pct(sf, fe), '%.0f' % sr, pct(sr, re_), pct(sf + sr, fe + re_)))
        table(['y', 'same clause, free', 'of free equal', 'same clause, reads', 'of reads equal', 'same clause, of equal'], rows)
        scales = (1, 2, 3, 5, 8, 12)
        pr = pairs_of(R, name, scales)
        print('Pair count, a model: a kept clause may come again in a later Search that holds its reads. The rank scale says how much later it sits there. The share on free clauses, whose repeats are bounded above, picks the scale.\n')
        table(['rank scale', 'pairs free', 'pairs reads', 'same free, model', 'of free equal', 'same reads, model', 'of reads equal'],
              [(lam, pr[lam]['free'], pr[lam]['reads'], '%.0f' % same_of(pr[lam]['free'], kf, nf), pct(same_of(pr[lam]['free'], kf, nf), fe), '%.0f' % same_of(pr[lam]['reads'], kr, nr), pct(same_of(pr[lam]['reads'], kr, nr), re_)) for lam in scales])
    print('Read-pick arms, `search-pool-read-pick-heldout37-300s-f257c002`, 37 held-out tasks, 300 s. A clause in d_pick must read a pick, so scope overlap gives it fewer repeats, and its yield is near y of a clause that reads a form.\n')
    run = R + '/search-pool-read-pick-heldout37-300s-f257c002/'
    ys = {}
    rows = []
    for arm in ('d_search', 'd_pick'):
        c = collections.Counter()
        for f in glob.glob(run + arm + '/*.nodes.jsonl.zst'):
            seen = set()
            for r in nodes_of(f):
                d = r['tags']['draw']
                if d not in seen:
                    seen.add(d)
                    if not r['tags'].get('seeded'):
                        c['kept'] += 1
                        c['free'] += not reads_of(r['clause'])
        t, n, _ = direct_arm(run + arm)
        kr = c['kept'] - c['free']
        ys[arm] = kr, t['search:equal reads scope']
        rows.append((arm, kr, t['search:equal reads scope'], '%.3f' % (kr / (kr + t['search:equal reads scope'])), t['search.dead:reads no pick'], '%.0f' % t['search.seconds dead:reads no pick'], '%.0f' % t['search.seconds']))
    table(['arm', 'kept that read a form', 'equal that read a form', 'yield', 'runs ended, reads no pick', 'their seconds', 'search seconds'], rows)
    kr, re_ = ys['d_search']
    y = ys['d_pick'][0] / sum(ys['d_pick'])
    print('At y %.3f, d_search has %.0f same-clause repeats among reads-scope clauses, %s of its reads equal. d_pick still repeats where a pick comes twice, so the true y is above this, and this share is a lower bound.\n' % (y, kr + re_ - kr / y, pct(kr + re_ - kr / y, re_)))


def s_visits(R):
    print('## Visits\n')
    print('A resume goes on with a Search; the policy\'s pick opens a new one. An eight-and-out visit has 8 tries and no new form. Run half is by the draw at the visit\'s start.\n')
    for name, note in RUNS2:
        print('`%s`, %s.\n' % (name, note))
        rows = collections.defaultdict(collections.Counter)
        total, sc = 0, 0
        for task, (slots, draws, _, _) in searches(R, name).items():
            sc += len(slots)
            for s in slots:
                for i, (d0, tries, new) in enumerate(s['visits']):
                    c = rows['resume' if i else 'new Search', half(d0, draws)]
                    c['visits'] += 1
                    c['tries'] += tries
                    c['new'] += new
                    if tries == 8 and new == 0:
                        c['out'] += 1
                        c['out tries'] += 8
                    total += tries
        table(['visit', 'run half', 'visits', 'tries', 'new', 'yield', 'tries/visit', 'eight-and-out visits', 'their share of all tries'], [(w, a, c['visits'], c['tries'], c['new'], '%.3f' % (c['new'] / c['tries']), '%.1f' % (c['tries'] / c['visits']), c['out'], pct(c['out tries'], total)) for (w, a), c in sorted(rows.items())])
        print('Searches %d. Visits with an equal scope and kind are one Search, so a pick that lands on an old Search is a resume here.\n' % sc)


def s_right(R, points):
    print('## The right cell, from visits\n')
    print('A visit is in the right cell where, at its start, some gold form with one read or more is not yet covered, all its read forms have a covered node, the visit has that form\'s kind, and the scope holds the forms of those nodes. Cover events give a gold form\'s node. A gold form whose table equals an earlier one has no cover event of its own, so its readers are left out. Gold is points-eval.json of the kit.\n')
    gold = {x['task']: x['gold_sexp'] for x in json.load(open(points))}
    name_re = re.compile(r'&[A-Za-z_]\w*')
    for name, note in RUNS2:
        print('`%s`, %s.\n' % (name, note))
        rows = collections.defaultdict(collections.Counter)
        for task, (slots, draws, node_form, covers) in searches(R, name).items():
            lines = [x for x in gold[task].strip().split('\n') if not x.startswith('(OUT')]
            heads = [x.split()[1].split('.')[0] for x in lines]
            kinds = [x[1:x.index(' ')] for x in lines]
            index = {}
            wants = []
            for i, x in enumerate(lines):
                rd = {index[m] for m in name_re.findall(x) if m in index and m != heads[i]}
                index[heads[i]] = i
                if rd:
                    wants.append((i, kinds[i], rd))
            for s in slots:
                held = 0
                for j, (d0, tries, new) in enumerate(s['visits']):
                    ok = False
                    for i, k, rd in wants:
                        if k != s['kind'] or (i in covers and covers[i][1] <= d0) or not all(r in covers and covers[r][1] <= d0 for r in rd):
                            continue
                        if all(node_form.get(covers[r][0]) in s['fids'] for r in rd):
                            ok = True
                            break
                    c = rows['right cell' if ok else 'other visits', 'new Search' if not j else 'resume']
                    c['visits'] += 1
                    c['tries'] += tries
                    c['new'] += new
                    c['first eight'] += min(tries, 8)
        table(['cell', 'visit', 'visits', 'tries', 'new', 'not new', 'tries/visit'], [(a, b, c['visits'], c['tries'], c['new'], pct(c['tries'] - c['new'], c['tries']), '%.1f' % (c['tries'] / c['visits'])) for (a, b), c in sorted(rows.items())])


def s_textlen(R):
    print('## Clause text past 300 characters, for SEARCH_TRACE=2, which prints the first 300\n')
    c = collections.Counter()
    for f in sorted(glob.glob('%s/%s/control_search/*.nodes.jsonl.zst' % (R, GATE))):
        seen = set()
        for r in nodes_of(f):
            d = r['tags']['draw']
            if d not in seen:
                seen.add(d)
                k = r['clause'][1:r['clause'].index(' ')]
                c[k] += 1
                c[k + ' long'] += len(r['clause']) > 300
    print({k: pct(c[k + ' long'], c[k]) for k in ('INIT', 'RULE', 'DET')}, '\n')


def s_catch(R):
    print('## What the known-table check caught, by kind, table-bar arms, 37 held-out tasks, 60 s\n')
    b, _, _ = direct_arm(R + '/search-pool-table-bar-heldout37-60s-3d796f2b/base_search')
    n, _, _ = direct_arm(R + '/search-pool-table-bar-heldout37-60s-3d796f2b/new_search')
    rows = []
    for k in ('INIT', 'RULE', 'DET'):
        x, y = b['search:equal ' + k] / b['kept:' + k], n['search:equal ' + k] / n['kept:' + k]
        rows.append((k, b['kept:' + k], b['search:equal ' + k], '%.3f' % x, n['kept:' + k], n['search:equal ' + k], '%.3f' % y, '%.1f%%' % (100 * (1 - y / x))))
    table(['kind', 'kept, base', 'equal, base', 'equal per kept, base', 'kept, new_search', 'equal, new_search', 'equal per kept, new_search', 'caught'], rows)
    print('ms per proposal, wall: search:seconds next %.0f and %.0f, take %.0f and %.0f; runs per proposal %.2f and %.2f; ms per dead run %.1f and %.1f; dead share of search seconds %s and %s; ms per run that gives a clause %.1f and %.1f.\n' % (
        1000 * b['search:seconds next'] / b['draws'], 1000 * n['search:seconds next'] / n['draws'], 1000 * b['search:seconds take'] / b['draws'], 1000 * n['search:seconds take'] / n['draws'], b['search.runs'] / b['draws'], n['search.runs'] / n['draws'],
        1000 * b['search.seconds dead'] / b['search.dead'], 1000 * n['search.seconds dead'] / n['search.dead'], pct(b['search.seconds dead'], b['search.seconds']), pct(n['search.seconds dead'], n['search.seconds']), 1000 * b['search.seconds clause'] / b['search.clauses'], 1000 * n['search.seconds clause'] / n['search.clauses']))


def s_rankmatch(R):
    print('## y at the ranks later Searches try\n')
    print('A later Search tries mostly top ranks, where a first Search yields most. This section weighs the first-Search yield of each rank band by the tries of later Searches in that band. A first Search reaches a rank later in its life than its pool would suggest for a late Search, so this y is high, and the same-clause share it gives is a ceiling.\n')
    out = {}
    for name, note in RUNS2:
        first, later = collections.defaultdict(collections.Counter), collections.Counter()
        for task, (slots, draws, _, _) in searches(R, name).items():
            seen = set()
            for s in slots:
                was = s['kind'] in seen
                seen.add(s['kind'])
                for b in BANDS:
                    if s['tries'] >= b[0]:
                        n = min(s['tries'], b[1]) - b[0] + 1
                        if was:
                            later[b] += n
                        else:
                            first[b]['tries'] += n
                            first[b]['kept'] += sum(b[0] <= x[0] <= b[1] for x in s['kept'])
        y = sum(later[b] * first[b]['kept'] / first[b]['tries'] for b in BANDS if first[b]['tries']) / sum(later[b] for b in BANDS if first[b]['tries'])
        t, c = split_inputs(R, name)
        fe, re_ = t['search:equal scope-free'], t['search:equal reads scope']
        kf, kr = c['first kept free'] + c['later kept free'], c['first kept reads'] + c['later kept reads']
        sf, sr = fe + kf - kf / y, re_ + kr - kr / y
        out[name] = y, sf / fe, sr / re_, (sf + sr) / (fe + re_)
        print('`%s`: y %.3f, same clause %s of free equal, %s of reads equal, %s of equal.\n' % (name, y, pct(sf, fe), pct(sr, re_), pct(sf + sr, fe + re_)))
    return out


def s_fit(R):
    print('## Cost of one try of each kind, `evict` arms of %s\n' % EVICT)
    print('A least-squares fit of a span\'s CPU s on its counts of tries of each kind, with no job term, as in rate-age-read.md. CPU s per try, so the machine\'s load is in it. Spans of 37 held-out tasks, seeds 1 and 101, 600 s, EPYC 9654 pods.\n')
    rows = []
    for label, lo, hi in (('all ages', 0, 1e9), ('age under 120 s', 0, 120), ('age 360 s and over', 360, 1e9)):
        X, Y = [], []
        for (arm, task), p in sorted(job_logs(R + '/' + EVICT).items()):
            if not arm.startswith('evict'):
                continue
            prev = None
            for r in prof_lines(p):
                if prev is not None and r['gen'] == prev['gen'] and lo <= r['t'] < hi and r['draws'] > prev['draws'] and r['cpu'] > prev['cpu']:
                    d = r['draws'] - prev['draws']
                    forms = r['forms'] - prev['forms']
                    dup = r.get('dup', 0) - prev.get('dup', 0)
                    equal = r['equal'] - prev['equal']
                    X.append((forms - dup, dup, equal, d - forms - equal))
                    Y.append(r['cpu'] - prev['cpu'])
                prev = r
        b = np.linalg.lstsq(np.array(X, float), np.array(Y, float), rcond=None)[0]
        rows.append((label, len(X), '%.0f' % (1000 * b[0]), '%.0f' % (1000 * b[1]), '%.0f' % (1000 * b[2]), '%.0f' % (1000 * b[3])))
    table(['spans', 'count', 'new form', 'dup form', 'equal', 'failed'], rows)
    return rows


def s_sizing(R):
    print('## Sizing, per 1,000 proposals of the `evict` arms\n')
    arms = span_totals(R + '/' + EVICT)
    t = collections.Counter()
    for arm in ('evict_s1', 'evict_s101'):
        t.update(arms[arm])
    d = t['draws']
    rate, ms = d / t['cpu'], 1000 * t['cpu'] / d
    E = 1000 * t['equal'] / d
    new = 1000 * (t['forms'] - t['dup']) / d
    failed = 1000 * (t['draws'] - t['forms'] - t['equal'] - t['notable']) / d
    take = 1000 * (t['take'] - t['test']) / d
    c0, _, _ = direct_arm(R + '/' + GATE + '/control_search')
    share = {k: c0['search:equal ' + k] / c0['node:equal'] for k in ('INIT', 'RULE', 'DET')}
    free = c0['search:equal scope-free'] / c0['node:equal']
    tries_rd = 1 - (c0['search:equal INIT'] + c0['kept:INIT']) / (c0['node:equal'] + c0['kept'])
    b, _, _ = direct_arm(R + '/search-pool-table-bar-heldout37-60s-3d796f2b/base_search')
    n, _, _ = direct_arm(R + '/search-pool-table-bar-heldout37-60s-3d796f2b/new_search')
    catch = {k: 1 - (n['search:equal ' + k] / n['kept:' + k]) / (b['search:equal ' + k] / b['kept:' + k]) for k in ('INIT', 'RULE', 'DET')}
    key = 1000 * n['sr:new table:cpu'] / n['search.runs']
    end = END_MS
    print('Inputs: %.2f proposals/CPU s, %.1f ms/try, equal %.0f, new %.0f, failed %.0f per 1,000; take less test %.1f ms; END table %.1f ms, the mean step_tables call, an estimate: no record splits the END call from the body calls; merge key at a stop %.2f ms; share of equal by kind %s; scope-free share of equal %.3f; RULE and DET share of tries %.3f; caught by the check %s.\n' % (
        rate, ms, E, new, failed, take, end, key, {k: round(v, 3) for k, v in share.items()}, free, tries_rd, {k: round(v, 3) for k, v in catch.items()}))
    rows = []

    def row(what, caught, net_s, note):
        rows.append((what, '%.0f' % caught, '%.2f' % (caught / ms), '%.1f' % net_s, '%.1f%%' % (100 * net_s / ms), '%.2f' % (rate * net_s / ms), note))
    for label, s in (('low', S_LOW), ('middle', S_MID), ('high', S_HIGH)):
        c = E * s
        row('memo of clause keys over the pool, at the leaf, s %s %.2f' % (label, s), c, c * take / 1000 - 1000 * MEMO_LEAF_MS / 1000, 'saves take; the walk and END are paid')
    for label, s in (('low', S_LOW), ('middle', S_MID), ('high', S_HIGH)):
        c = E * s
        rd = share['RULE'] + share['DET']
        row('memo at the stop coin, s %s %.2f' % (label, s), c, c * (take + rd * end) / 1000 - 1000 * MEMO_STOP_MS / 1000, 'also saves END on RULE and DET; INIT stays at the leaf')
    c = E * (share['RULE'] * catch['RULE'] + share['DET'] * catch['DET'])
    row('known-table check that ends the path at the stop, not run', c, c * (take + end) / 1000 - 1000 * tries_rd * key / 1000, 'one merge key per RULE or DET stop taken')
    c = E * free
    row('drop a scope-free clause at the stop, after a first Search, not run', c, c * (take + end) / 1000, 'loses the 2.5% of new forms a later scope-free clause gives')
    table(['avoidance', 'repeats removed per 1,000', 'repeats removed per CPU s', 'net CPU s saved per 1,000', 'net share of CPU', 'extra proposals per CPU s', 'note'], rows)
    print('Arms that ran, new forms at equal wall seconds (section bars): the check as built, which bars the stop and goes on, -9.3%, proposals -40%, 60 s. Read a scope form, -2.5%, proposals -12%, 60 s. Read a pick, -4.4%, proposals -28%, 300 s.\n')
    print('Failed tries, not in the rows above: %.0f per 1,000. A memo at the stop that also keeps failed clauses saves the END read of each repeat among them. At the fitted cost of a failed try less that of an equal one, and with the same-clause share s, that is up to the same size again. No record gives s on failed tries.\n' % failed)


def s_overlap(R):
    print('## Search yield by overlap with an earlier same-kind scope\n')
    print('Overlap is the largest share of a Search\'s scope that one earlier same-kind scope holds. Run half is by the draw of the Search\'s first visit. First Searches and empty scopes are out.\n')
    edges = [(0, .25), (.25, .5), (.5, .75), (.75, .9), (.9, 1.01)]
    for name, note in RUNS2:
        print('`%s`, %s.\n' % (name, note))
        rows = collections.defaultdict(collections.Counter)
        for task, (slots, draws, _, _) in searches(R, name).items():
            seen = collections.defaultdict(list)
            for s in slots:
                fids, k = s['fids'], s['kind']
                if fids and seen[k]:
                    best = max(len(fids & o) / len(fids) for o in seen[k])
                    b = next(e for e in edges if e[0] <= best < e[1])
                    c = rows[half(s['first_draw'], draws), b]
                    c['searches'] += 1
                    c['tries'] += s['tries']
                    c['kept'] += len(s['kept'])
                seen[k].append(fids)
        table(['run half', 'overlap', 'Searches', 'tries', 'kept', 'yield'], [(a, '%.2f-%.2f' % (b[0], min(b[1], 1)), c['searches'], c['tries'], c['kept'], '%.3f' % (c['kept'] / c['tries'])) for (a, b), c in sorted(rows.items())])


def s_six(R):
    print('## The six tasks of the probe against the 37, `evict` arms of %s\n' % EVICT)
    six = ('5961cc34', 'aa4ec2a5', 'b5ca7ac4', 'c7f57c3e', 'dbff022c', 'e3721c99')
    rows = collections.defaultdict(collections.Counter)
    per = []
    for (arm, task), p in sorted(job_logs(R + '/' + EVICT).items()):
        if not arm.startswith('evict'):
            continue
        c = collections.Counter()
        prev = None
        for r in prof_lines(p):
            if prev is not None and r['gen'] == prev['gen'] and r['t'] > prev['t'] and r['draws'] >= prev['draws'] and r['cpu'] >= prev['cpu']:
                for k in ('draws', 'forms', 'equal', 'dup'):
                    c[k] += r.get(k, 0) - prev.get(k, 0)
                c['cpu'] += r['cpu'] - prev['cpu']
            prev = r
        rows['37'].update(c)
        if task in six:
            rows['6'].update(c)
        per.append(c['equal'] / c['draws'])
    per.sort()
    table(['tasks', 'proposals', 'proposals/CPU s', 'new', 'equal', 'dup'], [(k, c['draws'], '%.2f' % (c['draws'] / c['cpu']), pct(c['forms'] - c['dup'], c['draws']), pct(c['equal'], c['draws']), pct(c['dup'], c['draws'])) for k, c in sorted(rows.items())])
    print('Equal share by job: q10 %.3f, median %.3f, q90 %.3f.\n' % (per[len(per) // 10], per[len(per) // 2], per[len(per) * 9 // 10]))


SECTIONS = dict(shares=s_shares, evict=s_evict, age=s_age, direct=s_direct, kinds=s_kinds, within=s_within, fails=s_fails, bars=s_bars, catch=s_catch, costs=s_costs, ranks=s_ranks, overlap=s_overlap, split=s_split, rankmatch=s_rankmatch, visits=s_visits, textlen=s_textlen, six=s_six, fit=s_fit, sizing=s_sizing)


def main():
    R = sys.argv[1].rstrip('/')
    pick = [x for x in sys.argv[2:] if not x.startswith('--')] or list(SECTIONS)
    for s in pick:
        SECTIONS[s](R)
    points = next((x.split('=', 1)[1] for x in sys.argv[2:] if x.startswith('--points=')), None)
    if points:
        s_right(R, points)


if __name__ == '__main__':
    main()
