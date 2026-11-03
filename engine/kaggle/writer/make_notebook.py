#!/usr/bin/env python3
"""Writes notebook.ipynb: one cell of the standard library, which never raises."""
import json
import pathlib
import sys

CELL = r'''
# The whole run. Only the standard library runs in this process, and no failure of what it starts can stop the submission file.
import glob, hashlib, json, os, shutil, subprocess, sys, tarfile, time, traceback

T0 = time.time()
SUBMISSION = '/kaggle/working/submission.json'
PRIVATE_SUBMISSION = '/kaggle/working/private_submission.json'
RECORD_LIMIT = 15 << 30  # the most record.tar may hold, under Kaggle's output limit
RERUN = bool(os.environ.get('KAGGLE_IS_COMPETITION_RERUN'))
RERUN_SECONDS = 11 * 3600
ROOT = '/tmp/arc'


def log(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def fallback(challenges):
    def grid(t):
        return t['input'] if isinstance(t, dict) and t.get('input') else [[0]]
    return {k: [dict(attempt_1=grid(t), attempt_2=grid(t)) for t in v['test']] for k, v in challenges.items()}


def one(pattern):
    got = glob.glob('/kaggle/input/**/' + pattern, recursive=True)
    return got[0] if got else None


def run():
    path = one('arc-agi_test_challenges.json')
    with open(path, 'rb') as f:
        raw = f.read()
    digest = hashlib.sha256(raw).hexdigest()
    log('challenges', path, 'rerun', RERUN, 'sha256', digest)
    challenges = json.loads(raw)
    with open(SUBMISSION, 'w') as f:
        json.dump(fallback(challenges), f)
    log('tasks', len(challenges), 'fallback written')
    with open(one('run_config.json')) as f:
        config = json.load(f)
    seconds = RERUN_SECONDS if RERUN else config['seconds']
    tasks = 0 if RERUN else config['tasks']
    chosen = one('private_tasks.json')
    private = not RERUN and chosen and digest == config.get('test_sha256')  # any other test file is the competition's, whatever the variable says
    log('private tasks', bool(private), 'pool', config.get('pool'))
    data = os.path.dirname(one('supervisor.py'))
    os.makedirs(ROOT + '/code', exist_ok=True)
    with tarfile.open(data + '/code.bin') as t:
        t.extractall(ROOT + '/code', filter='data')
    for wheel in sorted(glob.glob(data + '/*.whl')):  # each wheel on its own, so one that fails to install leaves the others
        r = subprocess.run([sys.executable, '-m', 'pip', 'install', '--quiet', '--no-index', '--no-deps', '--target', ROOT + '/site', wheel], capture_output=True, text=True, timeout=600)
        log('pip', os.path.basename(wheel), r.returncode, r.stderr[-300:])
    sampler = ROOT + '/code/model/study/sampler'
    env = dict(os.environ, PYTHONPATH=ROOT + '/site:' + sampler, ARC_MODELS=data, ARC_POLICY=ROOT + '/code/model/study/policy', POLICY_MODEL=data + '/policy_model.pkl', RUST_BACKTRACE='1', POOL_CLAUSES=config.get('pool', 'draws'), ARC_STORE=ROOT + '/store')
    env.update({k: str(v).replace('{data}', data) for k, v in config.get('env', {}).items()})
    if not RERUN:
        env['ARC_RECORD'] = ROOT + '/record'
        os.makedirs(env['ARC_RECORD'], exist_ok=True)
    worker = '%s -u %s/kaggle_worker.py' % (sys.executable, sampler)
    limit = [] if RERUN or not config.get('rss_limit_mib') else ['--rss-limit-mib', str(config['rss_limit_mib'])]
    cmd = [sys.executable, data + '/supervisor.py', '--challenges', chosen if private else path, '--submission', PRIVATE_SUBMISSION if private else SUBMISSION, '--work', ROOT + '/work',
           '--seconds', str(int(seconds - (time.time() - T0))), '--tasks', str(tasks), '--worker-cmd', worker] + limit
    subprocess.run(cmd, env=env, timeout=seconds + 900)


try:
    run()
except BaseException:
    traceback.print_exc()

try:
    with open(one('arc-agi_test_challenges.json')) as f:
        challenges = json.load(f)
    try:
        with open(SUBMISSION) as f:
            s = json.load(f)
    except Exception:
        s = {}
    if set(s) != set(challenges) or any(len(s[k]) != len(challenges[k]['test']) for k in challenges):
        log('the submission does not match the challenges: fallback written')
        with open(SUBMISSION, 'w') as f:
            json.dump(fallback(challenges), f)
        s = challenges
    log('submission tasks', len(s), 'seconds', int(time.time() - T0))
    if not RERUN:
        out = []
        for p in sorted(glob.glob(ROOT + '/work/*.log'))[:60]:
            with open(p, errors='replace') as f:
                out.append(p + '\n' + f.read()[-3000:])
        with open('/kaggle/working/worker_logs.txt', 'w') as f:
            f.write('\n'.join(out))
        print('\n'.join(out)[:6000], flush=True)
        with tarfile.open('/kaggle/working/work.tar.gz', 'w:gz', compresslevel=6) as t:
            t.add(ROOT + '/work', 'work')
        subprocess.run("find %s/record -type f ! -name '*.zst' | xargs -r -P 46 -n 1 gzip -6" % ROOT, shell=True, stdin=subprocess.DEVNULL, timeout=3600)
        size, kept = 0, 0
        with tarfile.open('/kaggle/working/record.tar', 'w') as t:
            for p in sorted(glob.glob(ROOT + '/record/*'), key=os.path.getsize):
                size += os.path.getsize(p)
                if size < RECORD_LIMIT:
                    t.add(p, 'record/' + os.path.basename(p))
                    kept += 1
        log('record bytes', size, 'files kept', kept, 'seconds', int(time.time() - T0))
except BaseException:
    traceback.print_exc()
'''
nb = dict(nbformat=4, nbformat_minor=5, metadata=dict(kernelspec=dict(display_name='Python 3', language='python', name='python3')),
          cells=[dict(cell_type='code', id='run', metadata={}, execution_count=None, outputs=[], source=CELL.strip().splitlines(True))])
pathlib.Path(sys.argv[1]).write_text(json.dumps(nb))
