"""The lib as its readers read it: its files in include order, parsed into
items and comments, and each file rendered as documentation, its `//!` and
`///` comments as prose and the declarations they document in code blocks,
or as an index, one line per top-level public component. An entry
document's `lib` attribute gives the form the lib renders in after it
(`LibForm`)."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

import controlled_markdown as nm
from controlled_markdown import mctx
from engine import checkout
from engine.memo import kept_recent
from souffle import printer
from souffle.layout import written_lines
from handbook import paths
from handbook.attributes import attr_form
from handbook.generated import Rendering
from handbook.items import (
    Comp,
    Decl,
    Define,
    Include,
    Init,
    Item,
    Program,
    Rule,
    SubtypeForm,
    TypeDecl,
)
from handbook.items import parse as parse_file
from handbook.paths import document, repo_label

LIB_SRC = document(paths.lib_src())


def parse(text: str, base_dir: Path | None = None) -> Program:
    """One lib file's items and comments (`handbook.items.parse`), each
    `#include` in it resolved against `base_dir`, the programs directory
    as the contexts read it where none is given."""
    return parse_file(text, base_dir or document(checkout.programs()))


def lib_sources(root: Path | None = None) -> list[tuple[Path, str]]:
    """The lib's files in include order, each with its text: the root, the
    lib the runner reads as the contexts read it (`LIB_SRC`) when none is given, then the
    file of each `#include` in it, resolved against the root's
    directory."""
    root = LIB_SRC if root is None else root
    text = root.read_text()
    out = [(root, text)]
    for it in parse(text, root.parent).items:
        if isinstance(it, Include):
            path = root.parent / it.path
            out.append((path, path.read_text()))
    return out


# The comment kinds. A `//!` line documents its file; a `///` block
# documents the item under it; any other comment is for the maintainer.
FILE_DOC = "//!"
ITEM_DOC = "///"

# The items a `///` block may document.
DOCUMENTED = (Decl, Comp, Define, TypeDecl, Init)
type Documented = Decl | Comp | Define | TypeDecl | Init


def _prose(comment_lines: list[str], mark: str) -> str:
    """Comment lines as the markdown they hold: the mark and one space
    after it stripped from each."""
    return "\n".join(line.strip()[len(mark):].removeprefix(" ")
                     for line in comment_lines).strip("\n")


def _doc_blocks(program: Program, mark: str) -> dict[int, tuple[int, int]]:
    """The blocks of consecutive own-line `mark` comments, keyed by their
    last line: (first line, last line)."""
    doc_lines = sorted(c.line for c in program.comments
                       if c.own_line and c.text.startswith(mark)
                       and not c.text.startswith(mark + "/"))
    blocks: dict[int, tuple[int, int]] = {}
    start = None
    for ln in doc_lines:
        if start is None or (ln - 1) not in blocks:
            start = ln
        else:
            blocks.pop(ln - 1)
        blocks[ln] = (start, ln)
    return blocks


def _documented(items: list[Item]) -> list[Item]:
    """The items a `///` block may document, at every depth."""
    out: list[Item] = []
    for it in items:
        if isinstance(it, DOCUMENTED):
            out.append(it)
        if isinstance(it, Comp):
            out.extend(_documented(it.items))
    return out


def _name(it: Documented) -> str:
    return it.inst if isinstance(it, Init) else it.name


def _hidden(it: Documented) -> bool:
    """A `_`-prefixed item is private to the lib."""
    return _name(it).startswith("_")


def _comp_block(comp: Comp, lines: list[str], docs: dict[int, tuple[int, int]]) -> list[str]:
    """A comp as its interface: the header, each public inner declaration
    under its doc as a `//` comment, the facts under an input-marked one,
    and the closing brace."""
    out = [lines[comp.line - 1].rstrip()]
    facts: dict[str, list[int]] = {}
    for it in comp.items:
        if isinstance(it, Rule) and it.body is None:
            facts.setdefault(it.head.name, []).extend(range(it.line, it.end_line + 1))
    prev: tuple[bool, bool] | None = None   # (documented, input) of the last item
    for it in comp.items:
        if not isinstance(it, DOCUMENTED) or _hidden(it):
            continue
        block = docs.get(it.line - 1)
        is_input = isinstance(it, Decl) and it.input
        cur = (block is not None, is_input)
        if prev is not None and (cur[0] or prev[0] or cur[1] != prev[1]):
            out.append("")
        prev = cur
        if block is not None:
            for ln in range(block[0], block[1] + 1):
                line = lines[ln - 1]
                indent = line[:len(line) - len(line.lstrip())]
                out.append(indent + "//" + line.lstrip()[len(ITEM_DOC):])
        if isinstance(it, Comp):
            out.extend(_comp_block(it, lines, docs))
            continue
        end = it.end_line if isinstance(it, Decl) else it.line
        out += written_lines(lines, it.line, end)
        if isinstance(it, Decl) and is_input:
            out.extend(lines[ln - 1].rstrip() for ln in sorted(set(facts.get(it.name, []))))
    out += written_lines(lines, comp.end_line, comp.end_line)
    return out


def _runs(items: list[Item], docs: dict[int, tuple[int, int]]) -> list[list[Documented]]:
    """The top-level public items a `///` block may document, each in its
    run. Undocumented siblings on consecutive lines fold into the item over
    them: defines, or subtypes of one base."""
    items = [it for it in items if not isinstance(it, (Include, Rule))]
    out: list[list[Documented]] = []
    i = 0
    while i < len(items):
        it = items[i]
        if not isinstance(it, DOCUMENTED) or _hidden(it):
            i += 1
            continue
        run: list[Documented] = [it]
        j = i + 1
        while j < len(items):
            nxt = items[j]
            if not (isinstance(nxt, DOCUMENTED) and type(nxt) is type(it)
                    and nxt.line == run[-1].line + 1
                    and docs.get(nxt.line - 1) is None and not _hidden(nxt)
                    and (isinstance(it, Define)
                         or (isinstance(it, TypeDecl) and isinstance(nxt, TypeDecl)
                             and isinstance(it.form, SubtypeForm)
                             and nxt.form == it.form))):
                break
            run.append(nxt)
            j += 1
        out.append(run)
        i = j
    return out


def lib_entries(text: str) -> str:
    """One lib file as an index: its `//!` lines as prose, then one line per
    top-level public component, its name and the first sentence of its doc. A
    unit with no doc gives its name alone, and a relation with no doc its
    declaration. A run that folds in `lib_doc` gives its names on one line."""
    program = parse(text)
    lines = text.splitlines()
    docs = _doc_blocks(program, ITEM_DOC)
    file_docs = _doc_blocks(program, FILE_DOC)
    prose = [_prose(lines[start - 1:end], FILE_DOC)
             for _, (start, end) in sorted(file_docs.items())]
    out: list[str] = []
    for run in _runs(program.items, docs):
        names = ", ".join(f"**{_name(it)}**" for it in run)
        block = docs.get(run[0].line - 1)
        if block is None:
            it = run[0]
            if isinstance(it, Decl) and len(run) == 1:
                names = f"**{it.name}**" + printer.signature(
                    it.columns, it.qualifiers, it.choice_domain)
            out.append(f"- {names}")
            continue
        para = " ".join(_prose(lines[block[0] - 1:block[1]], ITEM_DOC).split("\n\n")[0].split())
        out.append(f"- {names} — {nm.gist(para)}")
    return "\n\n".join(p for p in (*prose, "\n".join(out)) if p) + "\n"


@kept_recent(16)
def lib_doc(text: str) -> str:
    """One lib file as markdown: its `//!` lines as prose, then each public
    item under its `///` prose in a code block. Rules, functors, and
    plain comments do not render. Undocumented defines on consecutive
    lines fold to one line of names, and undocumented subtypes of one base
    on consecutive lines to one line."""
    program = parse(text)
    lines = text.splitlines()
    docs = _doc_blocks(program, ITEM_DOC)
    file_docs = _doc_blocks(program, FILE_DOC)
    attached = {it.line - 1 for it in _documented(program.items)}

    parts: list[str] = []          # prose paragraphs and code blocks, in order
    code: list[str] | None = None  # the open code block

    def emit_prose(p: str) -> None:
        nonlocal code
        if code:
            parts.append(_code_block(code))
        code = None
        parts.append(p)

    def emit_code(block_lines: list[str]) -> None:
        nonlocal code
        if code is None:
            code = []
        elif block_lines:
            code.append("")
        code.extend(block_lines)

    for _, (start, end) in sorted(file_docs.items()):
        emit_prose(_prose(lines[start - 1:end], FILE_DOC))

    for run in _runs(program.items, docs):
        it = run[0]
        block = docs.get(it.line - 1)
        if block is not None:
            emit_prose(_prose(lines[block[0] - 1:block[1]], ITEM_DOC))
        emit_code(_run_code(run, lines, docs))
    # A block over no item renders where it stands.
    for end, (start, _) in sorted(docs.items()):
        if end not in attached:
            emit_prose(_prose(lines[start - 1:end], ITEM_DOC))
    emit_prose("")
    return "\n\n".join(p for p in parts if p) + "\n"


def _run_code(run: list[Documented], lines: list[str],
              docs: dict[int, tuple[int, int]]) -> list[str]:
    """The code lines a run of lib items renders as: consecutive defines
    folded to one line of names, consecutive subtypes of one base to one
    `.type … <:` line, a component as its block, any other item as its
    source lines."""
    it = run[0]
    if len(run) > 1 and isinstance(it, Define):
        return [" ".join(_name(d) for d in run)]
    if len(run) > 1 and isinstance(it, TypeDecl) \
            and isinstance(it.form, SubtypeForm):
        return [printer.subtypes(tuple(_name(t) for t in run), it.form.base)]
    if isinstance(it, Comp):
        return _comp_block(it, lines, docs)
    end = it.end_line if isinstance(it, Decl) else it.line
    return written_lines(lines, it.line, end)


def _code_block(code: list[str]) -> str:
    return "```\n" + "\n".join(code) + "\n```"


def interface_path(src: Path) -> Path:
    """The interface file beside a lib source: the `.md` of the same stem."""
    return src.with_suffix(".md")


def lib_component(src: Path, name: str) -> str:
    """One component's interface, as the interface file beside `src` holds
    it: the component's `///` prose, then its declarations in a code
    block."""
    text = src.read_text()
    program = parse(text)
    lines = text.splitlines()
    docs = _doc_blocks(program, ITEM_DOC)
    for run in _runs(program.items, docs):
        if not any(_name(it) == name for it in run):
            continue
        it = run[0]
        block = docs.get(it.line - 1)
        prose = _prose(lines[block[0] - 1:block[1]], ITEM_DOC) if block else ""
        code = _code_block(_run_code(run, lines, docs))
        return "\n\n".join(p for p in (f"# {name}", prose, code) if p) + "\n"
    raise SystemExit(f"no component `{name}` in `{repo_label(src)}`")


def interface_renderings(lib: Path = LIB_SRC) -> list[Rendering]:
    """The interface file beside each of the lib's sources, each under a
    line saying it's generated."""
    return [Rendering(interface_path(path), mctx(
        "<!-- Generated from {name} by scripts/context.py. -->").format(
            name=path.name) + "\n\n" + lib_doc(text))
        for path, text in lib_sources(lib)]


class LibForm(Enum):
    """How the lib renders after an entry document, as its `lib`
    attribute states."""

    INTERFACE = "interface"
    INDEX = "index"
    NONE = "none"


def lib_form(document: nm.Node) -> LibForm:
    return attr_form(document, "lib", LibForm, LibForm.INTERFACE)


def lib_part(lib: Path = LIB_SRC, kind: LibForm = LibForm.INTERFACE) -> str:
    """The lib's files, each under a heading stating its file: as each file's
    interface, or as an index pointing at the interface file beside each
    source. `none` leaves the lib out."""
    if kind is LibForm.NONE:
        return ""
    parts = []
    for path, text in lib_sources(lib):
        rel = Path("programs") / path.relative_to(lib.parent)
        if kind is LibForm.INDEX:
            parts.append(f"\n---\n\n## {rel} — index\n\n{lib_entries(text)}")
        else:
            parts.append(f"\n---\n\n## {rel}\n\n{lib_doc(text)}")
    return "".join(parts)
