"""The reference context a solver session reads, projected down to what the
procedure uses: an entry document composed with the lib, the roles and the
workflows that run them, the handbook's sections, and the files a codex
session reads.

The lib renders as `handbook.lib` gives it. Each file's interface is also
written beside it, as the `.md` of the same stem, and `section_text` prints
one component's interface from the source.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Sequence
from pathlib import Path

import controlled_markdown as nm
from engine import checkout
from handbook.generated import (Regenerated, Rendering, regenerate,
                                write_generated, write_whole_text)
from handbook.lib import (LIB_SRC, LibForm, interface_renderings,
                          lib_component, lib_form, lib_part, lib_sources)
from handbook.paths import DOCUMENTS_ROOT, REPO_ROOT, document, repo_label
from handbook.wrappers import wrappers_text

# The handbook's own files. Nothing here reads them as a directory: the
# composition document lists each one, and the registry reads it from there.
DOCS_DIR = document(checkout.handbook())


def role_dir(root: Path = DOCUMENTS_ROOT) -> Path:
    """`prompts/roles/` under the documents root `root`."""
    return document(checkout.prompts(), root) / "roles"


ROLE_DIR = role_dir()


# The session's own entry document: the handbook, and the passes it runs.
SESSION_DOC = document(checkout.prompts()) / "session.md"
# The codex session's entry document, composed the same way.
CODEX_DOC = document(checkout.prompts()) / "codex.md"


def role_file(name: str, roles: Path = ROLE_DIR) -> Path:
    """The role document of the role `name` under `roles`."""
    return roles / f"{name}.md"


def entry_text(doc: Path, lib: Path = LIB_SRC) -> str:
    """One entry document as its reader gets it: the document rendered, then
    the lib as the document's `lib` attribute says."""
    return composed(doc, lib)[0]


def composed(doc: Path, lib: Path) -> tuple[str, nm.Registry, LibForm]:
    """`entry_text` of `doc`, the registry that holds each document the
    render read, and the form the lib renders in after it."""
    registry = nm.Registry(DOCUMENTS_ROOT)
    document = registry.load(doc)
    form = lib_form(document)
    after = lib_part(lib, form)
    return nm.render(document, registry, after=after) + after, registry, form


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
            raise no_item_named("lib source", "lib sources", name,
                                [repo_label(p) for p, _ in lib_sources()])
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


def first_heading(document: nm.Node) -> nm.Node | None:
    """A document's first heading; None where it has none."""
    return next((c for c in document.children if c.kind == nm.HEADING), None)


def _title(document: nm.Node) -> str | None:
    """A document's title, its first heading's text (`first_heading`);
    None where it has no heading."""
    head = first_heading(document)
    return None if head is None else head.text


def workflow_dir(root: Path = DOCUMENTS_ROOT) -> Path:
    """`.claude/workflows/` under the documents root `root`."""
    return document(checkout.workflows(), root)


WORKFLOW_DIR = workflow_dir()


def workflow_names(workflows: Path = WORKFLOW_DIR) -> list[str]:
    """The workflow scripts, by name."""
    return sorted(p.stem for p in workflows.glob("*.js"))


def no_item_named(kind: str, kinds: str, name: str,
                  names: list[str]) -> SystemExit:
    return SystemExit(f"no {kind} named `{name}`; the {kinds} are "
                      + ", ".join(names))


def workflow_file(name: str, workflows: Path = WORKFLOW_DIR) -> Path:
    """The script of the workflow `name`; an error where none stands."""
    path = workflows / f"{name}.js"
    if not path.is_file():
        raise no_item_named("workflow", "workflows", name,
                            workflow_names(workflows))
    return path


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


HANDBOOK_AGENT = "handbook"
"""The agent a role with no `agent` attribute runs on."""


def agent_and_text(document: nm.Node, registry: nm.Registry) -> tuple[str, str]:
    """A role document as the agent it runs on and its text."""
    return (document.attr("agent") or HANDBOOK_AGENT,
            nm.render(document, registry))


def role_document(name: str, roles: Path = ROLE_DIR) -> tuple[str, str]:
    """One role document under `roles`: the agent it runs on, and the text
    the agent's prompt opens with, as the agent running it reads it, with
    nothing above."""
    if not role_file(name, roles).is_file():
        raise no_item_named("role", "roles", name, role_stems(roles))
    registry = nm.Registry(DOCUMENTS_ROOT)
    return agent_and_text(registry.load(role_file(name, roles)), registry)


def role_text(name: str, roles: Path = ROLE_DIR) -> str:
    """One role document under `roles`, as the session that spawns the role
    reads it: `Agent: <name>` on the first line, then the text the agent's
    prompt opens with."""
    agent, text = role_document(name, roles)
    return f"Agent: {agent}\n\n{text}"


WRAPPERS_PATH = document(REPO_ROOT / "src" / "lib_components" / "components.py")
"""The Python module of the lib's component wrappers, at its place in the
checkout under the documents root, the root `LIB_SRC` is read under."""


def write_lib_output(renderings: Sequence[Rendering] = (),
                     lib: Path = LIB_SRC, wrappers: Path = WRAPPERS_PATH,
                     stale: bool = False) -> tuple[list[Path], Regenerated]:
    """Write the lib's generated output with `renderings`. The module of the
    lib's wrappers is tracked, and so is written outside the manifest."""
    interfaces = interface_renderings(lib)
    written = [*interfaces, *renderings]
    if stale:
        done = regenerate(written)
    else:
        write_generated(written)
        done = Regenerated([], [])
    module = write_whole_text(wrappers, wrappers_text(lib))
    return ([*(r.path for r in interfaces), module,
             *(r.path for r in renderings)], done)


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


def codex_renderings(root: Path = REPO_ROOT, lib: Path = LIB_SRC,
                     doc: Path = CODEX_DOC) -> list[Rendering]:
    """The codex files under `root`."""
    style_path = root / CODEX_STYLE
    style = style_path.read_text() if style_path.exists() else None
    return [Rendering(root / "AGENTS.md", entry_text(doc, lib)),
            Rendering(root / CODEX_CONFIG, codex_config(style))]


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
