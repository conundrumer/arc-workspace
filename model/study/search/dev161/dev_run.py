"""The live search on the dev or train tasks of the split, in arms that differ only by the writer's tree, judged by solves on the test example.

    run_heavy.py --cpus JOBS --need soon dev_run.py RUN --code DIR --site DIR [--models DIR] [--tree FILE] [--split dev|train] [--arms tree,hand] [--seeds 0] [--seconds 120] [--jobs JOBS] [--tasks N] [--skip TASK,...] [--record]

RUN names the output folder, $DATA/search/dev161/RUN for dev and $DATA/search/train866/RUN for train (DATA is study_paths.DATA_ROOT). DIR holds model/study, a kit made from a commit.
Each job is one task of one arm and one seed: the pool search with the v9 notebook's environment and a fresh store of its own. --models
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
job's draws.jsonl (sampler/draw_record.py).
"""
import argparse
import collections
import concurrent.futures as cf
import importlib.util
import json
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
ARMS = {'tree': {'WRITER_TREE': None}, 'hand': {}, 'tree_reads': {'WRITER_TREE': None, 'WRITER_LEGAL_ADD': 'ReadsScope'}, 'tree_first': {'WRITER_TREE': None, 'WRITER_LEGAL_ADD': 'ReadsScopeFirst'},
        'tree_fp': {'WRITER_TREE': None, 'FIRST_PASS_SECONDS': '4'}, 'tree_first_fp': {'WRITER_TREE': None, 'WRITER_LEGAL_ADD': 'ReadsScopeFirst', 'FIRST_PASS_SECONDS': '4'}}  # WRITER_TREE None: --tree; the checks of the ReadsScope rules
RSS_LIMIT_MIB = 2888
STOP_AFTER = 4  # the run stops where its first STOP_AFTER jobs all die with no draw
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
    env = dict(env, ARC_CPU_CLOCK='1', PYTHONPATH='%s:%s' % (Path(__file__).resolve().parent / 'cpu_clock', env['PYTHONPATH']))
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


def run_job(a, out, task, arm, seed):
    n = 0
    while (out / 'jobs' / ('%s.%s.s%d.%d' % (task, arm, seed, n))).exists():  # an attempt that a stopped run left keeps its folder; each attempt has a fresh store
        n += 1
    w = out / 'jobs' / ('%s.%s.s%d.%d' % (task, arm, seed, n))
    w.mkdir(parents=True)
    d = json.loads((MAIN_ROOT / 'data/tasks' / (task + '.json')).read_text())
    (w / 'challenges.json').write_text(json.dumps({task: dict(train=d['train'], test=[dict(input=x['input']) for x in d['test']])}))
    samp = Path(a.code) / 'model/study/sampler'
    env = dict(os.environ, PYTHONPATH='%s:%s' % (a.site, samp), ARC_MODELS=str(a.models), ARC_POLICY=str(Path(a.code) / 'model/study/policy'),
               POLICY_MODEL=str(DATASET / 'policy_model.pkl'), POOL_CLAUSES='search', ARC_STORE=str(w / 'store'), ARC_SEED_BASE=str(1000 * seed),
               RUST_BACKTRACE='1', RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
               NUMEXPR_NUM_THREADS='1', PYTHONDONTWRITEBYTECODE='1')
    for k in ('WRITER_TREE', 'WRITER_LEGAL_ADD', 'FIRST_PASS_SECONDS', 'FIRST_PASS_RULE', 'WRITER_LOOKAHEAD', 'ORDER_FREE', 'ONE_REPAIR', 'P_DAG', 'ARCLOG_IDENT_SOURCE', 'WRITER', 'SEARCH_STATE_SCORE'):
        env.pop(k, None)
    env.update({k: v if v is not None else str(a.tree) for k, v in ARMS[arm].items()})
    if a.record:  # the draw records (sampler/draw_record.py), one file per job
        env.update(ARC_DRAW_RECORD=str(w / 'draws.jsonl'), ARC_DRAW_RUN='%s/%s' % (a.run, w.name), ARC_DRAW_SITE=Path(a.site).name,
                   ARC_DRAW_RELEASE=Path(a.code).name)
    sup = Path(a.code) / 'supervisor.py'
    sup = sup if sup.exists() else DATASET / 'supervisor.py'
    t0 = time.time()
    if a.budget == 'cpu':
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
    rec = dict(task=task, arm=arm, seed=seed, job=w.name, budget=a.budget, solved=ok, tests=ntest, candidates=cands, draws=draws, cpu=cpu, rc=rc, seconds=round(time.time() - t0, 1),
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
    lines.append('paired tasks: %d; solved only by tree: %s; only by hand: %s' % (
        len(paired), sorted(t for t in paired if any(r['task'] == t and r['arm'] == 'tree' and r['solved'] for r in recs) and not any(r['task'] == t and r['arm'] == 'hand' and r['solved'] for r in recs)),
        sorted(t for t in paired if any(r['task'] == t and r['arm'] == 'hand' and r['solved'] for r in recs) and not any(r['task'] == t and r['arm'] == 'tree' and r['solved'] for r in recs))))
    (out / 'summary.txt').write_text('\n'.join(lines) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run')
    ap.add_argument('--code', required=True)
    ap.add_argument('--site', required=True)
    ap.add_argument('--models', default=str(DATASET))
    ap.add_argument('--tree', default=str(TREE))
    ap.add_argument('--skip', default='')
    ap.add_argument('--arms', default='tree,hand')
    ap.add_argument('--seeds', default='0')
    ap.add_argument('--seconds', type=int, default=120)
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--tasks', type=int, default=0)
    ap.add_argument('--split', default='dev')
    ap.add_argument('--record', action='store_true', help='each worker writes its draw records')
    ap.add_argument('--budget', choices=('cpu', 'wall'), default='cpu', help='cpu: --seconds of the worker\'s own CPU time; wall: --seconds of wall-clock time, under the kernel supervisor')
    ap.add_argument('--wall-cap', type=int, default=1800, help='with --budget cpu, the wall-clock seconds after which a job is killed')
    a = ap.parse_args()
    CPU_MODE[0] = a.budget == 'cpu'
    out = DATA_ROOT / 'search' / OUT_DIRS.get(a.split, 'none') / a.run
    out.mkdir(parents=True, exist_ok=True)
    with open(out / 'runs.jsonl', 'a') as f:  # each start's arguments and the kit's manifest
        man = Path(a.code) / 'manifest.json'
        f.write(json.dumps(dict(time=time.strftime('%Y-%m-%dT%H:%M:%S%z'), args=vars(a), manifest=json.loads(man.read_text()) if man.exists() else None)) + '\n')
    done = set()
    if (out / 'results.jsonl').exists():
        done = {(r['task'], r['arm'], r['seed']) for r in map(json.loads, open(out / 'results.jsonl'))}
    tasks = [t for t in split_tasks(a.split) if t not in a.skip.split(',')][:a.tasks or None]
    todo = [(t, arm, int(s)) for t in tasks for s in a.seeds.split(',') for arm in a.arms.split(',') if (t, arm, int(s)) not in done]
    print('%d %s tasks, %d jobs to run, %d done' % (len(tasks), a.split, len(todo), len(done)), flush=True)
    t0, n, dead = time.time(), 0, 0
    with cf.ThreadPoolExecutor(16) as ex:  # gate() holds the jobs to the limit
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
