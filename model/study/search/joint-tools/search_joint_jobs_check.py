"""Check of the joint round's jobs file against the jobs file of round 1.

  <python> -I search_joint_jobs_check.py JOBS_FILE [SMOKE_FILE]

Items (each prints ok or FAIL):
  lines      the file has 151 lines: 3 check lines, then 148
  checks     the first 3 lines are the check lines: arms jointcheck_s0, jointcheck_s1 and jointfail_s0, all with the rule, on the first task
  bundle     the bundle lines of the file equal, in text, the bundle lines of the 37 held-out tasks in round 1's jobs file (74 lines, none changed)
  joint      each joint line is the bundle line of its task and seed with `SEARCH_SCOPE_RULE=$PWD/scope/joint.py ` added before ./run3600.sh and the arm renamed;
             a joint line has no NODE_SCORE
  tasks      each of the 37 tasks has 4 lines (bundle_s0, joint_s0, bundle_s1, joint_s1), all 600 s, and they share one SAME_POD
  smoke      (with SMOKE_FILE) 4 lines: smokebundle_s0 and smokejoint_s0 on 135a2760 and 74dd1130, 180 s; the bundle lines equal round 1's smoke lines
Exit status 0 where all items pass.
"""
import collections
import json
import re
import sys

BASE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/kits/'
BASE_JOBS = BASE + 'search-refit-r1-jobs-heldout37-ramp22-2seeds-600s.txt'
BASE_KIT = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/joint/base/search-refit-r1-kit-0729e4943/'
RULE = 'SEARCH_SCOPE_RULE=$PWD/scope/joint.py '
LINE = re.compile(r'^(?P<head>.*?)\./run3600\.sh (?P<task>\w+) (?P<arm>\w+) (?P<models>\S+) (?P<seconds>\d+)$')


def lines_of(path):
    return open(path).read().split('\n')[:-1]  # the file ends with a newline


def main():
    jobs = lines_of(sys.argv[1])
    base = lines_of(BASE_JOBS)
    tasks = json.load(open(BASE_KIT + 'refit-tasks.json'))['heldout37']
    parsed = [LINE.match(x) for x in jobs]
    results = []

    def item(name, ok, text=''):
        results.append(ok)
        print('%-8s %s %s' % (name, 'ok  ' if ok else 'FAIL', text))
    item('lines', len(jobs) == 151 and all(parsed), '%d lines' % len(jobs))
    chk = parsed[:3]
    item('checks', [m['arm'] for m in chk] == ['jointcheck_s0', 'jointcheck_s1', 'jointfail_s0'] and all(m['task'] == tasks[0] and RULE in m['head'] for m in chk)
         and 'SCOPE_RULE_FAIL=1' in chk[2]['head'], ', '.join('%s %ss' % (m['arm'], m['seconds']) for m in chk))
    body = jobs[3:]
    base_bundle = [x for x in base if (m := LINE.match(x)) and m['arm'] in ('bundle_s0', 'bundle_s1') and m['task'] in tasks]
    got_bundle = [x for x in body if LINE.match(x)['arm'].startswith('bundle_s')]
    item('bundle', len(base_bundle) == 74 and sorted(got_bundle) == sorted(base_bundle) and len(set(got_bundle)) == 74,
         '%d bundle lines, %d of them equal to round 1\'s' % (len(got_bundle), len(set(got_bundle) & set(base_bundle))))
    by = {(LINE.match(x)['arm'], LINE.match(x)['task']): x for x in body}
    bad = []
    for t in tasks:
        for s in (0, 1):
            b, j = by.get(('bundle_s%d' % s, t)), by.get(('joint_s%d' % s, t))
            want = None if b is None else LINE.sub(lambda m: '%s%s./run3600.sh %s joint_s%d %s %s' % (m['head'], RULE, m['task'], s, m['models'], m['seconds']), b)
            if j is None or j != want or 'NODE_SCORE' in j:
                bad.append((s, t))
    item('joint', not bad and sum(LINE.match(x)['arm'].startswith('joint_s') for x in body) == 74, '%d of 74 joint lines differ from the rule' % len(bad))
    per = collections.defaultdict(list)
    for x in body:
        m = LINE.match(x)
        per[m['task']].append((m['arm'], m['seconds'], re.search(r'SAME_POD=(\S+)', m['head'])[1]))
    ok = set(per) == set(tasks) and all(sorted(a for a, _, _ in v) == ['bundle_s0', 'bundle_s1', 'joint_s0', 'joint_s1'] and {s for _, s, _ in v} == {'600'} and len({p for _, _, p in v}) == 1
                                        for v in per.values())
    item('tasks', ok, '%d tasks, 4 lines each' % len(per))
    if len(sys.argv) > 2:
        smoke = lines_of(sys.argv[2])
        base_smoke = [x for x in lines_of(BASE_KIT + 'smoke-jobs.txt') if 'smokebundle_s0' in x]
        arms = [(LINE.match(x)['task'], LINE.match(x)['arm'], LINE.match(x)['seconds']) for x in smoke]
        want = [('135a2760', 'smokebundle_s0', '180'), ('135a2760', 'smokejoint_s0', '180'), ('74dd1130', 'smokebundle_s0', '180'), ('74dd1130', 'smokejoint_s0', '180')]
        item('smoke', arms == want and [x for x in smoke if 'smokebundle' in x] == base_smoke and all(RULE in x and 'NODE_SCORE' not in x for x in smoke if 'smokejoint' in x),
             '%d lines' % len(smoke))
    return 0 if all(results) else 2


if __name__ == '__main__':
    sys.exit(main())
