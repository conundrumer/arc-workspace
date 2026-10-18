"""The documents agents read, each with the text its budget bounds
(`handbook.budget`).

The documents are each `.md` file of `CLAUDE.md`, the handbook and
`prompts/agents/`. An agent's entry document whose lib form is `none`
bounds its agent's definition as `--write` writes it, the coordinator's
source bounds the coordinator's rendering, and a `<name>-next.md` that an
agent reads after its prompt bounds that rendering with no list its render
computes (`handbook.listings`): a list grows with the files it lists, and
that growth is intended. Each other document, an entry document that
renders the lib among them, bounds its own text without its attribute
lines, which no render shows: the lib grows with each declaration solver
work adds, and that growth is intended."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import controlled_markdown as nm
from engine import checkout
from handbook.agent_documents import AGENT_DIR, agent_doc, agent_document
from handbook.agents import (agent_names, agent_renderings, next_file,
                             next_name, next_readers, next_unlisted_text)
from handbook.budget import (Measured, Size, WithoutAttributes, WithoutLists,
                             size)
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


@dataclass(frozen=True)
class Bounded:
    """The text a document bounds, other than its own, and what it is."""

    text: str
    measured: Measured


def _whole(rendering: Rendering) -> Bounded:
    return Bounded(rendering.text, rendering.path)


def rendered_texts() -> dict[Path, Bounded]:
    """The rendering each document that bounds one bounds, by document."""
    texts = {COORDINATOR_DOC: _whole(coordinator_rendering())}
    for name, rendering in zip(agent_names(), agent_renderings()):
        if lib_form(agent_document(name)) is LibForm.NONE:
            texts[agent_doc(name)] = _whole(rendering)
    for name in next_readers():
        texts[agent_doc(next_name(name))] = Bounded(
            next_unlisted_text(name), WithoutLists(next_file(name)))
    return texts


def without_attributes(doc: Path) -> str:
    """The text of `doc` without its `+ name: value` lines."""
    text = doc.read_text()
    nodes = list(nm._walk(nm.parse(text, str(doc))))
    dropped = ({n.line for n in nodes if n.kind == nm.ATTRIBUTE}
               - {n.line for n in nodes if n.star})
    return "".join(line for num, line in enumerate(text.splitlines(keepends=True), start=1)
                   if num not in dropped)


def sizes() -> list[Size]:
    """The size of the text each document bounds, against its budget."""
    rendered = rendered_texts()
    return [size(doc, r.text, r.measured)
            if (r := rendered.get(doc)) is not None
            else size(doc, without_attributes(doc), WithoutAttributes(doc))
            for doc in budgeted_docs()]
