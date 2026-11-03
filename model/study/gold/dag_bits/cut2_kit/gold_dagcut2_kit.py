"""Builds the pod kit of stage `dagcut2` (the DAG split cut, tool 2, version 2, on the 1,011 training stems of the pod kit): writes gold-v3-dagcut2-kit.tar.gz, its sha256 and manifest.json in this folder. Plain python3, no engine.

  python3 gold_dagcut2_kit.py prepare          lines.json (from the base tar), tasks.txt, skipped.txt, weights.json, base-rows.json, check-task.txt
  python3 gold_dagcut2_kit.py mac99            mac99/: tasks.txt, weights.json, base-rows.json for the 99 less the stems with an incomplete pod row
  python3 gold_dagcut2_kit.py expect ROWS      check-expected.json from the Mac's row of the check stem (ROWS: the runner's rows file)
  python3 gold_dagcut2_kit.py refit ROWS...    refit.json: the estimate refit from the cpu of mac99 rows against the pod cpu
  python3 gold_dagcut2_kit.py choose ROWS...   check-task.txt: the mac99 stem with a commit and the least cpu (default 409aa875)
  python3 gold_dagcut2_kit.py build            the kit tar; check-expected.json has to exist

The base kit is dag-pod/gold-v3-dag-pod-kit.tar.gz. Its wheel, models, data/tasks, model/study/sampler and lines.json are kept byte for byte, so there is no new pin and the pod rows stay valid as start figures.
"""
import glob, hashlib, json, os, random, shutil, statistics, subprocess, sys, tarfile, time, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.dirname(HERE)
R = '/Users/davidlu/code/arc-workspace/'
D = R + 'work/lm/data-study/'
G = D + 'gold/'
PODALL = G + 'gold-v3-dag-bits/pod-all/'
RAMP = G + 'gold-heldout-ramp-pass1/ramp-fold.txt'
BASE = S + '/dag-pod/gold-v3-dag-pod-kit.tar.gz'
BASE_NAME = 'gold-v3-dag-pod-kit'
BASE_MANIFEST = S + '/dag-pod/manifest.json'
TASKS99 = S + '/dag-kit/tasks99.txt'
NAME = 'gold-v3-dagcut2-kit'
SUPERDAG = D + 'sampler/search-worker/poolsearch/superdag.py'
SUPERDAG_SHA256 = "19d1f8bcf8f53a0075fc7246076bf59bbb5a1a4867c49ac62175ff5862f9e447"
POD_CODE = 'ddafd4ecfa4a'
CHECK_STEM = open(HERE + '/check-task.txt').read().split()[0] if os.path.exists(HERE + '/check-task.txt') else '409aa875'  # `choose` writes check-task.txt
SHARDS = 16
CODE = ('gold_chain.py', 'gold_orcut_cuts.py', 'gold_shapecut_cuts.py', 'gold_shapecut_shapes.py', 'gold_shapecut_one.py', 'gold_fork_reads.py', 'gold_dag_orders.py', 'gold_dag_cuts.py', 'gold_dag_bits.py',
        'gold_pod_bits.py', 'gold_pod_run.py', 'gold_pod_check.py', 'gold_dagcut2_one.py', 'gold_dagcut2_run.py', 'gold_dagcut2_check.py')
DAG_FILES = ('gold_dagcut2_one.py', 'gold_dag_cuts.py', 'gold_dag_orders.py')
KEEP = ('lines.json', 'golds-stub.json', 'wheel-so-sha256.txt')
SETUP = 'ORCUT_SO_SHA256=${ORCUT_SO_SHA256-$(cat wheel-so-sha256.txt)} SAMPLER_CODE=$kit/model/study/sampler SEARCH_MODELS=$kit/models SEARCH_GOLDS=$kit/golds-stub.json ARC_ROOT=$kit PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 RAYON_NUM_THREADS=1 ARCLOG_THREADS=1 PYTHONPATH=$kit:$kit/model/study/sampler:${EXTRA_PATH:-}'
RUN = """#!/bin/bash
# run.sh SHARDS: the stage `dagcut2`, stem by stem, in SHARDS processes, from the kit's top folder, with $PY set. A restart skips finished stems, with any shard count. Each stem has 900 s and 8 GiB over its process group (soft end 840 s), with no retry at a higher bound. A form has at most POD_FORM_SECONDS (120). Rows: out/rows-<k>.jsonl.
n=${1:?shards}; kit=$PWD
mkdir -p out
for k in $(seq 0 $((n - 1))); do
  ( %s POD_FORM_SECONDS=120 \\
    "$PY" -u gold_dagcut2_run.py tasks.txt lines.json weights.json base-rows.json out/rows-$k.jsonl $k "$n" >> out/rows-$k.log 2>&1 ) &
done
wait
""" % SETUP
CHECK = """#!/bin/bash
# check.sh [SHARDS]: from the kit's top folder, with $PY set. Reads the wheel, /proc and the limits for SHARDS shards (default 16), tests the group memory count, the cap and the reaping, then runs the check stem through the runner as run.sh does and compares its row with the Mac's. Exits 1 at the first failure.
n=${1:-16}; kit=$PWD
set -e
rm -rf out-check
mkdir out-check
export %s POD_FORM_SECONDS=120
"$PY" -u gold_pod_check.py limits "$n"
"$PY" -u gold_pod_check.py group
"$PY" -u gold_dagcut2_run.py check-task.txt lines.json weights.json base-rows.json out-check/rows-check.jsonl 0 1
"$PY" -u gold_dagcut2_check.py rows out-check/rows-check.jsonl check-expected.json
echo "check ok"
""" % SETUP


def sha_of(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while b := f.read(1 << 20):
            h.update(b)
    return h.hexdigest()


def line_sha(ls):
    return hashlib.sha256('\n'.join(ls).encode()).hexdigest()[:16]


def tree_hash(d):
    return hashlib.sha256(b''.join(open(p, 'rb').read() for p in sorted(glob.glob(d + '/**/*.py', recursive=True)))).hexdigest()[:12]


def dag_code():
    return hashlib.sha256(b''.join(open(HERE + '/' + f, 'rb').read() for f in DAG_FILES)).hexdigest()[:12]


def pod_rows():
    rows = {}
    for p in sorted(glob.glob(PODALL + 'rows-*.jsonl')):
        for l in open(p):
            try:
                r = json.loads(l)
                rows[r['task']] = r
            except (json.JSONDecodeError, KeyError):
                continue
    return rows


def why_incomplete(r):
    """None where the pod row is complete: finished, no late, no error, no form unread; else why."""
    if r is None:
        return 'no pod row'
    if r.get('error'):
        return 'error %s' % r['error']
    if r.get('late'):
        return 'late'
    if not r.get('finished'):
        return 'not finished'
    n = sum(1 for f in r['forms'] if f['status'] == 'unread')
    return '%d forms unread' % n if n else None


def entry(r):
    """The start figures of a pod row, as base-rows.json holds them: [line, bits, status, scope_sha, fcol] for each form."""
    return dict(base_sha=r['base_sha'], forms=[[f['line'], f['bits'], f['status'], f.get('scope_sha'), f['status'] == 'none' and any('fcol' in str(b) for b in f.get('bad') or ())] for f in r['forms']])


def base_lines():
    with tarfile.open(BASE) as t:
        raw = t.extractfile(BASE_NAME + '/lines.json').read()
    open(HERE + '/lines.json', 'wb').write(raw)
    return json.loads(raw)


def checked(text, rows, stems):
    """Stops the build where a pod row of a stem is not on the stem's text or not from the pinned code."""
    for t in stems:
        r = rows.get(t)
        if r is None:
            continue
        if r.get('base_sha') != line_sha([x for x in text[t] if x.strip()]):
            sys.exit('the base_sha of %s is not the hash of its lines' % t)
        if r.get('code') != POD_CODE:
            sys.exit('the row of %s has code %s, not %s' % (t, r.get('code'), POD_CODE))


def write_tasks(path, tiers):
    open(path, 'w').write('\n\n'.join('\n'.join(x) for x in tiers if x) + '\n')


def prepare():
    text = base_lines()
    rows = pod_rows()
    stems99 = set(open(TASKS99).read().split())
    train = sorted(set(text) - stems99)
    checked(text, rows, train)
    if CHECK_STEM not in text or CHECK_STEM in train:
        sys.exit('the check stem is not one of the 99')
    complete = [t for t in train if why_incomplete(rows.get(t)) is None]
    skipped = {t: why_incomplete(rows.get(t)) for t in train if t not in complete}
    ramp = set(open(RAMP).read().split())
    heavy = lambda ts: sorted(ts, key=lambda t: (-rows[t]['cpu'], t))
    tiers = [heavy([t for t in complete if t in ramp]), heavy([t for t in complete if t not in ramp])]
    write_tasks(HERE + '/tasks.txt', tiers)
    open(HERE + '/skipped.txt', 'w').write(''.join('%s %s\n' % (t, w) for t, w in sorted(skipped.items())))
    weights = {t: rows[t]['cpu'] for t in complete + [CHECK_STEM]}
    json.dump(weights, open(HERE + '/weights.json', 'w'))
    json.dump({t: entry(rows[t]) for t in complete + [CHECK_STEM]}, open(HERE + '/base-rows.json', 'w'))
    if not os.path.exists(HERE + '/check-task.txt'):
        open(HERE + '/check-task.txt', 'w').write(CHECK_STEM + '\n')
    print(len(text), 'stems in the base kit;', len(train), 'training stems;', len(complete), 'to run, tiers', [len(x) for x in tiers], ';', len(skipped), 'skipped', sorted(skipped.items())[:3], '...')
    print('pod cpu of the stems to run: %.2f h; of the skipped: %.2f h' % (sum(rows[t]['cpu'] for t in complete) / 3600, sum(rows[t]['cpu'] for t in skipped if t in rows) / 3600))
    return complete, skipped, rows


def mac99():
    text = base_lines()
    rows = pod_rows()
    stems99 = [x for x in open(TASKS99).read().split()]
    checked(text, rows, stems99)
    ok = [t for t in stems99 if why_incomplete(rows.get(t)) is None]
    out = HERE + '/mac99'
    os.makedirs(out, exist_ok=True)
    write_tasks(out + '/tasks.txt', [sorted(ok, key=lambda t: (-rows[t]['cpu'], t))])
    json.dump({t: rows[t]['cpu'] for t in ok}, open(out + '/weights.json', 'w'))
    json.dump({t: entry(rows[t]) for t in ok}, open(out + '/base-rows.json', 'w'))
    open(out + '/skipped.txt', 'w').write(''.join('%s %s\n' % (t, why_incomplete(rows.get(t))) for t in stems99 if t not in ok))
    print(len(stems99), 'stems of the 99;', len(ok), 'to run;', len(stems99) - len(ok), 'with an incomplete pod row:', [t for t in stems99 if t not in ok])


def expect(path):
    rows = []
    for l in open(path):
        try:
            r = json.loads(l)
        except json.JSONDecodeError:
            continue
        if r.get('task') == CHECK_STEM:
            rows.append(r)
    r = rows[-1]
    if r.get('error') or not r.get('finished') or r.get('skipped'):
        sys.exit('the row of the check stem is not a finished row: error %s finished %s skipped %s' % (r.get('error'), r.get('finished'), r.get('skipped')))
    if not r.get('landed'):
        print('WARNING: the check stem %s has no commit, so check.sh does not test a landing or the handover. Run mac99.sh first: it picks a stem that commits.' % CHECK_STEM)
    json.dump([dict(task=CHECK_STEM, row=r)], open(HERE + '/check-expected.json', 'w'))
    print('check-expected.json:', CHECK_STEM, 'steps', len(r['steps']), 'committed', [k for k, s in enumerate(r['steps']) if s['committed']], 'worst', r['before']['worst'], '->', r['after']['worst'])


def last_rows(paths):
    last = {}
    for pat in paths:
        for p in glob.glob(pat):
            for l in open(p):
                try:
                    r = json.loads(l)
                except json.JSONDecodeError:
                    continue
                if r.get('task') and r.get('stage') == 'dagcut2':
                    last[r['task']] = r
    return last


def choose(paths):
    """check-task.txt: the stem of the mac99 rows with a commit and the least cpu (finished, no late, no error, handover held)."""
    got = sorted((r['cpu'], t) for t, r in last_rows(paths).items() if r.get('landed') and r.get('finished') and not r.get('late') and not r.get('error') and not r.get('program_fail'))
    if not got:
        print('WARNING: no stem of the 99 has a commit with a handover that held; the check stem stays %s' % CHECK_STEM)
        return
    open(HERE + '/check-task.txt', 'w').write(got[0][1] + '\n')
    print('check stem', got[0][1], 'cpu', got[0][0], '; stems with a commit:', len(got), [t for _, t in got[:8]])


def refit(paths):
    """The estimate redone from the cpu of the mac99 rows against the pod cpu of the same stems."""
    pod = pod_rows()
    last = last_rows(paths)
    ratios, landed, rest = [], [], []
    for t, r in last.items():
        if r.get('skipped') or r.get('error') or t not in pod or not pod[t]['cpu']:
            continue
        x = (r.get('cpu') or 0) / pod[t]['cpu']
        ratios.append(x)
        (landed if r.get('landed') else rest).append(x)
    complete = [t for t in pod if t in json.load(open(HERE + '/weights.json')) and t != CHECK_STEM]
    cpus = [pod[t]['cpu'] for t in complete]
    rng = random.Random(1)
    totals = {}
    for name, factor in (('mac_ratio', 1.0), ('with_pod_over_mac_2_23', 2.23)):
        sums = sorted(sum(min(900.0, rng.choice(ratios) * factor * c) for c in cpus) / 3600 for _ in range(200))
        totals[name] = dict(cpu_h_mean=round(statistics.mean(sums), 2), cpu_h_5_95=[round(sums[10], 2), round(sums[189], 2)], wall_min_at_16=round(statistics.mean(sums) * 3600 * 1.06 / 16 * 1.2 / 60, 1))
    got = dict(stems=len(ratios), landed=len(landed), ratio_v2_mac_cpu_over_pod_cpu=dict(median=round(statistics.median(ratios), 3), landed_median=round(statistics.median(landed), 3) if landed else None, others_median=round(statistics.median(rest), 3) if rest else None,
               max=round(max(ratios), 3)), stems_estimated=len(complete), pod_cpu_h_of_those=round(sum(cpus) / 3600, 2), estimate=totals, note='ratios drawn at random for each stem, times the stem pod cpu, capped at 900 s; wall is cpu times 1.06 over 16 times 1.2; the second line scales the Mac cpu by the pod over Mac factor 2.23 of the design')
    json.dump(got, open(HERE + '/refit.json', 'w'), indent=1)
    print(json.dumps(got, indent=1))


def build():
    complete, skipped, rows = prepare()
    if not os.path.exists(HERE + '/check-expected.json'):
        sys.exit('check-expected.json does not exist: run expect')
    work = HERE + '/kit-build'
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    with tarfile.open(BASE) as t:
        t.extractall(work, filter='data')
    kit = work + '/' + NAME
    os.rename(work + '/' + BASE_NAME, kit)
    for f in os.listdir(kit):
        if f.startswith('gold_') or f in ('tasks.txt', 'weights.json', 'run.sh', 'check.sh', 'manifest.json', 'check-task.txt', 'check-expected.json', 'base-rows.json', 'skipped.txt'):
            os.remove(kit + '/' + f)
    shutil.rmtree(kit + '/out', ignore_errors=True)
    # The base kit has no superdag.py (the pin has none, and the pod kit build left out the combined kit's top-level copy). gold_shapecut_one imports it: the copy that the Mac runs, which is the combined kit's top-level one.
    if sha_of(SUPERDAG) != SUPERDAG_SHA256:
        sys.exit('superdag.py of poolsearch is not the file of the combined kit')
    shutil.copy(SUPERDAG, kit + '/superdag.py')
    for f in ('tasks.txt', 'skipped.txt', 'weights.json', 'base-rows.json', 'check-task.txt', 'check-expected.json'):
        shutil.copy(HERE + '/' + f, kit + '/' + f)
    for f in CODE:
        shutil.copy(HERE + '/' + f, kit + '/' + f)
    open(kit + '/run.sh', 'w').write(RUN)
    open(kit + '/check.sh', 'w').write(CHECK)
    base = json.load(open(BASE_MANIFEST))
    for what, want in (('sampler tree', base['sampler_code']['tree_sha256']), ):
        if tree_hash(kit + '/model/study/sampler') != want:
            sys.exit('the %s of the kit is not the base kit\'s' % what)
    if sha_of(kit + '/lines.json') != base['base_text']['lines_sha256']:
        sys.exit('lines.json of the kit is not the base kit\'s')
    for p in glob.glob(kit + '/**/._*', recursive=True):
        os.remove(p)
    out = HERE + '/%s.tar.gz' % NAME
    refit_json = json.load(open(HERE + '/refit.json')) if os.path.exists(HERE + '/refit.json') else None
    est = dict(basis='tool 2 CPU over old tool 1 CPU by stem, 97 stems: median 0.11, 0.94 on landed stems, 0.07 on others; drawn at random for each of the 996 stems, times the stem pod CPU, capped at 900 s: 4.5 CPU h (3.6 to 5.3) for the first pass; v2: landed stems are 65% of tool 2 CPU, the reader saving and VERIFY 3 take that part to about 0.55, so 0.71 of 4.5',
               central=dict(cpu_h=3.2, wall_at_16='about 20 min'), range=dict(cpu_h='2.5 to 5.5', wall_at_16='15 to 30 min'), if_each_stem_costs_what_tool_1_cost=dict(cpu_h=11, wall_at_16='44 min'),
               wall='CPU times 1.06 (pod wall over CPU in pod-all) over 16, and a factor of 1.2 for balance; a 900 s stem sets a floor of 15 minutes; check.sh a few minutes more', verify_share='a guess with no measurement', refit_from_mac99=refit_json if refit_json else 'not run: mac99.sh writes refit.json, then rebuild')
    settings = dict(DAG_MARGIN='bits from the last commit at which a step commits, default 3', DAG_TENTATIVE='tentative steps in a row after which the stem stops, default 3', DAG_SCREEN_SLACK='default 8', DAG_START_READ='1 reads the start text instead of taking the pod row (order_check.sh)', POD_FORM_SECONDS='seconds for a form, default 120 (run.sh sets it)', POD_ORDER_CAP='default or_q.ORDER_CAP', POD_BUDGET='default or_q.ORDER_BUDGET')
    budget = '900 s and 8 GiB over the process group, a stem, with no retry at a higher bound; soft end at 840 s'
    measures = ['before and after of each stem on or_q.walk (field `after` is the last commit; `after_reads` is `working`)', 'steps with `committed`, the working text, shape, rank, estimate, new forms with bits', 'program (N) of the last commit and program_fail', 'rows_differ and rows_columns of each step', 'kept_out, counts (fields retried, start forms read again), cpu, wall, peak GiB and processes']
    residue = 'form_orders treats an unmarked `=` in an OR as a guard and a marked `=` as a binder, so the same form in two written orders can have two order sets. 422 of 24,743 forms have an OR and a `=`. It is in the sampler at the pin and v2 does not fix it; it shows only between two written forms of one start text.'
    m = dict(job='gold-v3-dagcut2', purpose='the DAG split cut (tool 2, version 2) on the training stems of the pod kit: every landing figure by or_q.walk, start figures from the pod rows, steps tentative and committed on a margin', settings=settings, budget=budget, measures=measures,
             task_set='tasks.txt, %d stems: the %d training stems of the pod kit (1,110 less the 99) with a complete pod row; ramp-fold stems first, then the others, heaviest first by pod cpu' % (len(complete), len(complete) + len(skipped)),
             skipped=dict(count=len(skipped), file='skipped.txt', rule='the pod row is not complete (error, late, not finished, or a form unread): each spent its 840 s or its memory in tool 1 alone', stems=sorted(skipped)),
             margin=dict(rule='commit where the forms with no bits fall, or stay and the worst form is DAG_MARGIN under the last commit; stop after DAG_TENTATIVE tentative steps; the stem result is the last commit', DAG_MARGIN=3, DAG_TENTATIVE=3),
             after_reads='working: `before`, `after` and every step read W, the pruned cut text. `program` is N (handover text) whose own figures differ from W\'s; for them run gold_pod_run.py with POD_PREFIX=0 on a lines file of the programs', equals_residue=residue,
             sampler_code=base['sampler_code'], wheel_engine=base['wheel_engine'], priors=base['priors'], pin='no new pin: the wheel, models, data/tasks, model/study/sampler and lines.json are the base kit\'s, byte for byte',
             dag_code=dict(hash=dag_code(), hash_of=' '.join(DAG_FILES) + ', as row field `dag_code`'), estimate=est, shards=SHARDS,
             run='pip install the wheel, then PY=<python> bash check.sh 16, then PY=<python> bash run.sh 16', records='out/rows-<k>.jsonl, one row per stem, field `stage` dagcut2; resumable with any shard count, key (dagcut2, task, base_sha, cap, budget, margin)',
             processes='a stem has its own process and one idle root process (F.begin); no read forks', failed_stems='A stem past 900 s or 8 GiB keeps its last streamed row, with error set. No rerun at a higher bound.', reads=list(CODE) + ['lines.json', 'tasks.txt', 'weights.json', 'base-rows.json', 'check-task.txt', 'check-expected.json'])
    json.dump(m, open(kit + '/manifest.json', 'w'), indent=1)
    subprocess.check_call(['tar', 'czf', out, '-C', work, NAME], env=dict(os.environ, COPYFILE_DISABLE='1'))
    sha = sha_of(out)
    open(out + '.sha256', 'w').write('%s  %s.tar.gz\n' % (sha, NAME))
    commit = subprocess.run(['git', '-C', R, 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    json.dump(dict(m, command='PY=<python> bash check.sh 16; PY=<python> bash run.sh 16, in the kit', commit=commit, built=time.strftime('%Y-%m-%dT%H:%M:%S%z'), machine='pod; on the Mac, gold_dagcut2_env.sh runs the code on runtime-ba0754492',
                        kit=dict(file=NAME + '.tar.gz', sha256=sha, bytes=os.path.getsize(out), stems=len(complete), shards=SHARDS, check_stem=CHECK_STEM)), open(HERE + '/manifest.json', 'w'), indent=1)
    shutil.rmtree(work)
    print(out, os.path.getsize(out), 'sha256', sha)
    print(len(complete), 'stems', 'skipped', len(skipped), 'check stem', CHECK_STEM, 'dag_code', dag_code())


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'build'
    if what == 'expect':
        expect(sys.argv[2])
    elif what == 'refit':
        refit(sys.argv[2:])
    elif what == 'choose':
        choose(sys.argv[2:])
    else:
        {'prepare': prepare, 'mac99': mac99, 'build': build}[what]()
