"""The Python files of a checkout whose checks a change to some of its
Python files can affect: each file from which a Python file the change
touches is reached along the edges a `Reach` gives.

An `import` statement (`kept_reads.imports_of`) is an edge to the file of
each module it names, with its parent packages (`kept_reads.named_modules`).
A module's file is found from its name under each of `MODULE_ROOTS`, and
under the directory of the importing file, so every file a module of that
name can resolve to is reached.

A run can also load code by its path or its name, as a test loads a script
with `importlib`, starts it as a command, or reads its source. Under
`Reach.RUN`, then:

- a string constant other than a docstring is an edge to each file it can
  name (`Graph.named_by`);
- a `glob` or `rglob` call whose directory `directory_of` gives is an edge
  to each file its pattern lists there, and its pattern names no other
  file;
- the attribute `__path__` of a module, which finds the package's modules
  at run time, is an edge to every module of that package;
- a file is an edge to each `conftest.py` above it, which pytest loads for
  a test file.

A file that does not parse has an edge to every file."""

import ast
import fnmatch
from collections.abc import Callable, Iterable, Iterator, Set
from enum import Enum
from pathlib import Path, PurePosixPath

from kept_reads import imports_in, named_modules

from engine import checkout
from ticketing.references import MODULE_ROOTS, module_names

PYTHON_SUFFIX = ".py"

GLOBS = {"glob": False, "rglob": True}
"""The methods of a path that list the files a pattern matches, with
whether each lists the directories below it too."""

type Scope = tuple[tuple[str, ...], bool]
"""A directory a run can list: the parts of its path from the checkout's
root, and whether it can be any directory below that one, where a part of
its path is computed at run time."""


class Reach(Enum):
    """The edges a check follows: `IMPORTS`, the `import` statements, which
    are all a type checker reads; `RUN`, those and the loads of code by a path
    or a name that the module docstring gives."""

    IMPORTS = "imports"
    RUN = "run"


def module_paths(name: str) -> list[str]:
    """The paths, from a directory, at which a module of `name` stands."""
    stem = name.replace(".", "/")
    return [stem + PYTHON_SUFFIX, f"{stem}/__init__{PYTHON_SUFFIX}"]


class Graph:
    """The Python files of the checkout `tree` that stand in it, those git
    tracks and those of `touched`, and the Python files of `touched`, the
    paths a change touches, with the names of the modules each stands
    for."""

    def __init__(self, tree: Path, touched: Iterable[str]) -> None:
        self.tree = tree
        tracked = checkout.git_out(tree, "ls-files", "-z", "--", f"*{PYTHON_SUFFIX}")
        self.touched = frozenset(p for p in touched if p.endswith(PYTHON_SUFFIX))
        self.files = frozenset(p for p in {*tracked.split("\0"), *self.touched}
                               if p and (tree / p).is_file())
        self.paths = self.files | self.touched
        self.by_name: dict[str, set[str]] = {}
        for path in self.paths:
            for name in module_names(path):
                self.by_name.setdefault(name, set()).add(path)
        self.parsed: dict[str, ast.Module | None] = {}
        self.imported: dict[str, set[str]] = {}
        self.named: dict[str, set[str]] = {}

    def dependents(self, reach: Reach) -> set[str]:
        """The files of `files` that reach a touched Python file under
        `reach`."""
        back: dict[str, set[str]] = {}
        for path in self.files:
            for to in self.edges(path, reach):
                back.setdefault(to, set()).add(path)
        return set(reached(lambda p: back.get(p, ()), self.touched)) & self.files

    def parse(self, path: str) -> ast.Module | None:
        if path not in self.parsed:
            try:
                self.parsed[path] = ast.parse((self.tree / path).read_bytes())
            except (SyntaxError, ValueError):
                self.parsed[path] = None
        return self.parsed[path]

    def modules(self, name: str, near: str) -> set[str]:
        """The paths of the module `name` imported from the file at `near`."""
        here = PurePosixPath(near).parent
        local = {str(here / p) for p in module_paths(name)} & self.paths
        return self.by_name.get(name, set()) | local

    def edges(self, path: str, reach: Reach) -> Set[str]:
        """The paths the file at `path` has an edge to under `reach`."""
        tree = self.parse(path)
        if tree is None:
            return self.paths
        if path not in self.imported:
            names = module_names(path)
            module = names[0] if names else PurePosixPath(path).stem
            self.imported[path] = {p for statement in imports_in(tree)
                                   for name in named_modules(module, Path(path), statement)
                                   for p in self.modules(name, path)}
        if reach is Reach.IMPORTS:
            return self.imported[path]
        return self.imported[path] | self.run_edges(tree, path)

    def run_edges(self, tree: ast.Module, path: str) -> set[str]:
        out: set[str] = set(conftests(path) & self.paths)
        assigned = module_assignments(tree)
        skipped: set[int] = set()
        texts: list[tuple[int, str]] = []
        for node in ast.walk(tree):
            match node:
                case ast.Expr(value=ast.Constant() as doc):
                    skipped.add(id(doc))
                case ast.Constant(value=str(text)):
                    texts.append((id(node), text))
                case ast.Call(func=ast.Attribute(value=value, attr=method),
                              args=[ast.Constant(value=str(pattern)) as arg, *_]) \
                        if method in GLOBS:
                    scope = directory_of(value, path, assigned)
                    if scope is not None:
                        skipped.add(id(arg))
                        out |= self.listed(scope, GLOBS[method], pattern)
                case ast.Attribute(value=ast.Name(id=package), attr="__path__"):
                    out |= {p for name, paths in self.by_name.items()
                            if name == package or name.startswith(package + ".")
                            for p in paths}
        for at, text in texts:
            if at not in skipped:
                out |= self.named_by(text)
        return out

    def listed(self, scope: Scope, recursive: bool, pattern: str) -> set[str]:
        """The paths a glob of `pattern` in the directory `scope` gives, the
        directories below it too where `recursive`."""
        base, below = scope
        found: set[str] = set()
        for p in self.paths:
            parts = PurePosixPath(p).parts
            if parts[:len(base)] != base:
                continue
            rel = "/".join(parts[len(base):])
            if fnmatch.fnmatchcase(rel, pattern) or (
                    (recursive or below) and fnmatch.fnmatchcase(rel, "*/" + pattern)):
                found.add(p)
        return found

    def named_by(self, text: str) -> set[str]:
        """The paths the string `text` can name: those of the module it names,
        or, where it holds a `/` or `PYTHON_SUFFIX` and no whitespace, as a
        path does, each path it is a trailing part of, or a glob pattern of
        a trailing part of."""
        if text in self.named:
            return self.named[text]
        found = self.named[text] = set(self.by_name.get(text, ()))
        if ("/" in text or PYTHON_SUFFIX in text) and not any(c.isspace() for c in text):
            patterns = {text, text.replace("**/", "")}
            found |= {p for p in self.paths
                      if any(p == t or p.endswith("/" + t) or fnmatch.fnmatchcase(p, t)
                             or fnmatch.fnmatchcase(p, "*/" + t) for t in patterns)}
        return found


def module_assignments(tree: ast.Module) -> dict[str, ast.expr]:
    """The value each name is given at the top level of `tree`, where a
    single assignment gives it one."""
    out: dict[str, ast.expr] = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            out[node.targets[0].id] = node.value
        elif (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
              and node.value is not None):
            out[node.target.id] = node.value
    return out


def directory_of(expr: ast.expr, path: str, assigned: dict[str, ast.expr],
                 seen: frozenset[str] = frozenset()) -> Scope | None:
    """The directory the path `expr` of the file at `path` gives, where it
    is built from `__file__` or `checkout.ROOT` by `Path`, `resolve`,
    `absolute`, `parent`, `parents` and `/`, through the names `assigned`
    gives; None where it is built otherwise."""
    match expr:
        case ast.Name(id="__file__"):
            return PurePosixPath(path).parts, False
        case ast.Attribute(value=ast.Name(id="checkout"), attr="ROOT"):
            return (), False
        case ast.Name(id=name) if name in assigned and name not in seen:
            return directory_of(assigned[name], path, assigned, seen | {name})
        case ast.Call(func=ast.Name(id="Path"), args=[arg]):
            return directory_of(arg, path, assigned, seen)
        case ast.Call(func=ast.Attribute(value=value, attr="resolve" | "absolute"), args=[]):
            return directory_of(value, path, assigned, seen)
        case ast.Attribute(value=value, attr="parent"):
            return up(directory_of(value, path, assigned, seen), 1)
        case ast.Subscript(value=ast.Attribute(value=value, attr="parents"),
                           slice=ast.Constant(value=int(n))):
            return up(directory_of(value, path, assigned, seen), n + 1)
        case ast.BinOp(left=left, op=ast.Div(), right=right):
            scope = directory_of(left, path, assigned, seen)
            if scope is None:
                return None
            if isinstance(right, ast.Constant) and isinstance(right.value, str):
                return scope[0] + PurePosixPath(right.value).parts, scope[1]
            return scope[0], True
    return None


def up(scope: Scope | None, levels: int) -> Scope | None:
    if scope is None or levels > len(scope[0]):
        return None
    return scope[0][:len(scope[0]) - levels], scope[1]


def conftests(path: str) -> set[str]:
    """The `conftest.py` files pytest loads for a test file at `path`: one in
    each directory above it."""
    return {str(parent / "conftest.py") for parent in PurePosixPath(path).parents}


def reached(edges: Callable[[str], Iterable[str]],
            start: Set[str]) -> Iterator[str]:
    """Each path that a path of `edges` leads to from one of `start`, `start`
    among them, `edges` giving the paths one path has an edge to."""
    seen = set(start)
    todo = list(start)
    while todo:
        path = todo.pop()
        yield path
        for to in edges(path):
            if to not in seen:
                seen.add(to)
                todo.append(to)
