"""The agent documents and the agents' definitions rendered from them.

An agent document under `prompts/agents/` states what its agent reads, and
`write_agent` renders one per agent into `.claude/agents/`, front matter and
all. Read those documents for what each agent gets. Each one holds front
matter giving the agent's definition, a `lib` attribute saying how the lib
renders, and an `include` of the composition document. An agent
runs a role under prompts/roles/ with the rendered document as its system
prompt. A role's document states its agent in an `agent` attribute. A role
with no such attribute runs as the handbook agent. The files under
`.claude/agents/` are generated and listed in the manifest of
`handbook.generated`.
"""

from __future__ import annotations

import re
from pathlib import Path

import controlled_markdown as nm
from controlled_markdown import mctx
from engine import checkout
from handbook.context import (ROLE_DIR, WRAPPERS_PATH, composed, entry_text,
                              write_wrappers)
from handbook.generated import (Rendering, in_checkout, read_manifest,
                                write_generated)
from handbook.lib import (LIB_SRC, LibForm, interface_renderings,
                          lib_sources)
from handbook.paths import DOCUMENTS_ROOT, REPO_ROOT, document, repo_label


def agent_dir(root: Path = DOCUMENTS_ROOT) -> Path:
    """`prompts/agents/` under the documents root `root`."""
    return document(checkout.prompts(), root) / "agents"


AGENT_DIR = agent_dir()


AGENT_OUT = checkout.agents()
"""Where the agent definitions are written."""


def agent_file(name: str) -> Path:
    """The definition file of the agent `name`."""
    return AGENT_OUT / f"{name}.md"


def agent_doc(name: str, agents: Path = AGENT_DIR) -> Path:
    """The agent document of the agent `name` under `agents`."""
    return agents / f"{name}.md"


HANDBOOK_AGENT = "handbook"
"""The agent a role with no `agent` attribute runs on."""
AGENT_PATH = agent_file(HANDBOOK_AGENT)
AGENT_NAMES = (HANDBOOK_AGENT, "handbook-expanded")
# The steps the analyze agent reads after it writes the concept: a document
# under `AGENT_DIR` with no front matter, rendered to its own file.
ANALYZE_NEXT = "analyze-next"
ANALYZE_NEXT_PATH = checkout.claude() / "analyze-next.md"


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
    text, registry, form = composed(agent_doc(name, agents), lib)
    lib_files = ([] if form is LibForm.NONE
                 else [path for path, _ in lib_sources(lib)])
    tools: list[Path] = []
    for m in TOOL_RE.finditer(text):
        path = (REPO_ROOT / m.group(1) if m.group(1)
                else REPO_ROOT / "src" / m.group(2))
        if path.exists() and path not in tools:
            tools.append(path)
    return [*registry.files, *lib_files, *tools]


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


def agent_prompt(handbook: str) -> str:
    """The handbook agent's system prompt over a rendering of the handbook."""
    return mctx(
        "Your message is a brief, or a role and then its brief. A role is "
        "the text of a file under `{roles}/`, as `uv run python "
        "scripts/context.py role <stem>` prints it below its first line. "
        "Where your message opens with a role, follow the role, and take the "
        "rest of the message as its brief.").format(
            roles=repo_label(ROLE_DIR)) + "\n\n" + handbook


def agent_definition(document: nm.Node, handbook: str) -> str:
    """An agent's definition file: the agent document's front matter as it
    stands, then the prompt. A document whose `message` attribute is `brief`
    takes the brief alone as its message, and its rendering is the whole
    prompt; any other agent's message is a brief, or a role and then its
    brief, and the prompt says how the agent tells the two apart."""
    return f"{document.front}\n{_prompt(document, handbook)}"


def _prompt(document: nm.Node, handbook: str) -> str:
    """The prompt of the agent `document` defines, over its rendering."""
    if _takes_brief(document):
        return handbook
    return agent_prompt(handbook)


def agent_names(agents: Path = AGENT_DIR) -> list[str]:
    """The agents defined under `agents`: one per document with front
    matter."""
    return [p.stem for p in sorted(agents.glob("*.md"))
            if p.read_text().startswith("---\n")]


def agent_paths(path: Path = AGENT_PATH, agents: Path = AGENT_DIR
                ) -> list[tuple[str, Path]]:
    """Each agent under `agents` with the file `write_agent` writes it to:
    beside `path`, the handbook agent's file, under the agent's name."""
    return [(name, path.with_name(f"{name}{path.suffix}"))
            for name in agent_names(agents)]


def agent_renderings(path: Path = AGENT_PATH, lib: Path = LIB_SRC,
                     agents: Path = AGENT_DIR) -> list[Rendering]:
    """Each agent's definition under `agents`, at its file (`agent_paths`)."""
    return [Rendering(out, agent_definition(agent_document(name, agents),
                                            render(name, lib, agents)))
            for name, out in agent_paths(path, agents)]


def write_agent(path: Path = AGENT_PATH, lib: Path = LIB_SRC,
                agents: Path = AGENT_DIR,
                wrappers: Path = WRAPPERS_PATH) -> Path:
    """Write every agent definition under `agents`, the lib's interface
    files and its wrappers module at `wrappers`, and return the handbook
    agent's path, `path`."""
    write_generated([*interface_renderings(lib),
                     *agent_renderings(path, lib, agents)])
    write_wrappers(lib, wrappers)
    return path


def unlisted_agents(path: Path = AGENT_PATH, agents: Path = AGENT_DIR,
                    root: Path = REPO_ROOT) -> list[Path]:
    """Each file beside `path`, with its suffix, that no agent under
    `agents` is written to and that the manifest at `root` does not list,
    which no run removes."""
    current = {out for _name, out in agent_paths(path, agents)}
    listed = set(read_manifest(root))
    return [file for file in sorted(path.parent.glob(f"*{path.suffix}"))
            if file not in current and in_checkout(file, root) not in listed]


def analyze_next_rendering(path: Path = ANALYZE_NEXT_PATH,
                           agents: Path = AGENT_DIR) -> Rendering:
    """The steps the analyze agent reads after it writes the concept."""
    return Rendering(path, render(ANALYZE_NEXT, agents=agents))


def agent_prompt_text(name: str, lib: Path = LIB_SRC,
                      agents: Path = AGENT_DIR) -> str:
    """An agent's system prompt: what its definition file holds under the
    front matter."""
    return _prompt(agent_document(name, agents), render(name, lib, agents))
