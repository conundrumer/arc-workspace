"""The parser of Controlled Markdown: text read into a tree of nodes, under
rule 10, the escape of a statement that opens with Markdown block syntax,
and the run of the numbers of numbered statements."""

from __future__ import annotations

import re

from controlled_markdown.nodes import (
    ATTRIBUTE,
    CODE,
    CONTENT,
    DOCUMENT,
    HEADING,
    INDENT,
    QUOTE,
    TABLE,
    ControlledMarkdownError,
    Node,
    Rule,
)


# ---------------------------------------------------------------- rule 10

# Markdown block syntax at the start of a statement. A `-`, `+`, `*`, or `#`
# counts only when a space or the line end follows it, which is what makes it
# a block in CommonMark.
BLOCK_RE = re.compile(
    r"(?:[-+*](?:[ \t]|$)"
    r"|#{1,6}(?:[ \t]|$)"
    r"|\d+[.)](?:[ \t]|$)"
    r"|>"
    r"|\|"
    r"|---"
    r"|==="
    r"|\[ \]"
    r"|```"
    r"|~~~"
    r"|<[A-Za-z!/])"
)
ESCAPE_RE = re.compile(r"(\d*)\\")


def unescape(text: str, source: str, line: int) -> str:
    """A statement's text with its escape taken off, or an error when it
    begins with unescaped block syntax."""
    m = ESCAPE_RE.match(text)
    if m is not None:
        bare = m.group(1) + text[m.end():]
        if BLOCK_RE.match(bare):
            return bare
    if BLOCK_RE.match(text):
        raise ControlledMarkdownError(source, line, Rule.BLOCK_SYNTAX,
                           "a statement begins with Markdown block syntax")
    return text


def escape(text: str) -> str:
    """A statement's text with an escape put on, where rule 10 needs one."""
    if not BLOCK_RE.match(text):
        return text
    m = re.match(r"(\d+)([.)])", text)
    if m is not None:
        return m.group(1) + "\\" + text[m.end(1):]
    return "\\" + text


# ---------------------------------------------------------------- parser

FRONT_FENCE = "---"


def split_front(text: str, source: str) -> tuple[str, str, int]:
    """A document's front matter block, the text under it, and the count of
    lines the block takes.

    A document may open with `---`, lines, and a closing `---`. The block is
    kept verbatim, with no trailing newline.
    """
    if not text.startswith(FRONT_FENCE + "\n"):
        return "", text, 0
    lines = text.split("\n")
    for i, line in enumerate(lines[1:], start=1):
        if line.rstrip() == FRONT_FENCE:
            return "\n".join(lines[:i + 1]), "\n".join(lines[i + 1:]), i + 1
    raise ControlledMarkdownError(source, 1, Rule.FRONT_MATTER,
                              "a front matter block needs a closing `---`")


# The blocks that hold verbatim lines. A block runs while its own marker
# stays at one indent under one parent.
BLOCK_MARKER = {QUOTE: ">", TABLE: "|"}
BLOCK_KIND = {marker: kind for kind, marker in BLOCK_MARKER.items()}
# The rules a line breaks under a block of each kind, a closed code node
# among them: a line that opens with the block's own marker, and any other
# line.
NEST_RULES = {QUOTE: (Rule.QUOTE_NEST, Rule.QUOTE_CHILD),
              TABLE: (Rule.TABLE_NEST, Rule.TABLE_CHILD),
              CODE: (Rule.CODE_NEST, Rule.CODE_CHILD)}
# The rule a block of each kind breaks with no parent node.
PARENT_RULES = {QUOTE: Rule.QUOTE_PARENT, TABLE: Rule.TABLE_PARENT}

FENCE_RE = re.compile(r"^(`{3,}|~{3,})(.*)$")
NUMBERED_RE = re.compile(r"^(\d+)\. (.*)$")

HEADING_RE = re.compile(r"^(#{1,})(?:[ \t]+(.*))?$")
CLOSER_RE = re.compile(r"\s#+$")
RESERVED = {"heading"}


def split_named(body: str) -> tuple[str, str | None]:
    """An attribute line as its name and its value."""
    if ": " in body:
        name, value = body.split(": ", 1)
        return name.strip(), value
    if body.endswith(":"):
        return body[:-1].strip(), ""
    return body.strip(), None


def parse(text: str, source: str = "<input>", fragment: bool = False) -> Node:
    """Text as a document node. Raises ControlledMarkdownError on the first broken rule."""
    front, text, offset = split_front(text, source)
    document = Node(DOCUMENT, source=source, front=front)
    # The open headings, shallowest first, each with its `#` count and the
    # level it sits at. A heading sits at column zero, or under a directive at
    # that directive's child indent.
    heads: list[tuple[Node, int, int]] = []
    stack: list[Node] = [document]  # stack[i] is the parent of a line at level i
    block: Node | None = None   # the open quote or table
    block_level = 0
    block_parent: Node | None = None
    code: Node | None = None    # the open code node
    code_indent = 0
    code_level = 0
    code_parent: Node | None = None
    code_fence = ""             # the opening fence, which the closer matches
    pending_blank = False
    blank_before: set[int] = set()  # the lines a blank line precedes

    for num, line in enumerate(text.split("\n"), start=offset + 1):
        line = line.rstrip()
        if code is not None:
            if not line.strip():
                code.text += "\n"
                continue
            lead = line[:len(line) - len(line.lstrip(" \t"))]
            if "\t" in lead:
                raise ControlledMarkdownError(source, num, Rule.INDENT_TAB,
                                   "indentation holds a tab")
            if len(lead) < code_indent:
                raise ControlledMarkdownError(source, num, Rule.CODE_INDENT,
                                   "a code line sits at the fence's indent")
            body = line[code_indent:]
            code.text += "\n" + body
            if len(lead) == code_indent and _closes(body, code_fence):
                # A closed code node still holds its place, so a deeper line
                # after it reads as nesting under it.
                block, block_level, block_parent = code, code_level, code_parent
                code = None
            continue
        if not line.strip():
            block = None
            pending_blank = True
            continue
        if pending_blank:
            blank_before.add(num)
            pending_blank = False

        lead = line[:len(line) - len(line.lstrip(" \t"))]
        if "\t" in lead:
            raise ControlledMarkdownError(source, num, Rule.INDENT_TAB,
                               "indentation holds a tab")
        if len(lead) % INDENT:
            raise ControlledMarkdownError(source, num, Rule.INDENT_WIDTH,
                               "indentation is not a multiple of four spaces")
        level = len(lead) // INDENT
        body = line[len(lead):]

        # --- headings
        if body.startswith("#"):
            m = HEADING_RE.match(body)
            if m is None or len(m.group(1)) > 6:
                raise ControlledMarkdownError(source, num, Rule.HEADING_DEPTH,
                                   "a heading takes one to six `#`")
            title = (m.group(2) or "").strip()
            if title and CLOSER_RE.search(title):
                raise ControlledMarkdownError(source, num, Rule.HEADING_CLOSER,
                                   "a heading takes no closing `#`")
            count = len(m.group(1))
            if title:
                title = unescape(title, source, num)
            if level > len(stack) - 1:
                raise ControlledMarkdownError(source, num, Rule.INDENT_JUMP,
                                   "indentation goes deeper by more than one level")
            if level and not _is_directive(stack[level]):
                raise ControlledMarkdownError(source, num, Rule.HEADING_INDENT,
                                   "a heading sits at column zero or under a "
                                   "directive")
            while heads and (heads[-1][2] > level
                             or (heads[-1][2] == level and heads[-1][1] >= count)):
                heads.pop()
            under = heads[-1][0] if heads else document
            parent = stack[level] if level else under
            node = Node(HEADING, text=title, depth=len(heads) + 1,
                        line=num, source=source)
            parent.children.append(node)
            heads.append((node, count, level))
            stack = stack[:level] + [node]
            block = None
            continue

        fence = FENCE_RE.match(body)
        numbered = None if fence else NUMBERED_RE.match(body)
        marker = "```" if fence else "1." if numbered else body[0]
        if fence:
            rest = body
        elif numbered:
            rest = numbered.group(2)
        elif marker == "|":
            rest = body      # a table line is verbatim, marker and all
        elif marker not in "-+*>" or (len(body) > 1 and body[1] != " "):
            raise ControlledMarkdownError(source, num, Rule.NO_MARKER,
                               "a line opens with `-`, `+`, `*`, `>`, `|`, "
                               "`1.`, or `#`")
        else:
            rest = body[2:] if len(body) > 2 else ""

        # --- block continuation and termination
        if block is not None:
            own = BLOCK_MARKER.get(block.kind, "```")
            if level > block_level:
                nest, child = NEST_RULES[block.kind]
                rule = nest if marker == own else child
                raise ControlledMarkdownError(source, num, rule,
                                   f"nothing nests under a {block.kind}")
            if marker != own or level != block_level \
                    or stack[level] is not block_parent:
                block = None

        if level > len(stack) - 1:
            raise ControlledMarkdownError(source, num, Rule.INDENT_JUMP,
                               "indentation goes deeper by more than one level")
        parent = stack[level]
        if parent.kind == ATTRIBUTE:
            raise ControlledMarkdownError(source, num, Rule.ATTRIBUTE_LEAF,
                               "nothing indents under a `+` line")

        if fence is not None:
            if parent.kind == DOCUMENT and not fragment:
                raise ControlledMarkdownError(source, num, Rule.CODE_PARENT,
                                   "a code block needs a parent node")
            node = Node(CODE, text=body, line=num, source=source)
            parent.children.append(node)
            stack = stack[:level + 1]
            code, code_indent, code_fence = node, len(lead), fence.group(1)
            code_level, code_parent = level, parent
            continue

        if marker in BLOCK_KIND:
            kind = BLOCK_KIND[marker]
            if block is not None:
                block.text += "\n" + rest
                continue
            if parent.kind == DOCUMENT:
                raise ControlledMarkdownError(source, num, PARENT_RULES[kind],
                                   f"a {kind} needs a parent node")
            node = Node(kind, text=rest, line=num, source=source)
            parent.children.append(node)
            stack = stack[:level + 1]
            block, block_level, block_parent = node, level, parent
            continue

        if marker in ("-", "1."):
            node = Node(CONTENT, text=unescape(rest, source, num),
                        line=num, source=source,
                        number=int(numbered.group(1)) if numbered else 0)
            parent.children.append(node)
            stack = stack[:level + 1] + [node]
            continue

        if not rest.strip():
            raise ControlledMarkdownError(source, num, Rule.ATTRIBUTE_NAME,
                               "an attribute needs a name")
        name, value = split_named(unescape(rest, source, num))
        if not name:
            raise ControlledMarkdownError(source, num, Rule.ATTRIBUTE_NAME,
                               "an attribute needs a name")
        if name in RESERVED:
            raise ControlledMarkdownError(source, num, Rule.ATTRIBUTE_RESERVED,
                               f"`{name}` is a reserved attribute name")

        if marker == "*":
            # A directive: a node with no text of its own, holding one
            # attribute, on the lines under it.
            node = Node(CONTENT, line=num, source=source, star=True)
            node.children.append(Node(ATTRIBUTE, name=name, value=value,
                                      line=num, source=source))
        else:
            if name in parent.attributes():
                raise ControlledMarkdownError(source, num, Rule.ATTRIBUTE_REPEAT,
                                   f"`{name}` is already set on this node")
            node = Node(ATTRIBUTE, name=name, value=value, line=num,
                        source=source)

        parent.children.append(node)
        stack = stack[:level + 1] + [node]

    if code is not None:
        raise ControlledMarkdownError(source, code.line, Rule.CODE_FENCE,
                                  "a code block needs a closing fence")
    _check_numbers(document)
    _mark_blank(document, blank_before)
    return document


def _closes(line: str, fence: str) -> bool:
    """Whether a line, its indent taken off, closes the code block `fence`
    opened: a run of the fence's character at least as long, and nothing
    after it."""
    m = FENCE_RE.match(line)
    return (m is not None and m.group(1)[0] == fence[0]
            and len(m.group(1)) >= len(fence) and not m.group(2).strip())


def _mark_blank(node: Node, blank_before: set[int]) -> None:
    for child in node.children:
        child.blank = child.line in blank_before
        _mark_blank(child, blank_before)


# ---------------------------------------------------------------- numbering

def _check_numbers(node: Node) -> None:
    """A numbered statement opens with `1. `. The numbered statements under
    one parent run 1, 2, 3, with no gap and no repeat."""
    want = 1
    for child in node.children:
        if child.number:
            if child.number != want:
                raise ControlledMarkdownError(
                    child.source, child.line, Rule.NUMBER_RUN,
                    f"a numbered statement runs 1, 2, 3; `{want}` is next")
            want += 1
        _check_numbers(child)


# ---------------------------------------------------------------- `*` lines

def _directive_attribute(node: Node) -> Node | None:
    """The attribute a `*` line holds, when the node was written that way."""
    if not node.star or node.text:
        return None
    for child in node.children:
        if child.kind == ATTRIBUTE:
            return child
    return None


def _is_directive(node: Node) -> bool:
    """Whether a node was written as a `*` line."""
    return _directive_attribute(node) is not None
