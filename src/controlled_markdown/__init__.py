"""Controlled Markdown: parser, formatter, and renderers.

A document is a tree of nodes. Every line is one node, and every line is valid
CommonMark. `parse` reads text into a tree, `write` puts a tree back as
canonical text, and the renderers project a tree down to ordinary Markdown for
an agent to read.

A node carries attributes. `+ name: value` is an attribute of the node it is
nested under, and it describes that node. `* name: value` is a directive: a
node with no text of its own, carrying that attribute, and the lines under it
are the lines it governs.

`Registry` holds the documents a render draws on, together with each document's
path and its sections, keyed by the slug of each heading's text. An `include`
directive names a file and brings that whole document; an `inline` directive
names a section by `#<id>` or `<path>#<id>` and brings the lines under its
heading. The registry reads a document the first time a directive names it.

A render takes the values its variables read. `{{name}}` in a node's text is
replaced by the value of that name, and `if` and `unless` read the values
too.

A document may open with a front matter block, `---` to `---`. `parse` keeps it
verbatim, `write` puts it back unchanged, and a render leaves it out.
"""

from __future__ import annotations

import ast
import functools
import inspect
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

from engine import checkout
from engine.quotes import quotes

# ---------------------------------------------------------------- errors


class ControlledMarkdownError(Exception):
    """A line that breaks a rule. `rule` is the rule's short name."""

    def __init__(self, source: str, line: int, rule: str, message: str):
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
NOTICE = "notice"    # a sentence the renderer inserts, not a parsed line

FULL = "full"
INDEX = "index"
EDITIONS = (FULL, INDEX)


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
        raise ControlledMarkdownError(source, line, "block-syntax",
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
    raise ControlledMarkdownError(source, 1, "front-matter",
                              "a front matter block needs a closing `---`")


# The blocks that hold verbatim lines. A block runs while its own marker
# stays at one indent under one parent.
BLOCK_MARKER = {QUOTE: ">", TABLE: "|"}
BLOCK_KIND = {marker: kind for kind, marker in BLOCK_MARKER.items()}

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
                raise ControlledMarkdownError(source, num, "indent-tab",
                                   "indentation holds a tab")
            if len(lead) < code_indent:
                raise ControlledMarkdownError(source, num, "code-indent",
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
            raise ControlledMarkdownError(source, num, "indent-tab",
                               "indentation holds a tab")
        if len(lead) % INDENT:
            raise ControlledMarkdownError(source, num, "indent-width",
                               "indentation is not a multiple of four spaces")
        level = len(lead) // INDENT
        body = line[len(lead):]

        # --- headings
        if body.startswith("#"):
            m = HEADING_RE.match(body)
            if m is None or len(m.group(1)) > 6:
                raise ControlledMarkdownError(source, num, "heading-depth",
                                   "a heading takes one to six `#`")
            title = (m.group(2) or "").strip()
            if title and CLOSER_RE.search(title):
                raise ControlledMarkdownError(source, num, "heading-closer",
                                   "a heading takes no closing `#`")
            count = len(m.group(1))
            if title:
                title = unescape(title, source, num)
            if level > len(stack) - 1:
                raise ControlledMarkdownError(source, num, "indent-jump",
                                   "indentation goes deeper by more than one level")
            if level and not _is_directive(stack[level]):
                raise ControlledMarkdownError(source, num, "heading-indent",
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
            raise ControlledMarkdownError(source, num, "no-marker",
                               "a line opens with `-`, `+`, `*`, `>`, `|`, "
                               "`1.`, or `#`")
        else:
            rest = body[2:] if len(body) > 2 else ""

        # --- block continuation and termination
        if block is not None:
            own = BLOCK_MARKER.get(block.kind, "```")
            if level > block_level:
                rule = f"{block.kind}-{'nest' if marker == own else 'child'}"
                raise ControlledMarkdownError(source, num, rule,
                                   f"nothing nests under a {block.kind}")
            if marker != own or level != block_level \
                    or stack[level] is not block_parent:
                block = None

        if level > len(stack) - 1:
            raise ControlledMarkdownError(source, num, "indent-jump",
                               "indentation goes deeper by more than one level")
        parent = stack[level]
        if parent.kind == ATTRIBUTE:
            raise ControlledMarkdownError(source, num, "attribute-leaf",
                               "nothing indents under a `+` line")

        if fence is not None:
            if parent.kind == DOCUMENT and not fragment:
                raise ControlledMarkdownError(source, num, "code-parent",
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
                raise ControlledMarkdownError(source, num, f"{kind}-parent",
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
            raise ControlledMarkdownError(source, num, "attribute-name",
                               "an attribute needs a name")
        name, value = split_named(unescape(rest, source, num))
        if not name:
            raise ControlledMarkdownError(source, num, "attribute-name",
                               "an attribute needs a name")
        if name in RESERVED:
            raise ControlledMarkdownError(source, num, "attribute-reserved",
                               f"`{name}` is a reserved attribute name")

        if marker == "*":
            # A directive: a node with no text of its own, carrying one
            # attribute, on the lines under it.
            node = Node(CONTENT, line=num, source=source, star=True)
            node.children.append(Node(ATTRIBUTE, name=name, value=value,
                                      line=num, source=source))
        else:
            if name in parent.attributes():
                raise ControlledMarkdownError(source, num, "attribute-repeat",
                                   f"`{name}` is already set on this node")
            node = Node(ATTRIBUTE, name=name, value=value, line=num,
                        source=source)

        parent.children.append(node)
        stack = stack[:level + 1] + [node]

    if code is not None:
        raise ControlledMarkdownError(source, code.line, "code-fence",
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
                    child.source, child.line, "number-run",
                    f"a numbered statement runs 1, 2, 3; `{want}` is next")
            want += 1
        _check_numbers(child)


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
                                          "attribute-first",
                                          "a `+` line comes before every "
                                          "other line under one parent")
        else:
            seen = True
        check_order(child)


# ----------------------------------------------------------------- prose

def mctx(prose):
    """A string a program holds that enters an agent's context. On a str it
    strips the common indent and the blank lines around it; on a dict it
    returns the dict as it stands, each value being a fragment of its own.

    The name is the marker the check reads: every `mctx` call in the repo
    gives up its strings, and each is checked as the format."""
    if isinstance(prose, str):
        return dedent(prose)
    return prose


def dedent(text: str) -> str:
    """Text with the indent its lines share taken off and its outer blank
    lines dropped."""
    lines = text.split("\n")
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    pad = min((len(ln) - len(ln.lstrip(" ")) for ln in lines if ln.strip()),
              default=0)
    return "\n".join(ln[pad:] if ln.strip() else "" for ln in lines)


# A hole a fragment leaves for the program to fill: `{name}` in Python,
# `${name}` in JavaScript. The check puts one opaque word in its place, since
# what stands there is a value and not prose.
PY_HOLE_RE = re.compile(r"\{\{|\}\}|\{([A-Za-z_][A-Za-z0-9_.]*)\}")
JS_HOLE_RE = re.compile(r"\$\{([^}]*)\}")
HOLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*$")
FILLED = "value"


@dataclass
class Fragment:
    """One string a program holds, with where it stands."""
    text: str
    file: Path
    source: str
    line: int


def _py_fragments(tree, path: Path, source: str):
    """Every string an `mctx` call in a Python file gives up. A call whose
    argument is not a literal is an error: the prose is read without running
    the program."""
    def values(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.lineno, dedent(node.value)
        elif isinstance(node, ast.Dict):
            for v in node.values:
                yield from values(v)
        else:
            raise ControlledMarkdownError(
                source, node.lineno, "mctx-literal",
                "`mctx` takes a string or a dict of them, written out")

    def tagged(func) -> bool:
        """The call is `mctx`, by its own name or through a module."""
        if isinstance(func, ast.Name):
            return func.id == "mctx"
        return isinstance(func, ast.Attribute) and func.attr == "mctx"

    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and tagged(node.func)
                and len(node.args) == 1):
            for line, text in values(node.args[0]):
                yield Fragment(text, path, source, line)


# The tag, where it opens a literal: a name on its own, and not the word in
# a comment or inside a span.
JS_TAG_RE = re.compile(r"(?<![A-Za-z0-9_$`])mctx`")

def _js_fragments(text: str, path: Path, source: str):
    """Every string an `mctx` tag in a JavaScript file gives up. A backtick
    inside the literal opens a nested one, which the check does not read."""
    for m in JS_TAG_RE.finditer(text):
        at = m.start()
        line = text.count("\n", 0, at) + 1
        j, depth, body = m.end(), 0, []
        while j < len(text):
            ch = text[j]
            if ch == "\\" and j + 1 < len(text):
                body.append(text[j + 1])
                j += 2
                continue
            if ch == "$" and text[j:j + 2] == "${":
                depth += 1
            elif ch == "}" and depth:
                depth -= 1
            elif ch == "`":
                if depth:
                    raise ControlledMarkdownError(
                        source, line + "".join(body).count("\n"), "mctx-nested",
                        "a backtick inside an `mctx` literal opens a nested "
                        "one")
                break
            body.append(ch)
            j += 1
        yield Fragment(dedent("".join(body)), path, source, line)


PY_WHOLE_RE = re.compile(r"^\s*\{[A-Za-z_][A-Za-z0-9_.]*\}\s*$")
JS_WHOLE_RE = re.compile(r"^\s*\$\{[^}]*\}\s*$")


def _placed(text: str, whole: re.Pattern) -> str:
    """A line that is one hole places a fragment of its own, checked where
    that fragment stands, so this one reads past it."""
    return "\n".join("" if whole.match(ln) else ln for ln in text.split("\n"))


def _holed(fragment: Fragment) -> str:
    """The fragment with each hole replaced by one opaque word, so what the
    program fills is read as a value and not as prose. A line that is one
    hole is left blank: it places a fragment the check reads on its own."""
    if fragment.file.suffix == ".py":
        def py_hole(m):
            if m.group(1) is None:
                return m.group(0)[0]
            return FILLED
        return PY_HOLE_RE.sub(py_hole, _placed(fragment.text, PY_WHOLE_RE))

    def js_hole(m):
        if not HOLE_NAME_RE.match(m.group(1).strip()):
            raise ControlledMarkdownError(
                fragment.source, fragment.line, "hole-name",
                f"`${{{m.group(1)}}}` is not a name; a fragment leaves a hole "
                f"for a value the program computes above it")
        return FILLED
    return JS_HOLE_RE.sub(js_hole, _placed(fragment.text, JS_WHOLE_RE))


MARKER_RE = re.compile(r"^(?:[-+*>|]\s|\d+\.\s|#{1,6}\s|`{3,}|~{3,})")


def check_fragment(fragment: Fragment, root: Path | None = None) -> None:
    """One fragment under the rules its shape takes. A fragment that opens
    with a marker is format lines and takes every rule; any other fragment is
    the text of one statement and takes the text rules."""
    text = _holed(fragment)
    opening = next((ln for ln in text.split("\n") if ln.strip()), "")
    if MARKER_RE.match(opening):
        # A fragment is a run of lines, not a document: the brief that places
        # it supplies the line a block stands under.
        document = parse(text, fragment.source, fragment=True)
        check_order(document)
        check_blocks(document)
        check_links(document, fragment.file, root)
        return
    if "\n" in text:
        raise ControlledMarkdownError(
            fragment.source, 1, "fragment-break",
            "a fragment that is one statement holds one line")
    node = Node(CONTENT, text=text, source=fragment.source, line=1)
    document = Node(DOCUMENT, source=fragment.source)
    document.children = [node]
    check_links(document, fragment.file, root)


def fragments(path: Path, source: str):
    """Every fragment a file holds."""
    text = path.read_text()
    if path.suffix == ".py":
        if "mctx" not in text:
            return
        yield from _py_fragments(ast.parse(text, str(path)), path, source)
    elif "mctx`" in text:
        yield from _js_fragments(text, path, source)


def check_file_fragments(path: Path, source: str,
                         root: Path | None = None) -> None:
    """Every fragment a file holds, checked where it stands. An error carries
    the file and the fragment's own line, offset within a multi-line one."""
    for fragment in fragments(path, source):
        try:
            check_fragment(fragment, root)
        except ControlledMarkdownError as err:
            raise ControlledMarkdownError(
                source, fragment.line + max(err.line - 1, 0), err.rule,
                err.message) from None


# A path a document takes in the repo: the shapes the document set uses, so a
# literal that names one is checked against the tree.
DOC_PATH_RE = re.compile(
    r"^(?:docs/[\w./-]+\.md|prompts/[\w./-]+\.md|CLAUDE\.md"
    r"|\.claude/[\w./-]+\.md)$")


def _named_paths(path: Path, text: str):
    """Every string a file holds that names a document, with its line. A
    string holding a hole or a wildcard names a shape and is passed over."""
    def wanted(value: str, line: int):
        if "{" in value or "*" in value or not DOC_PATH_RE.match(value):
            return
        yield line, value

    if path.suffix == ".py":
        for node in ast.walk(ast.parse(text, str(path))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                yield from wanted(node.value, node.lineno)
        return
    for m in JS_STRING_RE.finditer(text):
        yield from wanted(m.group(2), text.count("\n", 0, m.start()) + 1)


JS_STRING_RE = re.compile(r"""(['"])((?:[^'"\\\n]|\\.)*?)\1""")


def check_paths(path: Path, source: str, root: Path) -> None:
    """Every document a file names by path stands in the tree. A name that
    goes stale is a reference no reader can follow."""
    for line, value in _named_paths(path, path.read_text()):
        if not (root / value).exists():
            raise ControlledMarkdownError(
                source, line, "path-missing",
                f"no file at `{value}`")


# A `quotes` call names a handbook document, a heading in it and the words
# under that heading. The checker's own rule on which of its functions carry
# one is `checker.quoting`'s.
LINE_MARKER_RE = re.compile(r"^\s*(?:[-+*]\s+|\d+\.\s+)?")


@dataclass(frozen=True)
class Quote:
    """One `quotes(document, heading, words)` call, read as a literal."""
    line: int
    document: str
    heading: str
    words: str


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _quote(node: ast.Call, source: str) -> Quote:
    """The three strings of a `quotes` call, which the check reads without
    running the program."""
    names = ("document", "heading", "words")
    given = dict(zip(names, node.args))
    given.update((k.arg, k.value) for k in node.keywords if k.arg in names)
    values = [v.value for name in names
              if isinstance(v := given.get(name), ast.Constant)
              and isinstance(v.value, str)]
    if len(values) != 3 or len(node.args) + len(node.keywords) != 3:
        raise ControlledMarkdownError(
            source, node.lineno, "quote-literal",
            "a `quotes` call takes three string literals: the document, the "
            "heading and the words")
    return Quote(node.lineno, *values)


def _squeezed(text: str) -> str:
    return " ".join(text.split())


def _headings(node: Node) -> Iterator[Node]:
    """The headings under `node`, in document order."""
    for child in node.children:
        if child.kind == HEADING:
            yield child
            yield from _headings(child)


@functools.cache
def handbook_sections(document: Path) -> dict[str, list[str]]:
    """Each heading's text, as `parse` reads it, mapped to the text that
    stands under it, its subsections included, as one line per heading of
    that text with each line's marker and indent dropped."""
    text = document.read_text()
    lines = text.split("\n")
    heads = [(h.line - 1, h.depth, h.text)
             for h in _headings(parse(text, str(document)))]
    out: dict[str, list[str]] = {}
    for k, (i, depth, title) in enumerate(heads):
        end = next((j for j, d, _ in heads[k + 1:] if d <= depth),
                   len(lines))
        body = (LINE_MARKER_RE.sub("", ln, count=1) for ln in lines[i + 1:end])
        out.setdefault(title, []).append(_squeezed(" ".join(body)))
    return out


def check_quotes(path: Path, source: str) -> list[ControlledMarkdownError]:
    """Every `quotes` call names a handbook document and a heading in it,
    and its words stand under that heading, up to line wrapping."""
    text = path.read_text()
    if quotes.__name__ not in text:
        return []
    tree = ast.parse(text, str(path))
    errors: list[ControlledMarkdownError] = []
    found: list[Quote] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_name(node) == quotes.__name__:
            try:
                found.append(_quote(node, source))
            except ControlledMarkdownError as err:
                errors.append(err)
    for q in found:
        document = checkout.handbook() / q.document
        if not document.is_file():
            errors.append(ControlledMarkdownError(
                source, q.line, "quote-document",
                f"no handbook document `{q.document}`"))
            continue
        under = handbook_sections(document).get(q.heading)
        if under is None:
            errors.append(ControlledMarkdownError(
                source, q.line, "quote-heading",
                f"no heading \"{q.heading}\" in `{q.document}`"))
        elif not any(_squeezed(q.words) in body for body in under):
            errors.append(ControlledMarkdownError(
                source, q.line, "quote-words",
                f"not under \"{q.heading}\" in `{q.document}`: "
                f"\"{_squeezed(q.words)}\""))
    return errors


def check_quote_rule(shown: Callable[[Path], str]
                     ) -> list[ControlledMarkdownError]:
    """Each check or survey of the checker that breaks its rule on the words
    it rests on (`checker.quoting`), at its `def` line, its file as `shown`
    gives it."""
    from checker.quoting import (PRINCIPLES, Breach, checks_and_surveys,
                                 unquoted)
    sentence = {
        Breach.GUARD: "`{name}` carries a `guard`, which only a hint or lint "
                      "check may carry",
        Breach.MISSING: "`{name}` carries no `quotes`",
        Breach.PRINCIPLE: "`{name}` carries no `quotes` from `{principles}`",
    }
    errors: list[ControlledMarkdownError] = []
    for u in unquoted(checks_and_surveys()):
        lines, first = inspect.getsourcelines(u.function)
        at = first + next(i for i, ln in enumerate(lines)
                          if ln.lstrip().startswith(("def ", "async def ")))
        errors.append(ControlledMarkdownError(
            shown(Path(inspect.getfile(u.function))), at, u.breach.value,
            sentence[u.breach].format(name=u.function.__name__,
                                      principles=PRINCIPLES)))
    return errors


# The lib's doc comments: `//!` heads a file's doc and `///` an item's. Each
# line is the text of one statement, so it takes the rules on a statement's
# text and neither the marker nor the indent rules.
DL_DOC_RE = re.compile(r"^\s*(?://!|///)[ \t]?(.*)$")


def dl_fragments(path: Path, source: str):
    """Every doc-comment line a Souffle file holds. A line blank after its
    marker carries no prose."""
    for n, line in enumerate(path.read_text().split("\n"), 1):
        m = DL_DOC_RE.match(line)
        if m is not None and m.group(1).strip():
            yield Fragment(m.group(1).strip(), path, source, n)


def check_dl_comments(path: Path, source: str, root: Path | None = None):
    """Every doc-comment line, read as the text of one statement."""
    for fragment in dl_fragments(path, source):
        node = Node(CONTENT, text=fragment.text, source=source,
                    line=fragment.line)
        document = Node(DOCUMENT, source=source)
        document.children = [node]
        check_links(document, path, root)


def reached(entry: Path, registry: Registry) -> set[str]:
    """Every document the composition at `entry` reaches, by source name: the
    entry, what it includes, and what those include, down."""
    out: set[str] = set()

    def walk(path: Path) -> None:
        try:
            document = registry.open(path)
        except OSError:
            return
        if document.source in out:
            return
        out.add(document.source)
        for node in _walk(document):
            for name in (INCLUDE, INLINE):
                if not node.has(name):
                    continue
                where = (node.attr(name) or "").strip().partition("#")[0]
                if where:
                    walk(path.parent / where)

    walk(entry)
    return out


def carried(node: Node) -> Iterator[Node]:
    """Every node a render carries: the lines under a `comment` are the
    editor's and reach no reader."""
    for child in node.children:
        if child.has(COMMENT):
            continue
        yield child
        yield from carried(child)


def check_closure(entries: list[Path], document_set: set[Path],
                  root: Path) -> None:
    """A document a composition includes links only to another document in
    that set, or to a file outside the document set. A link to a document the
    render leaves out sends its reader where the render does not go.

    An entry document is the composition itself, and its lead is its own: it
    points an editor at what the render leaves out, so it is not closed. Only
    the lines a render carries count, so a link under a `comment` is the
    editor's and not a reader's.
    """
    registry = Registry(root)
    opened = {registry.rel(registry.open(e)) for e in entries}
    inside: set[str] = set()
    for entry in entries:
        inside |= reached(entry, registry)
    for source in sorted(inside - opened):
        document = registry.documents[source]
        file = registry.sources[source]
        for node in carried(document):
            if node.kind == CODE or not node.text:
                continue
            for _, _, path, _ in _text_links(node):
                if not path:
                    continue
                target = target_of(path, file, root)
                if target not in document_set:
                    continue
                if registry.rel(registry.open(target)) not in inside:
                    raise ControlledMarkdownError(
                        source, node.line, "handbook-link",
                        f"`{path}` is a document the handbook does not carry")


# The heading whose sections are the partials of a document: the runs of
# lines the document's own messages inline.
PARTIALS = "Partials"


def partials(document: Node) -> list[Node]:
    """The sections under a `Partials` heading of `document`: the headings one
    level under it. A heading deeper than that belongs to a partial's body."""
    out: list[Node] = []
    for node in _walk(document):
        if node.kind == HEADING and node.text == PARTIALS:
            out.extend(c for c in node.children if c.kind == HEADING)
    return out


def inline_sites(documents: list[tuple[Path, Node]]) -> dict[tuple[Path, str], int]:
    """How many `inline` directives reach each section, keyed by the target
    document's resolved path and the id the directive names. A directive with
    no path before the `#` reaches its own document."""
    out: dict[tuple[Path, str], int] = {}
    for file, document in documents:
        for node in _walk(document):
            value = node.attr(INLINE)
            if value is None:
                continue
            where, hashed, ident = value.strip().partition("#")
            where, ident = where.strip(), ident.strip()
            if not hashed or not ident:
                continue
            target = (file.parent / where).resolve() if where else file
            out[(target, ident)] = out.get((target, ident), 0) + 1
    return out


# How many sites a partial is inlined at. A run of lines one site uses belongs
# at that site.
PARTIAL_SITES = 2


def check_partial_sites(
        documents: list[tuple[Path, Node]]) -> list[ControlledMarkdownError]:
    """Each partial is inlined at `PARTIAL_SITES` sites at least, counted over
    the whole document set. Each file is given as its resolved path and its
    parsed document, and the errors come back one per partial."""
    sites = inline_sites(documents)
    out: list[ControlledMarkdownError] = []
    for file, document in documents:
        for heading in partials(document):
            ident = slug(heading.text)
            count = sites.get((file.resolve(), ident), 0)
            if count < PARTIAL_SITES:
                out.append(ControlledMarkdownError(
                    heading.source, heading.line, "partial-sites",
                    f"`{ident}` is a partial inlined at {count} "
                    f"{'site' if count == 1 else 'sites'}; a partial is "
                    f"inlined at two sites at least"))
    return out


def check_blocks(node: Node) -> None:
    """A line has at most one block under it, a block being a code node, a
    quote, or a table. Two quotes a blank line apart are two blocks. The
    formatter does not settle this, so a document is checked for it."""
    seen = False
    for child in node.children:
        if child.kind in (CODE, QUOTE, TABLE):
            if seen:
                raise ControlledMarkdownError(child.source, child.line,
                                          "block-repeat",
                                          "a line carries one code node, "
                                          "quote, or table at most")
            seen = True
        check_blocks(child)


LINK_RE = re.compile(r"\[([^\]\n]*)\]\(([^)\s]+)\)")
SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.-]*:|^//|^#")


def _text_links(node: Node) -> Iterator[tuple[Node, str, str, str]]:
    """Every link in one node's text, as (node, text, path, slug). A backtick
    span is literal, so a link written inside one is text."""
    for part in SPAN_RE.split(node.text):
        if part.startswith("`"):
            continue
        for m in LINK_RE.finditer(part):
            target = m.group(2)
            if SCHEME_RE.match(target):
                continue
            path, _, slug = target.partition("#")
            yield node, m.group(1), path, slug


def links(node: Node) -> Iterator[tuple[Node, str, str, str]]:
    """Every link under `node`."""
    for child in _walk(node):
        if child.kind == CODE or not child.text:
            continue
        yield from _text_links(child)


def target_of(path: str, file: Path, root: Path | None = None) -> Path:
    """Where a link's target stands. A target that opens with `./` or `../`
    is relative to the document that holds it; every other target is relative
    to the repo root, since that is where a session runs."""
    if not path:
        return file.resolve()
    base = file.parent if path.startswith(("./", "../")) else (root or Path.cwd())
    return (base / path).resolve()


def check_links(document: Node, file: Path, root: Path | None = None) -> None:
    """Every link in the document resolves: the file or directory stands where
    `target_of` puts it, and a slug names a heading of that file whose text the
    link text gives. An external target is skipped."""
    for node, text, path, ident in links(document):
        target = target_of(path, file, root)
        if not target.exists():
            raise ControlledMarkdownError(node.source, node.line, "link-missing",
                                      f"nothing at `{path}`")
        if not ident:
            continue
        if not target.is_file():
            raise ControlledMarkdownError(node.source, node.line, "link-missing",
                                      f"`{path}` is a directory and holds no "
                                      f"heading `{ident}`")
        heads = {slug(h.text): h.text for h in _walk(
            parse(target.read_text(), str(target))) if h.kind == HEADING}
        if ident not in heads:
            raise ControlledMarkdownError(node.source, node.line, "link-missing",
                                      f"no heading `{ident}` in `{path}`")
        if text != heads[ident]:
            raise ControlledMarkdownError(node.source, node.line, "link-text",
                                      f"a link to a heading reads as that "
                                      f"heading: `{heads[ident]}`")


def check_text_links(text: str, file: Path, source: str,
                     root: Path | None = None) -> None:
    """Every link in raw text resolves, each reported at its own line. The
    text is not parsed, so a code file is read for its links and nothing
    else."""
    for n, line in enumerate(text.split("\n"), 1):
        if "](" not in line:
            continue
        node = Node(CONTENT, text=line, source=source, line=n)
        document = Node(DOCUMENT, source=source)
        document.children = [node]
        check_links(document, file, root)


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


# ---------------------------------------------------------------- registry


class Registry:
    """The documents a render draws on, their paths, and their sections.

    An include or an inline names a file, so the registry reads a document
    the first time one names it, and keys it by its resolved path. `load`
    reads one explicitly, for the document a render starts from.

    An id is scoped to its document: a heading's id is the slug of its text,
    lower case with each run of spaces as one hyphen, and two documents may
    use one name. A collision within a document is settled by renaming a
    heading.

    `root` is the directory the paths a notice names are relative to.
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = root
        self.documents: dict[str, Node] = {}
        self.ids: dict[str, dict[str, Node]] = {}  # source name -> id -> node
        self.paths: dict[str, str] = {}      # document source name -> path
        self.files: dict[Path, Node] = {}    # resolved path -> document
        self.sources: dict[str, Path] = {}   # source name -> resolved path

    def add(self, name: str, document: Node, path: str = "",
            file: Path | None = None) -> Node:
        """A parsed document under `name`, with `path` as the path a notice
        names and `file` as the path an include resolves against."""
        self.documents[name] = document
        self.paths[name] = path
        self.paths.setdefault(document.source, path)
        rel = path or document.source or name
        self.ids[document.source] = self._index(document, rel)
        if file is not None:
            self.files[file] = document
            self.sources[document.source] = file
        return document

    def load(self, path: Path, name: str | None = None) -> Node:
        """A document read from `path`. The path a notice names is relative to
        the registry's root."""
        path = path.resolve()
        rel = relative(path, self.root)
        return self.add(name or rel, parse(path.read_text(), name or rel),
                        rel, file=path)

    def open(self, path: Path) -> Node:
        """The document at `path`, read the first time an include names it."""
        path = path.resolve()
        document = self.files.get(path)
        return document if document is not None else self.load(path)

    def rel(self, document: Node) -> str:
        """The path a notice names for `document`."""
        return self.paths.get(document.source) or document.source

    def file(self, source: str) -> Path | None:
        """The file a document was read from, which its includes resolve
        against."""
        return self.sources.get(source)

    def _index(self, node: Node, rel: str) -> dict[str, Node]:
        """The sections under `node`, keyed by id: a heading's id is the slug
        of its text."""
        out: dict[str, Node] = {}
        for child in _walk(node):
            if child.kind != HEADING:
                continue
            ident = slug(child.text)
            if not ident:
                continue
            if ident in out:
                raise ControlledMarkdownError(child.source, child.line,
                                          "id-repeat",
                                          f"`{ident}` is already an id in {rel}")
            out[ident] = child
        return out


def _walk(node: Node):
    for child in node.children:
        yield child
        yield from _walk(child)


def relative(path: Path, root: Path | None = None) -> str:
    """A path as `root` sees it, or as given when it lies outside `root` or
    when no root is given."""
    if root is None:
        return str(path)
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path)


# ---------------------------------------------------------------- renderers

# The directives the renderer acts on. `comment` heads an editing note, which
# no reader outside the source sees.
COMMENT = "comment"
INCLUDE = "include"
INLINE = "inline"
CODE_OF = "code"
QUOTE_OF = "quote"
TEXT_OF = "text"
# The directives that read a value, beyond the two that name text to fill.
READERS = (CODE_OF, QUOTE_OF, TEXT_OF, "if", "unless")

VARIABLE_RE = re.compile(r"\{\{([A-Za-z0-9_.-]+)\}\}")
SPAN_RE = re.compile(r"(`[^`]*`)")


def gist(text: str) -> str:
    """A statement's first sentence, up to the first period that whitespace
    or the end follows."""
    return re.split(r"(?<=\.)\s+", " ".join(text.split()), maxsplit=1)[0]


# A section a render carries: its document's file and the section's id.
type SectionKey = tuple[Path, str]


@dataclass
class _State:
    reg: Registry
    values: dict
    given: bool = False     # whether the caller gave values at all
    # How many times so far the render has left lines out of what it
    # expands, by an `exclude` or by an abridgement. A section expanded with
    # the count unchanged is carried whole.
    left_out: int = 0
    # Each section the render carries whole, with each copy's heading in the
    # render: the heading written at the site of an `inline` that is the one
    # line under it, or None where the copy has no heading of its own.
    whole: dict[SectionKey, list[Node | None]] = field(default_factory=dict)


def _index_kind(document: Node) -> str | None:
    """The index a document's `index` attribute asks for, or None when the
    document renders in full."""
    name = (document.attr("index") or "").strip()
    return name if name in ("entries", "headings") else None


def _split_list(value: str | None) -> list[str]:
    """An attribute whose value is a comma-separated list."""
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _fill(text: str, node: Node, st: _State) -> str:
    """A node's text with each variable replaced by its value. A backtick span
    is literal, so its braces are text. A render with no values at all leaves
    the text as written."""
    if not st.given:
        return text

    def one(m):
        name = m.group(1)
        if name not in st.values:
            raise ControlledMarkdownError(node.source, node.line,
                                      "variable-missing",
                                      f"no value for `{name}`")
        value = str(st.values[name])
        if "\n" in value:
            raise ControlledMarkdownError(node.source, node.line,
                                      "variable-block",
                                      f"the value of `{name}` holds a line "
                                      f"break, which fits a `code` or a "
                                      f"`quote` directive only")
        return value
    return "".join(part if part.startswith("`") else VARIABLE_RE.sub(one, part)
                   for part in SPAN_RE.split(text))


def _expand(nodes: list[Node], st: _State, seen: tuple[str, ...],
            rel: str, drop: tuple[str, ...],
            abridged: set[Path] | str | None = None,
            site: Node | None = None) -> list[Node]:
    """A child list with its includes put in place, its directives applied,
    and its variables filled. `rel` is the path of the document the nodes come
    from. `drop` names the attributes an enclosing `include` excludes, and
    `abridged` the documents it renders as their `index` says. Both reach the
    documents this one includes. `site` is the rendered heading the nodes
    stand under where they are one `inline` directive (`_sole_inline`)."""
    out: list[Node] = []
    for node in nodes:
        if node.kind == ATTRIBUTE:
            out.append(node)
            continue
        if node.has(COMMENT):
            continue
        if any(node.has(name) for name in drop):
            st.left_out += 1
            continue
        if node.has(INCLUDE):
            out.extend(_include(node, st, seen, drop, abridged))
            continue
        if node.has(INLINE):
            out.extend(_inline(node, st, seen, drop, abridged, site))
            continue
        if node.has("if") and not _bound(node, "if", st):
            continue
        if node.has("unless") and _bound(node, "unless", st):
            continue
        if node.has(CODE_OF) or node.has(QUOTE_OF) or node.has(TEXT_OF):
            if st.given:
                out.append(_block(node, st))
            continue
        copy = Node(node.kind, node.text, node.name, node.value, node.depth,
                    node.line, node.source, star=node.star,
                    number=node.number)
        if copy.text and node.kind != CODE:
            copy.text = _rooted(_fill(copy.text, node, st), node, st)
        left_out = st.left_out
        copy.children = _expand(
            node.children, st, seen, rel, drop, abridged,
            copy if node.kind == HEADING and _sole_inline(node) else None)
        if node.kind == HEADING and st.left_out == left_out:
            _carry(node.source, slug(node.text), copy, st)
        out.append(copy)
    return out


def _sole_inline(heading: Node) -> bool:
    """Whether the lines a render carries under a heading are one `inline`
    directive, which makes the heading the inlined section's heading."""
    lines = [c for c in heading.children
             if c.kind != ATTRIBUTE and not c.has(COMMENT)]
    return len(lines) == 1 and lines[0].has(INLINE)


def _carry(source: str, ident: str, heading: Node | None, st: _State) -> None:
    """Note that the render carries the section `ident` of the document read
    as `source` whole, under `heading`. No link names a document read from no
    file, so nothing is noted for one."""
    file = st.reg.file(source)
    if file is None or not ident:
        return
    st.whole.setdefault((file, ident), []).append(heading)


def _names(nodes: list[Node], st: _State, seen: tuple[str, ...],
           rel: str) -> set[str]:
    """The names the nodes read, the lines they inline and include among
    them. Both branches of an `if` count, since either may render."""
    out: set[str] = set()
    for node in nodes:
        if node.kind == ATTRIBUTE or node.has(COMMENT):
            continue
        if node.has(INCLUDE) or node.has(INLINE):
            out |= _reached(node, st, seen)
            continue
        for name in READERS:
            if node.has(name):
                key = (node.attr(name) or "").strip()
                if key:
                    out.add(key)
        if node.text and node.kind != CODE:
            out |= _text_names(node.text)
        out |= _names(node.children, st, seen, rel)
    return out


def _text_names(text: str) -> set[str]:
    """The variables a node's text holds, the backtick spans left out."""
    return {name for part in SPAN_RE.split(text) if not part.startswith("`")
            for name in VARIABLE_RE.findall(part)}


def _reached(node: Node, st: _State, seen: tuple[str, ...]) -> set[str]:
    """The names the document or the section a directive reaches reads."""
    if node.has(INCLUDE):
        where = (node.attr(INCLUDE) or "").strip()
        document = _document_at(node, where, st)
        if document.source in seen:
            return set()
        return _names(document.children, st, seen + (document.source,),
                      st.reg.rel(document))
    value = (node.attr(INLINE) or "").strip()
    where, _, ident = value.partition("#")
    where, ident = where.strip(), ident.strip()
    document = _document_at(node, where, st) if where else _own_document(node, st)
    key = f"{document.source}#{ident}"
    target = st.reg.ids.get(document.source, {}).get(ident)
    if target is None or key in seen:
        return set()
    return _names(target.children, st, seen + (key,), st.reg.rel(document))


def _value_of(node: Node, name: str, st: _State) -> str:
    """The value a `code`, a `quote`, or a `text` directive names."""
    key = (node.attr(name) or "").strip()
    if key not in st.values:
        raise ControlledMarkdownError(node.source, node.line, "variable-missing",
                                  f"no value for `{key}`")
    return str(st.values[key])


def _fence(text: str) -> str:
    """A backtick fence the text cannot close: longer than its longest run."""
    runs = [len(run) for run in re.findall(r"`+", text)]
    return "`" * max(3, max(runs, default=0) + 1)


def _block(node: Node, st: _State) -> Node:
    """The block a `code`, a `quote`, or a `text` directive renders. A `text`
    block carries the value as it stands, so a render marks it up no
    further."""
    if node.has(TEXT_OF):
        return Node(CODE, text=_value_of(node, TEXT_OF, st),
                    source=node.source, line=node.line)
    if node.has(CODE_OF):
        text = _value_of(node, CODE_OF, st)
        fence = _fence(text)
        info = (node.attr("language") or "").strip()
        return Node(CODE, text=f"{fence}{info}\n{text}\n{fence}",
                    source=node.source, line=node.line)
    return Node(QUOTE, text=_value_of(node, QUOTE_OF, st),
                source=node.source, line=node.line)


def _rooted(text: str, node: Node, st: _State) -> str:
    """A link's target as the repo root sees it. A target that opens with `./`
    or `../` is relative to the document it stands in, so the render rewrites
    it; every other target already stands from the root and is left alone."""
    base = st.reg.file(node.source)
    if base is None:
        return text

    def one(m):
        path = m.group(2).partition("#")[0]
        if (not path or SCHEME_RE.match(m.group(2))
                or not path.startswith(("./", "../"))):
            return m.group(0)
        whole = (base.parent / path).resolve()
        rooted = relative(whole, st.reg.root)
        return f"[{m.group(1)}]({rooted}{m.group(2)[len(path):]})"

    return "".join(part if part.startswith("`") else LINK_RE.sub(one, part)
                   for part in SPAN_RE.split(text))


def _bound(node: Node, name: str, st: _State) -> bool:
    """Whether the value an `if` or `unless` directive names holds anything."""
    key = (node.attr(name) or "").strip()
    return bool(st.values.get(key))


def _include(node: Node, st: _State, seen: tuple[str, ...],
             drop: tuple[str, ...],
             abridged: set[Path] | str | None = None) -> list[Node]:
    """A whole document, in place of the `include` directive that names it.

    The path is relative to the file that carries the directive. `exclude`
    names the attributes to drop throughout, and `abridged` picks the
    documents that render as their `index` says.
    """
    where = (node.attr(INCLUDE) or "").strip()
    if not where or "#" in where:
        raise ControlledMarkdownError(node.source, node.line, "include-missing",
                                  f"`{where}` is not a path; a section is "
                                  f"reached with `inline`")
    document = _document_at(node, where, st)
    if document.source in seen:
        raise ControlledMarkdownError(node.source, node.line, "include-cycle",
                                  f"`{where}` includes itself")
    seen = seen + (document.source,)
    drop = drop + tuple(_split_list(node.attr("exclude")))
    if node.has("abridged"):
        abridged = _abridged(node, st)
    return _document_nodes(document, st, seen, drop, abridged)


def _inline(node: Node, st: _State, seen: tuple[str, ...],
            drop: tuple[str, ...],
            abridged: set[Path] | str | None = None,
            site: Node | None = None) -> list[Node]:
    """A section's body, in place of the `inline` directive that names it.

    `#<id>` names a section of the directive's own document and
    `<path>#<id>` one of the document at that path. The section's heading
    stays behind: a heading the lines need is written at the site, and
    `site` is that heading as rendered, where the directive is the one line
    under it.
    """
    value = (node.attr(INLINE) or "").strip()
    where, hashed, ident = value.partition("#")
    where, ident = where.strip(), ident.strip()
    if not hashed or not ident:
        raise ControlledMarkdownError(node.source, node.line, "inline-missing",
                                  f"`{value}` names no section; a whole "
                                  f"document is reached with `include`")
    document = (_document_at(node, where, st) if where
                else _own_document(node, st))
    key = f"{document.source}#{ident}"
    if key in seen:
        raise ControlledMarkdownError(node.source, node.line, "inline-cycle",
                                  f"`{value}` inlines itself")
    target = st.reg.ids.get(document.source, {}).get(ident)
    if target is None:
        raise ControlledMarkdownError(node.source, node.line, "inline-missing",
                                  f"no section in {st.reg.rel(document)} "
                                  f"carries the id `{ident}`")
    left_out = st.left_out
    out = _expand(target.children, st, seen + (key,),
                  st.reg.rel(document), drop, abridged)
    if st.left_out == left_out:
        _carry(document.source, ident, site, st)
    return out


def _abridged(node: Node, st: _State) -> set[Path] | str | None:
    """What an `abridged` attribute names: `all`, or the resolved paths it
    lists."""
    value = (node.attr("abridged") or "").strip()
    if value == "all":
        return "all"
    base = st.reg.file(node.source)
    root = base.parent if base is not None else Path()
    return {(root / part).resolve() for part in _split_list(value)}


def _own_document(node: Node, st: _State) -> Node:
    """The document a directive sits in."""
    document = st.reg.documents.get(node.source)
    if document is None:
        raise ControlledMarkdownError(node.source, node.line, "inline-missing",
                                  f"`{node.source}` is not in the registry")
    return document


def _document_at(node: Node, where: str, st: _State) -> Node:
    """The document at `where`, relative to the file the directive sits in."""
    base = st.reg.file(node.source)
    path = (base.parent / where) if base is not None else Path(where)
    try:
        return st.reg.open(path)
    except OSError:
        raise ControlledMarkdownError(node.source, node.line, "include-missing",
                                  f"no document at `{where}`") from None


def _document_nodes(document: Node, st: _State, seen: tuple[str, ...],
                    drop: tuple[str, ...],
                    abridged: set[Path] | str | None) -> list[Node]:
    """A whole document as nodes, abridged to the index its `index` attribute
    names when the including directive asks for that."""
    kind = _index_kind(document)
    if kind is not None and _is_abridged(document, st, abridged):
        st.left_out += 1
        return _index_nodes(document, st, seen, kind, drop, abridged)
    return _expand(document.children, st, seen, st.reg.rel(document), drop,
                   abridged)


def _is_abridged(document: Node, st: _State,
                 abridged: set[Path] | str | None) -> bool:
    if isinstance(abridged, str):
        return abridged == "all"
    if not abridged:
        return False
    return st.reg.file(document.source) in abridged


def _top(document: Node) -> Node:
    heads = [c for c in document.children if c.kind == HEADING]
    return heads[0] if heads else document


def _kept(node: Node) -> bool:
    """Whether a heading reaches an index."""
    return not node.has(COMMENT)


def _heading_lines(node: Node) -> list[Node]:
    """One heading per heading under `node`, with nothing under it but the
    headings it holds. A heading stays a heading, so a reader names the
    section the same way a render of the whole document lets them."""
    out: list[Node] = []
    for child in node.children:
        if child.kind != HEADING or not _kept(child):
            continue
        line = Node(HEADING, text=child.text, depth=child.depth,
                    source=child.source, line=child.line)
        line.children = _heading_lines(child)
        out.append(line)
    return out


def _entry_lines(top: Node) -> list[Node]:
    """One node per section under `top`: the section's title and the first
    sentence of its first statement."""
    out: list[Node] = []
    for head in top.children:
        if head.kind != HEADING or not _kept(head):
            continue
        opening = ""
        for child in head.children:
            if child.kind == CONTENT and child.text and _kept(child):
                opening = gist(child.text)
                break
        text = f"**{head.text}** — {opening}" if opening else f"**{head.text}**"
        out.append(Node(CONTENT, text=text, source=head.source, line=head.line))
    return out


def _index_nodes(document: Node, st: _State, seen: tuple[str, ...],
                 kind: str, drop: tuple[str, ...] = (),
                 abridged: set[Path] | str | None = None) -> list[Node]:
    """A document as an index: its title heading, the lines above its first
    section, a line naming the command that prints a section in full, and one
    line per section or per entry."""
    rel = st.reg.rel(document)
    top = _top(document)
    lead: list[Node] = []
    for child in top.children:
        if child.kind == HEADING:
            break
        lead.append(child)
    body = _expand(lead, st, seen, rel, drop, abridged)
    chapter = Path(document.source).stem if top is document else top.text
    if kind == "entries":
        note = ("Each line below is an entry's title and its first sentence, "
                "and `uv run python scripts/context.py section "
                f"'{chapter}#<title>'` prints the whole entry.")
    else:
        note = ("Only this chapter's headings are shown below, "
                "and `uv run python scripts/context.py section "
                f"'{chapter}#<heading>'` prints a section.")
    body.append(Node(CONTENT, text=note, source=top.source, line=top.line))
    body += _entry_lines(top) if kind == "entries" else _heading_lines(top)
    if top is document:
        return body
    title = Node(HEADING, text=top.text, depth=top.depth, source=top.source,
                 line=top.line)
    title.children = body
    return [title]


def _emit(nodes: list[Node], out: list[str], pad: str, hdepth: int,
          in_list: bool, shown: list[Node] | None = None) -> None:
    """A child list as Markdown lines. A directive puts its children in its
    own place, in the list its own line stood in. A heading takes its depth
    from where it lands, so an included document's headings sit under the
    including point. `shown` takes each node written as a heading."""
    for node in nodes:
        if node.kind == ATTRIBUTE:
            continue
        if node.kind == HEADING and not in_list:
            if out and out[-1] != "":
                out.append("")
            head = "#" * (hdepth + 1)
            out.append(f"{head} {node.text}" if node.text else head)
            out.append("")
            if shown is not None:
                shown.append(node)
            _emit(node.children, out, "", hdepth + 1, False, shown)
            continue
        if node.kind in (QUOTE, TABLE, CODE):
            if out and out[-1] != "":
                out.append("")
            lead = "> " if node.kind == QUOTE else ""
            for line in node.text.split("\n"):
                out.append(f"{pad}{lead}{line}".rstrip())
            out.append("")
            continue
        if node.anonymous():
            _emit(node.children, out, pad, hdepth, in_list, shown)
            continue
        if node.number:
            mark = f"{node.number}. "
            out.append(f"{pad}{mark}{escape(node.text)}".rstrip())
            _emit(node.children, out, pad + " " * INDENT, hdepth, True, shown)
            continue
        out.append(f"{pad}- {escape(node.text)}".rstrip())
        _emit(node.children, out, pad + " " * INDENT, hdepth, True, shown)


def _tidy(out: list[str]) -> str:
    text = "\n".join(out)
    text = re.sub(r"\n{3,}", "\n\n", text).strip("\n")
    return text + "\n"


# A line of ordinary Markdown that is an ATX heading, with its text, its
# indent taken off. A fence or a heading stands at an indent of three spaces
# at most.
MD_HEADING_RE = re.compile(r"^#{1,6}(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
MD_INDENT = 3


def markdown_headings(text: str) -> list[str]:
    """The text of each ATX heading in ordinary Markdown, the lines of its
    fenced code blocks left out."""
    out: list[str] = []
    fence = ""
    for line in text.split("\n"):
        lead = len(line) - len(line.lstrip(" "))
        if lead > MD_INDENT:
            continue
        body = line[lead:]
        if fence:
            if _closes(body, fence):
                fence = ""
        elif (m := FENCE_RE.match(body)) is not None:
            fence = m.group(1)
        elif (h := MD_HEADING_RE.match(body)) is not None:
            out.append(h.group(1) or "")
    return out


def _lay_out(nodes: list[Node], st: _State, after: str = "") -> str:
    """The nodes as Markdown, each link to a section they carry whole pointed
    at that section's heading (`_anchored`). `after` is the Markdown a caller
    sets after this text, whose headings take anchors too."""
    shown: list[Node] = []
    _emit(nodes, [], "", 0, False, shown)
    anchors: dict[str, int] = {}
    for text in (*(h.text for h in shown), *markdown_headings(after)):
        anchors[slug(text)] = anchors.get(slug(text), 0) + 1
    shown_ids = {id(h) for h in shown}
    for node in _walk_all(nodes):
        if node.text and node.kind not in (CODE, ATTRIBUTE):
            node.text = _anchored(node, st, shown_ids, anchors)
    out: list[str] = []
    _emit(nodes, out, "", 0, False)
    return _tidy(out)


def _walk_all(nodes: list[Node]) -> Iterator[Node]:
    """Every node of a child list, at every depth."""
    for node in nodes:
        yield node
        yield from _walk(node)


def _anchored(node: Node, st: _State, shown: set[int],
              anchors: dict[str, int]) -> str:
    """A node's text with each link to a section the render carries whole
    pointing at that section's heading in the render, as `#<anchor>`. A link
    stays as it is where the render gives its section no one heading of its
    own, written as a heading whose anchor no other heading of the render
    repeats. `shown` holds the headings the render writes as headings, by
    `id`, and `anchors` counts the headings of each anchor."""
    base = st.reg.file(node.source)

    def one(m: re.Match[str]) -> str:
        target = m.group(2)
        path, _, ident = target.partition("#")
        if SCHEME_RE.match(target) or not ident:
            return m.group(0)
        if base is None and path.startswith(("./", "../")):
            raise ControlledMarkdownError(
                node.source, node.line, "link-anchor",
                f"`{target}` is relative to a document read from no file")
        file = target_of(path, base or Path(node.source), st.reg.root)
        copies = st.whole.get((file, ident))
        if copies is None:
            return m.group(0)
        heading = copies[0] if len(copies) == 1 else None
        if (heading is None or id(heading) not in shown
                or anchors.get(slug(heading.text)) != 1):
            return m.group(0)
        return f"[{m.group(1)}](#{slug(heading.text)})"

    return "".join(part if part.startswith("`") else LINK_RE.sub(one, part)
                   for part in SPAN_RE.split(node.text))


def _state(reg: Registry | None, values: dict | None) -> _State:
    return _State(reg or Registry(), dict(values or {}), values is not None)


def variables(document: Node, reg: Registry | None = None) -> set[str]:
    """The names a document reads: every name its own lines and the lines it
    inlines and includes use, across a variable, a `code`, a `quote`, an `if`,
    and an `unless`. It is the document's interface, inferred."""
    st = _state(reg, None)
    return _names(document.children, st, (), st.reg.rel(document))


def _require(document: Node, st: _State) -> None:
    """The names a caller gives match the names the document reads. A render
    with no values at all skips the check and fills nothing."""
    if not st.given:
        return
    used = _names(document.children, st, (), st.reg.rel(document))
    # A document node stands over every line and carries no line of its own,
    # so the report names the document's first line.
    line = document.line or 1
    missing = sorted(used - set(st.values))
    if missing:
        raise ControlledMarkdownError(document.source, line,
                                  "variable-missing",
                                  f"no value for {_listed(missing)}")
    extra = sorted(set(st.values) - used)
    if extra:
        raise ControlledMarkdownError(document.source, line,
                                  "variable-unused",
                                  f"nothing reads {_listed(extra)}")


def _listed(names: list[str]) -> str:
    return ", ".join(f"`{name}`" for name in names)


def full(document: Node, reg: Registry | None = None,
         values: dict | None = None, after: str = "") -> str:
    """A document as ordinary Markdown: headings as headings, statements as
    nested lists, quotes as blockquotes, code nodes as fenced blocks.
    `after` is the Markdown a caller sets after it (`_lay_out`)."""
    st = _state(reg, values)
    _require(document, st)
    return _lay_out(_expand(document.children, st, (), st.reg.rel(document), ()),
                    st, after)


def headings(document: Node, reg: Registry | None = None,
             values: dict | None = None) -> str:
    """A document as its title, the lines above its first section, and one
    line per heading."""
    st = _state(reg, values)
    _require(document, st)
    return _lay_out(_index_nodes(document, st, (), "headings"), st)


def entries(document: Node, reg: Registry | None = None,
            values: dict | None = None) -> str:
    """A document as its title, the lines above its first section, and one
    line per entry: the entry's title and the first sentence of its first
    statement."""
    st = _state(reg, values)
    _require(document, st)
    return _lay_out(_index_nodes(document, st, (), "entries"), st)


def role(document: Node, reg: Registry | None = None,
         values: dict | None = None) -> tuple[str, str]:
    """A role document as its agent's name and its text."""
    return document.attr("agent") or "handbook", render(document, reg, values)


def brief(document: Node, reg: Registry | None = None,
          values: dict | None = None) -> str:
    """A document with its includes put in place."""
    return render(document, reg, values)


def render(document: Node, reg: Registry | None = None,
           values: dict | None = None, after: str = "") -> str:
    """A document in full. An `index` attribute picks an index rendering only
    where an `include` asks for it. `after` is the Markdown a caller sets
    after it (`_lay_out`)."""
    return full(document, reg, values, after)



# ---------------------------------------------------------------- round trip


def round_trips(document: Node) -> bool:
    """Whether the formatter's output parses back to the same tree."""
    return parse(write(document), document.source).shape() == document.shape()
