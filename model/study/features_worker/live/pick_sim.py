"""Simulated pick rules on recorded Kaggle runs: the nodes arrive in their recorded order, a rule picks scopes from the nodes alive at each recorded draw, and the score is how often gold nodes are picked. The pool does not react to the simulated picks, so this ranks rules for screening and predicts no cover count. The rule has temperature T, use penalty U, and R of k picks kept for oldest least used.

  pick_sim.py TAG
"""
import collections, glob, json, math, os, random, re, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
REC = '/Users/davidlu/code/arc-workspace/work/lm/data-study/sampler/runs/kaggle-v5/record'
tag = sys.argv[1]; K = 6; PER = 4  # picks per scope, draws per scope
BANDS = ('1', '2-3', '4-6', '7+')
TR = re.compile(r'"draw": ?(\d+)')
TK = re.compile(r'"token": ?"(\d+)"')
tasks = []
for f in sorted(glob.glob(f'{HERE}/rank/{tag}/*.json')):
    v = json.load(open(f)); t = v['task']
    lab = json.load(open(f'{HERE}/labels/{t}.json'))
    r = glob.glob(f'{REC}/{t}*.zst')[0]
    birth = []
    for raw in subprocess.Popen(['zstd', '-dcq', r], stdout=subprocess.PIPE).stdout:
        head, tail = raw[:60].decode('utf8', 'ignore'), raw[-160:].decode('utf8', 'ignore')
        m, q = TK.search(head), TR.search(tail)
        if m and q:
            birth.append((int(q[1]), int(m[1])))
    gold = {int(h['token']) for h in lab['hits']}
    tasks.append((t, sorted(birth), {int(k): x for k, x in v['score'].items()}, {int(k): b for k, b in v['band'].items()}, gold))
print('tasks', len(tasks), 'gold', sum(len(x[4]) for x in tasks), flush=True)


def run(task, T, U, R, seed):
    t, birth, score, band, gold = task
    rng = random.Random(f'{t} {seed}')
    uses = collections.Counter(); alive = []; i = 0
    last = birth[-1][0] if birth else 0
    slots = collections.Counter(); base = collections.Counter()
    for draw in range(PER, last + 1, PER):
        while i < len(birth) and birth[i][0] < draw:
            if birth[i][1] in score:
                alive.append(birth[i][1])
            i += 1
        if not alive:
            continue
        key = {n: (score[n] - U * uses[n]) / T - math.log(-math.log(rng.random() or 1e-12)) for n in alive}
        best = sorted(alive, key=lambda n: -key[n])[:K - R]
        rest = sorted((n for n in alive if n not in set(best)), key=lambda n: (uses[n], n))[:R]
        g = {}
        for n in alive:
            if n in gold:
                g[band[n]] = g.get(band[n], 0) + 1
        for n in best + rest:
            uses[n] += 1
            if n in gold:
                slots[band[n]] += 1
        for b, c in g.items():
            base[b] += K * c / len(alive)
    return slots, base


rules = [(1, 1, 1), (1, .3, 1), (1, .1, 1), (1, .03, 1), (1, 1, 0), (1, .3, 0), (.5, 1, 1), (.5, .3, 1), (2, .3, 1), (1e9, 0, 1)]
print('T U R: enrichment over uniform by band', flush=True)
for T, U, R in rules:
    s, b = collections.Counter(), collections.Counter()
    for tk in tasks:
        a, c = run(tk, T, U, R, 0)
        s.update(a); b.update(c)
    print(T, U, R, ' '.join(f'{x}:{s[x] / b[x]:.2f}' if b[x] else f'{x}:-' for x in BANDS), flush=True)
