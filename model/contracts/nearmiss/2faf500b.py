import json
from pathlib import Path

BG = 0
MARK = 6


def _comps(g):
    h, w = len(g), len(g[0])
    seen = set()
    res = []
    for r in range(h):
        for c in range(w):
            if g[r][c] != BG and (r, c) not in seen:
                st = [(r, c)]
                seen.add((r, c))
                comp = []
                while st:
                    y, x = st.pop()
                    comp.append((y, x))
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and g[ny][nx] != BG and (ny, nx) not in seen:
                            seen.add((ny, nx))
                            st.append((ny, nx))
                res.append(comp)
    return res


def _axis(g, comp):
    """'row' if every row of the shape holds a mark (cut runs vertically, halves split left/right),
    'col' if every column holds a mark. None if neither."""
    rows = {y for y, x in comp}
    cols = {x for y, x in comp}
    mr = {y for y, x in comp if g[y][x] == MARK}
    mc = {x for y, x in comp if g[y][x] == MARK}
    if rows <= mr:
        return "row"
    if cols <= mc:
        return "col"
    return None


def _split(inp, shift_lo=-1, shift_hi=1, keep_mark=None, fill_mark=False, swap_axis=False,
           midline=False, only=None, whole=None):
    h, w = len(inp), len(inp[0])
    out = [[BG] * w for _ in range(h)]
    comps = _comps(inp)
    if only == "largest":
        big = max(comps, key=len)
    for comp in comps:
        ax = _axis(inp, comp)
        if only == "largest" and comp is not big:
            for y, x in comp:
                out[y][x] = inp[y][x]
            continue
        if ax is None:
            for y, x in comp:
                out[y][x] = inp[y][x]
            continue
        if swap_axis:
            ax = "col" if ax == "row" else "row"
        ys = [y for y, x in comp]
        xs = [x for y, x in comp]
        cell_set = set(comp)
        if ax == "row":
            lines = {}
            for y, x in comp:
                lines.setdefault(y, []).append(x)
        else:
            lines = {}
            for y, x in comp:
                lines.setdefault(x, []).append(y)
        for key, vals in lines.items():
            marks = [v for v in vals if (inp[key][v] if ax == "row" else inp[v][key]) == MARK]
            if midline or not marks:
                m = (min(vals) + max(vals)) / 2.0
            else:
                m = sum(marks) / len(marks)
            for v in vals:
                y, x = (key, v) if ax == "row" else (v, key)
                col = inp[y][x]
                if col == MARK and not midline:
                    if keep_mark:
                        out[y][x] = MARK
                    elif fill_mark:
                        out[y][x] = 9
                    continue
                if whole is not None:
                    d = whole
                elif v < m:
                    d = shift_lo
                elif v > m:
                    d = shift_hi
                else:
                    d = 0
                ny, nx = (y, x + d) if ax == "row" else (y + d, x)
                if 0 <= ny < h and 0 <= nx < w:
                    out[ny][nx] = col
    return out


def true_rule(inp, out):
    return _split(inp)


def only_low_moves(inp, out):
    return _split(inp, -1, 0)


def only_high_moves(inp, out):
    return _split(inp, 0, 1)


def inward(inp, out):
    return _split(inp, 1, -1)


def move_two(inp, out):
    return _split(inp, -2, 2)


def keep_marks(inp, out):
    return _split(inp, keep_mark=True)


def fill_marks(inp, out):
    return _split(inp, fill_mark=True)


def wrong_axis(inp, out):
    return _split(inp, swap_axis=True)


def midline_cut(inp, out):
    return _split(inp, midline=True)


def largest_only(inp, out):
    return _split(inp, only="largest")


def shift_whole(inp, out):
    return _split(inp, whole=1)


def marks_erased_no_move(inp, out):
    return [[BG if v == MARK else v for v in row] for row in inp]


def mark_as_bg_split_dir_flipped(inp, out):
    # halves move apart along the cut line (perpendicular to the right direction), swapped axis, by 1
    return _split(inp, swap_axis=True, midline=True)


ALTERNATIVES = [
    ("Only the left/upper half moves away; the other half stays", only_low_moves),
    ("Only the right/lower half moves away; the other half stays", only_high_moves),
    ("Halves move toward each other by one cell instead of apart", inward),
    ("Halves move apart by two cells instead of one", move_two),
    ("Marker cells stay as 6 after the split", keep_marks),
    ("Marker cells become 9 after the split", fill_marks),
    ("Shape is split along the wrong axis (rows vs columns swapped)", wrong_axis),
    ("Shape is split at its bounding-box middle instead of at the 6 cells", midline_cut),
    ("Only the largest shape is split; other shapes left as in input", largest_only),
    ("Whole shape shifts one cell right/down with the 6s erased, no split", shift_whole),
    ("Only the 6 markers are erased; nothing moves", marks_erased_no_move),
    ("Split at bbox middle along the wrong axis", mark_as_bg_split_dir_flipped),
]


def _valid(g, ref):
    if not isinstance(g, list) or not g or not all(isinstance(r, list) for r in g):
        return False
    if len({len(r) for r in g}) != 1 or not g[0]:
        return False
    if not all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r):
        return False
    return g != ref


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/2faf500b.json"))
    pairs = task["train"]
    ok = sum(true_rule(p["input"], p["output"]) == p["output"] for p in pairs)
    print(f"sanity: true rule reproduces {ok}/{len(pairs)} outputs")
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g, p["output"]):
                n += 1
        print(f"{n}/{len(pairs)}  {desc}")
