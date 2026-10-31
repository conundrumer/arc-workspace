"""Score a sampler run's draws with the online scorer as the draws file grows, and give each draw its log weight under
the target P(c)·exp(BETA·score(c))·[c passes the hard rules].

    python score_stage.py RUN [--soft tree|linear] [--beta B] [--shard I/N] [--follow PID]

Runtime: work/lm/.venv/bin/python (the scorer's).

The score is the tree classifier's log-odds (--soft tree, the default, BETA 0.5) or the linear v11 soft score (--soft
linear, BETA 2). RUN/scores-<tree model stem>.<I>of<N>.jsonl.zst (scores-tree for tree_v11, scores for linear) gets one row per draw (gold rows too) of the points whose key hashes to shard I: task, case,
point, draw, gold, passes, soft_score, hard_keys, errors, and logw = logp - logq_full + BETA·soft_score for a passing draw
with logq_full, None otherwise. Gold rows get logw None and keep the rest. A restart skips the points it has
finished, in its own file or in another shard's. With --follow, it waits for new draws while process PID runs, and ends once PID has ended and every draw
is scored."""
import argparse
import glob
import json
import os
import sys

os.environ.setdefault('OMP_NUM_THREADS', '1')  # the tree scores one row at a time, which a thread pool only slows
import time
_fstore = os.path.join(sys.argv[1], 'fstore.txt') if len(sys.argv) > 1 else ''
for _ in range(600):  # the sampler writes fstore.txt as it starts; a scorer that follows it waits for the file
    if not _fstore or os.path.exists(_fstore):
        break
    time.sleep(0.5)
if _fstore:  # the scorer reads each point from the feature store the run drew from
    os.environ['FSTORE_POINTS'] = open(_fstore).read().strip()
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sampler_paths as P  # noqa: E402
sys.path[:0] = [P.STUDY, P.CODE]
from judge3.framed_jsonl import JsonlWriter, iter_json  # noqa: E402
import online_score  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument('run')
ap.add_argument('--shard', default='0/1')
ap.add_argument('--soft', choices=('tree', 'linear'), default='tree')
ap.add_argument('--beta', type=float)
ap.add_argument('--follow', type=int, default=0)
a = ap.parse_args()
shard, nshard = map(int, a.shard.split('/'))
draws_path = os.path.join(a.run, 'draws.jsonl.zst')
beta = a.beta if a.beta is not None else 0.5 if a.soft == 'tree' else 2.0
tag = 'scores' if a.soft == 'linear' else 'scores-tree' if online_score.SOFT_TREE.stem == 'tree_v11' else 'scores-' + online_score.SOFT_TREE.stem
out_path = os.path.join(a.run, '%s.%dof%d.jsonl.zst' % (tag, shard, nshard))  # one file name per soft model, so models never mix
soft = dict(soft=online_score.SOFT_TREE) if a.soft == 'tree' else {}


def pkey(r):
    return '%s|%s|%s' % (r['task'], r['case'], json.dumps(r['point']))


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


while a.follow and alive(a.follow) and not os.path.exists(draws_path + '.idx.jsonl'):  # the run has written no frame yet
    time.sleep(5)
done = {}  # point key -> draws scored, in the files of any shard count, so a restart may change N
for f in glob.glob(os.path.join(a.run, '%s.*of*.jsonl.zst' % tag)):
    for r in iter_json(f):
        done[pkey(r)] = done.get(pkey(r), 0) + 1
names, scorers, seen = {}, {}, {}
line, n, cut, t0 = 1, 0, 0, time.time()
with JsonlWriter(out_path) as w:
    while True:
        got = 0
        for d in iter_json(draws_path, start_line=line):
            line += 1
            got += 1
            k = pkey(d)
            if zlib.crc32(k.encode()) % nshard != shard:
                continue
            seen[k] = seen.get(k, 0) + 1
            if seen[k] <= done.get(k, 0):
                continue
            if k not in names:
                names = json.load(open(os.path.join(a.run, 'names.json')))
            if k not in scorers:
                scorers.clear()  # a point's draws are contiguous in the draws file
                scorers[k] = online_score.PointScorer(d['task'], d['case'], d['point'], **soft)
            s = scorers[k].score(d, names.get(k) or {})
            ok = s.get('passes') and s.get('soft_score') is not None
            logw = (d['logp'] - d['logq_full'] + beta * s['soft_score']
                    if ok and not d.get('gold') and d.get('logp') is not None and d.get('logq_full') is not None else None)
            w.write(dict(task=d['task'], case=d['case'], point=d['point'], draw=d.get('draw'), gold=bool(d.get('gold')),
                         passes=s.get('passes'), soft_score=s.get('soft_score'), hard_keys=s.get('hard_keys'),
                         errors=s.get('errors'), logw=logw))
            n += 1
            cut += s.get('passes') is None or (s.get('passes') and s.get('soft_score') is None)
            if n % 500 == 0:
                w.flush()
                print('%s scored %d draws, %.1f per s, %d cut by the bound' % (time.strftime('%H:%M'), n, n / (time.time() - t0), cut), flush=True)
        w.flush()
        if got == 0 and not (a.follow and alive(a.follow)):
            break
        if got == 0:
            time.sleep(15)
print('%s done: %d draws scored in %.0f s, %d cut by the bound' % (time.strftime('%H:%M'), n, time.time() - t0, cut), flush=True)
