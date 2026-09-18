"""The reference context a solver session reads, projected down to what the
procedure uses.

The lib renders as documentation: each file's `//!` and `///` comments as
prose, and the declarations they document in code blocks, without the rule
bodies. That is the lib's interface, and each file's interface is also
written beside it, as the `.md` of the same stem. The catalog docs render as
one line per entry. The other docs pass through without their editor notes
and their deferred sections. Each rendering names the file that holds the
rest, and derives from the live file, so no copy can go stale.

The handbook renders two ways, and an agent carries each. The lib is its
interface, for a task that edits `.dl`, or an index: one line per public component
of each file, under a note that points at the interface file for the rest. In
the index rendering, some docs are an index too: the doc's preamble and one
line per heading under it, under a note that points at the file for the
sections.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from functools import lru_cache
from pathlib import Path

from dl.dlparse import (Comp, Decl, Define, Include, Init, Item, Program,
                        Rule, TypeDecl, parse)
from dl.paths import PROGRAMS_DIR, REPO_ROOT

DOCS_DIR = REPO_ROOT / "docs" / "wf-solver"
LIB_SRC = PROGRAMS_DIR / "lib.dl"

# The agent definitions, generated from the handbook: an agent runs a role
# under .claude/roles/ with the handbook as its system prompt. The files are
# regenerated at each entry point and not tracked. A role's file names its
# agent in its first line, `Agent: <name>`. A role file with no such line runs
# as the handbook agent.
AGENT_PATH = REPO_ROOT / ".claude" / "agents" / "handbook.md"
AGENT_META = {
    "name": "handbook",
    "description": "The handbook, with the lib as an index: one line per "
                   "component.",
    "model": "opus",
    "effort": "high",
    "tools": "Read, Grep, Glob, Bash, Edit, Write",
}
EXPANDED_AGENT_META = {
    **AGENT_META,
    "name": "handbook-expanded",
    "description": "The handbook, with the lib's full interface: every "
                   "component's relations and their docs.",
}
AGENT_LINE_RE = re.compile(r"\AAgent: (\S+)\n+")


def role_agent(text: str) -> tuple[str, str]:
    """A role's agent and its text: the agent its first line names, or the
    handbook agent, and the text after that line."""
    m = AGENT_LINE_RE.match(text)
    if m is None:
        return AGENT_META["name"], text
    return m.group(1), text[m.end():]


ROLE_NOTE = "Your prompt opens with your role, then its brief. Follow the role.\n\n"

# The docs the procedure reads, in reading order: the theory, then its form,
# then what the corpus made of it.
DOCS = ("procedure.md", "principles.md", "style.md", "patterns.md", "keywords.md",
        "lib-protocol.md", "former-names.md")
# Catalog docs: entries are independent and a session uses few, so the context
# carries the index and the session reads the entry it needs.
INDEX = {"patterns.md"}
# The docs the index edition carries as a heading index: the preamble and the
# headings under it, with the sections left in the file.
HEADING_INDEX = {"procedure.md", "lib-protocol.md", "keywords.md"}


def lib_sources(root: Path = LIB_SRC) -> list[tuple[Path, str]]:
    """The lib's files in include order, each with its text: the root, then
    the file of each `#include` in it, resolved against the root's
    directory."""
    text = root.read_text()
    out = [(root, text)]
    for it in parse(text).items:
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


def _name(it: Item) -> str:
    return it.inst if isinstance(it, Init) else getattr(it, "name", "")


def _hidden(it: Item) -> bool:
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
        out.extend(lines[ln - 1].rstrip() for ln in range(it.line, end + 1))
        if is_input:
            out.extend(lines[ln - 1].rstrip() for ln in sorted(set(facts.get(it.name, []))))
    out.append(lines[comp.end_line - 1].rstrip())
    return out


def _runs(items: list[Item], docs: dict[int, tuple[int, int]]) -> list[list[Item]]:
    """The top-level public items a `///` block may document, each in its
    run. Undocumented siblings on consecutive lines fold into the item over
    them: defines, or subtypes of one base."""
    items = [it for it in items if not isinstance(it, (Include, Rule))]
    out: list[list[Item]] = []
    i = 0
    while i < len(items):
        it = items[i]
        if _hidden(it) or not isinstance(it, DOCUMENTED):
            i += 1
            continue
        run = [it]
        j = i + 1
        while (j < len(items) and type(items[j]) is type(it)
               and items[j].line == run[-1].line + 1
               and docs.get(items[j].line - 1) is None and not _hidden(items[j])
               and (isinstance(it, Define)
                    or (isinstance(it, TypeDecl) and it.rhs.startswith("<:")
                        and items[j].rhs == it.rhs))):
            run.append(items[j])
            j += 1
        out.append(run)
        i = j
    return out


INTERFACE_NOTE = ("A module's interface file, its path with `.md` for `.dl`, holds "
                  "each component's signature and the rest of its doc.")


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
        out.append(f"- {names} — {gist(para)}")
    return "\n\n".join(p for p in (*prose, "\n".join(out)) if p) + "\n"


@lru_cache(maxsize=16)
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
        if len(run) > 1:
            if isinstance(it, Define):
                emit_code([" ".join(d.name for d in run)])
            else:
                emit_code([f".type {', '.join(t.name for t in run)} {it.rhs}"])
        elif isinstance(it, Comp):
            emit_code(_comp_block(it, lines, docs))
        else:
            end = it.end_line if isinstance(it, Decl) else it.line
            emit_code([lines[ln - 1].rstrip() for ln in range(it.line, end + 1)])
    # A block over no item renders where it stands.
    for end, (start, _) in sorted(docs.items()):
        if end not in attached:
            emit_prose(_prose(lines[start - 1:end], ITEM_DOC))
    emit_prose("")
    return "\n\n".join(p for p in parts if p) + "\n"


def gist(para: str) -> str:
    """An entry's first sentence, up to the first period that whitespace
    follows — the catalog docs' convention is that it stands alone under its
    title."""
    return re.split(r"(?<=\.)\s+", para, maxsplit=1)[0]


def entry_index(text: str, source: str) -> str:
    """A `## ` catalog doc as its preamble and one line per entry. The
    preamble says what the doc is, which every entry stands on."""
    blocks = re.split(r"^## ", text, flags=re.M)
    preamble = "\n\n".join(p for p in blocks[0].split("\n\n")[1:] if p.strip())
    out: list[str] = []
    for block in blocks[1:]:
        title, _, rest = block.partition("\n")
        body = re.sub(r"```.*?```", "", rest, flags=re.S)
        opening = ""
        for para in body.split("\n\n"):
            para = " ".join(para.split())
            if para and not para.startswith(("#", "-", "|", "*")):
                opening = gist(para)
                break
        out.append(f"- **{title.strip()}** — {opening}" if opening
                   else f"- **{title.strip()}**")
    note = f"One line per entry. Read {source} for the entries you need."
    return "\n\n".join(p for p in (preamble.strip(), note, "\n".join(out)) if p) + "\n"


HEADING_NOTE = ("The sections are in the source: read a section in {rel} when "
                "the rule you need is under it.")


def heading_index(text: str, source: str) -> str:
    """A doc as its preamble and one line per heading under its title, in
    document order, indented by heading level. The preamble says what the doc
    is, which every section stands on."""
    body = re.sub(r"^```.*?^```", "", text, flags=re.S | re.M)
    head = re.split(r"^## ", body, maxsplit=1, flags=re.M)[0]
    preamble = "\n\n".join(p for p in head.split("\n\n")[1:] if p.strip())
    out = [" " * 4 * (len(m.group(1)) - 2) + f"- **{m.group(2).strip()}**"
           for m in re.finditer(r"^(##+) (.*)$", body, flags=re.M)]
    note = HEADING_NOTE.format(rel=source)
    return "\n\n".join(p for p in (preamble.strip(), note, "\n".join(out)) if p) + "\n"


HEADER = ("# Handbook\n\nThe solver docs and the lib as a session reads "
          "them. Before editing one of these files, open and read it, "
          "because it may contain editing rules not visible here.\n")

NOTES_DROPPED = ("Cited tasks carry worked applications of the principle "
                 "they sit under. Grep the task id in {rel} to read one.")
SECTION_DEFERRED = ("The {title} section is in the source: read it in {rel} "
                    "when a term is unclear.")


def drop_deferred(text: str) -> tuple[str, list[str]]:
    """A doc without its deferred sections, and their titles. A heading
    marked `<!-- deferred -->` opens a section a session reads on demand; the
    section runs to the next heading of its level or above."""
    titles: list[str] = []
    out: list[str] = []
    level = 0   # the deferred section's heading level, 0 outside one
    for line in text.splitlines(keepends=True):
        m = re.match(r"(#+) (.*?)( <!-- deferred -->)?\n", line)
        if m and level and len(m.group(1)) <= level:
            level = 0
        if m and m.group(3):
            titles.append(m.group(2))
            level = len(m.group(1))
        if not level:
            out.append(line)
    return "".join(out), titles


def strip_comments(text: str) -> tuple[str, bool]:
    """A doc without its opening editing note, and whether any comment past
    that note was dropped. The comments hold notes to the doc's editor."""
    text = re.sub(r"\A<!--.*?-->\s*", "", text, flags=re.S)
    stripped = uncommented(text)
    return stripped, stripped != text


def interface_path(src: Path) -> Path:
    """The interface file beside a lib source: the `.md` of the same stem."""
    return src.with_suffix(".md")


def render(docs: Path = DOCS_DIR, lib: Path = LIB_SRC,
           lib_index: bool = False) -> str:
    """The handbook: the docs and the lib's files, each under a heading naming
    its file. The lib renders as its interface, or under `lib_index` as an
    index pointing at the interface file beside each source. Under `lib_index`
    the docs in `HEADING_INDEX` render as a heading index."""
    parts: list[str] = []
    for name in DOCS:
        rel = f"docs/wf-solver/{name}"
        text, titles = drop_deferred((docs / name).read_text())
        text, dropped = strip_comments(text)
        notes: list[str] = []
        if dropped:
            notes.append(NOTES_DROPPED.format(rel=rel))
        notes += [SECTION_DEFERRED.format(title=t, rel=rel) for t in titles]
        note = "".join(f"\n\n{n}" for n in notes)
        if name in INDEX:
            index = entry_index(text, rel)
        elif lib_index and name in HEADING_INDEX:
            index = heading_index(text, rel)
        else:
            index = None
        if index is None:
            parts.append(f"\n---\n\n# {rel}{note}\n\n{text}")
        else:
            parts.append(f"\n---\n\n# {rel} — index{note}\n\n{index}")
    for i, (path, text) in enumerate(lib_sources(lib)):
        rel = Path("programs") / path.relative_to(lib.parent)
        if lib_index:
            note = f"\n\n{INTERFACE_NOTE}" if i == 0 else ""
            parts.append(f"\n---\n\n# {rel} — index{note}\n\n{lib_entries(text)}")
        else:
            parts.append(f"\n---\n\n# {rel}\n\n{lib_doc(text)}")
    return HEADER + "".join(parts)


def agent_prompt(handbook: str) -> str:
    """The handbook agent's system prompt over a rendering of the handbook."""
    return ROLE_NOTE + handbook


def agent_definition(handbook: str, meta: dict[str, str] = AGENT_META) -> str:
    """A handbook agent's definition file: `meta` as frontmatter, then the
    prompt."""
    front = "\n".join(f"{k}: {v}" for k, v in meta.items())
    return f"---\n{front}\n---\n{agent_prompt(handbook)}"


def expanded_agent_path(path: Path = AGENT_PATH) -> Path:
    """The expanded agent's file, beside the handbook agent's file."""
    return path.with_name(f"{path.stem}-expanded{path.suffix}")


def _write_whole(path: Path, text: str) -> Path:
    """Write a generated file, whole: a reader that opens it while the write
    is in progress reads the old file or the new one. A file that already
    holds the text is left alone."""
    if path.exists() and path.read_text() == text:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}-{threading.get_ident()}.tmp")
    try:
        tmp.write_text(text)
        tmp.replace(path)
    finally:
        tmp.unlink(missing_ok=True)
    return path


GENERATED_LINE = "<!-- Generated from {name} by scripts/context.py. -->\n\n"


def write_interfaces(lib: Path = LIB_SRC) -> list[Path]:
    """Write the interface file beside each of the lib's sources, each under
    a line saying it's generated, and return the paths."""
    return [_write_whole(interface_path(path),
                         GENERATED_LINE.format(name=path.name) + lib_doc(text))
            for path, text in lib_sources(lib)]


def write_agent(path: Path = AGENT_PATH, docs: Path = DOCS_DIR, lib: Path = LIB_SRC) -> Path:
    """Write both handbook agent definitions and the lib's interface files,
    and return the handbook agent's path. `path` holds the handbook agent;
    `expanded_agent_path(path)` holds the expanded agent."""
    write_interfaces(lib)
    _write_whole(expanded_agent_path(path),
                 agent_definition(render(docs, lib), EXPANDED_AGENT_META))
    return _write_whole(path, agent_definition(render(docs, lib, lib_index=True)))


# The files every codex session on the repo reads, in the desktop app or the
# CLI: the handbook and the project CLAUDE.md as the project's AGENTS.md, and
# the user's own style, `docs/codex-style.md`, as the developer instructions
# in the project config. Neither is tracked, and the style file is the
# user's to keep.
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


def write_codex(root: Path = REPO_ROOT, docs: Path = DOCS_DIR, lib: Path = LIB_SRC) -> list[Path]:
    """Write the codex files under `root` and return their paths."""
    claude_md = (root / "CLAUDE.md").read_text()
    style_path = root / CODEX_STYLE
    style = style_path.read_text() if style_path.exists() else None
    return [_write_whole(root / "AGENTS.md",
                         render(docs, lib) + "\n---\n\n# CLAUDE.md\n\n" + claude_md),
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
