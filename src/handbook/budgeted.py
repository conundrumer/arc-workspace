"""The documents agents read, each with the text its budget bounds
(`handbook.budget`).

The documents are each `.md` file of `CLAUDE.md`, the handbook and
`prompts/agents/`. An agent's entry document whose lib form is `none`
bounds its agent's definition as `--write` writes it, the coordinator's
source bounds the coordinator's rendering, and a `<name>-next.md` that an
agent reads after its prompt bounds that rendering. Each other document,
an entry document that renders the lib among them, bounds its own text: the
lib grows with each declaration solver work adds, and that growth is
intended."""

from __future__ import annotations

from pathlib import Path

from engine import checkout
from handbook.agents import (AGENT_DIR, agent_doc, agent_document,
                             agent_names, agent_renderings, next_name,
                             next_readers, next_renderings)
from handbook.budget import Size, size
from handbook.context import DOCS_DIR
from handbook.coordinator_document import (COORDINATOR_DOC,
                                           coordinator_rendering)
from handbook.generated import Rendering
from handbook.lib import LibForm, lib_form
from handbook.paths import document


def budgeted_docs() -> list[Path]:
    """Each document a budget bounds, in path order."""
    return [document(checkout.ROOT / "CLAUDE.md"),
            *sorted(DOCS_DIR.rglob("*.md")), *sorted(AGENT_DIR.rglob("*.md"))]


def rendered_texts() -> dict[Path, Rendering]:
    """The rendering each document that bounds one bounds, by document."""
    texts = {COORDINATOR_DOC: coordinator_rendering()}
    for name, rendering in zip(agent_names(), agent_renderings()):
        if lib_form(agent_document(name)) is LibForm.NONE:
            texts[agent_doc(name)] = rendering
    for name, rendering in zip(next_readers(), next_renderings()):
        texts[agent_doc(next_name(name))] = rendering
    return texts


def sizes() -> list[Size]:
    """The size of the text each document bounds, against its budget."""
    rendered = rendered_texts()
    return [size(doc, r.text, r.path) if (r := rendered.get(doc)) is not None
            else size(doc, doc.read_text())
            for doc in budgeted_docs()]
