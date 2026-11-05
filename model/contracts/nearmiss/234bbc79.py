import json
from collections import Counter
from pathlib import Path


def _bg(g):
    return Counter(c for r in g for c in r).most_common(1)[0][0]


def _copy(g):
    return [r[:] for r in g]


def _nonbg_cols(g, bg):
    return [j for j in range(len(g[0])) if any(r[j] != bg for r in g)]


def joints_to_bg(inp, out):
    # Joint color treated as background; no pieces are moved.
    bg = _bg(inp)
    return [[bg if c == 5 else c for c in r] for r in inp]


def compact_no_merge(inp, out):
    # Pieces are packed side by side with joints dropped, not merged into the chain.
    bg = _bg(inp)
    g = [[bg if c == 5 else c for c in r] for r in inp]
    cols = _nonbg_cols(g, bg)
    return [[r[j] for j in cols] for r in g]


def extra_column(inp, out):
    # Off-by-one width: one spare background column on the right.
    bg = _bg(out)
    return [r + [bg] for r in out]


def crop_last_column(inp, out):
    # Off-by-one width: last column cropped.
    return [r[:-1] for r in out]


def mirror_horizontal(inp, out):
    # Chain runs toward the opposite end.
    return [r[::-1] for r in out]


def flip_vertical(inp, out):
    # Chain is built with rows reversed.
    return out[::-1]


def swap_top_colors(inp, out):
    # Two most common piece colors exchanged.
    bg = _bg(out)
    cnt = Counter(c for r in out for c in r if c != bg).most_common(2)
    if len(cnt) < 2:
        return None
    a, b = cnt[0][0], cnt[1][0]
    m = {a: b, b: a}
    return [[m.get(c, c) for c in r] for r in out]


def drop_first_piece(inp, out):
    # The piece that should stay put is left out of the output.
    bg = _bg(out)
    g = _copy(out)
    cols = _nonbg_cols(g, bg)
    if not cols:
        return None
    first = g[[i for i in range(len(g)) if g[i][cols[0]] != bg][0]][cols[0]]
    for r in g:
        for j in range(len(r)):
            if r[j] == first:
                r[j] = bg
    return g


def drop_last_column_piece(inp, out):
    # The last piece's cells in the final column are erased.
    bg = _bg(out)
    g = _copy(out)
    cols = _nonbg_cols(g, bg)
    if not cols:
        return None
    for r in g:
        r[cols[-1]] = bg
    return g


def shift_down_wrap(inp, out):
    # Vertical offset: chain lands one row lower, wrapping around.
    return [out[-1]] + [r[:] for r in out[:-1]]


def shift_right_clip(inp, out):
    # Horizontal offset: chain starts one column too far right, last column clipped.
    bg = _bg(out)
    return [[bg] + r[:-1] for r in out]


def transpose_out(inp, out):
    # Chain assumed to run along the vertical axis.
    return [list(c) for c in zip(*out)]


ALTERNATIVES = [
    ("joint color just becomes background, no pieces move", joints_to_bg),
    ("pieces packed side by side, joints dropped instead of merged", compact_no_merge),
    ("output one column too wide", extra_column),
    ("output one column too narrow", crop_last_column),
    ("chain runs toward the opposite end (mirrored)", mirror_horizontal),
    ("rows in reverse order", flip_vertical),
    ("two most common piece colors swapped", swap_top_colors),
    ("fixed first piece omitted", drop_first_piece),
    ("last column of the chain erased", drop_last_column_piece),
    ("chain one row too low, wrapped", shift_down_wrap),
    ("chain one column too far right, clipped", shift_right_clip),
    ("chain assumed vertical (transposed)", transpose_out),
]


def _valid(g):
    return (
        isinstance(g, list) and len(g) > 0 and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/234bbc79.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
