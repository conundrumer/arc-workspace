"""Builds the pod kit of the job `gold-v3-reread5` (order-free bits by or_q.walk on every form of the ramp's kept union programs that are not the pinned program): writes gold-v3-reread5-kit.tar.gz, its sha256 and manifest.json in this folder.

  python3 gold_pod_kit.py          (run it through the symlink in work/lm/data-study/gold/gold-v3-dag-bits/reread5-kit, which holds check-expected.json and receives the outputs)

PIN is the master commit of the sampler. A build copies model/study/sampler of that commit (git archive) into kit-model/study/sampler of the output folder (the Mac's copy, which mac_check.sh runs) and into the kit, then checks that the two are equal. To move the pin, change PIN and rebuild.
Stems: `<task>~<program sha>` for each distinct program sha of a task in union-ramp.jsonl that is not in `left_out` and is not the sha of case `pinned`; plus the check stems, as plain task ids. Text of a program stem: the non-empty lines of `text` of union-keys-ramp.jsonl for any one case of that sha, OUT line included. Text of a check stem: its lines in the reread4 kit's lines.json, which are the lines that check-expected.json was made from (build stops if their hash is not the one in check-expected.json).
Every form of every stem is read (only.json holds [] for each stem). tasks.txt has one tier, heaviest first by line count; weights.json holds the line counts.
The kit's layout, wheel, engine/lib and priors come from the combined kit's tar, whose lib matches the named wheel; its sampler and its stem files are replaced.
The runner code (CODE) is copied from this file's own folder, where the symlink is resolved.
"""
import glob, gzip, hashlib, json, math, os, shutil, subprocess, sys, tarfile, time, zipfile

PIN = 'b8e52e249'
HERE = os.path.dirname(os.path.abspath(__file__))  # the output folder (the symlink's folder, when run through the symlink)
SRC = os.path.dirname(os.path.realpath(__file__))  # this file's folder: the runner code
R = '/Users/davidlu/code/arc-workspace/'
D = R + 'work/lm/data-study/'
G = D + 'gold/'
BASE = G + 'gold-v3-combined-cut/gold-v3-combined-cut-kit.tar.gz'
BASE_NAME = 'gold-v3-combined-cut-kit'
UNION = G + 'gold-union/union-ramp.jsonl'
UNION_SHA256 = '8f537a31d0e41ee2ff76d1e207096d4be4cbd8e31537eb1e445b91fa01971203'
KEYS = G + 'gold-union/union-keys-ramp.jsonl'
CHECK_TAR = G + 'gold-v3-dag-bits/reread4-kit/gold-v3-reread4-kit.tar.gz'
CHECK_TAR_LINES = 'gold-v3-reread4-kit/lines.json'
MODELS = D + 'sampler/sampler-worker/sampler-helper-forms/gold-v3-helper-forms-a036da074/models-base'
MOVED = D + 'sampler/sampler-worker/sampler-walk-faults/moved-final/moved-forms.json'
CHECK_STEMS = ('35ab12c3', '88bcf3b4')
WHEEL = 'arclog-0.1.0-cp312-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl'
WHEEL_SHA256 = 'eeebf281685646614e0935a8ac976aa6099c6b1dc1f4e1bb3499df0aabaef57d'
NAME = 'gold-v3-reread5-kit'
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


def lines_of(text):
    return [x for x in text.splitlines() if x.strip()]


def check_text():
    """Check stem -> lines, as the reread4 kit has them; they must hash to the base_sha of check-expected.json."""
    with tarfile.open(CHECK_TAR) as t:
        old = json.load(t.extractfile(CHECK_TAR_LINES))
    want = {e['task']: e['row']['base_sha'] for e in json.load(open(HERE + '/check-expected.json'))}
    for c in CHECK_STEMS:
        if hashlib.sha256('\n'.join(old[c]).encode()).hexdigest()[:16] != want[c]:
            sys.exit('the text of check stem %s is not the text of check-expected.json' % c)
    return {c: old[c] for c in CHECK_STEMS}


def programs():
    """Stem -> lines of each kept union program that is not the pinned one."""
    if sha_of(UNION) != UNION_SHA256:
        sys.exit('union-ramp.jsonl is not the file of the manifest')
    keys = {}
    for l in open(KEYS):
        x = json.loads(l)
        keys[(x['task'], x['case'])] = x['text']
    text = {}
    for l in open(UNION):
        u = json.loads(l)
        pin = u['cases']['pinned']
        got = {}
        for case, s in u['cases'].items():
            if s == pin or s in u['left_out']:
                continue
            t = lines_of(keys[(u['task'], case)])
            if got.setdefault(s, t) != t:
                sys.exit('cases of program %s of %s differ in text' % (s, u['task']))
        for s, t in got.items():
            text['%s~%s' % (u['task'], s)] = t
    return text


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


def main():
    text = programs()
    n_programs = len(text)
    text.update(check_text())
    tiers = [sorted(text, key=lambda t: (-len(text[t]), t))]
    tasks = sorted({t.split('~')[0] for t in text})
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
    for t in tasks:
        shutil.copy(R + 'data/tasks/%s.json' % t, kit + '/data/tasks/%s.json' % t)
    shutil.rmtree(kit + '/models')
    shutil.copytree(MODELS, kit + '/models', symlinks=False)
    shutil.rmtree(kit + '/model/study/sampler')
    pin_sampler(kit + '/model/study/sampler')
    if tree_hash(kit + '/model/study/sampler') != tree_hash(mac):
        sys.exit('the kit sampler and the Mac sampler differ')
    only = {t: [] for t in text}  # every form of every stem
    json.dump(text, open(kit + '/lines.json', 'w'))
    json.dump({t: float(len(text[t])) for t in text}, open(kit + '/weights.json', 'w'))
    json.dump(only, open(kit + '/only.json', 'w'))
    open(kit + '/tasks.txt', 'w').write('\n'.join(tiers[0]) + '\n')
    shutil.copy(HERE + '/check-expected.json', kit + '/check-expected.json')
    for f in CODE:
        shutil.copy(SRC + '/' + f, kit + '/' + f)
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
    out = HERE + '/%s.tar.gz' % NAME
    wheel_engine = dict(commit='c87cf482a', file=WHEEL, sha256=WHEEL_SHA256, so_sha256=so_sha)
    budget = '900 s and 8 GiB over the process group, a stem, with no retry at a higher bound; soft end at 840 s (forms not read by then have status `unread`); a form has at most 300 s'
    measures = ['bits of each form: -log2 of the summed chance over the form\'s valid atom orders, with parts by decision', 'status, order count, written-order bits and tight bits of each form', 'bits of the written order over every earlier written line (prefix)', 'cpu, wall, peak GiB and peak processes, by stem']
    settings = dict(POD_ORDER_CAP='orders walked in full, default or_q.ORDER_CAP 256', POD_BUDGET='walks of a guided draw for a form past the cap, default 256', POD_FORM_SECONDS='seconds for one form, default 300', POD_PREFIX='0 leaves out the prefix read; default 1', POD_ONLY='for a check: lines to read')
    per_task = {}
    for t in text:
        if '~' in t:
            per_task[t.split('~')[0]] = per_task.get(t.split('~')[0], 0) + 1
    m = dict(arm='union-bits: clause bits of the union programs, for the AND-OR graph read (gold_union_graph.py)',
             training_eligible='none: the 22 ramp tasks are the set the verdicts are read on, and these rows are figures for that read',
             read_rule='the read goes ahead when check.sh passes and each program stem has a row. A form with no figure (an error, a stem past 900 s or 8 GiB, or status none, cap or unread) leaves its production with no bits. That production stays in the graph: on known bits it can not be on a path, and on low bits it costs 0 bits. Each task gives its cheapest hyperpath both ways, with the count of productions without bits on the low-bits path; a task whose two paths differ is marked, and its known-bits path is its figure',
             job='gold-v3-reread5', purpose='or_q.walk at b8e52e249 on every form of the ramp\'s kept non-pinned union programs, union-ramp.jsonl sha %s' % UNION_SHA256, settings=settings,
             task_set='tasks.txt, %d stems in one tier, heaviest first by line count: %d program stems of %d tasks, stem `<task>~<program sha>`, and the check stems %s as plain task ids' % (len(text), n_programs, len(per_task), ', '.join(CHECK_STEMS)),
             programs=dict(source='union-ramp.jsonl (cases, left_out), union-keys-ramp.jsonl (text)', rule='each distinct program sha of a task that is not in left_out and is not the sha of case `pinned`; text of any one case that maps to it', count=n_programs, per_task=per_task, union_sha256=UNION_SHA256, lines=sum(len(text[t]) for t in text if '~' in t)),
             reads='every form of every stem (only.json holds [] for each stem); weights.json holds the line count of each stem',
             budget=budget, measures=measures, wheel_engine=wheel_engine, priors='models/: sampler-helper-forms/gold-v3-helper-forms-a036da074/models-base',
             sampler_code=dict(pin=PIN, commit=pin_commit, git_tree=pin_tree, hash=five, hash_of=' '.join(SAMPLER_FILES) + ', as row field `code`', tree_sha256=tree_hash(kit + '/model/study/sampler')),
             name_dependence='a form\'s name is in the text that the scope\'s sort (ancestor_order) reads, so slot numbers can depend on helper names, not on written position',
             run='pip install the wheel, then PY=<python> bash check.sh 16, then PY=<python> bash run.sh 16', shards=SHARDS,
             records='out/rows-<k>.jsonl, one row per stem, field `stage` pod, field `task` the stem, field `base_sha` the hash of the stem\'s text; resumable. Fields: gold_pod_bits.py docstring',
             failed_stems='A stem past 900 s or 8 GiB keeps its last streamed row (forms read so far), with error set. No rerun at a higher bound.')
    json.dump(m, open(kit + '/manifest.json', 'w'), indent=1)
    subprocess.check_call(['tar', 'czf', out, '-C', work, NAME], env=dict(os.environ, COPYFILE_DISABLE='1'))
    sha = sha_of(out)
    open(out + '.sha256', 'w').write('%s  %s.tar.gz\n' % (sha, NAME))
    commit = git('rev-parse', 'HEAD')
    prev = json.load(open(HERE + '/manifest.json')) if os.path.exists(HERE + '/manifest.json') else {}
    run = dict(m, command='PY=<python> bash check.sh 16; PY=<python> bash run.sh 16, in the kit', commit=commit, started=prev.get('started', 'not started'), built=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
               machine='pod; on the Mac, mac_check.sh runs the code on runtime-ba0754492',
               base_text=dict(rule='program stems: the non-empty lines of `text` of union-keys-ramp.jsonl; check stems: the lines of the reread4 kit\'s lines.json', lines_sha256=sha_of(kit + '/lines.json')),
               wheel_engine_mac=dict(commit='ba0754492', runtime='ast/run/runtime-ba0754492', so_sha256='4538e2630f39d751117a59354494a1d4035d873177c6e9abffe3927a71661371', note='no engine commit in ba0754492..c87cf482a'),
               kit=dict(file=NAME + '.tar.gz', sha256=sha, bytes=os.path.getsize(out), stems=len(text), tiers=[len(x) for x in tiers], shards=SHARDS, check_stems=['35ab12c3', '88bcf3b4 lines 56, 59, 72 at cap 4']),
               records='this folder: gold_pod_*.py, manifest.json, the kit tar and its sha256', node_records='none')
    json.dump(run, open(HERE + '/manifest.json', 'w'), indent=1)
    shutil.rmtree(work)
    print(out, os.path.getsize(out), 'sha256', sha)
    print(len(text), 'stems', n_programs, 'programs', sum(len(text[t]) for t in text if '~' in t), 'program lines', [len(x) for x in tiers], 'sampler', PIN, pin_tree, five)


if __name__ == '__main__':
    main()
