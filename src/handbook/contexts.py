"""The contexts: what each reader the `context` command knows reads,
printed as the reader receives it, and the roles a workflow script reaches,
each with the phase it runs in.
"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path

import controlled_markdown as nm
from controlled_markdown import mctx
from engine import checkout
from handbook import paths
from handbook.agents import (ANALYZE_NEXT, ANALYZE_NEXT_PATH, agent_document,
                             agent_file, agent_names, agent_prompt_text,
                             render)
from handbook.context import (CODEX_DOC, DOCS_DIR, ROLE_DIR, SESSION_DOC,
                              WORKFLOW_DIR, entry_text, first_heading,
                              role_body, role_file, role_stems, session_text,
                              workflow_file, write_interfaces)
from handbook.lib import LibForm, lib_form
from handbook.paths import DOCUMENTS_ROOT, document, repo_label

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
CONSOLE_DIR = document(checkout.console())

# The scripts that build a role's brief. A file here that states the role on a
# line about roles spawns that role.
SPAWN_GLOBS = ((WORKFLOW_DIR, "*.js"), (document(checkout.scripts()), "*.py"),
               (CONSOLE_DIR, "*.py"), (CONSOLE_DIR / "solver_console", "*.py"))
# The documents that tell a session to spawn a role. A session that reads one
# of them briefs the role itself.
SPAWN_DOC_GLOBS = ((DOCS_DIR, "*.md"),
                   (document(checkout.prompts()), "**/*.md"))


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
    write_interfaces()
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
        raise SystemExit(f"no agent named `{name}`; the agents are "
                         + ", ".join(agent_names()))
    text = marked_section(repo_label(agent_file(name)), agent_prompt_text(name))
    if name == "analyze":
        text += "\n" + marked_section(repo_label(ANALYZE_NEXT_PATH),
                                render(ANALYZE_NEXT))
    return text


def _role_agent(name: str, roles: Path = ROLE_DIR) -> str:
    """The agent a role runs on: its `agent` attribute, or the handbook
    agent."""
    registry = nm.Registry(DOCUMENTS_ROOT)
    return nm.role(registry.load(role_file(name, roles)), registry)[0]


def _spawners(name: str) -> list[str]:
    """The scripts that build the role's brief: the ones stating the role on a
    line that is about roles."""
    out = []
    for directory, pattern in SPAWN_GLOBS:
        for path in sorted(directory.glob(pattern)):
            for line in path.read_text().splitlines():
                if _role_columns(line, name):
                    out.append(repo_label(path))
                    break
    return out


def _word_at(word: str, line: str) -> int | None:
    """The column of the first whole-word occurrence of `word` on the
    line; None where it does not occur."""
    m = re.search(rf"\b{re.escape(word)}\b", line)
    return None if m is None else m.start()


def _role_columns(line: str, stem: str) -> list[int]:
    """Where a script's line refers to the role `stem`: as `roles.<stem>`,
    or as the quoted stem on a line that is about roles; the column of
    each."""
    out: list[int] = []
    if (at := _word_at(f"roles.{stem}", line)) is not None:
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
    return mctx("Brief: briefed by the session that spawns it.")


class Unplaced(Enum):
    """A role a workflow script refers to that no phase of the script
    reaches."""

    NO_PHASE = "no phase"


type Phase = str | Unplaced
"""The phase a workflow run reaches a role in: a title of the script's
`meta.phases`, or `Unplaced.NO_PHASE`."""


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
    if not role_file(name, roles).is_file():
        raise SystemExit(f"no role named `{name}`")
    agent = _role_agent(name, roles)
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
    parts = [head, marked_section(label, role_body(name, roles))]
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
        raise SystemExit(f"no console stage named `{stage}`; the stages are "
                         + ", ".join(stages))
    parts = [marked_section(APPENDIX, prompts.append_text())]
    parts += [marked_section(what, text)
              for what, text in _stage_messages(stage, stages, prompts)]
    return "\n".join(parts)


def survey_context() -> str:
    """What a survey session reads: the appendix its agent takes as its system
    prompt, then the role's text and the survey brief."""
    prompts, _ = _console()
    agent = agent_document(_role_agent("survey"))
    return "\n".join([
        marked_section(APPENDIX, prompts.append_text(
            index=lib_form(agent) is LibForm.INDEX)),
        marked_section(repo_label(role_file("survey")),
                 prompts.role_text("survey")),
        marked_section(mctx("the `survey` message"),
                 prompts.survey_brief(entry=SAMPLE_ENTRY, scope=SAMPLE_SCOPE,
                                      scratch=SAMPLE_SCRATCH)),
    ])





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


def _at_column(named: dict[str, int], stem: str, column: int) -> None:
    """Note that a line refers to `stem` at `column`, keeping the first
    column the line refers to it at."""
    named[stem] = min(column, named.get(stem, column))


def workflow_phases(name: str, roles: Path = ROLE_DIR,
                    workflows: Path = WORKFLOW_DIR) -> dict[str, Phase]:
    """Each role the workflow script refers to, in phase order, with the phase it
    runs in. A line inside an `agent(` call that carries a `phase:` option
    takes that phase, and any other line takes the phase of the nearest
    `phase()` statement above it. A line refers to a role by its stem, by a
    variable bound to `roles.<stem>`, or, inside such a call, by a list of
    stems or a function returning members of one. A role no phase reaches
    takes `Unplaced.NO_PHASE`, and it follows the placed roles, at the line it
    first stands on. Roles one line refers to follow the order they stand
    in on it."""
    path = workflow_file(name, workflows)
    text = path.read_text()
    phases = _workflow_phases(text)
    stems = role_stems(roles)
    aliases = _role_aliases(text, set(stems))
    groups = _role_groups(text, set(stems))
    call_phases = _call_phases(text)
    running: Phase = Unplaced.NO_PHASE
    found: dict[str, tuple[int, int, int, Phase]] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        bare = BARE_PHASE_RE.match(line)
        if bare:
            running = bare.group(1)
        option = PHASE_RE.search(line)
        named_phase = option.group(1) if option \
            else call_phases.get(number, running)
        title: Phase = named_phase if named_phase in phases \
            else Unplaced.NO_PHASE
        rank = len(phases) if isinstance(title, Unplaced) \
            else phases.index(title)
        named: dict[str, int] = {}
        for stem in stems:
            for column in _role_columns(line, stem):
                _at_column(named, stem, column)
        for variable, stem in aliases.items():
            if (at := _word_at(variable, line)) is not None:
                _at_column(named, stem, at)
        if number in call_phases:
            for group, members in groups.items():
                if (at := _word_at(group, line)) is not None:
                    for member in members:
                        _at_column(named, member, at)
        for stem, column in named.items():
            at = found.get(stem)
            if at is None or rank < at[0]:
                found[stem] = (rank, number, column, title)
    order = sorted(found, key=lambda s: found[s][:3])
    return {stem: found[stem][3] for stem in order}


def workflow_roles(name: str, roles: Path = ROLE_DIR,
                   workflows: Path = WORKFLOW_DIR) -> list[str]:
    """The roles the workflow script refers to, in phase order."""
    return list(workflow_phases(name, roles, workflows))





def workflow_roleless_phases(name: str, roles: Path = ROLE_DIR,
                             workflows: Path = WORKFLOW_DIR) -> list[str]:
    """The phases of the script's `meta.phases` that no role the roles listing
    places falls in, in `meta.phases` order."""
    path = workflow_file(name, workflows)
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
    path = workflow_file(name, workflows)
    script = repo_label(path)
    return "\n\n".join(f"{script}:{fragment.line}\n\n{fragment.text.rstrip()}"
                       for fragment in nm.fragments(path, script))


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
