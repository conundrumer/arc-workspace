"""Writes the jobs files of the joint round from the jobs file of round 1, and the manifest of the kit.

  <python> -I search_joint_build.py KIT_FOLDER OUT_FOLDER

Jobs file: 3 check lines, then for each of the 37 held-out tasks the lines bundle_s0, joint_s0, bundle_s1 and joint_s1 (148 lines).
  A bundle line is the round 1 line of the same task and arm, unchanged.
  A joint line is that bundle line with SEARCH_SCOPE_RULE=$PWD/scope/joint.py added and the arm renamed. It has no NODE_SCORE.
  Check lines, on the first task: jointcheck_s0 and jointcheck_s1 (the rule, 180 s) and jointfail_s0 (the rule with SCOPE_RULE_FAIL=1, so every opening falls back, 120 s).
Smoke file: smokebundle_s0 and smokejoint_s0 on 135a2760 and 74dd1130, 180 s.
"""
import json
import os
import re
import sys

BASE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/kits/'
BASE_JOBS = BASE + 'search-refit-r1-jobs-heldout37-ramp22-2seeds-600s.txt'
BASE_SMOKE = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/joint/base/search-refit-r1-kit-0729e4943/smoke-jobs.txt'
RULE = 'SEARCH_SCOPE_RULE=$PWD/scope/joint.py '
LINE = re.compile(r'^(?P<head>.*?)\./run3600\.sh (?P<task>\w+) (?P<arm>\w+) (?P<models>\S+) (?P<seconds>\d+)\s*$')
JOBS_NAME = 'search-joint-r1-jobs-heldout37-2seeds-600s.txt'


def parse(line):
    m = LINE.match(line)
    assert m, line
    return m


def make(m, arm, extra='', seconds=None):
    """The line of m with extra environment before ./run3600.sh, the arm renamed, and optionally other seconds."""
    return '%s%s./run3600.sh %s %s %s %s' % (m['head'], extra, m['task'], arm, m['models'], seconds or m['seconds'])


def main():
    kit, out = sys.argv[1:3]
    lines = [x for x in open(BASE_JOBS).read().split('\n') if x.strip()]
    tasks = json.load(open(kit + '/refit-tasks.json'))['heldout37']
    assert len(tasks) == 37
    bundle = {}
    for x in lines:
        m = parse(x)
        if m['arm'] in ('bundle_s0', 'bundle_s1') and m['task'] in tasks:
            assert 'NODE_SCORE' not in x and (m['arm'], m['task']) not in bundle
            bundle[m['arm'], m['task']] = x
    assert len(bundle) == 74, len(bundle)
    first = tasks[0]
    check = [make(parse(bundle['bundle_s0', first]), 'jointcheck_s0', RULE, 180),
             make(parse(bundle['bundle_s1', first]), 'jointcheck_s1', RULE, 180),
             make(parse(bundle['bundle_s0', first]), 'jointfail_s0', RULE + 'SCOPE_RULE_FAIL=1 ', 120)]
    body = []
    for t in tasks:
        for s in (0, 1):
            x = bundle['bundle_s%d' % s, t]
            body += [x, make(parse(x), 'joint_s%d' % s, RULE)]
    jobs = check + body
    assert len(jobs) == 151
    text = ''.join(x + '\n' for x in jobs)
    smoke = []
    for x in open(BASE_SMOKE).read().split('\n'):
        if x.strip():
            m = parse(x)
            smoke.append(x if m['arm'] == 'smokebundle_s0' else make(m, 'smokejoint_s0', RULE).replace('NODE_SCORE=$PWD/scores/refit.npz NODE_SCORE_MIX=.5 ', ''))
    assert len(smoke) == 4 and not any('NODE_SCORE' in x for x in smoke)
    os.makedirs(out, exist_ok=True)
    for d in (kit, out):
        open(d + '/' + JOBS_NAME, 'w').write(text)
        open(d + '/smoke-jobs.txt', 'w').write(''.join(x + '\n' for x in smoke))
    man = json.load(open(kit + '/manifest.json'))
    man['what'] = ('round r1 of the joint scope pick: the bundle (ORDER_FREE=tie,key, models-tk) against the same kit with the scope rule scope/joint.py (SEARCH_SCOPE_RULE), '
                   'two seeds on the 37 held-out tasks at 600 s; a task\'s 4 lines run on one pod')
    man['commit'] = ('search-refit-r1-kit-0729e4943 with one line added to model/study/sampler/kaggle_worker.py (search.load_rule() in source(), so that the worker loads '
                     'SEARCH_SCOPE_RULE) and the folder scope/ (joint.py, model.json); NODE_SCORE unset')
    man['arm'] = {'bundle': 'models-tk, seeds 0 and 1000, 37 tasks', 'joint': 'bundle plus SEARCH_SCOPE_RULE=scope/joint.py (beta 0.5, model.json: the fit on the 50 N600 tasks)',
                  'jointcheck': 'joint at 180 s on the first task', 'jointfail': 'joint at 120 s with SCOPE_RULE_FAIL=1: every opening falls back to the policy',
                  'smokebundle': 'bundle at 180 s', 'smokejoint': 'joint at 180 s'}
    man['task_set'] = tasks
    json.dump(man, open(kit + '/manifest.json', 'w'), indent=1)
    print('jobs %d lines, smoke %d lines' % (len(jobs), len(smoke)))


main()
