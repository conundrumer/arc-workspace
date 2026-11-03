"""Checks of item 3 on R120 records. Prints counts. Stops at SECONDS.

  features_node_checks.py MODE SECONDS [NODES]
MODE: cells (Position, Box, Example meaning on 3 tasks), empty (share of empty values on 1,000 nodes), order (order check on 2,000 nodes),
      names (banned words), cost (ms per node on 2,000 nodes), row (features from rebuilt rows against record rows: see features_node_rebuild.py --row-check)
"""
import collections, math, os, random, re, sys, time
HERE = '/Users/davidlu/code/arc-workspace/work/lm/data-study/features-worker/results/features-node-rank-model-train-read-hour13-heldout37/'  # the data folder
sys.path.insert(0, HERE)
import numpy as np
import features_node_io as IO, features_node_feats as FE, features_node_shape as SH

T0 = time.time()
MODE, LIMIT = sys.argv[1], float(sys.argv[2])
NNODES = int(sys.argv[3]) if len(sys.argv) > 3 else {'empty': 1000, 'order': 2000, 'cost': 2000}.get(MODE, 1000)
BANNED = ('gold', 'gold_atom', 'point', 'd_out', 'task', 'case', 'author', 'tags', 'is_gold', 'gold_sexp', 'output_test', 'test_output', 'age', 'uses', 'token', 'draw', 'scope', 'score', 'link_')


def r120_tasks(step, off=0):
    ex = IO.excluded()
    fs = sorted(f[:8] for d in IO.R120 for f in os.listdir(d) if f.endswith('.nodes.jsonl.zst'))
    fs = [t for t in fs if t not in ex and os.path.exists(IO.TASKDIR + t + '.json')]
    return fs[off::step]


def sample(n, step=23, per_task=None):
    """About n nodes spread over tasks: (task, ctx, record) with records taken at an even stride."""
    out = []
    ts = r120_tasks(step)
    per = per_task or max(1, n // max(len(ts), 1)) + 1
    for t in ts:
        if time.time() - T0 > LIMIT or len(out) >= n:
            break
        path = next(d + t + '.nodes.jsonl.zst' for d in IO.R120 if os.path.exists(d + t + '.nodes.jsonl.zst'))
        N = [r for r in IO.read_nodes(path) if r.get('x_rows')]
        if not N:
            continue
        ctx = FE.TaskCtx(IO.load_task(t))
        k = max(1, len(N) // per)
        for r in N[::k][:per]:
            out.append((t, ctx, r))
    return out[:n]


def feat(ctx, r):
    return FE.node_features(r['table_types'], r['x_rows'], r['clause'], 'DET', 1, 0, ctx)


def cells():
    c = collections.Counter()
    for t in r120_tasks(60)[:6]:
        task = IO.load_task(t)
        ntr = len(task['train'])
        ins = [p['input'] for p in task['train']] + [x['input'] for x in task['test']]
        path = IO.R120[0] + t + '.nodes.jsonl.zst'
        for r in IO.read_nodes(path):
            ty, cl = r['table_types'], r['clause']
            if not r['x_rows']:
                continue
            m = re.fullmatch(r'\((?:DET|RULE) &f\d+ \((input|ex_input) (?:\(:E \*E\) )?\(:P \*P\) \(:Col \*Col\)\)\)', cl)
            if m and ty in (['Position', 'Color'], ['Example', 'Position', 'Color']) and ('Example' in ty or all(e[0][0] != 0 for e in r['x_rows'])):
                T = FE.RD.read_table(ty, r['x_rows'], ntr, len(task['test']))
                pi, ci = [i for i, x in enumerate(T.cols) if x[0] == 'Position'][0], [i for i, x in enumerate(T.cols) if x[0] == 'Color'][0]
                for w in T.worlds:
                    for e, a in w.items():
                        g = np.array(ins[e])
                        s = T.cols[pi][1]
                        rr, cc = a[:, s], a[:, s + 2]
                        ok = (rr >= 0) & (rr < g.shape[0]) & (cc >= 0) & (cc < g.shape[1])
                        c['position cells checked'] += len(a)
                        c['cell in grid with input color equal to Color'] += int((g[rr[ok], cc[ok]] == a[ok, T.cols[ci][1]]).sum())
                        c['cell is (row, H-1-row, col, W-1-col) of the example grid'] += int(((a[:, s + 1] == g.shape[0] - 1 - rr) & (a[:, s + 3] == g.shape[1] - 1 - cc)).sum())
                        c['rows of test examples'] += len(a) if e >= ntr else 0
                if 'Example' in ty:
                    cs = collections.defaultdict(set)
                    for w in T.worlds:
                        for e, a in w.items():
                            cs[e] |= set(int(v) for v in a[:, T.cols[ci][1]])
                    for e, v in cs.items():
                        if e >= ntr:
                            c['test examples (Example value - n_train) checked'] += 1
                            c['  colors inside that test input'] += v <= {int(x) for row in ins[e] for x in row}
                        else:
                            c['train examples checked'] += 1
                            c['  colors inside that train input'] += v <= {int(x) for row in ins[e] for x in row}
            if 'Box' in ty and r['x_rows'] and any(x is not None for e in r['x_rows'] for xs in e[5][:1] for x in xs):
                c['box nodes with extents'] += 1
                T = FE.RD.read_table(ty, r['x_rows'], ntr, len(task['test']))
                w = T.worlds[0] if T.worlds else {}
                bi = [i for i, x in enumerate(T.cols) if x[0] == 'Box'][0]
                for e, a in w.items():
                    bd = T.boxdims[0].get(e)
                    if bd is None or np.isnan(bd[:, 0, 0]).all():
                        continue
                    s = T.cols[bi][1]
                    H, W = bd[:, 0, 0], bd[:, 0, 1]
                    c['box rows with extent'] += len(a)
                    c['box extent = grid of the example (input or output size)'] += int(((H == len(ins[e])) & (W == len(ins[e][0]))).sum()) if e < ntr else 0
                    c['box top+bottom margins within extent'] += int((a[:, s] + a[:, s + 1] <= H).sum())
    print(dict(c))


def empty():
    S = sample(NNODES)
    n = collections.Counter()
    for t, ctx, r in S:
        d = feat(ctx, r)
        for k, v in d.items():
            n[k] += v != v
    N = len(S)
    sh = sorted(((v / N, k) for k, v in n.items()), reverse=True)
    print('nodes', N, 'features', len(FE.NAMES), 'always empty', sum(v == N for v in n.values()), '>90% empty', sum(v / N > .9 for v in n.values()))
    print('share of empty values by feature (group, name, share), all:')
    for g in ('Table', 'Pairs', 'Output cells', 'Test input', 'Depth', 'Form shape'):
        xs = [(round(v / N, 3), k) for k, v in n.items() if FE.group_of(k) == g]
        print(g, len(xs), 'features; mean share', round(sum(a for a, _ in xs) / len(xs), 3), '; always empty:', [k for a, k in xs if a == 1.0][:12])
    print('per feature (not shape), share empty, highest first:', ' '.join('%s=%.2f' % (k, v) for v, k in sh if FE.group_of(k) != 'Form shape' and v > 0)[:2500])


def shuffle_tree(x, rng):
    if not isinstance(x, list) or not x:
        return x
    if isinstance(x[0], str):
        keep = 2 if x[0] in ('DET', 'RULE', 'INIT') else 1
        if x[0] in ('DET', 'RULE', 'INIT') and len(x) > 2 and isinstance(x[2], str):
            keep = 3
        head, rest = x[:keep], [shuffle_tree(y, rng) for y in x[keep:]]
        if x[0].startswith(':'):
            return x
        rng.shuffle(rest)
        return head + rest
    y = [shuffle_tree(z, rng) for z in x]
    rng.shuffle(y)
    return y


def ser(x):
    return '(' + ' '.join(ser(y) if isinstance(y, list) else y for y in x) + ')'


def rename(text, rng):
    labs = sorted({m[0] for m in re.findall(r'[*^]?[A-Za-z]\w*', text) if False})
    toks = re.findall(r'[*^]?[A-Za-z_]\w*', text)
    names = sorted({t.lstrip('*^') for t in toks if not t.startswith(':')})
    # labels are the second item of port bindings; rename only those
    labels = sorted({m for m in re.findall(r'\(:\w+ ([*^]?\w+)\)', text)}, key=lambda s: s)
    labels = sorted({l.lstrip('*^') for l in labels})
    perm = labels[:]
    rng.shuffle(perm)
    mp = {a: 'L%dx' % i for i, a in enumerate(perm)}
    def sub(m):
        l = m[2]
        return '(%s %s%s)' % (m[1], m[3] if False else '', mp.get(l.lstrip('*^'), l)) if False else m[0]
    out = re.sub(r'\((:\w+) ([*^]?)(\w+)\)', lambda m: '(%s %s%s)' % (m[1], m[2], mp.get(m[3], m[3])), text)
    fs = sorted({int(x) for x in re.findall(r'&f(\d+)', out)})
    fp = fs[:]
    rng.shuffle(fp)
    fm = {a: 1000 + b for a, b in zip(fs, fp)}
    out = re.sub(r'&f(\d+)', lambda m: '&f%d' % fm[int(m[1])], out)
    return out


def permute_record(r, rng):
    ty = list(r['table_types'])
    w = [FE.RD.WIDE.get(x, 1) for x in ty]
    off = [sum(w[:i]) for i in range(len(w))]
    wide = [i for i, x in enumerate(ty) if x in FE.RD.WIDE]
    # same-type column swaps
    order = list(range(len(ty)))
    bytype = collections.defaultdict(list)
    for i, x in enumerate(ty):
        bytype[x].append(i)
    new = order[:]
    for x, ids in bytype.items():
        p = ids[:]
        rng.shuffle(p)
        for a, b in zip(ids, p):
            new[a] = b
    # new column k is old column new[k]
    ty2 = [ty[new[k]] for k in range(len(ty))]
    cellidx = [c for k in range(len(ty)) for c in range(off[new[k]], off[new[k]] + w[new[k]])]
    wideslot = {i: s for s, i in enumerate(wide)}
    xr = []
    for e in r['x_rows']:
        rows = [[row[c] for c in cellidx] for row in e[1]]
        ext = e[5]
        wide2 = [new[k] for k in range(len(ty)) if ty[new[k]] in FE.RD.WIDE]
        ext2 = [[xs[wideslot[i]] for i in wide2] if xs else xs for xs in ext]
        perm = list(range(len(rows)))
        rng.shuffle(perm)
        xr.append([e[0], [rows[p] for p in perm], e[2], e[3], e[4], [ext2[p] for p in perm]])
    rng.shuffle(xr)
    cl = rename(ser(shuffle_tree(SH.parse(r['clause']), rng)), rng)
    return ty2, xr, cl


def order():
    S = sample(NNODES)
    rng = random.Random(1)
    diff = collections.Counter(); bad = 0; maxd = 0.0
    for t, ctx, r in S:
        d0 = feat(ctx, r)
        ty2, xr2, cl2 = permute_record(r, rng)
        d1 = FE.node_features(ty2, xr2, cl2, 'DET', 1, 0, ctx)
        nb = 0
        for k in d0:
            a, b = d0[k], d1[k]
            if (a != a) != (b != b) or (a == a and abs(a - b) > 1e-9 * max(1, abs(a))):
                diff[k] += 1; nb += 1
        bad += nb > 0
    print('order check: nodes', len(S), 'nodes with a difference', bad, 'features that differ', dict(diff.most_common(12)))


def names():
    bad = [n for n in FE.NAMES if any(w in n for w in BANNED)]
    print('feature names', len(FE.NAMES), 'with a banned word', bad)
    print('groups', dict(collections.Counter(FE.group_of(n) for n in FE.NAMES)))


def cost():
    S = sample(NNODES)
    ms = []
    for t, ctx, r in S:
        t1 = time.perf_counter(); feat(ctx, r); ms.append((time.perf_counter() - t1) * 1000)
    ms.sort()
    print('cost: nodes', len(ms), 'mean ms %.2f q50 %.2f q90 %.2f q99 %.2f max %.1f' % (sum(ms) / len(ms), ms[len(ms) // 2], ms[int(.9 * len(ms))], ms[int(.99 * len(ms))], ms[-1]), 'budget mean 8 q99 60 (features and model together)', 'seconds', round(time.time() - T0, 1))


{'cells': cells, 'empty': empty, 'order': order, 'names': names, 'cost': cost}[MODE]()
