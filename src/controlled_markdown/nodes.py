"""The node tree of Controlled Markdown: the `Node` every line of a
document becomes, the kinds of node, a heading's slug, and the error a
line that breaks a rule raises, with the rules it names."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum

# ---------------------------------------------------------------- errors


class Rule(StrEnum):
    """The rules a line can break, each by its short name."""

    ATTRIBUTE_FIRST = "attribute-first"
    ATTRIBUTE_LEAF = "attribute-leaf"
    ATTRIBUTE_NAME = "attribute-name"
    ATTRIBUTE_REPEAT = "attribute-repeat"
    ATTRIBUTE_RESERVED = "attribute-reserved"
    BLOCK_REPEAT = "block-repeat"
    BLOCK_SYNTAX = "block-syntax"
    CITATION_ANCHOR = "citation-anchor"
    CODE_CHILD = "code-child"
    CODE_FENCE = "code-fence"
    CODE_INDENT = "code-indent"
    CODE_NEST = "code-nest"
    CODE_PARENT = "code-parent"
    FRAGMENT_BREAK = "fragment-break"
    FRONT_MATTER = "front-matter"
    HANDBOOK_LINK = "handbook-link"
    HEADING_CLOSER = "heading-closer"
    HEADING_DEPTH = "heading-depth"
    HEADING_INDENT = "heading-indent"
    HOLE_NAME = "hole-name"
    ID_REPEAT = "id-repeat"
    INCLUDE_CYCLE = "include-cycle"
    INCLUDE_MISSING = "include-missing"
    INDENT_JUMP = "indent-jump"
    INDENT_TAB = "indent-tab"
    INDENT_WIDTH = "indent-width"
    INLINE_CYCLE = "inline-cycle"
    INLINE_MISSING = "inline-missing"
    LINK_ANCHOR = "link-anchor"
    LINK_MISSING = "link-missing"
    LINK_TEXT = "link-text"
    MCTX_LITERAL = "mctx-literal"
    MCTX_NESTED = "mctx-nested"
    NO_MARKER = "no-marker"
    NUMBER_RUN = "number-run"
    PARTIAL_SITES = "partial-sites"
    PATH_MISSING = "path-missing"
    QUOTE_CHILD = "quote-child"
    QUOTE_DOCUMENT = "quote-document"
    QUOTE_GUARD = "quote-guard"
    QUOTE_HEADING = "quote-heading"
    QUOTE_LITERAL = "quote-literal"
    QUOTE_MISSING = "quote-missing"
    QUOTE_NEST = "quote-nest"
    QUOTE_PARENT = "quote-parent"
    QUOTE_PRINCIPLE = "quote-principle"
    QUOTE_WORDS = "quote-words"
    TABLE_CHILD = "table-child"
    TABLE_NEST = "table-nest"
    TABLE_PARENT = "table-parent"
    VARIABLE_BLOCK = "variable-block"
    VARIABLE_MISSING = "variable-missing"
    VARIABLE_UNUSED = "variable-unused"


def finding_lines(rules: tuple[Rule, ...]) -> re.Pattern[str]:
    """The lines that report a finding of one of `rules`, in the form
    `ControlledMarkdownError` prints, with the file as `path`."""
    return re.compile(rf"^(?P<path>\S+):(?P<line>\d+): (?:{'|'.join(map(re.escape, rules))}): .*$",
                      re.MULTILINE)


class ControlledMarkdownError(Exception):
    """A line that breaks a rule. `rule` is the rule's short name."""

    def __init__(self, source: str, line: int, rule: Rule, message: str):
        self.source = source
        self.line = line
        self.rule = rule
        self.message = message
        super().__init__(f"{source}:{line}: {rule}: {message}")


# ---------------------------------------------------------------- nodes

# A heading's text as an anchor, the way a Markdown reader makes one.
SLUG_DROP = re.compile(r"[^\w\s-]")
SLUG_SPACE = re.compile(r"\s+")


def slug(text: str) -> str:
    """A heading's id when no `id` attribute names one: the text in lower
    case, each run of spaces as one hyphen, and the punctuation other than a
    hyphen dropped."""
    return SLUG_SPACE.sub("-", SLUG_DROP.sub("", text.lower()).strip())


INDENT = 4          # spaces per level

DOCUMENT = "document"
CONTENT = "content"
ATTRIBUTE = "attribute"
QUOTE = "quote"
TABLE = "table"
CODE = "code"
HEADING = "heading"


@dataclass
class Node:
    kind: str
    text: str = ""              # content text, heading text, quote body
    name: str = ""              # attribute name
    value: str | None = None    # attribute inline value
    depth: int = 0              # heading tree depth, 1 for a top heading
    line: int = 0
    source: str = ""
    children: list[Node] = field(default_factory=list)
    star: bool = False          # written as `* name`, which is spelling only
    blank: bool = False         # a blank line precedes it, which is spelling only
    front: str = ""             # a document's front matter block, verbatim
    number: int = 0             # a numbered statement's number, 0 for `- `

    def attributes(self) -> dict[str, Node]:
        return {c.name: c for c in self.children if c.kind == ATTRIBUTE}

    def has(self, name: str) -> bool:
        return name in self.attributes()

    def attr(self, name: str) -> str | None:
        """The value of the attribute of that name, or None."""
        node = self.attributes().get(name)
        return node.value if node is not None else None

    def contents(self) -> list[Node]:
        return [c for c in self.children if c.kind in (CONTENT, HEADING)]

    def anonymous(self) -> bool:
        """Whether the node carries no text of its own."""
        return self.kind == CONTENT and self.text == ""

    def shape(self) -> tuple:
        """The node without its line numbers or its spelling, for round-trip
        comparison. `* name` and `-` with `+ name` share one shape."""
        return (self.kind, self.text, self.name, self.value, self.depth,
                self.front, self.number,
                tuple(c.shape() for c in self.children))
