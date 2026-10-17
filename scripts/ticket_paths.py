"""The paths a section of a ticket gives, as `section_paths` reads them,
the text of a ticket where it stands now, as `ticket_text` reads it, and
whether a text refers to a file, as `names` judges it."""

import re
from pathlib import Path

from handbook.paths import scripts_importable

scripts_importable()

from dependents import module_names  # noqa: E402
from ticket_files import ticket_path  # noqa: E402
from ticket_form import section, section_head  # noqa: E402
from ticket_numbers import ticket_number  # noqa: E402
from transcript_entries import Refused  # noqa: E402

from operations.state import Ticket  # noqa: E402
from operations.task_work import task_paths  # noqa: E402
from solver.vocabulary import SOLVER_SUFFIX  # noqa: E402

SCOPE = "Scope"

LINES = re.compile(r":\d+(?:-\d+)?$")


def section_paths(text: str, name: str, root: Path) -> frozenset[str]:
    """The paths the section `name` of the ticket text `text` gives, in
    backticks or as link targets, each with no line or span of lines after
    it: each that is not absolute and holds a
    `/` or stands at the root of the tree `root`, and, for each solver it
    gives, that solver's witness file, since a solver and its witness file
    are edited together. A ticket with no such section gives none."""
    if section_head(text, name) is None:
        return frozenset()
    body = section(text, name)
    words = re.findall(r"`([^`\s]+)`", body) + re.findall(r"\]\(([^)\s]+)\)", body)
    paths = {LINES.sub("", w.split("#", 1)[0].rstrip(":")) for w in words}
    given = {p for p in paths if p and not Path(p).is_absolute() and ("/" in p or (root / p).exists())}
    pairs = (task_paths(Path(p).name.removesuffix(SOLVER_SUFFIX)) for p in given)
    return frozenset(given | {str(w) for s, w in pairs if str(s) in given})


def ticket_text(t: Ticket) -> str | None:
    """The text of the ticket `t` where it stands now: at `t.path`, or,
    where it moved after the tracker read, at the path `ticket_path` gives
    it, read again for each later move. None where `ticket_path` refuses
    it."""
    path = t.path
    while True:
        try:
            return path.read_text()
        except FileNotFoundError:
            try:
                path = ticket_path(t.path.parent.parent, ticket_number(t.number))
            except Refused:
                return None


def scope_paths(t: Ticket, root: Path) -> frozenset[str]:
    """`section_paths` of the Scope of `t` where it stands now, none where
    it stands nowhere."""
    text = ticket_text(t)
    return frozenset() if text is None else section_paths(text, SCOPE, root)


def names(text: str, name: str) -> bool:
    """Whether `text` refers to `name`, as `CLOSED_ON_HELP` in `file_ticket.py`
    gives it. A package's name is no form of its `__init__.py`, since
    `whole_word` admits a `/` or a `.` on each side of a word, so that the
    name stands in each title that gives any module of the package."""
    if "/" not in name:
        return whole_word(text, name)
    path = Path(name)
    forms = [path.name]
    if path.suffix == ".py" and path.name != "__init__.py":
        forms += module_names(name)
    return name in text or any(whole_word(text, f) for f in forms)


def whole_word(text: str, word: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])", text) is not None
