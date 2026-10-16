"""The paths a section of a ticket gives, as `section_paths` reads them,
and whether a text names a file, as `names` judges it."""

import re
from pathlib import Path

from handbook.paths import scripts_importable

scripts_importable()

from ticket_form import section, section_head  # noqa: E402

from operations.state import Ticket  # noqa: E402
from operations.task_work import task_paths  # noqa: E402
from solver.vocabulary import SOLVER_SUFFIX  # noqa: E402

SCOPE = "Scope"

LINES = re.compile(r":\d+(?:-\d+)?$")

IMPORT_ROOTS = ("src", "scripts")
"""The directories a Python module's dotted name counts from."""


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


def scope_paths(t: Ticket, root: Path) -> frozenset[str]:
    return section_paths(t.path.read_text(), SCOPE, root)


def names(text: str, name: str) -> bool:
    """Whether `text` names `name`. A path, which holds a `/`, is named by
    the path, by its file name as a whole word, or, for a `.py` file under
    an import root, by its dotted module name as a whole word. Any other
    name is named as a whole word."""
    if "/" not in name:
        return whole_word(text, name)
    path = Path(name)
    forms = [path.name]
    root = next((r for r in IMPORT_ROOTS if path.is_relative_to(r)), None)
    if path.suffix == ".py" and root is not None:
        forms.append(".".join(path.relative_to(root).with_suffix("").parts))
    return name in text or any(whole_word(text, f) for f in forms)


def whole_word(text: str, word: str) -> bool:
    return re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])", text) is not None
