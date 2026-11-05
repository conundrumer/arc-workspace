import json
from pathlib import Path

MARK, BLOCK = 2, 5


def _marks(inp):
    h, w = len(inp), len(inp[0])
    return [(r, c) for r in range(h) for c in range(w) if inp[r][c] == MARK]


def _walk(inp, side=1, jog=1, early=0, through=False, back=False, stop_at_block=False):
    """Paths walked upward from each bottom-edge mark.

    side: sidestep direction (+1 right, -1 left); jog: sidestep width;
    early: sidestep this many rows before the blocker; through: ignore blockers;
    back: after passing the blocker, return to the original column;
    stop_at_block: end the walk at a blocker.
    Returns a list of (path cells, deflected flag).
    """
    h, w = len(inp), len(inp[0])
    result = []
    for (r0, c0) in _marks(inp):
        r, c = r0, c0
        cells = [(r, c)]
        deflected = False
        pending_back = None
        while r - 1 >= 0:
            if pending_back is not None and r - 1 < pending_back[0]:
                pass
            blocked = (not through) and inp[r - 1][c] == BLOCK
            if early and not through and not blocked and r - 1 - early >= 0 \
                    and inp[r - 1 - early][c] == BLOCK:
                blocked = True
            if blocked:
                if stop_at_block:
                    break
                nc = c + side * jog
                if not (0 <= nc < w):
                    break
                deflected = True
                c = nc
                cells.append((r, c))
                if back:
                    pending_back = (r - 2, c0)
                continue
            r -= 1
            cells.append((r, c))
            if pending_back is not None and r == pending_back[0] + 0 and False:
                pass
        result.append((cells, deflected))
    return result


def _render(inp, walks, keep_blocks=True):
    g = [row[:] for row in inp]
    for cells, _ in walks:
        for (r, c) in cells:
            if g[r][c] != BLOCK or not keep_blocks:
                g[r][c] = MARK
    return g


def deflect_left(inp, out):
    return _render(inp, _walk(inp, side=-1))


def stop_at_block(inp, out):
    return _render(inp, _walk(inp, stop_at_block=True))


def pass_through_overwrite(inp, out):
    return _render(inp, _walk(inp, through=True), keep_blocks=False)


def pass_through_keep(inp, out):
    return _render(inp, _walk(inp, through=True))


def jog_two(inp, out):
    return _render(inp, _walk(inp, jog=2))


def sidestep_only(inp, out):
    walks = [(cells[:], d) for cells, d in _walk(inp)]
    trimmed = []
    for cells, d in walks:
        if d:
            # keep the original column up to the sidestep cell, drop the rest
            for i in range(1, len(cells)):
                if cells[i][0] == cells[i - 1][0]:
                    cells = cells[: i + 1]
                    break
        trimmed.append((cells, d))
    return _render(inp, trimmed)


def blocker_removed(inp, out):
    g = [row[:] for row in out]
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == BLOCK:
                g[r][c] = 0
    return g


def blocks_also_emit(inp, out):
    g = [row[:] for row in out]
    for r, row in enumerate(inp):
        for c, v in enumerate(row):
            if v == BLOCK:
                for rr in range(r):
                    g[rr][c] = MARK
    return g


def only_deflected_lines(inp, out):
    walks = [(cells, d) for cells, d in _walk(inp) if d]
    return _render(inp, walks)


def early_deflect(inp, out):
    return _render(inp, _walk(inp, early=1))


def rejoin_column(inp, out):
    """After sidestepping, the line returns to its original column one row later."""
    h, w = len(inp), len(inp[0])
    g = [row[:] for row in inp]
    for (r0, c0) in _marks(inp):
        r, c = r0, c0
        g[r][c] = MARK
        stage = 0
        while r - 1 >= 0:
            if stage == 0 and inp[r - 1][c] == BLOCK:
                if c + 1 >= w:
                    break
                c += 1
                g[r][c] = MARK
                stage = 1
                continue
            if stage == 1 and inp[r - 1][c0] != BLOCK and inp[r][c0] != BLOCK \
                    and r < h and inp[r - 1][c - 1] != BLOCK and False:
                pass
            r -= 1
            g[r][c] = MARK
            if stage == 1 and inp[r][c0] == BLOCK:
                stage = 2  # beside the blocker
            elif stage == 2:
                # one row past the blocker: step back to the original column
                c = c0
                g[r][c] = MARK
                stage = 3
    return g


def unchanged(inp, out):
    return [row[:] for row in inp]


ALTERNATIVES = [
    ("sidestep goes to the left instead of the right", deflect_left),
    ("line stops below the blocker with no sidestep", stop_at_block),
    ("line ignores blockers and overwrites them", pass_through_overwrite),
    ("line ignores blockers but leaves the blocker cells alone", pass_through_keep),
    ("sidestep is two cells wide", jog_two),
    ("line ends right after the single sidestep cell", sidestep_only),
    ("blockers are erased in the output", blocker_removed),
    ("blockers also emit upward lines of the mark color", blocks_also_emit),
    ("only lines that meet a blocker are drawn", only_deflected_lines),
    ("sidestep happens one row before the blocker", early_deflect),
    ("line returns to its original column after passing the blocker", rejoin_column),
    ("output equals the input", unchanged),
]


def _valid(g):
    return (
        isinstance(g, list) and g and all(isinstance(r, list) for r in g)
        and len({len(r) for r in g}) == 1 and len(g[0]) > 0
        and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r)
    )


if __name__ == "__main__":
    task = json.loads((Path(__file__).resolve().parents[3] / "data/tasks/d9f24cd1.json").read_text())
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
