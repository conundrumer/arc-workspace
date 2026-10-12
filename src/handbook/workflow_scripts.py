"""The roles a workflow script reaches, each with the phase it runs in,
read from the script's text, the phases no role runs in, and the script's
briefs."""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path

from controlled_markdown import mctx
from handbook.context import ROLE_DIR, WORKFLOW_DIR, role_stems, workflow_file
from handbook.fragments import file_fragments_text
from handbook.role_briefs import role_columns, word_at


class Unplaced(Enum):
    """A role a workflow script refers to that no phase of the script
    reaches."""

    NO_PHASE = "no phase"


type Phase = str | Unplaced
"""The phase a workflow run reaches a role in: a title of the script's
`meta.phases`, or `Unplaced.NO_PHASE`."""


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
            for column in role_columns(line, stem):
                _at_column(named, stem, column)
        for variable, stem in aliases.items():
            if (at := word_at(variable, line)) is not None:
                _at_column(named, stem, at)
        if number in call_phases:
            for group, members in groups.items():
                if (at := word_at(group, line)) is not None:
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
    return file_fragments_text(workflow_file(name, workflows))
