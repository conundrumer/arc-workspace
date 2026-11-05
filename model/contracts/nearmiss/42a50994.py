from pathlib import Path
import json

D8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
D4 = [(-1, 0), (1, 0), (0, -1), (0, 1)]
DX = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
DH = [(0, -1), (0, 1)]


def _bg(g):
    cnt = {}
    for r in g:
        for v in r:
            cnt[v] = cnt.get(v, 0) + 1
    return max(cnt, key=cnt.get)


def _keep_by_dirs(inp, dirs, reach=1):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    res = [[bg] * w for _ in range(h)]
    for i in range(h):
        for j in range(w):
            if inp[i][j] == bg:
                continue
            for di, dj in dirs:
                for k in range(1, reach + 1):
                    a, b = i + di * k, j + dj * k
                    if 0 <= a < h and 0 <= b < w and inp[a][b] != bg:
                        res[i][j] = inp[i][j]
    return res


def _components(inp):
    bg = _bg(inp)
    h, w = len(inp), len(inp[0])
    seen = set()
    comps = []
    for i in range(h):
        for j in range(w):
            if inp[i][j] != bg and (i, j) not in seen:
                st = [(i, j)]
                seen.add((i, j))
                c = []
                while st:
                    a, b = st.pop()
                    c.append((a, b))
                    for di, dj in D8:
                        p, q = a + di, b + dj
                        if 0 <= p < h and 0 <= q < w and inp[p][q] != bg and (p, q) not in seen:
                            seen.add((p, q))
                            st.append((p, q))
                comps.append(c)
    return comps


def orthogonal_only(inp, out):
    return _keep_by_dirs(inp, D4)


def diagonal_only(inp, out):
    return _keep_by_dirs(inp, DX)


def horizontal_only(inp, out):
    return _keep_by_dirs(inp, DH)


def reach_two(inp, out):
    return _keep_by_dirs(inp, D8, 2)


def drop_pairs(inp, out):
    bg = _bg(inp)
    res = [[bg] * len(inp[0]) for _ in inp]
    for c in _components(inp):
        if len(c) >= 3:
            for a, b in c:
                res[a][b] = inp[a][b]
    return res


def largest_only(inp, out):
    bg = _bg(inp)
    res = [[bg] * len(inp[0]) for _ in inp]
    comps = _components(inp)
    big = max(comps, key=len)
    for a, b in big:
        res[a][b] = inp[a][b]
    return res


def keep_isolated(inp, out):
    bg = _bg(inp)
    return [[(inp[i][j] if inp[i][j] != bg and out[i][j] == bg else bg)
             for j in range(len(inp[0]))] for i in range(len(inp))]


def top_half_only(inp, out):
    h = len(inp)
    res = [r[:] for r in out]
    for i in range(h // 2, h):
        res[i] = inp[i][:]
    return res


def keep_border_isolated(inp, out):
    h, w = len(inp), len(inp[0])
    bg = _bg(inp)
    res = [r[:] for r in out]
    for i in range(h):
        for j in range(w):
            if inp[i][j] != bg and (i in (0, h - 1) or j in (0, w - 1)):
                res[i][j] = inp[i][j]
    return res


def crop_to_ink(inp, out):
    bg = _bg(out)
    rows = [i for i, r in enumerate(out) if any(v != bg for v in r)]
    cols = [j for j in range(len(out[0])) if any(r[j] != bg for r in out)]
    return [r[cols[0]:cols[-1] + 1] for r in out[rows[0]:rows[-1] + 1]]


def erased_marked(inp, out):
    bg = _bg(inp)
    return [[(2 if (inp[i][j] != bg and out[i][j] == bg and inp[i][j] != 2) else out[i][j])
             for j in range(len(inp[0]))] for i in range(len(inp))]


def drop_one_per_group(inp, out):
    bg = _bg(inp)
    res = [r[:] for r in out]
    for c in _components(inp):
        if len(c) >= 2:
            a, b = min(c)
            res[a][b] = bg
    return res


ALTERNATIVES = [
    ("neighbors counted orthogonally only; diagonal neighbors do not group", orthogonal_only),
    ("neighbors counted diagonally only; orthogonal neighbors do not group", diagonal_only),
    ("neighbors counted horizontally only", horizontal_only),
    ("neighbors counted within distance 2, so fewer dots are removed", reach_two),
    ("groups of two dots are removed too; only groups of 3 or more stay", drop_pairs),
    ("only the largest group stays", largest_only),
    ("inverted: isolated dots stay and grouped dots are removed", keep_isolated),
    ("isolated dots are removed only in the top half of the grid", top_half_only),
    ("dots on the grid border are always kept", keep_border_isolated),
    ("output cropped to the bounding box of the kept dots", crop_to_ink),
    ("isolated dots are recolored 2 instead of erased", erased_marked),
    ("one dot of each group is erased as well", drop_one_per_group),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/42a50994.json'))
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
