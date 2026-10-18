"""The Controlled Markdown parser and formatter.

A parser of an external format that accepts wrong input fails silently, so the
cases under `controlled_markdown_cases/` are pinned here. Each case names its
expectation in its first line under any front matter, `+ expect: ok` or
`+ expect: error <rule>`.
"""

import re
from pathlib import Path

import pytest

from controlled_markdown import (
    ControlledMarkdownError,
    Registry,
    check_blocks,
    carry_errors,
    check_links,
    check_order,
    parse,
    render,
    round_trips,
    split_front,
    write,
)

CASES = sorted((Path(__file__).parent / "controlled_markdown_cases").glob("*.md"))
EXPECT_RE = re.compile(r"^\+ expect: (ok|error (\S+))\s*$")

# The rules a render raises, not the parser. A case for one of these parses.
RENDER_RULES = {"include-missing", "include-cycle", "inline-missing",
                "inline-cycle", "id-repeat", "link-missing", "link-text"}


def expectation(text: str) -> tuple[str, str]:
    body = split_front(text, "case")[1].lstrip("\n")
    m = EXPECT_RE.match(body.split("\n", 1)[0])
    assert m is not None, ("a case's first line, under any front matter, must "
                           "be `+ expect: ...`")
    return ("ok", "") if m.group(1) == "ok" else ("error", m.group(2))


@pytest.mark.parametrize("path", CASES, ids=lambda p: p.stem)
def test_case(path):
    """A case parses as it expects, and an accepted case round trips."""
    text = path.read_text()
    kind, rule = expectation(text)
    if kind == "error" and rule not in RENDER_RULES:
        with pytest.raises(ControlledMarkdownError) as err:
            check_shape(parse(text, path.name))
        assert err.value.rule == rule
        return
    document = parse(text, path.name)
    check_shape(document)
    assert round_trips(document)
    canonical = write(document)
    assert write(parse(canonical, path.name)) == canonical
    if kind == "error":
        with pytest.raises(ControlledMarkdownError) as err:
            _render_case(path)
        assert err.value.rule == rule
        return
    _render_case(path)


def check_shape(document):
    """The rules a document keeps that the formatter does not settle."""
    check_order(document)
    check_blocks(document)
    for err in carry_errors(document):
        raise err


def _render_case(path):
    """A case rendered from its own directory, so an include by relative path
    resolves against the case file."""
    registry = Registry(path.parent)
    document = registry.load(path)
    check_links(document, path)
    render(document, registry)
