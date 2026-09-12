"""The reference context a solver session reads, projected down to what the
procedure uses.

The lib renders as documentation: each file's `//!` and `///` comments as
prose, and the declarations they document in code blocks, without the rule
bodies. The catalog docs render as one line per entry. The other docs pass
through without their editor notes, their `+` lines, and their deferred
sections. Each rendering names the file that holds the rest, and derives
from the live file, so no copy can go stale.
"""

from __future__ import annotations

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

# The one agent definition, generated from the handbook: an agent runs a
# role under .claude/roles/ with the handbook as its system prompt. The file
# is regenerated at each entry point and not tracked.
AGENT_PATH = REPO_ROOT / ".claude" / "agents" / "handbook.md"
AGENT_META = {
    "name": "handbook",
    "description": "Works the role its prompt opens with, one of .claude/roles/, "
                   "with the handbook as its system prompt.",
    "model": "opus",
    "effort": "high",
    "tools": "Read, Grep, Glob, Bash, Edit, Write",
}
ROLE_NOTE = "Your prompt opens with your role, then its brief. Follow the role.\n\n"

# The docs the procedure reads, in reading order: the theory, then its form,
# then what the corpus made of it.
DOCS = ("procedure.md", "principles.md", "style.md", "patterns.md", "keywords.md",
        "lib-protocol.md", "former-names.md")
# Catalog docs: entries are independent and a session uses few, so the context
# carries the index and the session reads the entry it needs.
INDEX = {"patterns.md"}


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


def _hidden(it: Item) -> bool:
    """A `_`-prefixed item is private to the lib."""
    name = it.inst if isinstance(it, Init) else getattr(it, "name", "")
    return name.startswith("_")


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
        if prev is not None and (any(cur) or any(prev) or cur != prev):
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

    items = [it for it in program.items if not isinstance(it, (Include, Rule))]
    i = 0
    while i < len(items):
        it = items[i]
        if _hidden(it) or not isinstance(it, DOCUMENTED):
            i += 1
            continue
        block = docs.get(it.line - 1)
        if block is not None:
            emit_prose(_prose(lines[block[0] - 1:block[1]], ITEM_DOC))
        # A run of undocumented siblings on consecutive lines folds:
        # defines to their names, subtypes of one base to one line.
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
        if len(run) > 1:
            if isinstance(it, Define):
                emit_code([" ".join(d.name for d in run)])
            else:
                emit_code([f".type {', '.join(t.name for t in run)} {it.rhs}"])
            i = j
            continue
        if isinstance(it, Comp):
            emit_code(_comp_block(it, lines, docs))
        else:
            end = it.end_line if isinstance(it, Decl) else it.line
            emit_code([lines[ln - 1].rstrip() for ln in range(it.line, end + 1)])
        i += 1
    # A block over no item renders where it stands.
    for end, (start, _) in sorted(docs.items()):
        if end not in attached:
            emit_prose(_prose(lines[start - 1:end], ITEM_DOC))
    emit_prose("")
    return "\n\n".join(p for p in parts if p) + "\n"


def gist(para: str) -> str:
    """An entry's first sentence — the catalog docs' convention is that it
    stands alone under its title."""
    return re.split(r"(?<=\.)\s+(?=[A-Z`\"(])", para, maxsplit=1)[0]


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


def drop_omitted(text: str) -> str:
    """A doc without its `+` list items. A `+` line is source-only: it
    reads as a bullet in a viewer and holds what a session doesn't read,
    such as a rule's formal statement."""
    text = re.sub(r"^[ \t]*\+ .*\n?", "", text, flags=re.M)
    return re.sub(r"\n{3,}", "\n\n", text)


def strip_comments(text: str) -> tuple[str, bool]:
    """A doc without its HTML comments, and whether any sat past the opening
    editing note. They hold notes to the doc's editor, and a solver session
    doesn't edit the doc."""
    text = re.sub(r"\A<!--.*?-->\s*", "", text, flags=re.S)
    stripped = re.sub(r" ?<!--.*?-->", "", text, flags=re.S)
    return stripped, stripped != text


def render(docs: Path = DOCS_DIR, lib: Path = LIB_SRC) -> str:
    """The handbook: the docs and the lib's files, each under a heading
    naming its file."""
    parts: list[str] = []
    for name in DOCS:
        rel = f"docs/wf-solver/{name}"
        text, titles = drop_deferred((docs / name).read_text())
        text, dropped = strip_comments(drop_omitted(text))
        notes = [SECTION_DEFERRED.format(title=t, rel=rel) for t in titles]
        if dropped:
            notes.insert(0, NOTES_DROPPED.format(rel=rel))
        note = "".join(f"\n\n{n}" for n in notes)
        if name in INDEX:
            parts.append(f"\n---\n\n# {rel} — index{note}\n\n{entry_index(text, rel)}")
        else:
            parts.append(f"\n---\n\n# {rel}{note}\n\n{text}")
    for path, text in lib_sources(lib):
        rel = Path("programs") / path.relative_to(lib.parent)
        parts.append(f"\n---\n\n# {rel}\n\n{lib_doc(text)}")
    return "# Handbook\n\nThe solver docs and the lib as a session reads them.\n" + "".join(parts)


def agent_prompt(handbook: str) -> str:
    """The handbook agent's system prompt over a rendering of the handbook."""
    return ROLE_NOTE + handbook


def agent_definition(handbook: str) -> str:
    """The handbook agent's definition file: AGENT_META as frontmatter, then
    the prompt."""
    front = "\n".join(f"{k}: {v}" for k, v in AGENT_META.items())
    return f"---\n{front}\n---\n{agent_prompt(handbook)}"


def write_agent(path: Path = AGENT_PATH, docs: Path = DOCS_DIR, lib: Path = LIB_SRC,
                handbook: str | None = None) -> Path:
    """Write the handbook agent's definition, whole: a session that starts
    while the write is in progress reads the old file or the new one. A file
    that already holds the definition is left alone. `handbook` is the
    rendered handbook, for a caller that has it.
    """
    text = agent_definition(render(docs, lib) if handbook is None else handbook)
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
