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

import json
import os
import re
import threading
import time
from functools import lru_cache
from pathlib import Path

import controlled_markdown as nm
from controlled_markdown import mctx
from dl.dlparse import Comp, Decl, Define, Include, Init, Item, Program, Rule, TypeDecl, parse
from dl.paths import PROGRAMS_DIR, REPO_ROOT

# The handbook's own files. Nothing here reads them as a directory: the
# composition document names each one, and the registry reads it from there.
DOCS_DIR = REPO_ROOT / "docs" / "handbook"
ROLE_DIR = REPO_ROOT / "prompts" / "roles"
# The doc that tells an editor where each section lives. It is not rendered.
EDITING_DOC = "editing.md"
LIB_SRC = PROGRAMS_DIR / "lib.dl"

# The agent documents, one per handbook agent: front matter holding the
# agent's definition, a `lib` attribute saying how the lib renders, and an
# `include` of the composition document. An agent runs a role under
# prompts/roles/ with the rendered document as its system prompt. The files
# under `.claude/agents/` are generated at each entry point and not tracked. A
# role's document names its agent in an `agent` attribute. A role with no such
# attribute runs as the handbook agent.
AGENT_DIR = REPO_ROOT / "prompts" / "agents"
# The session's own entry document: the handbook, and the passes it runs.
SESSION_DOC = REPO_ROOT / "prompts" / "session.md"
# The codex session's entry document, composed the same way.
CODEX_DOC = REPO_ROOT / "prompts" / "codex.md"
AGENT_PATH = REPO_ROOT / ".claude" / "agents" / "handbook.md"
AGENT_NAMES = ("handbook", "handbook-expanded")


APPENDIX = mctx("the system-prompt appendix")
"""What the console worker's first section is called."""


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


def interface_path(src: Path) -> Path:
    """The interface file beside a lib source: the `.md` of the same stem."""
    return src.with_suffix(".md")


def lib_part(lib: Path = LIB_SRC, kind: str = "interface") -> str:
    """The lib's files, each under a heading naming its file: as each file's
    interface, or as an index pointing at the interface file beside each
    source."""
    parts = []
    for path, text in lib_sources(lib):
        rel = Path("programs") / path.relative_to(lib.parent)
        if kind == "index":
            parts.append(f"\n---\n\n## {rel} — index\n\n{lib_entries(text)}")
        else:
            parts.append(f"\n---\n\n## {rel}\n\n{lib_doc(text)}")
    return "".join(parts)


def agent_document(name: str, agents: Path = AGENT_DIR) -> nm.Node:
    """One agent document, parsed."""
    return nm.Registry(REPO_ROOT).load(agents / f"{name}.md")


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
    registry = nm.Registry(REPO_ROOT)
    document = registry.load(agents / f"{name}.md")
    return (nm.render(document, registry)
            + lib_part(lib, (document.attr("lib") or "interface").strip()))


def entry_text(doc: Path, lib: Path = LIB_SRC) -> str:
    """One entry document as its reader gets it: the document rendered, then
    the lib as the document's `lib` attribute says."""
    registry = nm.Registry(REPO_ROOT)
    document = registry.load(doc)
    return (nm.render(document, registry)
            + lib_part(lib, (document.attr("lib") or "interface").strip()))


def session_text(doc: Path = SESSION_DOC, lib: Path = LIB_SRC) -> str:
    """What a session at a terminal reads: the handbook with its passes, then
    the lib."""
    return entry_text(doc, lib)


def _doc_path(name: str, docs: Path = DOCS_DIR) -> Path:
    """The handbook doc a reader names: the slug of its title, as a render
    shows it, its file stem, or the link form a document carries,
    `docs/handbook/<stem>.md`."""
    if name.endswith(".md"):
        name = name[:-3]
    name = name.rsplit("/", 1)[-1]
    want = nm.slug(name)
    for path in sorted(docs.glob("*.md")):
        if path.stem == want or path.stem == name:
            return path
        title = nm.parse(path.read_text(), path.name).children
        heads = [c for c in title if c.kind == nm.HEADING]
        if heads and nm.slug(heads[0].text) == want:
            return path
    raise SystemExit(f"no handbook doc named `{name}`")


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
        if len(run) > 1 and isinstance(it, Define):
            body = [" ".join(d.name for d in run)]
        elif len(run) > 1:
            body = [f".type {', '.join(t.name for t in run)} {it.rhs}"]
        elif isinstance(it, Comp):
            body = _comp_block(it, lines, docs)
        else:
            end = it.end_line if isinstance(it, Decl) else it.line
            body = [lines[ln - 1].rstrip() for ln in range(it.line, end + 1)]
        code = "```\n" + "\n".join(body) + "\n```"
        return "\n\n".join(p for p in (f"# {name}", prose, code) if p) + "\n"
    raise SystemExit(f"no component `{name}` in `{src.relative_to(REPO_ROOT)}`")


def section_text(where: str, docs: Path = DOCS_DIR) -> str:
    """One section of a handbook doc in full, named `<doc>#<section>`, or one
    lib component's interface, named `programs/lib/<module>.dl#<Component>`.
    The doc is the link form a document carries, the title a render shows, or
    its file stem, and the section is the title a render shows, slugified, so
    a reader runs the command off the lines in front of them. A render leaves
    no line out, so the section arrives with the glosses and the drafts an
    edition excludes."""
    name, _, ident = where.partition("#")
    name, ident = name.strip(), ident.strip()
    if name.endswith(".dl"):
        src = REPO_ROOT / name
        if not src.exists():
            raise SystemExit(f"no lib source named `{name}`")
        return lib_component(src, ident)
    registry = nm.Registry(REPO_ROOT)
    document = registry.load(_doc_path(name, docs))
    node = registry.ids[document.source].get(nm.slug(ident))
    if node is None:
        raise SystemExit(
            f"no section `{ident}` in {registry.rel(document)}")
    body = nm.Node(nm.DOCUMENT, source=document.source)
    body.children = [node]
    return nm.render(body, registry)


def workflow_bundle(name: str, roles: Path = ROLE_DIR) -> dict:
    """What a workflow run needs: the text of every role under `roles`, since
    a run picks the ones it reaches. The script holds its own briefs and its
    own return schemas, each an `mctx` literal the check reads where it
    stands. A name no script under `WORKFLOW_DIR` carries is an error."""
    names = workflow_names()
    if name not in names:
        raise SystemExit(f"no workflow named `{name}`; the workflows are "
                         + ", ".join(names))
    return {
        "roles": {r: role_text(r, roles) for r in _workflow_roles(name, roles)},
    }


def _workflow_roles(name: str, roles: Path) -> list[str]:
    """Every role under `roles`, since a run picks the ones it reaches."""
    return sorted(p.stem for p in roles.glob("*.md"))


def role_body(name: str, roles: Path = ROLE_DIR) -> str:
    """One role document under `roles`, as the agent running it reads it: the
    text the agent's prompt opens with, and nothing above."""
    registry = nm.Registry(REPO_ROOT)
    return nm.role(registry.load(roles / f"{name}.md"), registry)[1]


def role_text(name: str, roles: Path = ROLE_DIR) -> str:
    """One role document under `roles`, as the session that spawns the role
    reads it: `Agent: <name>` on the first line, then the text the agent's
    prompt opens with."""
    registry = nm.Registry(REPO_ROOT)
    agent, text = nm.role(registry.load(roles / f"{name}.md"), registry)
    return f"Agent: {agent}\n\n{text}"


def agent_prompt(handbook: str) -> str:
    """The handbook agent's system prompt over a rendering of the handbook."""
    return mctx("Your prompt opens with your role, then its brief. Follow "
                "the role.") + "\n\n" + handbook


def agent_definition(document: nm.Node, handbook: str) -> str:
    """A handbook agent's definition file: the agent document's front matter
    as it stands, then the prompt."""
    return f"{document.front}\n{agent_prompt(handbook)}"


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


def write_interfaces(lib: Path = LIB_SRC) -> list[Path]:
    """Write the interface file beside each of the lib's sources, each under
    a line saying it's generated, and return the paths."""
    return [_write_whole(
        interface_path(path),
        mctx("<!-- Generated from {name} by scripts/context.py. -->").format(
            name=path.name) + "\n\n" + lib_doc(text))
        for path, text in lib_sources(lib)]


def write_agent(path: Path = AGENT_PATH, lib: Path = LIB_SRC,
                agents: Path = AGENT_DIR) -> Path:
    """Write both handbook agent definitions and the lib's interface files,
    and return the handbook agent's path. `path` holds the handbook agent;
    `expanded_agent_path(path)` holds the expanded agent."""
    write_interfaces(lib)
    for name in AGENT_NAMES:
        out = path if name == AGENT_NAMES[0] else expanded_agent_path(path)
        _write_whole(out, agent_definition(agent_document(name, agents),
                                           render(name, lib, agents)))
    return path


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
SAMPLE_REFERENCE = "// reference solver"
SAMPLE_REPORTS = "<prior reports>"
SAMPLE_ENTRY = "docs/wf-solver/proposals/<entry>.md"
SAMPLE_SCOPE = "every solver"
SAMPLE_SCRATCH = ".scratch/survey/<run>"

# The session's own skill, which a session at a terminal reads beside the
# handbook.
SESSION_SKILL = REPO_ROOT / ".claude" / "skills" / "session" / "SKILL.md"
CONSOLE_DIR = REPO_ROOT / "tools" / "console"
WORKFLOW_DIR = REPO_ROOT / ".claude" / "workflows"
# The scripts that build a role's brief. A file here that names the role on a
# line about roles spawns that role.
SPAWN_GLOBS = (".claude/workflows/*.js", "scripts/*.py",
               "tools/console/*.py", "tools/console/solver_console/*.py")
# The documents that tell a session to spawn a role. A session that reads one
# of them briefs the role itself.
SPAWN_DOC_GLOBS = ("docs/handbook/*.md", "prompts/**/*.md")


def _section(what: str, text: str) -> str:
    """One marked section: the marker line, a blank line, and the text."""
    return MARKER.format(what=what) + "\n" + text.rstrip("\n") + "\n"


def _console():
    """The console's prompt builders and its stage chain. The console reads
    this module, so the import stands here."""
    import sys
    if str(CONSOLE_DIR) not in sys.path:
        sys.path.insert(0, str(CONSOLE_DIR))
    from solver_console import prompts, store
    return prompts, store


def _body(text: str) -> str:
    """A file's text from its first heading, so a front matter block that
    reaches no agent is left out."""
    head = re.search(r"^# ", text, re.M)
    return text[head.start():] if head else text


def session_context() -> str:
    """What a session at a terminal reads: the session skill the user invokes,
    then the session document with the lib, which the skill's first line sends
    the session to read. The lib's interface files are written first, the way
    the no-argument form writes them, so the lib index names the files as they
    stand."""
    write_interfaces()
    return "\n".join([
        _section(str(SESSION_SKILL.relative_to(REPO_ROOT)),
                 _body(SESSION_SKILL.read_text())),
        _section(str(SESSION_DOC.relative_to(REPO_ROOT)), session_text()),
    ])


def codex_context() -> str:
    """What a codex session on the repo reads: AGENTS.md, as `--write`
    renders it."""
    return _section("AGENTS.md", entry_text(CODEX_DOC))


def agent_context(name: str) -> str:
    """One handbook agent's system prompt, as `--write` writes it. The front
    matter the harness reads stands above it in the file, and the agent
    receives what follows."""
    if name not in AGENT_NAMES:
        raise SystemExit(f"no agent named `{name}`; the agents are "
                         + ", ".join(AGENT_NAMES))
    return _section(f".claude/agents/{name}.md", agent_prompt(render(name)))


def _role_agent(name: str, roles: Path = ROLE_DIR) -> str:
    """The agent a role runs on: its `agent` attribute, or the handbook
    agent."""
    registry = nm.Registry(REPO_ROOT)
    return nm.role(registry.load(roles / f"{name}.md"), registry)[0]


def _spawners(name: str) -> list[str]:
    """The scripts that build the role's brief: the ones naming the role on a
    line that is about roles."""
    quoted = re.compile(rf"""(['"]){re.escape(name)}\1""")
    attribute = re.compile(rf"\broles\.{re.escape(name)}\b")
    out = []
    for pattern in SPAWN_GLOBS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            for line in path.read_text().splitlines():
                if attribute.search(line) or (quoted.search(line)
                                              and "role" in line.lower()):
                    out.append(str(path.relative_to(REPO_ROOT)))
                    break
    return out


def _spawn_docs(name: str) -> list[str]:
    """The documents that tell a session to spawn the role."""
    said = re.compile(rf"(?i:spawn) the `{re.escape(name)}` role")
    out = []
    for pattern in SPAWN_DOC_GLOBS:
        for path in sorted(REPO_ROOT.glob(pattern)):
            if said.search(path.read_text()):
                out.append(str(path.relative_to(REPO_ROOT)))
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


def role_context(name: str, roles: Path = ROLE_DIR,
                 stage: str | None = None,
                 seen: set[str] | None = None,
                 brief: bool = True) -> str:
    """What an agent running the role reads: its agent's definition, its role
    text, then the line saying where its brief comes from. `stage` names the
    phase a workflow run reaches the role in, and the empty string says no
    phase of the script reaches it. `seen` holds the agents a caller has
    already printed, and an agent it holds takes a marker line in place of its
    definition. `brief` set to False leaves out the line about the brief, for
    a caller that names the source itself."""
    if not (roles / f"{name}.md").is_file():
        raise SystemExit(f"no role named `{name}`")
    agent = _role_agent(name, roles)
    path = f".claude/agents/{agent}.md"
    if seen is not None and agent in seen:
        head = MARKER.format(
            what=mctx("{path}, the definition printed above").format(path=path))
    else:
        head = agent_context(agent)
        if seen is not None:
            seen.add(agent)
    label = f"prompts/roles/{name}.md"
    if stage:
        label = mctx("{path}, in the {phase} phase").format(
            path=label, phase=stage)
    elif stage == "":
        label = mctx("{path}, in a phase this listing does not find").format(
            path=label)
    parts = [head, _section(label, role_body(name, roles))]
    if brief:
        parts.append(_section(mctx("the brief"), spawn_line(name)))
    return "\n".join(parts)


def console_stages() -> list[str]:
    """The stages of the chain a wave runs when it names none."""
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
                                    task=SAMPLE_TASK,
                                    reference=SAMPLE_REFERENCE)))
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
    `store.default_chain` gives, which is the chain a wave runs when it names
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
    agent = _role_agent("survey")
    return "\n".join([
        _section(APPENDIX,
                 prompts.append_text(index=agent == AGENT_NAMES[0])),
        _section("prompts/roles/survey.md", prompts.role_text("survey")),
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


def workflow_phases(name: str, roles: Path = ROLE_DIR,
                    workflows: Path = WORKFLOW_DIR) -> dict[str, str]:
    """Each role the workflow script names, in phase order, with the phase it
    runs in. A line inside an `agent(` call that carries a `phase:` option
    takes that phase, and any other line takes the phase of the nearest
    `phase()` statement above it. A line names a role by its stem, by a
    variable bound to `roles.<stem>`, or, inside such a call, by a list of
    stems or a function returning members of one. A role no phase reaches
    takes the empty string, and it follows the placed roles, at the line it
    first stands on."""
    path = workflows / f"{name}.js"
    if not path.is_file():
        raise SystemExit(f"no workflow named `{name}`")
    text = path.read_text()
    phases = _workflow_phases(text)
    stems = sorted(p.stem for p in roles.glob("*.md"))
    aliases = _role_aliases(text, set(stems))
    groups = _role_groups(text, set(stems))
    call_phases = _call_phases(text)
    running = ""
    found: dict[str, tuple[int, int, str]] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        bare = BARE_PHASE_RE.match(line)
        if bare:
            running = bare.group(1)
        option = PHASE_RE.search(line)
        title = option.group(1) if option else call_phases.get(number, running)
        title = title if title in phases else ""
        rank = phases.index(title) if title else len(phases)
        named: set[str] = set()
        for stem in stems:
            quoted = re.search(rf"""(['"]){re.escape(stem)}\1""", line)
            attribute = re.search(rf"\broles\.{re.escape(stem)}\b", line)
            if attribute or (quoted and "role" in line.lower()):
                named.add(stem)
        for variable, stem in aliases.items():
            if re.search(rf"\b{re.escape(variable)}\b", line):
                named.add(stem)
        if number in call_phases:
            for group, members in groups.items():
                if re.search(rf"\b{re.escape(group)}\b", line):
                    named.update(members)
        for stem in named:
            at = found.get(stem)
            if at is None or rank < at[0]:
                found[stem] = (rank, number, title)
    order = sorted(found, key=lambda s: found[s][:2])
    return {stem: found[stem][2] for stem in order}


def workflow_roles(name: str, roles: Path = ROLE_DIR,
                   workflows: Path = WORKFLOW_DIR) -> list[str]:
    """The roles the workflow script names, in phase order."""
    return list(workflow_phases(name, roles, workflows))


def workflow_roleless_phases(name: str, roles: Path = ROLE_DIR,
                             workflows: Path = WORKFLOW_DIR) -> list[str]:
    """The phases of the script's `meta.phases` that no role the roles listing
    places falls in, in `meta.phases` order."""
    path = workflows / f"{name}.js"
    if not path.is_file():
        raise SystemExit(f"no workflow named `{name}`")
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
    path = workflows / f"{name}.js"
    if not path.is_file():
        raise SystemExit(f"no workflow named `{name}`")
    script = f".claude/workflows/{name}.js"
    return "\n\n".join(f"{script}:{fragment.line}\n\n{fragment.text.rstrip()}"
                       for fragment in nm.fragments(path, script))


def workflow_context(name: str) -> str:
    """What each agent of a workflow run reads: the role context of every role
    the script names, in phase order, the phases no role runs in, then the
    line naming where the briefs are built and the briefs themselves."""
    script = f".claude/workflows/{name}.js"
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


# Each reader the `context` command knows, with the argument it takes and the
# values that argument takes.
CONTEXT_READERS = {
    "session": (None, lambda: []),
    "codex": (None, lambda: []),
    "agent": ("<name>", lambda: list(AGENT_NAMES)),
    "role": ("<name>", lambda: sorted(p.stem for p in ROLE_DIR.glob("*.md"))),
    "console": ("<stage>", console_stages),
    "survey": (None, lambda: []),
    "workflow": ("<name>", workflow_names),
}


def contexts_text() -> str:
    """Every reader the `context` command knows, one per line: its name, its
    argument form, and the values that argument takes."""
    out = []
    for name, (form, values) in CONTEXT_READERS.items():
        head = f"context {name}" + (f" {form}" if form else "")
        names = values()
        out.append(f"{head:<24}{', '.join(names)}".rstrip())
    return "\n".join(out) + "\n"


def context_text(reader: str, args: list[str]) -> str:
    """One reader's whole context, in the order it arrives."""
    if reader not in CONTEXT_READERS:
        raise SystemExit("no reader named "
                         f"`{reader}`\n{contexts_text()}".rstrip())
    form = CONTEXT_READERS[reader][0]
    if form and len(args) != 1:
        raise SystemExit(f"usage: context {reader} {form}")
    if not form and args:
        raise SystemExit(f"usage: context {reader}")
    if reader == "session":
        return session_context()
    if reader == "codex":
        return codex_context()
    if reader == "agent":
        return agent_context(args[0])
    if reader == "role":
        return role_context(args[0])
    if reader == "console":
        return console_context(args[0])
    if reader == "survey":
        return survey_context()
    return workflow_context(args[0])
