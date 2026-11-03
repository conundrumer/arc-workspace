"""Cost probe for the tower read design: on one held task, the DFS walk, then Sampler.clause draws at two walk steps with the
prefix as scope, under the models-kr bundle. Prints seconds a draw and the read classes of the draws. Not part of the read.

  probe_cost.py TASK STEP[,STEP] DRAWS
"""
import collections
import random
import sys
import time

sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-ident-block-read-heldout37-ramp22')
import ib_lib as L  # noqa: E402

L.KIT = L.STUDY + '/sampler/sampler-worker/kits/sampler-pool-keyident-value-199853802'
L.SAMPLER_DIR = L.KIT + '/model/study/sampler'
sys.dont_write_bytecode = True
sys.path[:0] = [L.SAMPLER_DIR, L.ENGINE]
import live  # noqa: E402
import live_try  # noqa: E402
import superdag as D  # noqa: E402
L.live, L.live_try, L.D = live, live_try, D


sys.path.insert(0, '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-dag-order-census-heldout37')
from features_dag_order import ProgramDag, short  # noqa: E402

BANDS = ('BT1', 'BT2', 'BT3+')


def mode_of(reads_f, chain):
    m = len(chain)
    if m and chain[-1] in reads_f:
        return 'EXTEND', 0
    for j in range(m - 2, -1, -1):
        if chain[j] in reads_f:
            d = m - 1 - j
            return BANDS[min(d, 3) - 1], d
    return 'JUMP', None


def walk(forms, seed):
    """Round-0 chain walk of walk.md: uniform over the (mode, kind) cells that the ready set holds, then uniform in the cell."""
    dag = ProgramDag(forms)
    keys = list(dag.lines)
    rng = random.Random('%d|%s' % (seed, short(''.join(sorted(dag.content[k] for k in keys)), 16)))
    S, chain, out = set(), [], []
    while len(S) < len(keys):
        ready = sorted((k for k in keys if k not in S and dag.parent_ids[k] <= S), key=dag.tie)
        cells = collections.defaultdict(list)
        for k in ready:
            cells[(mode_of(dag.parent_ids[k], chain)[0], dag.kinds[k])].append(k)
        cell = sorted(cells)[rng.randrange(len(cells))]
        f = cells[cell][rng.randrange(len(cells[cell]))]
        mode, d = mode_of(dag.parent_ids[f], chain)
        if mode == 'EXTEND':
            chain.append(f)
        elif mode == 'JUMP':
            chain = [f]
        else:
            chain = chain[:len(chain) - d] + [f]
        S.add(f)
        out.append((f, mode, len(chain)))
    return dag, out


def main():
    task, steps, ndraw = sys.argv[1], [int(x) for x in sys.argv[2].split(',')], int(sys.argv[3])
    t0 = time.time()
    forms = L.forms_of(L.held_gold()[task])
    dag, w = walk(forms, 0)
    head_i = {L.parse(f)['head']: i for i, f in enumerate(forms)}
    order = [head_i[k] for k, _, _ in w]
    print('%s: %d forms, modes %s' % (task, len(forms), collections.Counter(x[1] for x in w)), flush=True)
    sampler = live.Sampler(L.KIT + '/models-kr')
    sess, d = L.session_of(L.KIT + '/data/tasks/%s.json' % task)
    print('setup %.1fs' % (time.time() - t0), flush=True)
    for t in steps:
        g = order[t]
        kind = L.parse(forms[g])['kind']
        texts = [forms[j] for j in order[:t]]
        heads = {L.parse(forms[j])['head'] for j in order[:t]}
        c0, w0 = time.process_time(), time.time()
        got = collections.Counter()
        none = 0
        for i in range(ndraw):
            c = sampler.clause(sess, L.draw_seed(task, g, i), time.monotonic() + 20, d, texts, kind)
            if c is None:
                none += 1
                continue
            got[len(set(L.NAME.findall(c.text)) & heads)] += 1
        cpu = time.process_time() - c0
        print('step %d form %d %s mode %s prefix %d, gold reads %d | %d draws, %d none, %.2f cpu s a draw, %.1f s wall | draws by count of forms read %s' % (
            t, g, kind, w[t][1], t, len(dag.parent_ids[w[t][0]]), ndraw, none, cpu / ndraw, time.time() - w0, sorted(got.items())), flush=True)


if __name__ == '__main__':
    main()
