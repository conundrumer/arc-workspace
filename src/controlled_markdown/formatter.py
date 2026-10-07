"""The formatter of Controlled Markdown: a tree put back as canonical
text, and the order of a node's children it writes."""

from __future__ import annotations

from controlled_markdown.nodes import (
    ATTRIBUTE,
    CODE,
    CONTENT,
    HEADING,
    INDENT,
    QUOTE,
    TABLE,
    ControlledMarkdownError,
    Node,
    Rule,
)
from controlled_markdown.parser import BLOCK_MARKER, _directive_attribute, escape


# ---------------------------------------------------------------- formatter


def write(document: Node) -> str:
    """A document as canonical text: the front matter unchanged, normalized
    heading depth, four-space indent."""
    out: list[str] = document.front.split("\n") if document.front else []
    _write_children(document, out, 0)
    return "\n".join(out) + "\n"


def _ordered(children: list[Node]) -> list[Node]:
    """A child list with the attributes first, which is canonical order."""
    heads = [c for c in children if c.kind == ATTRIBUTE]
    return heads + [c for c in children if c.kind != ATTRIBUTE] if heads else children


def check_order(node: Node) -> None:
    """The `+` lines under one parent come before every other child. The
    formatter writes them that way, so this reports what `fmt` would move."""
    seen = False
    for child in node.children:
        if child.kind == ATTRIBUTE:
            if seen:
                raise ControlledMarkdownError(child.source, child.line,
                                          Rule.ATTRIBUTE_FIRST,
                                          "a `+` line comes before every "
                                          "other line under one parent")
        else:
            seen = True
        check_order(child)


def _write_children(parent: Node, out: list[str], level: int) -> None:
    prev: Node | None = None
    for node in _ordered(parent.children):
        if node.kind in BLOCK_MARKER and prev is not None \
                and prev.kind == node.kind:
            _blank(out)   # two blocks of one kind in a row stay two blocks
        if node.blank:
            _blank(out)
        _write_node(node, out, level)
        prev = node


def _blank(out: list[str]) -> None:
    if out and out[-1] != "":
        out.append("")


def _write_node(node: Node, out: list[str], level: int) -> None:
    pad = " " * (INDENT * level)
    if node.kind == HEADING:
        _blank(out)
        head = "#" * node.depth
        out.append(f"{head} {escape(node.text)}" if node.text else head)
        _write_children(node, out, 0)
        return
    if node.kind == QUOTE:
        for line in node.text.split("\n"):
            out.append(f"{pad}> {line}".rstrip())
        return
    if node.kind in (TABLE, CODE):
        for line in node.text.split("\n"):
            out.append(f"{pad}{line}".rstrip())
        return
    if node.kind == CONTENT:
        directive = _directive_attribute(node)
        if directive is not None:
            out.append(f"{pad}* {escape(_named(directive))}".rstrip())
            rest = Node(CONTENT, children=[c for c in node.children
                                           if c is not directive])
            _write_children(rest, out, level + 1)
            return
        mark = f"{node.number}." if node.number else "-"
        out.append(f"{pad}{mark} {escape(node.text)}".rstrip())
    else:
        out.append(f"{pad}+ {escape(_named(node))}".rstrip())
    _write_children(node, out, level + 1)


def _named(node: Node) -> str:
    return node.name if node.value is None else f"{node.name}: {node.value}"
