"""Mutates the `.arclog` texts of the corpus solvers as s-expressions and runs each mutant through the reader, the checker and the
evaluator of an `arclog-cli` build, and prints a line for each finding.

    scripts/run_heavy.py --cpus <n> --need idle uv run python engine/arclog-py/mutation_run.py --cli <arclog-cli> --jobs <n> [options] [<task id> ...]

The run is started by hand, such as after a change to the reader, the checker or the evaluator. It is no test and no condition of a
merge: no test suite, merge step or gate runs it. It needs no `arclog` package: it runs the subcommands `stream`, `decode` and
`tables` of the build that `--cli` gives, so it runs against any build.

Options:
  --cli <path>            the `arclog-cli` binary (required; a build with the `tool` profile, since `decode` and `tables` need an
                          optimized build)
  --corpus <dir>          the corpus of solvers (default `programs/arclog`)
  --tasks <dir>           the task files (default `data/tasks`)
  --out <dir>             where the mutants are kept (default `work/arclog/mutation`)
  --operators <a,b,...>   the operators to run (default every operator; the names are the keys of `OPERATORS`)
  --per-operator <k>      mutants of each operator per solver (default 1)
  --limit <n>             the most mutants of the run; each operator has the share `n // k` of the `k` operators, and the first `n mod k`
                          operators of `--operators` have one more; each operator's mutants are taken from the solvers in the order of a
                          shuffle by `--seed`, up to its share, and solvers are read until every share is met or none is left
  --seed <s>              the seed of every draw (default 0); a run is the same at every `--jobs`
  --jobs <n>              mutants run in parallel (default 1)
  <task id> ...           the solvers to mutate (default every solver of the corpus)

The operators, with the rule of `docs/arclog/` that gives the verdict of their mutants where one stands (`departs` needs one):
  zero            `0` for a label at a site, or at the second place of a `!=`, `<`, `<=`, `>` or `>=`; or `(!= X 0)` added after a
                  site that makes X. Rule (`docs/arclog/arclog.md`, Negation and constraints): a constraint with `0` as its second label is
                  refused unless the first label is a number, a Box, a Position or an Offset; a site is refused unless its column is one of
                  those four. The reader gives a Position and an Offset the Box type, so `0` against either is the zero box.
  fresh-again     a bare label at a site becomes `*X` where an earlier site of the body makes X. Rule (`docs/arclog/arclog.md`, Sites): refused.
  proposer-body   a proposer name put before the body of a `DET`, or a body atom put after the proposer of a `DET` that names one.
                  Rule (`docs/arclog/arclog.md`, Program): a `DET` that names a proposer has no body, so refused.
  rigid-lib-part  an atom of a lib relation added as a part of a `RIGID_DET`, with a site for each column whose type is the type of a label
                  that a part makes (the first such label in the order of the parts, whatever its name). Rule (`docs/arclog/rigid.md`,
                  Form, and the safety condition of `docs/engine/reader.md`): a part is a clause of its own and reads no label that
                  another part makes, so refused where the lib relation has modes and accepted where it enumerates.
  literal, column, mark, drop-site, repeat-site, drop-atom, repeat-atom
                  a number, constant or string for another; a site's column for another of its relation; `*X` to `X` or `X` to `^X`;
                  a site or an atom dropped or repeated. No rule gives a verdict.
The types of the columns of a lib relation come from `engine/lib/registry.sexpr`; a site of any other relation gets no expected verdict.
A label's type is the meet, over the lattice of `docs/engine/reader.md`, of the types of its sites in its clause outside `NOT` atoms; the
type of a site of a relation that a clause names as its own is the meet of the types of the label of its column's name in each such clause.
A label with no typed site, or whose types have no meet, gets no expected verdict.

A mutant is the text of a solver's `.arclog` with one span replaced, so its comments and layout stand. Each mutant has a directory of
its own under `--out`, with its `.arclog`, the `.arcdata` of the solver and the files of each solver that `.arcdata` names. Each stage
of a mutant runs under a bound of 60 s of CPU time, with a backstop of 600 s on the wall clock, and with `ARCLOG_THREADS=1`. `arclog-cli stream` gives the reader's verdict and the
checker's verdict on the concept case alone. Of a mutant that `stream` accepts, `arclog-cli decode --no-rows` checks each case it
decodes, runs the evaluator and replays the decoder, and `arclog-cli tables --bodies` runs the step tables. A mutant is refused where
`stream` refuses it, or where `decode` reports that the checker refuses a case (a fault line `a fault that stops the decode: the checker
refuses the case ...`), and the verdict of the mutant is then that refusal: `departs` and `no-cause` read it, the mutant gets no
`run-fault` for that line and no `tables` stage. A solver whose own file `stream` refuses, or whose own file `decode` reports such a
refusal, is left out of the run, and a kind of fault that `decode` gives on the solver's own file is no finding of its mutants.

Each finding is one line, `<kind> <task> <operator> <mutant dir>: <message>`, and its mutant's directory stays under `--out` for a
rerun, `arclog-cli stream <mutant dir>/<task>.arclog`. The kinds:
  panic     a stage panics, or ends by a signal.
  departs   an operator whose rule in `docs/arclog/` gives the verdict of its mutant, and the verdict of the build, as above, differs from it.
  run-fault an accepted mutant whose `decode` gives a fault, a refused case or a case differing in consistency, or a case with no
            solves outcome because the determination or the judged run faults (a program that no assignment solves, a case that stops
            at a bound, or whose parameters are underdetermined, is an outcome of a mutation and no finding), or whose `tables` fails
            where `decode` found nothing.
  no-cause  a refusal whose message is empty or has no text after the prefixes that give the stage and the case, such as
            `a fault that stops the stream: the checker refuses the case concept:`.
  stopped   a stage passes its CPU bound or its wall-clock bound.
The directories of mutants with no finding are removed. The last line gives, per operator, the mutants run, accepted, refused and the
findings. The exit status is 0 where the run ended, with findings or none.
"""
import argparse, dataclasses, enum, os, random, re, shutil, signal, subprocess, sys, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from arclog_convert.readback import read_checked  # every file of the corpus is read through it: the corpus is the converter's directory of converted solvers
STAGE_BOUND = 60  # seconds of CPU time
WALL_BOUND = 10 * STAGE_BOUND  # seconds on the wall clock, for a process that waits without using CPU
CONSTRAINT_OPS = ("=", "!=", "<", "<=", ">", ">=")
TYPE_UNDER = {"C4": "D4", "Dir": "Dir8", "DiagDir": "Dir8", "Axis": "Axis4", "DiagAxis": "Axis4", "Position": "Box", "Offset": "Box"}  # docs/engine/reader.md: a type to the type above it
CLAUSE_HEADS = ("RULE", "DET", "RIGID_DET", "INIT")  # the clauses that name a relation as their own, by their second item
BOX_TYPES = ("Box", "Position", "Offset")  # the three types of the box algebra
ZERO_TYPES = ("number", *BOX_TYPES)  # docs/arclog/arclog.md: the columns at which a site may hold `0`, and the first labels of a constraint with `0` second
REFUSAL_PREFIX = re.compile(r"(a fault that stops the (?:stream|decode):\s*)?(the checker refuses the case \S+:\s*|the solver's files do not read:\s*)?")
CASE_REFUSAL = re.compile(r"a fault that stops the decode:\s*the checker refuses the case\b")  # a `decode` line: the checker refuses a case
INTEGER = re.compile(r"\d+")


# ---- s-expressions with character spans

class NodeKind(enum.Enum):
    ATOM = "atom"
    STRING = "string"
    LIST = "list"


@dataclasses.dataclass(eq=False)
class Node:
    kind: NodeKind
    start: int
    end: int
    src: str
    items: list["Node"] = dataclasses.field(default_factory=list)
    parent: "Node | None" = None

    @property
    def text(self):
        return self.src[self.start:self.end]

    @property
    def head(self):
        """The text of a list's first item when that is an atom."""
        return self.items[0].text if self.kind == NodeKind.LIST and self.items and self.items[0].kind == NodeKind.ATOM else None


def read(src):
    """The top-level s-expressions of `src`, with spans; `ValueError` on unbalanced parentheses."""
    top, stack, i, n = [], [], 0, len(src)

    def add(node):
        node.parent = stack[-1] if stack else None
        (stack[-1].items if stack else top).append(node)

    while i < n:
        c = src[i]
        if c.isspace():
            i += 1
        elif c == ";":
            j = src.find("\n", i)
            i = n if j < 0 else j
        elif c == "(":
            node = Node(NodeKind.LIST, i, -1, src)
            add(node)
            stack.append(node)
            i += 1
        elif c == ")":
            if not stack:
                raise ValueError(f"unbalanced ) at {i}")
            stack.pop().end = i + 1
            i += 1
        elif c == '"':
            j = i + 1
            while j < n and src[j] != '"':
                j += 2 if src[j] == "\\" else 1
            add(Node(NodeKind.STRING, i, j + 1, src))
            i = j + 1
        else:
            j = i
            while j < n and not src[j].isspace() and src[j] not in '()";':
                j += 1
            add(Node(NodeKind.ATOM, i, j, src))
            i = j
    if stack:
        raise ValueError("unbalanced (")
    return top


def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node.items)


# ---- the lib's relations

class FindingKind(enum.Enum):
    PANIC = "panic"
    DEPARTS = "departs"
    RUN_FAULT = "run-fault"
    NO_CAUSE = "no-cause"
    STOPPED = "stopped"


class Bound(enum.Enum):
    CPU = enum.auto()
    WALL = enum.auto()


@dataclasses.dataclass
class Relation:
    columns: list[tuple[str, str | None]]  # name and type text; None for a macro's columns
    modes: list[set[str]]  # the sets of columns of which one must be bound; empty for a relation that enumerates
    is_fact: bool


class Lib:
    """The relations of `engine/lib/registry.sexpr` and the constants of its types."""

    def __init__(self, path):
        self.relations: dict[str, Relation] = {}
        self.groups: dict[str, list[list[str]]] = {}  # a constant's name to the constants of each type that holds it
        for form in read(path.read_text()):
            kind = form.head
            if kind in ("relation", "fact", "macro"):
                columns, modes = [], []
                for part in form.items[2:]:
                    if part.head == "columns":
                        columns = [(c.items[0].text, c.items[1].text if kind != "macro" else None) for c in part.items[1:]]
                    elif part.head == "modes":
                        modes = [{c.text for c in mode.items} for mode in part.items[1:]]
                self.relations[form.items[1].text] = Relation(columns, modes, kind == "fact")
            elif kind == "constants":
                members = [m.text for m in form.items[2:]]
                for name in members:
                    self.groups.setdefault(name, []).append(members)

    def lib_relations(self):
        return {name: rel for name, rel in self.relations.items() if not rel.is_fact and all(t for _, t in rel.columns)}


# ---- sites and atoms

@dataclasses.dataclass
class Site:
    node: Node
    column: str
    labels: list[Node]  # the atom labels directly in the site
    elided: bool

    @property
    def label(self):
        """The one label token of the site, or None."""
        return self.labels[0] if len(self.labels) == 1 and (self.elided or len(self.node.items) == 2) else None


def site_of(node):
    if node.kind == NodeKind.ATOM:
        return Site(node, node.text.lstrip("*^"), [node], True)
    if node.kind == NodeKind.LIST and node.items and node.items[0].kind == NodeKind.ATOM and node.items[0].text.startswith(":"):
        return Site(node, node.items[0].text[1:], [n for n in node.items[1:] if n.kind == NodeKind.ATOM], False)
    return None


def atom_sites(node, lib):
    """The sites of `node` where it is an atom: a list headed by a relation, whose items are sites."""
    head = node.head
    if head is None or not (head in lib.relations or head.startswith("&")) or len(node.items) < 2:
        return None
    sites = [site_of(item) for item in node.items[1:]]
    return None if None in sites else sites


def meet(a, b):
    """The lower of two types where one is the other or is under it, else None."""
    if a == b or TYPE_UNDER.get(a) == b:
        return a
    return b if TYPE_UNDER.get(b) == a else None


def meet_all(types):
    """The meet of the types, None where there are none or two have no meet."""
    types = iter(types)
    result = next(types, None)
    for t in types:
        if result is None:
            return None
        result = meet(result, t)
    return result


def bare(label):
    return label.text.lstrip("*^")


def mark(label):
    return label.text[:len(label.text) - len(bare(label))]


class Context:
    """One solver's text, its s-expressions, and what the operators read off them."""

    def __init__(self, task, src, lib, proposers):
        self.task, self.src, self.lib, self.proposers = task, src, lib, proposers
        self.tree = read(src)
        self.atoms = {id(n): s for n in walk(self.tree) if (s := atom_sites(n, lib)) is not None}
        self.owners: dict[str, list[Node]] = {}  # a relation's name to the clauses that name it as their own
        for clause in self.clauses(*CLAUSE_HEADS):
            self.owners.setdefault(clause.items[1].text, []).append(clause)
        self.label_types: dict[tuple[int, str], str | None] = {}  # (clause, label name) to the label's type, for the results that no cycle cut
        self.typing: set[tuple[int, str]] = set()
        self.cuts = 0

    def clauses(self, *heads):
        return [n for n in walk(self.tree) if n.kind == NodeKind.LIST and n.head in heads and len(n.items) >= 2]

    def body_atoms(self, clause):
        """The atoms that are items of the clause's body, in order."""
        return [k for k in clause.items[2:] if id(k) in self.atoms]

    def column_type(self, atom, site):
        rel = self.lib.relations.get(atom.head)
        return dict(rel.columns).get(site.column) if rel else None

    def site_types(self, atom, site):
        """The types that a site gives its label: its column's type for a lib relation, else the types of the same-named label in each clause that names the relation."""
        column = self.column_type(atom, site)
        if column:
            return [column]
        return [t for clause in self.owners.get(atom.head, []) if (t := self.label_type(clause, site.column))]

    def label_type(self, clause, label):
        """The meet of the types of the sites of the label named `label` in `clause`, outside `NOT` atoms; None where it has no meet. A
        relation that is defined through itself gives no type at its second visit."""
        key = (id(clause), label)
        if key in self.label_types:
            return self.label_types[key]
        if key in self.typing:
            self.cuts += 1
            return None
        self.typing.add(key)
        cuts = self.cuts
        types = []
        for atom in walk([clause]):
            if id(atom) in self.atoms and not self.inside_not(clause, atom):
                for site in self.atoms[id(atom)]:
                    if site.label is not None and bare(site.label) == label:
                        types += self.site_types(atom, site)
        self.typing.discard(key)
        result = meet_all(types)
        if self.cuts == cuts:
            self.label_types[key] = result
        return result

    @staticmethod
    def inside_not(clause, atom):
        node = atom.parent
        while node is not clause:
            if node.head == "NOT":
                return True
            node = node.parent
        return False

    def indent_of(self, node):
        line = self.src.rfind("\n", 0, node.start) + 1
        return re.match(r"[ \t]*", self.src[line:]).group()


@dataclasses.dataclass
class Edit:
    start: int
    end: int
    new: str
    expected: bool | None = None  # whether a line of docs/arclog/ makes `stream` accept the mutant
    note: str = ""
    variant: str = ""  # the draw takes the variants of an operator in turn


def replace(node, new, **kw):
    return Edit(node.start, node.end, new, **kw)


def removal(node):
    prev = node.parent.items[node.parent.items.index(node) - 1]
    return Edit(prev.end, node.end, "")


def insertion_after(ctx, node, text, **kw):
    return Edit(node.end, node.end, "\n" + ctx.indent_of(node) + text, **kw)


def site_label_edit(site, new, **kw):
    """The edit that gives the site the label text `new`: the label token, or the whole token of an elided site."""
    if site.elided:
        return replace(site.node, f"(:{site.column} {new})", **kw)
    return replace(site.label, new, **kw)


# ---- the operators

def direct_sites(ctx):
    """Each (clause, atom, site) where the atom is an item of the body of a `RULE` or `DET` clause."""
    for clause in ctx.clauses("RULE", "DET"):
        for atom in ctx.body_atoms(clause):
            for site in ctx.atoms[id(atom)]:
                yield clause, atom, site


def zero(ctx):
    edits = []
    for clause, atom, site in direct_sites(ctx):
        column = ctx.column_type(atom, site)
        label = site.label
        if column is None or label is None or bare(label) == "0" or mark(label) == "^":
            continue
        allowed = column in ZERO_TYPES
        expected = False if not allowed else (True if mark(label) == "" else None)
        note = f"`0` at a {column} column of {atom.head}"
        edits.append(site_label_edit(site, "0", expected=expected, note=note, variant="site"))
        if mark(label) == "*":
            edits.append(insertion_after(ctx, atom, f"(!= {bare(label)} 0)", expected=column in ZERO_TYPES, note=f"`(!= {bare(label)} 0)` over a {column} column of {atom.head}", variant="added"))
    for clause in ctx.clauses("RULE", "DET"):
        for item in clause.items[2:]:
            if item.kind == NodeKind.LIST and item.head in CONSTRAINT_OPS and item.head != "=" and len(item.items) == 3:
                first, second = item.items[1], item.items[2]
                if first.kind != NodeKind.ATOM or second.kind != NodeKind.ATOM or bare(second) in ("0", "") or INTEGER.fullmatch(second.text):
                    continue
                column = ctx.label_type(clause, bare(first))
                # docs/arclog/arclog.md: `0` as the second label is refused unless the first label is a number, a Box, a Position or an
                # Offset. No line gives a verdict for the ordering operators on a Box, a Position or an Offset.
                expected = None if column is None or (column in BOX_TYPES and item.head != "!=") else column in ZERO_TYPES
                edits.append(replace(second, "0", expected=expected, note=f"`0` as the second label of `{item.head}` over a {column} label", variant="constraint"))
    return edits


def fresh_again(ctx):
    edits = []
    for clause in ctx.clauses("RULE", "DET"):
        made = set()
        for atom in ctx.body_atoms(clause):
            for site in ctx.atoms[id(atom)]:
                label = site.label
                if label is None:
                    continue
                if mark(label) == "" and bare(label) in made:
                    edits.append(site_label_edit(site, "*" + label.text, expected=False, note=f"`*{label.text}` at a second site that makes it"))
            for site in ctx.atoms[id(atom)]:
                if site.label is not None and mark(site.label) == "*":
                    made.add(bare(site.label))
    return edits


def proposer_body(ctx):
    """A proposer put before the body of a `DET` that has one, and a body put after the proposer of a `DET` that names one."""
    edits = []
    for clause in ctx.clauses("DET"):
        if len(clause.items) > 2 and id(clause.items[2]) in ctx.atoms:
            for name in ctx.proposers:
                edits.append(Edit(clause.items[2].start, clause.items[2].start, name + " ", expected=False, note=f"the proposer {name} before the body", variant="before"))
        elif len(clause.items) == 3 and clause.items[2].kind == NodeKind.ATOM:
            for name, rel in sorted(ctx.lib.lib_relations().items()):
                if not rel.modes:
                    atom = f"({name} *{rel.columns[0][0]})"
                    edits.append(Edit(clause.items[2].end, clause.items[2].end, " " + atom, expected=False, note=f"the body {atom} after the proposer {clause.items[2].text}", variant="after"))
    return edits


def rigid_parts(form):
    """The part items of a `RIGID_DET` form, inside its `key` and `instance` clauses where it has them."""
    kids = form.items[2:]
    for kid in kids:
        if kid.kind == NodeKind.LIST and kid.head in ("key", "instance"):
            return rigid_parts(kid)
    return kids


def rigid_lib_part(ctx):
    edits = []
    for form in ctx.clauses("RIGID_DET"):
        parts = [p for p in rigid_parts(form) if id(p) in ctx.atoms]
        if not parts:
            continue
        made = {}  # a type to the first label in the order of the parts that a part makes with it
        for p in parts:
            for s in ctx.atoms[id(p)]:
                if s.label is not None and mark(s.label) == "*" and (t := ctx.label_type(form, bare(s.label))):
                    made.setdefault(t, bare(s.label))
        for name, rel in sorted(ctx.lib.lib_relations().items()):
            columns = [(c, made[t]) for c, t in rel.columns if t in made]
            if columns and (not rel.modes or any(mode <= {c for c, _ in columns} for mode in rel.modes)):
                text = "(" + " ".join([name] + [f"(:{c} {label})" for c, label in columns]) + ")"
                edits.append(insertion_after(ctx, parts[-1], text, expected=not rel.modes, note=f"the lib atom {text} as a part"))
    return edits


def literal(ctx):
    edits = []
    for node in walk(ctx.tree):
        if node.parent is None:
            continue
        if node.kind == NodeKind.ATOM and INTEGER.fullmatch(node.text):
            value = int(node.text)
            edits += [replace(node, str(other), note="another number", variant="number") for other in sorted({value + 1, value + 2, max(value - 1, 1), 9} - {value})]
        elif node.kind == NodeKind.ATOM and node.text in ctx.lib.groups:
            edits += [replace(node, other, note="another constant of its type", variant="constant") for other in ctx.lib.groups[node.text][0] if other != node.text]
        elif node.kind == NodeKind.STRING:
            edits.append(replace(node, '"x"', note="another string", variant="string"))
    return edits


def column(ctx):
    edits = []
    for clause, atom, site in direct_sites(ctx):
        rel = ctx.lib.relations.get(atom.head)
        if rel is None:
            continue
        for other, _ in rel.columns:
            if other != site.column:
                if site.elided:
                    edits.append(replace(site.node, f"(:{other} {site.node.text})", note=f"column {other} of {atom.head}"))
                else:
                    edits.append(replace(site.node.items[0], ":" + other, note=f"column {other} of {atom.head}"))
    return edits


def mark_op(ctx):
    edits = []
    for clause, atom, site in direct_sites(ctx):
        label = site.label
        if label is None or bare(label) == "0":
            continue
        if mark(label) == "*":
            edits.append(replace(label, bare(label), note="`*` removed"))
        elif mark(label) == "":
            edits.append(replace(label, "^" + label.text, note="`^` added"))
    return edits


def drop_site(ctx):
    return [removal(site.node) for _, _, site in direct_sites(ctx)]


def repeat_site(ctx):
    return [Edit(site.node.end, site.node.end, " " + site.node.text) for _, atom, site in direct_sites(ctx)]


def drop_atom(ctx):
    return [removal(atom) for clause in ctx.clauses("RULE", "DET", "RIGID_DET") for atom in ctx.body_atoms(clause)]


def repeat_atom(ctx):
    return [insertion_after(ctx, atom, atom.text) for clause in ctx.clauses("RULE", "DET", "RIGID_DET") for atom in ctx.body_atoms(clause)]


OPERATORS = {"zero": zero, "fresh-again": fresh_again, "proposer-body": proposer_body, "rigid-lib-part": rigid_lib_part, "literal": literal,
             "column": column, "mark": mark_op, "drop-site": drop_site, "repeat-site": repeat_site, "drop-atom": drop_atom, "repeat-atom": repeat_atom}


# ---- the run

@dataclasses.dataclass
class Mutant:
    index: int
    task: str
    operator: str
    text: str
    expected: bool | None
    note: str


def proposer_pool(corpus):
    """The proposer names that some `DET` of the corpus states in place of a body, sorted."""
    pool = set()
    for path in Path(corpus).glob("*.arclog"):
        pool.update(re.findall(r"\(DET\s+&[\w.]+\s+([A-Z]\w*)\s*\)", read_checked(path)))
    return sorted(pool)


def draw(ctx, operators, per_operator, seed):
    mutants = []
    for name in operators:
        edits = OPERATORS[name](ctx)
        edits = [e for e in edits if ctx.src[:e.start] + e.new + ctx.src[e.end:] != ctx.src]
        rng = random.Random(f"{seed}/{ctx.task}/{name}")
        variants = {}
        for edit in edits:
            variants.setdefault(edit.variant, []).append(edit)
        for group in variants.values():
            rng.shuffle(group)
        order = list(variants.values())
        rng.shuffle(order)
        turns = [group[turn] for turn in range(max(map(len, order), default=0)) for group in order if turn < len(group)]
        for edit in turns[:per_operator]:
            text = ctx.src[:edit.start] + edit.new + ctx.src[edit.end:]
            mutants.append(Mutant(-1, ctx.task, name, text, edit.expected, edit.note))
    return mutants


def share_of_limit(limit, operators):
    """Each operator's share of `limit` mutants: `limit // k` of the `k` operators, one more for the first `limit mod k`; None without a limit."""
    if limit is None:
        return None
    base, extra = divmod(limit, len(operators))
    return {o: base + (i < extra) for i, o in enumerate(operators)}


def named_solvers(corpus, task):
    """`task` and the solvers that its `.arcdata` names by `representative`, transitively."""
    found, todo = [], [task]
    while todo:
        name = todo.pop()
        if name not in found:
            found.append(name)
            path = Path(corpus) / f"{name}.arcdata"
            if path.exists():
                todo += re.findall(r"\(representative\s+(\w+)", read_checked(path))
    return found


FAULT_LINES = ("first case refused", "first case differing in consistency", "first case with no solves outcome", "a fault that stops the decode")
FAILURE_LINES = ("first case ", FAULT_LINES[3])  # the two forms in which `decode` writes a failure line, which gives it a non-zero exit


def decode_faults(task, output):
    """The (kind, line) of each line of `decode`'s output for `task` that reports a fault; the kind is the line's opening. A case with
    no solves outcome is a fault where the determination or the judged run faults, and no fault where no assignment solves."""
    found = []
    for line in output.splitlines():
        body = line.removeprefix(f"{task}: ")
        for kind in FAULT_LINES:
            if body.startswith(kind) and (kind != FAULT_LINES[2] or "faults at" in body):
                found.append((kind, body))
    return found


def case_refusals(faults):
    """The bodies of the fault lines of `faults` that report that the checker refuses a case."""
    return [body for _, body in faults if CASE_REFUSAL.match(body)]


def one_line(text, bound=300):
    return " ".join(text.split())[:bound]


class Runner:
    def __init__(self, args):
        self.args = args
        self.env = {**os.environ, "ARCLOG_THREADS": "1"}
        self.originals: dict[str, set[str] | None] = {}  # a task to the kinds of fault of its own file, None where `stream` or `decode` refuses the file
        self.guard = threading.Lock()
        self.locks: dict[str, threading.Lock] = {}

    def cli(self, *argv):
        """(exit code, stdout, stderr) of one call, or the `Bound` that the call passes: `CPU` where its process uses more than
        `STAGE_BOUND` s of CPU time, `WALL` where it does not end in `WALL_BOUND` s. The limit is set by `ulimit -t` in a shell, as
        `preexec_fn` is unsafe in the threads that call this."""
        try:
            run = subprocess.run(["/bin/sh", "-c", f'ulimit -t {STAGE_BOUND}; exec "$0" "$@"', self.args.cli, *argv],
                                 capture_output=True, text=True, errors="replace", timeout=WALL_BOUND, env=self.env)
        except subprocess.TimeoutExpired:
            return Bound.WALL
        if run.returncode == -signal.SIGXCPU:
            return Bound.CPU
        return run.returncode, run.stdout, run.stderr

    def original_faults(self, task):
        """The kinds of fault that `decode` gives on the solver's own file, which a mutant's findings leave out, or None where `stream`
        refuses that file or `decode` reports that the checker refuses a case of it."""
        with self.guard:
            lock = self.locks.setdefault(task, threading.Lock())
        with lock:
            if task not in self.originals:
                streamed = self.cli("stream", str(Path(self.args.corpus) / f"{task}.arclog"))
                decoded = self.cli("decode", self.args.corpus, self.args.tasks, "--no-rows", task) if isinstance(streamed, tuple) and streamed[0] == 0 else None
                faults = decode_faults(task, decoded[1]) if isinstance(decoded, tuple) else None
                self.originals[task] = None if faults is None or case_refusals(faults) else {kind for kind, _ in faults}
            return self.originals[task]

    def stage(self, label, result, findings):
        """Adds the `stopped` or `panic` finding of a stage's result; True where it has one."""
        if isinstance(result, Bound):
            findings.append((FindingKind.STOPPED, f"{label} uses more than {STAGE_BOUND} s of CPU time" if result is Bound.CPU else f"{label} does not end in {WALL_BOUND} s"))
            return True
        code, out, err = result
        lines = err.splitlines()
        for i, line in enumerate(lines):
            if "panicked at" in line:
                findings.append((FindingKind.PANIC, f"{label}: {line.strip()} {lines[i + 1].strip() if i + 1 < len(lines) else ''}".strip()))
                return True
        if code < 0 or "overflowed its stack" in err:
            findings.append((FindingKind.PANIC, f"{label} ends by signal {-code}: {(lines or [''])[-1].strip()}"))
            return True
        return False

    def write(self, mutant):
        directory = Path(self.args.out) / f"{mutant.index:05d}-{mutant.task}-{mutant.operator}"
        directory.mkdir(parents=True, exist_ok=True)
        for name in named_solvers(self.args.corpus, mutant.task):
            for extension in ("arcdata", "arclog"):
                source = Path(self.args.corpus) / f"{name}.{extension}"
                if source.exists():
                    (directory / source.name).write_text(read_checked(source))
        (directory / f"{mutant.task}.arclog").write_text(mutant.text)
        return directory

    def examine(self, mutant):
        """(accepted, findings, directory) of a mutant whose solver's own file `stream` and `decode` accept. The mutant is refused where
        `stream` refuses it or `decode` reports that the checker refuses a case."""
        task = mutant.task
        directory = self.write(mutant)
        findings = []
        result = self.cli("stream", str(directory / f"{task}.arclog"))
        if self.stage("stream", result, findings):
            return False, findings, directory
        accepted = result[0] == 0
        message = one_line(result[2], 1000)
        faults, decoded, decode_stopped = [], None, False
        if accepted:
            decoded = self.cli("decode", str(directory), self.args.tasks, "--no-rows", task)
            decode_stopped = self.stage("decode", decoded, findings)
            if not decode_stopped:
                faults = decode_faults(task, decoded[1])
                refusals = case_refusals(faults)
                if refusals:
                    accepted, message = False, one_line(refusals[0], 1000)
        if not accepted and not REFUSAL_PREFIX.sub("", message, count=1).strip():
            findings.append((FindingKind.NO_CAUSE, message or "the refusal has no message"))
        if mutant.expected is not None and mutant.expected != accepted:
            verdict = "accepted" if accepted else f"refused: {message}"
            findings.append((FindingKind.DEPARTS, f"{mutant.note}: the rule {'accepts' if mutant.expected else 'refuses'} it, the build {verdict}"))
        if not accepted or decode_stopped:
            return accepted, findings, directory
        findings += [(FindingKind.RUN_FAULT, f"decode: {body}") for kind, body in faults if kind not in self.original_faults(task)]
        if decoded[0] and not any(line.removeprefix(f"{task}: ").startswith(FAILURE_LINES) for line in decoded[1].splitlines()):
            findings.append((FindingKind.RUN_FAULT, f"decode exits {decoded[0]}: {one_line(decoded[2])}"))
        result = self.cli("tables", str(directory), self.args.tasks, "--bodies", task)
        if self.stage("tables", result, findings):
            return accepted, findings, directory
        failures = [l for l in result[1].splitlines() if not re.fullmatch(rf"{re.escape(task)}: .*: \d+ tables", l)]
        if not faults and (failures or result[0]):
            findings.append((FindingKind.RUN_FAULT, f"tables: {(failures or [one_line(result[2])])[0]}"))
        return accepted, findings, directory


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cli", required=True)
    ap.add_argument("--corpus", default="programs/arclog")
    ap.add_argument("--tasks", default="data/tasks")
    ap.add_argument("--out", default="work/arclog/mutation")
    ap.add_argument("--operators", default=",".join(OPERATORS))
    ap.add_argument("--per-operator", type=int, default=1)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--seed", default="0")
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("task_ids", nargs="*")
    args = ap.parse_args()
    operators = args.operators.split(",")
    unknown = [o for o in operators if o not in OPERATORS]
    if unknown:
        sys.exit(f"unknown operators {unknown}; the operators are {list(OPERATORS)}")
    lib = Lib(ROOT / "engine/lib/registry.sexpr")
    proposers = proposer_pool(args.corpus)
    tasks = args.task_ids or sorted(p.stem for p in Path(args.corpus).glob("*.arclog"))
    if args.limit is not None and not args.task_ids:
        random.Random(f"{args.seed}/tasks").shuffle(tasks)
    shares = share_of_limit(args.limit, operators)
    mutants = []
    for task in tasks:
        wanted = [o for o in operators if shares is None or shares[o] > 0]
        if not wanted:
            break
        try:
            drawn = draw(Context(task, read_checked(Path(args.corpus) / f"{task}.arclog"), lib, proposers), wanted, args.per_operator, args.seed)
        except (ValueError, OSError) as error:
            print(f"left out {task}: {error}", file=sys.stderr)
            continue
        for mutant in drawn:
            if shares is None:
                mutants.append(mutant)
            elif shares[mutant.operator] > 0:
                shares[mutant.operator] -= 1
                mutants.append(mutant)
    for index, mutant in enumerate(mutants):
        mutant.index = index
    runner = Runner(args)
    counts = {o: dict(mutants=0, accepted=0, refused=0, findings=0) for o in operators}
    left_out = 0

    def run(mutant):
        if runner.original_faults(mutant.task) is None:
            return mutant, None
        return mutant, runner.examine(mutant)

    with ThreadPoolExecutor(max(args.jobs, 1)) as pool:
        for mutant, outcome in pool.map(run, mutants):
            if outcome is None:
                left_out += 1
                continue
            accepted, findings, directory = outcome
            count = counts[mutant.operator]
            count["mutants"] += 1
            count["accepted" if accepted else "refused"] += 1
            count["findings"] += len(findings)
            for kind, message in findings:
                print(f"{kind.value} {mutant.task} {mutant.operator} {directory}: {message}", flush=True)
            if not findings:
                shutil.rmtree(directory, ignore_errors=True)
    print("; ".join(f"{o}: {c['mutants']} mutants, {c['accepted']} accepted, {c['refused']} refused, {c['findings']} findings" for o, c in counts.items())
          + (f"; {left_out} mutants left out for solvers whose own file stream or decode refuses or does not end within its bound" if left_out else ""), flush=True)


if __name__ == "__main__":
    main()
