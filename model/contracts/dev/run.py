"""Dev labeling layer: its output is not model input.

Variants of one task and the features of every table on each, streamed to out/<task>.variants.jsonl.

    <runtime python> -I -B run.py TASK [N_INPUT] [N_OUTPUT]

An input variant edits one train input at random (1 to 3 small edits) and appends it as an extra test input, so the train pairs, and the values
they determine, stay as they are; its features are those of that test input, its `stored` is whether the stored values that solve the train pairs are the task's (`same`), others (`changed`), or none (`unsolved`), and its `stored_changed` names the stored relations whose rows differ from the task's. Where none solve, each stored relation holds no row. An output variant recolors 1 or 2 cells of one train output; its
features are those at that train example of the task with the edited output, at the task's own proposer values, since an edit to a train output
breaks the fit of every value. Each variant's tables go to the table cache (tablecache.py). A restart skips the variants already written.
"""
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'features'))
import engine as E  # noqa: E402
import features as F  # noqa: E402
import jsonl as J  # noqa: E402
import tablecache as C  # noqa: E402

HERE = Path(__file__).parent
OUT = Path(os.environ.get('CONTRACTS_OUT', HERE / 'out'))  # where the variants go


def grids_of(task_json, ex):
    kind, i = ex.split('/')
    p = task_json[kind][int(i)]
    return p['input'], p.get('output') if kind == 'train' else None


CELL_OPS = ['erase', 'grow', 'recolor', 'speck', 'swap']
OBJECT_OPS = ['move object', 'copy object', 'recolor object', 'remove object']


def objects(g, bg, multi=False):
    """The objects of non-background cells, as lists of cells: 4-connected and of one color, or (multi) 8-connected and of any colors."""
    H, W = len(g), len(g[0])
    steps = [(a, b) for a in (-1, 0, 1) for b in (-1, 0, 1) if (a, b) != (0, 0)] if multi else [(1, 0), (-1, 0), (0, 1), (0, -1)]
    seen, out = set(), []
    for r in range(H):
        for c in range(W):
            if g[r][c] == bg or (r, c) in seen:
                continue
            todo, obj = [(r, c)], []
            while todo:
                x, y = todo.pop()
                if (x, y) in seen or not (0 <= x < H and 0 <= y < W) or g[x][y] == bg or (not multi and g[x][y] != g[r][c]):
                    continue
                seen.add((x, y))
                obj.append((x, y))
                todo += [(x + a, y + b) for a, b in steps]
            out.append(obj)
    return out


def place(g, obj, colors, dr, dc, bg, clear):
    """Draws obj moved by (dr, dc) where every target cell is in the grid and background (or the object's own); False otherwise."""
    H, W = len(g), len(g[0])
    own = set(obj) if clear else set()
    tgt = [(r + dr, c + dc) for r, c in obj]
    if not all(0 <= r < H and 0 <= c < W and (g[r][c] == bg or (r, c) in own) for r, c in tgt):
        return False
    if clear:
        for r, c in obj:
            g[r][c] = bg
    for (r, c), v in zip(tgt, colors):
        g[r][c] = v
    return True


def object_op(g, op, rng, bg, fg):
    objs = objects(g, bg, multi=rng.random() < 0.5)
    if not objs:
        return False
    obj = rng.choice(objs)
    colors = [g[r][c] for r, c in obj]
    if op == 'remove object':
        for r, c in obj:
            g[r][c] = bg
        return True
    if op == 'recolor object':
        old = rng.choice(sorted(set(colors)))
        new = rng.choice([x for x in fg if x != old] or [rng.randint(1, 9)])
        for r, c in obj:
            if g[r][c] == old:
                g[r][c] = new
        return True
    H, W = len(g), len(g[0])
    for _ in range(20):
        if op == 'move object':
            dr, dc = rng.choice([(a, b) for a in range(-2, 3) for b in range(-2, 3) if (a, b) != (0, 0)])
        else:
            dr, dc = rng.randrange(-H + 1, H), rng.randrange(-W + 1, W)
        if place(g, obj, colors, dr, dc, bg, op == 'move object'):
            return True
    return False


def mutate(g, rng, ops=CELL_OPS + OBJECT_OPS):
    g = [list(r) for r in g]
    H, W = len(g), len(g[0])
    bg = Counter(v for r in g for v in r).most_common(1)[0][0]
    fg = sorted({v for r in g for v in r} - {bg}) or [1]
    done = []
    for _ in range(rng.randint(1, 3)):
        op = rng.choice(ops)
        if op in OBJECT_OPS:
            if object_op(g, op, rng, bg, fg):
                done.append(op)
            continue
        ink = [(r, c) for r in range(H) for c in range(W) if g[r][c] != bg]
        if op == 'erase' and ink:
            r, c = rng.choice(ink)
            g[r][c] = bg
        elif op == 'grow' and ink:
            near = [(r + a, c + b) for r, c in ink for a in (-1, 0, 1) for b in (-1, 0, 1)
                    if 0 <= r + a < H and 0 <= c + b < W and g[r + a][c + b] == bg]
            if near:
                r, c = rng.choice(near)
                nb = [g[r + a][c + b] for a in (-1, 0, 1) for b in (-1, 0, 1) if 0 <= r + a < H and 0 <= c + b < W and g[r + a][c + b] != bg]
                g[r][c] = rng.choice(nb)
        elif op == 'recolor' and ink:
            r, c = rng.choice(ink)
            g[r][c] = rng.choice([x for x in fg if x != g[r][c]] or [rng.randint(1, 9)])
        elif op == 'swap' and len({g[r][c] for r, c in ink}) > 1:
            a = rng.choice(ink)
            b = rng.choice([x for x in ink if g[x[0]][x[1]] != g[a[0]][a[1]]])
            g[a[0]][a[1]], g[b[0]][b[1]] = g[b[0]][b[1]], g[a[0]][a[1]]
        elif op == 'speck':
            r, c = rng.randrange(H), rng.randrange(W)
            g[r][c] = rng.choice(fg)
        done.append(op)
    return g, done


def main(task, n_in=250, n_out=60, n_obj=0):
    OUT.mkdir(exist_ok=True)
    path = OUT / (task + '.variants.jsonl')
    done = {r['id'] for r in J.records(path)}
    eng = C.Engine(task)
    s, base_json, T0 = eng.s, eng.bj, eng.T0
    graph = E.reads(s.text)
    rd = E.table_reads(s.text)
    up = lambda g, name: E.upstream(g, name)
    todo = [('base', None, None)] + [('in', i, k) for k in range(n_in) for i in range(len(base_json['train']))] + \
           [('out', i, k) for k in range(n_out) for i in range(len(base_json['train']))] + \
           [('obj', i, k) for k in range(n_obj) for i in range(len(base_json['train']))]
    todo = [x for x in todo if '%s.%s.%s' % x not in done]
    t0, n = time.time(), 0
    fcache = F.FeatureCache()  # the features of tables that a variant leaves as they were
    with J.Appender(path) as fo, C.Cache(task, eng, {'%s.%s.%s' % x for x in todo}) as cache:
        for kind, i, k in todo:
            vid = '%s.%s.%s' % (kind, i, k)
            rec = dict(id=vid, kind=kind)
            try:
                if kind == 'base':
                    rec['examples'] = {}
                    exs = ['train/%d' % j for j in range(len(base_json['train']))] + ['test/%d' % j for j in range(len(base_json['test']))]
                    for ex in exs:
                        rec['examples'][ex] = enc(F.all_features(T0, ex, base_json, graph, up, grids_of, fcache, reads=rd, prov=s.provenance))
                    rec['tables'] = {name: [list(c) for c in t['columns']] for name, t in T0.items()}
                    rec['graph'] = {k: sorted(v) for k, v in graph.items()}
                    rec['reads_ports'] = {k: sorted(v) for k, v in E.reads_ports(s.text).items()}
                    rec['out'] = s.out
                elif kind in ('in', 'obj'):
                    rng = random.Random('%s.%s.%d.%d' % (task, kind, i, k))
                    g, ops = mutate(base_json['train'][i]['input'], rng, *([OBJECT_OPS] if kind == 'obj' else []))
                    rec.update(kind='in', source='train/%d' % i, ops=ops, grid=g)
                    T, tj, ex = cache.tables(rec)
                    rec['features'] = enc(F.all_features(T, ex, tj, graph, up, grids_of, fcache, reads=rd, prov=s.provenance))
                else:
                    rng = random.Random('%s.out.%d.%d' % (task, i, k))
                    o = [list(r) for r in base_json['train'][i]['output']]
                    ops = []
                    for _ in range(rng.randint(1, 2)):
                        r, c = rng.randrange(len(o)), rng.randrange(len(o[0]))
                        o[r][c] = rng.choice([x for x in range(10) if x != o[r][c]])
                        ops.append((r, c, o[r][c]))
                    rec.update(source='train/%d' % i, ops=ops)
                    T, tj, ex = cache.tables(rec)
                    rec['features'] = enc(F.all_features(T, ex, tj, graph, up, grids_of, fcache, reads=rd, prov=s.provenance))
            except Exception as e:  # noqa: BLE001
                rec['error'] = '%s: %s' % (type(e).__name__, str(e)[:300])
            fo.write(rec)
            n += 1
            if n % 100 == 0 or n == len(todo):
                el = time.time() - t0
                print('%s %d/%d  %.1f/s  eta %.0fs' % (task, n, len(todo), n / el, (len(todo) - n) * el / n), flush=True)


def enc(fs):
    return {'%s|%s' % k: v for k, v in fs.items()}


if __name__ == '__main__':
    main(sys.argv[1], *map(int, sys.argv[2:]))
