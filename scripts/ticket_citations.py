"""The `closed-on` and `citing` subcommands of `file_ticket.py`: their
helps, and the calls that list the tickets whose title refers to a name,
by the reference rule `CLOSED_ON_HELP` gives. `file_ticket.help_values`
gives the values their help texts are formatted with."""

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from ticket_files import listed_tickets, ticket_name, ticket_status
from ticket_form import TICKET_HEAD, front_kind, title
from ticket_log import Moved, log_lines, read_ticket
from ticketing.references import PreparedReference, word_forms
from ticketing.vocabulary import Kind, Status
from tree_reads import main_tree

EMPTY = mctx("the list is empty")

CLOSED_ON_HELP = mctx("""
    - `<name>` is a word or a path from the root of the tree, as the title of a ticket gives it.
    - The command prints, for each ticket under `tickets/{closed}/` whose title refers to a `<name>`, or a path that a `<name>` that is a path had before, as `git log --follow --name-only` gives it on `master`, its number and title, and under them its last log line, in the order of numbers, or `{empty}` where no title refers to one.
    - A title refers to a path, which holds a `/`, where it holds the path, the path's file name as a whole word, or, for a `.py` file other than a package's `__init__.py`, each dotted name it can be imported by, as a whole word, such as `operations.plan` for `src/operations/plan.py`. It refers to any other `<name>` where it holds it as a whole word.
    """)

CITING_HELP = mctx("""
    - `<name>`, the paths a `<name>` had before, and the rule by which a title refers to one of them are as `closed-on --help` gives them.
    - The command prints, for each `<name>` in the order given, a line with the `<name>` and the paths it had before, then each ticket under any status directory of `tickets/` whose title refers to one of them, with its number, its status, its kind and its title, and under them its last log line, in the order of numbers, or `{empty}` where no title refers to one.
    """)

NAMES = mctx("names: {names}")
CITED_NAME = mctx("{name}: names: {names}")


@dataclass(frozen=True)
class Names:
    """A name a call gives, with the paths it had before on `master`, as
    `git log --follow --name-only` gives them, with their reference matchers
    prepared for reuse across titles."""
    name: str
    references: tuple[tuple[str, PreparedReference], ...]

    @property
    def known(self) -> list[str]:
        return [n for n, _ in self.references]

    def cited_by(self, text: str) -> bool:
        return any(reference(text) for _, reference in self.references)


def names_of(main: Path, name: str) -> Names:
    """`name` with the paths it had before on `master`, where it is the
    path of a file: it holds a `/` and `main` holds no directory at it. A
    word, or a directory, has no earlier paths: `git log --follow` on a
    directory gives every file that ever stood under it."""
    known = {name}
    if "/" in name and not (main / name).is_dir():
        known |= {line for line in checkout.git_out(
            main, "log", "--follow", "--name-only", "--format=", "master", "--", name).splitlines() if line}
    return Names(name, tuple((n, PreparedReference(n, word_forms(n))) for n in sorted(known)))


@dataclass(frozen=True)
class Listed:
    """A ticket as the two subcommands list it."""
    path: Path
    kind: Kind
    title: str
    last: str
    """Its last log line."""


def listed(path: Path, text: str) -> Listed:
    """The ticket at `path`, whose text is `text`."""
    name = title(path, text)
    head = TICKET_HEAD.match(text)
    assert head is not None, "`title` refuses a text that `TICKET_HEAD` does not match"
    return Listed(path, front_kind(head), name, log_lines(text)[-1].group())


def citing(statuses: Collection[Status], groups: Sequence[Sequence[Names]]) -> list[list[Listed]]:
    """For each of `groups`, the tickets under `statuses` whose title one of
    its names cites, in the order of numbers. Each ticket is read once. A
    ticket that moves before its read, or whose text reads as empty, as a
    ticket another session writes at that time can, is left out."""
    tickets = main_tree() / "tickets"
    paths = sorted((p for s in statuses for p in listed_tickets(tickets, s)),
                   key=lambda p: ticket_name(p).number.order)
    found: list[list[Listed]] = [[] for _ in groups]
    for p in paths:
        try:
            text = read_ticket(p)
        except Moved:
            continue
        if not text:
            continue
        t = listed(p, text)
        for group, out in zip(groups, found, strict=True):
            if any(n.cited_by(t.title) for n in group):
                out.append(t)
    return found


def closed_on_command(targets: Sequence[str]) -> str:
    """Each closed ticket whose title refers to one of `targets`, as
    `CLOSED_ON_HELP` gives it."""
    main = main_tree()
    group = [names_of(main, n) for n in targets]
    [found] = citing((Status.CLOSED,), [group])
    rows = [f"{ticket_name(t.path).number} {t.title}\n    {t.last}" for t in found]
    known = {k for n in group for k in n.known}
    return "\n".join([NAMES.format(names=", ".join(sorted(known))), *(rows or [EMPTY])])


def citing_command(targets: Sequence[str]) -> str:
    """For each of `targets`, each ticket whose title refers to it, as
    `CITING_HELP` gives it."""
    main = main_tree()
    given = [names_of(main, n) for n in targets]
    blocks: list[str] = []
    for n, found in zip(given, citing(tuple(Status), [[n] for n in given]), strict=True):
        rows = [f"    {ticket_name(t.path).number} {ticket_status(t.path)} {t.kind} {t.title}"
                f"\n        {t.last}" for t in found]
        blocks.append("\n".join([CITED_NAME.format(name=n.name, names=", ".join(n.known)),
                                 *(rows or [f"    {EMPTY}"])]))
    return "\n".join(blocks)
