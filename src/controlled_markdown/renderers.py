"""The renderers of Controlled Markdown: each projects a document's tree down
to ordinary Markdown for an agent to read, with its directives put in place
and its variables filled."""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from controlled_markdown import (
    ATTRIBUTE,
    CODE,
    CODE_OF,
    COMMENT,
    CONTENT,
    DOCUMENT,
    FENCE_RE,
    HEADING,
    INCLUDE,
    INDENT,
    INLINE,
    LINK_RE,
    QUOTE,
    QUOTE_OF,
    READERS,
    SCHEME_RE,
    SPAN_RE,
    TABLE,
    TEXT_OF,
    ControlledMarkdownError,
    Node,
    Registry,
    Reference,
    RelativeToNoFile,
    Rule,
    _closes,
    _walk,
    escape,
    links,
    reference,
    relative,
    relative_link,
    resolve_reference,
    slug,
    target_of,
)

VARIABLE_RE = re.compile(r"\{\{([A-Za-z0-9_.-]+)\}\}")


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
                                      Rule.VARIABLE_MISSING,
                                      f"no value for `{name}`")
        value = str(st.values[name])
        if "\n" in value:
            raise ControlledMarkdownError(node.source, node.line,
                                      Rule.VARIABLE_BLOCK,
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
    ref = reference(node.attr(INLINE) or "")
    document = _referenced_document(node, ref, st)
    ident = ref.ident or ""
    key = f"{document.source}#{ident}"
    target = st.reg.ids.get(document.source, {}).get(ident)
    if target is None or key in seen:
        return set()
    return _names(target.children, st, seen + (key,), st.reg.rel(document))


def _value_of(node: Node, name: str, st: _State) -> str:
    """The value a `code`, a `quote`, or a `text` directive names."""
    key = (node.attr(name) or "").strip()
    if key not in st.values:
        raise ControlledMarkdownError(node.source, node.line, Rule.VARIABLE_MISSING,
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
        path = reference(m.group(2)).path
        if (not path or SCHEME_RE.match(m.group(2))
                or not relative_link(path)):
            return m.group(0)
        whole = resolve_reference(path, base)
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
        raise ControlledMarkdownError(node.source, node.line, Rule.INCLUDE_MISSING,
                                  f"`{where}` is not a path; a section is "
                                  f"reached with `inline`")
    document = _document_at(node, where, st)
    if document.source in seen:
        raise ControlledMarkdownError(node.source, node.line, Rule.INCLUDE_CYCLE,
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
    ref = reference(value)
    ident = ref.ident
    if not ident:
        raise ControlledMarkdownError(node.source, node.line, Rule.INLINE_MISSING,
                                  f"`{value}` names no section; a whole "
                                  f"document is reached with `include`")
    document = _referenced_document(node, ref, st)
    key = f"{document.source}#{ident}"
    if key in seen:
        raise ControlledMarkdownError(node.source, node.line, Rule.INLINE_CYCLE,
                                  f"`{value}` inlines itself")
    target = st.reg.ids.get(document.source, {}).get(ident)
    if target is None:
        raise ControlledMarkdownError(node.source, node.line, Rule.INLINE_MISSING,
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
    return {resolve_reference(part, base) if base is not None
            else Path(part).resolve() for part in _split_list(value)}


def _referenced_document(node: Node, ref: Reference, st: _State) -> Node:
    return (_document_at(node, ref.path, st) if ref.path
            else _own_document(node, st))


def _own_document(node: Node, st: _State) -> Node:
    """The document a directive sits in."""
    document = st.reg.documents.get(node.source)
    if document is None:
        raise ControlledMarkdownError(node.source, node.line, Rule.INLINE_MISSING,
                                  f"`{node.source}` is not in the registry")
    return document


def _document_at(node: Node, where: str, st: _State) -> Node:
    """The document at `where`, relative to the file the directive sits in.
    An empty `where` names no document."""
    missing = ControlledMarkdownError(node.source, node.line, Rule.INCLUDE_MISSING,
                                  f"no document at `{where}`")
    if not where:
        raise missing
    base = st.reg.file(node.source)
    path = resolve_reference(where, base) if base is not None else Path(where)
    try:
        return st.reg.open(path)
    except OSError:
        raise missing from None


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
# indent taken off. A heading stands at an indent of three spaces at most.
MD_HEADING_RE = re.compile(r"^#{1,6}(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
MD_INDENT = 3


def outside_fences(text: str) -> Iterator[str]:
    """Each line of ordinary Markdown outside its fenced code blocks, the
    fence lines left out. A fence counts at any indent, since a render nests
    a code block under a list item at that item's indent."""
    fence = ""
    for line in text.split("\n"):
        body = line.strip()
        if fence:
            if _closes(body, fence):
                fence = ""
        elif (m := FENCE_RE.match(body)) is not None:
            fence = m.group(1)
        else:
            yield line


def markdown_headings(text: str) -> list[str]:
    """The text of each ATX heading in ordinary Markdown, the lines of its
    fenced code blocks left out (`outside_fences`)."""
    out: list[str] = []
    for line in outside_fences(text):
        lead = len(line) - len(line.lstrip(" "))
        if lead > MD_INDENT:
            continue
        if (h := MD_HEADING_RE.match(line[lead:])) is not None:
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
    def one(m: re.Match[str]) -> str:
        target = m.group(2)
        ref = reference(target)
        path, ident = ref.path, ref.ident
        if SCHEME_RE.match(target) or not ident:
            return m.group(0)
        file = _link_file(node, path, st)
        copies = None if file is None else st.whole.get((file, ident))
        if copies is None:
            return m.group(0)
        heading = copies[0] if len(copies) == 1 else None
        if (heading is None or id(heading) not in shown
                or anchors.get(slug(heading.text)) != 1):
            return m.group(0)
        return f"[{m.group(1)}](#{slug(heading.text)})"

    return "".join(part if part.startswith("`") else LINK_RE.sub(one, part)
                   for part in SPAN_RE.split(node.text))


def _link_file(node: Node, path: str, st: _State) -> Path | None:
    """The file a link with `path` in the text of `node` names
    (`target_of`); None for a link to a section of its own document, in a
    document read from no file, which names no file (`_carry`). A link
    relative to its document, in a document read from no file, is a
    fault."""
    base = st.reg.file(node.source)
    if base is None and not path:
        return None
    try:
        return target_of(path, base, st.reg.root)
    except RelativeToNoFile:
        raise ControlledMarkdownError(
            node.source, node.line, Rule.LINK_ANCHOR,
            f"`{path}` is relative to a document read from no file") from None


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
                                  Rule.VARIABLE_MISSING,
                                  f"no value for {_listed(missing)}")
    extra = sorted(set(st.values) - used)
    if extra:
        raise ControlledMarkdownError(document.source, line,
                                  Rule.VARIABLE_UNUSED,
                                  f"nothing reads {_listed(extra)}")


def _listed(names: list[str]) -> str:
    return ", ".join(f"`{name}`" for name in names)


def full(document: Node, reg: Registry | None = None,
         values: dict | None = None, after: str = "") -> str:
    """A document as ordinary Markdown: headings as headings, statements as
    nested lists, quotes as blockquotes, code nodes as fenced blocks.
    `after` is the Markdown a caller sets after it (`_lay_out`)."""
    st = _state(reg, values)
    return _lay_out(_expanded(document, st), st, after)


def _expanded(document: Node, st: _State) -> list[Node]:
    _require(document, st)
    return _expand(document.children, st, (), st.reg.rel(document), ())


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


def render_linked(document: Node, reg: Registry | None = None
                  ) -> tuple[str, list[tuple[Path, str]]]:
    """A document as `render` gives it with no values, and the target of
    each link it holds, the links its includes and inlines bring among
    them, in the order it holds them: the file the link names, and the id
    of a section, empty where the link names the whole file. The targets
    are those of the links that name a file (`_link_file`)."""
    st = _state(reg, None)
    nodes = _expanded(document, st)
    holder = Node(DOCUMENT, source=document.source, children=nodes)
    found = [(file, ident) for node, _text, path, ident in links(holder, own=True)
             if (file := _link_file(node, path, st)) is not None]
    return _lay_out(nodes, st), found


def section_document(document: Node, section: Node) -> Node:
    """A document node that holds `section`, a section of `document`, on its
    own, so that a render gives that section alone."""
    return Node(DOCUMENT, source=document.source, children=[section])
