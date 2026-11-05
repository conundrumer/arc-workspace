"""Near-miss rules for ARC task 8a6d367c."""
import json
from collections import Counter
from pathlib import Path


def _bg(inp):
    return Counter(v for r in inp for v in r).most_common(1)[0][0]


def _parts(inp, out):
    bg = _bg(inp)
    frame = out[0][0]
    inner = [r[1:-1] for r in out[1:-1]]
    fills = {v for r in inner for v in r if v != bg}
    fill = next(iter(fills)) if fills else None
    return bg, frame, fill, inner


def _wrap(frame, inner):
    w = len(inner[0])
    return [[frame] * (w + 2)] + [[frame] + list(r) + [frame] for r in inner] + [[frame] * (w + 2)]


def _locate(inp, out):
    h, w = len(out), len(out[0])
    for r in range(len(inp) - h + 1):
        for c in range(len(inp[0]) - w + 1):
            ok = all(inp[r][c + j] == out[0][j] and inp[r + h - 1][c + j] == out[h - 1][j] for j in range(w))
            ok = ok and all(inp[r + i][c] == out[i][0] and inp[r + i][c + w - 1] == out[i][w - 1] for i in range(h))
            if ok:
                return r, c
    return None


def crop_interior(inp, out):
    return [r[1:-1] for r in out[1:-1]]


def inverted(inp, out):
    bg, frame, fill, inner = _parts(inp, out)
    sw = {bg: fill, fill: bg}
    return _wrap(frame, [[sw.get(v, v) for v in r] for r in inner])


def transposed(inp, out):
    bg, frame, fill, inner = _parts(inp, out)
    return _wrap(frame, [list(r) for r in zip(*inner)])


def hflip(inp, out):
    bg, frame, fill, inner = _parts(inp, out)
    return _wrap(frame, [r[::-1] for r in inner])


def empty_inside(inp, out):
    bg, frame, fill, inner = _parts(inp, out)
    return _wrap(frame, [[bg] * len(inner[0]) for _ in inner])


def full_inside(inp, out):
    bg, frame, fill, inner = _parts(inp, out)
    return _wrap(frame, [[fill] * len(inner[0]) for _ in inner])


def raw_crop(inp, out):
    pos = _locate(inp, out)
    if pos is None:
        return None
    r, c = pos
    return [row[c:c + len(out[0])] for row in inp[r:r + len(out)]]


def padded_crop(inp, out):
    pos = _locate(inp, out)
    if pos is None:
        return None
    r, c = pos
    r0, c0 = max(r - 1, 0), max(c - 1, 0)
    r1, c1 = min(r + len(out) + 1, len(inp)), min(c + len(out[0]) + 1, len(inp[0]))
    return [row[c0:c1] for row in inp[r0:r1]]


def wrong_color(inp, out):
    bg, frame, fill, inner = _parts(inp, out)
    cnt = Counter(v for r in inp for v in r if v not in (bg, frame, fill))
    if not cnt:
        return None
    other = cnt.most_common(1)[0][0]
    return [[other if v == fill else v for v in r] for r in out]


def frame_as_fill(inp, out):
    bg, frame, fill, inner = _parts(inp, out)
    return _wrap(fill, inner)


def _block(n, rows):
    for d in range(1, n + 1):
        if n % d == 0 and all(rows[i] == rows[i - i % d] for i in range(n)):
            return d
    return n


def first_block_row_repeated(inp, out):
    bg, frame, fill, inner = _parts(inp, out)
    d = _block(len(inner), inner)
    return _wrap(frame, [inner[i % d] for i in range(len(inner))])


def roll_block_rows(inp, out):
    bg, frame, fill, inner = _parts(inp, out)
    n = len(inner)
    d = _block(n, inner)
    return _wrap(frame, [inner[(i + d) % n] for i in range(n)])


ALTERNATIVES = [
    ("crop the frame's inside only, dropping the frame border", crop_interior),
    ("swap fill color and background inside the frame", inverted),
    ("pattern transposed before filling the frame", transposed),
    ("pattern mirrored left to right", hflip),
    ("frame left empty (no fill drawn)", empty_inside),
    ("frame interior filled completely with the fill color", full_inside),
    ("raw crop of the frame region from the input, no pattern applied", raw_crop),
    ("crop includes one extra cell of margin around the frame", padded_crop),
    ("fill drawn in another ink color instead of the interior's ink color", wrong_color),
    ("frame border drawn in the fill color", frame_as_fill),
    ("only the first block row of the pattern, repeated down", first_block_row_repeated),
    ("pattern block rows shifted by one block (cyclic)", roll_block_rows),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) and r for r in g)
            and len({len(r) for r in g}) == 1
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/8a6d367c.json").read_text())
    train = task["train"]
    print(f"{len(ALTERNATIVES)} readings, {len(train)} train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(f"{n}/{len(train)}  {desc}")
