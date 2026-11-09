"""The lint of the large relations of each solver's concept case.

`uv run python -m study.table_lint [--corpus <dir>] [<task_id> ...]`
prints, for every solver of the corpus where no task id is given, one line
for each relation that holds more than 1,000 rows summed over the solver's
inputs, or that stopped at a bound on some input, other than `&output`, which
no rewrite removes, and a relation that the decode gives no table, which
`row-counts` marks:

    <task_id> <relation> <rows per input> <test> <rewrite>

The principle each line states is that a table should hold something the
relations it is derived from do not. The test is the first of these that
derives the relation, those that read no rows (the form of the clauses that
make the relation, read from the arclog file) before those that read the rows
of every rows file:

    restatement             the rows equal another relation's, or a projection
                            of one; the table holds nothing beyond the other
                            relation
    cell instance           an `edge` of Distance or Propagation whose body is
                            the grid's adjacency inside a node set; the table
                            holds nothing beyond the node set, which CellDistance
                            or Flood takes alone
    product                 the rows are the product of the projections onto a
                            partition of the columns, or, for an input, a guard
                            with no variable times a domain; the table holds
                            nothing beyond the factors, or for a guard the
                            conjuncts that bind the columns
    closure                 the rows are the closure of a step relation inside a
                            node set; the table holds nothing beyond the steps
    order or class as pairs the key is a pair, and the rows are the pairs some
                            column orders, or an equivalence's pairs; the table
                            holds nothing beyond a score per member, or the
                            classes
    lib relation per pair   the rows are a lib relation (`same_line`,
                            `neighbor`, `apply`) restricted to a cell set; the
                            table holds nothing beyond the lib relation and the
                            cell set
    none                    a residual: the line gives the rows, the key and
                            the bits per row

The lines are hints. `--measure <task_id>` judges an edit of a solver by its
tables: it converts the solver as committed and as its file now holds it, each
apart from the corpus and cached by the solver's text, and prints each table's
rows, summed over the inputs, on both sides, with the largest table, the
tables over the cap and over the threshold, and whether the solver's tables got
smaller. It marks a table that no relation of the solver is the source of, by
the converter's name map, and it judges an edit that removes an instance of a
lib component worse. An edit is kept where the solver still passes its pairs
and its tables got smaller. The rewrite is a sentence that says
what to change, from what the test found: the relation the table restates,
the columns of each factor, the step relation of a closure, or the lib
relation per pair, each column by the name the solver gives it in the rows
file (`c<i>` for an output of a shared node, which the file names so). Where
the rows files differ, the rewrite is that of the largest. The pairs of a
total order or an equivalence are named before the closure that they are, and
the pairs of a partial order are a closure. Where no test derives the
relation, the test is `none` and the rewrite gives the relation's least key
and its bits per row, `log2(domain of the key / rows)`. Where the rows were
not read, the rewrite says so and gives the reason: the relation stopped at a
bound, which `row-counts` writes no rows for; or it has a rows file of more
than `WORK_CAP` rows × 2^columns, which the tests that read rows skip; or the
run that writes the rows of its solver faulted; or it has no rows file.

The rows of a relation whose columns the type check gives no types are not
written, so its line says no rows file was written.

The corpus is the arclog files of `corpus_dir()`: `programs/arclog/` in the main worktree,
`work/arclog/gen/` of the worktree in a linked one. They
reflect a solver's `.dl` file once `uv run python -m arclog_convert.convert
<stem>` has run on it. A run of the default corpus on given task ids runs that
command on them first, and prints its summary on stderr; a run on every
solver, or on another corpus, reads the files as they stand. The rows are
`arclog-cli row-counts`'s, which a corpus run needs built with the `tool`
profile; the checker calls nothing of this module.
"""

import argparse
import hashlib
import itertools
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path

from arc.task import TASKS_DIR
import arclog_convert
from arclog_convert import plans
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
from study.corpus_survey.trees import Node, arclog, head
from study.relation_shapes import BOX, RowsFile, Value, best_factoring, distinct_values, pair_shapes, read_rows_file

THRESHOLD = 1000
"""A relation is listed when its rows summed over the solver's inputs exceed this."""

CAP = 4000
"""The rows of a table the feature encoder sees whole (`--enc-max-rows`)."""

WORK_CAP = 1 << 22
"""The most rows × 2^columns of a rows file the value tests read: the cost
of the tests on one file is about that product."""

STOPPED = "stopped:"
OUTPUT = "&output"
NO_TABLE = ("no", "table")
"""The fields after a relation's name on the line of `row-counts` that marks a relation the decode gives no table."""
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


CELL_FORMS = {"Distance": "CellDistance", "Propagation": "Flood"}
"""The lib instance that takes the grid's adjacency in place of the `edge` of each instance."""


@dataclass(frozen=True)
class Finding:
    """A test that derives a relation, and the rewrite it names, as a sentence that says what to change."""

    test: Derivation
    rewrite: str


def quoted(names: Iterable[str]) -> str:
    return ", ".join(f"`{name}`" for name in names)


def in_linked_worktree() -> bool:
    return checkout.main_worktree(checkout.ROOT).resolve() != checkout.ROOT.resolve()


def corpus_out() -> Path:
    """The output directory of the default corpus: `work/arclog/` of this linked worktree, or `arclog_convert.out()` in the main worktree."""
    return checkout.ROOT / "work" / "arclog" if in_linked_worktree() else arclog_convert.out()


def corpus_dir() -> Path:
    """The default corpus: the converted solvers of `corpus_out()`, which are `programs/arclog/` in the main worktree and `gen/` of `corpus_out()` in a linked one."""
    return arclog_convert.corpus(corpus_out())


def reconvert(ids: Sequence[str]) -> None:
    """Convert the solvers `ids` into the default corpus, with the converter's summary on stderr."""
    over = ["--out", str(corpus_out())] if in_linked_worktree() else []
    command = [sys.executable, "-m", "arclog_convert.convert", *over, *ids]
    done = subprocess.run(command, cwd=checkout.ROOT, stdout=sys.stderr)
    if done.returncode != 0:
        raise RuntimeError(f"{' '.join(command)} exited with {done.returncode}")


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
    tabled: bool = True
    """Whether the decode gives the relation a table."""

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
        """Whether the relation is one of the solver's that has a table, not a fact of the task or the output, and large or stopped."""
        return self.tabled and self.name not in FACTS | {OUTPUT} and (self.total > THRESHOLD or self.stopped is not None)


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
    untabled = set()
    faults = []
    for line in text.splitlines():
        fields = line.split()
        if len(fields) > 1 and fields[1] == "fault":
            faults.append(line)
        elif len(fields) == 4:
            counts[fields[0], fields[2]].append(input_count(fields[3]))
        elif tuple(fields[3:]) == NO_TABLE:
            untabled.add((fields[0], fields[2]))
        elif len(fields) != 7 or fields[3] != "clause":
            raise ValueError(f"{line!r} is no line of `row-counts`")
    return [Relation(solver, name, tuple(c), (solver, name) not in untabled) for (solver, name), c in counts.items()], faults


def row_counts(corpus: Path, tasks: Path, ids: Sequence[str], rows: tuple[int, Path] | None = None) -> str:
    """The output of `arclog-cli row-counts` on the solvers `ids`, or on every
    solver of the corpus where there are none, with the rows of each model
    over `rows[0]` written under `rows[1]`."""
    over = ["--over", str(rows[0]), "--rows", str(rows[1])] if rows else []
    command = ["cargo", "run", "--profile", "tool", "-q", "-p", "arclog-cli", "--", "row-counts", *over, str(corpus), str(tasks), *ids]
    done = subprocess.run(command, cwd=checkout.ROOT / "engine", env=checkout.cargo_env(), stdout=subprocess.PIPE, text=True)
    if done.returncode not in (0, 1):  # 1: a solver faulted, and its line says so
        raise RuntimeError(f"{' '.join(command)} exited with {done.returncode}")
    return done.stdout


@dataclass(frozen=True)
class Signature:
    """What a rows file gives a comparison with another: its values per column."""

    relation: str
    path: Path
    rows: int
    names: tuple[str, ...]
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
    """The files within the cap of the relations the decode gives a table, by input and model."""


def written(rows_dir: Path, solver: str, untabled: frozenset[str] = frozenset()) -> Written:
    paths: dict[str, list[Path]] = defaultdict(list)
    over_cap: set[str] = set()
    peers: dict[tuple[str, int], list[Signature]] = defaultdict(list)
    for path in sorted((rows_dir / solver).rglob("*.json")):
        file = read_rows_file(path)
        paths[file.relation].append(path)
        if work(file) > WORK_CAP:
            over_cap.add(file.relation)
        elif file.relation not in untabled:
            names = tuple(name for name, _ in file.columns)
            types = tuple(ty for _, ty in file.columns)
            peers[file.input, file.model].append(Signature(file.relation, path, len(file.rows), names, types, column_values(file)))
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


@dataclass(frozen=True)
class Group:
    """Conjuncts of a body that share variables, and the variables they hold."""

    variables: set[str]
    items: list[list[Node]]


def groups(items: Sequence[list[Node]]) -> list[Group]:
    """The groups of conjuncts that share variables; a conjunct with no
    variable is a group of none."""
    parts: list[Group] = []
    for item in items:
        mine = Group(set(names(item_labels(item))), [item])
        apart = []
        for part in parts:
            if part.variables & mine.variables:
                mine = Group(mine.variables | part.variables, [*part.items, *mine.items])
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


def cell_instance(body: Body) -> str | None:
    """The rewrite of an `edge` of a `Distance` or `Propagation` instance that
    is one `neighbor` step between its two cells, with atoms of one variable
    each, on a cell or on the direction."""
    items = conjunction(body)
    if items is None or not is_cell_edge(body):
        return None
    assert body.component is not None  # an edge input has its instance
    steps = [item for item in items if item[0] == "neighbor"]
    if len(steps) != 1 or any(item_kind(item) is not Item.ATOM for item in items):
        return None
    labels = [strip(label) for label in atom_labels(steps[0])]
    cells = head_variables(body, [])
    if len(labels) != 3 or labels[0] == labels[2] or {labels[0], labels[2]} != cells or labels[1] in cells:
        return None
    if not all(len(variables := names(atom_labels(item))) == 1 and variables <= set(labels) for item in items if item is not steps[0]):
        return None
    return (
        f"The `edge` is the grid's `neighbor` steps between cells of a node set, which {CELL_FORMS[body.component]} "
        "takes from the node set alone: the table holds nothing the node set does not."
    )


def comparison_edge(body: Body) -> str | None:
    """The rewrite of an `edge` whose body orders two of its columns."""
    items = conjunction(body)
    if items is None or not is_cell_edge(body):
        return None
    cells = head_variables(body, [])
    for item in items:
        if item_kind(item) is Item.OP and item[0] in ORDERINGS and len(operands := names(item_labels(item))) == 2 and operands <= cells:
            first, second = (strip(label) for label in item_labels(item))
            return (
                f"The `edge` holds every pair of cells with `{first} {item[0]} {second}`, an order: "
                "the table holds nothing a score per cell does not."
            )
    return None


def columns_of(parts: Sequence[Group], columns: set[str]) -> str:
    """The columns that each group binds, one parenthesis for each."""
    return " and ".join(f"({quoted(sorted(part.variables & columns))})" for part in parts)


def product_body(body: Body) -> str | None:
    """The rewrite of a body that is two or more groups of conjuncts that
    share no variable, each binding a column; for a `Ray`'s `node`, also one
    group that binds a column beside a group that binds none, a guard."""
    items = conjunction(body)
    if items is None:
        return None
    parts = groups(items)
    columns = head_variables(body, [part.variables for part in parts])
    bound = [part for part in parts if part.variables & columns]
    guards = [part for part in parts if not part.variables & columns]
    if of_port(body, ("Ray",), "node"):
        if not bound or not (len(bound) > 1 or guards):
            return None
    elif len(bound) < 2 or guards:
        return None
    if guards:
        guard = quoted(sorted({str(head(item)) for part in guards for item in part.items}))
        return (
            f"The body is a guard ({guard}), conjuncts that bind no column, times the conjuncts that bind {columns_of(bound, columns)}: "
            "the guard tests once and adds nothing to the rows."
        )
    return (
        f"The body is {len(bound)} groups of conjuncts that share no variable, which bind {columns_of(bound, columns)}: "
        "the table is their product and holds nothing the groups do not."
    )


FORMS: tuple[tuple[Derivation, Callable[[Body], str | None]], ...] = (
    (Derivation.CELL_INSTANCE, cell_instance),
    (Derivation.PRODUCT, product_body),
    (Derivation.ORDER_OR_CLASS, comparison_edge),
)
"""The tests that read no rows, in the table's order, each by the form of the
clauses that make the relation, and each giving the rewrite of a body that has it."""


def restatement(file: RowsFile, peers: Mapping[tuple[str, int], Sequence[Signature]]) -> Finding | None:
    """The restatement the rows are, where they are those of another relation
    of the same input and model, or a projection of them onto columns of equal values."""
    types = [ty for _, ty in file.columns]
    values = column_values(file)
    for peer in peers[file.input, file.model]:
        if peer.relation == file.relation or peer.rows < len(file.rows):
            continue
        options = [[j for j in range(len(peer.types)) if peer.types[j] == ty and peer.values[j] == v] for ty, v in zip(types, values)]
        selections = [s for s in itertools.product(*options) if len(set(s)) == len(s)]
        if selections:
            rows = read_rows_file(peer.path).rows
            for selection in selections:
                if {tuple(row[j] for j in selection) for row in rows} == file.rows:
                    mine = quoted(name for name, _ in file.columns)
                    theirs = quoted(peer.names[j] for j in selection)
                    return Finding(
                        Derivation.RESTATEMENT,
                        f"The columns {mine} are the columns {theirs} of `{peer.relation}`: "
                        f"the table holds nothing `{peer.relation}` does not.",
                    )
    return None


def box_pair(file: RowsFile) -> tuple[int, int] | None:
    """The two columns of the least key where both are `Box` columns."""
    columns = least_key(file).columns
    return (columns[0], columns[1]) if len(columns) == 2 and all(file.columns[j][1] == BOX for j in columns) else None


def pair_kind(file: RowsFile) -> Finding | None:
    """What the pairs of the `Box` columns of the key are: the pairs of a
    total order or an equivalence, or a closure, where a smaller subrelation generates them."""
    pair = box_pair(file)
    if pair is None:
        return None
    a, b = pair
    (shape,) = pair_shapes(replace(file, columns=[file.columns[a], file.columns[b]], rows={(row[a], row[b]) for row in file.rows}))
    if not shape.transitive or shape.reduction is None or shape.reduction >= len(file.rows):
        return None
    pair_names = quoted(shape.columns)
    if shape.equivalence:
        return Finding(
            Derivation.ORDER_OR_CLASS,
            f"The pairs ({pair_names}) are an equivalence of {shape.classes} classes: the table holds nothing the classes do not.",
        )
    if shape.order == "total":
        return Finding(
            Derivation.ORDER_OR_CLASS,
            f"The pairs ({pair_names}) are a total order: the table holds nothing a score per cell does not.",
        )
    return Finding(
        Derivation.CLOSURE,
        f"The pairs ({pair_names}) are the closure of a step relation of {shape.reduction} pairs: "
        "the table holds nothing the steps do not.",
    )


def factored(file: RowsFile) -> Finding | None:
    found = best_factoring(file)
    if found is None or len(found.factors) < 2:
        return None
    relative = {name + ".rel": name for name in found.relative or []}
    factors = " and ".join(f"({quoted(relative.get(name, name) for name in names)})" for names, _ in found.factors)
    offsets = f", where {quoted(found.relative)} are offsets from `{found.base}`" if found.base and found.relative else ""
    return Finding(
        Derivation.PRODUCT,
        f"The rows are the join of their projections onto the columns {factors}{offsets}: "
        "the table holds nothing those parts do not.",
    )


def rows_tests(subject: Subject) -> list[Callable[[RowsFile], Finding | None]]:
    """The tests that read the rows of one file, in the table's order. A total
    order or an equivalence is named before the closure that it is."""

    def restated(file: RowsFile) -> Finding | None:
        return restatement(file, subject.peers)

    def lib_pair(file: RowsFile) -> Finding | None:
        read = sorted({str(atom[0]) for body in subject.bodies for atom in deep_atoms(body.items) if atom[0] in LIB_PAIRS})
        pair = box_pair(file)
        if not read or pair is None:
            return None
        a, b = (file.columns[j][0] for j in pair)
        return Finding(
            Derivation.LIB_RELATION,
            f"The pairs (`{a}`, `{b}`) of cells are what {quoted(read)} gives, restricted to a cell set: "
            f"the table holds nothing {quoted(read)} and that cell set do not.",
        )

    return [restated, factored, pair_kind, lib_pair]


def on_every_file(paths: Sequence[Path], test: Callable[[RowsFile], Finding | None]) -> Finding | None:
    """What `test` derives on every rows file, read one at a time, with the
    rewrite of the largest file that gives that test; a closure where it
    derives an order on some and a closure on others."""
    found: list[tuple[int, Finding]] = []
    for path in paths:
        file = read_rows_file(path)
        derived = test(file)
        if derived is None:
            return None
        found.append((len(file.rows), derived))
    tests = {finding.test for _, finding in found}
    chosen = tests.pop() if len(tests) == 1 else Derivation.CLOSURE
    return max(((size, finding) for size, finding in found if finding.test is chosen), key=lambda sized: sized[0])[1]


def residual(subject: Subject) -> str:
    """The key and bits per row of the largest rows file, or the reason the rows were not read."""
    if subject.paths is None:
        return f"Its rows were not read ({subject.unread}), so only the tests on the clauses ran, and none derives it."
    largest = ""
    best = -1
    for path in subject.paths:
        file = read_rows_file(path)
        if len(file.rows) > best:
            key = least_key(file)
            best = len(file.rows)
            largest = f"Its least key is {quoted(file.columns[j][0] for j in key.columns)}, at {bits_per_row(key, best):.1f} bits per row."
    return f"No test derives it. {largest} Rewriting it takes a reading of the task."


def derive(subject: Subject) -> Finding:
    """The first test that derives the relation, and its rewrite, or `none` and its residual. The tests that read no rows come first."""
    for test, form in FORMS:
        rewrites = [form(body) for body in subject.bodies]
        if rewrites and all(rewrites):
            return Finding(test, " ".join(dict.fromkeys(rewrite for rewrite in rewrites if rewrite)))
    if subject.paths is not None:
        for rows_test in rows_tests(subject):
            if (found := on_every_file(subject.paths, rows_test)) is not None:
                return found
    return Finding(Derivation.NONE, residual(subject))


def solver_lines(corpus: Path, rows_dir: Path, solver: str, flagged: Sequence[Relation], fault: str | None = None,
                 untabled: frozenset[str] = frozenset()) -> list[str]:
    """The lines of one solver's flagged relations; `fault` is the fault of
    the run that wrote its rows, where it had one, and `untabled` the
    relations the decode gives no table, which no relation restates."""
    concept = [body for body in bodies(solver, arclog(corpus, solver)) if not body.in_alt()]
    files = written(rows_dir, solver, untabled)
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
        found = derive(subject)
        lines.append(f"{solver} {relation.name} {','.join(map(str, relation.counts))} {found.test} {found.rewrite}")
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
            untabled = frozenset(r.name for r in relations if r.solver == solver and not r.tabled)
            lines[solver] = solver_lines(corpus, Path(rows_dir), solver, [r for r in flagged if r.solver == solver], dump_faults.get(solver), untabled)
    return [line for solver in sorted(lines) for line in lines[solver]]


MEASURES = checkout.ROOT / "work" / "table-information" / "measures"
"""The cached `row-counts` output of each solver text, one file per solver and hash of the text and the tools."""


def tools_key() -> str:
    """The committed trees of the engine, the converter and the lib, which the row counts of a solver text depend on."""
    trees = ["HEAD:engine", "HEAD:src/arclog_convert", "HEAD:programs/lib", "HEAD:programs/lib.dl"]
    return subprocess.run(["git", "rev-parse", *trees], cwd=checkout.ROOT, capture_output=True, text=True, check=True).stdout


def committed(solver: str) -> str:
    """The solver's text as committed."""
    return subprocess.run(["git", "show", f"HEAD:programs/solvers/{solver}.dl"], cwd=checkout.ROOT, capture_output=True, text=True, check=True).stdout


def counts_of(solver: str, text: str) -> str:
    """The `row-counts` output of the solver whose file holds `text`: converted and counted apart from the corpus, and cached by the hash of the text and the tools."""
    key = hashlib.sha256((tools_key() + text).encode()).hexdigest()[:20]
    cached = MEASURES / f"{solver}-{key}.txt"
    if cached.exists():
        return cached.read_text()
    with tempfile.TemporaryDirectory() as scratch:
        programs, out = Path(scratch) / "programs", Path(scratch) / "out"
        solvers = programs / "solvers"
        solvers.mkdir(parents=True)
        for entry in (checkout.ROOT / "programs").iterdir():  # what a solver's includes reach
            if entry.name != "solvers":
                (programs / entry.name).symlink_to(entry)
        (solvers / f"{solver}.dl").write_text(text)
        plan = arclog_convert.out() / "plan" / f"{solver}.txt"
        checkout_solvers = checkout.ROOT / "programs" / "solvers"
        if plan.exists() and (checkout_solvers / f"{solver}.dl").read_text() == text:
            was = plans.PLAN_HASH + plans.inputs_hash(solver, checkout_solvers)
            kept = plan.read_text()
            if was in kept.splitlines():  # the plan of this text: it records the inputs hash under the scratch solvers directory
                (out / "plan").mkdir(parents=True)
                (out / "plan" / plan.name).write_text(kept.replace(was, plans.PLAN_HASH + plans.inputs_hash(solver, solvers)))
        done = subprocess.run([sys.executable, "-m", "arclog_convert.convert", "--out", str(out), solver], cwd=checkout.ROOT,
                              env={**os.environ, "ARCLOG_SOLVERS": str(solvers)}, capture_output=True, text=True)
        if done.returncode != 0:
            raise RuntimeError(f"the conversion of {solver} failed:\n{done.stdout}{done.stderr}")
        got = row_counts(arclog_convert.corpus(out), TASKS_DIR, [solver])
        names = json.loads((out / "names" / f"{solver}.json").read_text())
    MEASURES.mkdir(parents=True, exist_ok=True)
    cached.with_suffix(".names.json").write_text(json.dumps(names))
    cached.write_text(got)
    return got


def sourced(solver: str, text: str) -> set[str]:
    """The arclog relation names whose source is a relation of the solver whose file holds `text`: each the converter's name map traces to one, and each input of an instance that the text writes under the instance's own name, from the cache `counts_of` writes."""
    key = hashlib.sha256((tools_key() + text).encode()).hexdigest()[:20]
    names = json.loads((MEASURES / f"{solver}-{key}.names.json").read_text())
    got = set(names.get("relations", {}))
    for instance, sources in names.get("instances", {}).items():
        for source in sources:
            if source.get("path"):
                for port in re.findall(rf"^\s*{re.escape(source['path'])}\.(\w+)\(", text, re.M):
                    got.add(f"{instance}.{port}")
    return got


def tables(text: str) -> dict[str, Relation]:
    """The relations of one solver's `row-counts` output that the decode gives a table, other than the task's facts and `&output`."""
    relations, _ = read_counts(text)
    return {r.name: r for r in relations if r.tabled and r.name not in FACTS | {OUTPUT}}


def summary(relations: Mapping[str, Relation]) -> tuple[int, int, int, int]:
    """The largest table, the tables over 4,000 rows and over `THRESHOLD` rows, and the rows of those over `THRESHOLD`, each table's rows summed over the inputs."""
    totals = [r.total for r in relations.values()]
    return max(totals, default=0), sum(t > CAP for t in totals), sum(t > THRESHOLD for t in totals), sum(t for t in totals if t > THRESHOLD)


def lib_instances(text: str) -> Counter[str]:
    """The instances of the lib's components in a solver's text, by component: each `.init` of a component the file does not define."""
    own = set(re.findall(r"^\s*\.comp\s+(\w+)", text, re.M))
    return Counter(c for c in re.findall(r"^\s*\.init\s+\w+\s*=\s*(\w+)", text, re.M) if c not in own)


def measure(solver: str, before: str, after: str, texts: tuple[str, str] = ("", ""), sources: set[str] | None = None) -> list[str]:
    """Each table of the solver whose rows, summed over the inputs, exceed 100 before or after, then the summary of both and whether the solver's tables got smaller.
    An edit that removes an instance of a lib component is worse whatever its tables: the instance states a claim of the task, and an edit keeps it."""
    old, new = tables(before), tables(after)
    shown = sorted((name for name in old.keys() | new.keys() if max(old[name].total if name in old else 0, new[name].total if name in new else 0) > 100),
                   key=lambda name: -max(old[name].total if name in old else 0, new[name].total if name in new else 0))
    def origin(name: str) -> str:
        return "" if sources is None or name in sources else "  (no relation of the solver is its source: report it, do not rewrite around it)"
    lines = [f"{solver} {name} {old[name].total if name in old else '-'} -> {new[name].total if name in new else '-'}{origin(name)}" for name in shown]
    a, b = summary(old), summary(new)
    lines.append(f"{solver} largest table {a[0]} -> {b[0]}; tables over {CAP} {a[1]} -> {b[1]}; tables over {THRESHOLD} {a[2]} -> {b[2]}, with {a[3]} -> {b[3]} rows")
    removed = sorted((lib_instances(texts[0]) - lib_instances(texts[1])).elements())
    if removed:
        verdict = f"worse: the edit removes an instance of {', '.join(f'`{c}`' for c in removed)}; keep each lib component instance, and where its encoding makes a table large, report it"
    elif b[0] > a[0] or b[1] > a[1]:
        verdict = f"worse: the largest table is larger, or more tables are over {CAP} rows"
    elif b[3] < a[3] or b[0] < a[0]:
        verdict = f"better: the largest table is no larger, no more tables are over {CAP} rows, and the largest table or the tables over {THRESHOLD} rows hold fewer rows"
    else:
        verdict = "no change"
    lines.append(f"{solver} {verdict}")
    return lines


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m study.table_lint", description=(__doc__ or "").split("\n\n")[0])
    parser.add_argument("--corpus", type=Path, default=corpus_dir(), help="the directory of the arclog files, `corpus_dir()` by default: `programs/arclog/` in the main worktree, `work/arclog/gen/` in a linked one")
    parser.add_argument("--measure", action="store_true", help="print each given solver's tables as committed and as its file now holds them, then its lint lines")
    parser.add_argument("task_ids", nargs="*", help="the solvers to lint, every solver of the corpus by default")
    args = parser.parse_args(argv)
    if args.measure:
        if not args.task_ids:
            parser.error("--measure takes task ids")
        for solver in args.task_ids:
            now = checkout.ROOT / "programs" / "solvers" / f"{solver}.dl"
            old, new = committed(solver), now.read_text()
            before, after = counts_of(solver, old), counts_of(solver, new)
            for line in measure(solver, before, after, (old, new), sourced(solver, old) | sourced(solver, new)):
                print(line, flush=True)
    if args.task_ids and args.corpus == corpus_dir():
        reconvert(args.task_ids)
    for line in lint(args.corpus, TASKS_DIR, args.task_ids):
        print(line, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
