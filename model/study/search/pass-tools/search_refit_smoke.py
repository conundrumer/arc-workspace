"""Smoke gate of a round: the arm and the bundle on a few tasks at 180 s, before any round pod starts.

  READ_ARM=pass <python> -I search_refit_smoke.py RUN_FOLDER OUT.json

RUN_FOLDER  holds out/<arm>/<task>/ of the jobs in smoke-jobs.txt (arms smokebundle_s0 and smoke<ARM>_s0), and the smoke jobs file (smoke-jobs.txt) in it, up to two folders above it,
            in the kits folder beside the runs folder, or at the root of the kit tar.
OUT.json    the result: pass, the reasons it failed, and the figures of each job.

The script exits 0 where all of these hold, and 2 where one fails (the JSON gives the reason):
  1. Every job of smoke-jobs.txt ended: its folder is there and its supervisor log has the line `status at <seconds> s` of its line. (The supervisor kills a worker at its end, so deaths and kills are only printed.)
  2. Every job is clean: no `uniform policy`, `steers off`, `bank not written` or `search failed` line.
  3. A bundle job has no node score line and no scope rule line.
  4. Joint (READ_ARM=joint): each smokejoint job has one scope rule line (name joint, beta 0.5), a count of 0 in the run counter `search:scope rule fallback` and no fallback line,
     and every opening with picked nodes is labelled `joint` in the picks file (at least 20 openings).
  5. Uses: over the picks file, the picks that the bank's lineage keeps give each node the uses that the bank holds (search_node_score_parity.py's Uses item), in every job.
  6. Refit (READ_ARM=refit): the node score checks of the refit smoke: the model loads, the node scores differ from the ship score, and the mix works.
  7. Pass (READ_ARM=pass): each smokepass job has the three `first pass` lines (INIT, RULE, DET) with the budget and CPU setting of its line, and each smokebundle job has none. The record
     of a job holds the pass's CPU and forms per kind, the gold forms covered when the pass ended, and the openings that reach the empty scope after 60 s.
Exit status 1 for a failure of the script itself (no jobs file, no run folder).
"""
import json
import os
import re
import sys
import time

import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault('READ_ARM', 'pass')
import search_refit_read as RR  # noqa: E402
import search_joint_rule as RU  # noqa: E402

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
    log = RR.read_text(p['log'])
    picks = [x for x in PA.read_lines(p['picks']) if 'picks' in x]
    if not q['exists']:
        why.append('no job folder')
    elif not q['ended']:
        why.append('job not ended (no status at %d s line and no done line in its supervisor log)' % spec['seconds'])
    if q['ended'] and bank is None:
        why.append('no bank file')
    if q['ns_errors'] and q['ns_errors'] > RR.ERROR_SHARE * max(q['nodes'] or 1, 1):
        why.append('ns_errors %d of %d nodes' % (q['ns_errors'], q['nodes']))
    rec = dict(job='%s/%s' % (name, spec['task']), folder=folder, ended=q['ended'], nodes=q['nodes'], ns_errors=q['ns_errors'], deaths=q['deaths'], kills=q['kills'])
    base = spec['arm']
    base = re.sub(r'^smoke', '', base)
    if RR.ARM == 'joint':
        if base in RU.RULE_ARMS or base == 'joint':
            why += RR.rule_running('joint', log)
            if q['ended']:
                for item, ok, text in RU.items('joint', log, picks):
                    if not ok:
                        why.append('%s: %s' % (item, text))
                if len(picks) < MIN_PICKS:
                    why.append('only %d openings with picks (want %d)' % (len(picks), MIN_PICKS))
            c = RU.counts(log)
            rec.update(fallbacks=c[RU.FALLBACK], rule_picks=c[RU.PICKED], markers=RU.markers(log))
        else:
            why += RR.rule_running(base, log)  # a bundle job has no scope rule line
        rec['openings_by_score'] = {str(k): v for k, v in RU.picks_by_score(picks).items()}
    if RR.ARM == 'pass':  # the pass lines fit the job line (a smokepass job has the three kinds, a smokebundle job has none); the figures go in the record
        evs = RR.PR.events(log)
        why += RR.PR.why(spec, evs, partial=not q['ended'])
        got = RR.PR.first_set(evs)
        rec.update(pass_events=len(evs), pass_cpu={k: got[k].get('cpu') for k in got}, pass_forms={k: got[k].get('forms') for k in got}, pass_covered=sorted(got['DET']['covered']) if 'DET' in got else None,
                   empty_scope_after_60s=RR.PR.empty_scope(folder, spec['task']))
    if bank is not None:
        kept, differ = PA.uses_check(bank, PA.read_lines(p['picks']))
        rec.update(uses_kept_picks=len(kept), uses_differ=differ)
        if differ:
            why.append('uses check: %d nodes differ from the picks (%d picks kept)' % (differ, len(kept)))
    if RR.ARM == 'refit' and spec['score'] is not None and bank is not None:
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
    result = dict(written=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), run=run, smoke_jobs=smoke, arm=RR.ARM, pass_=not reasons, reasons=reasons, jobs=jobs)
    result['pass'] = result.pop('pass_')
    RR.write_atomic(out, json.dumps(result, indent=1) + '\n')
    for j in jobs:
        print('%-30s %s  nodes %s, fallbacks %s, rule picks %s, openings %s, uses differ %s' % (j['job'], 'ok  ' if not j['why'] else 'FAIL', j['nodes'], j.get('fallbacks', '-'),
                                                                                           j.get('rule_picks', '-'), j.get('openings_by_score', '-'), j.get('uses_differ', '-')))
        for w in j['why']:
            print('   ' + w)
    print('smoke %s (%d jobs); wrote %s' % ('pass' if result['pass'] else 'FAIL', len(jobs), out))
    return 0 if result['pass'] else 2


if __name__ == '__main__':
    sys.exit(main())
