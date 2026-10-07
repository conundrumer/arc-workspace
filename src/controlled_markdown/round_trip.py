"""The formatter's round trip."""

from __future__ import annotations

from controlled_markdown import Node, parse, write


def round_trips(document: Node) -> bool:
    """Whether the formatter's output parses back to the same tree."""
    return parse(write(document), document.source).shape() == document.shape()
