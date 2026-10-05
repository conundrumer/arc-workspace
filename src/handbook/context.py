"""The reference context a solver session reads, projected down to what the
procedure uses.

The lib renders as documentation: each file's `//!` and `///` comments as
prose, and the declarations they document in code blocks, without the rule
bodies. That is `lib: interface`. Under `lib: index` each file gives one line
per top-level public component instead. Each file's interface is also written
beside it, as the `.md` of the same stem, and `section_text` prints one
component's interface from the source.

An agent document under `prompts/agents/` states what its agent reads, and
`write_agent` renders one per agent into `.claude/agents/`, front matter and
all. Read those documents for what each agent gets.
"""

from __future__ import annotations

import difflib
import json
import keyword
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum, StrEnum
from engine.memo import kept_recent
from pathlib import Path

import controlled_markdown as nm
from controlled_markdown import mctx
from engine import checkout
from engine.program import Primitive, Qualifier
from engine.memo import write_whole
from souffle.layout import written_lines
from handbook import paths
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
from handbook.paths import DOCUMENTS_ROOT, REPO_ROOT, document

# The handbook's own files. Nothing here reads them as a directory: the
# composition document lists each one, and the registry reads it from there.
DOCS_DIR = document(checkout.handbook())


def role_dir(root: Path = DOCUMENTS_ROOT) -> Path:
    """`prompts/roles/` under the documents root `root`."""
    return document(checkout.prompts(), root) / "roles"


ROLE_DIR = role_dir()
LIB_SRC = document(paths.lib_src())

# The agent documents, one per handbook agent: front matter holding the
# agent's definition, a `lib` attribute saying how the lib renders, and an
# `include` of the composition document. An agent runs a role under
# prompts/roles/ with the rendered document as its system prompt. The files
# under `.claude/agents/` are generated at each entry point and not tracked. A
# role's document states its agent in an `agent` attribute. A role with no such
# attribute runs as the handbook agent.
def agent_dir(root: Path = DOCUMENTS_ROOT) -> Path:
    """`prompts/agents/` under the documents root `root`."""
    return document(checkout.prompts(), root) / "agents"


AGENT_DIR = agent_dir()
# The session's own entry document: the handbook, and the passes it runs.
SESSION_DOC = document(checkout.prompts()) / "session.md"
# The codex session's entry document, composed the same way.
CODEX_DOC = document(checkout.prompts()) / "codex.md"
AGENT_OUT = checkout.agents()
"""Where the agent definitions are written."""


def agent_file(name: str) -> Path:
    """The definition file of the agent `name`."""
    return AGENT_OUT / f"{name}.md"


def repo_label(path: Path) -> str:
    """A path as the context prints it: from `DOCUMENTS_ROOT` where it
    stands under it, else from the checkout's root
    (`engine.checkout.shown`)."""
    under = checkout.shown(path, DOCUMENTS_ROOT)
    return str(checkout.shown(path) if under.is_absolute() else under)


def agent_doc(name: str, agents: Path = AGENT_DIR) -> Path:
    """The agent document of the agent `name` under `agents`."""
    return agents / f"{name}.md"


def role_file(name: str, roles: Path = ROLE_DIR) -> Path:
    """The role document of the role `name` under `roles`."""
    return roles / f"{name}.md"


HANDBOOK_AGENT = "handbook"
"""The agent a role with no `agent` attribute runs on."""
AGENT_PATH = agent_file(HANDBOOK_AGENT)
AGENT_NAMES = (HANDBOOK_AGENT, "handbook-expanded")
# The steps the analyze agent reads after it writes the concept: a document
# under `AGENT_DIR` with no front matter, rendered to its own file.
ANALYZE_NEXT = "analyze-next"
ANALYZE_NEXT_PATH = checkout.claude() / "analyze-next.md"


def parse(text: str, base_dir: Path | None = None) -> Program:
    """One lib file's items and comments (`handbook.items.parse`), each
    `#include` in it resolved against `base_dir`, the programs directory
    as the contexts read it where none is given."""
    return parse_file(text, base_dir or document(checkout.programs()))


APPENDIX = mctx("the system-prompt appendix")
"""What the console worker's first section is called."""


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
# The trailing directive on a `.decl` line that marks a relation the
# caller populates.
INPUT_MARK_RE = re.compile(r"//\s*@input\b")

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


def _is_input(decl: Decl, lines: list[str]) -> bool:
    return any(INPUT_MARK_RE.search(lines[ln - 1])
               for ln in range(decl.line, decl.end_line + 1))


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
        is_input = isinstance(it, Decl) and _is_input(it, lines)
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
                decl = " ".join(" ".join(lines[it.line - 1:it.end_line]).split())
                names = f"**{it.name}**" + decl.removeprefix(".decl " + it.name)
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
            parts.append("```\n" + "\n".join(code) + "\n```")
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
        return [f".type {', '.join(_name(t) for t in run)} <: {it.form.base}"]
    if isinstance(it, Comp):
        return _comp_block(it, lines, docs)
    end = it.end_line if isinstance(it, Decl) else it.line
    return written_lines(lines, it.line, end)


def interface_path(src: Path) -> Path:
    """The interface file beside a lib source: the `.md` of the same stem."""
    return src.with_suffix(".md")


class LibForm(Enum):
    """How the lib renders after an entry document, as its `lib`
    attribute states."""

    INTERFACE = "interface"
    INDEX = "index"
    NONE = "none"


def lib_form(document: nm.Node) -> LibForm:
    """The form an entry document's `lib` attribute states: `interface`
    where it states none, and an error where it states no form."""
    value = document.attr("lib")
    if value is None:
        return LibForm.INTERFACE
    try:
        return LibForm(value.strip())
    except ValueError:
        raise SystemExit(
            f"`lib: {value.strip()}` in {document.source} is no lib form; "
            "the forms are " + ", ".join(f.value for f in LibForm)) from None


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


def agent_document(name: str, agents: Path = AGENT_DIR) -> nm.Node:
    """One agent document, parsed."""
    return nm.Registry(DOCUMENTS_ROOT).load(agent_doc(name, agents))


def agent_meta(name: str, agents: Path = AGENT_DIR) -> dict[str, str]:
    """An agent's definition, as its document's front matter gives it."""
    out: dict[str, str] = {}
    for line in agent_document(name, agents).front.split("\n"):
        if ": " in line and not line.startswith("---"):
            key, value = line.split(": ", 1)
            out[key.strip()] = value.strip().strip('"')
    return out


def render(name: str = "handbook-expanded", lib: Path = LIB_SRC,
           agents: Path = AGENT_DIR) -> str:
    """The handbook an agent document composes: its body, with the doc each
    include names put in place, then the lib as its `lib` attribute says."""
    return entry_text(agent_doc(name, agents), lib)


def entry_text(doc: Path, lib: Path = LIB_SRC) -> str:
    """One entry document as its reader gets it: the document rendered, then
    the lib as the document's `lib` attribute says."""
    return _composed(doc, lib)[0]


def _composed(doc: Path, lib: Path) -> tuple[str, nm.Registry, LibForm]:
    """`entry_text` of `doc`, the registry that holds each document the
    render read, and the form the lib renders in after it."""
    registry = nm.Registry(DOCUMENTS_ROOT)
    document = registry.load(doc)
    form = lib_form(document)
    after = lib_part(lib, form)
    return nm.render(document, registry, after=after) + after, registry, form


TOOL_RE = re.compile(r"\b(scripts/[\w-]+\.py)\b|-m ([A-Za-z_]\w*)")
"""A script path, or the top-level module a `-m` option runs."""


def agent_sources(name: str, lib: Path = LIB_SRC,
                  agents: Path = AGENT_DIR) -> list[Path]:
    """The files an agent's prompt is composed from and the tools it names,
    each once, in order: its agent document and each document it includes
    or inlines, then the lib's files where its `lib` attribute is not
    `none`, then each script under `scripts/` and each package under `src/`
    that a `-m` option runs, which the rendered prompt names and the
    checkout holds. The modules those tools import are left out."""
    text, registry, form = _composed(agent_doc(name, agents), lib)
    lib_files = ([] if form is LibForm.NONE
                 else [path for path, _ in lib_sources(lib)])
    tools: list[Path] = []
    for m in TOOL_RE.finditer(text):
        path = (REPO_ROOT / m.group(1) if m.group(1)
                else REPO_ROOT / "src" / m.group(2))
        if path.exists() and path not in tools:
            tools.append(path)
    return [*registry.files, *lib_files, *tools]


def session_text(doc: Path = SESSION_DOC, lib: Path = LIB_SRC) -> str:
    """What a session at a terminal reads: the handbook with its passes, then
    the lib."""
    return entry_text(doc, lib)


def _handbook_docs(docs: Path = DOCS_DIR) -> list[Path]:
    """The handbook's documents under `docs`, in name order."""
    return sorted(docs.glob("*.md"))


def _no_doc(name: str, docs: Path = DOCS_DIR) -> SystemExit:
    """The exit where no handbook doc has the name `name` (`_named_doc`):
    the line that gives the forms of a name and lists each doc's names."""
    taken = ", ".join(_doc_names(path) for path in _handbook_docs(docs))
    link = repo_label(docs / "<stem>.md")
    return SystemExit(f"no handbook doc named `{name}`; a doc is named by its "
                      f"title, its file stem or its link form, `{link}`: "
                      f"{taken}")


def _named_doc(name: str, docs: Path = DOCS_DIR) -> Path | None:
    """The handbook doc a reader refers to: the slug of its title, as a render
    shows it, its file stem, or the link form a document carries,
    `docs/handbook/<stem>.md`; None where no doc has that name."""
    if name.endswith(".md"):
        name = name[:-3]
    name = name.rsplit("/", 1)[-1]
    want = nm.slug(name)
    for path in _handbook_docs(docs):
        if path.stem == want or path.stem == name:
            return path
        title = _doc_title(path)
        if title is not None and nm.slug(title) == want:
            return path
    return None


def _doc_title(path: Path) -> str | None:
    """The title of the handbook doc at `path` (`_title`)."""
    return _title(nm.parse(path.read_text(), path.name))


def _doc_names(path: Path) -> str:
    """The names `_named_doc` takes for one handbook doc, as `_no_doc`
    lists them: its title, then its file stem."""
    title = _doc_title(path)
    stem = f"`{path.stem}`"
    return stem if title is None else f"`{title}` ({stem})"


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
        code = "```\n" + "\n".join(_run_code(run, lines, docs)) + "\n```"
        return "\n\n".join(p for p in (f"# {name}", prose, code) if p) + "\n"
    raise SystemExit(f"no component `{name}` in `{repo_label(src)}`")


def section_text(where: str, docs: Path = DOCS_DIR) -> str:
    """One section of a handbook doc in full, named `<doc>#<section>`, or
    by its heading alone, bare or as a link within a document carries it,
    `#<section>`, where one section of the handbook's documents has that
    heading, the heading standing alone also where `<doc>` names no doc, as
    an agent's title in place of the chapter, or one lib component's
    interface, named
    `programs/lib/<module>.dl#<Component>`.
    The doc is named as `_named_doc` takes it, and the section is the title
    a render shows, slugified, so a reader runs the command off the lines in
    front of them. A render leaves no line out, so the section arrives with
    the glosses and the drafts an edition excludes."""
    name, sep, ident = where.partition("#")
    name, ident = name.strip(), ident.strip()
    if name.endswith(".dl"):
        src = DOCUMENTS_ROOT / name
        if not src.exists():
            raise SystemExit(f"no lib source named `{name}`")
        return lib_component(src, ident)
    registry = nm.Registry(DOCUMENTS_ROOT)
    heading = (ident if sep and not name
               else name if not sep and not name.endswith(".md") else None)
    if heading is not None:
        document, node = _bare_section(registry, heading, docs)
    elif (path := _named_doc(name, docs)) is None:
        try:
            document, node = _bare_section(registry, ident, docs)
        except SystemExit:
            raise _no_doc(name, docs)
    else:
        document = registry.load(path)
        ids = registry.ids[document.source]
        node = ids.get(nm.slug(ident)) if sep else next(iter(ids.values()), None)
        if node is None:
            raise SystemExit(
                f"no section `{ident}` in {registry.rel(document)}")
    body = nm.Node(nm.DOCUMENT, source=document.source)
    body.children = [node]
    return nm.render(body, registry)


def _bare_section(registry: nm.Registry, heading: str, docs: Path
                  ) -> tuple[nm.Node, nm.Node]:
    """The one section of the handbook's documents whose heading is
    `heading`, a document's title among them, with its document; where
    none or more than one is, the command exits with the line that says
    so, naming each candidate in the `<doc>#<section>` form."""
    want = nm.slug(heading)
    found: list[tuple[nm.Node, nm.Node]] = []
    for path in _handbook_docs(docs):
        document = registry.load(path)
        node = registry.ids[document.source].get(want)
        if node is not None and node.kind == nm.HEADING:
            found.append((document, node))
    if len(found) == 1:
        return found[0]
    if not found:
        raise SystemExit(f"no section `{heading}` in the handbook's documents")
    named = ", ".join(
        f"`{_title(document)}#{node.text}`" for document, node in found)
    raise SystemExit(f"`{heading}` is a section of more than one handbook "
                     f"document; name one: {named}")


def _first_heading(document: nm.Node) -> nm.Node | None:
    """A document's first heading; None where it has none."""
    return next((c for c in document.children if c.kind == nm.HEADING), None)


def _title(document: nm.Node) -> str | None:
    """A document's title, its first heading's text (`_first_heading`);
    None where it has no heading."""
    head = _first_heading(document)
    return None if head is None else head.text


def workflow_bundle(name: str, roles: Path = ROLE_DIR) -> dict:
    """What a workflow run needs: the text of every role under `roles`, since
    a run picks the ones it reaches. The script holds its own briefs and its
    own return schemas, each an `mctx` literal the check reads where it
    stands. A name no script under `WORKFLOW_DIR` carries is an error."""
    workflow_file(name)
    return {
        "roles": {r: role_text(r, roles) for r in _workflow_roles(name, roles)},
    }


def _workflow_roles(name: str, roles: Path) -> list[str]:
    """Every role under `roles`, since a run picks the ones it reaches."""
    return role_stems(roles)


def role_stems(roles: Path = ROLE_DIR) -> list[str]:
    """The stem of each role file under `roles`, in name order."""
    return sorted(p.stem for p in roles.glob("*.md"))


BRIEF_MESSAGE = "brief"
"""The one value of an agent document's `message` attribute."""


def _takes_brief(document: nm.Node) -> bool:
    """Whether an agent document's `message` attribute is `brief`: it takes
    the brief alone as its message. A document with no such attribute
    takes a role as its message, and any other value is an error."""
    value = document.attr("message")
    if value is None:
        return False
    if value.strip() != BRIEF_MESSAGE:
        raise SystemExit(f"`message: {value.strip()}` in {document.source} "
                         f"is no message form; the one form is "
                         f"`{BRIEF_MESSAGE}`")
    return True


def role_body(name: str, roles: Path = ROLE_DIR) -> str:
    """One role document under `roles`, as the agent running it reads it: the
    text the agent's prompt opens with, and nothing above."""
    registry = nm.Registry(DOCUMENTS_ROOT)
    return nm.role(registry.load(role_file(name, roles)), registry)[1]


def role_text(name: str, roles: Path = ROLE_DIR) -> str:
    """One role document under `roles`, as the session that spawns the role
    reads it: `Agent: <name>` on the first line, then the text the agent's
    prompt opens with."""
    registry = nm.Registry(DOCUMENTS_ROOT)
    agent, text = nm.role(registry.load(role_file(name, roles)), registry)
    return f"Agent: {agent}\n\n{text}"


def agent_prompt(handbook: str) -> str:
    """The handbook agent's system prompt over a rendering of the handbook."""
    return mctx("Your prompt opens with your role, then its brief. Follow "
                "the role.") + "\n\n" + handbook


def agent_definition(document: nm.Node, handbook: str) -> str:
    """An agent's definition file: the agent document's front matter as it
    stands, then the prompt. A document whose `message` attribute is `brief`
    takes the brief alone as its message, and its rendering is the whole
    prompt; any other agent's message opens with a role, and the prompt says
    so."""
    if _takes_brief(document):
        return f"{document.front}\n{handbook}"
    return f"{document.front}\n{agent_prompt(handbook)}"


def _write_whole(path: Path, text: str) -> Path:
    """Write a generated file, whole (`engine.memo.write_whole`): a reader
    that opens it while the write is in progress reads the old file or the
    new one. A file that already holds the text is left alone."""
    if path.exists() and path.read_text() == text:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    write_whole(path, text.encode())
    return path


def write_interfaces(lib: Path = LIB_SRC) -> list[Path]:
    """Write the interface file beside each of the lib's sources, each under
    a line saying it's generated, and the module of the lib's wrappers
    (`write_wrappers`), and return the paths."""
    return [_write_whole(
        interface_path(path),
        mctx("<!-- Generated from {name} by scripts/context.py. -->").format(
            name=path.name) + "\n\n" + lib_doc(text))
        for path, text in lib_sources(lib)]


WRAPPERS_PATH = REPO_ROOT / "src" / "lib_components" / "components.py"
"""The Python module of the lib's component wrappers."""


def _upper_snake(name: str) -> str:
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).upper()


@dataclass(frozen=True)
class _WrappedDecl:
    """A relation of a component as its wrapper passes it: its name,
    whether it is an input, whether it is declared `inline`, and its
    column names and types, each type
    written in the component's own type parameters."""

    name: str
    input: bool
    inline: bool
    column_names: tuple[str, ...]
    column_types: tuple[str, ...]


def _comp_decls(comp: Comp, comps: dict[str, tuple[Comp, list[str]]]
                ) -> list[_WrappedDecl]:
    """The public relations a component declares or inherits from its
    base, its own before its base's."""
    _, lines = comps[comp.name]
    out = [_WrappedDecl(it.name, _is_input(it, lines),
                        Qualifier.INLINE in it.qualifiers,
                        tuple(c.name for c in it.columns),
                        tuple(c.type for c in it.columns))
           for it in comp.items if isinstance(it, Decl) and not _hidden(it)]
    if comp.base is not None:
        if comp.base not in comps:
            raise SystemExit(f"`{comp.name}` extends `{comp.base}`, which no "
                             f"lib file declares")
        base = comps[comp.base][0]
        given = dict(zip(base.type_params, comp.base_type_args, strict=True))
        names = {d.name for d in out}
        out += [_WrappedDecl(d.name, d.input, d.inline, d.column_names,
                             tuple(given.get(t, t) for t in d.column_types))
                for d in _comp_decls(base, comps) if d.name not in names]
    return out


def _type_expr(t: str, comp: Comp, types: list[str]) -> str | None:
    """The Python expression of the column type `t` in a wrapper of
    `comp`: its type parameter, or the member of `Primitive` or `LibType`
    that names it. None for a type the calling program declares, which
    no Python call can declare."""
    if t in comp.type_params:
        return t
    if (prim := Primitive.named(t)) is not None:
        return f"Primitive.{prim.name}"
    if t in types:
        return f"LibType.{_upper_snake(t)}"
    return None


def wrappers_text(lib: Path = LIB_SRC) -> str:
    """The Python module of the lib's wrappers: the lib's types as an enum,
    and for each public top-level component whose columns are of the
    lib's types a function that runs it through `lib_components.call.call`
    over the relations it does not declare `inline`, with a tuple type of
    its output relations. A component that declares every relation
    `inline` gets no function."""
    types: list[str] = []
    comps: dict[str, tuple[Comp, list[str]]] = {}
    order: list[tuple[Path, Comp]] = []
    for path, text in lib_sources(lib):
        program = parse(text)
        for it in program.items:
            if isinstance(it, TypeDecl) and not _hidden(it):
                types.append(it.name)
            elif isinstance(it, Comp) and not _hidden(it):
                comps[it.name] = (it, text.splitlines())
                order.append((path, it))
    out = [mctx("\"\"\"Generated from the lib by scripts/context.py.\"\"\""), "",
           "from collections.abc import Iterable, Mapping",
           "from enum import StrEnum",
           "from typing import NamedTuple", "",
           "from engine.program import Primitive",
           "from lib_components.call import (Columns, GridTypes, PyRow, PyValue, Relation, Size,",
           "                                  call)",
           "", "",
           "class LibType(StrEnum):",
           '    """The types the lib declares, by name."""', ""]
    out += [f'    {_upper_snake(t)} = "{t}"' for t in types]
    out += ["", "", "type TypeArg = Primitive | LibType"]
    for path, comp in order:
        decls = [d for d in _comp_decls(comp, comps) if not d.inline]
        if not decls:
            continue
        exprs = {d.name: [_type_expr(t, comp, types) for t in d.column_types]
                 for d in decls}
        if any(None in e for e in exprs.values()):
            continue
        for d in decls:
            if keyword.iskeyword(d.name):
                raise SystemExit(f"`{comp.name}.{d.name}` is a Python keyword")
        ins = [d.name for d in decls if d.input]
        outs = [d.name for d in decls if not d.input]
        rows = f"{comp.name}Rows"
        out += ["", "", f"class {rows}(NamedTuple):",
                f'    """The output relations of `{comp.name}` '
                f'({repo_label(path)})."""', ""]
        out += [f"    {o}: Relation" for o in outs] or ["    pass"]
        params = [f"{t}: TypeArg" for t in comp.type_params]
        params += ["*", "sizes: Mapping[PyValue, Size] | None = None"]
        params += [f"{i}: Iterable[PyRow] | None = None" for i in ins]
        columns = ", ".join(
            f"{d.name!r}: Columns(("
            + "".join(f"{e}, " for e in exprs[d.name])
            + f"), {d.column_names[:1] == ('key',)})" for d in decls)
        out += ["", "", f"def {comp.name}({', '.join(params)}) -> {rows}:",
                f'    """Runs `{comp.name}` ({repo_label(path)}) over the rows '
                f'given, a cell of each `Position` column in the grid of '
                f'`sizes` for its key, or in the one grid of `sizes` where '
                f'the relation has no key, and each `Offset` column as a '
                f'(row, column) displacement."""',
                f"    got = call({comp.name!r}, [{', '.join(comp.type_params)}],",
                "               GridTypes(LibType.POSITION, LibType.OFFSET),",
                "               {" + columns + "},",
                "               {" + ", ".join(f"{i!r}: {i}" for i in ins) + "},",
                f"               {outs!r}, sizes)",
                f"    return {rows}(" + ", ".join(f"got[{o!r}]" for o in outs) + ")"]
    return "\n".join(out) + "\n"


def write_wrappers(lib: Path = LIB_SRC) -> Path:
    """Write the module of the lib's wrappers (`wrappers_text`), and return
    its path."""
    return _write_whole(WRAPPERS_PATH, wrappers_text(lib))


def agent_names(agents: Path = AGENT_DIR) -> list[str]:
    """The agents defined under `agents`: one per document with front
    matter."""
    return [p.stem for p in sorted(agents.glob("*.md"))
            if p.read_text().startswith("---\n")]


def write_agent(path: Path = AGENT_PATH, lib: Path = LIB_SRC,
                agents: Path = AGENT_DIR) -> Path:
    """Write every agent definition under `agents`, the lib's interface
    files, and the manifest (`AGENT_MANIFEST`), and return the handbook
    agent's path. `path` is the handbook agent's file, and each agent's file
    stands beside it under the agent's name."""
    write_interfaces(lib)
    written = agent_paths(path, agents)
    for name, out in written:
        _write_whole(out, agent_definition(agent_document(name, agents),
                                           render(name, lib, agents)))
    _write_manifest(path.parent, [*generated_agents(path.parent),
                                  *(out.name for _name, out in written)])
    return path


# The file `write_agent` keeps beside the agent files: the name of each file
# there it wrote, one per line. `remove_stale_agents` removes no file this
# list leaves out, so a hand-written agent file stays.
AGENT_MANIFEST = ".manifest"


def generated_agents(out: Path) -> list[str]:
    """The files under `out` that `write_agent` wrote and that still stand,
    by name, as its manifest lists them."""
    manifest = out / AGENT_MANIFEST
    if not manifest.exists():
        return []
    return [name for name in manifest.read_text().splitlines()
            if (out / name).exists()]


def _write_manifest(out: Path, names: list[str]) -> None:
    _write_whole(out / AGENT_MANIFEST,
                 "".join(f"{name}\n" for name in sorted(set(names))))


@dataclass(frozen=True)
class StaleAgents:
    """The agent files under one directory that have no document."""

    removed: list[Path]
    """The files `write_agent` wrote, which `remove_stale_agents` removed."""
    unlisted: list[Path]
    """The files its manifest does not list, left in place."""


def remove_stale_agents(path: Path = AGENT_PATH, agents: Path = AGENT_DIR
                        ) -> StaleAgents:
    """Remove each file beside `path` that `write_agent` wrote and whose
    document under `agents` no longer exists."""
    out = path.parent
    current = {file.name for _name, file in agent_paths(path, agents)}
    listed = generated_agents(out)
    removed = [out / name for name in listed if name not in current]
    for file in removed:
        file.unlink(missing_ok=True)
    _write_manifest(out, [name for name in listed if name in current])
    unlisted = [file for file in sorted(out.glob(f"*{path.suffix}"))
                if file.name not in current and file.name not in listed]
    return StaleAgents(removed, unlisted)


def agent_paths(path: Path = AGENT_PATH, agents: Path = AGENT_DIR
                ) -> list[tuple[str, Path]]:
    """Each agent under `agents` with the file `write_agent` writes it to:
    beside `path`, the handbook agent's file, under the agent's name."""
    return [(name, path.with_name(f"{name}{path.suffix}"))
            for name in agent_names(agents)]


def write_analyze_next(path: Path = ANALYZE_NEXT_PATH,
                       agents: Path = AGENT_DIR) -> Path:
    """Write the steps the analyze agent reads after it writes the concept,
    and return the path."""
    return _write_whole(path, render(ANALYZE_NEXT, agents=agents))


# The files every codex session on the repo reads, in the desktop app or the
# CLI: `prompts/codex.md` rendered as the project's AGENTS.md, and the user's
# own style, `docs/codex-style.md`, as the developer instructions in the
# project config. Neither is tracked, and the style file is the user's to
# keep. CLAUDE.md is the Claude session's router and does not render here.
CODEX_STYLE = Path("docs") / "codex-style.md"
CODEX_CONFIG = Path(".codex") / "config.toml"
# The project-doc budget; the default truncates the handbook silently.
CODEX_DOC_BYTES = 1 << 20
# The permission profile the session runs under. The built-in `:workspace`
# profile keeps the workspace root's own `.codex` and `.git` read-only, and
# the profile below lifts that for `.codex`, so a session can regenerate
# this file. A profile does not compose with `sandbox_mode`, so the config
# carries one or the other. The project layer applies only to a project the
# user's own config trusts.
CODEX_PROFILE = "project"


def uncommented(text: str) -> str:
    """The text without its HTML comments. A comment that fills whole lines
    takes those lines with it; an inline one takes the space before it."""
    text = re.sub(r"^[ \t]*<!--.*?-->[ \t]*\n", "", text, flags=re.S | re.M)
    return re.sub(r" ?<!--.*?-->", "", text, flags=re.S)


def codex_config(style: str | None) -> str:
    """The project config: the style as the developer instructions when
    there is one, the doc budget, and the permissions that let a session
    edit the workspace, this file included."""
    keys: dict[str, object] = {}
    if style is not None:
        keys["developer_instructions"] = uncommented(style)
    keys["project_doc_max_bytes"] = CODEX_DOC_BYTES
    keys["default_permissions"] = CODEX_PROFILE
    # json.dumps gives a TOML basic string: the escapes agree on these
    # values.
    head = "".join(f"{k} = {json.dumps(v)}\n" for k, v in keys.items())
    return head + f"""
[permissions.{CODEX_PROFILE}]
extends = ":workspace"

[permissions.{CODEX_PROFILE}.filesystem.":workspace_roots"]
".codex" = "write"
"""


def write_codex(root: Path = REPO_ROOT, lib: Path = LIB_SRC,
                doc: Path = CODEX_DOC) -> list[Path]:
    """Write the codex files under `root` and return their paths."""
    style_path = root / CODEX_STYLE
    style = style_path.read_text() if style_path.exists() else None
    return [_write_whole(root / "AGENTS.md", entry_text(doc, lib)),
            _write_whole(root / CODEX_CONFIG, codex_config(style))]


# A digest file no longer current, and untouched for this long, has no session
# left reading it.
DIGEST_TTL = 24 * 3600


def sweep_digests(path: Path, now: float | None = None) -> None:
    """Remove the stale digest files beside `path`, keeping `path` itself.

    A file named `<family>-<digest>.md` holds one rendering of its sources.
    A new rendering earns a new name, and the file it replaces stays on disk
    for the sessions still reading it. The age is time since a caller last
    took the file, so a caller that takes one already on disk touches it.
    """
    now = time.time() if now is None else now
    family = path.name.rsplit("-", 1)[0]
    for other in path.parent.glob(f"{family}-*.md"):
        if other == path:
            continue
        try:
            if now - other.stat().st_mtime > DIGEST_TTL:
                other.unlink()
        except OSError:
            continue


# ---------------------------------------------------------------- contexts

# A reader's context, printed as the reader receives it. Each section opens
# with a marker line, so two runs diff line by line.
MARKER = "==== {what} ====\n"

# The sample values a printed message takes in place of the ones a run fills.
SAMPLE_TID = "0000abcd"
SAMPLE_TASK = '{"train": [{"input": [[0]], "output": [[1]]}], "test": []}'
SAMPLE_REPORTS = "<prior reports>"
SAMPLE_ENTRY = "docs/wf-solver/proposals/<entry>.md"
SAMPLE_SCOPE = "every solver"
SAMPLE_SCRATCH = "work/console/surveys/<entry>/<run time>"

# The session's own skill, which a session at a terminal reads beside the
# handbook.
SESSION_SKILL = document(checkout.skills()) / "session" / "SKILL.md"
CONSOLE_DIR = document(checkout.console())


def workflow_dir(root: Path = DOCUMENTS_ROOT) -> Path:
    """`.claude/workflows/` under the documents root `root`."""
    return document(checkout.workflows(), root)


WORKFLOW_DIR = workflow_dir()
# The scripts that build a role's brief. A file here that states the role on a
# line about roles spawns that role.
SPAWN_GLOBS = ((WORKFLOW_DIR, "*.js"), (document(checkout.scripts()), "*.py"),
               (CONSOLE_DIR, "*.py"), (CONSOLE_DIR / "solver_console", "*.py"))
# The documents that tell a session to spawn a role. A session that reads one
# of them briefs the role itself.
SPAWN_DOC_GLOBS = ((DOCS_DIR, "*.md"),
                   (document(checkout.prompts()), "**/*.md"))


def _section(what: str, text: str) -> str:
    """One marked section: the marker line, a blank line, and the text."""
    return MARKER.format(what=what) + "\n" + text.rstrip("\n") + "\n"


def _console():
    """The console's prompt builders and its stage chain. The console reads
    this module, so the import stands here."""
    paths.console_importable()
    from solver_console import prompts, store
    return prompts, store


def _body(path: Path) -> str:
    """A file's text from its first heading (`_first_heading`), so a front
    matter block that reaches no agent is left out."""
    text = path.read_text()
    head = _first_heading(nm.parse(text, path.name))
    if head is None:
        return text
    return "".join(text.splitlines(keepends=True)[head.line - 1:])


def session_context() -> str:
    """What a session at a terminal reads: the session skill the user invokes,
    then the session document with the lib, which the skill's first line sends
    the session to read. The lib's interface files are written first, the way
    the no-argument form writes them, so the lib index lists the files as they
    stand."""
    write_interfaces()
    return "\n".join([
        _section(repo_label(SESSION_SKILL),
                 _body(SESSION_SKILL)),
        _section(repo_label(SESSION_DOC), session_text()),
    ])


def codex_context() -> str:
    """What a codex session on the repo reads: AGENTS.md, as `--write`
    renders it."""
    return _section("AGENTS.md", entry_text(CODEX_DOC))


def agent_prompt_text(name: str, lib: Path = LIB_SRC,
                      agents: Path = AGENT_DIR) -> str:
    """An agent's system prompt: what its definition file holds under the
    front matter."""
    document = agent_document(name, agents)
    text = render(name, lib, agents)
    if _takes_brief(document):
        return text
    return agent_prompt(text)


def agent_context(name: str) -> str:
    """One agent's system prompt, as `--write` writes it. The front matter
    the harness reads stands above it in the file, and the agent receives
    what follows."""
    if name not in agent_names():
        raise SystemExit(f"no agent named `{name}`; the agents are "
                         + ", ".join(agent_names()))
    text = _section(repo_label(agent_file(name)), agent_prompt_text(name))
    if name == "analyze":
        text += "\n" + _section(repo_label(ANALYZE_NEXT_PATH),
                                render(ANALYZE_NEXT))
    return text


def _role_agent(name: str, roles: Path = ROLE_DIR) -> str:
    """The agent a role runs on: its `agent` attribute, or the handbook
    agent."""
    registry = nm.Registry(DOCUMENTS_ROOT)
    return nm.role(registry.load(role_file(name, roles)), registry)[0]


def _spawners(name: str) -> list[str]:
    """The scripts that build the role's brief: the ones stating the role on a
    line that is about roles."""
    out = []
    for directory, pattern in SPAWN_GLOBS:
        for path in sorted(directory.glob(pattern)):
            for line in path.read_text().splitlines():
                if _role_columns(line, name):
                    out.append(repo_label(path))
                    break
    return out


def _word_at(word: str, line: str) -> int | None:
    """The column of the first whole-word occurrence of `word` on the
    line; None where it does not occur."""
    m = re.search(rf"\b{re.escape(word)}\b", line)
    return None if m is None else m.start()


def _role_columns(line: str, stem: str) -> list[int]:
    """Where a script's line refers to the role `stem`: as `roles.<stem>`,
    or as the quoted stem on a line that is about roles; the column of
    each."""
    out: list[int] = []
    if (at := _word_at(f"roles.{stem}", line)) is not None:
        out.append(at)
    if (m := re.search(rf"""(['"]){re.escape(stem)}\1""", line)) \
            and "role" in line.lower():
        out.append(m.start())
    return out


def _spawn_docs(name: str) -> list[str]:
    """The documents that tell a session to spawn the role."""
    said = re.compile(rf"(?i:spawn) the `{re.escape(name)}` role")
    out = []
    for directory, pattern in SPAWN_DOC_GLOBS:
        for path in sorted(directory.glob(pattern)):
            if said.search(path.read_text()):
                out.append(repo_label(path))
    return sorted(set(out))


def spawn_line(name: str) -> str:
    """Where the role's brief comes from, in one line: the script that builds
    it, the session that spawns it per a document, or both."""
    files = ", ".join(_spawners(name))
    docs = ", ".join(_spawn_docs(name))
    if files and docs:
        return mctx("Brief: built by {files}, and by the session that spawns "
                    "it per {docs}.").format(files=files, docs=docs)
    if files:
        return mctx("Brief: built by {files}.").format(files=files)
    if docs:
        return mctx("Brief: built by the session that spawns it per "
                    "{docs}.").format(docs=docs)
    return mctx("Brief: briefed by the session that spawns it.")


class Unplaced(Enum):
    """A role a workflow script refers to that no phase of the script
    reaches."""

    NO_PHASE = "no phase"


type Phase = str | Unplaced
"""The phase a workflow run reaches a role in: a title of the script's
`meta.phases`, or `Unplaced.NO_PHASE`."""


def role_context(name: str, roles: Path = ROLE_DIR,
                 stage: Phase | None = None,
                 seen: set[str] | None = None,
                 brief: bool = True) -> str:
    """What an agent running the role reads: its agent's definition, its role
    text, then the line saying where its brief comes from. `stage` is the
    phase a workflow run reaches the role in, None for a role read outside
    a workflow. `seen` holds the agents a caller has
    already printed, and an agent it holds takes a marker line in place of its
    definition. `brief` set to False leaves out the line about the brief, for
    a caller that states the source itself."""
    if not role_file(name, roles).is_file():
        raise SystemExit(f"no role named `{name}`")
    agent = _role_agent(name, roles)
    path = repo_label(agent_file(agent))
    if seen is not None and agent in seen:
        head = MARKER.format(
            what=mctx("{path}, the definition printed above").format(path=path))
    else:
        head = agent_context(agent)
        if seen is not None:
            seen.add(agent)
    label = repo_label(role_file(name, roles))
    if stage is Unplaced.NO_PHASE:
        label = mctx("{path}, in a phase this listing does not find").format(
            path=label)
    elif stage is not None:
        label = mctx("{path}, in the {phase} phase").format(
            path=label, phase=stage)
    parts = [head, _section(label, role_body(name, roles))]
    if brief:
        parts.append(_section(mctx("the brief"), spawn_line(name)))
    return "\n".join(parts)


def console_stages() -> list[str]:
    """The stages of the chain a wave runs when it states none."""
    _, store = _console()
    return [st["name"] for st in store.default_chain()]


def _stage_messages(stage: str, stages: list[str], prompts) -> list[tuple[str, str]]:
    """Each message the console sends a worker in that stage: the ordinary
    ones in order, then each one a condition sends, under the condition."""
    first, last = stages[0], stages[-1]
    more = "yes" if stage != last else ""
    out: list[tuple[str, str]] = []
    if stage == first:
        out.append((mctx("message: create"),
                    prompts.message("create", tid=SAMPLE_TID,
                                    task=SAMPLE_TASK)))
    else:
        out.append((mctx("message: advance, where the stages before it left "
                         "a solver on disk"),
                    prompts.message("advance", tid=SAMPLE_TID,
                                    task=SAMPLE_TASK,
                                    reports=SAMPLE_REPORTS, more=more)))
        out.append((mctx("message: no-solver, where the stages before it "
                         "left no solver on disk"),
                    prompts.message("no-solver", tid=SAMPLE_TID,
                                    task=SAMPLE_TASK,
                                    reports=SAMPLE_REPORTS, more=more)))
    if stage == last:
        out.append((mctx("message: finalize, where the pass starts over a "
                         "committed solver"),
                    prompts.message("finalize", tid=SAMPLE_TID,
                                    task=SAMPLE_TASK,
                                    reports=SAMPLE_REPORTS)))
    out.append((mctx("message: nudge, where a turn ended at the output limit "
                     "with nothing run"), prompts.nudge_brief()))
    # A bail and a handoff ask for the report whose landing hands off, so the
    # last stage, which hands off to nobody, is sent neither.
    if stage != last:
        out.extend([
            (mctx("message: bail, where two turns ended with nothing run"),
             prompts.bail_brief()),
            (mctx("message: handoff, where the console asks for the handoff "
                  "report"), prompts.handoff_brief()),
            (mctx("message: refused-handoff, where the worker refuses that "
                  "ask"), prompts.refused_handoff_brief()),
        ])
    out.extend([
        (mctx("message: callout, where the pass lands and the callouts are "
              "asked for"), prompts.callout_brief()),
        (mctx("message: refused-callout, where the worker refuses that ask"),
         prompts.refused_callout_brief()),
    ])
    return out


def console_context(stage: str) -> str:
    """What a console worker reads in one stage: the system-prompt appendix,
    then each message the console sends it. The stages are the ones
    `store.default_chain` gives, which is the chain a wave runs when it states
    none."""
    prompts, _ = _console()
    stages = console_stages()
    if stage not in stages:
        raise SystemExit(f"no console stage named `{stage}`; the stages are "
                         + ", ".join(stages))
    parts = [_section(APPENDIX, prompts.append_text())]
    parts += [_section(what, text)
              for what, text in _stage_messages(stage, stages, prompts)]
    return "\n".join(parts)


def survey_context() -> str:
    """What a survey session reads: the appendix its agent takes as its system
    prompt, then the role's text and the survey brief."""
    prompts, _ = _console()
    agent = agent_document(_role_agent("survey"))
    return "\n".join([
        _section(APPENDIX, prompts.append_text(
            index=lib_form(agent) is LibForm.INDEX)),
        _section(repo_label(role_file("survey")),
                 prompts.role_text("survey")),
        _section(mctx("the `survey` message"),
                 prompts.survey_brief(entry=SAMPLE_ENTRY, scope=SAMPLE_SCOPE,
                                      scratch=SAMPLE_SCRATCH)),
    ])


def workflow_names(workflows: Path = WORKFLOW_DIR) -> list[str]:
    """The workflow scripts, by name."""
    return sorted(p.stem for p in workflows.glob("*.js"))


PHASES_RE = re.compile(r"phases:\s*\[(.*?)\n\s*\]", re.S)
TITLE_RE = re.compile(r"title:\s*'([^']*)'")
PHASE_RE = re.compile(r"phase:\s*'([^']*)'")
# A `phase()` statement on a line of its own, which opens a run of lines whose
# agents run in that phase.
BARE_PHASE_RE = re.compile(r"\s*phase\('([^']*)'\)\s*$")
# A variable bound to a role text, as in `const role = args.roles.cleanup`.
ROLE_ALIAS_RE = re.compile(
    r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=[^\n]*?"
    r"\broles\.([A-Za-z0-9_-]+)\b")
# A list of role stems, as in `const FIX_ROLES = ['retro-fix', ...]`.
ROLE_LIST_RE = re.compile(r"\bconst\s+([A-Za-z_$][\w$]*)\s*=\s*\[([^\]]*)\]")
# A one-line arrow function, whose body may return role stems.
ARROW_FN_RE = re.compile(r"\bconst\s+([A-Za-z_$][\w$]*)\s*=\s*\([^)]*\)\s*=>"
                         r"([^\n]*)")
QUOTED_RE = re.compile(r"""['"]([^'"]+)['"]""")
# How far past an `agent(` the scan looks for the call's closing paren.
CALL_LINES = 40


def _workflow_phases(text: str) -> list[str]:
    """The phase titles the script's `meta.phases` gives, in order."""
    block = PHASES_RE.search(text)
    return TITLE_RE.findall(block.group(1)) if block else []


def _call_spans(text: str) -> list[tuple[int, int]]:
    """The first and last line of each `agent(` call, counting parentheses
    outside quoted text."""
    spans = []
    for opening in re.finditer(r"\bagent\(", text):
        at = opening.end() - 1
        depth = 0
        quote = ""
        index = at
        while index < len(text):
            char = text[index]
            if quote:
                if char == "\\":
                    index += 2
                    continue
                if char == quote:
                    quote = ""
            elif char in "'\"`":
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    break
            index += 1
        first = text.count("\n", 0, at) + 1
        last = text.count("\n", 0, min(index, len(text) - 1)) + 1
        if last - first <= CALL_LINES:
            spans.append((first, last))
    return spans


def _call_phases(text: str) -> dict[int, str]:
    """The phase each line stands in through the `phase:` option of the
    innermost `agent(` call around it."""
    lines = text.splitlines()
    out: dict[int, str] = {}
    for first, last in sorted(_call_spans(text), key=lambda s: s[1] - s[0]):
        option = PHASE_RE.search("\n".join(lines[first - 1:last]))
        if not option:
            continue
        for number in range(first, last + 1):
            out.setdefault(number, option.group(1))
    return out


def _role_aliases(text: str, stems: set[str]) -> dict[str, str]:
    """Each variable bound to a role text, with the stem it carries."""
    return {m.group(1): m.group(2) for m in ROLE_ALIAS_RE.finditer(text)
            if m.group(2) in stems}


def _role_groups(text: str, stems: set[str]) -> dict[str, list[str]]:
    """Each name that stands for several roles: a list of role stems, and a
    function whose body returns members of such a list."""
    groups: dict[str, list[str]] = {}
    for m in ROLE_LIST_RE.finditer(text):
        members = [q for q in QUOTED_RE.findall(m.group(2)) if q in stems]
        if members:
            groups[m.group(1)] = members
    listed = {stem for members in groups.values() for stem in members}
    for m in ARROW_FN_RE.finditer(text):
        members = [q for q in QUOTED_RE.findall(m.group(2)) if q in listed]
        if members and m.group(1) not in groups:
            groups[m.group(1)] = members
    return groups


def _at_column(named: dict[str, int], stem: str, column: int) -> None:
    """Note that a line refers to `stem` at `column`, keeping the first
    column the line refers to it at."""
    named[stem] = min(column, named.get(stem, column))


def workflow_phases(name: str, roles: Path = ROLE_DIR,
                    workflows: Path = WORKFLOW_DIR) -> dict[str, Phase]:
    """Each role the workflow script refers to, in phase order, with the phase it
    runs in. A line inside an `agent(` call that carries a `phase:` option
    takes that phase, and any other line takes the phase of the nearest
    `phase()` statement above it. A line refers to a role by its stem, by a
    variable bound to `roles.<stem>`, or, inside such a call, by a list of
    stems or a function returning members of one. A role no phase reaches
    takes `Unplaced.NO_PHASE`, and it follows the placed roles, at the line it
    first stands on. Roles one line refers to follow the order they stand
    in on it."""
    path = workflow_file(name, workflows)
    text = path.read_text()
    phases = _workflow_phases(text)
    stems = role_stems(roles)
    aliases = _role_aliases(text, set(stems))
    groups = _role_groups(text, set(stems))
    call_phases = _call_phases(text)
    running: Phase = Unplaced.NO_PHASE
    found: dict[str, tuple[int, int, int, Phase]] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        bare = BARE_PHASE_RE.match(line)
        if bare:
            running = bare.group(1)
        option = PHASE_RE.search(line)
        named_phase = option.group(1) if option \
            else call_phases.get(number, running)
        title: Phase = named_phase if named_phase in phases \
            else Unplaced.NO_PHASE
        rank = len(phases) if isinstance(title, Unplaced) \
            else phases.index(title)
        named: dict[str, int] = {}
        for stem in stems:
            for column in _role_columns(line, stem):
                _at_column(named, stem, column)
        for variable, stem in aliases.items():
            if (at := _word_at(variable, line)) is not None:
                _at_column(named, stem, at)
        if number in call_phases:
            for group, members in groups.items():
                if (at := _word_at(group, line)) is not None:
                    for member in members:
                        _at_column(named, member, at)
        for stem, column in named.items():
            at = found.get(stem)
            if at is None or rank < at[0]:
                found[stem] = (rank, number, column, title)
    order = sorted(found, key=lambda s: found[s][:3])
    return {stem: found[stem][3] for stem in order}


def workflow_roles(name: str, roles: Path = ROLE_DIR,
                   workflows: Path = WORKFLOW_DIR) -> list[str]:
    """The roles the workflow script refers to, in phase order."""
    return list(workflow_phases(name, roles, workflows))


def workflow_file(name: str, workflows: Path = WORKFLOW_DIR) -> Path:
    """The script of the workflow `name`; an error where none stands."""
    path = workflows / f"{name}.js"
    if not path.is_file():
        raise SystemExit(f"no workflow named `{name}`; the workflows are "
                         + ", ".join(workflow_names(workflows)))
    return path


def workflow_roleless_phases(name: str, roles: Path = ROLE_DIR,
                             workflows: Path = WORKFLOW_DIR) -> list[str]:
    """The phases of the script's `meta.phases` that no role the roles listing
    places falls in, in `meta.phases` order."""
    path = workflow_file(name, workflows)
    placed = set(workflow_phases(name, roles, workflows).values())
    return [title for title in _workflow_phases(path.read_text())
            if title not in placed]


def workflow_roleless_line(name: str, roles: Path = ROLE_DIR,
                           workflows: Path = WORKFLOW_DIR) -> str:
    """The phases that run an agent with no role, in one line."""
    rest = workflow_roleless_phases(name, roles, workflows)
    if not rest:
        return mctx("Every phase runs a role.")
    return mctx("Phases with no role: {phases}").format(
        phases=", ".join(rest))


def workflow_fragments(name: str, workflows: Path = WORKFLOW_DIR) -> str:
    """The script's briefs and schema descriptions: every `mctx` fragment the
    file holds, in file order, each under a line giving the script and the
    line the fragment starts on. The holes stand as the source writes them."""
    path = workflow_file(name, workflows)
    script = repo_label(path)
    return "\n\n".join(f"{script}:{fragment.line}\n\n{fragment.text.rstrip()}"
                       for fragment in nm.fragments(path, script))


def workflow_context(name: str) -> str:
    """What each agent of a workflow run reads: the role context of every role
    the script refers to, in phase order, the phases no role runs in, then the
    line stating where the briefs are built and the briefs themselves."""
    script = repo_label(workflow_file(name))
    phases = workflow_phases(name)
    parts = [_section(mctx("the roles {path} reaches").format(path=script),
                      "\n".join(phases))]
    # One definition per agent: a later role on the same agent takes a marker
    # line pointing at the copy above.
    seen: set[str] = set()
    parts += [role_context(role, stage=stage, seen=seen, brief=False)
              for role, stage in phases.items()]
    parts.append(_section(mctx("the phases with no role"),
                          workflow_roleless_line(name)))
    briefs = mctx("Brief: built by {path}, in its briefs "
                  "region.").format(path=script)
    parts.append(_section(mctx("the workflow's briefs"),
                          briefs + "\n\n" + workflow_fragments(name)))
    return "\n".join(parts)


class ArgumentForm(StrEnum):
    """The argument a reader of the `context` command takes, as its usage
    line writes it."""

    NAME = "<name>"
    STAGE = "<stage>"


@dataclass(frozen=True)
class Reader:
    """A reader the `context` command knows: the form of the argument it
    takes, None where it takes none; the values that argument takes, from
    the documents root they are listed under; and its context, from the
    arguments."""

    form: ArgumentForm | None
    values: Callable[[Path], list[str]]
    context: Callable[[list[str]], str]


def _no_values(_root: Path) -> list[str]:
    return []


def _console_stages(root: Path) -> list[str]:
    """The console's stages, which `console_stages` lists only under
    `DOCUMENTS_ROOT`: another root is a fault."""
    if root != DOCUMENTS_ROOT:
        raise ValueError(f"the console's stages are listed under {DOCUMENTS_ROOT} alone, "
                         f"not under {root}")
    return console_stages()


CONTEXT_READERS = {
    "session": Reader(None, _no_values, lambda _a: session_context()),
    "codex": Reader(None, _no_values, lambda _a: codex_context()),
    "agent": Reader(ArgumentForm.NAME, lambda r: agent_names(agent_dir(r)),
                    lambda a: agent_context(a[0])),
    "role": Reader(ArgumentForm.NAME, lambda r: role_stems(role_dir(r)),
                   lambda a: role_context(a[0])),
    "console": Reader(ArgumentForm.STAGE, _console_stages,
                      lambda a: console_context(a[0])),
    "survey": Reader(None, _no_values, lambda _a: survey_context()),
    "workflow": Reader(ArgumentForm.NAME, lambda r: workflow_names(workflow_dir(r)),
                       lambda a: workflow_context(a[0])),
}
"""Each reader the `context` command knows, by name."""


def reader_calls() -> list[tuple[str, list[str]]]:
    """Each reader the `context` command knows, with each argument list it
    takes."""
    calls: list[tuple[str, list[str]]] = []
    for name, reader in CONTEXT_READERS.items():
        if reader.form:
            calls += [(name, [value]) for value in reader.values(DOCUMENTS_ROOT)]
        else:
            calls.append((name, []))
    return calls


def contexts_text() -> str:
    """Every reader the `context` command knows, one per line: its name, its
    argument form, and the values that argument takes."""
    out = []
    for name, reader in CONTEXT_READERS.items():
        form = reader.form
        head = f"context {name}" + (f" {form}" if form else "")
        names = reader.values(DOCUMENTS_ROOT)
        out.append(f"{head:<24}{', '.join(names)}".rstrip())
    return "\n".join(out) + "\n"


def context_text(reader: str, args: list[str]) -> str:
    """One reader's whole context, in the order it arrives."""
    if reader not in CONTEXT_READERS:
        raise SystemExit("no reader named "
                         f"`{reader}`\n{contexts_text()}".rstrip())
    known = CONTEXT_READERS[reader]
    form = known.form
    if form and len(args) != 1:
        raise SystemExit(f"usage: context {reader} {form}")
    if not form and args:
        raise SystemExit(f"usage: context {reader}")
    return known.context(args)


CONTEXT_SCRIPT = (checkout.scripts() / "context.py").relative_to(checkout.ROOT)
"""The command that prints a reader's context, from a checkout's root."""


def _command(reader: str, args: list[str]) -> str:
    """The `context` command line that prints one reader's context."""
    return " ".join(["context", reader, *args])


@contextmanager
def _tree_at(commit: str) -> Iterator[Path]:
    """The tree of `commit`, checked out as a detached git worktree of the
    repository in a temporary directory, so that the checkout stays as it
    is and the commit's own code finds the main worktree as in any other
    checkout. The worktree is removed on every exit of the block and leaves
    no entry in `git worktree list`."""
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "tree"
        try:
            checkout.git_out(REPO_ROOT, "worktree", "add", "--detach",
                             str(tree), commit)
        except checkout.GitFailed as e:
            raise SystemExit(e.stderr.strip())
        try:
            yield tree
        finally:
            checkout.git_out(REPO_ROOT, "worktree", "remove", "--force", str(tree))


def _run_in(tree: Path, commit: str, argv: list[str]) -> str:
    """The output of `scripts/context.py` with `argv`, run in `tree`, the
    tree of `commit`, with that tree's own code."""
    paths = [str(tree / "src"), os.environ.get("PYTHONPATH", "")]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(p for p in paths if p)}
    done = subprocess.run([sys.executable, str(tree / CONTEXT_SCRIPT), *argv],
                          cwd=tree, env=env, capture_output=True, text=True)
    if done.returncode != 0:
        failed = mctx("The run of `{command}` at {commit} failed.").format(
            command=" ".join(argv), commit=commit)
        raise SystemExit(f"{failed}\n{done.stderr.strip()}")
    return done.stdout


def _render_in(tree: Path, commit: str, reader: str, args: list[str]) -> str:
    """One reader's whole context as `tree`, the tree of `commit`, renders
    it."""
    return _run_in(tree, commit, ["context", reader, *args])


def context_at(commit: str, reader: str, args: list[str]) -> str:
    """One reader's whole context as the tree of `commit` renders it, with
    that tree's own code, run in a detached worktree of `commit`
    (`_tree_at`)."""
    with _tree_at(commit) as tree:
        return _render_in(tree, commit, reader, args)


def context_diff(commit: str, reader: str, args: list[str]) -> str:
    """The unified diff from one reader's context at `commit`, as
    `context_at` renders it in a detached worktree of `commit`, to its
    context in the checkout. Empty where the two are the same. A side that
    does not define the reader, as `contexts_diff` finds it, gives an empty
    context, so the diff of an added reader gains every line and that of a
    removed one loses every line. A reader neither side defines, and a
    render that fails, are faults."""
    call = (reader, args)
    with _tree_at(commit) as tree:
        then = call in _calls_in(tree, commit)
        before = _render_in(tree, commit, reader, args) if then else ""
    now = call in reader_calls()
    after = context_text(reader, args) if now or not then else ""
    head = _command(reader, args)
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=f"{head} at {commit}", tofile=head))


CONTEXTS_LINE_RE = re.compile(r"context (\S+)(?: (<[^>]*>))? *(.*)")
"""A line of `contexts_text`: the reader, its argument form, and the values
that argument takes."""


def _calls_in(tree: Path, commit: str) -> list[tuple[str, list[str]]]:
    """Each reader the `context` command of `tree`, the tree of `commit`,
    knows, with each argument list it takes, read from that tree's
    `contexts` output, the one form a commit's own code is known to
    give them in."""
    calls: list[tuple[str, list[str]]] = []
    for line in _run_in(tree, commit, ["contexts"]).splitlines():
        match = CONTEXTS_LINE_RE.fullmatch(line)
        if not match:
            raise SystemExit(mctx("A line of `contexts` at {commit} is not a "
                                  "reader: {line}").format(commit=commit, line=line))
        name, form, values = match.groups()
        if form:
            calls += [(name, [v]) for v in values.split(", ") if v]
        else:
            calls.append((name, []))
    return calls


class ReaderChange(StrEnum):
    """How a change alters a reader's context: only the checkout defines
    the reader, only the commit does, or both do and its contexts
    differ."""

    ADDED = "added"
    REMOVED = "removed"
    CHANGED = "changed"


def contexts_diff(commit: str) -> str:
    """Each reader, with its arguments, whose context the change since
    `commit` alters, one per line, marked with its `ReaderChange` where
    only one side defines it. A reader both sides define is altered where
    its context at `commit`, as `context_at` renders it in a detached
    worktree of `commit`, differs from its context in the checkout; a
    render at `commit` that fails is a fault.
    The checkout's readers come first, in `reader_calls` order, then the
    ones only the commit defines."""
    now = reader_calls()
    with _tree_at(commit) as tree:
        then = _calls_in(tree, commit)
        both = [c for c in now if c in then]
        with ThreadPoolExecutor() as pool:
            befores = list(pool.map(lambda c: _render_in(tree, commit, *c), both))
    rendered = {_command(*c): before for c, before in zip(both, befores, strict=True)}
    changes = [(c, ReaderChange.ADDED if c not in then else ReaderChange.CHANGED)
               for c in now]
    changes += [(c, ReaderChange.REMOVED) for c in then if c not in now]
    out = []
    for (reader, args), change in changes:
        command = _command(reader, args)
        if change is ReaderChange.CHANGED:
            if rendered[command] != context_text(reader, args):
                out.append(f"{command}\n")
        else:
            out.append(f"{command} ({change})\n")
    return "".join(out)
