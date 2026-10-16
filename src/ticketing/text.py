"""The text of a ticket that a filing gives on stdin, which the ticket tools
under `scripts/` and the operator's command write: the sections of each
kind and the writer of the text from its title and its sections."""

from collections.abc import Mapping

from ticketing.vocabulary import DEFECT_SECTIONS, Kind

SECTIONS = {Kind.CHANGE: ("Intent", "Motivation", "Scope", "Grounds"),
            Kind.REQUEST: ("Goal", "Transcript", "Grounds")}
"""The sections of each kind that has its own; every other kind has
`DEFECT_SECTIONS`."""


DESIGN = "Design"
"""The section a `change` that adds a mechanism to code, or adds or
changes a rule or a fact in the agent-facing documents, adds after its
Intent, which `body_form` lets stand between its sections."""


VALIDATION = "Validation"
"""The section of a `request` that a `change` serves that gives what a
later run must show for its need to count as met. `ticket_form.body_form`
admits it as it admits any line after the sections it requires."""


def kind_sections(kind: Kind) -> tuple[str, ...]:
    return SECTIONS.get(kind, DEFECT_SECTIONS)


HEADING_MARK = "## "


def heading(section: str) -> str:
    return f"{HEADING_MARK}{section}"


def ticket_text(kind: Kind, title: str, lines: Mapping[str, str],
                fields: Mapping[str, str] | None = None) -> str:
    """The text of a `kind` ticket with the front matter fields `fields`
    after `kind`, whose sections, each with its `lines`, are the kind's
    own, with a `DESIGN` section after the first where `lines` gives one."""
    sections = kind_sections(kind)
    if DESIGN in lines and kind is Kind.CHANGE:
        sections = (sections[0], DESIGN, *sections[1:])
    if set(lines) != set(sections):
        raise ValueError(f"the sections {sorted(lines)} are not those of a `{kind}`")
    front = "".join(f"{k}: {v}\n" for k, v in (fields or {}).items())
    body = "\n\n".join(f"{heading(s)}\n{lines[s]}" for s in sections)
    return f"---\nkind: {kind.value}\n{front}---\n# {title}\n\n{body}\n"
