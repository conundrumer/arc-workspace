"""The references from a document to code and to other documents: the
definitions and sections a line declares in an `xref` attribute, and the
scripts, modules and paths the backticked spans of a statement's text name,
with the check that each resolves and the declarations whose target's lines
a diff changes.

An `xref` value is a list of targets separated by commas. A target is a path
from the root of the tree; for a Python file, the path, `:` and the
dotted name of a definition in it: a module-level `def`, `class`, `type`
alias, assignment or annotated assignment, or such a name in the body of a
class the name before it gives; or, for a document, the path, `#` and the
slug of a heading in it, which gives that heading's section, its
subsections included."""

from __future__ import annotations

import ast
import re
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from pathlib import Path

from controlled_markdown import (
    CONTENT,
    ControlledMarkdownError,
    HEADING,
    Node,
    parse,
    Rule,
    section,
    SPAN_RE,
    _walk,
)

XREF = "xref"

# The directories a backticked path token names code or documents under.
PATH_ROOTS = ("scripts/", "src/", "programs/", "tests/", "tools/", "docs/",
              "prompts/")
PATH_TOKEN_RE = re.compile(r"[\w./-]+")
MODULE_RE = re.compile(r"[\w.]+")
# A target: its path, then a `Mark` and the name after it.
TARGET_RE = re.compile(r"([^:#]*)([:#]?)(.*)")
# The words that open a command that runs a Python file or module.
RUNNER = ("uv", "run", "python")
# The directory a module that `-m` runs stands under.
MODULE_ROOT = "src"


@dataclass(frozen=True)
class Xref:
    """An `xref` attribute: the node it describes, and each target."""

    node: Node
    targets: tuple[str, ...]


def xrefs(document: Node) -> Iterator[Xref]:
    """Each `xref` attribute of the document's nodes, with its node and its
    targets."""
    for node in _walk(document):
        value = node.attr(XREF)
        if value is not None:
            yield Xref(node, tuple(t.strip() for t in value.split(",") if t.strip()))


@cache
def _tree(text: str) -> ast.Module | None:
    """The AST of the Python text `text`, or None where it parses not."""
    try:
        return ast.parse(text)
    except SyntaxError:
        return None


def _defined(node: ast.stmt) -> tuple[str, ...]:
    """The names a statement of a module or class body defines."""
    match node:
        case ast.FunctionDef() | ast.AsyncFunctionDef() | ast.ClassDef():
            return (node.name,)
        case ast.TypeAlias(name=ast.Name(id=name)):
            return (name,)
        case ast.Assign(targets=targets):
            return tuple(t.id for t in targets if isinstance(t, ast.Name))
        case ast.AnnAssign(target=ast.Name(id=name)):
            return (name,)
    return ()


def _definition(body: list[ast.stmt], names: list[str]) -> ast.stmt | None:
    """The statement of `body` that defines the dotted name `names`, the
    names after the first read in the body of the class the first gives."""
    first, rest = names[0], names[1:]
    for node in body:
        if first in _defined(node):
            if not rest:
                return node
            return _definition(node.body, rest) if isinstance(node, ast.ClassDef) else None
    return None


class Mark(StrEnum):
    """What a target's name after its path names."""

    FILE = ""           # no name: the whole file
    DEFINITION = ":"    # a dotted name of a Python definition
    SECTION = "#"       # a heading's slug


def _target(target: str) -> tuple[str, Mark, str]:
    """The target's path, its mark, and the name after the mark."""
    match = TARGET_RE.fullmatch(target)
    assert match is not None  # each group matches the empty string
    path, mark, name = match.groups()
    return path, Mark(mark), name


def _section_span(text: str, path: str, ident: str) -> tuple[int, int] | None:
    """The first and last line of the section of the document `text`,
    read from `path`, whose heading's slug is `ident`: the heading's line
    to the line before the first node that `parse` puts outside the
    heading's subtree after it, or to the last line. None where the
    document holds no such heading."""
    document = parse(text, path)
    heading = section(document, ident)
    if heading is None:
        return None
    inside = {id(n) for n in _walk(heading)}
    end = next((n.line - 1 for n in _walk(document)
                if n.line > heading.line and id(n) not in inside),
               len(text.splitlines()))
    return heading.line, max(heading.line, end)


def _span_in(text: str, target: str) -> tuple[int, int] | None:
    """The first and last line in the text of the target's file of what the
    target names: the whole text for a bare path, a document's section
    (`_section_span`), or the definition of a dotted name, its decorators
    included. None where a mark has no name after it, or where the file
    is of no kind its mark names or holds no such section or name."""
    path, mark, name = _target(target)
    if mark is Mark.FILE:
        return 1, max(1, len(text.splitlines()))
    if not name:
        return None
    if mark is Mark.SECTION:
        return _section_span(text, path, name) if path.endswith(".md") else None
    module = _tree(text) if path.endswith(".py") else None
    node = _definition(module.body, name.split(".")) if module is not None else None
    if node is None:
        return None
    decorators = getattr(node, "decorator_list", [])
    first = min([node.lineno, *(d.lineno for d in decorators)])
    return first, node.end_lineno or node.lineno


def _defined_text(text: str, target: str) -> str | None:
    """The lines of what the target names in `text`, the text of the
    target's file, or None where it holds no such thing (`_span_in`)."""
    lines = _span_in(text, target)
    if lines is None:
        return None
    return "".join(text.splitlines(keepends=True)[lines[0] - 1:lines[1]])


def span(target: str, root: Path) -> tuple[int, int] | None:
    """The first and last line of what the target names, as `_span_in`
    gives them, or None where the file, the section or the name is
    absent."""
    file = root / _target(target)[0]
    if not file.is_file():
        return None
    return _span_in(file.read_text(), target)


@dataclass(frozen=True)
class CodeReference:
    """What a statement's backticked span names, as `named` gives it: a
    script a command runs, a module, or a path token, with the paths from
    the root of the tree that each stand for it."""

    node: Node
    named: str
    paths: tuple[str, ...]


def _command(tokens: list[str]) -> tuple[str, ...]:
    """The paths that stand for the file a command of `tokens` runs, where
    they run a Python file or module through `uv run python`: a module as
    its file or its package under `src/`. A command that runs no file, as
    `-c` gives one, stands for none."""
    for i in range(len(tokens) - len(RUNNER) + 1):
        if tuple(tokens[i:i + len(RUNNER)]) != RUNNER:
            continue
        rest = iter(tokens[i + len(RUNNER):])
        for token in rest:
            if token == "-c":
                return ()
            if token == "-m":
                module = next(rest, "")
                if not MODULE_RE.fullmatch(module):
                    return ()
                path = f"{MODULE_ROOT}/{module.replace('.', '/')}"
                return f"{path}.py", path
            if not token.startswith("-"):
                return (token,) if PATH_TOKEN_RE.fullmatch(token) else ()
    return ()


def references(document: Node) -> Iterator[CodeReference]:
    """Each script or module a backticked span of a statement's text runs,
    and each path token of such a span under `PATH_ROOTS`, a trailing `/`
    read off. A token with a glob character, a colon or any other character
    outside `PATH_TOKEN_RE` names no path, and `check_xrefs` resolves no
    path that git ignores. A path a statement names twice is given once."""
    for node in _walk(document):
        if node.kind not in (CONTENT, HEADING):
            continue
        seen: set[tuple[str, ...]] = set()
        for part in SPAN_RE.split(node.text):
            if not part.startswith("`"):
                continue
            tokens = part.strip("`").split()
            run = _command(tokens)
            found = ([CodeReference(node, f"`{' '.join(tokens)}`", run)] if run else []) + [
                CodeReference(node, f"`{t}`", (t.rstrip("/"),)) for t in tokens
                if t.startswith(PATH_ROOTS) and PATH_TOKEN_RE.fullmatch(t)]
            for ref in found:
                if ref.paths not in seen:
                    seen.add(ref.paths)
                    yield ref


def _ignored(root: Path, paths: set[str]) -> set[str]:
    """The paths of `paths` that git ignores under `root`, each asked as a
    file and as a directory, so a pattern that names a directory meets a
    path that stands nowhere."""
    if not paths:
        return set()
    asked = sorted(paths | {f"{p}/" for p in paths})
    answer = subprocess.run(["git", "check-ignore", "-z", "--stdin"], cwd=root,
                            input="\0".join(asked) + "\0", capture_output=True, text=True)
    # `git check-ignore` exits 1 where it ignores none of the paths.
    if answer.returncode not in (0, 1):
        raise subprocess.CalledProcessError(answer.returncode, answer.args,
                                            answer.stdout, answer.stderr)
    return {p.rstrip("/") for p in answer.stdout.split("\0") if p}


def check_xrefs(document: Node, root: Path) -> list[ControlledMarkdownError]:
    """An `xref-missing` error for each target of an `xref` that `span`
    finds nothing for, and for each reference of `references` that no
    path of the tree stands for, at the line of the statement. A reference
    that a path git ignores stands for is resolved by no worktree, so it is
    not reported."""
    absent = [ref for ref in references(document)
              if not any((root / p).exists() for p in ref.paths)]
    ignored = _ignored(root, {p for ref in absent for p in ref.paths})
    return [
        *(ControlledMarkdownError(x.node.source, x.node.line, Rule.XREF_MISSING,
                                  f"nothing at `{target}`")
          for x in xrefs(document) for target in x.targets
          if span(target, root) is None),
        *(ControlledMarkdownError(ref.node.source, ref.node.line, Rule.XREF_MISSING,
                                  f"{ref.named}: the tree holds no "
                                  f"`{ref.paths[0]}`")
          for ref in absent if not ignored & set(ref.paths))]


@dataclass(frozen=True)
class Touch:
    """A node whose `xref` target a diff changes, with that target."""

    node: Node
    target: str


@cache
def _text_at(root: Path, base: str, path: str) -> str | None:
    """The text of `path` at the commit `base`, or None where it holds no
    such file."""
    shown = subprocess.run(["git", "show", f"{base}:{path}"], cwd=root,
                           capture_output=True, text=True)
    return shown.stdout if shown.returncode == 0 else None


def touched(documents: list[Node], root: Path, base: str) -> list[Touch]:
    """Each node and target of an `xref` whose lines (`span`) differ
    between the commit `base` and the working tree, in document and line
    order. A target that no longer resolves counts as touched, and so does
    one that resolved at nothing at `base`."""
    out: list[Touch] = []
    for document in documents:
        for x in xrefs(document):
            for target in x.targets:
                path = _target(target)[0]
                file = root / path
                now = _defined_text(file.read_text(), target) if file.is_file() else None
                before = _text_at(root, base, path)
                if now is None or before is None or _defined_text(before, target) != now:
                    out.append(Touch(x.node, target))
    return out
