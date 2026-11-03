"""Builds the kit and the job files of one round of the node score refit loop.

  <python> -I search_refit_build.py MODEL_STATE [CARD] OUT_DIR

MODEL_STATE  node-score-rN.state.pkl, the pickle of (models, rounds_done) with 150 HistGradientBoostingRegressor. The card (default: the .json beside it) and the
             .sha256 file beside it are found by the file name. The round name rN is read from the file name (r0 where it has none).
OUT_DIR      where the files go. A second run with the same inputs skips the stages it has done (marker files in OUT_DIR/build), so a stopped run goes on.

Exit status: 0 done; 2 the sha256 of the state differs from the .sha256 file or from the card; 1 any other failure.

Before the stages the script checks the base kit tar's sha256 and the state's sha256 against the .sha256 file and the card. Then the stages, each printed as [k/7]
with the time it took, and lines with a rate and the time left inside the long ones:
  1. extract  the base kit's tar into OUT_DIR/build/base.
  2. edit     a copy of that as OUT_DIR/build/<kit name>, then the mix patch (not the Ident patience patch), the ramp gold in points-eval.json, the 50 N600 tasks and their
              gold in points-n600.json, and ARC_GOLD from the environment in run3600.sh.
  3. convert  search_node_score_make.py on the state: scores/refit.npz, which must print PASS.
  4. files    the task lists, the Ident-only file, the kit manifest, and the jobs files.
  5. diff     the kit against the base kit: only the edits above may differ, and the 3 patched files differ by the patch's lines.
  6. pack     the kit tar.
  7. manifest the run manifest.
Writes to OUT_DIR: the kit tar, search-refit-rN-jobs-heldout37-ramp22-2seeds-600s.txt (3 check lines first, then 236 lines), smoke-jobs.txt, positives-jobs.txt, manifest.json,
and copies of refit-tasks.json, gold-ident-only-refit.json, points-eval.json and points-n600.json, which search_refit_read.py looks for beside the run.
Prints the kit tar's sha256 last.
Environment: REFIT_PY (the engine python for the converter), REFIT_PATCH, REFIT_BASE_TAR, REFIT_ROWS (the folder of base rows), REFIT_RECORD=0 (no ARC_RECORD on the positives lines).
"""
import collections
import datetime
import difflib
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = '/Users/davidlu/code/arc-workspace'
DATA = REPO + '/work/lm/data-study'
SEARCH_WORKER = DATA + '/sampler/search-worker'
SCRATCH = '/private/tmp/claude-501/-Users-davidlu-code-arc-workspace/b0431573-360c-4463-a250-926e25570e30/scratchpad'
BASE_NAME = 'sampler-pool-tiekey-value-0729e4943'
BASE_TAR = os.environ.get('REFIT_BASE_TAR', DATA + '/sampler/sampler-worker/kits/%s.tar.gz' % BASE_NAME)
BASE_JOBS = DATA + '/sampler/sampler-worker/kits/%s-jobs.txt' % BASE_NAME
BASE_SHA_START = '1d9807f6fb2d403a'
PATCH = os.environ.get('REFIT_PATCH') or next(p for p in (SCRATCH + '/identj/patches/2-node-score-mix.patch', SEARCH_WORKER + '/node-score/2-node-score-mix.patch') if os.path.exists(p))
PY = os.environ.get('REFIT_PY', DATA + '/ast/run/runtime-kaggle-py313/venv/bin/python')
MAKE = SEARCH_WORKER + '/search_node_score_make.py'
ROWS = os.environ.get('REFIT_ROWS', DATA + '/features-worker/results/features-node-rank-model-train-read-hour13-heldout37/base-rows')
RAMP_DIR = DATA + '/gold/gold-heldout-ramp-pass1'
IDENT_37 = SEARCH_WORKER + '/node-score/gold-ident-only-kit50.json'
IDENT_RAMP = os.environ.get('REFIT_IDENT_RAMP', HERE + '/gold-ident-only-ramp22.json')
N600_TASKS = DATA + '/features-worker/results/features-node-score-refit-loop/n600-tasks.txt'
N600_DATA = REPO + '/data/tasks'
N600_GOLD = DATA + '/gold/gold-v3-combined-cut/view-final'
STAND_IN_SHA = '916864da7ac598dfcb77cc34f59db260cc68f2d7bba6080131a46c77bd6bb7f6'  # the M-T state, which stands in until the real model lands
CHECK_TASK = '135a2760'
SMOKE_TASKS = ('135a2760', '74dd1130')
SECONDS, PARITY_SECONDS, CHECK_SECONDS, SMOKE_SECONDS = 600, 600, 120, 180  # a smoke job runs past the first bank save at about 130 s
EDITED = {'policy/nodescore.py', 'model/study/sampler/superdag_search.py', 'model/study/sampler/kaggle_worker.py'}  # the files that the mix patch edits
LINE = re.compile(r'^(?P<head>.*?)\./run3600\.sh (?P<task>\w+) (?P<arm>\w+) (?P<models>\S+) (?P<seconds>\d+)\s*$')


class Stop(Exception):
    def __init__(self, text, code=1):
        super().__init__(text)
        self.code = code


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


class Progress:
    """Prints a line at most each 2 s with the count done, the rate and the time left."""

    def __init__(self, label, total):
        self.label, self.total, self.t0, self.last = label, total, time.time(), 0.0

    def step(self, done, force=False):
        now = time.time()
        if force or now - self.last >= 2:
            self.last = now
            rate = done / (now - self.t0) if now > self.t0 else 0.0
            eta = (self.total - done) / rate if rate else 0.0
            print('    %s %d/%d, %.0f per s, %.0f s left' % (self.label, done, self.total, rate, eta), flush=True)


def stage(k, n, name, fp, out, fn):
    """Runs fn unless the marker of this stage holds the fingerprint of the inputs."""
    marker = os.path.join(out, 'build', '.done-%s' % name)
    t0 = time.time()
    if os.path.exists(marker) and open(marker).read() == fp:
        print('[%d/%d] %s: done before, skipped' % (k, n, name), flush=True)
        return
    print('[%d/%d] %s' % (k, n, name), flush=True)
    fn()
    open(marker, 'w').write(fp)
    spent = time.time() - t0
    print('[%d/%d] %s: %.1f s' % (k, n, name, spent), flush=True)


def first_hex(text):
    m = re.search(r'\b[0-9a-f]{64}\b', text)
    return m[0] if m else None


def find_inputs(state, card_arg):
    """(card path, sha256 file path or None, round name)."""
    base = state[:-len('.state.pkl')] if state.endswith('.state.pkl') else os.path.splitext(state)[0]
    card = card_arg or next((p for p in (base + '.json', state + '.json') if os.path.exists(p)), None)
    shafile = next((p for p in (base + '.sha256', state + '.sha256') if os.path.exists(p)), None)
    m = re.search(r'-(r\d+)\.state\.pkl$', os.path.basename(state))
    return card, shafile, m[1] if m else 'r0'


def main():
    args = sys.argv[1:]
    if len(args) not in (2, 3):
        raise Stop('usage: search_refit_build.py MODEL_STATE [CARD] OUT_DIR')
    state, out = os.path.abspath(args[0]), os.path.abspath(args[-1])
    card_arg = os.path.abspath(args[1]) if len(args) == 3 else None
    card_path, shafile, rnd = find_inputs(state, card_arg)
    if not os.path.exists(state):
        raise Stop('no model state at %s' % state)
    if not card_path or not os.path.exists(card_path):
        raise Stop('no card beside %s' % state)
    os.makedirs(out + '/build', exist_ok=True)
    kit_name = 'search-refit-%s-kit-0729e4943' % rnd
    work = out + '/build'
    kit = '%s/%s' % (work, kit_name)
    t_start = time.time()
    ctx = {}
    names = dict(jobs='search-refit-%s-jobs-heldout37-ramp22-2seeds-600s.txt' % rnd, smoke='smoke-jobs.txt', positives='positives-jobs.txt')

    def inputs():
        h = sha256_of(BASE_TAR)
        if not h.startswith(BASE_SHA_START):
            raise Stop('base kit tar sha256 %s does not start with %s' % (h, BASE_SHA_START))
        got = sha256_of(state)
        card = json.load(open(card_path))
        if shafile and first_hex(open(shafile).read()) != got:
            raise Stop('state sha256 %s differs from %s (%s)' % (got, shafile, first_hex(open(shafile).read())), 2)
        if 'sha256' in card and card['sha256'] != got:
            raise Stop('state sha256 %s differs from the card sha256 %s' % (got, card['sha256']), 2)
        if not shafile and 'sha256' not in card:
            raise Stop('no .sha256 file beside the state and no sha256 in the card: nothing to check the state against', 2)
        print('    state sha256 %s matches %s' % (got, 'the .sha256 file' if shafile else 'the card'), flush=True)
        for need in ('feature_names', 't'):
            if need not in card:
                raise Stop('card has no %s' % need)
        print('    card: %d feature names, t %s; round %s' % (len(card['feature_names']), card['t'], rnd), flush=True)

    # the fingerprint covers every input that changes the kit
    fp_parts = [sha256_of(state), sha256_of(card_path), sha256_of(BASE_TAR), sha256_of(PATCH), sha256_of(IDENT_RAMP) if os.path.exists(IDENT_RAMP) else 'no ramp ident',
                sha256_of(os.path.abspath(__file__))]
    fp = '\n'.join(fp_parts)
    print('search_refit_build: state %s, round %s, out %s' % (state, rnd, out), flush=True)
    N = 7
    inputs()  # always runs: the sha check is the gate, and it is cheap apart from the base tar
    base_manifest = {}

    def extract():
        if os.path.isdir(work + '/base'):
            shutil.rmtree(work + '/base')
        os.makedirs(work + '/base')
        with tarfile.open(BASE_TAR) as t:
            members = t.getmembers()
            p = Progress('files', len(members))
            for i, m in enumerate(members):
                t.extract(m, work + '/base', filter='data')
                p.step(i + 1)

    stage(1, N, 'extract', fp, out, extract)

    def edit():
        if os.path.isdir(kit):
            shutil.rmtree(kit)
        src = work + '/base/' + BASE_NAME
        files = sum(len(fs) for _, _, fs in os.walk(src))
        p, n = Progress('copied', files), [0]

        def cp(a, b):
            shutil.copy2(a, b)
            n[0] += 1
            p.step(n[0])
        shutil.copytree(src, kit, copy_function=cp)

        # the mix patch
        r = subprocess.run(['patch', '-p1', '--dry-run', '-d', kit, '-i', PATCH], capture_output=True, text=True)
        if r.returncode:
            raise Stop('the mix patch does not apply: ' + r.stdout[-400:] + r.stderr[-400:])
        r = subprocess.run(['patch', '-p1', '-d', kit, '-i', PATCH], capture_output=True, text=True)
        print('    ' + r.stdout.strip().replace('\n', '\n    '), flush=True)
        for root, _, fs in os.walk(kit):
            for f in fs:
                if f.endswith('.rej'):
                    raise Stop('patch left %s' % f)
                if f.endswith('.orig'):  # the backup that BSD patch writes
                    os.remove(os.path.join(root, f))
        # 3b. the ramp gold: the 22 tasks' entries of points-eval.json take the ramp's gold
        ramp = json.load(open(RAMP_DIR + '/points-ramp.json'))
        evalp = kit + '/points-eval.json'
        gold = json.load(open(evalp))
        by = {x['task']: x for x in ramp}
        changed = []
        for x in gold:
            if x['task'] in by and x['gold_sexp'] != by[x['task']]['gold_sexp']:
                changed.append(x['task'])
                x['gold_sexp'] = by[x['task']]['gold_sexp']
        missing = [t for t in by if t not in {x['task'] for x in gold}]
        if missing:
            raise Stop('ramp tasks not in the kit gold: %s' % missing)
        json.dump(gold, open(evalp, 'w'))
        print('    ramp gold replaced the entries of %d tasks: %s' % (len(changed), ' '.join(changed)), flush=True)
        # 3c. the N600 tasks and their gold
        tasks = open(N600_TASKS).read().split()
        n600 = []
        p = Progress('n600 tasks', len(tasks))
        for i, t in enumerate(tasks):
            dst = '%s/data/tasks/%s.json' % (kit, t)
            if os.path.exists(dst):
                raise Stop('N600 task %s is in the kit already' % t)
            shutil.copy2('%s/%s.json' % (N600_DATA, t), dst)
            with gzip.open('%s/%s/pairs.jsonl.gz' % (N600_GOLD, t), 'rt') as f:
                row = json.loads(f.readline())
            n600.append(dict(task=t, gold_sexp=row['gold_sexp']))
            p.step(i + 1)
        json.dump(n600, open(kit + '/points-n600.json', 'w'))
        # 3d. run3600.sh takes ARC_GOLD from the environment where it is set
        sh = open(kit + '/run3600.sh').read()
        old = 'env ARC_GOLD=$KIT/points-eval.json '
        if sh.count(old) != 1:
            raise Stop('run3600.sh has no single %r' % old)
        open(kit + '/run3600.sh', 'w').write(sh.replace(old, 'env ARC_GOLD=${ARC_GOLD:-$KIT/points-eval.json} '))

    stage(2, N, 'edit', fp, out, edit)

    def convert():
        card = json.load(open(card_path))
        cards = work + '/cards/final-models'
        os.makedirs(cards, exist_ok=True)
        card.setdefault('sha256', sha256_of(state))
        json.dump(card, open(cards + '/card.json', 'w'))
        sha = sha256_of(state)
        code = ('import sys\nsys.path.insert(0, %r)\nimport search_node_score_make as M\nM.FEATURES_DIR = %r\nM.SOURCE_SHA["T"] = %r\n'
                'sys.argv = ["make", %r, "T", "refit", %r, %r]\nM.main()\n') % (os.path.dirname(MAKE), work + '/cards/', sha[:8], state, kit + '/scores/refit.npz', ROWS)
        env = dict(os.environ, KIT_POLICY=kit + '/policy', PYTHONDONTWRITEBYTECODE='1')
        p = subprocess.Popen([PY, '-I', '-c', code], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        lines = []
        for line in p.stdout:
            lines.append(line)
            print('    ' + line.rstrip(), flush=True)
        if p.wait() or not lines or lines[-1].strip() != 'PASS':
            raise Stop('the converter did not end with PASS')

    stage(3, N, 'convert', fp, out, convert)

    def files():
        base_manifest.update(json.load(open(kit + '/manifest.json')))
        t37 = base_manifest['task_set'][:37]
        ramp = open(RAMP_DIR + '/ramp-fold.txt').read().split()
        n600 = open(N600_TASKS).read().split()
        if set(t37) & set(ramp):
            raise Stop('the 37 and the ramp share tasks')
        for t in t37 + ramp + n600:
            if not os.path.exists('%s/data/tasks/%s.json' % (kit, t)):
                raise Stop('kit data/tasks has no %s' % t)
        json.dump(dict(round=rnd, heldout37=t37, ramp22=ramp, n600=n600), open(kit + '/refit-tasks.json', 'w'), indent=1)
        # the Ident-only forms of the 37 and of the 22: the counts must match the forms of the kit's gold
        ident = json.load(open(IDENT_37))
        ident_ramp = json.load(open(IDENT_RAMP))
        gold = {x['task']: x['gold_sexp'] for x in json.load(open(kit + '/points-eval.json'))}
        merged = {}
        for t in t37:
            merged[t] = ident[t]
        for t in ramp:
            merged[t] = ident_ramp[t]
        for t, d in merged.items():
            forms = len([x for x in gold[t].strip().split('\n') if x.strip() and not x.startswith('(OUT')])
            if d['forms'] != forms or d['error']:
                raise Stop('Ident-only entry of %s has %d forms (error %s), the kit gold has %d' % (t, d['forms'], d['error'], forms))
        json.dump(merged, open(kit + '/gold-ident-only-refit.json', 'w'))
        # the job lines
        base = [LINE.match(x.strip()) for x in open(BASE_JOBS) if x.strip()]
        heads = {}
        for m in base:
            if m['arm'] in ('dagk_s0', 'dagk_s1', 'dagkf_s0', 'dagkf_s1'):
                heads.setdefault(m['arm'].replace('dagkf', 'dagk'), m['head'].replace('SAME_POD=%s ' % m['task'], 'SAME_POD={task} ', 1))
                if m['head'].replace('SAME_POD=%s ' % m['task'], 'SAME_POD={task} ', 1) != heads[m['arm'].replace('dagkf', 'dagk')]:
                    raise Stop('base line of %s %s differs from the others in its settings' % (m['task'], m['arm']))
                want_models = 'models-tkf' if 'dagkf' in m['arm'] else 'models-tk'
                if m['models'] != want_models or m['seconds'] != str(SECONDS):
                    raise Stop('base line %s %s has %s at %s s' % (m['task'], m['arm'], m['models'], m['seconds']))
        if sorted(heads) != ['dagk_s0', 'dagk_s1']:
            raise Stop('base job file lacks dagk lines')
        MIX = 'NODE_SCORE=$PWD/scores/refit.npz NODE_SCORE_MIX=.5 '

        def head(seed, task, extra=''):
            return heads['dagk_s%d' % seed].format(task=task) + extra

        def line(seed, task, arm, extra='', models='models-tk', seconds=SECONDS, pod=None):
            h = head(seed, pod or task, extra)
            return '%s./run3600.sh %s %s_s%d %s %d' % (h, task, arm, seed, models, seconds)
        main = [line(0, CHECK_TASK, 'parity', 'NODE_SCORE=$PWD/scores/ship.npz NODE_SCORE_CHECK=1 ', seconds=PARITY_SECONDS),
                line(1, CHECK_TASK, 'parity', 'NODE_SCORE=$PWD/scores/ship.npz NODE_SCORE_CHECK=1 ', seconds=PARITY_SECONDS),
                line(0, CHECK_TASK, 'refitcheck', MIX, seconds=CHECK_SECONDS)]
        for t in t37 + ramp:
            for seed in (0, 1):
                main += [line(seed, t, 'bundle'), line(seed, t, 'refit', MIX)]
        # the 37's bundle lines must be the base file's dagk lines, with the arm name bundle
        basel = {(m['task'], m['arm']): m[0] for m in base}
        for t in t37:
            for seed in (0, 1):
                mine = line(seed, t, 'bundle')
                theirs = basel[(t, 'dagk_s%d' % seed)].replace(' dagk_s%d ' % seed, ' bundle_s%d ' % seed)
                if mine != theirs:
                    raise Stop('bundle line of %s differs from the base kit line:\n%s\n%s' % (t, mine, theirs))
        for t in ramp:
            if (t, 'dagkf_s0') in basel:
                for seed in (0, 1):
                    theirs = basel[(t, 'dagkf_s%d' % seed)].replace(' dagkf_s%d models-tkf ' % seed, ' bundle_s%d models-tk ' % seed)
                    if line(seed, t, 'bundle') != theirs:
                        raise Stop('bundle line of ramp task %s differs from the base kit line' % t)
        if len(main) != 3 + 4 * 59:
            raise Stop('%d main lines' % len(main))
        smoke = []
        for t in SMOKE_TASKS:
            smoke += [line(0, t, 'smokebundle', seconds=SMOKE_SECONDS, pod='smoke'), line(0, t, 'smokerefit', MIX, seconds=SMOKE_SECONDS, pod='smoke')]
        record = os.environ.get('REFIT_RECORD', '1') != '0'
        pos = []
        for t in n600:
            extra = MIX + 'ARC_GOLD=$PWD/points-n600.json ' + ('ARC_RECORD=$PWD/out/refitp_s0/%s ' % t if record else '')
            pos.append(line(0, t, 'refitp', extra))
        for name, lines in (('jobs', main), ('smoke', smoke), ('positives', pos)):
            open('%s/%s' % (kit, names[name]), 'w').write('\n'.join(lines) + '\n')
        # the kit manifest
        m = base_manifest
        m['what'] = ('round %s of the node score refit loop: the bundle (ORDER_FREE=tie,key, models-tk) against the same kit with scores/refit.npz mixed with the ship score on half the openings '
                     '(NODE_SCORE_MIX=.5); two seeds on the 37 held-out tasks and the 22 ramp tasks at 600 s' % rnd)
        m['command'] = 'cd <kit>; PY=<python> EXTRA_PATH=<arclog path> ARC14_ROOT=<state folder> bash -c \'<one line of a jobs file>\''
        m['task_set'] = t37 + ramp
        m['arm'] = dict(bundle='models-tk, seeds 0 and 1000, 59 tasks', refit='bundle plus NODE_SCORE=scores/refit.npz NODE_SCORE_MIX=.5',
                        parity='NODE_SCORE=scores/ship.npz NODE_SCORE_CHECK=1', refitcheck='refit at 120 s', smokebundle='bundle at 60 s', smokerefit='refit at 60 s',
                        refitp='refit on the 50 N600 tasks, seed 0, ARC_GOLD=points-n600.json')
        m['gold'] = dict(m.get('gold', {}), refit='points-eval.json: the 22 ramp tasks hold the ramp gold of gold-heldout-ramp-pass1/points-ramp.json; points-n600.json holds the 50 N600 tasks')
        m['node_score_files'] = dict(m['node_score_files'], **{'scores/refit.npz': sha256_of(kit + '/scores/refit.npz')})
        m['sha256'] = dict(m['sha256'], **{'points-eval.json': sha256_of(kit + '/points-eval.json'), 'points-n600.json': sha256_of(kit + '/points-n600.json')})
        m['reads'] = list(m['reads']) + ['scores/refit.npz', 'points-n600.json', 'data/tasks/* of the 50 N600 tasks', 'run3600.sh: ARC_GOLD from the environment']
        m['node_records'] = 'refitp lines write ARC_RECORD to out/refitp_s0/<task>' if record else 'none'
        m['training_eligibility'] = ('the 37 are held out; the 22 ramp tasks are training tasks of models-tk, not of the node score; the 50 N600 tasks feed the next fit '
                                     'and are not held-out tasks')
        m['built'] = datetime.datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S%z')
        m['refit'] = dict(round=rnd, state_sha256=sha256_of(state), stand_in=sha256_of(state) == STAND_IN_SHA, patch=os.path.basename(PATCH))
        json.dump(m, open(kit + '/manifest.json', 'w'), indent=1)

    stage(4, N, 'files', fp, out, files)

    def check_diff():
        base_dir = work + '/base/' + BASE_NAME
        added = {'scores/refit.npz', 'points-n600.json', 'refit-tasks.json', 'gold-ident-only-refit.json', names['jobs'], names['smoke'], names['positives']}
        edited = EDITED | {'points-eval.json', 'manifest.json', 'run3600.sh'}
        added |= {'data/tasks/%s.json' % t for t in open(N600_TASKS).read().split()}
        seen_new, seen_diff = set(), set()
        for root, _, fs in os.walk(kit):
            for f in fs:
                rel = os.path.relpath(os.path.join(root, f), kit)
                other = os.path.join(base_dir, rel)
                if not os.path.exists(other):
                    seen_new.add(rel)
                elif open(os.path.join(root, f), 'rb').read() != open(other, 'rb').read():
                    seen_diff.add(rel)
        gone = [os.path.relpath(os.path.join(root, f), base_dir) for root, _, fs in os.walk(base_dir) for f in fs if not os.path.exists(os.path.join(kit, os.path.relpath(os.path.join(root, f), base_dir)))]
        problems = []
        if gone:
            problems.append('removed: %s' % gone[:5])
        if seen_new != added:
            problems.append('new files differ from the plan: extra %s, missing %s' % (sorted(seen_new - added)[:5], sorted(added - seen_new)[:5]))
        if seen_diff != edited:
            problems.append('changed files differ from the plan: extra %s, missing %s' % (sorted(seen_diff - edited)[:5], sorted(edited - seen_diff)[:5]))
        # the patched files differ from the base by the lines of the patch, and by no other
        patch_lines = collections.Counter(x for x in open(PATCH).read().split('\n') if x and x[0] in '+-' and not x.startswith(('+++', '---')))
        got = collections.Counter()
        for rel in sorted(EDITED):
            a = open(os.path.join(base_dir, rel)).read().split('\n')
            b = open(os.path.join(kit, rel)).read().split('\n')
            got.update(x for x in difflib.unified_diff(a, b, lineterm='', n=0) if x and x[0] in '+-' and not x.startswith(('+++', '---')))
        if got != patch_lines:
            problems.append('lines of the 3 patched files differ from the patch lines by %s' % list(((got - patch_lines) + (patch_lines - got)).items())[:3])
        # run3600.sh differs in one line only
        a, b = open(base_dir + '/run3600.sh').read().split('\n'), open(kit + '/run3600.sh').read().split('\n')
        d = [x for x in difflib.unified_diff(a, b, lineterm='', n=0) if x and x[0] in '+-' and not x.startswith(('+++', '---'))]
        if len(d) != 2:
            problems.append('run3600.sh differs in %d lines' % len(d))
        # points-eval.json differs only in the entries of the ramp tasks
        pa, pb = {x['task']: x for x in json.load(open(base_dir + '/points-eval.json'))}, {x['task']: x for x in json.load(open(kit + '/points-eval.json'))}
        ramp = set(open(RAMP_DIR + '/ramp-fold.txt').read().split())
        if set(pa) != set(pb) or {t for t in pa if pa[t] != pb[t]} - ramp:
            problems.append('points-eval.json differs outside the ramp tasks')
        print('    new files %d, changed files %d: %s' % (len(seen_new), len(seen_diff), ' '.join(sorted(seen_diff))), flush=True)
        print('    patched files differ from the base by exactly the patch lines (%d lines)' % sum(patch_lines.values()), flush=True)
        print('    run3600.sh differs in one line; points-eval.json differs in %d ramp tasks' % len({t for t in pa if pa[t] != pb[t]}), flush=True)
        if problems:
            raise Stop('diff against the base kit: ' + '; '.join(problems))

    stage(5, N, 'diff', fp, out, check_diff)

    def pack():
        tar_path = '%s/%s.tar.gz' % (out, kit_name)
        entries = []
        for root, dirs, fs in os.walk(kit):
            dirs.sort()
            entries.append(root)
            entries += [os.path.join(root, f) for f in sorted(fs)]
        p = Progress('packed', len(entries))
        mtime = int(datetime.datetime(2026, 11, 1).timestamp())
        with open(tar_path + '.tmp', 'wb') as raw, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0, compresslevel=6) as gz, tarfile.open(fileobj=gz, mode='w') as t:
            for i, path in enumerate(entries):
                info = t.gettarinfo(path, arcname=os.path.join(kit_name, os.path.relpath(path, kit)).rstrip('/.'))
                info.uid = info.gid = 0
                info.uname = info.gname = ''
                info.mtime = mtime
                if info.isfile():
                    with open(path, 'rb') as f:
                        t.addfile(info, f)
                else:
                    t.addfile(info)
                p.step(i + 1)
        os.replace(tar_path + '.tmp', tar_path)
        for n in names.values():
            shutil.copy2('%s/%s' % (kit, n), '%s/%s' % (out, n))
        for n in ('refit-tasks.json', 'gold-ident-only-refit.json', 'points-eval.json', 'points-n600.json'):
            shutil.copy2('%s/%s' % (kit, n), '%s/%s' % (out, n))
        ctx['sha'] = sha256_of(tar_path)
        open(out + '/build/.tar-sha256', 'w').write(ctx['sha'])

    stage(6, N, 'pack', fp, out, pack)
    tar_path = '%s/%s.tar.gz' % (out, kit_name)
    sha = open(out + '/build/.tar-sha256').read() if os.path.exists(out + '/build/.tar-sha256') else sha256_of(tar_path)

    def manifest():
        km = json.load(open(kit + '/manifest.json'))
        card = json.load(open(card_path))
        t = json.load(open(kit + '/refit-tasks.json'))
        before = {x['task']: x['gold_sexp'] for x in json.load(open(base_dir_gold()))}
        after = {x['task']: x['gold_sexp'] for x in json.load(open(kit + '/points-eval.json'))}
        ramp_changed = sorted(x for x in after if before[x] != after[x])
        stand_in = sha256_of(state) == STAND_IN_SHA
        man = dict(
            name='search-refit-%s-heldout37-ramp22-2seeds-600s-0729e4943' % rnd,
            alias='refit node score %s, mixed with the ship score on half the openings, against the bundle' % rnd,
            round=rnd,
            kit='%s.tar.gz' % kit_name, kit_sha256=sha, kit_sha256_24=sha[:24],
            jobs=names['jobs'], smoke_jobs=names['smoke'], positives_jobs=names['positives'],
            commit='kit %s (sha256 %s) with node-score/2-node-score-mix.patch (patch 1, the Ident INIT patience, is not applied); edits listed in the kit manifest' % (BASE_NAME, BASE_SHA_START),
            wheel_engine=dict(km['wheel_engine'], sha256_checked_in_kit=sha256_of(kit + '/arclog-0.1.0-cp312-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl') == km['wheel_engine']['sha256']),
            model=dict(state=state, state_sha256=sha256_of(state), card=card_path, card_name=card.get('name'), sha256_file=shafile, node_score_file='scores/refit.npz',
                       node_score_sha256=sha256_of(kit + '/scores/refit.npz'), marker_name='refit', features=card.get('features'), t=card.get('t'),
                       stand_in=stand_in, stand_in_note='the M-T model stands in for the real model; the numbers of this build are not a result' if stand_in else None),
            gold=dict(file='kit/points-eval.json', sha256_8=sha256_of(kit + '/points-eval.json')[:8], ramp='the 22 ramp entries hold gold-heldout-ramp-pass1/points-ramp.json; entries that differ from the base kit file: %s' % ' '.join(ramp_changed),
                      ident_only='gold-ident-only-refit.json: the 37 from node-score/gold-ident-only-kit50.json, the 22 from search_node_score_gold_ident.py on the ramp gold with the Mac engine and ARCLOG_IDENT_SOURCE=value',
                      n600='kit/points-n600.json, the first row gold_sexp of gold-v3-combined-cut/view-final/<task>/pairs.jsonl.gz'),
            task_set=dict(heldout37=t['heldout37'], ramp22=t['ramp22'], n600='50 tasks of features-node-score-refit-loop/n600-tasks.txt, positives jobs only'),
            budget='%d lines: 3 check lines (2 parity at %d s, 1 refitcheck at %d s), then 236 lines of bundle and refit on 59 tasks at 2 seeds, %d s wall; smoke 4 lines at %d s; positives 50 lines at %d s' % (
                3 + 236, PARITY_SECONDS, CHECK_SECONDS, SECONDS, SMOKE_SECONDS, SECONDS),
            arms=[
                'bundle: dagk of %s: ORDER_FREE=tie,key, models-tk, ARCLOG_IDENT_SOURCE=value, SAME_POD per task' % BASE_NAME,
                'refit: bundle plus NODE_SCORE=$PWD/scores/refit.npz NODE_SCORE_MIX=.5',
                'ramp tasks use models-tk, as the bundle; they are training tasks of models-tk, and not of the node score'],
            report='search_refit_read.py RUN_FOLDER OUT.json [--returns DIR]; search_refit_check.py RUN_FOLDER; search_refit_smoke.py RUN_FOLDER OUT.json',
            prediction=None, decision_rule=None,
            training_eligible='The 37 are held out. The 22 ramp tasks are training tasks of models-tk. The node score saw none of the 37, the 22, the 99 or the drifted tasks. The refitp run on the 50 N600 tasks feeds the next fit.',
            start=None, pod_cpu=None, result=None,
            kit_check='diff against the base kit shows only the edits of the kit manifest; the converter printed PASS',
            patches='node-score/2-node-score-mix.patch',
            built=datetime.datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S%z'))
        json.dump(man, open(out + '/manifest.json', 'w'), indent=1)

    def base_dir_gold():
        return work + '/base/' + BASE_NAME + '/points-eval.json'

    manifest()
    print('[7/7] manifest: %s/manifest.json' % out, flush=True)
    print('done in %.0f s' % (time.time() - t_start))
    print('kit %s' % tar_path)
    print('sha256 %s' % sha)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Stop as e:
        print('search_refit_build: %s' % e, file=sys.stderr)
        sys.exit(e.code)
