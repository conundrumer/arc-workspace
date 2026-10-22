"""The shape of each large relation of a solver's concept case, and its makers.

`uv run python -m study.relation_shapes <rows dir> <row-counts output>`
reads what `arclog-cli row-counts --over <n> --rows <rows dir>` writes: one
rows file per solver, input, relation and model, and the output's `clause`
lines, which give the rows of each clause body that makes a relation. It
prints one block per rows file: the relation's count, its makers, and its
shape.

The engine types a Position or an Offset column `Box`, so each `Box` column
stands for a position, and for the base or the offset it is taken
relative to.

The shape holds:

- the distinct values of each column, the density of the relation, and the
  density of each pair of `Box` columns;
- per pair of columns, grouped by the other columns:
  functional each way, an order total or partial, an equivalence with its
  classes, and a transitive relation with the size of a generating
  subrelation;
- the `Box` and `Ident` columns that are functions of the row;
- the least projections whose join gives the relation whole, and the same
  after the `Box` columns are taken relative to each other `Box` column in
  turn.
"""

import itertools
import json
import math
import sys
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

type Value = int | str | tuple["Value", ...]
type Row = tuple[Value, ...]
type Column = tuple[str, str]

BOX = "Box"
IDENT = "Ident"
PAIRED = {BOX, IDENT}
CLAUSE = "clause"


@dataclass(frozen=True)
class RowsFile:
    """One model's rows of a relation on an input."""

    solver: str
    input: str
    relation: str
    model: int
    columns: list[Column]
    rows: set[Row]


def freeze(value: object) -> Value:
    """A JSON value with each list a tuple."""
    if isinstance(value, list):
        return tuple(freeze(item) for item in value)
    if isinstance(value, int | str):
        return value
    raise ValueError(f"{value!r} is no value of a rows file")


def read_rows_file(path: Path) -> RowsFile:
    """The rows file at `path`, or a `ValueError` where it is no rows file."""
    data = json.loads(path.read_text())
    try:
        columns = [(column["name"], column["type"]) for column in data["columns"]]
        rows = {tuple(freeze(value) for value in row) for row in data["rows"]}
        file = RowsFile(data["solver"], data["input"], data["relation"], data["model"], columns, rows)
    except (KeyError, TypeError) as error:
        raise ValueError(f"{path} is no rows file: {error!r}") from error
    arity = len(columns)
    if any(not isinstance(row, tuple) or len(row) != arity for row in rows):
        raise ValueError(f"{path} holds a row that is no row of {arity} columns")
    if len(rows) != len(data["rows"]):
        raise ValueError(f"{path} holds a row twice")
    return file


@dataclass(frozen=True)
class Maker:
    """A clause that makes a relation: the rows of its body, and what it reads."""

    path: str
    body: str
    reads: tuple[str, ...]


def read_makers(counts: str) -> dict[tuple[str, str, str], list[Maker]]:
    """The makers in the `clause` lines of a `row-counts` output, by the
    solver, input and relation they make."""
    makers: dict[tuple[str, str, str], list[Maker]] = defaultdict(list)
    for line in counts.splitlines():
        fields = line.split()
        if len(fields) == 7 and fields[3] == CLAUSE:
            solver, input, relation, _, path, body, reads = fields
            makers[solver, input, relation].append(Maker(path, body, () if reads == "-" else tuple(reads.split(","))))
    return makers


def distinct_values(file: RowsFile) -> list[int]:
    return [len({row[j] for row in file.rows}) for j in range(len(file.columns))]


def pair_densities(file: RowsFile, distinct: list[int]) -> list[tuple[str, str, int, int]]:
    """For each pair of `Box` columns, the pairs of values they hold and the
    pairs they could hold."""
    boxes = [j for j, (_, ty) in enumerate(file.columns) if ty == BOX]
    return [
        (file.columns[a][0], file.columns[b][0], len({(row[a], row[b]) for row in file.rows}), distinct[a] * distinct[b])
        for a, b in itertools.combinations(boxes, 2)
    ]


def functional_columns(file: RowsFile) -> list[str]:
    """The `Box` and `Ident` columns that take a different value in each row."""
    return [
        name
        for j, (name, ty) in enumerate(file.columns)
        if ty in PAIRED and len({row[j] for row in file.rows}) == len(file.rows)
    ]


def determined_columns(file: RowsFile) -> list[str]:
    """The columns that the other columns determine: no two rows agree on
    all the other columns."""
    return [
        name
        for j, (name, _) in enumerate(file.columns)
        if len({row[:j] + row[j + 1 :] for row in file.rows}) == len(file.rows)
    ]


def bits(mask: int) -> Iterator[int]:
    while mask:
        low = mask & -mask
        yield low.bit_length() - 1
        mask ^= low


@dataclass(frozen=True)
class Graph:
    """What one set of edges is."""

    forward: bool
    backward: bool
    order: str | None
    transitive: bool
    equivalence: bool
    classes: int | None
    reduction: int | None
    edges: int


def graph(edges: set[tuple[Value, Value]]) -> Graph:
    nodes = sorted({v for edge in edges for v in edge}, key=repr)
    ids = {v: i for i, v in enumerate(nodes)}
    n = len(nodes)
    adj = [0] * n
    rev = [0] * n
    for a, b in edges:
        adj[ids[a]] |= 1 << ids[b]
        rev[ids[b]] |= 1 << ids[a]
    forward = all(x.bit_count() <= 1 for x in adj)
    backward = all(x.bit_count() <= 1 for x in rev)
    irreflexive = all(not (adj[i] >> i & 1) for i in range(n))
    reflexive = all(adj[i] >> i & 1 for i in range(n))
    symmetric = adj == rev
    transitive = all(not (adj[j] & ~adj[i]) for i in range(n) for j in bits(adj[i]))
    order = None
    if irreflexive and transitive:
        order = "total" if len(edges) == n * (n - 1) // 2 else "partial"
    reduction = classes = None
    if transitive:
        # A transitive digraph has complete strongly connected components. A
        # cycle spans each nontrivial component; singleton loops and the
        # covers of the quotient complete a minimum generating subrelation.
        components: list[int] = []
        seen = 0
        for i in range(n):
            if seen >> i & 1:
                continue
            mask = (adj[i] & rev[i]) | (1 << i)
            seen |= mask
            components.append(mask)
        component_of = {a: i for i, mask in enumerate(components) for a in bits(mask)}
        quotient = [0] * len(components)
        quotient_rev = [0] * len(components)
        reduction = 0
        for i, mask in enumerate(components):
            a = next(bits(mask))
            size = mask.bit_count()
            reduction += size if size > 1 else int(bool(adj[a] >> a & 1))
            for b in bits(adj[a] & ~mask):
                quotient[i] |= 1 << component_of[b]
                quotient_rev[component_of[b]] |= 1 << i
        reduction += sum(not (quotient[i] & quotient_rev[j]) for i in range(len(components)) for j in bits(quotient[i]))
        if reflexive and symmetric:
            classes = len(components)
    return Graph(forward, backward, order, transitive, bool(reflexive and symmetric and transitive), classes, reduction, len(edges))


@dataclass(frozen=True)
class PairShape:
    """What two columns are, with the other columns held fixed."""

    columns: tuple[str, str]
    keys: int
    forward: bool
    backward: bool
    order: str | None
    equivalence: bool
    classes: int | None
    transitive: bool
    reduction: int | None


def pair_shapes(file: RowsFile) -> list[PairShape]:
    """The shape of each pair of columns, over the groups of
    rows that agree on the other columns."""
    shapes = []
    for a, b in itertools.combinations(range(len(file.columns)), 2):
        groups: dict[Row, set[tuple[Value, Value]]] = defaultdict(set)
        for row in file.rows:
            groups[row[:a] + row[a + 1 : b] + row[b + 1 :]].add((row[a], row[b]))
        graphs = [graph(edges) for edges in groups.values()]
        transitive = all(g.transitive for g in graphs)
        equivalence = all(g.equivalence for g in graphs)
        order = None
        if all(g.order for g in graphs):
            order = "total" if all(g.order == "total" for g in graphs) else "partial"
        shapes.append(
            PairShape(
                (file.columns[a][0], file.columns[b][0]),
                len(groups),
                all(g.forward for g in graphs),
                all(g.backward for g in graphs),
                order,
                equivalence,
                sum(g.classes or 0 for g in graphs) if equivalence else None,
                transitive,
                sum(g.reduction or 0 for g in graphs) if transitive else None,
            )
        )
    return shapes


def join_exact(rows: set[Row], cols: list[int], factors: list[int], projections: Mapping[int, set[Row]]) -> bool:
    """Whether the join of the projections, each of the columns in the bit
    mask of its factor, is `rows` and no more."""
    if not rows:
        return True
    if len(factors) == 2:
        a, b = factors
        shared = [i for i in cols if (a & b) >> i & 1]

        def counts(mask: int) -> Counter[Row]:
            index = [i for i in cols if mask >> i & 1]
            positions = [index.index(i) for i in shared]
            return Counter(tuple(row[j] for j in positions) for row in projections[mask])

        left, right = counts(a), counts(b)
        return sum(v * right.get(key, 0) for key, v in left.items()) == len(rows)
    # A generic join over tries stops at the first row that is no row of `rows`.
    order = sorted(cols, key=lambda j: len({row[j] for row in rows}))
    tries: list[dict] = []
    members: list[set[int]] = []
    for factor in factors:
        index = [i for i in cols if factor >> i & 1]
        in_order = [i for i in order if i in index]
        position = {j: index.index(j) for j in index}
        root: dict = {}
        for row in projections[factor]:
            node = root
            for j in in_order:
                node = node.setdefault(row[position[j]], {})
        tries.append(root)
        members.append(set(in_order))
    current: list[Value] = [0] * (max(cols) + 1)
    seen = 0

    def walk(k: int, nodes: list[dict]) -> bool:
        nonlocal seen
        if k == len(order):
            if tuple(current[j] for j in cols) not in rows:
                return False
            seen += 1
            return True
        j = order[k]
        touch = [i for i, m in enumerate(members) if j in m]
        smallest = min(touch, key=lambda i: len(nodes[i]))
        others = [i for i in touch if i != smallest]
        for v in nodes[smallest]:
            if not all(v in nodes[i] for i in others):
                continue
            current[j] = v
            below = nodes.copy()
            for i in touch:
                below[i] = nodes[i][v]
            if not walk(k + 1, below):
                return False
        return True

    ok = walk(0, tries)
    if ok and seen != len(rows):
        raise ValueError(f"the join of {factors} gave {seen} rows of {len(rows)}")
    return ok


@dataclass(frozen=True)
class Factoring:
    """Projections whose join is a relation."""

    factors: list[tuple[list[str], int]]
    largest: int
    total: int
    base: str | None = None
    relative: list[str] | None = None


def factor(rows: set[Row], cols: list[Column], allow: Callable[[int], bool] | None = None) -> Factoring | None:
    """The projections of `rows` of least size whose join is `rows`, among
    those that `allow` accepts, or `None` where no projections smaller than
    `rows` join to it."""
    d = len(cols)
    full = (1 << d) - 1
    if d < 2:
        return None
    projections: dict[int, set[Row]] = {}
    for mask in range(1, full):
        if allow is not None and not allow(mask):
            continue
        index = [i for i in range(d) if mask >> i & 1]
        projected = {tuple(row[j] for j in index) for row in rows}
        if len(projected) < len(rows):
            projections[mask] = projected
    sizes = {mask: len(p) for mask, p in projections.items()}
    levels = sorted(set(sizes.values()))
    if not levels:
        return None

    def test(limit: int) -> tuple[bool, list[int]]:
        allowed = sorted((m for m in projections if sizes[m] <= limit), key=lambda m: -m.bit_count())
        chosen: list[int] = []
        for m in allowed:
            if not any(m & f == m for f in chosen):
                chosen.append(m)
        cover = 0
        for f in chosen:
            cover |= f
        return cover == full and join_exact(rows, list(range(d)), chosen, projections), chosen

    if not test(levels[-1])[0]:
        return None
    low, high = 0, len(levels) - 1
    while low < high:
        mid = (low + high) // 2
        if test(levels[mid])[0]:
            high = mid
        else:
            low = mid + 1
    _, chosen = test(levels[low])
    # Drop each factor whose removal leaves the join exact.
    for f in sorted(chosen, key=lambda m: (-sizes[m], -m.bit_count())):
        trial = [m for m in chosen if m != f]
        cover = 0
        for m in trial:
            cover |= m
        if cover == full and join_exact(rows, list(range(d)), trial, projections):
            chosen = trial
    return Factoring(
        [([cols[i][0] for i in range(d) if m >> i & 1], sizes[m]) for m in chosen],
        max(sizes[m] for m in chosen),
        sum(sizes[m] for m in chosen),
    )


def minus(value: Value, base: Value) -> Value:
    """The Box `value` taken relative to the Box `base`, by coordinate."""
    sides = list(zip(value, base)) if isinstance(value, tuple) and isinstance(base, tuple) else []
    if not all(isinstance(a, int) and isinstance(b, int) for a, b in sides) or not sides:
        raise ValueError(f"{value!r} and {base!r} are no Boxes")
    return tuple(a - b for a, b in sides if isinstance(a, int) and isinstance(b, int))


def best_factoring(file: RowsFile) -> Factoring | None:
    """The factoring of least largest and total size, of the relation as it
    is and of the relation with its `Box` columns taken relative to each
    other `Box` column in turn."""
    cols = file.columns
    best = factor(file.rows, cols)
    for base, (base_name, base_type) in enumerate(cols):
        if base_type != BOX:
            continue
        targets = [j for j, (_, ty) in enumerate(cols) if ty == BOX and j != base]
        if not targets:
            continue
        shifted_cols = [(name + (".rel" if j in targets else ""), ty) for j, (name, ty) in enumerate(cols)]
        shifted: set[Row] = {
            tuple(minus(v, row[base]) if j in targets else v for j, v in enumerate(row)) for row in file.rows
        }
        target_mask = sum(1 << j for j in targets)
        found = factor(shifted, shifted_cols, lambda m: not (m >> base & 1 and m & target_mask))
        if found is None:
            continue
        found = Factoring(found.factors, found.largest, found.total, base_name, [cols[j][0] for j in targets])
        if best is None or (found.largest, found.total) < (best.largest, best.total):
            best = found
    return best


def block(file: RowsFile, makers: list[Maker]) -> str:
    """The text on one relation: count, makers and shape."""
    distinct = distinct_values(file)
    density = len(file.rows) / math.prod(distinct) if distinct else 0
    lines = [f"{file.solver} {file.input} {file.relation} model {file.model}: {len(file.rows)} rows"]
    if makers:
        lines += [f"  maker {m.path}: body {m.body} rows, reads {', '.join(m.reads) or '-'}" for m in makers]
    else:
        lines.append(f"  maker: no clause; {file.relation} is made by an instance port or is a parameter")
    lines.append("  columns: " + "; ".join(f"{name}:{ty}={d}" for (name, ty), d in zip(file.columns, distinct)))
    lines.append(f"  density: {density:.4g}")
    for a, b, held, possible in pair_densities(file, distinct):
        lines.append(f"  pair density {a} x {b}: {held} / {possible} = {held / possible:.4g}")
    if functions := functional_columns(file):
        lines.append("  functions of the row: " + ", ".join(functions))
    if determined := determined_columns(file):
        lines.append("  determined by the other columns: " + ", ".join(determined))
    for shape in pair_shapes(file):
        facts = [
            text
            for text, held in [
                ("a -> b", shape.forward),
                ("b -> a", shape.backward),
                (f"{shape.order} order", shape.order),
                (f"equivalence of {shape.classes} classes", shape.equivalence),
                (f"transitive, generated by {shape.reduction} rows", shape.transitive),
            ]
            if held
        ]
        lines.append(f"  pair {shape.columns[0]} x {shape.columns[1]} over {shape.keys} keys: {'; '.join(facts) or 'none'}")
    best = best_factoring(file)
    if best is None:
        lines.append("  factoring: none")
    else:
        parts = " JOIN ".join(f"({', '.join(names)}) {size}" for names, size in best.factors)
        relative = f", {', '.join(best.relative)} relative to {best.base}" if best.base and best.relative else ""
        lines.append(f"  factoring{relative}: {parts}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: python -m study.relation_shapes <rows dir> <row-counts output>", file=sys.stderr)
        return 2
    rows_dir, counts = Path(argv[0]), Path(argv[1])
    makers = read_makers(counts.read_text())
    for path in sorted(rows_dir.rglob("*.json")):
        file = read_rows_file(path)
        print(block(file, makers.get((file.solver, file.input, file.relation), [])), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
