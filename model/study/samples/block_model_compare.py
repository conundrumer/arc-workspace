#!/usr/bin/env python3
"""Compares two block-boost model.jsonl files tree by tree and stops at the first tree that differs.

    block_model_compare.py A B [--start S] [--count N] [--tol T] [--wait SECONDS]

Tree i of A is compared with tree i of B, for i from S (0-based, default 0), for N trees (default: until a file has no more whole lines).
A line counts only once it ends in a newline, so a file that a running fit still writes can be read. With --wait, a file that has no next whole
line is polled for that many seconds before the comparison stops there.

A tree is the same where the split columns, thresholds, default directions, nan flags and child links are equal. Gains and leaf values are equal
where |a - b| <= T * max(|a|, |b|); the default T is 0, which asks for the same f64.

It exits 0 where every compared tree is the same, 1 at the first tree that differs, 2 where it compared fewer trees than --count asked for.
"""
import argparse
import json
import sys
import time

STRUCTURE = ["column", "threshold", "default_left", "nan_seen", "left", "right"]


def tree_lines(path, wait):
    """Yields each whole line of the file as it appears."""
    with open(path, "rb") as f:
        partial = b""
        idle_since = None
        while True:
            chunk = f.readline()
            if chunk.endswith(b"\n"):
                line, partial = partial + chunk, b""
                idle_since = None
                yield line.decode()
                continue
            partial += chunk
            if chunk:
                continue
            # End of file inside or between lines.
            if idle_since is None:
                idle_since = time.monotonic()
            if time.monotonic() - idle_since >= wait:
                return
            time.sleep(1.0)


def close(a, b, tol):
    return a == b or abs(a - b) <= tol * max(abs(a), abs(b))


def describe(tree, n):
    return (
        f"column {tree['column'][n]} threshold {tree['threshold'][n]} default_left {tree['default_left'][n]} "
        f"left {tree['left'][n]} right {tree['right'][n]} gain {tree['gain'][n]!r}"
    )


def differences(a, b, tol):
    """The ways two trees differ, as lines of text; none where they are the same."""
    out = []
    splits = min(len(a["column"]), len(b["column"]))
    if len(a["column"]) != len(b["column"]):
        out.append(f"split counts differ: {len(a['column'])} and {len(b['column'])}")
    first = None
    for n in range(splits):
        if any(a[key][n] != b[key][n] for key in STRUCTURE):
            first = n
            break
    if first is not None:
        out.append(f"first split that differs is node {first}:")
        out.append(f"    A: {describe(a, first)}")
        out.append(f"    B: {describe(b, first)}")
        same_column = a["column"][first] == b["column"][first]
        out.append(f"    gains: A {a['gain'][first]!r} B {b['gain'][first]!r}; the splits are on {'the same' if same_column else 'different'} columns")
        for key in STRUCTURE:
            bad = [n for n in range(splits) if a[key][n] != b[key][n]]
            if bad:
                out.append(f"    {key} differs at {len(bad)} of {splits} nodes, first {bad[:8]}")
    bad_gain = [n for n in range(splits) if not close(a["gain"][n], b["gain"][n], tol)]
    if bad_gain:
        n = bad_gain[0]
        out.append(f"gains differ at {len(bad_gain)} of {splits} nodes; node {n}: A {a['gain'][n]!r} B {b['gain'][n]!r} (relative {abs(a['gain'][n] - b['gain'][n]) / max(abs(a['gain'][n]), abs(b['gain'][n])):.3e})")
    leaves = min(len(a["value"]), len(b["value"]))
    if len(a["value"]) != len(b["value"]):
        out.append(f"leaf counts differ: {len(a['value'])} and {len(b['value'])}")
    bad_value = [i for i in range(leaves) if not close(a["value"][i], b["value"][i], tol)]
    if bad_value:
        i = bad_value[0]
        worst = max(bad_value, key=lambda j: abs(a["value"][j] - b["value"][j]) / max(abs(a["value"][j]), abs(b["value"][j])))
        out.append(f"leaf values differ at {len(bad_value)} of {leaves} leaves; leaf {i}: A {a['value'][i]!r} B {b['value'][i]!r}")
        out.append(f"    largest relative difference is at leaf {worst}: A {a['value'][worst]!r} B {b['value'][worst]!r}")
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("a")
    parser.add_argument("b")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--count", type=int, default=None)
    parser.add_argument("--tol", type=float, default=0.0)
    parser.add_argument("--wait", type=float, default=0.0)
    args = parser.parse_args()

    lines_a, lines_b = tree_lines(args.a, args.wait), tree_lines(args.b, args.wait)
    compared = 0
    index = 0
    worst_gain = worst_value = 0.0
    for index, (line_a, line_b) in enumerate(zip(lines_a, lines_b)):
        if index < args.start:
            continue
        if args.count is not None and compared >= args.count:
            break
        a, b = json.loads(line_a), json.loads(line_b)
        found = differences(a, b, args.tol)
        if found:
            print(f"tree {index} (counting from 0) differs after {compared} equal trees:")
            for line in found:
                print("  " + line)
            return 1
        for x, y in zip(a["gain"], b["gain"]):
            worst_gain = max(worst_gain, abs(x - y) / max(abs(x), abs(y), 1e-300))
        for x, y in zip(a["value"], b["value"]):
            worst_value = max(worst_value, abs(x - y) / max(abs(x), abs(y), 1e-300))
        compared += 1
    print(f"{compared} trees from tree {args.start} are the same (tolerance {args.tol}); largest relative gain difference {worst_gain:.3e}, leaf value {worst_value:.3e}")
    if args.count is not None and compared < args.count:
        print(f"only {compared} of the {args.count} asked-for trees were whole lines in both files")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
