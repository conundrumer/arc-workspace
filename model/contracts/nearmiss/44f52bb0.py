import json
from pathlib import Path


def _color(inp, out):
    return out[0][0]


def _other(c):
    return 7 if c == 1 else 1


def _fliplr(g):
    return [r[::-1] for r in g]


def _flipud(g):
    return g[::-1]


def _transpose(g):
    return [list(r) for r in zip(*g)]


def _rot180(g):
    return [r[::-1] for r in g[::-1]]


def _antitranspose(g):
    return _rot180(_transpose(g))


def _verdict(flag):
    return [[1 if flag else 7]]


def swapped_color(inp, out):
    return [[_other(_color(inp, out))]]


def always_one(inp, out):
    return [[1]]


def always_seven(inp, out):
    return [[7]]


def input_unchanged(inp, out):
    return [list(r) for r in inp]


def right_color_input_size(inp, out):
    c = _color(inp, out)
    return [[c] * len(inp[0]) for _ in inp]


def main_diagonal_only(inp, out):
    return _verdict(inp == _transpose(inp))


def antidiagonal_only(inp, out):
    return _verdict(inp == _antitranspose(inp))


def middle_row_palindrome(inp, out):
    row = inp[len(inp) // 2]
    return _verdict(row == row[::-1])


def column_centroid_centered(inp, out):
    cols = [c for r in inp for c, v in enumerate(r) if v == 2]
    if not cols:
        return None
    return _verdict(2 * sum(cols) == (len(inp[0]) - 1) * len(cols))


def at_least_five_twos(inp, out):
    return _verdict(sum(v == 2 for r in inp for v in r) >= 5)


def even_count_of_twos(inp, out):
    n = sum(v == 2 for r in inp for v in r)
    return _verdict(n % 2 == 0)


def empty_cell_output(inp, out):
    return [[0]]


def input_color_output(inp, out):
    return [[2]]


ALTERNATIVES = [
    ("outputs the opposite color (1 vs 7) of the true one", swapped_color),
    ("always outputs 1", always_one),
    ("always outputs 7", always_seven),
    ("returns the input grid unchanged", input_unchanged),
    ("right color but fills a grid of the input's size", right_color_input_size),
    ("tests only anti-diagonal mirror symmetry (1 if symmetric, else 7)", antidiagonal_only),
    ("tests only main-diagonal (transpose) symmetry", main_diagonal_only),
    ("tests only whether the middle row is a palindrome", middle_row_palindrome),
    ("1 if the 2 cells' mean column is the middle column, else 7", column_centroid_centered),
    ("1 if there are at least five 2 cells, else 7", at_least_five_twos),
    ("1 if the count of 2 cells is even, else 7", even_count_of_twos),
    ("outputs a single 2 cell (the input's object color)", input_color_output),
]


def _valid(g):
    return (isinstance(g, list) and len(g) > 0 and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(type(v) is int and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    path = Path(__file__).resolve().parents[3] / 'data/tasks/44f52bb0.json'
    train = json.loads(path.read_text())["train"]
    print(len(train), "train pairs")
    for desc, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, desc)
