import json
from collections import Counter
from pathlib import Path


def _cells(out):
    """Output as a list of cell colors along its long axis, and whether it is a column."""
    vertical = len(out[0]) == 1
    seq = [r[0] for r in out] if vertical else list(out[0])
    return seq, vertical


def _build(seq, vertical):
    if not seq:
        return None
    return [[c] for c in seq] if vertical else [list(seq)]


def _runs(seq):
    runs = []
    for c in seq:
        if runs and runs[-1][0] == c:
            runs[-1][1] += 1
        else:
            runs.append([c, 1])
    return runs


def _input_seq(inp, out):
    """Input sequence along the output's long axis, one color per line."""
    vertical = len(out[0]) == 1
    seq = [r[0] for r in inp] if vertical else list(inp[0])
    return seq, vertical


def transposed(inp, out):
    return [list(r) for r in zip(*out)]


def unchanged(inp, out):
    return [list(r) for r in inp]


def no_sequence_collapse(inp, out):
    # Collapse only the constant axis; keep every line of the sequence axis.
    seq, vertical = _input_seq(inp, out)
    return _build(seq, vertical)


def drop_last(inp, out):
    seq, vertical = _cells(out)
    return _build(seq[:-1], vertical)


def reversed_order(inp, out):
    seq, vertical = _cells(out)
    return _build(seq[::-1], vertical)


def global_unique(inp, out):
    seq, vertical = _input_seq(inp, out)
    seen = []
    for c in seq:
        if c not in seen:
            seen.append(c)
    return _build(seen, vertical)


def sorted_colors(inp, out):
    seq, vertical = _cells(out)
    return _build(sorted(set(seq)), vertical)


def collapse_only_long_runs(inp, out):
    # Merge a run only when it has 3 or more lines.
    seq, vertical = _input_seq(inp, out)
    res = []
    for c, n in _runs(seq):
        res.extend([c] if n >= 3 else [c] * n)
    return _build(res, vertical)


def majority_fill(inp, out):
    counts = Counter(c for r in inp for c in r)
    top = max(counts.values())
    color = min(c for c, n in counts.items() if n == top)
    return [[color for _ in r] for r in out]


def rolled_by_one(inp, out):
    seq, vertical = _cells(out)
    return _build(seq[-1:] + seq[:-1], vertical)


ALTERNATIVES = [
    ("collapse gives the transpose: cells laid out along the wrong axis", transposed),
    ("no collapse at all: output is the input", unchanged),
    ("collapse only the constant axis, keep every line of the sequence axis", no_sequence_collapse),
    ("drop the last run (off-by-one in the cell count)", drop_last),
    ("runs listed in reverse order", reversed_order),
    ("merge equal colors anywhere in the sequence, not only adjacent lines", global_unique),
    ("distinct colors sorted ascending instead of in input order", sorted_colors),
    ("merge a run only when it has 3 or more lines", collapse_only_long_runs),
    ("every output cell takes the most common input color", majority_fill),
    ("run order rotated by one cell", rolled_by_one),
]


def _valid(g):
    return (
        isinstance(g, list)
        and len(g) > 0
        and all(isinstance(r, list) and len(r) == len(g[0]) and len(r) > 0 for r in g)
        and all(isinstance(c, int) and 0 <= c <= 9 for r in g for c in r)
    )


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / "data/tasks/746b3537.json"))
    pairs = task["train"]
    print(len(ALTERNATIVES), "readings,", len(pairs), "pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in pairs:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, "/", len(pairs), desc)
