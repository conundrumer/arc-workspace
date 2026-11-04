from pathlib import Path
import json, sys

MC, TC = 4, 2


def _markers(inp):
    h, w = len(inp), len(inp[0])
    cells = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == MC]
    ds = [abs(a[0] - b[0]) + abs(a[1] - b[1]) for a in cells for b in cells
          if a < b and (a[0] == b[0] or a[1] == b[1])]
    s = min(ds)
    seen, groups = set(), []
    for c in cells:
        if c in seen:
            continue
        grp, stack = [], [c]
        seen.add(c)
        while stack:
            p = stack.pop()
            grp.append(p)
            for q in cells:
                if q not in seen and max(abs(p[0] - q[0]), abs(p[1] - q[1])) <= s:
                    seen.add(q)
                    stack.append(q)
        groups.append(grp)
    marks = []
    for g in groups:
        rs = sorted({p[0] for p in g})
        cs = sorted({p[1] for p in g})
        for r in rs:
            for c in cs:
                if (r, c) not in g:
                    ctr = (sum(p[0] for p in g) / 3, sum(p[1] for p in g) / 3)
                    # direction from empty corner toward the three cells
                    tr = 1 if rs[-1] > r else -1
                    tc = 1 if cs[-1] > c else -1
                    marks.append(dict(E=(r, c), toward=(tr, tc), cells=g))
    return s, marks


def _solve(inp, mirror_axes="diff", direction=1, keep_markers=True, color=None,
           only=None, shift=(0, 0), drop_partial=False, extra=None):
    """mirror_axes: 'diff' (correct), 'none', 'both', 'row', 'col', 'same'."""
    h, w = len(inp), len(inp[0])
    s, marks = _markers(inp)
    tmpl = [(r, c) for r in range(h) for c in range(w) if inp[r][c] == TC]
    r0, r1 = min(p[0] for p in tmpl), max(p[0] for p in tmpl)
    c0, c1 = min(p[1] for p in tmpl), max(p[1] for p in tmpl)
    src = None
    for m in marks:
        t = (-m["toward"][0], -m["toward"][1])
        er, ec = m["E"]
        okr = (r0 == er) if t[0] == 1 else (r1 == er)
        okc = (c0 == ec) if t[1] == 1 else (c1 == ec)
        if okr and okc:
            src = m
    t0 = (-src["toward"][0], -src["toward"][1])
    out = [row[:] for row in inp]
    if not keep_markers:
        out = [[0 if v == MC else v for v in row] for row in out]
    targets = [m for m in marks if m is not src]
    if only is not None:
        targets = only(src, targets)
    for m in targets:
        t = (-m["toward"][0], -m["toward"][1])
        if direction == -1:
            t = (-t[0], -t[1])
        fr = t[0] * t0[0]
        fc = t[1] * t0[1]
        if mirror_axes == "none":
            fr = fc = 1
        elif mirror_axes == "both":
            fr = fc = -1
        elif mirror_axes == "row":
            fc = 1
        elif mirror_axes == "col":
            fr = 1
        elif mirror_axes == "same":
            fr, fc = -fr, -fc
        er, ec = m["E"]
        er += shift[0]
        ec += shift[1]
        placed = []
        for (r, c) in tmpl:
            nr = er + fr * (r - src["E"][0])
            nc = ec + fc * (c - src["E"][1])
            placed.append((nr, nc))
        if drop_partial and any(not (0 <= a < h and 0 <= b < w) for a, b in placed):
            continue
        for nr, nc in placed:
            if 0 <= nr < h and 0 <= nc < w:
                out[nr][nc] = color if color is not None else TC
    return out


def _nearest(src, targets):
    d = lambda m: abs(m["E"][0] - src["E"][0]) + abs(m["E"][1] - src["E"][1])
    return [min(targets, key=d)]


def _same_orient(src, targets):
    return [m for m in targets if m["toward"] == src["toward"]]


def _farthest_dropped(src, targets):
    d = lambda m: abs(m["E"][0] - src["E"][0]) + abs(m["E"][1] - src["E"][1])
    return sorted(targets, key=d)[:-1]


def _template_only_copy_no_template(inp, out):
    # copies written, but the template itself erased
    o = _solve(inp)
    for r in range(len(inp)):
        for c in range(len(inp[0])):
            if inp[r][c] == TC:
                o[r][c] = 0
    return o


def _marker_cells_erased_in_copy(inp, out):
    # copy region cleared of marker color wherever copy lands: here, erase markers that
    # are the targets (their cells vanish)
    o = _solve(inp)
    s, marks = _markers(inp)
    for m in marks:
        for (r, c) in m["cells"]:
            if o[r][c] == MC:
                o[r][c] = 0
    return o


ALTERNATIVES = [
    ("copies are plain translations of the template; no mirroring on any axis",
     lambda i, o: _solve(i, "none")),
    ("every copy is turned 180 degrees (mirrored on both axes) regardless of the target marker",
     lambda i, o: _solve(i, "both")),
    ("mirror only across the row axis (vertical flip); the column axis is never mirrored",
     lambda i, o: _solve(i, "row")),
    ("mirror only across the column axis (horizontal flip); the row axis is never mirrored",
     lambda i, o: _solve(i, "col")),
    ("mirror is inverted: axes that should flip stay, axes that should stay get flipped",
     lambda i, o: _solve(i, "same")),
    ("copy extends toward the marker's three cells instead of away from them",
     lambda i, o: _solve(i, "diff", direction=-1)),
    ("copy corner is anchored one cell diagonally off the marker's empty corner",
     lambda i, o: _solve(i, "diff", shift=(1, 1))),
    ("template copied only to the single nearest other marker",
     lambda i, o: _solve(i, "diff", only=_nearest)),
    ("template copied only to markers with the same orientation as the template's marker",
     lambda i, o: _solve(i, "diff", only=_same_orient)),
    ("template copied to every other marker except the farthest one",
     lambda i, o: _solve(i, "diff", only=_farthest_dropped)),
    ("copies are drawn in the marker color instead of the template color",
     lambda i, o: _solve(i, "diff", color=MC)),
    ("the original template is erased after copying",
     _template_only_copy_no_template),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9
                    for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(str(Path(__file__).resolve().parents[3] / 'data/tasks/ac0c5833.json')))
    pairs = task["train"]
    # sanity: the correct reading reproduces the true output
    print("correct reading matches:", [_solve(p["input"]) == p["output"] for p in pairs])
    print("task ac0c5833, readings", len(ALTERNATIVES), "pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            try:
                g = f(p["input"], p["output"])
            except Exception as e:
                print("  error:", desc, repr(e))
                g = None
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), desc)
