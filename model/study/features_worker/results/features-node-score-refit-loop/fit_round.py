"""One round of the node score refit: rows, fit, model file. A rerun resumes each step and skips a finished one.

  PY fit_round.py ROUND OUTDIR [--positives FILE]

ROUND is a small int (1, 2, ...); the model is named rROUND. Steps:
  rows   S120 rows of every eligible seeded corpus task (outside the 37 held, the ramp, the 99 and the drifted tasks), 4 processes.
  fit    features_node_fit.py on N600 and S120 rows, feature set T, 150 rounds, softmax, fold all. Prints a line per round.
  out    OUTDIR/node-score-rROUND.state.pkl, .json (card: feature_names, t, sha256, rows, positives), then .sha256 last.
         Each is written to a temporary name and renamed, so the .sha256 file appearing means the round is done.
--positives FILE: rows the driver adds, one JSON line each. Round 1 reads none, and the command refuses a line it can't use yet.
Exit 0 on success. PY is the engine venv (sklearn 1.6.1): work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python.
"""
import hashlib, json, os, pickle, subprocess, sys, time

HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/'  # the data folder
PY = '/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python'
HEAVY = '/Users/davidlu/code/arc-workspace/scripts/run_heavy.py'
T0 = time.time()
args = sys.argv[1:]
rnd, out = int(args[0]), os.path.abspath(args[1]) + '/'
pos = args[args.index('--positives') + 1] if '--positives' in args else None
name = 'r%d' % rnd
env = dict(os.environ, S120_N='5000', OMP_NUM_THREADS='1')


def log(m):
    print('%7.1fs %s' % (time.time() - T0, m), flush=True)


def run(cmd):
    log('run: ' + ' '.join(cmd)[-160:])
    r = subprocess.run(cmd, cwd=HERE, env=env)
    if r.returncode:
        sys.exit('step failed, rc %d' % r.returncode)


if pos and os.path.exists(pos) and any(l.strip() for l in open(pos)):
    sys.exit('refused: %s has rows; this fit takes added positives from round 2 on, once the live record format is fixed' % pos)
os.makedirs(out, exist_ok=True)
final = out + 'node-score-%s' % name
if os.path.exists(final + '.sha256'):
    log('done before: ' + final + '.sha256')
    sys.exit(0)

# rows
procs = [subprocess.Popen([HEAVY, '--cpus', '1', '--need', 'soon', 'bash', HERE + 'rt600.sh', HERE + 'features_node_matrix.py', 's120', '3000', '5000', '%d/4' % i],
                          cwd=HERE, env=env) for i in range(4)]
if any(p.wait() for p in procs):
    sys.exit('rows failed')
log('rows: %d S120 tasks' % len(os.listdir(HERE + 's120-rows')))

# fit
st = HERE + 'fit-out/%s-fall.state.pkl' % name
done = pickle.load(open(st, 'rb'))[1] if os.path.exists(st) else 0
if done < 150:
    run([PY, '-I', HERE + 'features_node_fit.py', '--features', 'T', '--sources', 'n600,s120', '--a', '0', '--fold', 'all', '--rounds', '150',
         '--seconds', '100000', '--name', name, '--objective', 'softmax', '--label', 'true'])
models, done = pickle.load(open(st, 'rb'))
assert done == 150, done

# out
sys.path.insert(0, HERE)
import features_node_feats as FE
sha = hashlib.sha256(open(st, 'rb').read()).hexdigest()
fitlog = [l for l in open(HERE + 'fit-out/%s.log' % name)] if os.path.exists(HERE + 'fit-out/%s.log' % name) else []
card = dict(name=name, round=rnd, features='T', feature_names=list(FE.names_T()), n_features=len(FE.names_T()), t=.5, rounds=150,
            sources='n600,s120', s120_tasks=len(os.listdir(HERE + 's120-rows')), objective='softmax', sha256=sha,
            format='pickle of (models, rounds_done); models: HistGradientBoostingRegressor per round, sklearn 1.6.1; score = t * sum(m.predict(X))')
os.makedirs(HERE + 'final-models', exist_ok=True)
json.dump(card, open(HERE + 'final-models/%s.json' % name, 'w'), indent=1)
for path, data, mode in ((final + '.state.pkl', open(st, 'rb').read(), 'wb'), (final + '.json', json.dumps(card, indent=1), 'w'), (final + '.sha256', sha + '  node-score-%s.state.pkl\n' % name, 'w')):
    with open(path + '.tmp', mode) as f:
        f.write(data)
    os.replace(path + '.tmp', path)
log('wrote ' + final + '.sha256')
