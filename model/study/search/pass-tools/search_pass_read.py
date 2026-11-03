"""The facts of the first pass, for the read, the check and the smoke of the arm pass (READ_ARM=pass).

  <python> -I search_pass_read.py RUN_FOLDER      prints the three tables below without the rest of the read

The worker writes one log line `first pass {json}` for each kind of the pass (INIT, RULE, DET, in that order), with the keys kind, seconds, cpu, tries, nodes, forms, exhausted,
budget, by_cpu and covered (the gold forms covered so far). A worker that renews skips the pass, so a job has one set of three lines, or more where a worker started with an
empty bank again.

Tables, over the jobs in RUN_FOLDER/out/<arm>_s<seed>/<task>:
  1. The pass: for each group of tasks (the 37 held-out tasks, the 22 ramp tasks) and each seed, the mean CPU seconds, wall seconds, tries, new nodes and forms of each kind, and the
     mean of the gold forms covered when the kind ended.
  2. The roots: the gold roots that the direct run (PASS_DIRECT, default the results.jsonl of search-root-direct-19-60cpus-mac) took and that are real misses: its 17 takes less the 9
     whose table is also the table of a lower-indexed gold form that is not a take (PASS_DUPS, default the dups.json of the gold-dups fix), which leaves 8. For each root and seed: the kind of the pass that covered it, else when the job covered it later, else no; for the pass arm and the bundle.
  3. Empty-scope openings after the first 60 s, for each job of the arms bundle and pass: the openings (picks lines) later than 60 s after the job's start file, those whose picks are empty
     (the opening reaches the empty scope), and the visits of the empty scope after 60 s, split into visits of a slot that had no visit before (new) and later visits (resumed).
"""
import collections
import json
import os
import re
import sys

sys.dont_write_bytecode = True

KINDS = ('INIT', 'RULE', 'DET')
PASS_ARMS = ('pass', 'passcheck')
LINE = re.compile(r'^first pass (\{.*\})\s*$', re.M)
SETTING = re.compile(r'\b(FIRST_PASS_SECONDS|FIRST_PASS_RULE|FIRST_PASS_CPU)=(\S+)')
DIRECT = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/runs/search-root-direct-19-60cpus-mac/results.jsonl'
DUPS = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/gold-dups/dups.json'  # the gold forms of each task that share one table
LAST_DUPLICATES = set()  # the takes of the direct run that roots() left out as duplicate-table forms
SLACK = 22.0  # CPU seconds past a kind's budget that one try can take (the clause limit is 20 s)
LATE = 60  # seconds: the openings after this are counted in table 3


def settings(head):
    """The pass settings of a job line's head: {seconds, rule, cpu} (rule is the seconds of the RULE kind, cpu is true where the budgets are CPU seconds), or None for a line with no pass."""
    got = dict(SETTING.findall(head))
    if 'FIRST_PASS_SECONDS' not in got or float(got['FIRST_PASS_SECONDS']) <= 0:
        return None
    seconds = float(got['FIRST_PASS_SECONDS'])
    return dict(seconds=seconds, rule=float(got.get('FIRST_PASS_RULE', seconds)), cpu=got.get('FIRST_PASS_CPU', '0') == '1')


def events(log):
    """The `first pass` events of a worker log, in order."""
    got = []
    for text in LINE.findall(log):
        try:
            got.append(json.loads(text))
        except ValueError:
            pass
    return got


def first_set(evs):
    """The first INIT, RULE, DET events of the job: {kind: event}. Events of a later set (a worker that started with an empty bank) are left out."""
    got = {}
    for e in evs:
        if e.get('kind') in KINDS and e['kind'] not in got:
            got[e['kind']] = e
    return got


def why(spec, evs, partial=False):
    """The reasons that the pass events of a job do not fit its line (spec['first'] holds the line's pass settings, or None). With partial, the job still runs: the events
    that are there must fit, and fewer than all of them is no fault."""
    first = spec.get('first')
    if first is None:
        return ['first pass line in a job with no pass'] if evs else []
    if not evs:
        return [] if partial else ['no first pass line']
    out = []
    kinds = [e.get('kind') for e in evs]
    if partial:
        if kinds != [KINDS[i % len(KINDS)] for i in range(len(kinds))]:
            out.append('first pass kinds %s, want INIT RULE DET' % ' '.join(map(str, kinds)))
    elif len(evs) % len(KINDS) or kinds != list(KINDS) * (len(evs) // len(KINDS)):
        out.append('first pass kinds %s, want INIT RULE DET' % ' '.join(map(str, kinds)))
    for e in evs:
        budget = first['rule'] if e.get('kind') == 'RULE' else first['seconds']
        if e.get('budget') != budget or bool(e.get('by_cpu')) != first['cpu']:
            out.append('first pass %s budget %s by_cpu %s, want %s %s' % (e.get('kind'), e.get('budget'), e.get('by_cpu'), budget, first['cpu']))
        elif first['cpu'] and e.get('cpu', 0) > budget + SLACK:
            out.append('first pass %s used %s CPU s of a budget of %s' % (e.get('kind'), e.get('cpu'), budget))
    return out


def job_dir(run, name, task):
    for base in (run + '/out', run):
        if os.path.isdir('%s/%s/%s' % (base, name, task)):
            return '%s/%s/%s' % (base, name, task)
    return None


def lines(path):
    got = []
    if os.path.exists(path):
        for line in open(path, errors='replace'):
            try:
                got.append(json.loads(line))
            except ValueError:
                pass
    return got


def log_of(folder, task):
    path = '%s/work/%s.log' % (folder, task)
    return open(path, errors='replace').read() if os.path.exists(path) else ''


def start_of(folder, picks):
    try:
        return float(open(folder + '/start').read().split()[0])
    except (OSError, ValueError, IndexError):
        return min((p['time'] for p in picks if 'time' in p), default=None)


def empty_scope(folder, task, secs=LATE):
    """Facts of one job: the openings later than secs after the start, those with empty picks, and the visits of the empty scope later than secs (new: the slot had no visit before)."""
    work = '%s/work/%s.out.jsonl' % (folder, task)
    picks, visits = lines(work + '.picks'), lines(work + '.visits')
    t0 = start_of(folder, picks)
    if t0 is None:
        return None
    late = [p for p in picks if 'picks' in p and p['time'] - t0 > secs]
    vis = [v for v in visits if not v['fids'] and v['time'] - t0 > secs]
    return dict(openings=len(late), empty=sum(not p['picks'] for p in late), visits=len(vis), visits_new=sum(not v['resume'] for v in vis), visits_resumed=sum(bool(v['resume']) for v in vis),
                openings_all=sum('picks' in p for p in picks), empty_all=sum('picks' in p and not p['picks'] for p in picks))


def duplicates(takes, path=None):
    """The set of (task, g) among takes that are duplicate-table forms: the gold form shares its table with a lower-indexed gold form of the same task that is not itself a take.
    path is dups.json: {task: [[gold indices that share one table], ...]}."""
    path = path or os.environ.get('PASS_DUPS', DUPS)
    groups = json.load(open(path))
    taken = set(takes)
    return {(t, g) for t, g in taken if any(g in grp and any(h < g and (t, h) not in taken for h in grp) for grp in groups.get(t, []))}


def roots(path=None):
    """[(task, g, kind, hit_cpu)] of the real misses: the takes of the direct run less its duplicate-table forms (see duplicates)."""
    path = path or os.environ.get('PASS_DIRECT', DIRECT)
    if not os.path.exists(path):
        return []
    got = {}
    for r in lines(path):
        if r.get('hit') and not r.get('error') and r['hit_cpu'] <= r['budget'] + 1e-9:
            got[r['task'], r['g']] = (r['task'], r['g'], r['kind'], r['hit_cpu'])
    global LAST_DUPLICATES
    LAST_DUPLICATES = duplicates(got)
    return sorted((v for k, v in got.items() if k not in LAST_DUPLICATES), key=lambda x: x[3])


def fmt(rows):
    w = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    return ['  ' + '  '.join(c.ljust(w[i]) for i, c in enumerate(r)).rstrip() for r in rows]


def mean(v):
    v = list(v)
    return sum(v) / len(v) if v else float('nan')


SEEDS = (('0', 0), ('1000', 1))


def tables(RR, run, cfg):
    """(lines, data) of the three tables for the tasks of cfg (heldout37, ramp22)."""
    out, data = [], {}
    groups = (('37', cfg.get('heldout37', [])), ('ramp22', cfg.get('ramp22', [])))
    # 1. the pass
    rows = [['tasks', 'seed', 'jobs', 'kind', 'CPU s', 'wall s', 'tries', 'new nodes', 'forms', 'gold covered after', 'exhausted']]
    data['pass'] = {}
    totals = []
    for gname, tasks in groups:
        for sname, seed in SEEDS:
            sets = []
            for t in tasks:
                f = job_dir(run, 'pass_s%d' % seed, t)
                if f:
                    s = first_set(events(log_of(f, t)))
                    if len(s) == len(KINDS):
                        sets.append(s)
            if not sets:
                continue
            cell = data['pass'].setdefault(gname, {}).setdefault(sname, dict(jobs=len(sets)))
            for kind in KINDS:
                es = [s[kind] for s in sets]
                cell[kind] = dict(cpu=mean(e['cpu'] for e in es), seconds=mean(e['seconds'] for e in es), tries=mean(e['tries'] for e in es), nodes=mean(e['nodes'] for e in es),
                                  forms=mean(e.get('forms', float('nan')) for e in es), covered=mean(len(e['covered']) for e in es), exhausted=sum(bool(e.get('exhausted')) for e in es))
                c = cell[kind]
                rows.append([gname, sname, str(len(sets)), kind, '%.1f' % c['cpu'], '%.1f' % c['seconds'], '%.0f' % c['tries'], '%.1f' % c['nodes'], '%.1f' % c['forms'], '%.2f' % c['covered'],
                             '%d' % c['exhausted']])
            tot = [sum(s[k]['cpu'] for k in KINDS) for s in sets]
            cell['cpu_total'] = dict(mean=mean(tot), max=max(tot))
            rows.append([gname, sname, str(len(sets)), 'all', '%.1f (max %.1f)' % (mean(tot), max(tot)), '%.1f' % mean(sum(s[k]['seconds'] for k in KINDS) for s in sets), '', '',
                         '%.1f' % mean(sum(s[k].get('forms', 0) for k in KINDS) for s in sets), '', ''])
            totals += tot
    out += ['\nThe first pass (mean over the pass jobs of the group and seed that logged all three kinds; CPU s and wall s are per kind)'] + (fmt(rows) if len(rows) > 1 else ['  no pass job has logged the pass yet'])
    # 2. the roots
    rt = roots()
    out.append('\nRoots that the direct run took and that are real misses (its takes less %d duplicate-table forms: %s): %d' % (
        len(LAST_DUPLICATES), ' '.join('%s g%d' % x for x in sorted(LAST_DUPLICATES)), len(rt)))
    data['roots'] = []
    if not rt:
        out.append('  no direct run results at %s' % os.environ.get('PASS_DIRECT', DIRECT))
    else:
        inrun = {t for _, ts in groups for t in ts}
        head = ['task', 'gold', 'kind', 'direct CPU s', 'pass s0', 'pass s1000', 'bundle s0', 'bundle s1000']
        rows = [head]
        took = collections.Counter()
        listed = [r for r in rt if r[0] in inrun]
        for task, g, kind, cpu in rt:
            row = [task, 'g%d' % g, kind, '%.2f' % cpu]
            rec = dict(task=task, g=g, kind=kind, direct_cpu=cpu, in_jobs=task in inrun)
            for arm in ('pass', 'bundle'):
                for sname, seed in SEEDS:
                    f = job_dir(run, '%s_s%d' % (arm, seed), task) if task in inrun else None
                    if not f:
                        cell = 'no job'
                    else:
                        cover = RR.cover_times(f, task) or {}
                        if arm == 'pass':
                            evs = first_set(events(log_of(f, task)))
                            by = next((k for k in KINDS if k in evs and g in evs[k]['covered']), None)
                        else:
                            by = None
                        if by:
                            cell = 'pass ' + by
                            took['pass', sname] += 1
                        elif g in cover:
                            cell = ('later %.0f s' if arm == 'pass' else 'at %.0f s') % cover[g]
                            took[arm + ' later' if arm == 'pass' else 'bundle', sname] += 1
                        else:
                            cell = 'no'
                    rec['%s_s%s' % (arm, sname)] = cell
                    row.append(cell)
            rows.append(row)
            data['roots'].append(rec)
        out += fmt(rows)
        n_in = len(listed)
        within = sum(r[3] <= 15 for r in rt)
        out.append('  roots whose task is in the round: %d of %d; the direct run took %d of the %d within 15 CPU s' % (n_in, len(rt), within, len(rt)))
        for sname, _ in SEEDS:
            out.append('  seed %s: the pass took %d of %d roots (the direct run took %d of those within 15 CPU s); the pass job covered %d more later; the bundle job covered %d' % (
                sname, took['pass', sname], n_in, sum(1 for r in listed if r[3] <= 15), took['pass later', sname], took['bundle', sname]))
        data['roots_summary'] = dict(roots=len(rt), with_jobs=n_in, direct_within_15=within, taken={'%s_s%s' % k: v for k, v in took.items()})
    # 3. empty-scope openings after the first 60 s
    rows = [['arm', 'seed', 'task', 'openings after 60 s', 'empty-scope openings', 'empty visits new', 'empty visits resumed']]
    data['empty'] = {}
    sums = {}
    for arm in ('bundle', 'pass'):
        for sname, seed in SEEDS:
            tot = collections.Counter()
            n = zero = 0
            per = {}
            for gname, tasks in groups:
                for t in tasks:
                    f = job_dir(run, '%s_s%d' % (arm, seed), t)
                    e = empty_scope(f, t) if f else None
                    if e is None:
                        continue
                    n += 1
                    zero += e['empty'] == 0
                    tot.update(openings=e['openings'], empty=e['empty'], visits_new=e['visits_new'], visits_resumed=e['visits_resumed'])
                    per[t] = e
                    if arm == 'bundle':
                        rows.append([arm, sname, t, str(e['openings']), str(e['empty']), str(e['visits_new']), str(e['visits_resumed'])])
            if n:
                sums[arm, sname] = (n, zero, tot)
                data['empty']['%s_s%s' % (arm, sname)] = dict(jobs=n, jobs_with_none=zero, per_job=per, **tot)
    out.append('\nOpenings that reach the empty scope after the first %d s of a job (picks lines with empty picks; per job for the bundle arm, sums for each arm and seed)' % LATE)
    out += fmt(rows) if len(rows) > 1 else ['  no bundle job yet']
    for (arm, sname), (n, zero, tot) in sorted(sums.items()):
        out.append('  %s seed %s: %d jobs, %d openings after %d s, %d of them empty-scope (%.1f per job, %d jobs with none), empty-scope visits %d new, %d resumed' % (
            arm, sname, n, tot['openings'], LATE, tot['empty'], tot['empty'] / n, zero, tot['visits_new'], tot['visits_resumed']))
    return out, data


def main():
    run = os.path.abspath(sys.argv[1])
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    os.environ.setdefault('READ_ARM', 'pass')
    import search_refit_read as RR
    tasks = RR.find_file(run, RR.TASK_FILES['tasks'], 'READ_TASKS')
    if not tasks:
        raise SystemExit('no refit-tasks.json beside %s' % run)
    text, _ = tables(RR, run, json.load(open(tasks)))
    print('\n'.join(text))


if __name__ == '__main__':
    main()
