import json
from pathlib import Path

WEDGE = 5


def _analyze(inp):
    """Return line color, axis kind, line key, and per side wedge info."""
    h, w = len(inp), len(inp[0])
    cells = {}
    for r in range(h):
        for c in range(w):
            v = inp[r][c]
            if v != 0:
                cells.setdefault(v, []).append((r, c))
    lc = [v for v in cells if v != WEDGE][0]
    line = cells[lc]
    kind = None
    for kd, f in (("d", lambda r, c: c - r), ("s", lambda r, c: c + r)):
        if len({f(r, c) for r, c in line}) == 1:
            kind = kd
    f = (lambda r, c: c - r) if kind == "d" else (lambda r, c: c + r)
    key = f(*line[0])
    sides = {}
    for r, c in cells.get(WEDGE, []):
        off = f(r, c) - key
        s = 1 if off > 0 else -1
        d = sides.setdefault(s, {"k": 0, "cells": []})
        d["k"] = max(d["k"], abs(off))
        d["cells"].append((r, c))
    return dict(h=h, w=w, lc=lc, line=line, kind=kind, key=key, f=f, sides=sides)


def _render(a, new_lines, color=None, keep_line=True, extra=()):
    h, w = a["h"], a["w"]
    g = [[0] * w for _ in range(h)]
    col = a["lc"] if color is None else color
    if keep_line:
        for r, c in a["line"]:
            g[r][c] = a["lc"]
    for k, cells in new_lines:
        for r in range(h):
            for c in range(w):
                if a["f"](r, c) == k and (cells is None or (r, c) in cells):
                    g[r][c] = col
    for r, c in extra:
        g[r][c] = WEDGE
    return g


def _with_gap(inp, gapfix, sign_flip=False, **kw):
    a = _analyze(inp)
    lines = []
    for s, d in a["sides"].items():
        ss = -s if sign_flip else s
        lines.append((a["key"] + ss * gapfix(d), None))
    return _render(a, lines, **kw)


def gap0(inp, out):
    return _with_gap(inp, lambda d: d["k"] + 1)


def gap2(inp, out):
    return _with_gap(inp, lambda d: d["k"] + 3)


def offset_k(inp, out):
    return _with_gap(inp, lambda d: d["k"])


def cell_count(inp, out):
    return _with_gap(inp, lambda d: len(d["cells"]))


def mirrored(inp, out):
    return _with_gap(inp, lambda d: d["k"] + 2, sign_flip=True)


def wrong_color(inp, out):
    return _with_gap(inp, lambda d: d["k"] + 2, color=WEDGE)


def keep_wedges(inp, out):
    a = _analyze(inp)
    extra = [p for d in a["sides"].values() for p in d["cells"]]
    return _with_gap(inp, lambda d: d["k"] + 2, extra=extra)


def no_new_line(inp, out):
    a = _analyze(inp)
    return _render(a, [])


def partial_line(inp, out):
    a = _analyze(inp)
    lines = []
    for s, d in a["sides"].items():
        rows = {r for r, c in d["cells"]}
        lo, hi = min(rows), max(rows)
        k = a["key"] + s * (d["k"] + 2)
        cells = {(r, c) for r in range(lo, hi + 1) for c in range(a["w"])}
        lines.append((k, cells))
    return _render(a, lines)


def drop_original_line(inp, out):
    return _with_gap(inp, lambda d: d["k"] + 2, keep_line=False)


def only_largest_wedge(inp, out):
    a = _analyze(inp)
    if len(a["sides"]) < 2:
        return None
    s, d = max(a["sides"].items(), key=lambda t: len(t[1]["cells"]))
    return _render(a, [(a["key"] + s * (d["k"] + 2), None)])


ALTERNATIVES = [
    ("new line directly next to the wedge's far corner (no empty diagonal gap)", gap0),
    ("two empty diagonals between the wedge and the new line instead of one", gap2),
    ("new line drawn on the wedge's farthest diagonal, one step too near", offset_k),
    ("distance of the new line taken from the wedge's cell count", cell_count),
    ("new line drawn on the side of the line opposite the wedge", mirrored),
    ("new line drawn in the wedge color instead of the line color", wrong_color),
    ("wedges left in place and new line added", keep_wedges),
    ("wedges erased but no new line drawn", no_new_line),
    ("new line limited to the rows the wedge spans, not edge to edge", partial_line),
    ("original line removed, only the new lines kept", drop_original_line),
    ("only the larger wedge gets a new line", only_largest_wedge),
]


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/a78176bb.json"))
    pairs = task["train"]
    print("pairs", len(pairs))
    # the true rule with gap 1 must reproduce the output
    for p in pairs:
        assert _with_gap(p["input"], lambda d: d["k"] + 2) == p["output"], "base rule mismatch"

    def valid(g, out):
        return (
            isinstance(g, list)
            and len(g) > 0
            and all(isinstance(r, list) and len(r) == len(g[0]) for r in g)
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r)
            and g != out
        )

    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and valid(g, p["output"]):
                n += 1
        print(n, "/", len(pairs), desc)
