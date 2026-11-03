"""Smoke gate of a refit round: the refit arm and the bundle on a few tasks at 60 s, before any round pod starts.

  <python> -I search_refit_smoke.py RUN_FOLDER OUT.json

RUN_FOLDER  holds out/<arm>/<task>/ of the jobs in smoke-jobs.txt (arms smokerefit_s0 and smokebundle_s0), and the smoke jobs file (smoke-jobs.txt, or search-refit-rN-smoke-jobs.txt) in it, up to two folders above it, in the kits folder beside the runs folder, or at the root of the kit tar.
OUT.json    the result: pass, the reasons it failed, and the figures of each job.

The script exits 0 where all of these hold, and 2 where one fails (the JSON gives the reason):
  1. Every job of smoke-jobs.txt ended: its folder is there and its supervisor log has the line `status at <seconds> s` of its line. (The supervisor kills a worker at its end, so deaths and kills are only printed.)
  2. Every job is clean: no `uniform policy`, `steers off` or `bank not written` line, and ns_errors at most .1% of the nodes.
  3. The model loads: each refit job's log has one node score line, its name is the file name of the NODE_SCORE of the job's line (refit), and its mix is that of the line.
     A bundle job has no node score line.
  4. The node scores differ from the ship score on the same nodes: for each refit job the bank holds, for each node, the node score (policy score) and the ship score
     (policy score_ship, which the policy computes with the hand model at the node's birth). At least 30 nodes, and the scores differ on at least 90% of them.
  5. The mix works: where a refit job has at least 20 scope picks, the picks file shows both the refit score and the ship score as the score of an opening.
Exit status 1 for a failure of the script itself (no jobs file, no run folder).
"""
import json
import os
import sys
import time

import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import search_refit_read as RR  # noqa: E402

PA = RR.PA
MIN_NODES, MIN_DIFFER_SHARE, MIN_PICKS = 30, .9, 20


def job_dir(run, name, task):
    for base in (run + '/out', run):
        if os.path.isdir('%s/%s/%s' % (base, name, task)):
            return '%s/%s/%s' % (base, name, task)
    return '%s/out/%s/%s' % (run, name, task)


def one_job(run, spec):
    name = '%s_s%d' % (spec['arm'], spec['seed'])
    folder = job_dir(run, name, spec['task'])
    q = RR.quick_job(folder, spec['task'], spec['score'], spec['mix'], spec['seconds'])
    p = RR.job_paths(folder, spec['task'])
    bank = q.pop('bank', None)
    why = list(q['why'])
    if not q['exists']:
        why.append('no job folder')
    elif not q['ended']:
        why.append('job not ended (no status at %d s line and no done line in its supervisor log)' % spec['seconds'])
    if q['ended'] and bank is None:
        why.append('no bank file')
    if q['ns_errors'] and q['ns_errors'] > RR.ERROR_SHARE * max(q['nodes'] or 1, 1):
        why.append('ns_errors %d of %d nodes' % (q['ns_errors'], q['nodes']))
    rec = dict(job='%s/%s' % (name, spec['task']), folder=folder, ended=q['ended'], nodes=q['nodes'], ns_errors=q['ns_errors'], deaths=q['deaths'], kills=q['kills'])
    if spec['score'] is not None and bank is not None:
        policy = bank['policy']
        ids = policy['ids']
        ship = policy.get('score_ship') or {}
        both = [i for i in ids if i in policy['score'] and i in ship]
        a = np.array([policy['score'][i] for i in both], float)
        b = np.array([ship[i] for i in both], float)
        differ = float((a != b).mean()) if len(both) else 0.0
        rec.update(nodes_compared=len(both), differ_share=round(differ, 4), corr=round(float(np.corrcoef(a, b)[0, 1]), 3) if len(both) > 2 else None)
        if len(both) < MIN_NODES:
            why.append('only %d nodes with both scores (want %d)' % (len(both), MIN_NODES))
        elif differ < MIN_DIFFER_SHARE:
            why.append('node scores differ from the ship score on %.0f%% of %d nodes (want %.0f%%)' % (100 * differ, len(both), 100 * MIN_DIFFER_SHARE))
        picks = [x for x in PA.read_lines(p['picks']) if 'picks' in x]
        used = {}
        for x in picks:
            used[x.get('score')] = used.get(x.get('score'), 0) + 1
        rec['openings_by_score'] = {str(k): v for k, v in used.items()}
        if len(picks) >= MIN_PICKS and not (used.get(spec['score'], 0) and used.get('ship', 0)):
            why.append('the mix used one score only in %d openings: %s' % (len(picks), rec['openings_by_score']))
    rec['why'] = why
    return rec


def main():
    run = os.path.abspath(sys.argv[1])
    out = sys.argv[2]
    smoke = next((p for p in RR.find_jobs(run) if 'smoke' in os.path.basename(p)), None)
    if not smoke or not os.path.isdir(run):
        print('no smoke-jobs.txt beside %s' % run, file=sys.stderr)
        return 1
    arms = {a: v for a, v in RR.parse_jobs([smoke]).items() if a.startswith('smoke')}
    jobs = [one_job(run, s) for arm in sorted(arms) for s in arms[arm]]
    reasons = ['%s: %s' % (j['job'], w) for j in jobs for w in j['why']]
    result = dict(written=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), run=run, smoke_jobs=smoke, pass_=not reasons, reasons=reasons, jobs=jobs)
    result['pass'] = result.pop('pass_')
    RR.write_atomic(out, json.dumps(result, indent=1) + '\n')
    for j in jobs:
        print('%-30s %s  nodes %s, differ %s, openings %s' % (j['job'], 'ok  ' if not j['why'] else 'FAIL', j['nodes'], j.get('differ_share', '-'), j.get('openings_by_score', '-')))
        for w in j['why']:
            print('   ' + w)
    print('smoke %s (%d jobs); wrote %s' % ('pass' if result['pass'] else 'FAIL', len(jobs), out))
    return 0 if result['pass'] else 2


if __name__ == '__main__':
    sys.exit(main())
