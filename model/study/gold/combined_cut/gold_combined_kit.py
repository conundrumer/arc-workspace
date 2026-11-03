"""Builds the pod kit of the two cut stages: reads the stem list and the corpus view, writes the stems' text, tiers and weights, then gold-v3-combined-cut-kit.tar.gz, its sha256 and manifest.json in this folder.

  python3 gold_combined_kit.py

Stems: gold-v3-shape-cut/next-pod-stems.txt. Start text: the first row's gold_sexp in the stem's corpus-view pairs.jsonl.gz.
Order: the 37 held-out stems, the rest of the 99, then all others, with a blank line of tasks.txt between those tiers. The stems of a tier run heaviest first.
Weight: an estimate of a stem's seconds in the old stages on the pod, from the stem's count of forms and its characters, by a fit over the pod rows of each stage.
The kit's layout and its lib files come from the cover kit, whose lib matches the named wheel. Sampler code is orcut-fast/kit-model, pinned; a master change that is off by default needs no rebuild. Tasks and priors are current.
check-expected.json holds the check stem's two rows from the Mac.
"""
import glob, gzip, hashlib, json, math, os, shutil, subprocess, sys, tarfile, time, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.dirname(HERE)
R = '/Users/davidlu/code/arc-workspace/'
D = R + 'work/lm/data-study/'
G = D + 'gold/'
COVER = G + 'gold-v3-cover-forms-a036da074/gold-v3-cover-forms-kit.tar.gz'
VIEW = G + 'gold-v3-cover-forms-a036da074/corpus-view/'
STEMS = G + 'gold-v3-shape-cut/next-pod-stems.txt'
MODELS = D + 'sampler/sampler-worker/sampler-helper-forms/gold-v3-helper-forms-a036da074/models-base'
EVAL = D + 'features-worker/arm/eval-tasks.txt'
HELD = D + 'sampler/sampler-worker/held/tasks.txt'
SAMPLER = S + '/orcut-fast/kit-model/study/sampler'
WHEEL = 'arclog-0.1.0-cp312-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl'
WHEEL_SHA256 = 'eeebf281685646614e0935a8ac976aa6099c6b1dc1f4e1bb3499df0aabaef57d'
NAME = 'gold-v3-combined-cut-kit'
SHARDS, CHECK_STEM = 16, 'ac3e2b04'
FIT = dict(ext=(-10.452, -0.745, 2.121, 0.83), shape=(-16.275, -1.02, 2.88, 0.85))  # log seconds = a + b log forms + c log characters, with the fit's residual sd
CODE = ('gold_combined_run.py', 'gold_combined_check.py', 'gold_fork_reads.py', 'gold_orcut_one.py', 'gold_extcut_cuts.py', 'gold_shapecut_one.py', 'gold_shapecut_cuts.py', 'gold_shapecut_shapes.py', 'gold_orcut_cuts.py', 'gold_orcut_base.py', 'gold_chain.py')
SETUP = 'ORCUT_SO_SHA256=${ORCUT_SO_SHA256-$(cat wheel-so-sha256.txt)} SAMPLER_CODE=$kit/model/study/sampler SEARCH_MODELS=$kit/models SEARCH_GOLDS=$kit/golds-stub.json ARC_ROOT=$kit PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 RAYON_NUM_THREADS=1 ARCLOG_THREADS=1 PYTHONPATH=$kit:$kit/model/study/sampler:${EXTRA_PATH:-}'
RUN = """#!/bin/bash
# run.sh SHARDS: the extended cut then the shape cut, stem by stem, in SHARDS processes, from the kit's top folder, with $PY set. A restart skips finished stages. Each stage of a stem has 900 s and 8 GiB over its process group, with no retry. ORCUT_KEPT_NODES (default 64) bounds a stem's parked processes.
n=${1:?shards}; kit=$PWD
mkdir -p out
for k in $(seq 0 $((n - 1))); do
  ( %s \\
    "$PY" -u gold_combined_run.py tasks.txt lines.json weights.json out/rows-$k.jsonl $k "$n" >> out/rows-$k.log 2>&1 ) &
done
wait
""" % SETUP
CHECK = """#!/bin/bash
# check.sh [SHARDS]: from the kit's top folder, with $PY set. Reads the wheel, /proc and the limits for SHARDS shards (default 16), tests the group memory count, the cap and the reaping, then runs one stem through both stages as run.sh does and compares its rows with the Mac's. Exits 1 at the first failure.
n=${1:-16}; kit=$PWD
set -e
rm -rf out-check
mkdir out-check
export %s
"$PY" -u gold_combined_check.py limits "$n"
"$PY" -u gold_combined_check.py group
"$PY" -u gold_combined_run.py check-task.txt lines.json weights.json out-check/rows-check.jsonl 0 1
"$PY" -u gold_combined_check.py rows out-check/rows-check.jsonl check-expected.json
echo "check ok"
""" % SETUP


def text_of(t):
    with gzip.open(VIEW + t + '/pairs.jsonl.gz', 'rt') as f:
        return [x for x in json.loads(f.readline())['gold_sexp'].splitlines() if x.strip()]


def weight(ls):
    x, y = math.log(len(ls)), math.log(sum(map(len, ls)))
    return round(sum(math.exp(a + b * x + c * y + sd * sd / 2) for a, b, c, sd in FIT.values()), 1)


def sha_of(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        while b := f.read(1 << 20):
            h.update(b)
    return h.hexdigest()


def stage_text():
    stems = open(STEMS).read().split()
    text = {t: text_of(t) for t in stems}
    weights = {t: weight(x) for t, x in text.items()}
    held, ev = open(HELD).read().split(), open(EVAL).read().split()
    tiers = [[t for t in held if t in text], [t for t in ev if t not in held and t in text], [t for t in text if t not in held and t not in ev]]
    tiers = [sorted(x, key=lambda t: (-weights[t], t)) for x in tiers]
    return tiers, text, weights


def main():
    tiers, text, weights = stage_text()
    work = HERE + '/kit-build'
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    with tarfile.open(COVER) as t:
        t.extractall(work, filter='data')
    kit = work + '/' + NAME
    os.rename(work + '/gold-v3-cover-forms-kit', kit)
    for f in os.listdir(kit):
        if f.startswith('gold_') or f in ('covers.json', 'crossing.json', 'lines.json', 'tasks.txt', 'run.sh', 'manifest.json'):
            os.remove(kit + '/' + f)
    shutil.rmtree(kit + '/out', ignore_errors=True)
    shutil.rmtree(kit + '/models')
    shutil.copytree(MODELS, kit + '/models', symlinks=False)
    shutil.rmtree(kit + '/model/study/sampler')
    shutil.copytree(SAMPLER, kit + '/model/study/sampler', ignore=shutil.ignore_patterns('._*', '__pycache__'))
    shutil.copy(D + 'sampler/search-worker/poolsearch/superdag.py', kit + '/superdag.py')
    for t in text:
        shutil.copy(R + 'data/tasks/%s.json' % t, kit + '/data/tasks/%s.json' % t)
    json.dump(text, open(kit + '/lines.json', 'w'))
    json.dump(weights, open(kit + '/weights.json', 'w'))
    open(kit + '/tasks.txt', 'w').write('\n\n'.join('\n'.join(x) for x in tiers) + '\n')
    open(kit + '/check-task.txt', 'w').write(CHECK_STEM + '\n')
    shutil.copy(HERE + '/check-expected.json', kit + '/check-expected.json')
    for f in CODE:
        shutil.copy(HERE + '/' + f, kit + '/' + f)
    open(kit + '/run.sh', 'w').write(RUN)
    open(kit + '/check.sh', 'w').write(CHECK)
    if sha_of(kit + '/' + WHEEL) != WHEEL_SHA256:
        sys.exit('the wheel is not the wheel of the manifest')
    with zipfile.ZipFile(kit + '/' + WHEEL) as z:
        so_sha = hashlib.sha256(z.read(next(n for n in z.namelist() if n.endswith('.so')))).hexdigest()
    open(kit + '/wheel-so-sha256.txt', 'w').write(so_sha + '\n')
    five = hashlib.sha256(b''.join(open(SAMPLER + '/' + f, 'rb').read() for f in ('live.py', 'or_q.py', 'search.py', 'search_gold.py', 'live_try.py'))).hexdigest()[:12]
    wheel_engine = dict(commit='c87cf482a', file=WHEEL, sha256=WHEEL_SHA256, so_sha256=so_sha)
    priors = 'models/: sampler-helper-forms/gold-v3-helper-forms-a036da074/models-base, fit by live_priors.py --leave-out held/leave_out.txt, which holds the 99'
    budget = '900 s and 8 GiB over the process group, a stem per stage, with no retry at a higher bound; soft end at 840 s; ORCUT_KEPT_NODES 64 parked processes a stem'
    measures = ['bits of each form before and after, by stage', 'landing value before and after, by stage', 'steps by shape', 'cpu, peak GiB and peak processes, by stem and stage']
    purpose = 'the two cut stages over gold on the stems whose text changed: the extended cut, then the shape cut on its result, each with prefix reuse by parked forked processes'
    settings = dict(BAR='the bits at or over which the shape cut tries a form, default 13', LANDING='the shape cut: worst, the default, then the sum. The extended cut has its own rule', ORCUT_KEPT_NODES='parked processes a stem, default 64; it sets speed and memory, and the rows do not depend on it')
    m = dict(job='gold-v3-combined-cut', purpose=purpose, settings=settings, task_set='tasks.txt, %d stems: %d held-out, %d others of the 99, %d others' % (len(text), *map(len, tiers)), budget=budget, measures=measures,
             wheel_engine=wheel_engine, priors=priors, sampler_code=dict(hash=five, of='live.py, or_q.py, search.py, search_gold.py, live_try.py, as row field `code`'),
             reads=['lines.json', 'tasks.txt', 'weights.json', 'check-task.txt', 'check-expected.json', 'data/tasks', 'models', 'model/study/sampler', 'engine/lib', 'superdag.py', 'wheel-so-sha256.txt'] + list(CODE),
             run='pip install the wheel, then PY=<python> bash check.sh 16, then PY=<python> bash run.sh 16', shards=SHARDS, records='out/rows-<k>.jsonl, one row per stage per stem, field `stage` ext or shape, field `base_sha` the hash of that stage\'s start text; resumable',
             failed_stems='A stage past 900 s or 8 GiB keeps its last landing, which passed the bar, with error set, and the shape cut starts from that state. No rerun at a higher bound.', node_records='none')
    json.dump(m, open(kit + '/manifest.json', 'w'), indent=1)
    for p in glob.glob(kit + '/**/._*', recursive=True):
        os.remove(p)
    out = HERE + '/%s.tar.gz' % NAME
    subprocess.check_call(['tar', 'czf', out, '-C', work, NAME], env=dict(os.environ, COPYFILE_DISABLE='1'))
    sha = sha_of(out)
    open(out + '.sha256', 'w').write('%s  %s.tar.gz\n' % (sha, NAME))
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=R, capture_output=True, text=True).stdout.strip()
    prev = json.load(open(HERE + '/manifest.json')) if os.path.exists(HERE + '/manifest.json') else {}
    all_stems = sorted(text)
    run = dict(job=m['job'], purpose=purpose, command='PY=<python> bash check.sh 16; PY=<python> bash run.sh 16, in the kit', commit=commit, started=prev.get('started', 'not started'), built=time.strftime('%Y-%m-%dT%H:%M:%S%z'), machine='pod; on the Mac, gold_combined_env.sh runs the code on runtime-ba0754492',
               task_set=m['task_set'], budget=budget, measures=measures, settings=settings,
               base_text=dict(rule='the first row\'s gold_sexp of corpus-view/<stem>/pairs.jsonl.gz, final through round 52', revision_of_view=json.load(open(G + 'gold-v3-cover-forms-a036da074/manifest.json')).get('revision'), lines_sha256=sha_of(kit + '/lines.json')),
               shape_start='the shape cut\'s start text on a stem is the `program` of its ext row, or the ext start text where that row has none',
               priors=priors, steers='live.STEERS, the links in models-base',
               sampler_code=dict(source='orcut-fast/kit-model/study/sampler', hash=five, hash_of='live.py, or_q.py, search.py, search_gold.py, live_try.py, as row field `code`', tree_sha256=hashlib.sha256(b''.join(open(p, 'rb').read() for p in sorted(glob.glob(kit + '/model/study/sampler/**/*.py', recursive=True)))).hexdigest()[:12], later_master='the shape pod ran master with UNREAD_BETA, default 0; a later master change that is off by default needs no rebuild'),
               cuts=dict(ext='gold_extcut_cuts.py, gold-v3-extended-cut/gold_orcut_cuts.py as it stands', shape='gold_orcut_cuts.py and gold_shapecut_cuts.py of the shape kit, with the chain-tail fix'),
               wheel_engine=wheel_engine, wheel_engine_mac=dict(commit='ba0754492', runtime='ast/run/runtime-ba0754492', so_sha256='4538e2630f39d751117a59354494a1d4035d873177c6e9abffe3927a71661371', note='no engine commit in ba0754492..c87cf482a'),
               kit=dict(file=NAME + '.tar.gz', sha256=sha, bytes=os.path.getsize(out), stems=len(text), tiers=[len(x) for x in tiers], shards=SHARDS, check_stem=CHECK_STEM),
               processes=prev.get('processes'), landing=prev.get('landing'), estimate=prev.get('estimate'),
               records='this folder: gold_*.py, gold_combined_env.sh, landing/, manifest.json, the kit tar and its sha256; scratch/ holds the one-use scripts', node_records='none')
    json.dump(run, open(HERE + '/manifest.json', 'w'), indent=1)
    shutil.rmtree(work)
    print(out, os.path.getsize(out), 'sha256', sha)
    print(len(text), 'stems', [len(x) for x in tiers], 'check stem', CHECK_STEM, 'sampler', five, 'weights top', sorted(weights.values())[-3:])


if __name__ == '__main__':
    main()
