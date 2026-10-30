"""Layouts of a relation's rows: tables and grids, nested in any order.

A layout is a list of entries, written in one string separated by spaces:

    A,B   a table entry: the rows grouped by the values of A and B, each key printed once, with what the rest of
          the layout gives for that group beside it; as the last entry, the distinct values of A and B
    P*    a grid entry: the rows drawn on a grid by the cell column P, each grid cell holding what the rest of the
          layout gives for the rows at that cell
    E     the example, an implicit column of every table: ex0, ex1, ..., test0
    M     the model, an implicit column of a relation with more than one model at an example: each model has a
          block of its own, and a layout that holds M shows every model, where the default shows the first two

`render(rows, entries)` gives the lines of one layout over a list of Rows.
"""
from typing import NamedTuple


class Row(NamedTuple):
    text: dict    # {column: the value's text}
    key: dict     # {column: a value that sorts in the column's order}
    cell: dict    # {column: (row, col, height, width)} for a Box column whose value is a cell of its frame


class Table(NamedTuple):
    cols: tuple


class Grid(NamedTuple):
    col: str


def parse(layout):
    """The entries of a layout string. E and M, which every view groups by first, are left out."""
    out = []
    for tok in layout.split():
        if tok in ("E", "M"):
            continue
        if tok.endswith("*") and len(tok) > 1 and "," not in tok:
            out.append(Grid(tok[:-1]))
        else:
            out.append(Table(tuple(c for c in tok.split(",") if c)))
    return out


def show(entries):
    return " ".join(f"{e.col}*" if isinstance(e, Grid) else ",".join(e.cols) for e in entries)


def isgrid(entries):
    return any(isinstance(e, Grid) for e in entries)


def columns(entries):
    return [c for e in entries for c in ((e.col,) if isinstance(e, Grid) else e.cols)]


def render(rows, entries):
    """The lines of the layout over rows."""
    if not entries or not rows:
        return []
    e, rest = entries[0], entries[1:]
    if isinstance(e, Grid):
        return grid(rows, e.col, rest)
    return table(rows, e.cols, rest)


def table(rows, cols, rest):
    groups = {}
    for r in rows:
        groups.setdefault(tuple(r.text.get(c, "?") for c in cols), []).append(r)
    order = sorted(groups, key=lambda k: tuple(sort_key(groups[k][0], c) for c in cols))
    widths = [max(len(k[j]) for k in groups) for j in range(len(cols))]
    out = []
    for k in order:
        head = "  ".join(x.ljust(w) for x, w in zip(k, widths)).rstrip()
        sub = render(groups[k], rest)
        if not sub:
            out.append(head)
            continue
        pad = " " * (sum(widths) + 2 * (len(widths) - 1))
        out.append(head.ljust(len(pad)) + " " + sub[0])
        out += [pad + " " + s for s in sub[1:]]
    return out


def sort_key(r, c):
    k = r.key.get(c)
    return (0, k) if k is not None else (1, r.text.get(c, ""))


def grid(rows, col, rest):
    """The rows drawn on the grid of col's frame, and the rows whose cell lies off it listed below; a table entry on
    col where the rows do not share one frame."""
    frames = {r.cell[col][2:] for r in rows if col in r.cell}
    if len(frames) != 1 or any(col not in r.cell for r in rows):
        return table(rows, (col,), rest)
    h, w = frames.pop()
    at, off = {}, []
    for r in rows:
        y, x = r.cell[col][:2]
        if 0 <= y < h and 0 <= x < w:
            at.setdefault((y, x), []).append(r)
        else:
            off.append(r)
    blocks = {p: (render(rs, rest) or ["#"]) for p, rs in at.items()}
    out = []
    if blocks:
        cw = max(len(s) for b in blocks.values() for s in b)
        compact = all(len(b) == 1 and " " not in b[0] for b in blocks.values())
        empty = ["."]
        if compact:
            out = [" ".join(blocks.get((y, x), empty)[0].ljust(cw) for x in range(w)).rstrip() for y in range(h)]
        else:
            ch = max(len(b) for b in blocks.values())
            rule = "┼".join("─" * cw for _ in range(w))
            for y in range(h):
                if y:
                    out.append(rule)
                cells = [blocks.get((y, x), empty) for x in range(w)]
                for i in range(ch):
                    out.append("│".join((b[i] if i < len(b) else "").ljust(cw) for b in cells).rstrip())
    else:
        out = [" ".join("." for _ in range(w)) for _ in range(h)]
    if off:
        out.append(f"off the {h}x{w} grid:")
        out += ["  " + x for x in table(off, (col,), rest)]
    return out
