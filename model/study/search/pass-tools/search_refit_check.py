"""Checks of a running round of the arm READ_ARM (pass by default here; joint for the joint scope rule arm, refit for the refit node score arm), for a driver to call each 2 minutes: the 3 check jobs, and the 60 s read on the 37.

  READ_ARM=pass <python> -I search_refit_check.py RUN_FOLDER

With READ_ARM=pass the check jobs are parity_s0 and parity_s1 (600 s) and passcheck_s0 (120 s), all on the first task. A job fails where its pass lines do not fit its job line: a pass job
needs the three `first pass` lines (INIT, RULE, DET) with the budget and CPU setting of its line, and a job with no pass needs none.

RUN_FOLDER holds out/<arm>/<task>/ as run3600.sh writes it, and beside it (in it, or up to two folders above) the jobs file search-<arm>-*jobs*.txt and refit-tasks.json.
Exit status:
  0  every check passes or is still running, and the 60 s read has not stopped the round. A line `checks pass` is printed where all 3 checks passed, and `60s pass` where
     the 60 s read passed.
  2  a check failed (the line `check FAILED` names the job and the reason).
  3  the 60 s read stops the round: the mean of the two seeds of the arm is below the bundle by more than the 60 s noise band.
  1  the script could not run (no jobs file, no task list).
The result is written to RUN_FOLDER/refit-check.json each time (status, the checks, the 60 s figures; on exit 3 the reason is in `verdict.reason`).

Checks, on the jobs of the first 3 lines of the jobs file (refit: parity_s0 and parity_s1 at 600 s, refitcheck_s0 at 120 s; joint: jointcheck_s0 and jointcheck_s1 at 180 s, jointfail_s0 at 120 s; all on the first task):
  a job that is running fails at once where its log has `uniform policy`, `steers off` or `bank not written`, or a node score line whose name is not the file name of the
  NODE_SCORE of its line (parity: ship with check 1 and fold 0), or whose mix is not the line's. A job that ended (its supervisor log has `status at <seconds> s` of its line) is checked by search_node_score_parity.py's items
  (Marker, Fallbacks, Nodes, Picks, Errors, Cost, Proc, Uses, Lineage), plus the mix of its marker line.

60 s read, on the 37 held-out tasks only. A task counts when its 4 jobs (bundle and the arm, seeds 0 and 1000) are past 60 s: the job ended (its supervisor log has `status at 600 s`; the `end:` line of the worker log is not used, because a renewal prints one), or one of its files was written
more than 60 s after its start file. A job's forms covered at 60 s are the gold forms whose first cover line has time minus the start file at most 60. For each seed s:
  D(s) = forms covered at 60 s by the arm's job of seed s minus by the bundle's, summed over the counted tasks.
  Noise band at 60 s = |forms covered at 60 s by the bundle on seed 0 minus on seed 1|, summed over the same tasks, as the read does at 600 s.
The round stops (exit 3) where at least N_MIN tasks count and D(s) is below minus the noise band on both seeds. The round passes the 60 s read (`60s pass`) where at least
N_MIN tasks count and it does not stop. N_MIN is 12 of the 37: a task's 4 jobs run on one pod, so a slow pod lowers both arms of its tasks and D does not move, and 12 tasks
are more than the share of one pod when 4 or more pods run the 37 (37 / 4 is under 10). The first time the read passes, the script writes RUN_FOLDER/sixty-pass (the figures as JSON)
through a temp file and a rename, once.
Environment: REFIT_WHERE (pod or mac; the cost budget of the parity script applies on the pod), REFIT_N_MIN, REFIT_PAST_SECONDS and REFIT_READ_SECONDS (both 60) for tests.
"""
import json
import os
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import search_refit_read as RR  # noqa: E402
import search_joint_rule as RU  # noqa: E402

PA = RR.PA
N_MIN = int(os.environ.get('REFIT_N_MIN', 12))
BAND_FLOOR = 4  # forms: the least noise band at 60 s
NO_STOP = os.environ.get('REFIT_NO_STOP', '') == '1'  # skips the 60 s stop
PAST = float(os.environ.get('REFIT_PAST_SECONDS', 60))
READ = float(os.environ.get('REFIT_READ_SECONDS', 60))
WHERE = os.environ.get('REFIT_WHERE', 'pod')
CHECK_ARMS = RR.CHECK_ARMS


def job_dir(run, name, task):
    for base in (run + '/out', run):
        if os.path.isdir('%s/%s/%s' % (base, name, task)):
            return '%s/%s/%s' % (base, name, task)
    return '%s/out/%s/%s' % (run, name, task)


def check_job(run, spec):
    """('pending'|'running'|'pass'|'fail', [reasons]) of one check job."""
    name = '%s_s%d' % (spec['arm'], spec['seed'])
    folder = job_dir(run, name, spec['task'])
    if not os.path.isdir(folder) or not os.path.exists(RR.job_paths(folder, spec['task'])['log']):
        return 'pending', []
    q = RR.quick_job(folder, spec['task'], spec['score'], spec['mix'], spec['seconds'], with_bank=False)
    why = list(q['why'])
    p = RR.job_paths(folder, spec['task'])
    log = RR.read_text(p['log'])
    why += RR.rule_running(spec['arm'], log)  # a job of a rule arm fails at once without the rule's marker line, or with a fallback
    why += RR.PR.why(spec, RR.PR.events(log), partial=not q['ended'])  # the pass lines fit the job line: all of them in an ended job, those so far in a running one
    if q['ended']:
        for item, ok, text in PA.check_job(name, spec['task'], folder, WHERE):
            if not ok:
                why.append('%s: %s' % (item, text))
        if spec['arm'] in RR.RULE_ARMS:
            for item, ok, text in RU.items(spec['arm'], log, PA.read_lines(p['picks'])):
                if not ok:
                    why.append('%s: %s' % (item, text))
    return ('fail' if why else 'pass' if q['ended'] else 'running'), why


def at_seconds(folder, task, secs):
    """The number of gold forms whose first cover line came within secs seconds of the job's start file, or None where the job has no start file."""
    times = RR.cover_times(folder, task)
    return None if times is None else sum(1 for t in times.values() if t <= secs)


def sixty(run, tasks, SECONDS):
    """The 60 s figures over the tasks whose 4 jobs are past 60 s."""
    counted, skipped = [], []
    sums = {(a, s): 0 for a in ('bundle', RR.ARM) for s in RR.PROMOTION_SEEDS}
    for t in tasks:
        folders = {(a, s): job_dir(run, '%s_s%d' % (a, s), t) for a in ('bundle', RR.ARM) for s in RR.PROMOTION_SEEDS}
        if not all(os.path.isdir(f) and RR.past_seconds(f, t, PAST, SECONDS) for f in folders.values()):
            continue
        bad = [k for k, f in folders.items() if any(x in RR.read_text(RR.job_paths(f, t)['log']) for x in RR.FALLBACKS)
               or (k[0] in RR.RULE_ARMS and RU.fallback_lines(RR.read_text(RR.job_paths(f, t)['log'])))]
        if bad:
            skipped.append(dict(task=t, jobs=['%s_s%d' % k for k in bad], why='fallback line in the log (the node score policy, or the scope rule)'))
            continue
        got = {k: at_seconds(f, t, READ) for k, f in folders.items()}
        for k, v in got.items():
            sums[k] += v or 0
        counted.append(t)
    d = {s: sums[RR.ARM, s] - sums['bundle', s] for s in RR.PROMOTION_SEEDS}
    band = max(abs(sums['bundle', 0] - sums['bundle', 1]), BAND_FLOOR)  # a floor, so that a band that is 0 or small by chance stops no round
    enough = len(counted) >= N_MIN
    mean = sum(d.values()) / len(d)
    fall = enough and not NO_STOP and mean < -band
    return dict(
        seconds=READ, tasks_counted=len(counted), tasks_listed=len(tasks), tasks_needed=N_MIN, skipped=skipped,
        forms_covered={'%s_s%d' % k: v for k, v in sums.items()}, D={RR.SEED_NAME[s]: d[s] for s in d}, noise_band=band,
        noise_band_definition='|forms covered at 60 s by the bundle on seed 0 minus on seed 1|, summed over the counted tasks, and at least BAND_FLOOR (%d)' % BAND_FLOOR,
        mean_D=mean, stop_rule='exit 3 where tasks_counted >= tasks_needed and the mean of D over the two seeds < -noise_band; REFIT_NO_STOP=1 (a late-acting lever, or a stopped round run to its end) skips the stop', no_stop=NO_STOP,
        enough_tasks=enough, stop=bool(fall), passed=bool(enough and not fall))


def main():
    run = os.path.abspath(sys.argv[1])
    tasks_file = RR.find_file(run, RR.TASK_FILES['tasks'], 'READ_TASKS')
    jobs = RR.find_jobs(run)
    if not tasks_file or not jobs:
        print('no refit-tasks.json or no jobs file of the arm beside %s' % run, file=sys.stderr)
        return 1
    RR.prepare(run, tasks_file, jobs)
    C = RR.Context
    out = dict(written=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), run=run, round=C.cfg.get('round'), checks={}, status=None)
    for arm in CHECK_ARMS:
        for spec in sorted(C.specs.get(arm, []), key=lambda s: s['seed']):
            state, why = check_job(run, spec)
            name = '%s_s%d/%s' % (arm, spec['seed'], spec['task'])
            out['checks'][name] = dict(state=state, reasons=why)
            print('%-28s %s%s' % (name, state, ': ' + '; '.join(why) if why else ''), flush=True)
    failed = [(n, c['reasons']) for n, c in out['checks'].items() if c['state'] == 'fail']
    seconds = next(x['seconds'] for x in C.specs['bundle'])
    s60 = sixty(run, C.cfg['heldout37'], seconds)
    out['sixty'] = s60
    print('60 s read: %d of %d tasks counted (need %d), D %s, noise band %d' % (s60['tasks_counted'], s60['tasks_listed'], N_MIN, s60['D'], s60['noise_band']), flush=True)
    code = 0
    if failed:
        for n, why in failed:
            print('check FAILED: %s: %s' % (n, '; '.join(why)))
        out['status'] = 'check failed'
        out['verdict'] = dict(passed=False, final=False, reason='check failed: ' + '; '.join('%s: %s' % (n, '; '.join(w)) for n, w in failed))
        code = 2
    elif s60['stop']:
        out['status'] = 'stopped at 60 s'
        out['verdict'] = dict(passed=False, final=False, reason='stopped at 60 s: the mean D of the %s arm against the bundle' % RR.ARM + ' over the two seeds, %.1f, is past the noise band %d (D %s over %d tasks)' % (
            s60['mean_D'], s60['noise_band'], s60['D'], s60['tasks_counted']))
        print('60s STOP: ' + out['verdict']['reason'])
        code = 3
    else:
        out['status'] = 'ok' if all(c['state'] == 'pass' for c in out['checks'].values()) else 'running'
        if all(c['state'] == 'pass' for c in out['checks'].values()) and len(out['checks']) == 3:
            print('checks pass')
        if s60['passed']:
            print('60s pass')
            marker = os.path.join(run, 'sixty-pass')
            if not os.path.exists(marker):
                RR.write_atomic(marker, json.dumps(s60, indent=1) + '\n')
    RR.write_atomic(os.path.join(run, 'refit-check.json'), json.dumps(out, indent=1) + '\n')
    return code


def crashed(e):
    """Writes refit-check.json with status `check crashed` and a failed verdict that names the crash, so that a driver stops the round on it, and gives 2."""
    import traceback
    run = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()
    why = '%s: %s' % (type(e).__name__, e)
    out = dict(written=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), run=run, status='check crashed', trace=traceback.format_exc()[-2000:],
               verdict=dict(passed=False, final=False, reason='check crashed: ' + why))
    try:
        RR.write_atomic(os.path.join(run, 'refit-check.json'), json.dumps(out, indent=1) + '\n')
    except Exception:  # noqa: BLE001
        pass
    print('check CRASHED: ' + why, file=sys.stderr)
    return 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:  # noqa: BLE001
        sys.exit(crashed(e))
