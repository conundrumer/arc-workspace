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
    ATTRIBUTE,
    CODE,
    CONTENT,
    HEADING,
    QUOTE,
    TABLE,
    ControlledMarkdownError,
    Registry,
    check_blocks,
    check_links,
    check_order,
    full,
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


def _render_case(path):
    """A case rendered from its own directory, so an include by relative path
    resolves against the case file."""
    registry = Registry(path.parent)
    document = registry.load(path)
    check_links(document, path)
    render(document, registry)


def test_markers():
    """Each marker kind lands as its own node."""
    document = parse(
        "+ agent: handbook\n"
        "# T\n"
        "- parent\n"
        "    + note: v\n"
        "    - child\n"
        "    > body\n"
        "* wrap\n"
        "    - inner\n"
    )
    agent, head = document.children
    assert (agent.kind, agent.name, agent.value) == (ATTRIBUTE, "agent", "handbook")
    assert (head.kind, head.text, head.depth) == (HEADING, "T", 1)
    parent, wrap = head.children
    assert (parent.kind, parent.text) == (CONTENT, "parent")
    note, child, quote = parent.children
    assert (note.kind, note.name, note.value) == (ATTRIBUTE, "note", "v")
    assert (child.kind, child.text) == (CONTENT, "child")
    assert (quote.kind, quote.text) == (QUOTE, "body")
    assert wrap.anonymous() and wrap.star
    assert wrap.attributes()["wrap"].value is None
    assert [c.text for c in wrap.contents()] == ["inner"]


def test_block_syntax_escape():
    """A statement that opens with block syntax needs a backslash, and the
    formatter puts it back."""
    text = "# T\n- \\> quoted\n- 1\\. numbered\n"
    document = parse(text)
    assert [c.text for c in document.children[0].children] == ["> quoted", "1. numbered"]
    assert write(document) == text
    with pytest.raises(ControlledMarkdownError) as err:
        parse("# T\n- > quoted\n")
    assert err.value.rule == "block-syntax"


def test_number_run():
    """The numbered statements under one parent run from 1 with no gap."""
    text = "# T\n1. one\n    - under\n2. two\n"
    document = parse(text)
    one = document.children[0].children[0]
    assert (one.number, one.text) == (1, "one")
    assert write(document) == text
    assert full(document) == "# T\n\n1. one\n    - under\n2. two\n"
    with pytest.raises(ControlledMarkdownError) as err:
        parse("# T\n1. one\n3. three\n")
    assert err.value.rule == "number-run"


def test_table_renders_under_its_parent():
    """A table renders at the list indent, with no `>`, so a Markdown reader
    shows it as a table."""
    text = "# T\n- parent\n    | A | B |\n    | --- | --- |\n    | 1 | 2 |\n"
    document = parse(text)
    table = document.children[0].children[0].children[0]
    assert (table.kind, table.text) == (TABLE, "| A | B |\n| --- | --- |\n| 1 | 2 |")
    assert write(document) == text
    assert full(document) == (
        "# T\n\n- parent\n\n    | A | B |\n    | --- | --- |\n    | 1 | 2 |\n"
    )


def test_code_renders_at_the_content_indent():
    """A code node renders with its fences at the list content indent, so a
    Markdown reader shows it as a code block."""
    text = "# T\n- parent\n    ```py\n    a = 1\n\n    b = 2\n    ```\n"
    document = parse(text)
    code = document.children[0].children[0].children[0]
    assert code.kind == CODE
    assert code.text == "```py\na = 1\n\nb = 2\n```"
    assert write(document) == text
    assert full(document) == (
        "# T\n\n- parent\n\n    ```py\n    a = 1\n\n    b = 2\n    ```\n"
    )


def test_blank_lines_kept():
    """The formatter keeps the writer's blank lines."""
    text = "# T\n- first\n\n- second\n    - under\n\n    - apart\n"
    assert write(parse(text)) == text
