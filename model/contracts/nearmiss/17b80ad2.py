"""Near-miss rules for ARC task 17b80ad2."""
import json
from pathlib import Path


def _copy(g):
    return [list(r) for r in g]


def _marks(inp):
    """Columns with a mark in the bottom row, with that row's color."""
    return [(c, v) for c, v in enumerate(inp[-1]) if v != 0]


def _inks(inp, c):
    return [r for r in range(len(inp) - 1) if inp[r][c] != 0]


def _same(g, out):
    return g == out


def _ret(g, out):
    return None if g == out else g


def _flow_up(inp, cols=None, mark_fill=True, top_fill=True):
    """The rule: ink paints from itself up to the next ink; mark fills below the last ink."""
    H, W = len(inp), len(inp[0])
    g = _copy(inp)
    cs = cols if cols is not None else [c for c, _ in _marks(inp)]
    for c in cs:
        mark = inp[-1][c]
        prev = -1
        for r in _inks(inp, c):
            if not (prev == -1 and not top_fill):
                for k in range(prev + 1, r + 1):
                    g[k][c] = inp[r][c]
            prev = r
        if mark_fill:
            for k in range(prev + 1, H):
                g[k][c] = mark
    return g


def down_flow(inp, out):
    """Ink flows toward the mark edge (down) until the next ink."""
    g = _copy(inp)
    H = len(inp)
    for c, _ in _marks(inp):
        ink = _inks(inp, c) + [H - 1]
        for a, b in zip(ink, ink[1:]):
            for k in range(a, b):
                g[k][c] = inp[a][c]
    return _ret(g, out)


def lower_wins(inp, out):
    """Each ink paints up to the top edge and a lower ink overwrites an upper one."""
    H = len(inp)
    g = _copy(inp)
    for c, mark in _marks(inp):
        ink = _inks(inp, c)
        for r in ink:
            for k in range(0, r + 1):
                g[k][c] = inp[r][c]
        last = ink[-1] if ink else -1
        for k in range(last + 1, H):
            g[k][c] = mark
    return _ret(g, out)


def no_mark_fill(inp, out):
    """Mark gap below the last ink is left as background."""
    return _ret(_flow_up(inp, mark_fill=False), out)


def mark_fill_last_ink(inp, out):
    """Last ink extends to the bottom edge instead of the mark color filling the gap."""
    H = len(inp)
    g = _flow_up(inp)
    for c, _ in _marks(inp):
        ink = _inks(inp, c)
        if ink:
            for k in range(ink[-1] + 1, H - 1):
                g[k][c] = inp[ink[-1]][c]
    return _ret(g, out)


def all_columns(inp, out):
    """Every column with ink flows up, not only columns that have a mark."""
    H, W = len(inp), len(inp[0])
    g = _flow_up(inp)
    for c in range(W):
        if inp[-1][c] != 0:
            continue
        prev = -1
        for r in _inks(inp, c):
            for k in range(prev + 1, r + 1):
                g[k][c] = inp[r][c]
            prev = r
    return _ret(g, out)


def snap_down_with_top_fill(inp, out):
    """Each ink color extends down to the row before the next ink; rows above the first ink take its color."""
    H = len(inp)
    g = _copy(inp)
    for c, _ in _marks(inp):
        ink = _inks(inp, c)
        if not ink:
            continue
        for k in range(0, ink[0]):
            g[k][c] = inp[ink[0]][c]
        bounds = ink + [H - 1]
        for a, b in zip(bounds, bounds[1:]):
            for k in range(a, b):
                g[k][c] = inp[a][c]
    return _ret(g, out)


def off_by_one_mark_fill(inp, out):
    """The mark fill starts one row too low: the last ink also covers the row below it."""
    H = len(inp)
    g = _flow_up(inp)
    for c, _ in _marks(inp):
        ink = _inks(inp, c)
        if ink and ink[-1] + 1 < H - 1:
            g[ink[-1] + 1][c] = inp[ink[-1]][c]
    return _ret(g, out)


def first_marked_column_only(inp, out):
    """Only the left-most marked column is transformed."""
    ms = _marks(inp)
    if len(ms) < 2:
        return None
    return _ret(_flow_up(inp, cols=[ms[0][0]]), out)


def no_top_fill(inp, out):
    """The topmost ink does not paint upward; cells above it stay background."""
    return _ret(_flow_up(inp, top_fill=False), out)


def horizontal_flow(inp, out):
    """Wrong axis: ink in each row flows left to the previous ink in that row."""
    H, W = len(inp), len(inp[0])
    g = _copy(inp)
    for r in range(H - 1):
        prev = -1
        for c in range(W):
            if inp[r][c] != 0:
                for k in range(prev + 1, c + 1):
                    g[r][k] = inp[r][c]
                prev = c
    return _ret(g, out)


def unchanged(inp, out):
    """Output equals the input."""
    return _ret(_copy(inp), out)


ALTERNATIVES = [
    ("ink flows down toward the mark edge instead of up", down_flow),
    ("a lower ink overwrites an upper ink when painting up to the top", lower_wins),
    ("mark gap below the last ink is left as background", no_mark_fill),
    ("last ink extends to the bottom edge instead of the mark color filling", mark_fill_last_ink),
    ("every column with ink flows up, not only marked columns", all_columns),
    ("each ink color extends down to the next ink, top rows take first ink color", snap_down_with_top_fill),
    ("mark fill starts one row too low", off_by_one_mark_fill),
    ("only the left-most marked column is transformed", first_marked_column_only),
    ("topmost ink does not paint upward", no_top_fill),
    ("ink flows left along rows instead of up along columns", horizontal_flow),
    ("output equals the input", unchanged),
]


def _valid(g, out):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != out


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/17b80ad2.json").read_text())
    train = task["train"]
    # sanity: base rule reproduces every train output
    assert all(_flow_up(p["input"]) == p["output"] for p in train), "base rule mismatch"
    print(f"{len(ALTERNATIVES)} readings, {len(train)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(train)}  {desc}")
