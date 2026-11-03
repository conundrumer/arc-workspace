"""Builds the pod kit of stage `pod` (order-free bits by or_q.walk on all stems of view-final): writes gold-v3-dag-pod-kit.tar.gz, its sha256 and manifest.json in this folder.

  python3 gold_pod_kit.py

PIN is the master commit of the sampler. A build copies model/study/sampler of that commit (git archive) into kit-model/study/sampler of this folder (the Mac's copy, which gold_pod_env.sh runs) and into the kit, then checks that the two are equal. To move the pin, change PIN and rebuild; then rerun measured.sh and expect.sh if the rows may change.
Stems: every folder of view-final. Text: the first row's gold_sexp of <stem>/pairs.jsonl.gz, read at build time (view-final changes). The manifest counts the stems whose text differs from dag-kit's all-lines.json.
Tiers, with a blank line of tasks.txt between: the 37 held-out stems, the rest of the 99, the rest of ramp-fold.txt (22), all others. A tier runs heaviest first, by dag-kit's weights.json.
The kit's layout, wheel, engine/lib and priors come from the combined kit's tar, whose lib matches the named wheel; its sampler and its stem files are replaced.
check-expected.json holds the Mac's rows of the check stems.
"""
import glob, gzip, hashlib, json, math, os, shutil, subprocess, sys, tarfile, time, zipfile

PIN = 'b8e52e249'
HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.dirname(HERE)
R = '/Users/davidlu/code/arc-workspace/'
D = R + 'work/lm/data-study/'
G = D + 'gold/'
VIEW = G + 'gold-v3-combined-cut/view-final/'
RAMP = G + 'gold-heldout-ramp-pass1/ramp-fold.txt'
BASE = S + '/combined-kit/gold-v3-combined-cut-kit.tar.gz'
BASE_NAME = 'gold-v3-combined-cut-kit'
OLD_LINES = S + '/dag-kit/all-lines.json'
WEIGHTS = S + '/dag-kit/weights.json'
MODELS = D + 'sampler/sampler-worker/sampler-helper-forms/gold-v3-helper-forms-a036da074/models-base'
MOVED = D + 'sampler/sampler-worker/sampler-walk-faults/moved-final/moved-forms.json'
CHECK_STEMS = ('35ab12c3', '88bcf3b4')
EVAL = D + 'features-worker/arm/eval-tasks.txt'
HELD = D + 'features-worker/arm/held-tasks.txt'
WHEEL = 'arclog-0.1.0-cp312-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl'
WHEEL_SHA256 = 'eeebf281685646614e0935a8ac976aa6099c6b1dc1f4e1bb3499df0aabaef57d'
NAME = 'gold-v3-reread2-kit'
SHARDS = 16
CODE = ('gold_pod_bits.py', 'gold_pod_run.py', 'gold_pod_check.py', 'gold_pod_compare.py')
SAMPLER_FILES = ('live.py', 'or_q.py', 'form_orders.py', 'search.py', 'search_gold.py', 'live_try.py')
SETUP = 'ORCUT_SO_SHA256=${ORCUT_SO_SHA256-$(cat wheel-so-sha256.txt)} SAMPLER_CODE=$kit/model/study/sampler SEARCH_MODELS=$kit/models SEARCH_GOLDS=$kit/golds-stub.json ARC_ROOT=$kit PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 RAYON_NUM_THREADS=1 ARCLOG_THREADS=1 PYTHONPATH=$kit:$kit/model/study/sampler:${EXTRA_PATH:-}'
RUN = """#!/bin/bash
# run.sh SHARDS: the stage `pod`, stem by stem, in SHARDS processes, from the kit's top folder, with $PY set. A restart skips finished stems, with any shard count. Each stem has 900 s and 8 GiB over its process group, with no retry at a higher bound. Rows: out/rows-<k>.jsonl.
n=${1:?shards}; kit=$PWD
mkdir -p out
for k in $(seq 0 $((n - 1))); do
  ( %s \\
    "$PY" -u gold_pod_run.py tasks.txt lines.json weights.json out/rows-$k.jsonl $k "$n" >> out/rows-$k.log 2>&1 ) &
done
wait
""" % SETUP
CHECK = """#!/bin/bash
# check.sh [SHARDS]: from the kit's top folder, with $PY set. Reads the wheel, /proc and the limits for SHARDS shards (default 16), tests the group memory count, the cap and the reaping, then runs the check stems through the runner as run.sh does (the second with POD_ORDER_CAP=4 POD_BUDGET=32 POD_ONLY=56,59,72 POD_PREFIX=0, which gives a form of status `bound`) and compares their rows with the Mac's. Exits 1 at the first failure.
n=${1:-16}; kit=$PWD
set -e
rm -rf out-check
mkdir out-check
export %s
"$PY" -u gold_pod_check.py limits "$n"
"$PY" -u gold_pod_check.py group
echo 35ab12c3 > check-task-1.txt
echo 88bcf3b4 > check-task-2.txt
"$PY" -u gold_pod_run.py check-task-1.txt lines.json weights.json out-check/rows-check.jsonl 0 1
POD_ORDER_CAP=4 POD_BUDGET=32 POD_ONLY=56,59,72 POD_PREFIX=0 "$PY" -u gold_pod_run.py check-task-2.txt lines.json weights.json out-check/rows-check.jsonl 0 1
"$PY" -u gold_pod_check.py rows out-check/rows-check.jsonl check-expected.json
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


def git(*a):
    return subprocess.run(['git', '-C', R, *a], capture_output=True, text=True, check=True).stdout.strip()


def pin_sampler(dest):
    """model/study/sampler of PIN into dest (replacing it), by git archive."""
    shutil.rmtree(dest, ignore_errors=True)
    tmp = dest + '.tmp'
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    arch = subprocess.run(['git', '-C', R, 'archive', PIN, 'model/study/sampler'], capture_output=True, check=True).stdout
    subprocess.run(['tar', '-x', '-C', tmp], input=arch, check=True)
    shutil.move(tmp + '/model/study/sampler', dest)
    shutil.rmtree(tmp)


def tree_hash(d):
    return hashlib.sha256(b''.join(open(p, 'rb').read() for p in sorted(glob.glob(d + '/**/*.py', recursive=True)))).hexdigest()[:12]


def stems_text():
    stems = sorted(x for x in os.listdir(VIEW) if os.path.exists(VIEW + x + '/pairs.jsonl.gz'))
    text = {t: text_of(t) for t in stems}
    return text


def text_changes(text):
    """The stems whose text is not dag-kit's all-lines.json."""
    old = json.load(open(OLD_LINES))
    return sorted(t for t in set(old) | set(text) if old.get(t) != text.get(t))


def tiers_of(text, weights):
    held, ev, ramp = (open(f).read().split() for f in (HELD, EVAL, RAMP))
    seen = set()
    tiers = []
    for tier in (held, [t for t in ev if t not in held], ramp, list(text)):
        got = [t for t in tier if t in text and t not in seen]
        seen |= set(got)
        tiers.append(sorted(got, key=lambda t: (-weights.get(t, 1.0), t)))
    return tiers


def pod_rows():
    rows = {}
    for p in glob.glob(G + 'gold-v3-dag-bits/pod-all/rows-*.jsonl'):
        for l in open(p):
            try:
                r = json.loads(l)
            except ValueError:
                continue
            rows[r['task']] = r
    return rows


def reread_of(text):
    if os.path.exists(HERE + '/stems.txt'):  # every form of these stems
        return {t: [] for t in open(HERE + '/stems.txt').read().split() + list(CHECK_STEMS)}
    """stem -> lines to read: the forms the walk fixes move, the forms pod-all left with no figure, and every form ([]) of a stem whose text is not pod-all's."""
    moved = json.load(open(MOVED))
    rows = pod_rows()
    only = {}
    for t, ls in text.items():
        r = rows.get(t)
        if r is None or r['base_sha'] != hashlib.sha256('\n'.join(ls).encode()).hexdigest()[:16]:
            only[t] = []
            continue
        x = set(moved.get(t, [])) | {f['line'] for f in r['forms'] if f['status'] in ('none', 'unread')}
        if x:
            only[t] = sorted(x)
    for t in CHECK_STEMS:
        only[t] = []
    return only


def rewt(t, only, text, weights):
    return weights.get(t, 1.0) if not only[t] else max(1.0, weights.get(t, 1.0) * len(only[t]) / len(text[t]))


def main():
    text = stems_text()
    weights = json.load(open(WEIGHTS))
    tiers = tiers_of(text, weights)
    changed = text_changes(text)
    pin_commit = git('rev-parse', PIN)
    pin_tree = git('rev-parse', PIN + ':model/study/sampler')
    mac = HERE + '/kit-model/study/sampler'
    pin_sampler(mac)
    work = HERE + '/kit-build'
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    with tarfile.open(BASE) as t:
        t.extractall(work, filter='data')
    kit = work + '/' + NAME
    os.rename(work + '/' + BASE_NAME, kit)
    for f in os.listdir(kit):
        if f.startswith('gold_') or f in ('lines.json', 'tasks.txt', 'weights.json', 'run.sh', 'check.sh', 'manifest.json', 'check-task.txt', 'check-expected.json', 'superdag.py'):
            os.remove(kit + '/' + f)
    shutil.rmtree(kit + '/out', ignore_errors=True)
    shutil.rmtree(kit + '/data/tasks')
    os.makedirs(kit + '/data/tasks')
    for t in text:
        shutil.copy(R + 'data/tasks/%s.json' % t, kit + '/data/tasks/%s.json' % t)
    shutil.rmtree(kit + '/models')
    shutil.copytree(MODELS, kit + '/models', symlinks=False)
    shutil.rmtree(kit + '/model/study/sampler')
    pin_sampler(kit + '/model/study/sampler')
    if tree_hash(kit + '/model/study/sampler') != tree_hash(mac):
        sys.exit('the kit sampler and the Mac sampler differ')
    only = reread_of(text)
    tiers = [[t for t in x if t in only] for x in tiers]
    json.dump({t: text[t] for t in only}, open(kit + '/lines.json', 'w'))
    json.dump({t: rewt(t, only, text, weights) for t in only}, open(kit + '/weights.json', 'w'))
    json.dump(only, open(kit + '/only.json', 'w'))
    open(kit + '/tasks.txt', 'w').write('\n\n'.join('\n'.join(x) for x in tiers) + '\n')
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
    for p in glob.glob(kit + '/**/._*', recursive=True):
        os.remove(p)
    five = hashlib.sha256(b''.join(open(kit + '/model/study/sampler/' + f, 'rb').read() for f in SAMPLER_FILES)).hexdigest()[:12]
    measured = json.load(open(HERE + '/measured.json')) if os.path.exists(HERE + '/measured.json') else None
    out = HERE + '/%s.tar.gz' % NAME
    wheel_engine = dict(commit='c87cf482a', file=WHEEL, sha256=WHEEL_SHA256, so_sha256=so_sha)
    budget = '900 s and 8 GiB over the process group, a stem, with no retry at a higher bound; soft end at 840 s (forms not read by then have status `unread`); a form has at most 300 s'
    measures = ['bits of each form: -log2 of the summed chance over the form\'s valid atom orders, with parts by decision', 'status, order count, written-order bits and tight bits of each form', 'bits of the written order over every earlier written line (prefix)', 'cpu, wall, peak GiB and peak processes, by stem']
    settings = dict(POD_ORDER_CAP='orders walked in full, default or_q.ORDER_CAP 256', POD_BUDGET='walks of a guided draw for a form past the cap, default 256', POD_FORM_SECONDS='seconds for one form, default 300', POD_PREFIX='0 leaves out the prefix read; default 1', POD_ONLY='for a check: lines to read')
    m = dict(job='gold-v3-reread', purpose='or_q.walk at b8e52e249 on every form of the stems whose view-final text changed after merged.jsonl (stems.txt); earlier: on the forms its fixes move, the forms pod-all has no figure for, and every form of a stem whose text changed since pod-all (only.json); the other forms keep their pod-all figures', settings=settings, task_set='tasks.txt, %d stems: %s' % (len(text), ', '.join('%d %s' % (len(x), n) for x, n in zip(tiers, ('held-out', 'others of the 99', 'others of ramp-fold.txt', 'others')))),
             budget=budget, measures=measures, wheel_engine=wheel_engine, priors='models/: sampler-helper-forms/gold-v3-helper-forms-a036da074/models-base',
             sampler_code=dict(pin=PIN, commit=pin_commit, git_tree=pin_tree, hash=five, hash_of=' '.join(SAMPLER_FILES) + ', as row field `code`', tree_sha256=tree_hash(kit + '/model/study/sampler')),
             name_dependence='a form\'s name is in the text that the scope\'s sort (ancestor_order) reads, so slot numbers can depend on helper names, not on written position',
             run='pip install the wheel, then PY=<python> bash check.sh 16, then PY=<python> bash run.sh 16', shards=SHARDS,
             records='out/rows-<k>.jsonl, one row per stem, field `stage` pod, field `base_sha` the hash of the stem\'s text; resumable. Fields: gold_pod_bits.py docstring',
             failed_stems='A stem past 900 s or 8 GiB keeps its last streamed row (forms read so far), with error set. No rerun at a higher bound.')
    m['estimate_cpu_hours'] = 'about 9 from pod-all form seconds of the moved forms, plus whole changed stems'
    json.dump(m, open(kit + '/manifest.json', 'w'), indent=1)
    subprocess.check_call(['tar', 'czf', out, '-C', work, NAME], env=dict(os.environ, COPYFILE_DISABLE='1'))
    sha = sha_of(out)
    open(out + '.sha256', 'w').write('%s  %s.tar.gz\n' % (sha, NAME))
    commit = git('rev-parse', 'HEAD')
    prev = json.load(open(HERE + '/manifest.json')) if os.path.exists(HERE + '/manifest.json') else {}
    run = dict(m, command='PY=<python> bash check.sh 16; PY=<python> bash run.sh 16, in the kit', commit=commit, started=prev.get('started', 'not started'), built=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
               machine='pod; on the Mac, gold_pod_env.sh runs the code on runtime-ba0754492',
               base_text=dict(rule='the first row\'s gold_sexp of view-final/<stem>/pairs.jsonl.gz, read at build time', differs_from_dag_kit_all_lines=changed, lines_sha256=sha_of(kit + '/lines.json')),
               wheel_engine_mac=dict(commit='ba0754492', runtime='ast/run/runtime-ba0754492', so_sha256='4538e2630f39d751117a59354494a1d4035d873177c6e9abffe3927a71661371', note='no engine commit in ba0754492..c87cf482a'),
               kit=dict(file=NAME + '.tar.gz', sha256=sha, bytes=os.path.getsize(out), stems=len(text), tiers=[len(x) for x in tiers], shards=SHARDS, check_stems=['35ab12c3', '88bcf3b4 lines 56, 59, 72 at cap 4']),
               estimate=measured, records='this folder: gold_pod_*.py, gold_pod_env.sh, measured/, manifest.json, the kit tar and its sha256; scratch/ holds the one-use files', node_records='none')
    json.dump(run, open(HERE + '/manifest.json', 'w'), indent=1)
    shutil.rmtree(work)
    print(out, os.path.getsize(out), 'sha256', sha)
    print(len(text), 'stems', [len(x) for x in tiers], 'sampler', PIN, pin_tree, five, 'weights top', sorted(weights.values())[-3:])


if __name__ == '__main__':
    main()
