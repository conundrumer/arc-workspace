"""The whole-document pass: the `change` ticket that
`scripts/merge_change.py` files on the documents past their budget
(`handbook.budget`), as its `--help` gives, its text, and the lookup that
finds one outside `tickets/closed/` by its title, which is the same for
each pass. `uv run python scripts/document_pass.py` files it in the main
tree and prints its path."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from handbook.budget import Size, Standing, measured_text
from handbook.budgeted import rendered_texts, sizes
from handbook.context import composed
from handbook.lib import LIB_SRC
from handbook.paths import repo_label, scripts_importable
from operations.roles import Role
from ticketing.text import DESIGN, SECTIONS, ticket_text
from ticketing.vocabulary import Domain, Kind, Status

scripts_importable()

from file_ticket import file_ticket, main_tickets  # noqa: E402
from ticket_files import ticket_files, ticket_name  # noqa: E402
from ticket_form import title  # noqa: E402
from ticket_log import log_moves, read_ticket  # noqa: E402
from ticket_vocabulary import Filer  # noqa: E402

FILER = Filer.MERGE_CHANGE.value
SUBJECT = "handbook-document-pass"
EDITORS = Role.DOC_EDITOR

TITLE = mctx("handbook: a whole-document pass on each document past its budget")
"""The title of every pass, by which the lookup finds one."""

INTENT = mctx("""
    - Make a [Whole-document pass](prompts/agents/doc-editor/whole-document.md#whole-document-pass) on each of these documents: {documents}.
""")

PASS_DESIGN = mctx("""
    - Make the pass as [Whole-document pass](prompts/agents/doc-editor/whole-document.md#whole-document-pass) gives it.
""")

MOTIVATION = mctx("""
    - Each change that adds a line to a document passes its own review, and the growth of a document over many changes has no owner.
""")

SCOPE = mctx("""
    - The documents the Intent gives: {documents}.
    - Each document whose text the bounded text of one of them holds, by its `* inline:` and `* include:` lines: {read}.
    - Each document the pass moves text into.
""")

GROUNDS = mctx("""
    - The sizes `handbook.budgeted.sizes()` gives at `master` `{commit}`: {sizes}.
""")

SIZE = mctx("{text} {size} of {budget}")

OPENED = mctx("opens with no ticket review: its text is fixed")
"""The note of the line that moves a pass from `tickets/draft/` to
`tickets/open/`."""


def _ticked(path: Path) -> str:
    return f"`{repo_label(path)}`"


def listed(paths: list[Path]) -> str:
    return ", ".join(_ticked(p) for p in paths)


def read_by(docs: list[Path]) -> list[Path]:
    """Each document other than `docs` that the rendering one of `docs`
    bounds reads, in path order."""
    rendered = rendered_texts()
    found = {f for doc in docs if doc in rendered
             for f in composed(doc, LIB_SRC)[1].files}
    return sorted(found - set(docs))


def pass_text(past: list[Size], commit: str) -> str:
    """The text of the pass on the documents `past` gives, as `master`
    stands at `commit`."""
    intent, motivation, scope, grounds = SECTIONS[Kind.CHANGE]
    docs = [s.doc for s in past]
    read = read_by(docs)
    return ticket_text(Kind.CHANGE, TITLE, {
        intent: INTENT.format(documents=listed(docs)),
        DESIGN: PASS_DESIGN,
        motivation: MOTIVATION,
        scope: SCOPE.format(documents=listed(docs),
                              read=listed(read) if read else mctx("none")),
        grounds: GROUNDS.format(commit=commit, sizes=", ".join(
            SIZE.format(text=measured_text(s.measured, _ticked), size=s.size,
                        budget=s.budget)
            for s in past)),
    }, {"editors": EDITORS})


def open_pass(tickets: Path) -> Path | None:
    """The pass that stands outside `tickets/closed/`, or None."""
    return next((p for status in Status if status is not Status.CLOSED
                 for p in ticket_files(tickets, status)
                 if title(p, read_ticket(p)) == TITLE), None)


def file_pass(tickets: Path, found: list[Size], commit: str) -> Path | None:
    """File the pass on each document of `found` past its budget under
    `tickets/open/`, and give its path, where one stands so and no pass
    stands outside `tickets/closed/`."""
    past = [s for s in found if s.standing is Standing.PAST]
    if not past or open_pass(tickets) is not None:
        return None
    path = file_ticket(tickets, Domain.CHANGE.value, SUBJECT, FILER, pass_text(past, commit))
    return log_moves(tickets, ticket_name(path).number, Status.OPEN, FILER, Status.DRAFT,
                     None, OPENED).moved[0]


def main(argv: list[str]) -> None:
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    path = file_pass(main_tickets(), sizes(),
                     checkout.git_out(checkout.ROOT, "rev-parse", "HEAD").strip())
    if path is not None:
        print(path)


if __name__ == "__main__":
    main(sys.argv[1:])
