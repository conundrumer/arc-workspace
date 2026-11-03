"""Can a join of recorded nodes give the output? A node that reads the train output, or reads such a node, is left out. A node is clean where its table, painted on the train inputs, fixes at least one wrong cell and breaks none, with no wrong color, conflict or cell out of bounds. The task's reach is the share of wrong train cells that clean nodes fix together. Where they fix all, a greedy cover picks a small set, and its paint on each test input is compared with the test output. Only that last check reads a test output; it decides nothing above it.

  union.py TAG RECORD_DIR TASK_FILE
"""
import collections, glob, itertools, json, os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE + '/../policy5')
from nodefeat import Pair, columns  # noqa: E402
tag, rec, tf = sys.argv[1:4]
OUT = f'{HERE}/out/{tag}'
os.makedirs(OUT, exist_ok=True)


def base_of(p, i, j):
    return p.a[i][j] if p.same else p.obg


def paint(node, pairs):
    """The best (fixed cells, position column, color column) over the node's column pairs, for a clean paint."""
    types = node['table_types'] or node['types']
    pos = [i for i, t in enumerate(types) if t == 'Position']; col = [i for i, t in enumerate(types) if t == 'Color']
    if not pos or not col:
        return None
    tab = {}
    for ent in node['x_rows'] or []:
        (a, e), rows = ent[0], ent[1]
        c = columns(rows, types)
        if a == 1 and e < len(pairs) and c is not None:
            tab[e] = c
    best = None
    for pi, ci in itertools.product(pos, col):
        fixed = set(); ok = True
        for e, p in enumerate(pairs):
            cells = collections.defaultdict(set)
            for r in tab.get(e, ()):
                cells[(r[pi][0], r[pi][2])].add(r[ci][0])
            H, W = len(p.b), len(p.b[0])
            for (i, j), cs in cells.items():
                if not (0 <= i < H and 0 <= j < W) or len(cs) > 1 or next(iter(cs)) != p.b[i][j]:
                    ok = False; break
                if base_of(p, i, j) != p.b[i][j]:
                    fixed.add((e, i, j))
            if not ok:
                break
        if ok and fixed and (best is None or len(fixed) > len(best[0])):
            best = fixed, pi, ci
    return best


t0 = time.time()
tasks = open(tf).read().split()
for n, t in enumerate(tasks, 1):
    o = f'{OUT}/{t}.json'; f = glob.glob(f'{rec}/{t}*.zst')
    if os.path.exists(o) or not f:
        continue
    d = json.load(open(f'/Users/davidlu/code/arc-workspace/data/tasks/{t}.json'))
    pairs = [Pair(x['input'], x['output']) for x in d['train']]
    need = {(e, i, j) for e, p in enumerate(pairs) for i, j in (p.changed if p.same else p.ofg)}
    clean = []; nodes = 0; bad = set()
    for raw in subprocess.Popen(['zstd', '-dcq', f[0]], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout:
        try:
            r = json.loads(raw)
        except ValueError:
            continue
        nodes += 1
        if '(output ' in (r['clause'] or '') or any(x in bad for x in r['parents']):
            bad.add(r['token'])  # reads the train output, so it has no rows on a test input
            continue
        b = paint(r, pairs) if any(e[0] == 2 and e[2] for e in r['examples']) else None  # a node with no row on any test input can't change a test output
        if b:
            clean.append((b[0], b[1], b[2], r))
    u = set().union(*[c[0] for c in clean]) if clean else set()
    pick = []
    if need and u == need:
        left = set(need)
        while left:
            c = max(clean, key=lambda c: (len(c[0] & left), -c[3]['depth']))
            pick.append(c); left -= c[0]
    right = None
    if pick and all(p.same for p in pairs):
        types = None; right = True
        for k, ex in enumerate(d['test']):
            g = [list(x) for x in ex['input']]
            for _, pi, ci, r in pick:
                types = r['table_types'] or r['types']
                for ent in r['x_rows'] or []:
                    if ent[0] == [2, k]:
                        for row in columns(ent[1], types) or []:
                            i, j = row[pi][0], row[pi][2]
                            if 0 <= i < len(g) and 0 <= j < len(g[0]):
                                g[i][j] = row[ci][0]
            right = right and 'output' in ex and g == ex['output']
    v = dict(task=t, nodes=nodes, clean=len(clean), need=len(need), reach=len(u) / max(len(need), 1), full=bool(need and u == need), picks=len(pick), depths=[c[3]['depth'] for c in pick], right=right, same=all(p.same for p in pairs))
    json.dump(v, open(o + '.new', 'w')); os.replace(o + '.new', o)
    el = time.time() - t0
    print(f'{n}/{len(tasks)} {t} nodes {nodes} clean {len(clean)} need {len(need)} reach {v["reach"]:.2f} picks {len(pick)} right {right} | {el:.0f} s | ETA {el / n * (len(tasks) - n):.0f} s', flush=True)
print('done', flush=True)
