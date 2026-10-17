"""The contexts: what each reader the `context` command knows reads,
printed as the reader receives it.
"""

from __future__ import annotations

from pathlib import Path

import controlled_markdown as nm
from controlled_markdown import mctx
from engine import checkout
from handbook import paths
from handbook.agent_documents import agent_document
from handbook.agents import (agent_file, agent_names,
                             agent_prompt_text, next_file, next_readers,
                             next_text)
from handbook.context import (CODEX_DOC, ROLE_DIR, SESSION_DOC, entry_text,
                              first_heading, no_item_named, role_document,
                              role_file, session_text, workflow_file,
                              write_lib_output)
from handbook.lib import LibForm, lib_form
from handbook.paths import document, repo_label
from handbook.role_briefs import spawn_line
from handbook.workflow_scripts import (Phase, Unplaced, workflow_fragments,
                                      workflow_phases, workflow_roleless_line)

APPENDIX = mctx("the system-prompt appendix")
"""What the console worker's first section is called."""

# A reader's context, printed as the reader receives it. Each section opens
# with a marker line, so two runs diff line by line.
MARKER = "==== {what} ====\n"

# The sample values a printed message takes in place of the ones a run fills.
SAMPLE_TID = "0000abcd"
SAMPLE_TASK = '{"train": [{"input": [[0]], "output": [[1]]}], "test": []}'
SAMPLE_REPORTS = "<prior reports>"
SAMPLE_ENTRY = "docs/wf-solver/proposals/<entry>.md"
SAMPLE_SCOPE = "every solver"
SAMPLE_SCRATCH = "work/console/surveys/<entry>/<run time>"

# The session's own skill, which a session at a terminal reads beside the
# handbook.
SESSION_SKILL = document(checkout.skills()) / "session" / "SKILL.md"


def marked_section(what: str, text: str) -> str:
    """One marked section: the marker line, a blank line, and the text."""
    return MARKER.format(what=what) + "\n" + text.rstrip("\n") + "\n"


def _console():
    """The console's prompt builders and its stage chain, imported once
    `console_importable` puts the console on the path."""
    paths.console_importable()
    from solver_console import prompts, store
    return prompts, store


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


def console_stages() -> list[str]:
    """The stages of the chain a wave runs when it states none."""
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
                                    task=SAMPLE_TASK)))
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
    `store.default_chain` gives, which is the chain a wave runs when it states
    none."""
    prompts, _ = _console()
    stages = console_stages()
    if stage not in stages:
        raise no_item_named("console stage", "stages", stage, stages)
    parts = [marked_section(APPENDIX, prompts.append_text())]
    parts += [marked_section(what, text)
              for what, text in _stage_messages(stage, stages, prompts)]
    return "\n".join(parts)


def survey_context() -> str:
    """What a survey session reads: the appendix its agent takes as its system
    prompt, then the role's text and the survey brief."""
    prompts, _ = _console()
    agent = agent_document(role_document("survey")[0])
    return "\n".join([
        marked_section(APPENDIX, prompts.append_text(
            index=lib_form(agent) is LibForm.INDEX)),
        marked_section(repo_label(role_file("survey")),
                 prompts.role_text("survey")),
        marked_section(mctx("the `survey` message"),
                 prompts.survey_brief(entry=SAMPLE_ENTRY, scope=SAMPLE_SCOPE,
                                      scratch=SAMPLE_SCRATCH)),
    ])


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
