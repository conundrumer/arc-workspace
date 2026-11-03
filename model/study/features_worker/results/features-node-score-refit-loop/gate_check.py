"""Gate 1 of the node score loop: the checks on a round's model before any pod starts.

  PY gate_check.py MODEL_PATH OUT.json

MODEL_PATH is OUTDIR/node-score-rN.state.pkl from fit_round.py. Exit 0 when every check passes, 2 when one fails; the reasons are in OUT.json.
Checks:
  ident_positives     seeded positives with an Ident column in the fit rows, above 0. A sample of 10 is checked: the node is tagged
                      seeded by the search, and its clause equals a form of the task's gold text with labels renamed.
  positive_tasks      tasks with a positive in the fit rows, more than 500.
  held_read           the held read (features_node_read_held.py) on H, 3,600 s, hash labels: M1 and the median rank of Ident tables at or
                      better than the shipped score's, with the node rank model's figures beside them. One held read per round.
"""
import glob, gzip, hashlib, json, os, pickle, random, re, subprocess, sys, time

HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-score-refit-loop/'  # the data folder
PY = '/Users/davidlu/code/arc-workspace/work/lm/data-study/ast/run/runtime-kaggle-py313/venv/bin/python'
HEAVY = '/Users/davidlu/code/arc-workspace/scripts/run_heavy.py'
VIEW = '/Users/davidlu/code/arc-workspace/work/lm/data-study/gold/gold-v3-combined-cut/view-final/'
RANK = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-rank-model-train-read-hour13-heldout37/read-out/M-T.results.json'
S120 = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-corpus-pool-seed1-120s-ship7/level1_search/'
model, out = os.path.abspath(sys.argv[1]), sys.argv[2]
name = re.search(r'node-score-(r\d+)\.state\.pkl$', model)[1]
arm = name.upper()
os.environ['S120_N'] = '5000'
env = dict(os.environ, S120_N='5000', OMP_NUM_THREADS='1')
rec = dict(model=model, arm=arm, time=time.strftime('%Y-%m-%dT%H:%M:%S%z'), checks={})
sys.path.insert(0, HERE)
import numpy as np
import features_node_data as DT


def done(ok):
    rec['pass'] = ok
    with open(out + '.tmp', 'w') as f:
        json.dump(rec, f, indent=1)
    os.replace(out + '.tmp', out)
    print(json.dumps(rec['checks'])[:2000])
    sys.exit(0 if ok else 2)


def norm(c):
    return re.sub(r'&[fr]\d+', '&', re.sub(r'\s+', ' ', c)).strip()


# fit rows
D = DT.load(['n600', 's120'], 'T')
y, X, names = D['y'], D['X'], [str(n) for n in D['names']]
iid = names.index('tb_t_Ident')
pos = y == 1
idp = pos & (X[:, iid] > 0)
ptask = {D['pools'][g][1] for g in np.unique(D['pool'][pos])}
rng = random.Random(0)
samp = rng.sample([i for i in np.flatnonzero(idp) if D['pools'][D['pool'][i]][0] == 's120'], min(10, int(idp.sum())))
checked = []
for i in samp:
    src, t, _ = D['pools'][D['pool'][i]]
    tok = str(int(D['node'][i]))
    import zstandard
    node = None
    with open(S120 + t + '.nodes.jsonl.zst', 'rb') as f:
        for l in zstandard.ZstdDecompressor().stream_reader(f).read().decode().splitlines():
            r = json.loads(l)
            if r['token'] == tok:
                node = r
                break
    g = VIEW + t + '/pairs.jsonl.gz'
    gold = json.loads(gzip.open(g, 'rt').readline())['gold_sexp'] if os.path.exists(g) else ''
    gl = {norm(x) for x in re.findall(r'\((?:RULE|INIT|DET)[^\n]*', gold)}
    checked.append(dict(task=t, token=tok, seeded=bool(node and (node.get('tags') or {}).get('seeded')),
                        ident=bool(node and 'Ident' in node['table_types']), clause_in_gold=bool(node and norm(node['clause']) in gl)))
rec['checks']['ident_positives'] = dict(count=int(idp.sum()), positives=int(pos.sum()), sample=checked,
                                        ok=bool(idp.sum() > 0 and all(c['seeded'] and c['ident'] for c in checked)))
rec['checks']['positive_tasks'] = dict(count=len(ptask), ok=len(ptask) > 500)

# held read: the base once, then this round
for a in ('hand', arm):
    if os.path.exists(HERE + 'read-out/%s.results.json' % a):
        continue
    procs = [subprocess.Popen([HEAVY, '--cpus', '1', '--need', 'soon', PY, '-I', HERE + 'features_node_read_held.py', a, 'run', '3000', '%d/4' % i], cwd=HERE, env=env) for i in range(4)]
    if any(p.wait() for p in procs):
        rec['checks']['held_read'] = dict(ok=False, reason='held read of %s failed' % a)
        done(False)
    subprocess.run([PY, '-I', HERE + 'features_node_read_held.py', a, 'finish'], cwd=HERE, env=env, stdout=open(HERE + 'read-out/%s.finish.txt' % a, 'w'), stderr=subprocess.STDOUT)


def figs(p):
    d = json.load(open(p))
    return dict(M1=float(d['H3600|hash|all']['M1']), ident_median_rank=float(d['cut:H3600|all']['cells']['ident']['median_rank']),
                M1_B=float(d['B|hash|all']['M1']), ident_median_rank_B=float(d['cut:B|all']['cells']['ident']['median_rank']))


me, base, rank = figs(HERE + 'read-out/%s.results.json' % arm), figs(HERE + 'read-out/hand.results.json'), figs(RANK)
rec['checks']['held_read'] = dict(model=me, shipped=base, node_rank_model=rank,
                                  ok=me['M1'] >= base['M1'] and me['ident_median_rank'] <= base['ident_median_rank'])
fails = [k for k, v in rec['checks'].items() if not v['ok']]
rec['reason'] = 'fails: ' + ', '.join(fails) if fails else 'all pass'
done(not fails)
