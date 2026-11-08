"""The live search on the dev or train tasks of the split, in arms that differ only by the writer's tree, judged by solves on the test example.

    run_heavy.py --cpus JOBS --need soon dev_run.py RUN --code DIR --site DIR [--models DIR] [--tree FILE] [--split dev|train] [--arms tree] [--seeds 0] [--seconds 120] [--jobs JOBS] [--tasks N] [--skip TASK,...] [--record]

RUN names the output folder, $DATA/search/dev161/RUN for dev and $DATA/search/train866/RUN for train (DATA is study_paths.DATA_ROOT). DIR holds model/study, a kit made from a commit.
Every arm runs under one writer plan (WRITER_PLAN): the plan that --tree records (sampler/writer_plan.py).
Each job is one task of one arm and one seed: the search of --source (the one search over the graph, or the state search) with the v9 notebook's
environment and a fresh store of its own. --models
is the worker's models folder (default the v9 dataset's), and --tree the writer's tree of the arms that take one. With
--budget cpu (the default), one worker runs on --seconds of its own CPU time (cpu_clock/sitecustomize.py), and the kernel supervisor's
code (supervisor.py beside the --code kit, else the v9 dataset's) makes the submission from its candidates. With --budget wall, the
kernel supervisor runs it for --seconds of wall-clock time. The jobs of a task
run next to each other, so the arms are paired as results arrive.

Each finished job appends one line to results.jsonl: task, arm, seed, job (its folder under jobs/), solved (every test example has an attempt equal to its output),
candidates, draws, CPU seconds, deaths and kills, and seconds. A restart skips the jobs that have a line. With --budget cpu, an
attempt that reaches --wall-cap before it has used its CPU budget writes its line to capped.jsonl, with the CPU it used, and the job
runs again in a fresh folder when the limit lets it; the capped attempt's folder, with its draws, is not the job's result. summary.txt is rewritten after each line, and runs.jsonl gets each start's arguments and the kit's manifest. The file <RUN>/limit, where it
holds a number, sets how many jobs run at once while the run goes on.
The run stops where its first STOP_AFTER jobs all die with no draw. Held-out tasks never run, and --skip leaves out the tasks it lists. With --record, each worker writes one draw record per draw to the
job's draws.jsonl (sampler/draw_record.py), which becomes draws.jsonl.zst when the job ends (draw_file.py).
"""
import argparse, random
import collections
import concurrent.futures as cf
import hashlib
import importlib.util
import json
import pickle
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from study_paths import DATA_ROOT, MAIN_ROOT  # noqa: E402

DATASET = MAIN_ROOT / 'work/synth-kaggle/kernel-writer-dry8/dataset'  # the v9 bundle's dataset: models, policy model, supervisor
PY = MAIN_ROOT / 'work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python'
TREE = DATA_ROOT / 'samples/models/training-ordered-vec750-p1.txt'
sys.path.insert(0, str(Path(__file__).resolve().parent))
import draw_file  # noqa: E402

POPPED = ('WRITER_TREE', 'WRITER_PLAN', 'SEARCH_STATE_SCORE')
ARMS = {'tree': {'WRITER_TREE': None}, 'tok': {'WRITER_TREE': None}, 'fast': {'WRITER_TREE': None}, 'base': {'WRITER_TREE': None}}  # WRITER_TREE None: --tree; tok and fast: tree under other names, so that two runs of different kits or sites pair by reach.py's --arms
RSS_LIMIT_MIB = 2888
STOP_AFTER = 4  # the run stops where its first STOP_AFTER jobs all die with no draw
WORK_GUARD = 4  # with --budget work, a worker's CPU seconds past this times --seconds end it, whatever its work
LOCK = threading.Lock()
RUNNING = [0]  # the jobs running now
CPU_MODE = [False]  # --budget cpu, where a worker's clock is its CPU time


OUT_DIRS = {'dev': 'dev161', 'train': 'train866'}


def split_tasks(split):
    if split not in OUT_DIRS:
        sys.exit('split %r: only dev and train run' % split)
    lines = (DATA_ROOT / 'samples/split.tsv').read_text().splitlines()[1:]
    return sorted(l.split('\t')[0] for l in lines if l.split('\t')[1] == split)


def solved(task, sub):
    """Whether each test example of task has an attempt equal to its output, and the count of test examples."""
    tests = json.loads((MAIN_ROOT / 'data/tasks' / (task + '.json')).read_text())['test']
    got = sub.get(task, [])
    ok = len(got) == len(tests) and all(any(a.get(k) == t['output'] for k in ('attempt_1', 'attempt_2')) for a, t in zip(got, tests))
    return ok, len(tests)


def effort(w):
    """(draws, CPU seconds) of a job's workers: the draws of the last end line, else of the last progress line, and the CPU seconds summed over
    the worker processes (a process's CPU count goes on across a renewal's execv and starts again in a new worker)."""
    draws, cpu, seg = 0, 0.0, 0.0
    for p in (w / 'work').glob('*.log'):
        for l in p.read_text(errors='replace').splitlines():
            m = re.match(r'rss \d+ at \d+ s of \d+, cpu (\d+) s, (\d+) samples', l)
            if m:
                c = float(m.group(1))
                if c < seg:
                    cpu += seg
                seg, draws = c, int(m.group(2))
            m = re.match(r'end: [^,]*, (\d+) draws.*, (\d+) s$', l)
            if m:
                draws = int(m.group(1))
                if os.environ.get('ARC_CPU_CLOCK') == '1' or CPU_MODE[0]:  # the end line's seconds are the process's CPU seconds
                    seg = max(seg, float(m.group(2)))
    return draws, round(cpu + seg)


def work_of(w):
    """The engine work of the job's worker: the sum of the `clock: work W cpu S` lines of its logs, which the worker writes at its end and at each renewal (arclog.work_total), or None
    where an engine build or a worker writes none."""
    found = [int(m.group(1)) for p in (w / 'work').glob('*.log') for l in p.read_text(errors='replace').splitlines() if (m := re.match(r'clock: work (\d+) cpu', l))]
    return sum(found) if found else None


def gate(out, a):
    """Waits until fewer jobs run than the limit in the file <out>/limit (default --jobs), which can be changed while the run goes on."""
    while True:
        try:
            limit = int((out / 'limit').read_text())
        except (OSError, ValueError):
            limit = a.jobs
        with LOCK:
            if RUNNING[0] < limit:
                RUNNING[0] += 1
                return
        time.sleep(5)


def job(a, out, task, arm, seed):
    """Runs the job until an attempt ends within the wall cap: a capped attempt waits at the gate again and runs anew."""
    while True:
        gate(out, a)
        try:
            rec = run_job(a, out, task, arm, seed)
        finally:
            with LOCK:
                RUNNING[0] -= 1
        if rec['rc'] != 'wall cap':
            return rec


def cpu_job(a, w, task, seed, env, samp, sup):
    """One worker of the task on a budget of a.seconds of its own CPU time (cpu_clock/sitecustomize.py), with no supervisor, so a death
    ends the job. The submission is the supervisor's: its candidates best first, two attempts per test input. Gives (rc, log text, submission)."""
    work = w / 'work'
    work.mkdir()
    clock = dict(ARC_WORK_CLOCK=str(a.work_rate), ARC_WORK_GUARD=str(WORK_GUARD * a.seconds)) if a.budget == 'work' else dict(ARC_CPU_CLOCK='1')
    env = dict(env, **clock, PYTHONPATH='%s:%s' % (Path(__file__).resolve().parent / 'cpu_clock', env['PYTHONPATH']))
    out = work / (task + '.out.jsonl')
    (work / (task + '.beat')).touch()
    cmd = [str(PY), '-u', str(samp / 'kaggle_worker.py'), '--task', str(MAIN_ROOT / 'data/tasks' / (task + '.json')), '--out', str(out),
           '--beat', str(work / (task + '.beat')), '--seconds', str(a.seconds), '--seed', str(1000 * seed), '--rss-limit-mib', str(RSS_LIMIT_MIB)]
    with open(work / (task + '.log'), 'w') as log:
        try:
            rc = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=a.wall_cap).returncode
        except subprocess.TimeoutExpired:
            rc = 'wall cap'
    spec = importlib.util.spec_from_file_location('kernel_supervisor', sup)
    S = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(S)
    challenges = json.loads((w / 'challenges.json').read_text())
    S.write_submission(str(w / 'submission.json'), challenges, {task: S.read_candidates(str(out))})
    died = rc not in (0, 'wall cap')
    text = 'submission written; deaths %d kills %d' % (int(died), int(rc == 'wall cap'))
    return rc, text, json.loads((w / 'submission.json').read_text())


def check_priors(a):
    """Refuses a run whose live_priors.pkl was fitted on a task outside the train split, or does not record its tasks (live_priors.py writes fit_tasks): such priors have seen the gold of the tasks a run reads."""
    split = {t: s for t, s, *_ in (l.split('\t') for l in (DATA_ROOT / 'samples/split.tsv').read_text().splitlines()[1:])}
    for models in {a.models, a.base_models} - {None}:
        with open(Path(models) / 'live_priors.pkl', 'rb') as f:
            fit = pickle.load(f).get('fit_tasks')
        bad = None if fit is None else sorted(t for t in fit if split.get(t, 'train') != 'train')
        if (fit is None or bad) and not a.allow_dev_priors:
            raise SystemExit('%s/live_priors.pkl %s: a run may read only priors fitted on train tasks (live_priors.py --leave-out). --allow-dev-priors runs it anyway.' % (models, 'does not record its tasks' if fit is None else 'was fitted on %d tasks outside train, such as %s' % (len(bad), bad[:3])))


def arm_tree(a, arm):
    """The tree of an arm: --base-tree for the arm base, which runs beside the others under one load, and --tree for every other arm."""
    return a.base_tree if arm == 'base' and a.base_tree else a.tree


def parity_gate(a, out, arm, tasks):
    """Refuses a live run whose worker gives a model other input rows than training rows: a short worker on a few tasks writes a sample of its points (WRITER_PARITY_DIR), and sampler/serving_parity.py rebuilds them at a session as rows make it. A stamp in the code's folder keeps a pass for this sampler code, site, tree and writer settings."""
    samp = Path(a.code) / 'model/study/sampler'
    if not (samp / 'serving_parity.py').exists():
        raise SystemExit('this kit has no serving parity check: %s has no serving_parity.py. --no-parity runs it unchecked.' % samp)
    settings = sorted((k, v) for k, v in os.environ.items() if k.startswith('WRITER_') and k != 'WRITER_PARITY_DIR')
    code = hashlib.sha256(b''.join(p.read_bytes() for p in sorted(samp.glob('*.py')))).hexdigest()  # a change to the sampler's code needs a new check
    tree = arm_tree(a, arm)
    key = hashlib.sha256(json.dumps([a.site, str(tree), a.plan, settings, code] + (sorted(a.tok_env) if arm != 'base' else [])).encode()).hexdigest()[:16]
    stamp = Path(a.code) / 'parity' / (key + '.json')
    if stamp.exists():
        return
    folder = out / ('parity' if arm != 'base' else 'parity-base')  # each tree's check has its own folder
    short = argparse.Namespace(**{**vars(a), 'seconds': 25})
    for task in tasks[:3]:
        w = folder / task
        w.mkdir(parents=True)
        d = json.loads((MAIN_ROOT / 'data/tasks' / (task + '.json')).read_text())
        (w / 'challenges.json').write_text(json.dumps({task: dict(train=d['train'], test=[dict(input=x['input']) for x in d['test']])}))
        env = job_env(a, w, arm, 0)
        env['WRITER_PARITY_DIR'] = str(folder)
        sup = Path(a.code) / 'supervisor.py'
        cpu_job(short, w, task, 0, env, samp, sup if sup.exists() else DATASET / 'supervisor.py')
    env = job_env(a, folder, arm, 0)
    env.update(ARC_ROOT=str(MAIN_ROOT), ARCLOG_IDENT_SOURCE='value', PYTHONPATH='%s:%s:%s' % (a.site, samp, Path(a.code) / 'model/study/samples'))
    env.pop('ARC_DRAW_RECORD', None)
    got = subprocess.run([str(PY), str(samp / 'serving_parity.py'), str(folder), '--tree', str(tree), '--models', str(a.models)], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(got.stdout[-3000:], flush=True)
    if got.returncode:
        raise SystemExit('serving parity failed: this run would read other rows than its model was fit on. Details above; --no-parity runs it anyway.')
    stamp.parent.mkdir(exist_ok=True)
    stamp.write_text(json.dumps(dict(site=a.site, tree=str(tree), plan=a.plan, settings=settings, report=got.stdout[-2000:])))


def job_env(a, w, arm, seed):
    samp = Path(a.code) / 'model/study/sampler'
    env = dict(os.environ, PYTHONPATH='%s:%s' % (a.site, samp), ARC_MODELS=str(a.base_models if arm == 'base' and a.base_models else a.models), ARC_POLICY=str(Path(a.code) / 'model/study/policy'),
               POOL_CLAUSES=a.source, ARC_SEED_BASE=str(1000 * seed),
               RUST_BACKTRACE='1', RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
               NUMEXPR_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1', ARCLOG_IDENT_SOURCE='value')  # an Ident cell is a digest of its content; unset, it is an intern number, which depends on the order of interning
    for k in POPPED:
        env.pop(k, None)
    env.update({k: v if v is not None else str(arm_tree(a, arm)) for k, v in ARMS[arm].items()}, WRITER_PLAN=a.plan)
    if arm != 'base':  # --tok-env: env of every arm but base
        env.update(dict(x.split('=', 1) for x in a.tok_env))
    return env


def run_job(a, out, task, arm, seed):
    n = 0
    while (out / 'jobs' / ('%s.%s.s%d.%d' % (task, arm, seed, n))).exists():  # an attempt that a stopped run left keeps its folder; each attempt has a fresh store
        n += 1
    w = out / 'jobs' / ('%s.%s.s%d.%d' % (task, arm, seed, n))
    w.mkdir(parents=True)
    d = json.loads((MAIN_ROOT / 'data/tasks' / (task + '.json')).read_text())
    (w / 'challenges.json').write_text(json.dumps({task: dict(train=d['train'], test=[dict(input=x['input']) for x in d['test']])}))
    samp = Path(a.code) / 'model/study/sampler'
    env = job_env(a, w, arm, seed)
    if a.gate_records:  # each form at the gate (live.GateRecords): its program form, test attempts, leave-one-out result and decision, in the job's folder
        env.update(GATE_RECORDS=str(w), GATE_RECORD_TASK=task)
    if a.record:  # the draw records (sampler/draw_record.py), one file per job
        env.update(ARC_DRAW_RECORD=str(w / 'draws.jsonl'), ARC_DRAW_RUN='%s/%s' % (a.run, w.name), ARC_DRAW_SITE=Path(a.site).name,
                   ARC_DRAW_RELEASE=Path(a.code).name)
    sup = Path(a.code) / 'supervisor.py'
    sup = sup if sup.exists() else DATASET / 'supervisor.py'
    t0 = time.time()
    if a.budget in ('cpu', 'work'):
        rc, text, sub = cpu_job(a, w, task, seed, env, samp, sup)
    else:
        cmd = [str(PY), '-u', str(sup), '--challenges', str(w / 'challenges.json'),
               '--submission', str(w / 'submission.json'), '--work', str(w / 'work'), '--seconds', str(a.seconds), '--workers', '1',
               '--rss-limit-mib', str(RSS_LIMIT_MIB), '--worker-cmd', '%s -u %s' % (PY, samp / 'kaggle_worker.py')]
        with open(w / 'supervisor.log', 'w') as log:
            rc = subprocess.run(cmd, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=a.seconds + 600).returncode
        text = (w / 'supervisor.log').read_text()
        sub = json.loads((w / 'submission.json').read_text()) if (w / 'submission.json').exists() else {}
    ok, ntest = solved(task, sub)
    last = next((l for l in reversed(text.splitlines()) if 'submission written; deaths' in l), '')
    dk = re.search(r'deaths (\d+) kills (\d+)', last)
    cands = sum(1 for p in (w / 'work').glob('*.out.jsonl') for l in open(p) if l.strip())
    draws, cpu = effort(w)
    draw_file.compress(w)
    rec = dict(task=task, arm=arm, seed=seed, job=w.name, budget=a.budget, solved=ok, tests=ntest, candidates=cands, draws=draws, cpu=cpu, work=work_of(w), rc=rc, seconds=round(time.time() - t0, 1),
               deaths=int(dk.group(1)) if dk else None, kills=int(dk.group(2)) if dk else None,
               tracebacks=sum(p.read_text(errors='replace').count('Traceback') for p in (w / 'work').glob('*.log')))
    with LOCK:
        with open(out / ('capped.jsonl' if rc == 'wall cap' else 'results.jsonl'), 'a') as f:
            f.write(json.dumps(rec) + '\n')
        summary(out)
    return rec


def summary(out):
    recs = [json.loads(l) for l in open(out / 'results.jsonl')]
    by = collections.defaultdict(list)
    for r in recs:
        by[(r['arm'], r['seed'])].append(r)
    lines = []
    for (arm, seed), rs in sorted(by.items()):
        lines.append('%s s%d: %d tasks, %d solved, %d with a candidate, %d tracebacks, %d kills' % (
            arm, seed, len(rs), sum(r['solved'] for r in rs), sum(r['candidates'] > 0 for r in rs), sum(r['tracebacks'] for r in rs), sum(r['kills'] or 0 for r in rs)))
    tasks = {r['task'] for r in recs}
    arms = {r['arm'] for r in recs}
    paired = [t for t in tasks if all(any(r['task'] == t and r['arm'] == arm for r in recs) for arm in arms)]
    solved = {arm: {r['task'] for r in recs if r['arm'] == arm and r['solved']} for arm in arms}
    lines.append('paired tasks: %d; %s' % (len(paired), '; '.join('solved only by %s: %s' % (arm, sorted(t for t in paired if t in solved[arm] and not any(t in solved[o] for o in arms if o != arm))) for arm in sorted(arms))))
    (out / 'summary.txt').write_text('\n'.join(lines) + '\n')


def run_plan(a):
    """The writer plan of every arm: the plan that --tree records (sampler/writer_plan.py). Raises where
    WRITER_PLAN and the tree give different plans."""
    spec = importlib.util.spec_from_file_location('writer_plan', Path(__file__).resolve().parents[2] / 'sampler/writer_plan.py')
    assert spec is not None and spec.loader is not None
    wp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wp)
    tree = str(a.tree) if any(arm != 'base' for arm in a.arms.split(',')) else None
    plan = wp.plan_of_process(tree, os.environ.get('WRITER_PLAN'))[0]
    if 'base' in a.arms.split(','):
        other = wp.plan_of_process(str(a.base_tree or a.tree), os.environ.get('WRITER_PLAN'))[0]
        if tree is not None and other != plan:
            raise SystemExit('--base-tree gives the plan %s and --tree gives %s: a run has one plan' % (other, plan))
        plan = other
    return plan


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run')
    ap.add_argument('--code', required=True)
    ap.add_argument('--site', required=True)
    ap.add_argument('--models', default=str(DATASET))
    ap.add_argument('--tree', default=str(TREE))
    ap.add_argument('--base-models', help='the models folder of the arm base; --models where not given')
    ap.add_argument('--allow-dev-priors', action='store_true', help='runs with a priors file fitted on dev or held-out tasks, or one that does not say which tasks it fitted on (check_priors)')
    ap.add_argument('--base-tree', help='the tree of the arm base, which runs beside the other arms under one load; --tree where not given')
    ap.add_argument('--skip', default='')
    ap.add_argument('--arms', default='tree')
    ap.add_argument('--source', choices=('search', 'state'), default='search', help='search: the pool search (superdag_search.py); state: the state search (state_search.py)')
    ap.add_argument('--seeds', default='0')
    ap.add_argument('--seconds', type=int, default=120)
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--tasks', type=int, default=0)
    ap.add_argument('--tok-env', action='append', default=[], help='KEY=VALUE in the env of every arm but base; may repeat')
    ap.add_argument('--gate-records', action='store_true', help='each job writes the gate\'s record of every form at the gate into its folder (gate-records/<task>.jsonl.gz)')
    ap.add_argument('--task-list', help='a file of the tasks to run, one a line, in its order, in place of the split\'s')
    ap.add_argument('--shuffle', type=int, help='takes the split\'s tasks in an order that this seed shuffles, so that --tasks gives a mixed sample')
    ap.add_argument('--split', default='dev')
    ap.add_argument('--record', action='store_true', help='each worker writes its draw records')
    ap.add_argument('--no-parity', action='store_true', help='runs with no check that a worker gives the model the rows it was fit on (parity_gate)')
    ap.add_argument('--budget', choices=('cpu', 'wall', 'work'), default='cpu', help='cpu: --seconds of the worker\'s own CPU time; wall: --seconds of wall-clock time, under the kernel supervisor; '
                    'work: --seconds of the engine\'s work at --work-rate units a second (arclog.work_total), the same on any machine, with WORK_GUARD times --seconds of CPU as the outer guard')
    ap.add_argument('--work-rate', type=float, help='with --budget work: the engine work units that one second of the budget is')
    ap.add_argument('--wall-cap', type=int, default=1800, help='with --budget cpu, the wall-clock seconds after which a job is killed')
    a = ap.parse_args()
    if a.budget == 'work' and not a.work_rate:
        ap.error('--budget work needs --work-rate')
    a.plan = run_plan(a)
    check_priors(a)
    CPU_MODE[0] = a.budget == 'cpu'
    out = DATA_ROOT / 'search' / OUT_DIRS.get(a.split, 'none') / a.run
    out.mkdir(parents=True, exist_ok=True)
    with open(out / 'runs.jsonl', 'a') as f:  # each start's arguments and the kit's manifest
        man = Path(a.code) / 'manifest.json'
        f.write(json.dumps(dict(time=time.strftime('%Y-%m-%dT%H:%M:%S%z'), args=vars(a), manifest=json.loads(man.read_text()) if man.exists() else None)) + '\n')
    done = set()
    if (out / 'results.jsonl').exists():
        done = {(r['task'], r['arm'], r['seed']) for r in map(json.loads, open(out / 'results.jsonl'))}
    tasks = [t for t in (open(a.task_list).read().split() if a.task_list else split_tasks(a.split)) if t not in a.skip.split(',')]
    if a.shuffle is not None:
        random.Random(a.shuffle).shuffle(tasks)
    tasks = tasks[:a.tasks or None]
    todo = [(t, arm, int(s)) for t in tasks for s in a.seeds.split(',') for arm in a.arms.split(',') if (t, arm, int(s)) not in done]
    if not a.no_parity and a.budget in ('cpu', 'work'):
        for arm in a.arms.split(','):
            parity_gate(a, out, arm, tasks)
    print('%d %s tasks, %d jobs to run, %d done' % (len(tasks), a.split, len(todo), len(done)), flush=True)
    t0, n, dead = time.time(), 0, 0
    with cf.ThreadPoolExecutor(max(16, a.jobs)) as ex:  # gate() holds the jobs to the limit; a pool smaller than --jobs would hold them below it
        for fut in cf.as_completed([ex.submit(job, a, out, *j) for j in todo]):
            r = fut.result()
            n += 1
            dead += r['deaths'] == 1 and r['draws'] == 0
            if n == STOP_AFTER and dead == n:
                print('the first %d jobs all died with no draw: the run stops' % n, flush=True)
                os._exit(1)
            rate = n / (time.time() - t0)
            print('%s %s s%d solved %s cands %d kills %d tb %d | %d/%d, ETA %.0f min' % (
                r['task'], r['arm'], r['seed'], r['solved'], r['candidates'], r['kills'], r['tracebacks'], n, len(todo), (len(todo) - n) / rate / 60), flush=True)


if __name__ == '__main__':
    main()
