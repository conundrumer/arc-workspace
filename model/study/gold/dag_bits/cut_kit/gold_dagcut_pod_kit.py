"""Builds the pod kit of stage `dagcut` (the DAG split cut, tool 2, on the training stems of view-final): writes gold-v3-dagcut-pod-kit.tar.gz, its sha256 and manifest.json in this folder.

  python3 gold_dagcut_pod_kit.py prepare   copies the stage code into this folder and writes lines.json, weights.json, tasks.txt, skipped.txt (for the Mac check run)
  python3 gold_dagcut_pod_kit.py build     does prepare, then builds the tar; check-task.txt and check-expected.json have to exist (gold_dagcut_pod_check.py expect)

Stems: every folder of view-final that is not in features-worker/arm/eval-tasks.txt. Text: the first row's gold_sexp of <stem>/pairs.jsonl.gz.
Skipped: a stem whose pod-all row (gold-v3-dag-bits/pod-all/rows-*.jsonl, tool 1) has the start text's base_sha, is finished with no error and no late flag, has bits on every form that draws, and has its worst form under 13 bits. Nothing would land for the bar there. A stem at a cap in pod-all is not skipped, and runs with the usual cap.
Order: one tier, heaviest first by the stem's `cpu` in its pod-all row (dag-kit/weights.json, scaled to the rows' cpu, for a stem with no row).
Code: the stage files come from dag-kit (gold_dag_*.py, gold_dagcut_one.py, gold_fork_reads.py) and combined-kit (the rest). The sampler is orcut-fast/kit-model, pinned by hash. The kit's layout, wheel, engine/lib and priors come from the combined kit's tar.
"""
import glob, gzip, hashlib, json, os, shutil, subprocess, sys, tarfile, time, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.dirname(HERE)
R = '/Users/davidlu/code/arc-workspace/'
D = R + 'work/lm/data-study/'
G = D + 'gold/'
VIEW = G + 'gold-v3-combined-cut/view-final/'
PODALL = G + 'gold-v3-dag-bits/pod-all/'
EVAL = D + 'features-worker/arm/eval-tasks.txt'
MODELS = D + 'sampler/sampler-worker/sampler-helper-forms/gold-v3-helper-forms-a036da074/models-base'
BASE = S + '/combined-kit/gold-v3-combined-cut-kit.tar.gz'
BASE_NAME = 'gold-v3-combined-cut-kit'
SAMPLER = S + '/orcut-fast/kit-model/study/sampler'
SAMPLER_HASH = '9467760e0a14'
DAG_KIT = S + '/dag-kit/'
COMBINED = S + '/combined-kit/'
WEIGHTS_FALLBACK = DAG_KIT + 'weights.json'
WHEEL = 'arclog-0.1.0-cp312-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl'
WHEEL_SHA256 = 'eeebf281685646614e0935a8ac976aa6099c6b1dc1f4e1bb3499df0aabaef57d'
NAME = 'gold-v3-dagcut-pod-kit'
SHARDS, UNDER = 16, 13.0
FROM_DAG = ('gold_dag_run.py', 'gold_dagcut_one.py', 'gold_dag_cuts.py', 'gold_dag_bits.py', 'gold_dag_orders.py', 'gold_fork_reads.py')
FROM_COMBINED = ('gold_combined_run.py', 'gold_combined_check.py', 'gold_chain.py', 'gold_orcut_one.py', 'gold_extcut_cuts.py', 'gold_shapecut_one.py', 'gold_shapecut_cuts.py', 'gold_shapecut_shapes.py', 'gold_orcut_cuts.py', 'gold_orcut_base.py')
OWN = ('gold_dagcut_pod_check.py',)
CODE = FROM_DAG + FROM_COMBINED + OWN
DAG_FILES = ('gold_dag_orders.py', 'gold_dag_bits.py', 'gold_dag_cuts.py', 'gold_dagcut_one.py')
SETUP = 'DAG_STAGES=dagcut ORCUT_KEPT_NODES=${ORCUT_KEPT_NODES-48} ORCUT_SO_SHA256=${ORCUT_SO_SHA256-$(cat wheel-so-sha256.txt)} SAMPLER_CODE=$kit/model/study/sampler SEARCH_MODELS=$kit/models SEARCH_GOLDS=$kit/golds-stub.json ARC_ROOT=$kit PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 RAYON_NUM_THREADS=1 ARCLOG_THREADS=1 PYTHONPATH=$kit:$kit/model/study/sampler:${EXTRA_PATH:-}'
RUN = """#!/bin/bash
# run.sh SHARDS: the stage `dagcut`, stem by stem, in SHARDS processes, from the kit's top folder, with $PY set. A restart skips finished stems, with any shard count. Each stem has 900 s and 8 GiB over its process group (soft end 840 s), with no retry at a higher bound. ORCUT_KEPT_NODES (default 48) bounds a stem's parked processes. Rows: out/rows-<k>.jsonl.
n=${1:?shards}; kit=$PWD
mkdir -p out
for k in $(seq 0 $((n - 1))); do
  ( %s \\
    "$PY" -u gold_dag_run.py tasks.txt lines.json weights.json out/rows-$k.jsonl $k "$n" >> out/rows-$k.log 2>&1 ) &
done
wait
""" % SETUP
CHECK = """#!/bin/bash
# check.sh [SHARDS]: from the kit's top folder, with $PY set. Reads the wheel, /proc and the limits for SHARDS shards (default 16), tests the group memory count, the cap and the reaping, then runs the check stem through the runner as run.sh does and compares its row with the Mac's. Exits 1 at the first failure.
n=${1:-16}; kit=$PWD
set -e
rm -rf out-check
mkdir out-check
export %s
"$PY" -u gold_dagcut_pod_check.py limits "$n"
"$PY" -u gold_dagcut_pod_check.py group
"$PY" -u gold_dag_run.py check-task.txt lines.json weights.json out-check/rows-check.jsonl 0 1
"$PY" -u gold_dagcut_pod_check.py rows out-check/rows-check.jsonl check-expected.json
echo "check ok"
""" % SETUP


def sha_of(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while b := f.read(1 << 20):
            h.update(b)
    return h.hexdigest()


def text_of(t):
    with gzip.open(VIEW + t + '/pairs.jsonl.gz', 'rt') as f:
        return [x for x in json.loads(f.readline())['gold_sexp'].splitlines() if x.strip()]


def line_sha(ls):
    return hashlib.sha256('\n'.join(ls).encode()).hexdigest()[:16]


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


def skippable(r, sha):
    """Whether the pod-all row r shows that no cut would land for the bar: the worst form is under 13 bits."""
    if r is None or r.get('base_sha') != sha or not r.get('finished') or r.get('error') or r.get('late'):
        return False
    nums = []
    for f in r['forms']:
        b = f.get('bits')
        if isinstance(b, (int, float)):
            nums.append(b)
        elif f.get('status') != 'no draw':
            return False
    return max(nums, default=0) < UNDER


def stage_text():
    ev = set(open(EVAL).read().split())
    stems = sorted(x for x in os.listdir(VIEW) if x not in ev and os.path.exists(VIEW + x + '/pairs.jsonl.gz'))
    text = {t: text_of(t) for t in stems}
    rows = pod_rows()
    skipped = {t: rows[t]['worst'] for t in stems if skippable(rows.get(t), line_sha(text[t]))}
    run = [t for t in stems if t not in skipped]
    old = json.load(open(WEIGHTS_FALLBACK))
    have = [t for t in run if t in rows]
    scale = sum(rows[t]['cpu'] for t in have) / max(1e-9, sum(old.get(t, 0) for t in have))
    weights = {t: round(rows[t]['cpu'], 1) if t in rows else round(old.get(t, 1.0) * scale, 1) for t in run}
    order = sorted(run, key=lambda t: (-weights[t], t))
    return stems, text, skipped, weights, order, [t for t in run if t not in rows], rows


def sync_code():
    for names, src in ((FROM_DAG, DAG_KIT), (FROM_COMBINED, COMBINED)):
        for f in names:
            shutil.copy(src + f, HERE + '/' + f)


def tree_hash(d):
    return hashlib.sha256(b''.join(open(p, 'rb').read() for p in sorted(glob.glob(d + '/**/*.py', recursive=True)))).hexdigest()[:12]


def sampler_hash(d):
    return hashlib.sha256(b''.join(open(d + '/' + f, 'rb').read() for f in ('live.py', 'or_q.py', 'search.py', 'search_gold.py', 'live_try.py'))).hexdigest()[:12]


def dag_code():
    return hashlib.sha256(b''.join(open(HERE + '/' + f, 'rb').read() for f in DAG_FILES)).hexdigest()[:12]


def prepare():
    stems, text, skipped, weights, order, norow, rows = stage_text()
    if sampler_hash(SAMPLER) != SAMPLER_HASH:
        sys.exit('the sampler of orcut-fast/kit-model is not %s' % SAMPLER_HASH)
    sync_code()
    json.dump({t: text[t] for t in order}, open(HERE + '/lines.json', 'w'))
    json.dump(weights, open(HERE + '/weights.json', 'w'))
    open(HERE + '/tasks.txt', 'w').write('\n'.join(order) + '\n')
    open(HERE + '/skipped.txt', 'w').write(''.join('%s %s\n' % (t, w) for t, w in sorted(skipped.items())))
    print(len(stems), 'training stems;', len(skipped), 'skipped (worst form under %g bits in pod-all);' % UNDER, len(order), 'to run;', len(norow), 'with no pod-all row; top weights', [weights[t] for t in order[:3]])
    return stems, text, skipped, weights, order, rows


def build():
    stems, text, skipped, weights, order, rows = prepare()
    check_stem = open(HERE + '/check-task.txt').read().strip()
    if check_stem not in weights:
        sys.exit('the check stem is not a stem to run')
    work = HERE + '/kit-build'
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    with tarfile.open(BASE) as t:
        t.extractall(work, filter='data')
    kit = work + '/' + NAME
    os.rename(work + '/' + BASE_NAME, kit)
    for f in os.listdir(kit):
        if f.startswith('gold_') or f in ('lines.json', 'tasks.txt', 'weights.json', 'run.sh', 'check.sh', 'manifest.json', 'check-task.txt', 'check-expected.json'):
            os.remove(kit + '/' + f)
    shutil.rmtree(kit + '/out', ignore_errors=True)
    shutil.rmtree(kit + '/data/tasks')
    os.makedirs(kit + '/data/tasks')
    for t in order:
        shutil.copy(R + 'data/tasks/%s.json' % t, kit + '/data/tasks/%s.json' % t)
    shutil.rmtree(kit + '/models')
    shutil.copytree(MODELS, kit + '/models', symlinks=False)
    shutil.rmtree(kit + '/model/study/sampler')
    shutil.copytree(SAMPLER, kit + '/model/study/sampler', ignore=shutil.ignore_patterns('._*', '__pycache__'))
    if sampler_hash(kit + '/model/study/sampler') != SAMPLER_HASH:
        sys.exit('the kit sampler is not %s' % SAMPLER_HASH)
    for f in ('lines.json', 'weights.json', 'tasks.txt', 'skipped.txt', 'check-task.txt', 'check-expected.json'):
        shutil.copy(HERE + '/' + f, kit + '/' + f)
    for f in CODE:
        shutil.copy(HERE + '/' + f, kit + '/' + f)
    open(kit + '/run.sh', 'w').write(RUN)
    open(kit + '/check.sh', 'w').write(CHECK)
    if sha_of(kit + '/' + WHEEL) != WHEEL_SHA256:
        sys.exit('the wheel is not the wheel of the manifest')
    with zipfile.ZipFile(kit + '/' + WHEEL) as z:
        so_sha = hashlib.sha256(z.read(next(n for n in z.namelist() if n.endswith('.so')))).hexdigest()
    open(kit + '/wheel-so-sha256.txt', 'w').write(so_sha + '\n')
    for p in glob.glob(kit + '/**/._*', recursive=True):
        os.remove(p)
    wheel_engine = dict(commit='c87cf482a', file=WHEEL, sha256=WHEEL_SHA256, so_sha256=so_sha)
    priors = 'models/: sampler-helper-forms/gold-v3-helper-forms-a036da074/models-base'
    budget = '900 s and 8 GiB over the process group, a stem, with no retry at a higher bound; soft end at 840 s; ORCUT_KEPT_NODES 48 parked processes a stem'
    measures = ['before and after of each stem: forms, worst, score, sum, undrawn, bits, status, kinds (tool 1 figures)', 'steps: shape, rank, estimate, new forms with their bits', 'kept_out: why candidates were refused', 'cpu, wall, peak GiB and peak processes, by stem']
    purpose = 'the DAG split cut (tool 2, stage dagcut) on the training stems of view-final: splits of the worst form over its body as a DAG, kept where the bar holds and the landing value falls'
    settings = dict(DAG_STAGES='dagcut, set by run.sh and check.sh', ORCUT_KEPT_NODES='parked processes a stem, default 48 here; it sets speed and memory, and the rows do not depend on it', DAG_ORDER_CAP='tool 1 order cap, default 120 (not set)', DAG_DELTA='default 16 (not set)', DAG_SCREEN_SLACK='default 8 (not set)', DAG_BASE_ROWS='not set: the start text is read, not taken from tool 1 rows')
    note = 'After a first landing, the next step reads the engine\'s normal form, so a run of several steps can depend on the start text\'s written order.'
    eta = dict(basis=['tool 1 on the pod: 17.1 CPU hours for 1,110 stems on or_q.walk; %.1f CPU hours for the %d stems of this kit (pod-all rows)' % (sum(rows[t]['cpu'] for t in order) / 3600, len(order)),
                      'dagcut was 1.1 to 3 times the Mac tool 1 CPU on 5 stems',
                      'on the 99 (eval stems, not in this kit), outcut99 rows give dagcut CPU 2,528 s against 10,919 s of tool 1 on the pod: 0.23 times'],
               cpu_hours=dict(low_1_1x=15.5, high_3x=42.3, from_99=3.3),
               wall_hours_16_shards=dict(low='1.1 (1.1x; pod-all wall of each stem times 1.1, held to 900 s, shards balanced by weight)', high='2.6 (3x; by CPU)', from_99='0.3 to 0.5'),
               tail='20 stems ran to 840 s or more in pod-all; a stem is held to 900 s')
    m = dict(job='gold-v3-dagcut-pod', purpose=purpose, settings=settings, task_set='tasks.txt, %d stems: the %d training stems of view-final less %d skipped; one tier, heaviest first by pod-all tool 1 cpu' % (len(order), len(stems), len(skipped)), budget=budget, measures=measures, wheel_engine=wheel_engine, priors=priors,
             sampler_code=dict(source='orcut-fast/kit-model/study/sampler', hash=SAMPLER_HASH, hash_of='live.py, or_q.py, search.py, search_gold.py, live_try.py, as row field `code`', tree_sha256=tree_hash(kit + '/model/study/sampler')),
             dag_code=dict(hash=dag_code(), hash_of=' '.join(DAG_FILES) + ', as row field `dag_code`'),
             reads=['lines.json', 'tasks.txt', 'weights.json', 'skipped.txt', 'check-task.txt', 'check-expected.json', 'data/tasks', 'models', 'model/study/sampler', 'engine/lib', 'superdag.py', 'wheel-so-sha256.txt'] + list(CODE),
             note=note, run='pip install the wheel, then PY=<python> bash check.sh 16, then PY=<python> bash run.sh 16', shards=SHARDS,
             records='out/rows-<k>.jsonl, one row per stem, field `stage` dagcut, field `base_sha` the hash of the stem\'s start text, fields `cap` and `delta`; resumable, with any shard count. Fields: gold_dagcut_one.py docstring',
             failed_stems='A stem past 900 s or 8 GiB keeps its last streamed row (the last landing), with error set. No rerun at a higher bound; this includes the stems that were at a cap in pod-all.', node_records='none')
    json.dump(m, open(kit + '/manifest.json', 'w'), indent=1)
    out = HERE + '/%s.tar.gz' % NAME
    subprocess.check_call(['tar', 'czf', out, '-C', work, NAME], env=dict(os.environ, COPYFILE_DISABLE='1'))
    sha = sha_of(out)
    open(out + '.sha256', 'w').write('%s  %s.tar.gz\n' % (sha, NAME))
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=R, capture_output=True, text=True).stdout.strip()
    prev = json.load(open(HERE + '/manifest.json')) if os.path.exists(HERE + '/manifest.json') else {}
    at_cap = sorted(t for t in order if rows[t].get('error'))
    need = SHARDS * (53 + 3)
    run = dict(job=m['job'], purpose=purpose, command='PY=<python> bash check.sh 16; PY=<python> bash run.sh 16, in the kit', commit=commit, started=prev.get('started', 'not started'), built=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
               machine='pod; on the Mac, gold_dagcut_pod_env.sh runs the code on runtime-ba0754492', task_set=m['task_set'], budget=budget, measures=measures, settings=settings, note=note,
               base_text=dict(rule='the first row\'s gold_sexp of view-final/<stem>/pairs.jsonl.gz, read at build time, for the stems not in features-worker/arm/eval-tasks.txt', lines_sha256=sha_of(kit + '/lines.json')),
               skipped=dict(count=len(skipped), rule='pod-all row with the start text\'s base_sha, finished, no error, no late flag, bits on every drawing form, worst form under %g bits' % UNDER, file='skipped.txt', stems=sorted(skipped)),
               at_cap_in_pod_all=dict(stems=at_cap, rule='run as usual with the same caps; no retry at a higher bound'),
               priors=priors, steers='live.STEERS, the links in models-base', sampler_code=m['sampler_code'], dag_code=m['dag_code'],
               cuts=dict(dagcut='gold_dagcut_one.py with gold_dag_cuts.py, gold_dag_bits.py (the fixed read), gold_dag_orders.py, gold_fork_reads.py, as in dag-kit; shape-stage helpers from combined-kit'),
               wheel_engine=wheel_engine, wheel_engine_mac=dict(commit='ba0754492', runtime='ast/run/runtime-ba0754492', so_sha256='4538e2630f39d751117a59354494a1d4035d873177c6e9abffe3927a71661371', note='no engine commit in ba0754492..c87cf482a'),
               kit=dict(file=NAME + '.tar.gz', sha256=sha, bytes=os.path.getsize(out), stems=len(order), tiers=[len(order)], shards=SHARDS, check_stem=check_stem),
               processes=dict(a_shard='ORCUT_KEPT_NODES + 5, 53 at 48: runner, stem process, root Node, 48 Nodes, one Node past the bound, one fork', runner_threads='3 on the Mac; check.sh reads them on the pod', need_at_16_shards=need, limit_to_set=need * 5 // 4, rule='16 x (53 + 3), with a quarter over. check.sh fails under that', open_files='hard limit at least 160'),
               estimate=eta, records='this folder: gold_dagcut_pod_*.py, gold_dagcut_pod_env.sh, the copied stage files, manifest.json, the kit tar and its sha256; scratch/ holds the one-use files', node_records='none')
    json.dump(run, open(HERE + '/manifest.json', 'w'), indent=1)
    shutil.rmtree(work)
    print(out, os.path.getsize(out), 'sha256', sha)
    print(len(order), 'stems', 'skipped', len(skipped), 'check stem', check_stem, 'sampler', SAMPLER_HASH, 'dag_code', dag_code())


if __name__ == '__main__':
    {'prepare': prepare, 'build': build}[sys.argv[1] if len(sys.argv) > 1 else 'build']()
