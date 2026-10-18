"""Whether an edit of a Python file, or of a Souffle file of the lib,
changes what a check runs: the edits that change nothing but text no gate
command, pyright or pytest reads."""

import ast
import io
import tokenize
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from cli import HELP_FLAGS
from gating.commands import COMMANDS

if TYPE_CHECKING:
    from gating.hunks import Hunk

HELP_KEYWORDS = frozenset({"help", "description", "epilog"})
"""The keywords of an argparse parser builder whose text argparse prints
only for a help flag."""

HELP_CALLEES = frozenset({"ArgumentParser", "add_argument", "add_parser", "add_subparsers",
                          "add_argument_group", "add_mutually_exclusive_group"})
"""The argparse parser builders, by the name a call gives them."""

HELP_HELPERS = {"src/cli/parser.py": frozenset({"command"})}
"""By file, the functions that pass their `HELP_KEYWORDS` on to an argparse
parser builder."""


@cache
def _help_printed() -> bool:
    """Whether some gate command's arguments hold a help flag."""
    return any(a in HELP_FLAGS for c in COMMANDS.values() for s in c.stems
               for a in c.argv(s, Path()))


def _callee(call: ast.Call) -> str | None:
    f = call.func
    return f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else None


def _import_bindings(tree: ast.Module) -> tuple[set[str], dict[str, tuple[str, str | None]]]:
    """The modules the module-level imports of `tree` name, and each name
    they bind, with the module and the original name it is bound to."""
    modules: set[str] = set()
    binds: dict[str, tuple[str, str | None]] = {}
    for n in tree.body:
        modules.update(_modules(n))
        if isinstance(n, ast.Import):
            for a in n.names:
                binds[a.asname or a.name.split(".")[0]] = (
                    a.name if a.asname else a.name.split(".")[0], None)
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                binds[a.asname or a.name] = ("." * n.level + (n.module or ""), a.name)
    return modules, binds


def _modules(n: ast.stmt) -> list[str]:
    """The modules the statement `n` imports, in order, where it is an
    import statement."""
    if isinstance(n, ast.Import):
        return [a.name for a in n.names]
    if isinstance(n, ast.ImportFrom):
        return ["." * n.level + (n.module or "")]
    return []


def _first_imports(body: list[ast.stmt]) -> list[ast.stmt]:
    """`body` with each import statement replaced, in its place, by one
    that imports only the modules no statement before it imports, and
    dropped where it imports none: the order and place in which modules
    are first imported decide what an import cycle or a `sys.path` edit
    gives."""
    seen: set[str] = set()
    out: list[ast.stmt] = []
    for n in body:
        if not isinstance(n, (ast.Import, ast.ImportFrom)):
            out.append(n)
            continue
        first = [m for m in dict.fromkeys(_modules(n)) if m not in seen]
        seen.update(first)
        if first:
            out.append(ast.Import(names=[ast.alias(name=m) for m in first]))
    return out


def _same_imports(old: ast.Module, new: ast.Module) -> bool:
    (om, ob), (nm, nb) = _import_bindings(old), _import_bindings(new)
    return om == nm and all(ob[k] == nb[k] for k in ob.keys() & nb.keys())


def _is_string(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str)


def _drop_strings(tree: ast.Module) -> None:
    """Drop each bare string statement of `tree`, in place."""
    for n in ast.walk(tree):
        for field, value in ast.iter_fields(n):
            if isinstance(value, list):
                setattr(n, field, [v for v in value
                                   if not (isinstance(v, ast.Expr) and _is_string(v.value))])


def _blank_help(tree: ast.Module, path: str, *, plain: bool) -> None:
    """Make the value of each `HELP_KEYWORDS` keyword of a parser builder
    of `tree` one placeholder, in place, where `plain` only a value that is
    a plain string constant."""
    callees = HELP_CALLEES | HELP_HELPERS.get(path, frozenset())
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and _callee(n) in callees:
            for k in n.keywords:
                if k.arg in HELP_KEYWORDS and (not plain or _is_string(k.value)):
                    k.value = ast.Constant(None)


def _normalized(tree: ast.Module, path: str, imports: bool) -> str:
    """`tree` dumped without its bare string statements, with the value of
    each `HELP_KEYWORDS` keyword of a parser builder made one placeholder
    where no gate command prints help, and with its module-level imports
    reduced to the modules each imports first (`_first_imports`) where
    `imports`."""
    _drop_strings(tree)
    if not _help_printed():
        _blank_help(tree, path, plain=False)
    if imports:
        tree.body = _first_imports(tree.body)
    return ast.dump(tree)


def inert(path: str, old: str, new_lines: Sequence[str], hunk: "Hunk") -> bool:
    """Whether the hunk `hunk` of the Python file `path`, whose old side is
    numbered in the text `old` and whose new side is `new_lines`, applied
    alone, changes nothing a gate command runs: whether it changes nothing
    but comments, blank lines and bare string statements, the
    `HELP_KEYWORDS` values of parser builders, and module-level imports
    where both sides import the same modules, first in the same order and
    places, and bind no name both bind to another module or original
    name. A gate command reads no `__doc__`.
    A hunk whose applied text does not parse is not inert."""
    lines = old.splitlines(keepends=True)
    at = hunk.old_start if not hunk.old_count else hunk.old_start - 1
    applied = "".join([*lines[:at], *new_lines, *lines[at + hunk.old_count:]])
    try:
        a, b = ast.parse(old), ast.parse(applied)
    except SyntaxError:
        return False
    imports = _same_imports(a, b)
    return _normalized(a, path, imports) == _normalized(b, path, imports)


DL_COMMENT = "//"
"""The opening of a Souffle line comment."""

DL_BLOCK = ("/*", "*/")
"""The opening and the closing of a Souffle block comment."""


def inert_dl(old: str, new_lines: Sequence[str], hunk: "Hunk") -> bool:
    """Whether the hunk `hunk` of a Souffle file, whose old side is
    numbered in the text `old` and whose new side is `new_lines`, changes
    nothing a Souffle run reads and moves no line: whether its old and new
    sides have the same count and each of their lines is blank or a `//`
    comment that holds no `DL_BLOCK` mark, since such a line may open or
    close a block comment around other lines. A command that reads the comment text of a Souffle file is
    affected all the same (`gating.affects.COMMENT_READERS`)."""
    lines = old.splitlines(keepends=True)
    old_lines = lines[hunk.old_start - 1:hunk.old_start - 1 + hunk.old_count]
    return hunk.old_count == hunk.new_count and all(
        not s or (s.startswith(DL_COMMENT) and not any(m in s for m in DL_BLOCK))
        for s in (x.strip() for x in [*old_lines, *new_lines]))


DIRECTIVES = ("type:", "pyright:")
"""The openings of a comment, after its `#`, that carry a directive to a
type checker."""


LAYOUT = frozenset({tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
                    tokenize.DEDENT, tokenize.ENDMARKER})
"""The tokens that are no code on a line."""


def _directives(text: str) -> list[tuple[str, tuple[str, ...]]]:
    """The comments of the Python text `text` that carry a type-checker
    directive, in order, each with the code tokens of its line: a type
    checker applies such a comment to the line it stands on."""
    tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    return [(t.string, tuple(c.string for c in tokens
                             if c.type not in LAYOUT and c.start[0] <= t.start[0] <= c.end[0]))
            for t in tokens
            if t.type == tokenize.COMMENT and t.string[1:].lstrip().startswith(DIRECTIVES)]


def same_code(path: str, old: str, new: str) -> bool:
    """Whether the texts `old` and `new` of the Python file `path` give
    pyright and pytest the same code, by the rule
    `scripts/merge_change.py --help` gives. A text that does not parse
    gives `False`."""
    try:
        a, b = ast.parse(old), ast.parse(new)
    except SyntaxError:
        return False
    for tree in (a, b):
        _drop_strings(tree)
        _blank_help(tree, path, plain=True)
    return ast.dump(a) == ast.dump(b) and _directives(old) == _directives(new)
