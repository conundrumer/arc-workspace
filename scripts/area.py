"""Print what bears on a set of files: the open changes whose Scope gives
one of them, the recent tickets whose text names one, and the files of the
tree that import, load or name one. `HELP`, which `--help` prints, gives
the usage form and the rules of each list."""

import argparse
import ast
import sys
import textwrap
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from controlled_markdown import mctx
from handbook.paths import scripts_importable

scripts_importable()

from ticket_paths import scope_paths, ticket_text  # noqa: E402
from ticketing.references import refers, word_forms  # noqa: E402
from ticket_reads import read_tickets  # noqa: E402
from path_args import refuse_absolute  # noqa: E402
from transcript_snapshots import Refused, print_refused  # noqa: E402
from tree_reads import main_tree  # noqa: E402
from dependents import Graph, Reach, conftests, module_of  # noqa: E402
from kept_reads import named_modules  # noqa: E402

from engine import checkout  # noqa: E402
from ticketing.references import Referring  # noqa: E402

from operations.state import Ticket  # noqa: E402
from ticketing.vocabulary import Kind, Status  # noqa: E402

RECENT_DAYS = 14

HELP = mctx("""
    - Usage: `uv run python scripts/area.py <path> [<path> ...]`
    - `<path>` is the path of a file or a directory from the root of the tree.
    - The command reads the main tree and prints three lists, each under its heading, with `{none}` under a heading whose list is empty. The first two, in the order of numbers, come from its ticket tracker.
    - Open changes: each `{change}` outside `tickets/{closed}/` whose `## Scope` gives a path that is a `<path>`, or stands under one, or that a `<path>` stands under, with its number, its status and its title.
        - The paths a Scope gives are those `uv run python scripts/file_ticket.py --help-all` gives.
    - Recent tickets: each ticket filed or closed in the last {days} days whose text names a `<path>`, as `uv run python scripts/file_ticket.py closed-on --help` gives, with its number, its kind, its status and its title.
    - References: one row for each file of the tree and each `<path>` it bears on, in the order of the files' paths.
        - A Python file that git tracks bears on each Python file that is a `<path>` or stands under one, where it has an edge to it under `Reach.RUN`, as `scripts/dependents.py` gives it. Its row gives the line of each `import` statement that makes the edge, the line of each load by a string, a `glob` or a `__path__` that makes it, `{conftest}` where pytest loads that file as a `conftest.py`, and each name of that file's module that it uses, with the lines it uses it on.
            - A name it uses is each name a `from ... import` statement takes from that module, and each attribute it reads on a name that an `import` statement binds to that module.
            - A file that does not parse has an edge to every file, and it gets one row, `{unparsed}`.
        - A file of the tree, tracked or untracked and not ignored, other than the `<path>`s themselves, bears on each `<path>` where a line of its text gives that `<path>` whole, or, as a whole word, its file name or a dotted module name of it. Its row gives the numbers of those lines. The copies of the tree under `.claude/worktrees/`, and the tickets, are no files of the tree.
        - The list leaves out these references, each with the key to search for it by:
            - A call of a method or an attribute of a class that a file defines, on an instance that a function of that file returns to a third module: the name the change alters.
            - A reference by a name a run builds from a string: that name's parts.
            - A Rust `use` path: the path.
            - A document line that states a rule or what a file does and names no file: the key words of the line the change rewrites.
    - The command refuses an absolute `<path>`.
    """)

CHANGES = mctx("Open changes whose Scope gives a path:")
RECENT = mctx("Tickets filed or closed in the last {days} days whose text names a path:")
CHANGE_ROW = mctx("{number} {status} {title}")
RECENT_ROW = mctx("{number} {kind} {status} {title}")
NONE = mctx("none")
REFERENCES = mctx("References, the files of the tree that import, load or name a path:")
REFERENCE_ROW = mctx("{path} on {target}: {parts}")
UNPARSED_ROW = mctx("{path}: {unparsed}")
UNPARSED = mctx("does not parse")
IMPORTS = mctx("import {lines}")
LOADS = mctx("load {lines}")
CONFTEST = mctx("conftest")
USES = mctx("uses {names}")
USE = mctx("{name} {lines}")
NAMES = mctx("names {lines}")


@dataclass
class Reference:
    """How one file of the tree bears on one `<path>`: the lines of its
    `import` statements and its loads, whether pytest loads the `<path>`
    as its `conftest.py`, each name of the `<path>`'s module it uses with
    the lines it uses it on, and the lines of its text that name the
    `<path>`."""

    imports: list[int] = field(default_factory=list)
    loads: list[int] = field(default_factory=list)
    conftest: bool = False
    uses: dict[str, list[int]] = field(default_factory=dict)
    names: list[int] = field(default_factory=list)


@dataclass
class References:
    """The `References` list: a `Reference` for each file of the tree and
    each `<path>` it bears on, by the file's path and the `<path>`, and the
    Python files that do not parse."""

    rows: dict[tuple[str, str], Reference] = field(default_factory=dict)
    unparsed: list[str] = field(default_factory=list)

    def at(self, path: str, target: str) -> Reference:
        return self.rows.setdefault((path, target), Reference())


def overlaps(a: str, b: str) -> bool:
    """Whether the path `a` is `b`, or one of them stands under the other."""
    return Path(a).is_relative_to(b) or Path(b).is_relative_to(a)


def open_changes(tickets: dict[str, Ticket], paths: list[str], root: Path) -> list[Ticket]:
    return [t for t in tickets.values()
            if t.kind is Kind.CHANGE and t.status is not Status.CLOSED
            and any(overlaps(s, p) for s in scope_paths(t, root) for p in paths)]


def recent(tickets: dict[str, Ticket], paths: list[str], since: float) -> list[Ticket]:
    forms = [(p, word_forms(p)) for p in paths]
    return [t for t in tickets.values()
            if (t.filed >= since or any(line.status is Status.CLOSED and line.time >= since
                                        for line in t.log))
            and (text := ticket_text(t)) is not None and any(refers(text, p, f) for p, f in forms)]


def references(root: Path, paths: list[str]) -> References:
    """The `References` list of `paths` in the checkout `root`."""
    out = References()
    importers(root, paths, out)
    namers(root, paths, out)
    return out


def importers(root: Path, paths: list[str], out: References) -> None:
    """Add to `out` the Python files with an edge to a Python file of
    `paths` or under one."""
    graph = Graph(root, paths)
    targets = {f for f in graph.paths if any(PurePosixPath(f).is_relative_to(p) for p in paths)}
    for path in sorted(graph.files):
        found = (graph.edges(path, Reach.RUN) & targets) - {path}
        if not found:
            continue
        tree = graph.parse(path)
        if tree is None:
            out.unparsed.append(path)
            continue
        loads = list(graph.loads(tree, path))
        for target in sorted(found):
            reference = out.at(path, target)
            reference.loads = sorted({line for line, loaded in loads if target in loaded})
            reference.conftest = target in conftests(path)
            uses_of(graph, path, tree, target, reference)


def uses_of(graph: Graph, path: str, tree: ast.Module, target: str, reference: Reference) -> None:
    """Fill in `reference` with the `import` statements of the file at
    `path`, whose parsed text is `tree`, that make an edge to `target`, and
    the names of `target`'s module that the file uses."""
    module = module_of(path)

    def imports(name: str) -> bool:
        return target in graph.modules(name, path)

    taken: dict[str, str] = {}
    bound: set[tuple[str, ...]] = set()
    for node in ast.walk(tree):
        match node:
            case ast.Import(names=aliases):
                for alias in aliases:
                    if any(imports(n) for n in named_modules(module, Path(path), (0, alias.name, ()))):
                        reference.imports.append(node.lineno)
                    if imports(alias.name):
                        bound.add((alias.asname,) if alias.asname else tuple(alias.name.split(".")))
            case ast.ImportFrom(level=level, module=base, names=aliases):
                statement = (level, base or "", tuple(a.name for a in aliases))
                if any(imports(n) for n in named_modules(module, Path(path), statement)):
                    reference.imports.append(node.lineno)
                resolved = named_modules(module, Path(path), (level, base or "", ()))
                if not resolved:
                    continue
                for alias in aliases:
                    local = alias.asname or alias.name
                    if imports(f"{resolved[-1]}.{alias.name}"):
                        bound.add((local,))
                    elif alias.name != "*" and imports(resolved[-1]):
                        taken[local] = alias.name
                        reference.uses.setdefault(alias.name, [])
    reference.imports = sorted(set(reference.imports))
    for node in ast.walk(tree):
        match node:
            case ast.Name(id=name, ctx=ast.Load()) if name in taken:
                reference.uses[taken[name]].append(node.lineno)
            case ast.Attribute(value=value, attr=attr) if dotted(value) in bound:
                reference.uses.setdefault(attr, []).append(node.lineno)
    reference.uses = {name: sorted(set(lines)) for name, lines in sorted(reference.uses.items())}


def dotted(expr: ast.expr) -> tuple[str, ...] | None:
    """The parts of the dotted name `expr` is, such as `a.b.c`, or None
    where it is no such name."""
    match expr:
        case ast.Name(id=name):
            return (name,)
        case ast.Attribute(value=value, attr=attr):
            parts = dotted(value)
            return None if parts is None else (*parts, attr)
    return None


def namers(root: Path, paths: list[str], out: References) -> None:
    """Add to `out` the files of the tree, tracked or untracked and not
    ignored, whose lines name a path of `paths`."""
    listed = checkout.git_out(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    every = Referring(paths)
    each = {p: Referring([p]) for p in paths}
    for path in sorted(set(listed.split("\0")) - {"", *paths}):
        file = root / path
        if not file.is_file():
            continue
        try:
            text = file.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if not every(text):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for target, refers in each.items():
                if refers(line):
                    out.at(path, target).names.append(number)


def lines_text(lines: list[int]) -> str:
    return " ".join(map(str, lines))


def rendered(references: References) -> list[str]:
    rows = [UNPARSED_ROW.format(path=p, unparsed=UNPARSED) for p in references.unparsed]
    for (path, target), r in references.rows.items():
        uses = ", ".join(USE.format(name=n, lines=lines_text(lines)) for n, lines in r.uses.items())
        parts = [*(form.format(lines=lines_text(lines))
                   for form, lines in ((IMPORTS, r.imports), (LOADS, r.loads)) if lines),
                 *([CONFTEST] if r.conftest else []),
                 *([USES.format(names=uses)] if uses else []),
                 *([NAMES.format(lines=lines_text(r.names))] if r.names else [])]
        rows.append(REFERENCE_ROW.format(path=path, target=target, parts="; ".join(parts)))
    return sorted(rows)


def area(paths: list[str]) -> str:
    refuse_absolute(paths, "area")
    root = main_tree()
    tickets, _ = read_tickets(root / "tickets")
    ordered = dict(sorted(tickets.items(), key=lambda kv: kv[1].order))
    changes = [CHANGE_ROW.format(number=t.number, status=t.status, title=t.title)
               for t in open_changes(ordered, paths, root)]
    since = time.time() - RECENT_DAYS * 86400
    others = [RECENT_ROW.format(number=t.number, kind=t.kind, status=t.status, title=t.title)
              for t in recent(ordered, paths, since)]
    found = rendered(references(root, paths))
    return "\n".join([CHANGES, *(changes or [NONE]), "",
                      RECENT.format(days=RECENT_DAYS), *(others or [NONE]), "",
                      REFERENCES, *(found or [NONE])])


def main() -> int:
    parser = argparse.ArgumentParser(
        description=textwrap.dedent(HELP).format(none=NONE, change=Kind.CHANGE, closed=Status.CLOSED,
                                                 days=RECENT_DAYS, conftest=CONFTEST,
                                                 unparsed=UNPARSED),
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", metavar="path")
    args = parser.parse_args()
    try:
        print(area(args.paths))
    except Refused as e:
        print_refused(e)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
