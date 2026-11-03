"""Writes the jobs files and the manifest of the pass round from the jobs file of round 1, and checks the kit against the round 1 kit.

  <python> -I search_pass_build.py BASE_KIT KIT OUT

BASE_KIT  the round 1 kit, extracted (search-refit-r1-kit-0729e4943 from the tar with sha256 43600cbb...).
KIT       the pass kit folder: BASE_KIT with the gold-dups patches and the pass edits of superdag_search.py and kaggle_worker.py applied.
OUT       where the jobs file, the smoke file and the manifest are copied.

Jobs file: 3 check lines, then for each task of the round 1 file, in its order, the lines bundle_s0, pass_s0, bundle_s1 and pass_s1 (236 lines).
  The check lines are the two parity lines of round 1, unchanged, and passcheck_s0: the bundle_s0 line of the first task with the pass, 120 s.
  A bundle line is the round 1 line of the same task and arm, unchanged.
  A pass line is that bundle line with the pass settings added and the arm renamed.
Smoke file: smokebundle_s0 and smokepass_s0 on 135a2760 and 74dd1130, 180 s, SAME_POD=smoke.
Pass settings: FIRST_PASS_SECONDS=15 FIRST_PASS_RULE=15 FIRST_PASS_CPU=1, which is 15 CPU s for each of INIT, RULE and DET.
"""
import hashlib
import json
import os
import re
import sys

sys.dont_write_bytecode = True
BASE_JOBS = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/search-worker/kits/search-refit-r1-jobs-heldout37-ramp22-2seeds-600s.txt'
BASE_TAR_SHA = '43600cbbfaa36af2599f681046edbac522138a7cb07425d2e0e4e946786a8176'
GOLD_DUPS = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad/gold-dups/'
PASS = 'FIRST_PASS_SECONDS=15 FIRST_PASS_RULE=15 FIRST_PASS_CPU=1 '
LINE = re.compile(r'^(?P<head>.*?)\./run3600\.sh (?P<task>\w+) (?P<arm>\w+) (?P<models>\S+) (?P<seconds>\d+)\s*$')
JOBS_NAME = 'search-pass-r1-jobs-heldout37-ramp22-2seeds-600s.txt'
OLD_JOBS = 'search-refit-r1-jobs-heldout37-ramp22-2seeds-600s.txt'
CHECK_SECONDS = 120
EDITED = {'model/study/sampler/superdag.py', 'model/study/sampler/superdag_search.py', 'model/study/sampler/kaggle_worker.py'}
REMOVED = {OLD_JOBS, 'positives-jobs.txt'}  # the round 1 jobs file and the positives file stay out of the pass kit
ADDED = {JOBS_NAME}


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def parse(line):
    m = LINE.match(line.strip())
    assert m, line
    return m


def make(m, arm, extra='', seconds=None):
    """The line of m with extra environment before ./run3600.sh, the arm renamed, and optionally other seconds."""
    return '%s%s./run3600.sh %s %s %s %s' % (m['head'], extra, m['task'], arm, m['models'], seconds or m['seconds'])


def tree(root):
    """The files under root, without the AppleDouble files (._*) that the round 1 tar holds and the pass kit leaves out."""
    return {os.path.relpath(os.path.join(d, f), root) for d, _, fs in os.walk(root) for f in fs if not f.startswith('._')}


def main():
    base, kit, out = (os.path.abspath(x) for x in sys.argv[1:4])
    lines = [x.strip() for x in open(BASE_JOBS) if x.strip()]
    assert len(lines) == 3 + 4 * 59, len(lines)
    parity, rest = lines[:2], lines[3:]
    assert all(parse(x)['arm'] in ('parity_s0', 'parity_s1') for x in parity) and parse(lines[2])['arm'] == 'refitcheck_s0'
    bundles = [x for x in rest if parse(x)['arm'] in ('bundle_s0', 'bundle_s1')]
    assert len(bundles) == 118 and all(parse(x)['seconds'] == '600' for x in bundles)
    first = parse(bundles[0])
    assert first['arm'] == 'bundle_s0' and first['task'] == parse(lines[0])['task']
    check = parity + [make(first, 'passcheck_s0', PASS, CHECK_SECONDS)]
    body = []
    for x in bundles:
        m = parse(x)
        seed = m['arm'].rsplit('_s', 1)[1]
        body += [x, make(m, 'pass_s%s' % seed, PASS)]
    jobs = check + body
    assert len(jobs) == 3 + 236
    # each pass line is its bundle line plus the pass settings; the bundle lines are the round 1 lines
    assert [x for x in jobs[3:] if parse(x)['arm'].startswith('bundle')] == bundles
    for b, p in zip(jobs[3::2], jobs[4::2]):
        mb, mp = parse(b), parse(p)
        assert mp['arm'] == mb['arm'].replace('bundle', 'pass') and mp['head'] == mb['head'] + PASS and (mp['task'], mp['models'], mp['seconds']) == (mb['task'], mb['models'], mb['seconds'])
        assert p == b.replace('./run3600.sh', PASS + './run3600.sh').replace(' %s ' % mb['arm'], ' %s ' % mp['arm']), (b, p)
    text = ''.join(x + '\n' for x in jobs)
    smoke = []
    for x in open(base + '/smoke-jobs.txt'):
        if x.strip():
            m = parse(x)
            if m['arm'] == 'smokebundle_s0':
                smoke += [x.strip(), make(m, 'smokepass_s0', PASS)]
    assert len(smoke) == 4 and not any('NODE_SCORE' in x for x in smoke) and [parse(x)['task'] for x in smoke] == ['135a2760', '135a2760', '74dd1130', '74dd1130']
    assert all(parse(x)['seconds'] == '180' and 'SAME_POD=smoke ' in x for x in smoke)
    os.makedirs(out, exist_ok=True)
    for name in REMOVED:
        if os.path.exists(kit + '/' + name):
            os.remove(kit + '/' + name)
    for d in (kit, out):
        open(d + '/' + JOBS_NAME, 'w').write(text)
        open(d + '/smoke-jobs.txt', 'w').write(''.join(x + '\n' for x in smoke))
    # the kit against the round 1 kit: only the planned files differ
    a, b = tree(base), tree(kit)
    changed = {f for f in a & b if open(base + '/' + f, 'rb').read() != open(kit + '/' + f, 'rb').read()}
    plan = EDITED | {'manifest.json', 'smoke-jobs.txt'}
    problems = []
    if b - a != ADDED:
        problems.append('new files %s' % sorted((b - a) ^ ADDED))
    if a - b != REMOVED:
        problems.append('removed files %s' % sorted((a - b) ^ REMOVED))
    if changed - {'manifest.json'} != plan - {'manifest.json'}:
        problems.append('changed files %s' % sorted((changed - {'manifest.json'}) ^ (plan - {'manifest.json'})))
    if problems:
        raise SystemExit('kit differs from the plan: ' + '; '.join(problems))
    man = json.load(open(base + '/manifest.json'))
    dups = {n: sha(GOLD_DUPS + n) for n in ('gold-dups.patch', 'gold-dups-search.patch', 'dups.json')}
    man['what'] = ('round r1 of the first pass: the bundle (ORDER_FREE=tie,key, models-tk) against the same kit with a one-time empty-scope best-first pass of 15 CPU s for each of INIT, RULE and DET '
                   'at the start of each task (45 CPU s in all, 7.5% of 600 s), no patience inside it; two seeds (0 and 1000) on the 37 held-out tasks and the 22 ramp tasks at 600 s; '
                   'a task\'s 4 lines run on one pod')
    man['commit'] = ('search-refit-r1-kit-0729e4943 (sha256 %s) with: (1) the gold-dups patches (a cover event for every gold index of a table key; both arms), (2) in model/study/sampler/superdag_search.py '
                     'FIRST_PASS_CPU (the budgets of the pass are CPU seconds of time.process_time) and the fields forms, exhausted, budget and by_cpu in the `first pass` event, (3) in '
                     'model/study/sampler/kaggle_worker.py a log line `first pass <json>` for each `first pass` event; NODE_SCORE unset in bundle and pass' % BASE_TAR_SHA)
    man['arm'] = {'bundle': 'models-tk, seeds 0 and 1000, 59 tasks',
                  'pass': 'bundle plus FIRST_PASS_SECONDS=15 FIRST_PASS_RULE=15 FIRST_PASS_CPU=1',
                  'parity': 'NODE_SCORE=scores/ship.npz NODE_SCORE_CHECK=1',
                  'passcheck': 'pass at 120 s on the first task', 'smokebundle': 'bundle at 180 s', 'smokepass': 'pass at 180 s'}
    man['budget'] = ('%d lines: 3 check lines (2 parity at 600 s, 1 passcheck at %d s), then 236 lines of bundle and pass on 59 tasks at 2 seeds, 600 s wall; smoke 4 lines at 180 s' % (3 + 236, CHECK_SECONDS))
    man['pass'] = dict(
        settings='FIRST_PASS_SECONDS=15 FIRST_PASS_RULE=15 FIRST_PASS_CPU=1: 15 CPU s of time.process_time for each of INIT, RULE and DET, 45 CPU s in all, 7.5% of a 600 s run',
        kinds='INIT, RULE, DET, in that order, on the empty scope, with no patience',
        choice=('from the direct run on the 19 stuck roots (runs/search-root-direct-19-60cpus-mac/read.txt, 60 CPU s per root): 17 of 19 roots took; 14 of the 17 takes came within 5 CPU s, '
                '16 within 15 CPU s, and 17 within 60 CPU s (the last, c4d067a0 g3 RULE, at 55.19 CPU s). 15 CPU s per kind covers 16 of the 17 takes; the takes within 15 CPU s are '
                'aa4ec2a5 g4 g9 g10 (DET, 0.00 to 0.04), db695cfb g25 (RULE, 0.06), c7f57c3e g0 (INIT, 0.13), 135a2760 g1 (RULE, 0.32), b99e7126 g1 (RULE, 0.46), dfadab01 g4 (DET, 0.83), '
                'e3721c99 g0 (DET, 0.94), d59b0160 g23 (DET, 2.33), 135a2760 g8 (RULE, 2.47), 5961cc34 g16 (RULE, 2.84), b5ca7ac4 g0 (DET, 2.96), b99e7126 g8 (RULE, 3.77), '
                'db695cfb g7 and g3 (RULE, 11.9). The 8 real misses are those 17 takes less the 9 duplicate-table forms (by gold-dups/dups.json: the take shares its table with a lower-indexed gold form that is not a take) aa4ec2a5 g4 g9 g10, dfadab01 g4, db695cfb g25, 135a2760 g1 g8 and b99e7126 g1 g8; they are c7f57c3e g0, e3721c99 g0, d59b0160 g23, 5961cc34 g16, b5ca7ac4 g0, db695cfb g3 and g7, c4d067a0 g3; 7 of the 8 are within 15 CPU s (c4d067a0 g3 is at 55.19).'),
        clock=('the pass ends a kind by time.process_time() (FIRST_PASS_CPU=1). A visit of the search ends at most that many wall seconds from the visit start, since CPU time does not pass '
               'faster than wall time, and the loop goes on until the CPU budget is spent. The visit limit SEARCH_VISIT_SECONDS (4 s wall) still ends each visit.'),
        runs_once='grow_first runs the pass only where the pool has no form; a renewed worker reads its bank file, has forms, and skips it. A worker that starts with an empty bank runs it again.')
    man['bundle_settings'] = dict(man['bundle_settings'], **{'left at the kernel\'s defaults': 'ARC_RENEW_SHARE .6, STEER_COVER unset, OUT_PAIRS and OUT_CANDS unset, SEARCH_NEW_TABLE, SEARCH_FREE_STOP, FIRST_PASS_SECONDS (unset in bundle lines), KIND_SHARE empty'})
    man['gold_dups'] = dict(patches=dups, note='both patches applied to the pass kit and the bundle runs in it: model/study/sampler/superdag.py and superdag_search.py')
    man['node_records'] = 'none'
    man['training_eligibility'] = 'the 37 are held out; the 22 ramp tasks are training tasks of models-tk, not of the node score'
    man['reads'] = [x for x in man['reads'] if 'n600' not in x and 'N600' not in x and x != 'scores/refit.npz']
    man['arm_files'] = [JOBS_NAME, 'smoke-jobs.txt']
    man.pop('refit', None)
    man['pass_kit'] = dict(base='search-refit-r1-kit-0729e4943', base_sha256=BASE_TAR_SHA, removed=sorted(REMOVED), edited=sorted(EDITED),
                           sha256={f: sha(kit + '/' + f) for f in sorted(EDITED)})
    json.dump(man, open(kit + '/manifest.json', 'w'), indent=1)
    shutil_copy(kit + '/manifest.json', out + '/manifest.json')
    print('jobs %d lines, smoke %d lines; kit differs from the round 1 kit in %s, adds %s, removes %s' % (len(jobs), len(smoke), sorted(changed | {'smoke-jobs.txt'}), sorted(ADDED), sorted(REMOVED)))


def shutil_copy(a, b):
    open(b, 'wb').write(open(a, 'rb').read())


main()
