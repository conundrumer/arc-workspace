"""Whether an edit of a Python file changes what pyright reads: the edits
that change nothing but bare string statements, argparse help values that
are plain strings, and blank lines and comments that hold no type-checker
directive."""

import ast
import io
import tokenize

HELP_KEYWORDS = frozenset({"help", "description", "epilog"})
"""The keywords of an argparse parser builder whose text argparse prints
only for a help flag."""

HELP_CALLEES = frozenset({"ArgumentParser", "add_argument", "add_parser", "add_subparsers",
                          "add_argument_group", "add_mutually_exclusive_group"})
"""The argparse parser builders, by the name a call gives them."""

HELP_HELPERS = {"src/cli/parser.py": frozenset({"command"})}
"""By file, the functions that pass their `HELP_KEYWORDS` on to an argparse
parser builder."""


def _callee(call: ast.Call) -> str | None:
    f = call.func
    return f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else None


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


DIRECTIVES = ("type:", "pyright:")
"""The openings of a comment, after its `#`, that hold a directive to a
type checker."""


LAYOUT = frozenset({tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
                    tokenize.DEDENT, tokenize.ENDMARKER})
"""The tokens that are no code on a line."""


def _directives(text: str) -> list[tuple[str, tuple[str, ...]]]:
    """The comments of the Python text `text` that hold a type-checker
    directive, in order, each with the code tokens of its line: a type
    checker applies such a comment to the line it stands on."""
    tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    return [(t.string, tuple(c.string for c in tokens
                             if c.type not in LAYOUT and c.start[0] <= t.start[0] <= c.end[0]))
            for t in tokens
            if t.type == tokenize.COMMENT and t.string[1:].lstrip().startswith(DIRECTIVES)]


def same_code(path: str, old: str, new: str) -> bool:
    """Whether the texts `old` and `new` of the Python file `path` give
    pyright the same code. A text that does not parse gives `False`."""
    try:
        a, b = ast.parse(old), ast.parse(new)
    except SyntaxError:
        return False
    for tree in (a, b):
        _drop_strings(tree)
        _blank_help(tree, path, plain=True)
    return ast.dump(a) == ast.dump(b) and _directives(old) == _directives(new)
