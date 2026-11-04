from pathlib import Path
import json, os
from collections import Counter

def cp(g): return [r[:] for r in g]

def new_cells(inp, out):
    return {(r, c) for r in range(len(out)) for c in range(len(out[0]))
            if out[r][c] == 8 and inp[r][c] != 8}

def old_cells(inp):
    return {(r, c) for r in range(len(inp)) for c in range(len(inp[0])) if inp[r][c] == 8}

def comps(cells):
    cells = set(cells); res = []
    while cells:
        s = cells.pop(); comp = {s}; st = [s]
        while st:
            r, c = st.pop()
            for dr in (-1, 0, 1):
                for dc in (-1, 0, 1):
                    n = (r + dr, c + dc)
                    if n in cells:
                        cells.discard(n); comp.add(n); st.append(n)
        res.append(comp)
    return sorted(res, key=lambda k: min(k))

def revert(inp, out, cells):
    g = cp(out)
    for r, c in cells: g[r][c] = inp[r][c]
    return g

def drop_last_stamp(inp, out):
    cs = comps(new_cells(inp, out))
    return revert(inp, out, cs[-1]) if cs else None

def drop_first_stamp(inp, out):
    cs = comps(new_cells(inp, out))
    return revert(inp, out, cs[0]) if cs else None

def stamp_wrong_color(inp, out):
    g = cp(out)
    for r, c in new_cells(inp, out): g[r][c] = 1
    return g

def bbox_fill(inp, out):
    cs = comps(new_cells(inp, out))
    g = cp(out)
    for k in cs:
        rs = [p[0] for p in k]; cc = [p[1] for p in k]
        for r in range(min(rs), max(rs) + 1):
            for c in range(min(cc), max(cc) + 1): g[r][c] = 8
    return g

def top_half_only(inp, out):
    g = cp(out); h = len(out)
    for r, c in new_cells(inp, out):
        if r >= h // 2: g[r][c] = inp[r][c]
    return g

def shifted_stamp(inp, out):
    g = cp(inp); w = len(out[0])
    for r, c in new_cells(inp, out):
        if c + 1 < w: g[r][c + 1] = 8
    return g

def erase_original(inp, out):
    g = cp(out); h = len(out); w = len(out[0])
    for r, c in old_cells(inp):
        nb = Counter(inp[r + dr][c + dc] for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                     if 0 <= r + dr < h and 0 <= c + dc < w and inp[r + dr][c + dc] != 8)
        g[r][c] = nb.most_common(1)[0][0]
    return g

def same_rows_only(inp, out):
    rows = {r for r, c in old_cells(inp)}
    g = cp(out)
    for r, c in new_cells(inp, out):
        if r not in rows: g[r][c] = inp[r][c]
    return g

def drop_last_row(inp, out):
    return [r[:] for r in out[:-1]]

def mirrored_stamp(inp, out):
    g = cp(inp); w = len(out[0])
    for r, c in new_cells(inp, out): g[r][w - 1 - c] = 8
    for r, c in old_cells(inp): g[r][c] = 8
    return g

def stamp_without_original_footprint_on_blob(inp, out):
    # stamps only the blobs of exactly one component, painting all of them with 8 including the unmarked rest of tile row
    cs = comps(new_cells(inp, out))
    if not cs: return None
    g = cp(out)
    for k in cs:
        for r in {p[0] for p in k}:
            for c in range(len(out[0])):
                if inp[r][c] == inp[next(iter(k))[0]][next(iter(k))[1]]: g[r][c] = 8
    return g

ALTERNATIVES = [
    ("copy the pattern to no other blob (input unchanged)", lambda i, o: cp(i)),
    ("last stamped blob is left unfilled", drop_last_stamp),
    ("first stamped blob is left unfilled", drop_first_stamp),
    ("stamped cells painted with color 1 instead of the mark color", stamp_wrong_color),
    ("whole bounding box of each stamp filled with the mark color", bbox_fill),
    ("only the top half of the grid gets stamps", top_half_only),
    ("stamps offset one column to the right", shifted_stamp),
    ("original mark erased to its neighbour color", erase_original),
    ("only stamps in rows of the original mark kept", same_rows_only),
    ("output one row shorter than the input", drop_last_row),
    ("stamps mirrored left to right", mirrored_stamp),
    ("every same-colored cell in the stamp rows painted", stamp_without_original_footprint_on_blob),
]

if __name__ == "__main__":
    p = os.path.join(str(Path(__file__).resolve().parents[3] / 'data/tasks/4ff4c9da.json'))
    train = json.load(open(p))["train"]
    for desc, f in ALTERNATIVES:
        n = 0
        for pr in train:
            try:
                g = f(pr["input"], pr["output"])
            except Exception as e:
                print("  error", e); g = None
            ok = (g is not None and g and all(len(r) == len(g[0]) for r in g)
                  and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
                  and g != pr["output"])
            n += ok
        print(n, desc)
    print(len(ALTERNATIVES), "readings,", len(train), "pairs")
