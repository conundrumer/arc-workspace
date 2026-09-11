"""The reference context a solver session reads, projected down to what the
procedure uses.

`lib.dl` renders as signatures, and the catalog docs render as one line per
entry. The other docs pass through without their editor notes, their `+` lines,
and their deferred sections. Each rendering names the file that holds the
rest, and derives from the live file, so no copy can go stale.
"""

from __future__ import annotations

import os
import re
import threading
import time
from functools import lru_cache
from pathlib import Path

from dl.dlparse import (Comp, Decl, Define, Functor, Init, Item, Rule,
                        TypeDecl, parse)
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

LIB_PREAMBLE = """\
// Signatures only: rule bodies are dropped, and the facts of a top-level
// lookup relation stand described by its comment. Inside a component, a
// `.decl` marked `// input` is one the solver populates; the rest derive.
// Names with a leading underscore are comp-internal and omitted here.
// Read programs/lib.dl for a body.

"""


@lru_cache(maxsize=2)
def lib_signatures(text: str) -> str:
    """lib.dl as its interface: the declarations and the structure around
    them, with the bodies that derive from them dropped.

    `LIB_PREAMBLE` states the conventions the rendering follows, and opens
    the result.
    """
    program = parse(text)
    lines = text.splitlines()
    keep: set[int] = set()
    hidden: set[int] = set()       # underscore-named internals
    stmt_lines: set[int] = set()   # lines of rules and facts
    decls: list[Decl] = []
    comps: list[tuple[int, int]] = []   # the line range of each kept comp

    def walk(items: list[Item], in_comp: bool) -> None:
        for it in items:
            if isinstance(it, (Define, Functor, TypeDecl, Init)):
                name = (it.name if isinstance(it, TypeDecl)
                        else it.inst if isinstance(it, Init) else "")
                if name.startswith("_") or isinstance(it, Functor):
                    hidden.add(it.line)
                    continue
                keep.add(it.line)
            elif isinstance(it, Decl):
                if it.name.startswith("_"):
                    hidden.update(range(it.line, it.end_line + 1))
                    continue
                keep.update(range(it.line, it.end_line + 1))
                decls.append(it)
            elif isinstance(it, Comp):
                if it.name.startswith("_"):
                    hidden.update(range(it.line, it.end_line + 1))
                    continue
                keep.add(it.line)
                keep.add(it.end_line)
                comps.append((it.line, it.end_line))
                walk(it.items, True)
            elif isinstance(it, Rule):
                stmt_lines.update(range(it.line, it.end_line + 1))
                if in_comp and it.body is None:
                    keep.update(range(it.line, it.end_line + 1))
    walk(program.items, False)
    keep.update(c.line for c in program.comments if c.own_line)

    comment_lines = {c.line for c in program.comments if c.own_line}
    for ln in sorted(hidden):
        probe = ln - 1
        while probe in comment_lines and probe not in hidden:
            hidden.add(probe)
            probe -= 1
    keep -= hidden

    inputs: set[int] = set()   # decl start lines to mark // input
    for decl in decls:
        probe = decl.end_line + 1
        derived = False
        while probe <= len(lines):
            if probe in stmt_lines:
                derived = True
                break
            if not lines[probe - 1].strip() or probe in keep:
                break
            probe += 1
        if not derived:
            inputs.add(decl.line)

    # A comment inside a comp documents the line under it. Where that line
    # is dropped, the comment documents a body the projection drops, so it
    # goes too. Descending order takes a whole block out with its subject.
    interior = {ln for start, end in comps for ln in range(start + 1, end)}
    closing = {end for _, end in comps}
    for ln in sorted(comment_lines & interior & keep, reverse=True):
        if ln + 1 not in keep or ln + 1 in closing:
            keep.discard(ln)

    out: list[str] = []
    for i, line in enumerate(lines, start=1):
        if not line.strip():
            out.append(line)
        elif i in keep:
            mark = "  // input" if i in inputs and not line.endswith("// input") else ""
            out.append(line + mark)
    return LIB_PREAMBLE + re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip() + "\n"


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
    """The handbook: the docs and lib.dl, each under a heading naming its file."""
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
    parts.append("\n---\n\n# programs/lib.dl — signatures\n\n"
                 f"```\n{lib_signatures(lib.read_text())}```\n")
    return "# Handbook\n\nThe solver docs and lib.dl as a session reads them.\n" + "".join(parts)


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
