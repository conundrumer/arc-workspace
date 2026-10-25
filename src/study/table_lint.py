"""The lint of the large relations of each solver's concept case.

`uv run python -m study.table_lint [--corpus <dir>] [<task_id> ...]`
prints, for every solver of the corpus where no task id is given, one line
for each relation that holds more than 1,000 rows summed over the solver's
inputs, or that stopped at a bound on some input:

    <task_id> <relation> <rows per input> <test> <rewrite>

The test is the first that derives the relation of the table of
`docs/table-information.md#the-lint`, those that read no rows (the form of
the clauses that make the relation, read from the arclog file) before those
that read the rows of every rows file, and the rewrite is that table's. The
pairs of a total order or an equivalence are named before the closure that
they are, and the pairs of a partial order are a closure. Where no test
derives the relation, the test is `none` and the rewrite is the relation's
key and its bits per row, `log2(domain of the key / rows)`. Where the rows
were not read, the rewrite is `- - rows not read: <reason>`: the relation
stopped at a bound, which `row-counts` writes no rows for; or it has a rows
file of more than `WORK_CAP` rows × 2^columns, which the tests that read
rows skip; or the run that writes the rows of its solver faulted; or it has
no rows file.

The corpus is the arclog files of `gen/` of `arclog_convert.out`, which
reflect a solver's `.dl` file once `uv run python -m arclog_convert.convert
<stem>` has run on it. The rows are `arclog-cli row-counts`'s, which a
corpus run needs built with the `tool` profile; the checker calls nothing of
this module.
"""

import argparse
import itertools
import math
import subprocess
import sys
import tempfile
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from arc.task import TASKS_DIR
from engine import checkout
from study.corpus_survey.bodies import (
    FACTS,
    Body,
    Item,
    Kind,
    atom_labels,
    bodies,
    deep_atoms,
    item_kind,
    item_labels,
    names,
    strip,
)
from study.corpus_survey.trees import Node, arclog, gen_dir
from study.relation_shapes import BOX, RowsFile, Value, best_factoring, distinct_values, pair_shapes, read_rows_file

THRESHOLD = 1000
"""A relation is listed when its rows summed over the solver's inputs exceed this."""

WORK_CAP = 1 << 22
"""The most rows × 2^columns of a rows file the value tests read: the cost
of the tests on one file is about that product."""

STOPPED = "stopped:"
LIB_PAIRS = frozenset({"same_line", "neighbor", "apply"})
ORDERINGS = frozenset({"<", "<=", ">", ">="})


class Derivation(StrEnum):
    RESTATEMENT = "restatement"
    CELL_INSTANCE = "cell instance"
    PRODUCT = "product"
    CLOSURE = "closure"
    ORDER_OR_CLASS = "order or class as pairs"
    LIB_RELATION = "lib relation per pair"
    NONE = "none"


REWRITES = {
    Derivation.RESTATEMENT: "read the relation where the table was read; an input of one atom",
    Derivation.CELL_INSTANCE: "CellDistance or Flood",
    Derivation.PRODUCT: "the factors; for a guard, the input it binds or nothing",
    Derivation.CLOSURE: "Flood or Connectivity",
    Derivation.ORDER_OR_CLASS: "Order's score form; Quotient's `edge`",
    Derivation.LIB_RELATION: "the lib relation at the reading site; for Agreement, its `transform` form once the lib has it",
}
"""The rewrite each test names; `none` names none."""


@dataclass(frozen=True)
class Stopped:
    """The bound a model of a relation stopped at."""

    bound: str

    def __str__(self) -> str:
        return STOPPED + self.bound


type Count = int | Stopped


@dataclass(frozen=True)
class Relation:
    """A relation's largest model count on each input, in `row-counts`' order."""

    solver: str
    name: str
    counts: tuple[Count, ...]

    @property
    def stopped(self) -> Stopped | None:
        return next((c for c in self.counts if isinstance(c, Stopped)), None)

    @property
    def total(self) -> int:
        return sum(c for c in self.counts if isinstance(c, int))

    @property
    def largest(self) -> int:
        return max((c for c in self.counts if isinstance(c, int)), default=0)

    @property
    def flagged(self) -> bool:
        """Whether the relation is one of the solver's, not a fact of the task, and large or stopped."""
        return self.name not in FACTS and (self.total > THRESHOLD or self.stopped is not None)


def input_count(field: str) -> Count:
    """The count of one input: the bound a model stopped at, or the largest
    model count, `undefined` being 0 rows."""
    models: list[Count] = [
        Stopped(m[len(STOPPED) :]) if m.startswith(STOPPED) else 0 if m == "undefined" else int(m)
        for m in field.split(",")
    ]
    stopped = [m for m in models if isinstance(m, Stopped)]
    return stopped[0] if stopped else max(m for m in models if isinstance(m, int))


def read_counts(text: str) -> tuple[list[Relation], list[str]]:
    """The relations of a `row-counts` output, and its fault lines. The
    `clause` lines of the output are not read."""
    counts: dict[tuple[str, str], list[Count]] = defaultdict(list)
    faults = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) > 1 and fields[1] == "fault":
            faults.append(line)
        elif len(fields) == 4:
            counts[fields[0], fields[2]].append(input_count(fields[3]))
        elif len(fields) != 7 or fields[3] != "clause":
            raise ValueError(f"{line!r} is no line of `row-counts`")
    return [Relation(solver, name, tuple(c)) for (solver, name), c in counts.items()], faults


def row_counts(corpus: Path, tasks: Path, ids: Sequence[str], rows: tuple[int, Path] | None = None) -> str:
    """The output of `arclog-cli row-counts` on the solvers `ids`, or on every
    solver of the corpus where there are none, with the rows of each model
    over `rows[0]` written under `rows[1]`."""
    over = ["--over", str(rows[0]), "--rows", str(rows[1])] if rows else []
    command = ["cargo", "run", "--profile", "tool", "-q", "-p", "arclog-cli", "--", "row-counts", *over, str(corpus), str(tasks), *ids]
    done = subprocess.run(command, cwd=checkout.ROOT / "engine", stdout=subprocess.PIPE, text=True)
    if done.returncode not in (0, 1):  # 1: a solver faulted, and its line says so
        raise RuntimeError(f"{' '.join(command)} exited with {done.returncode}")
    return done.stdout


@dataclass(frozen=True)
class Signature:
    """What a rows file gives a comparison with another: its values per column."""

    relation: str
    path: Path
    rows: int
    types: tuple[str, ...]
    values: tuple[frozenset[Value], ...]


def work(file: RowsFile) -> int:
    """About the cost of a test that reads `file`: its rows × 2^columns."""
    return len(file.rows) * 2 ** len(file.columns)


def column_values(file: RowsFile) -> tuple[frozenset[Value], ...]:
    return tuple(frozenset(row[j] for row in file.rows) for j in range(len(file.columns)))


@dataclass(frozen=True)
class Written:
    """The rows files `row-counts` wrote for one solver."""

    paths: Mapping[str, Sequence[Path]]
    over_cap: frozenset[str]
    """The relations with a file over `WORK_CAP`."""
    peers: Mapping[tuple[str, int], Sequence[Signature]]
    """The files within the cap, by input and model."""


def written(rows_dir: Path, solver: str) -> Written:
    paths: dict[str, list[Path]] = defaultdict(list)
    over_cap: set[str] = set()
    peers: dict[tuple[str, int], list[Signature]] = defaultdict(list)
    for path in sorted((rows_dir / solver).rglob("*.json")):
        file = read_rows_file(path)
        paths[file.relation].append(path)
        if work(file) > WORK_CAP:
            over_cap.add(file.relation)
        else:
            types = tuple(ty for _, ty in file.columns)
            peers[file.input, file.model].append(Signature(file.relation, path, len(file.rows), types, column_values(file)))
    return Written(paths, frozenset(over_cap), peers)


@dataclass(frozen=True)
class Key:
    """Columns of a rows file that keep every row, and the product of their distinct counts."""

    columns: tuple[int, ...]
    domain: int


def least_key(file: RowsFile) -> Key:
    """The key of the fewest columns, at most four, of least domain, or all
    columns where none of at most four keeps every row."""
    distinct = distinct_values(file)
    for size in range(1, min(len(file.columns), 4) + 1):
        keys = [
            Key(columns, math.prod(distinct[j] for j in columns))
            for columns in itertools.combinations(range(len(file.columns)), size)
            if len({tuple(row[j] for j in columns) for row in file.rows}) == len(file.rows)
        ]
        if keys:
            return min(keys, key=lambda key: key.domain)
    return Key(tuple(range(len(file.columns))), math.prod(distinct))


def bits_per_row(key: Key, rows: int) -> float:
    return math.log2(key.domain / rows) if key.domain > rows else 0.0


@dataclass(frozen=True)
class Subject:
    """A relation to derive: the bodies of the clauses of the concept case
    that make it, and its rows files, none where its rows are not read, for
    the reason `unread` gives."""

    relation: Relation
    bodies: Sequence[Body]
    paths: Sequence[Path] | None
    unread: str
    peers: Mapping[tuple[str, int], Sequence[Signature]]


def conjunction(body: Body) -> list[list[Node]] | None:
    """The items of a body that is a flat conjunction of atoms and
    constraints, or `None` where it holds a nested form or a mark."""
    items = [item for item in body.items if isinstance(item, list) and item]
    return items if all(item_kind(item) in (Item.ATOM, Item.OP) for item in items) else None


def groups(items: Sequence[list[Node]]) -> list[set[str]]:
    """The variables of each group of conjuncts that share variables; a
    conjunct with no variable is a group of none."""
    parts: list[set[str]] = []
    for item in items:
        mine = set(names(item_labels(item)))
        apart = []
        for part in parts:
            if part & mine:
                mine |= part
            else:
                apart.append(part)
        parts = [*apart, mine]
    return parts


def head_variables(body: Body, parts: Sequence[set[str]]) -> set[str]:
    """The variables that are columns: an input's head labels, or every variable of a clause."""
    return {strip(label) for _, label in body.heads} if body.kind is Kind.INPUT else set().union(*parts)


def of_port(body: Body, components: Sequence[str], port: str) -> bool:
    return body.kind is Kind.INPUT and body.component in components and body.name.endswith("." + port)


def is_cell_edge(body: Body) -> bool:
    """An `edge` input of a `Distance` or `Propagation` instance."""
    return of_port(body, ("Distance", "Propagation"), "edge")


def is_cell_instance(body: Body) -> bool:
    """An `edge` of a `Distance` or `Propagation` instance that is one
    `neighbor` step between its two cells, with atoms of one variable each, on a cell or on the direction."""
    items = conjunction(body)
    if items is None or not is_cell_edge(body):
        return False
    steps = [item for item in items if item[0] == "neighbor"]
    if len(steps) != 1 or any(item_kind(item) is not Item.ATOM for item in items):
        return False
    labels = [strip(label) for label in atom_labels(steps[0])]
    cells = head_variables(body, [])
    if len(labels) != 3 or labels[0] == labels[2] or {labels[0], labels[2]} != cells or labels[1] in cells:
        return False
    return all(len(variables := names(atom_labels(item))) == 1 and variables <= set(labels) for item in items if item is not steps[0])


def is_comparison_edge(body: Body) -> bool:
    """An `edge` whose body orders two of its columns."""
    items = conjunction(body)
    if items is None or not is_cell_edge(body):
        return False
    cells = head_variables(body, [])
    return any(item_kind(item) is Item.OP and item[0] in ORDERINGS and len(operands := names(item_labels(item))) == 2 and operands <= cells for item in items)


def is_product(body: Body) -> bool:
    """Two or more groups of conjuncts that share no variable, each binding a
    column; for a `Ray`'s `node`, also one group that binds a column beside a
    group that binds none, a guard."""
    items = conjunction(body)
    if items is None:
        return False
    parts = groups(items)
    head = head_variables(body, parts)
    bound = [part for part in parts if part & head]
    guarded = len(bound) < len(parts)
    if of_port(body, ("Ray",), "node"):
        return bool(bound) and (len(bound) > 1 or guarded)
    return len(bound) > 1 and not guarded


def reads_apply_per_pair(body: Body) -> bool:
    return of_port(body, ("Agreement",), "correspondence") and any(atom[0] == "apply" for atom in deep_atoms(body.items))


def is_one_atom_input(body: Body) -> bool:
    """An instance input whose body is one atom of a derived relation."""
    items = conjunction(body)
    return body.kind is Kind.INPUT and items is not None and len(items) == 1 and item_kind(items[0]) is Item.ATOM and str(items[0][0]).startswith("&")


FORMS: tuple[tuple[Derivation, Callable[[Body], bool]], ...] = (
    (Derivation.RESTATEMENT, is_one_atom_input),
    (Derivation.CELL_INSTANCE, is_cell_instance),
    (Derivation.PRODUCT, is_product),
    (Derivation.ORDER_OR_CLASS, is_comparison_edge),
    (Derivation.LIB_RELATION, reads_apply_per_pair),
)
"""The tests that read no rows, in the table's order, each by the form of the clauses that make the relation."""


def restates(file: RowsFile, peers: Mapping[tuple[str, int], Sequence[Signature]]) -> bool:
    """Whether the rows are those of another relation of the same input and
    model, or a projection of them onto columns of equal values."""
    types = [ty for _, ty in file.columns]
    values = column_values(file)
    for peer in peers[file.input, file.model]:
        if peer.relation == file.relation or peer.rows < len(file.rows):
            continue
        options = [[j for j in range(len(peer.types)) if peer.types[j] == ty and peer.values[j] == v] for ty, v in zip(types, values)]
        selections = [s for s in itertools.product(*options) if len(set(s)) == len(s)]
        if selections:
            rows = read_rows_file(peer.path).rows
            if any({tuple(row[j] for j in s) for row in rows} == file.rows for s in selections):
                return True
    return False


def box_pair(file: RowsFile) -> tuple[int, int] | None:
    """The two columns of the least key where both are `Box` columns."""
    columns = least_key(file).columns
    return (columns[0], columns[1]) if len(columns) == 2 and all(file.columns[j][1] == BOX for j in columns) else None


def pair_kind(file: RowsFile) -> Derivation | None:
    """What the pairs of the `Box` columns of the key are: the pairs of a
    total order or an equivalence, or a closure, where a smaller subrelation generates them."""
    pair = box_pair(file)
    if pair is None:
        return None
    a, b = pair
    (shape,) = pair_shapes(replace(file, columns=[file.columns[a], file.columns[b]], rows={(row[a], row[b]) for row in file.rows}))
    if not shape.transitive or shape.reduction is None or shape.reduction >= len(file.rows):
        return None
    return Derivation.ORDER_OR_CLASS if shape.order == "total" or shape.equivalence else Derivation.CLOSURE


def factored(file: RowsFile) -> Derivation | None:
    found = best_factoring(file)
    return Derivation.PRODUCT if found is not None and len(found.factors) > 1 else None


def rows_tests(subject: Subject) -> list[Callable[[RowsFile], Derivation | None]]:
    """The tests that read the rows of one file, in the table's order. A total
    order or an equivalence is named before the closure that it is."""

    def restated(file: RowsFile) -> Derivation | None:
        return Derivation.RESTATEMENT if restates(file, subject.peers) else None

    def lib_pair(file: RowsFile) -> Derivation | None:
        reads_lib = any(atom[0] in LIB_PAIRS for body in subject.bodies for atom in deep_atoms(body.items))
        return Derivation.LIB_RELATION if reads_lib and box_pair(file) is not None else None

    return [restated, factored, pair_kind, lib_pair]


def on_every_file(paths: Sequence[Path], test: Callable[[RowsFile], Derivation | None]) -> Derivation | None:
    """What `test` derives on every rows file, read one at a time; a closure where it derives an order on some and a closure on others."""
    found = set()
    for path in paths:
        derived = test(read_rows_file(path))
        if derived is None:
            return None
        found.add(derived)
    return found.pop() if len(found) == 1 else Derivation.CLOSURE


def residual(subject: Subject) -> str:
    """The key and bits per row of the largest rows file, or the reason the rows were not read."""
    if subject.paths is None:
        return f"- - rows not read: {subject.unread}"
    largest = ""
    best = -1
    for path in subject.paths:
        file = read_rows_file(path)
        if len(file.rows) > best:
            key = least_key(file)
            best = len(file.rows)
            largest = f"{','.join(file.columns[j][0] for j in key.columns)} {bits_per_row(key, best):.1f}"
    return largest


def derive(subject: Subject) -> tuple[Derivation, str]:
    """The first test that derives the relation, and its rewrite, or `none` and its residual. The tests that read no rows come first."""
    for test, form in FORMS:
        if subject.bodies and all(form(body) for body in subject.bodies):
            return test, REWRITES[test]
    if subject.paths is not None:
        for rows_test in rows_tests(subject):
            if (test := on_every_file(subject.paths, rows_test)) is not None:
                return test, REWRITES[test]
    return Derivation.NONE, residual(subject)


def solver_lines(corpus: Path, rows_dir: Path, solver: str, flagged: Sequence[Relation], fault: str | None = None) -> list[str]:
    """The lines of one solver's flagged relations; `fault` is the fault of
    the run that wrote its rows, where it had one."""
    concept = [body for body in bodies(solver, arclog(corpus, solver)) if not body.in_alt()]
    files = written(rows_dir, solver)
    lines = []
    for relation in flagged:
        if relation.stopped is not None:
            unread = str(relation.stopped)
        elif fault is not None:
            unread = fault
        elif relation.name in files.over_cap:
            unread = "over the work cap"
        elif relation.name not in files.paths:
            unread = "no rows file written"
        else:
            unread = ""
        paths = None if unread else files.paths[relation.name]
        subject = Subject(relation, [b for b in concept if b.name == relation.name], paths, unread, files.peers)
        test, rewrite = derive(subject)
        lines.append(f"{solver} {relation.name} {','.join(map(str, relation.counts))} {test} {rewrite}")
    return lines


def lint(corpus: Path, tasks: Path, ids: Sequence[str]) -> list[str]:
    """Every line of the lint, by solver."""
    relations, faults = read_counts(row_counts(corpus, tasks, ids))
    flagged = [r for r in relations if r.flagged]
    lines: dict[str, list[str]] = {fault.split()[0]: [fault] for fault in faults}
    solvers = sorted({r.solver for r in flagged})
    counted = [r.largest for r in flagged if r.largest]
    dump_faults: dict[str, str] = {}
    with tempfile.TemporaryDirectory() as rows_dir:
        if counted:
            # The least `over` that writes each flagged relation's rows on its largest input.
            _, dumped = read_counts(row_counts(corpus, tasks, solvers, (max(min(counted) - 1, 0), Path(rows_dir))))
            dump_faults = {fault.split()[0]: fault.split(" ", 1)[1] for fault in dumped}
        for solver in solvers:
            lines[solver] = solver_lines(corpus, Path(rows_dir), solver, [r for r in flagged if r.solver == solver], dump_faults.get(solver))
    return [line for solver in sorted(lines) for line in lines[solver]]


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m study.table_lint", description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--corpus", type=Path, default=gen_dir(), help="the directory of the arclog files, `gen/` of `arclog_convert.out` by default")
    parser.add_argument("task_ids", nargs="*", help="the solvers to lint, every solver of the corpus by default")
    args = parser.parse_args(argv)
    for line in lint(args.corpus, TASKS_DIR, args.task_ids):
        print(line, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
