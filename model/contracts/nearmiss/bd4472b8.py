import json
from pathlib import Path


def _parts(inp):
    """Header colors, number of header rows (1), body start row, width, height."""
    hdr = list(inp[0])
    return hdr, 2, len(inp[0]), len(inp)


def _body(inp, color_at, stop=None):
    hdr, start, w, h = _parts(inp)
    g = [list(r) for r in inp]
    end = h if stop is None else stop
    for r in range(start, end):
        c = color_at(hdr, r - start)
        g[r] = [c] * w
    return g


def reversed_order(inp, out):
    return _body(inp, lambda h, i: h[::-1][i % len(h)])


def column_stripes(inp, out):
    hdr, start, w, h = _parts(inp)
    g = [list(r) for r in inp]
    for r in range(start, h):
        g[r] = list(hdr)
    return g


def one_cycle_only(inp, out):
    hdr, start, w, h = _parts(inp)
    return _body(inp, lambda hh, i: hh[i], stop=min(h, start + len(hdr)))


def start_at_separator(inp, out):
    hdr, start, w, h = _parts(inp)
    g = [list(r) for r in inp]
    for r in range(1, h):
        g[r] = [hdr[(r - 1) % len(hdr)]] * w
    return g


def shifted_start(inp, out):
    return _body(inp, lambda h, i: h[(i + 1) % len(h)])


def first_color_only(inp, out):
    return _body(inp, lambda h, i: h[0])


def double_height_stripes(inp, out):
    return _body(inp, lambda h, i: h[(i // 2) % len(h)])


def sorted_order(inp, out):
    return _body(inp, lambda h, i: sorted(h)[i % len(h)])


def clamp_last_color(inp, out):
    return _body(inp, lambda h, i: h[min(i, len(h) - 1)])


def separator_color_body(inp, out):
    return _body(inp, lambda h, i: 5)


def drop_separator(inp, out):
    hdr, start, w, h = _parts(inp)
    g = _body(inp, lambda hh, i: hh[i % len(hh)])
    return [g[0]] + g[2:]


def stop_one_short(inp, out):
    hdr, start, w, h = _parts(inp)
    return _body(inp, lambda hh, i: hh[i % len(hh)], stop=h - 1)


ALTERNATIVES = [
    ("body stripes cycle through the header colors in reverse order", reversed_order),
    ("each body row is the header row copied down (vertical stripes, wrong orientation)", column_stripes),
    ("only one cycle of the header colors is painted; remaining body rows stay 0", one_cycle_only),
    ("stripes start on the separator row, overwriting it", start_at_separator),
    ("stripe cycle starts at the second header color", shifted_start),
    ("whole body is filled with the first header color", first_color_only),
    ("each stripe is two rows tall", double_height_stripes),
    ("stripes follow the header colors sorted by value", sorted_order),
    ("colors do not cycle; the last header color fills the rest of the body", clamp_last_color),
    ("body is filled with the separator color 5", separator_color_body),
    ("separator row is dropped from the output (grid one row shorter)", drop_separator),
    ("last body row is left unfilled", stop_one_short),
]


def _valid(g):
    return (isinstance(g, list) and g and all(isinstance(r, list) for r in g)
            and len({len(r) for r in g}) == 1 and len(g[0]) > 0
            and all(isinstance(v, int) and 0 <= v <= 9 for r in g for v in r))


if __name__ == "__main__":
    task = json.load(open(Path(__file__).resolve().parents[3] / 'data/tasks/bd4472b8.json'))
    train = task["train"]
    print("pairs", len(train))
    for name, fn in ALTERNATIVES:
        n = 0
        for p in train:
            g = fn(p["input"], p["output"])
            if g is not None and _valid(g) and g != p["output"]:
                n += 1
        print(n, name)
