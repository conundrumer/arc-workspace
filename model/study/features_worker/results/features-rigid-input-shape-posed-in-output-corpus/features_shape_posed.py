"""Whether an input shape reappears in a train output at another D4 pose, per task.

Reads train inputs, train outputs and test inputs from data/tasks. Test outputs are dropped at load. No pool, no engine, no gold in the statistic; labels.tsv only picks the tasks and the control donors.

Terms:
  shape: a set of colored cells, moved to its corner. A class is a shape up to D4 and translation. A pose is one image of the class.
  bg: the most common color of the grid, per grid.
  Shape kinds:
    s8  single-color 8-connected component of non-bg cells
    s4  single-color 4-connected component
    m8  8-connected component of non-bg cells, any colors
    cs  all cells of one non-bg color in a grid, where that color has at least 2 s8 components
    win tight rectangular window, 3 to 5 on a side, at least 4 non-bg cells, with bg cells kept as bg
  col: same keeps the colors of the shape, free keeps its non-bg mask.
  match: comp is a shape of the same kind in the output. embed is the cells of the shape anywhere in the output (s8 and m8, at least 4 cells, the 60 largest classes).
  chg: 1 asks that every cell of the output copy differs from the input at that cell. In a pair with grids of different size every cell counts as changed.
  scope: pair reads the copy against the input of its own pair. across reads it against inputs of other train pairs. task reads it against all train and test inputs.
  pose: new, a copy at a pose that the scope's inputs don't show. other, the scope's inputs and copies hold at least 2 poses. several, at least 3. The same-pose reading is a copy at a pose that the scope's inputs show.

Each form gives, per task: hit, same, share of train pairs with a hit, largest hit shape, classes hit, classes copied.

  features_shape_posed.py --shard i/n [--split train|held] [--forms file] [--limit k] [--draws k] OUT
"""
import argparse
import collections
import hashlib
import json
import os
import random
import time

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view as swv

R = '/Users/davidlu/code/arc-workspace/'
RUN = os.path.dirname(os.path.abspath(__file__)) + '/'
MAXS = 150
EMB_MIN = 4
EMB_CAP = 60
DIMS = [(3, 3), (3, 4), (3, 5), (4, 4), (4, 5), (5, 5)]
WIN_CAP = 400
D4 = [(lambda r, c: (r, c)), (lambda r, c: (r, -c)), (lambda r, c: (-r, c)), (lambda r, c: (-r, -c)),
      (lambda r, c: (c, r)), (lambda r, c: (c, -r)), (lambda r, c: (-c, r)), (lambda r, c: (-c, -r))]


def F(kind='s8', col='same', match='comp', chg=0, scope='pair', pose='new', size=4, images=4):
    return dict(kind=kind, col=col, match=match, chg=chg, scope=scope, pose=pose, size=size, images=images)


FORMS = {
    'base': F(),
    's4': F(kind='s4'), 'm8': F(kind='m8'), 'cs': F(kind='cs'), 'win': F(kind='win'),
    'free': F(col='free'),
    'embed': F(match='embed'),
    'chg': F(chg=1),
    'across': F(scope='across'), 'task': F(scope='task'),
    'other': F(pose='other'), 'several': F(pose='several'),
    'size3': F(size=3), 'size6': F(size=6), 'size8': F(size=8),
    'img2': F(images=2), 'img8': F(images=8),
    'm8-free': F(kind='m8', col='free'),
    'm8-chg': F(kind='m8', chg=1),
    'free-chg': F(col='free', chg=1),
    'other-chg': F(pose='other', chg=1),
    'free-other-chg': F(col='free', pose='other', chg=1),
    'm8-other-chg': F(kind='m8', pose='other', chg=1),
    'several-free': F(pose='several', col='free'),
    'task-several': F(scope='task', pose='several'),
    'across-free-chg': F(scope='across', col='free', chg=1),
    'embed-chg': F(match='embed', chg=1),
    'win-chg': F(kind='win', chg=1),
    'task-free-chg': F(scope='task', col='free', chg=1),
}

# The form with the highest AUC in the sweep of every combination, chosen on non-held tasks after the fixed forms were read.
SWEPT = {'sweep-best': F(kind='win', col='free', chg=1, scope='across', pose='other', images=8)}


def load(task):
    d = json.load(open(f'{R}data/tasks/{task}.json'))
    train = [(p['input'], p['output']) for p in d['train']]
    tests = [p['input'] for p in d['test']]
    del d
    return train, tests


def background(g):
    return collections.Counter(v for row in g for v in row).most_common(1)[0][0]


def components(g, bg, how):
    """how: 's8', 's4' or 'm8'. Lists of (r, c, color)."""
    h, w = len(g), len(g[0])
    seen = [[False] * w for _ in range(h)]
    near = ((-1, 0), (1, 0), (0, -1), (0, 1)) if how == 's4' else ((-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1))
    multi = how == 'm8'
    out = []
    for i in range(h):
        for j in range(w):
            v = g[i][j]
            if v == bg or seen[i][j]:
                continue
            stack, cells = [(i, j)], []
            seen[i][j] = True
            while stack:
                a, b = stack.pop()
                cells.append((a, b, g[a][b]))
                for dx, dy in near:
                    x, y = a + dx, b + dy
                    if 0 <= x < h and 0 <= y < w and not seen[x][y]:
                        u = g[x][y]
                        if (u != bg) if multi else (u == v):
                            seen[x][y] = True
                            stack.append((x, y))
            out.append(cells)
    return out


def instances(g, kinds):
    bg = background(g)
    out = {}
    s8 = components(g, bg, 's8') if 's8' in kinds or 'cs' in kinds else None
    if 's8' in kinds:
        out['s8'] = s8
    if 's4' in kinds:
        out['s4'] = components(g, bg, 's4')
    if 'm8' in kinds:
        out['m8'] = components(g, bg, 'm8')
    if 'cs' in kinds:
        by = collections.defaultdict(list)
        for cells in s8:
            by[cells[0][2]].append(cells)
        out['cs'] = [[c for part in v for c in part] for v in by.values() if len(v) >= 2]
    return out


def norm(cells, col):
    r, c = min(x[0] for x in cells), min(x[1] for x in cells)
    if col == 'same':
        return tuple(sorted(((x[0] - r) << 10) | ((x[1] - c) << 5) | x[2] for x in cells))
    return tuple(sorted(((x[0] - r) << 10) | ((x[1] - c) << 5) for x in cells))


IMAGES = {}


def images(pose):
    """All D4 images of a pose, as encoded cell tuples."""
    got = IMAGES.get(pose)
    if got is None:
        cells = [(x >> 10, (x >> 5) & 31, x & 31) for x in pose]
        got = frozenset(norm([f(a, b) + (v,) for a, b, v in cells], 'same') for f in D4)
        IMAGES[pose] = got
    return got


def new_class(size, nimg):
    return dict(size=size, images=nimg, inp={}, out=[])


def add_input(tab, posemap, pose, size, g):
    key = posemap.get(pose)
    if key is None:
        ims = images(pose)
        key = min(ims)
        for p in ims:
            posemap[p] = key
        tab[key] = new_class(size, len(ims))
    tab[key]['inp'].setdefault(g, set()).add(pose)


def win_keep(m, h, w):
    M = swv(m, (h, w))
    tight = M[:, :, 0, :].any(2) & M[:, :, -1, :].any(2) & M[:, :, :, 0].any(2) & M[:, :, :, -1].any(2)
    return M, tight & (M.sum((2, 3)) >= 4)


def pose_bytes(V, h, w):
    pre = bytes((h, w))
    L = h * w
    b = V.reshape(len(V), -1).tobytes()
    return [pre + b[i * L:(i + 1) * L] for i in range(len(V))]


def win_input(g, gid, tabs, maps):
    a = np.array(g, dtype=np.int8)
    m = a != background(g)
    H, W = m.shape
    for col, val in (('same', np.where(m, a, -1).astype(np.int8)), ('free', m.astype(np.int8))):
        if ('win', col) not in tabs:
            continue
        tab, pm = tabs[('win', col)], maps[('win', col)]
        for h, w in DIMS:
            if H < h or W < w:
                continue
            M, keep = win_keep(m, h, w)
            if not keep.any():
                continue
            V, Mk = swv(val, (h, w))[keep], M[keep]
            if len(V) > WIN_CAP:
                step = len(V) / WIN_CAP
                at = [int(i * step) for i in range(WIN_CAP)]
                V, Mk = V[at], Mk[at]
            sizes = Mk.sum((1, 2))
            ims = [pose_bytes(t, h, w) for t in (V, V[:, :, ::-1], V[:, ::-1, :], V[:, ::-1, ::-1])]
            T = V.transpose(0, 2, 1)
            ims += [pose_bytes(t, w, h) for t in (T, T[:, :, ::-1], T[:, ::-1, :], T[:, ::-1, ::-1])]
            for i, self_pose in enumerate(ims[0]):
                key = pm.get(self_pose)
                if key is None:
                    all_i = {x[i] for x in ims}
                    key = min(all_i)
                    for p in all_i:
                        pm[p] = key
                    tab[key] = new_class(int(sizes[i]), len(all_i))
                tab[key]['inp'].setdefault(gid, set()).add(self_pose)


def win_output(g, changed, maps, record):
    a = np.array(g, dtype=np.int8)
    m = a != background(g)
    H, W = m.shape
    chg = None if changed is None else np.array(changed, dtype=bool)
    for h, w in sorted(set(DIMS) | {(w, h) for h, w in DIMS}):
        if H < h or W < w:
            continue
        M, keep = win_keep(m, h, w)
        if not keep.any():
            continue
        Mk = M[keep]
        ch = None if chg is None else (swv(chg, (h, w))[keep] | ~Mk).all((1, 2))
        for col, val in (('same', np.where(m, a, -1).astype(np.int8)), ('free', m.astype(np.int8))):
            if ('win', col) not in maps:
                continue
            pm = maps[('win', col)]
            V = swv(val, (h, w))[keep]
            for i, pose in enumerate(pose_bytes(V, h, w)):
                key = pm.get(pose)
                if key is not None:
                    record(('win', col, 'comp'), key, pose, True if ch is None else bool(ch[i]))


def bit_rows(g, changed):
    h, w = len(g), len(g[0])
    bg = background(g)
    rows = collections.defaultdict(lambda: [0] * h)
    nz = [0] * h
    for i, row in enumerate(g):
        for j, v in enumerate(row):
            rows[v][i] |= 1 << j
            if v != bg:
                nz[i] |= 1 << j
    ch = None
    if changed is not None:
        ch = [sum(1 << j for j, v in enumerate(row) if v) for row in changed]
    return rows, nz, ch, h, w


def embed_output(kind, col, tab, br, record):
    rows, nz, ch, H, W = br
    big = sorted((c['size'], k) for k, c in tab.items() if c['size'] >= EMB_MIN and c['images'] >= 2)[-EMB_CAP:]
    for _, key in big:
        for pose in images(key):
            cells = [(x >> 10, (x >> 5) & 31, x & 31) for x in pose]
            h = max(c[0] for c in cells) + 1
            w = max(c[1] for c in cells) + 1
            if h > H or w > W:
                continue
            base = (1 << (W - w + 1)) - 1
            found = moved = False
            for dr in range(H - h + 1):
                cand = base
                for r, c, v in cells:
                    src = rows[v] if col == 'same' else nz
                    cand &= src[r + dr] >> c
                    if not cand:
                        break
                if cand:
                    found = True
                    if ch is None:
                        moved = True
                    else:
                        for r, c, _ in cells:
                            cand &= ch[r + dr] >> c
                            if not cand:
                                break
                        moved = moved or bool(cand)
                    if moved:
                        break
            if found:
                record((kind, col, 'embed'), key, pose, moved)


def build_input(train, tests, need):
    tabs = {k: {} for k in need}
    maps = {k: {} for k in need}
    times = collections.Counter()
    kinds = {k for k, _ in need if k != 'win'}
    grids = [(p, a) for p, (a, _) in enumerate(train)] + [(f't{i}', g) for i, g in enumerate(tests)]
    for gid, g in grids:
        t0 = time.perf_counter()
        inst = instances(g, kinds)
        times['comps'] += time.perf_counter() - t0
        for kind, lists in inst.items():
            for col in ('same', 'free'):
                if (kind, col) not in tabs:
                    continue
                t0 = time.perf_counter()
                tab, pm = tabs[(kind, col)], maps[(kind, col)]
                for cells in lists:
                    if 3 <= len(cells) <= MAXS:
                        add_input(tab, pm, norm(cells, col), len(cells), gid)
                times[kind] += time.perf_counter() - t0
        if ('win', 'same') in tabs or ('win', 'free') in tabs:
            t0 = time.perf_counter()
            win_input(g, gid, tabs, maps)
            times['win'] += time.perf_counter() - t0
    return tabs, maps, times


def read_outputs(train, outs, tabs, maps, need_embed):
    """recs: match key -> class key -> {pair: {pose: changed}}."""
    recs = collections.defaultdict(dict)
    times = collections.Counter()
    kinds = {k for k, _ in tabs if k != 'win'}
    for p, ((a, _), o) in enumerate(zip(train, outs)):
        changed = None
        if len(a) == len(o) and len(a[0]) == len(o[0]):
            changed = [[x != y for x, y in zip(ra, ro)] for ra, ro in zip(a, o)]

        def record(mk, key, pose, moved, p=p):
            pd = recs[mk].setdefault(key, {}).setdefault(p, {})
            pd[pose] = pd.get(pose, False) or moved

        t0 = time.perf_counter()
        inst = instances(o, kinds)
        times['comps'] += time.perf_counter() - t0
        for kind, lists in inst.items():
            for col in ('same', 'free'):
                if (kind, col) not in tabs:
                    continue
                t0 = time.perf_counter()
                pm = maps[(kind, col)]
                for cells in lists:
                    if 3 <= len(cells) <= MAXS:
                        pose = norm(cells, col)
                        key = pm.get(pose)
                        if key is not None:
                            moved = changed is None or all(changed[r][c] for r, c, _ in cells)
                            record((kind, col, 'comp'), key, pose, moved)
                times[kind] += time.perf_counter() - t0
        if ('win', 'same') in tabs or ('win', 'free') in tabs:
            t0 = time.perf_counter()
            win_output(o, changed, maps, record)
            times['win'] += time.perf_counter() - t0
        if need_embed:
            t0 = time.perf_counter()
            br = bit_rows(o, changed)
            for kind, col in need_embed:
                embed_output(kind, col, tabs[(kind, col)], br, record)
            times['embed'] += time.perf_counter() - t0
    return recs, times


def evaluate(form, tabs, recs, npairs):
    tab = tabs[(form['kind'], form['col'])]
    rec = recs.get((form['kind'], form['col'], form['match']), {})
    hit_pairs = set()
    nhit = ncopied = nsame = maxsize = 0
    for key, by_pair in rec.items():
        cl = tab[key]
        if cl['size'] < form['size'] or cl['images'] < form['images']:
            continue
        inp = cl['inp']
        hit = same = False
        for p, od in by_pair.items():
            O = {pose for pose, mv in od.items() if mv or not form['chg']}
            if not O:
                continue
            if form['scope'] == 'pair':
                I = inp.get(p)
            elif form['scope'] == 'across':
                I = set()
                for q, v in inp.items():
                    if isinstance(q, int) and q != p:
                        I |= v
            else:
                I = set()
                for v in inp.values():
                    I |= v
            if not I:
                continue
            if form['pose'] == 'new':
                h = bool(O - I)
            else:
                h = len(O | I) >= (2 if form['pose'] == 'other' else 3)
            if h:
                hit = True
                hit_pairs.add(p)
            if O & I:
                same = True
        if hit or same:
            ncopied += 1
        if same:
            nsame += 1
        if hit:
            nhit += 1
            maxsize = max(maxsize, cl['size'])
    return [int(nhit > 0), int(nsame > 0), round(len(hit_pairs) / npairs, 3), maxsize, nhit, ncopied]


def whole_flag(train):
    """Pairs whose output is, or holds, a non-identity D4 image of the whole input that differs from the input."""
    is_n = holds_n = 0
    for a, o in train:
        A, O = np.array(a, dtype=np.int8), np.array(o, dtype=np.int8)
        ims = [np.rot90(A, k) for k in (1, 2, 3)] + [np.rot90(np.fliplr(A), k) for k in range(4)]
        is_, holds = False, False
        for g in ims:
            if g.shape == A.shape and (g == A).all():
                continue
            if g.shape[0] > O.shape[0] or g.shape[1] > O.shape[1]:
                continue
            if g.shape == O.shape:
                if (g == O).all():
                    is_ = True
            elif (swv(O, g.shape) == g).all((2, 3)).any():
                holds = True
        is_n += is_
        holds_n += holds
    return is_n, holds_n


class Donors:
    def __init__(self, tasks):
        self.by = collections.defaultdict(list)
        for t in tasks:
            train, _ = load(t)
            for _, o in train:
                self.by[(len(o), len(o[0]))].append((t, o))

    def pick(self, task, draw, p, h, w):
        rng = random.Random(f'{task}/{draw}/{p}')
        pool = [x for x in self.by.get((h, w), ()) if x[0] != task]
        exact = bool(pool)
        if not pool:
            best = min((abs(a - h) + abs(b - w), a, b) for (a, b) in self.by if any(x[0] != task for x in self.by[(a, b)]))
            pool = [x for x in self.by[best[1:]] if x[0] != task]
        return rng.choice(pool)[1], exact


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--shard', default='0/1')
    ap.add_argument('--split', default='train')
    ap.add_argument('--forms', default='')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--draws', type=int, default=3)
    ap.add_argument('--no-win', action='store_true')
    ap.add_argument('out')
    args = ap.parse_args()
    labels = {}
    for line in open(RUN + 'labels.tsv').read().split('\n')[1:]:
        if line:
            x = line.split('\t')
            labels[x[0]] = x
    forms = dict(FORMS)
    if args.forms:
        forms = {k: {**FORMS, **SWEPT}[k] for k in json.load(open(args.forms))}
    if args.no_win:
        forms = {k: v for k, v in forms.items() if v['kind'] != 'win'}
    need = {(f['kind'], f['col']) for f in forms.values()}
    need_embed = sorted({(f['kind'], f['col']) for f in forms.values() if f['match'] == 'embed'})
    order = {'positive': 0, 'one-pose': 0, 'looks-posed': 0, 'plain': 1}
    tasks = [t for t, x in labels.items() if x[2] == args.split and x[1] in order]
    tasks.sort(key=lambda t: (order[labels[t][1]], hashlib.sha1(t.encode()).hexdigest()))
    if args.limit:
        tasks = tasks[:args.limit]
    i, n = map(int, args.shard.split('/'))
    tasks = tasks[i::n]
    done = set()
    if os.path.exists(args.out):
        for line in open(args.out):
            try:
                done.add(json.loads(line)['task'])
            except ValueError:
                pass
    todo = [t for t in tasks if t not in done]
    plain = [t for t, x in labels.items() if x[2] == 'train' and x[1] == 'plain']
    donors = Donors(plain) if args.draws else None
    print(f'shard {args.shard}: {len(tasks)} tasks, {len(done)} done, {len(forms)} forms, {args.draws} draws', flush=True)
    t_start = time.time()
    with open(args.out, 'a') as f:
        for at, t in enumerate(todo):
            train, tests = load(t)
            t0 = time.perf_counter()
            tabs, maps, ti = build_input(train, tests, need)
            outs = [o for _, o in train]
            recs, to = read_outputs(train, outs, tabs, maps, need_embed)
            t1 = time.perf_counter()
            res = {k: evaluate(v, tabs, recs, len(train)) for k, v in forms.items()}
            t2 = time.perf_counter()
            who = whole_flag(train)
            t3 = time.perf_counter()
            ctrl, exact = {k: [] for k in forms}, 0
            for d in range(args.draws):
                alt = []
                for p, (_, o) in enumerate(train):
                    g, ex = donors.pick(t, d, p, len(o), len(o[0]))
                    alt.append(g)
                    exact += ex
                rc, _ = read_outputs(train, alt, tabs, maps, need_embed)
                for k, v in forms.items():
                    ctrl[k].append(evaluate(v, tabs, rc, len(train))[:4])
            row = dict(task=t, group=labels[t][1], split=labels[t][2], pairs=len(train), same_size=sum(len(a) == len(o) and len(a[0]) == len(o[0]) for a, o in train),
                       whole=who, forms=res, control=ctrl, exact=exact,
                       ms=dict(all=round((t1 - t0) * 1e3, 1), eval=round((t2 - t1) * 1e3, 1), whole=round((t3 - t2) * 1e3, 1), control=round((time.perf_counter() - t3) * 1e3, 1),
                               parts={k: round((ti[k] + to[k]) * 1e3, 1) for k in set(ti) | set(to)}),
                       n_inp={f'{k[0]}-{k[1]}': len(v) for k, v in tabs.items()})
            f.write(json.dumps(row, separators=(',', ':')) + '\n')
            f.flush()
            rate = (at + 1) / (time.time() - t_start)
            print(f'{t} {labels[t][1]} base={res.get("base", ["-"])[0]} {row["ms"]["all"]:.0f}ms {at + 1}/{len(todo)} {rate:.1f}/s eta {(len(todo) - at - 1) / rate / 60:.1f}m', flush=True)
            IMAGES.clear()


main()
