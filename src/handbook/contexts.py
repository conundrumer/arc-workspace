"""The contexts: what each reader the `context` command knows reads,
printed as the reader receives it.
"""

from __future__ import annotations

from pathlib import Path

import controlled_markdown as nm
from controlled_markdown import mctx
from engine import checkout
from handbook.agents import (agent_file, agent_names,
                             agent_prompt_text, next_file, next_readers,
                             next_text)
from handbook.context import (CODEX_DOC, ROLE_DIR, SESSION_DOC, entry_text,
                              first_heading, no_item_named, role_document,
                              role_file, session_text, workflow_file,
                              write_lib_output)
from handbook.paths import document, repo_label
from handbook.role_briefs import spawn_line
from handbook.workflow_scripts import (Phase, Unplaced, workflow_fragments,
                                      workflow_phases, workflow_roleless_line)

APPENDIX = mctx("the system-prompt appendix")
"""What the system-prompt appendix's section is called."""

# A reader's context, printed as the reader receives it. Each section opens
# with a marker line, so two runs diff line by line.
MARKER = "==== {what} ====\n"

# The session's own skill, which a session at a terminal reads beside the
# handbook.
SESSION_SKILL = document(checkout.skills()) / "session" / "SKILL.md"


def marked_section(what: str, text: str) -> str:
    """One marked section: the marker line, a blank line, and the text."""
    return MARKER.format(what=what) + "\n" + text.rstrip("\n") + "\n"


def _body(path: Path) -> str:
    """A file's text from its first heading (`first_heading`), so a front
    matter block that reaches no agent is left out."""
    text = path.read_text()
    head = first_heading(nm.parse(text, path.name))
    if head is None:
        return text
    return "".join(text.splitlines(keepends=True)[head.line - 1:])


def session_context() -> str:
    """What a session at a terminal reads: the session skill the user invokes,
    then the session document with the lib, which the skill's first line sends
    the session to read. The lib's interface files are written first, the way
    the no-argument form writes them, so the lib index lists the files as they
    stand."""
    write_lib_output()
    return "\n".join([
        marked_section(repo_label(SESSION_SKILL),
                 _body(SESSION_SKILL)),
        marked_section(repo_label(SESSION_DOC), session_text()),
    ])


def codex_context() -> str:
    """What a codex session on the repo reads: AGENTS.md, as `--write`
    renders it."""
    return marked_section("AGENTS.md", entry_text(CODEX_DOC))


def agent_context(name: str) -> str:
    """One agent's system prompt, as `--write` writes it. The front matter
    the harness reads stands above it in the file, and the agent receives
    what follows."""
    if name not in agent_names():
        raise no_item_named("agent", "agents", name, agent_names())
    text = marked_section(repo_label(agent_file(name)), agent_prompt_text(name))
    if name in next_readers():
        text += "\n" + marked_section(repo_label(next_file(name)),
                                       next_text(name))
    return text


def role_context(name: str, roles: Path = ROLE_DIR,
                 stage: Phase | None = None,
                 seen: set[str] | None = None,
                 brief: bool = True) -> str:
    """What an agent running the role reads: its agent's definition, its role
    text, then the line saying where its brief comes from. `stage` is the
    phase a workflow run reaches the role in, None for a role read outside
    a workflow. `seen` holds the agents a caller has
    already printed, and an agent it holds takes a marker line in place of its
    definition. `brief` set to False leaves out the line about the brief, for
    a caller that states the source itself."""
    agent, body = role_document(name, roles)
    path = repo_label(agent_file(agent))
    if seen is not None and agent in seen:
        head = MARKER.format(
            what=mctx("{path}, the definition printed above").format(path=path))
    else:
        head = agent_context(agent)
        if seen is not None:
            seen.add(agent)
    label = repo_label(role_file(name, roles))
    if stage is Unplaced.NO_PHASE:
        label = mctx("{path}, in a phase this listing does not find").format(
            path=label)
    elif stage is not None:
        label = mctx("{path}, in the {phase} phase").format(
            path=label, phase=stage)
    parts = [head, marked_section(label, body)]
    if brief:
        parts.append(marked_section(mctx("the brief"), spawn_line(name)))
    return "\n".join(parts)


def workflow_context(name: str) -> str:
    """What each agent of a workflow run reads: the role context of every role
    the script refers to, in phase order, the phases no role runs in, then the
    line stating where the briefs are built and the briefs themselves."""
    script = repo_label(workflow_file(name))
    phases = workflow_phases(name)
    parts = [marked_section(mctx("the roles {path} reaches").format(path=script),
                      "\n".join(phases))]
    # One definition per agent: a later role on the same agent takes a marker
    # line pointing at the copy above.
    seen: set[str] = set()
    parts += [role_context(role, stage=stage, seen=seen, brief=False)
              for role, stage in phases.items()]
    parts.append(marked_section(mctx("the phases with no role"),
                          workflow_roleless_line(name)))
    briefs = mctx("Brief: built by {path}, in its briefs "
                  "region.").format(path=script)
    parts.append(marked_section(mctx("the workflow's briefs"),
                          briefs + "\n\n" + workflow_fragments(name)))
    return "\n".join(parts)
