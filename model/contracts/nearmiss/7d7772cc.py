import json
from collections import Counter
from pathlib import Path


def parse(inp):
    H, W = len(inp), len(inp[0])
    cnt = Counter(v for row in inp for v in row)
    bg = cnt.most_common(1)[0][0]
    fence = None
    for c in cnt:
        if c == bg:
            continue
        if any(all(inp[r][x] == c for x in range(W)) for r in range(H)) or any(
            all(inp[y][x] == c for y in range(H)) for x in range(W)
        ):
            fence = c
            break
    cells = [(r, c) for r in range(H) for c in range(W) if inp[r][c] == fence]
    r0 = min(r for r, _ in cells)
    r1 = max(r for r, _ in cells)
    c0 = min(c for _, c in cells)
    c1 = max(c for _, c in cells)
    margins = {(-1, 0): r0, (1, 0): H - 1 - r1, (0, -1): c0, (0, 1): W - 1 - c1}
    d = max(margins, key=lambda k: margins[k])
    marks = []
    for r in range(H):
        for c in range(W):
            if r0 <= r <= r1 and c0 <= c <= c1:
                continue
            if inp[r][c] == bg:
                continue
            col = inp[r][c]
            if d == (-1, 0):
                s, g = (r0, c), (r0 + 1, c)
            elif d == (1, 0):
                s, g = (r1, c), (r1 - 1, c)
            elif d == (0, 1):
                s, g = (r, c1), (r, c1 - 1)
            else:
                s, g = (r, c0), (r, c0 + 1)
            toward = (s[0] + d[0], s[1] + d[1])
            if d == (-1, 0):
                away = (0, c)
            elif d == (1, 0):
                away = (H - 1, c)
            elif d == (0, 1):
                away = (r, W - 1)
            else:
                away = (r, 0)
            marks.append(
                dict(pos=(r, c), col=col, s=s, g=inp[g[0]][g[1]], toward=toward,
                     away=away, match=inp[g[0]][g[1]] == col)
            )
    return dict(H=H, W=W, bg=bg, fence=fence, box=(r0, r1, c0, c1), d=d, marks=marks)


def render(inp, info, place, keep=()):
    """place: list of (pos, color); keep: marks left at their original place."""
    g = [row[:] for row in inp]
    for m in info["marks"]:
        r, c = m["pos"]
        g[r][c] = info["bg"]
    for pos, col in place:
        g[pos[0]][pos[1]] = col
    return g


def shift(pos, d, k):
    return (pos[0] + d[0] * k, pos[1] + d[1] * k)


def clamp(info, pos):
    return (min(max(pos[0], 0), info["H"] - 1), min(max(pos[1], 0), info["W"] - 1))


def true_model(inp):
    info = parse(inp)
    place = [((m["toward"] if m["match"] else m["away"]), m["col"]) for m in info["marks"]]
    return render(inp, info, place)


def all_toward(inp, out):
    info = parse(inp)
    return render(inp, info, [(m["toward"], m["col"]) for m in info["marks"]])


def all_away(inp, out):
    info = parse(inp)
    return render(inp, info, [(m["away"], m["col"]) for m in info["marks"]])


def inverted(inp, out):
    info = parse(inp)
    return render(inp, info, [((m["away"] if m["match"] else m["toward"]), m["col"]) for m in info["marks"]])


def toward_gap(inp, out):
    info = parse(inp)
    d = info["d"]
    return render(inp, info, [((shift(m["toward"], d, 1) if m["match"] else m["away"]), m["col"]) for m in info["marks"]])


def away_short(inp, out):
    info = parse(inp)
    d = info["d"]
    return render(inp, info, [((m["toward"] if m["match"] else shift(m["away"], d, -1)), m["col"]) for m in info["marks"]])


def copy_not_move(inp, out):
    info = parse(inp)
    g = [row[:] for row in out]
    for m in info["marks"]:
        g[m["pos"][0]][m["pos"][1]] = m["col"]
    return g


def unmatched_stay(inp, out):
    info = parse(inp)
    g = render(inp, info, [])
    for m in info["marks"]:
        if m["match"]:
            g[m["toward"][0]][m["toward"][1]] = m["col"]
        else:
            g[m["pos"][0]][m["pos"][1]] = m["col"]
    return g


def matched_stay(inp, out):
    info = parse(inp)
    g = render(inp, info, [])
    for m in info["marks"]:
        if m["match"]:
            g[m["pos"][0]][m["pos"][1]] = m["col"]
        else:
            g[m["away"][0]][m["away"][1]] = m["col"]
    return g


def perpendicular(inp, out):
    # marks slide along the fence instead of toward or away from it
    info = parse(inp)
    d = info["d"]
    perp = (d[1], d[0])
    place = []
    for m in info["marks"]:
        step = perp if m["match"] else (-perp[0], -perp[1])
        r, c = m["pos"]
        if step[0]:
            e = (0 if step[0] < 0 else info["H"] - 1, c)
        else:
            e = (r, 0 if step[1] < 0 else info["W"] - 1)
        place.append((e, m["col"]))
    return render(inp, info, place)


def ignore_fence(inp, out):
    # matched marks slide to the grid edge through the fence
    info = parse(inp)
    d = info["d"]
    place = []
    for m in info["marks"]:
        if m["match"]:
            r, c = m["pos"]
            nd = (-d[0], -d[1])
            e = (0 if nd[0] < 0 else info["H"] - 1, c) if nd[0] else (r, 0 if nd[1] < 0 else info["W"] - 1)
            place.append((e, m["col"]))
        else:
            place.append((m["away"], m["col"]))
    return render(inp, info, place)


def recolor_to_inside(inp, out):
    info = parse(inp)
    return render(inp, info, [((m["toward"] if m["match"] else m["away"]), m["g"]) for m in info["marks"]])


ALTERNATIVES = [
    ("every mark slides to the fence, whether or not it matches the cell inside", all_toward),
    ("every mark slides away from the fence to the grid edge", all_away),
    ("match and mismatch swapped: matching marks go away, others go to the fence", inverted),
    ("matching marks stop one cell short of the fence", toward_gap),
    ("mismatching marks stop one cell short of the grid edge", away_short),
    ("marks are copied to their destination and also stay at the start", copy_not_move),
    ("mismatching marks do not move", unmatched_stay),
    ("matching marks do not move", matched_stay),
    ("marks slide along the fence axis instead of across it", perpendicular),
    ("matching marks pass through the fence and go to the opposite grid edge", ignore_fence),
    ("moved marks take the color of the cell inside the pen", recolor_to_inside),
]


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/7d7772cc.json").read_text())
    pairs = task["train"]
    print("pairs", len(pairs))
    print("true model reproduces output:", [true_model(p["input"]) == p["output"] for p in pairs])

    def valid(g):
        return (
            isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and all(len(r) == len(g[0]) for r in g)
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
        )

    for desc, f in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = f(p["input"], p["output"])
            if g is not None and valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
