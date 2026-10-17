"""Where a role's brief comes from: the scripts that build it, and the
documents that tell a session to spawn the role."""

from __future__ import annotations

import re

from controlled_markdown import mctx
from engine import checkout
from handbook.context import DOCS_DIR, WORKFLOW_DIR
from handbook.paths import document, repo_label

CONSOLE_DIR = document(checkout.console())

# The scripts that build a role's brief. A file here that states the role on a
# line about roles spawns that role.
SPAWN_GLOBS = ((WORKFLOW_DIR, "*.js"), (document(checkout.scripts()), "*.py"),
               (CONSOLE_DIR, "*.py"), (CONSOLE_DIR / "solver_console", "*.py"))
# The documents that tell a session to spawn a role. A session that reads one
# of them briefs the role itself.
SPAWN_DOC_GLOBS = ((DOCS_DIR, "*.md"),
                   (document(checkout.prompts()), "**/*.md"))


def _spawners(name: str) -> list[str]:
    """The scripts that build the role's brief: the ones stating the role on a
    line that is about roles."""
    out = []
    for directory, pattern in SPAWN_GLOBS:
        for path in sorted(directory.glob(pattern)):
            for line in path.read_text().splitlines():
                if role_columns(line, name):
                    out.append(repo_label(path))
                    break
    return out


def word_at(word: str, line: str) -> int | None:
    """The column of the first whole-word occurrence of `word` on the
    line; None where it does not occur."""
    m = re.search(rf"\b{re.escape(word)}\b", line)
    return None if m is None else m.start()


def role_columns(line: str, stem: str) -> list[int]:
    """Where a script's line refers to the role `stem`: as `roles.<stem>`,
    or as the quoted stem on a line that is about roles; the column of
    each."""
    out: list[int] = []
    if (at := word_at(f"roles.{stem}", line)) is not None:
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
    return mctx("Brief: written by the session that spawns it.")
