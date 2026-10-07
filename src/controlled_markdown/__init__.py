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

The package holds Controlled Markdown as a whole: this module holds the
parser, the formatter and the registry, `nodes` the node tree, `prose` the
checks of prose in code, `document_set` the checks of a document set with
the links a node's text holds, `renderers` the renderers, and `round_trip`
the formatter's round trip. This module gives every name of the package.
`nodes` imports nothing from the package; each other module imports from
this module, which gives their names once the rest of it is defined.
"""

from __future__ import annotations

import re
from pathlib import Path

from controlled_markdown.nodes import (
    ControlledMarkdownError as ControlledMarkdownError,
    slug as slug,
    INDENT as INDENT,
    DOCUMENT as DOCUMENT,
    CONTENT as CONTENT,
    ATTRIBUTE as ATTRIBUTE,
    QUOTE as QUOTE,
    TABLE as TABLE,
    CODE as CODE,
    HEADING as HEADING,
    Node as Node,
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


# ---------------------------------------------------------------- directives

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


from controlled_markdown.document_set import (  # noqa: E402
    reached as reached,
    carried as carried,
    check_closure as check_closure,
    PARTIALS as PARTIALS,
    partials as partials,
    inline_sites as inline_sites,
    PARTIAL_SITES as PARTIAL_SITES,
    check_partial_sites as check_partial_sites,
    check_blocks as check_blocks,
    LINK_RE as LINK_RE,
    SPAN_RE as SPAN_RE,
    EXTERNAL_RE as EXTERNAL_RE,
    SCHEME_RE as SCHEME_RE,
    links as links,
    relative_link as relative_link,
    relative_to_no_file as relative_to_no_file,
    target_of as target_of,
    check_links as check_links,
)
from controlled_markdown.prose import (  # noqa: E402
    mctx as mctx,
    dedent as dedent,
    PY_HOLE_RE as PY_HOLE_RE,
    JS_HOLE_RE as JS_HOLE_RE,
    HOLE_NAME_RE as HOLE_NAME_RE,
    FILLED as FILLED,
    Fragment as Fragment,
    JS_TAG_RE as JS_TAG_RE,
    PY_WHOLE_RE as PY_WHOLE_RE,
    JS_WHOLE_RE as JS_WHOLE_RE,
    MARKER_RE as MARKER_RE,
    check_fragment as check_fragment,
    fragments as fragments,
    check_file_fragments as check_file_fragments,
    DOC_PATH_RE as DOC_PATH_RE,
    JS_STRING_RE as JS_STRING_RE,
    check_paths as check_paths,
    LINE_MARKER_RE as LINE_MARKER_RE,
    Quote as Quote,
    handbook_sections as handbook_sections,
    check_quotes as check_quotes,
    check_quote_rule as check_quote_rule,
    DL_DOC_RE as DL_DOC_RE,
    dl_fragments as dl_fragments,
    check_dl_comments as check_dl_comments,
)
from controlled_markdown.renderers import brief as brief  # noqa: E402
from controlled_markdown.renderers import entries as entries  # noqa: E402
from controlled_markdown.renderers import full as full  # noqa: E402
from controlled_markdown.renderers import gist as gist  # noqa: E402
from controlled_markdown.renderers import headings as headings  # noqa: E402
from controlled_markdown.renderers import markdown_headings as markdown_headings  # noqa: E402
from controlled_markdown.renderers import outside_fences as outside_fences  # noqa: E402
from controlled_markdown.renderers import render as render  # noqa: E402
from controlled_markdown.renderers import render_linked as render_linked  # noqa: E402
from controlled_markdown.renderers import variables as variables  # noqa: E402
from controlled_markdown.round_trip import round_trips as round_trips  # noqa: E402
