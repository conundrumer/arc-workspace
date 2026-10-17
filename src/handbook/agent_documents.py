"""The agent documents under `prompts/agents/` as the contexts read them,
and the definition each one's front matter gives."""

from __future__ import annotations

from pathlib import Path

import controlled_markdown as nm
from engine import checkout
from handbook.paths import DOCUMENTS_ROOT, document


def agent_dir(root: Path = DOCUMENTS_ROOT) -> Path:
    """`prompts/agents/` under the documents root `root`."""
    return document(checkout.prompts(), root) / "agents"


AGENT_DIR = agent_dir()


def agent_doc(name: str, agents: Path = AGENT_DIR) -> Path:
    """The agent document of the agent `name` under `agents`."""
    return agents / f"{name}.md"


def agent_document(name: str, agents: Path = AGENT_DIR) -> nm.Node:
    """One agent document, parsed."""
    return nm.Registry(DOCUMENTS_ROOT).load(agent_doc(name, agents))


def front_fields(document: nm.Node) -> dict[str, tuple[int, str]]:
    """Each key of a document's front matter, with the line of the front
    matter that gives it and its value as written, quotes and all."""
    out: dict[str, tuple[int, str]] = {}
    for n, line in enumerate(document.front.split("\n"), 1):
        if ": " in line and not line.startswith("---"):
            key, value = line.split(": ", 1)
            out[key.strip()] = (n, value.strip())
    return out


def agent_meta(name: str, agents: Path = AGENT_DIR) -> dict[str, str]:
    """An agent's definition, as its document's front matter gives it."""
    return {key: value.strip('"') for key, (_, value)
            in front_fields(agent_document(name, agents)).items()}
