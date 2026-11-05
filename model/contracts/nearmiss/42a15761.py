import json
from pathlib import Path


def _split(g):
    """Return (list of (c0, c1) panel column spans, gap columns) from a grid."""
    h, w = len(g), len(g[0])
    gaps = [c for c in range(w) if all(g[r][c] == 0 for r in range(h))]
    spans, c = [], 0
    while c < w:
        if c in gaps:
            c += 1
            continue
        c0 = c
        while c < w and c not in gaps:
            c += 1
        spans.append((c0, c))
    return spans, gaps


def _panels(g):
    spans, _ = _split(g)
    return [[row[a:b] for row in g] for a, b in spans]


def _marks(p):
    return sum(row.count(0) for row in p)


def _assemble(g, panels):
    """Put panels back into the panel slots of grid g (keeps gap columns)."""
    spans, _ = _split(g)
    res = [row[:] for row in g]
    for (a, b), p in zip(spans, panels):
        for r in range(len(g)):
            res[r][a:b] = p[r]
    return res


def _desc(inp, out):
    ps = _panels(inp)
    return _assemble(inp, sorted(ps, key=_marks, reverse=True))


def _unsorted(inp, out):
    return [r[:] for r in inp]


def _reverse(inp, out):
    return _assemble(inp, _panels(inp)[::-1])


def _rotate(inp, out):
    ps = _panels(inp)
    return _assemble(inp, ps[1:] + ps[:1])


def _first_fixed(inp, out):
    ps = _panels(inp)
    return _assemble(inp, ps[:1] + sorted(ps[1:], key=_marks))


def _one_pass(inp, out):
    ps = _panels(inp)
    for i in range(len(ps) - 1):
        if _marks(ps[i]) > _marks(ps[i + 1]):
            ps[i], ps[i + 1] = ps[i + 1], ps[i]
    return _assemble(inp, ps)


def _by_first_mark_row(inp, out):
    def key(p):
        rows = [r for r, row in enumerate(p) if 0 in row]
        return rows[0] if rows else len(p)
    return _assemble(inp, sorted(_panels(inp), key=key))


def _top_aligned(inp, out):
    ps = _panels(out)
    new = []
    for p in ps:
        n = _marks(p)
        h, w = len(p), len(p[0])
        q = [[2] * w for _ in range(h)]
        for i in range(n):
            if 1 + 2 * i < h:
                q[1 + 2 * i][w // 2] = 0
        new.append(q)
    return _assemble(out, new)


def _gaps_filled(inp, out):
    _, gaps = _split(out)
    res = [r[:] for r in out]
    for c in gaps:
        for r in range(len(res)):
            res[r][c] = 2
    return res


def _crop_gaps(inp, out):
    _, gaps = _split(out)
    return [[v for c, v in enumerate(r) if c not in gaps] for r in out]


def _by_panel_row_parity(inp, out):
    # counts only marks on odd-numbered rows of 1,5,9 (every second mark)
    def key(p):
        return sum(1 for r, row in enumerate(p) if 0 in row and r % 4 == 1)
    return _assemble(inp, sorted(_panels(inp), key=key))


def _transposed_sort(inp, out):
    # sorts the panels by marks, then flips each panel vertically
    ps = sorted(_panels(inp), key=_marks)
    return _assemble(inp, [p[::-1] for p in ps])


ALTERNATIVES = [
    ("sort panels by mark count most first", _desc),
    ("leave the panels in input order", _unsorted),
    ("reverse the panel order", _reverse),
    ("rotate the panels one slot left", _rotate),
    ("sort all panels but the first", _first_fixed),
    ("one bubble pass instead of full sort", _one_pass),
    ("sort panels by row of first mark", _by_first_mark_row),
    ("stack marks from the top of each panel", _top_aligned),
    ("fill gap columns with panel color", _gaps_filled),
    ("drop gap columns from output", _crop_gaps),
    ("count only marks on rows 1,5,9 when sorting", _by_panel_row_parity),
    ("sort panels and flip each upside down", _transposed_sort),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(type(v) is int and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/42a15761.json"))
    train = task["train"]
    print(len(train), "train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(n, desc)
