"""File an issue in the form agents launched before tickets were given, as a
ticket under the main tree's `tickets/open/`. `LEGACY_HELP`, which `--help`
prints, says how an agent calls it."""

import re
import sys
from pathlib import Path

from controlled_markdown import mctx
from engine import checkout
from handbook.paths import importable

# `scripts/` is no package: a test loads this module by its path, with
# `scripts/` off `sys.path`, and `file_ticket` imports from there.
importable(checkout.scripts())

from file_ticket import (NAME_PART, Filing, logged, main_tickets,  # noqa: E402
                         run, statuses)
from ticket_numbers import write_after  # noqa: E402
from ticket_vocabulary import Kind, Status  # noqa: E402
from transcripts import Refused  # noqa: E402

LEGACY_HELP = mctx("""
    - Usage:
        ```
        {invocation} <unix time> <source> <agent> <<'EOF'
        ---
        kind: <kind>
        ---
        # <target>: <what is wrong in it>

        ## Effect
        <its effect>

        ## Evidence
        <the evidence>
        EOF
        ```
    - The command reads one issue from stdin, names it `<unix time>-<source>-<agent>-<i>.md`, writes it under `tickets/open/` in the main tree, and prints the path it wrote.
    - `<i>` is 1 more than the largest `<i>` of a file under `tickets/` with the same time, source and agent, so the issues of one `date +%s` count from 1.
    - Give one `date +%s` as `<unix time>` to every call that files your issues.
    - The command refuses, and writes nothing, where the text on stdin does not have the form above.
    """)

LEGACY_FORM = re.compile(r"---\nkind: (?P<kind>\S+)\n---\n# .+: .+\n\n## Effect\n(?:.*\n)*## Evidence(?:\n|$)")
"""The form `scripts/file_issue.py` takes, from agents launched before
tickets."""

LEGACY_KINDS = {"undecided": Kind.QUESTION, "gap": Kind.QUESTION}
"""The kinds an issue filed before tickets gives, mapped to the kind a ticket
gives in their place."""

LEGACY_FILING = Filing("file_issue.py", "file_ticket.py")


def file_legacy(tickets: Path, unix_time: str, source: str, agent: str, text: str) -> Path:
    """Writes an issue in the form `scripts/file_issue.py` takes as a
    ticket under `tickets/open/`, with the kind and section an issue gives
    under the names a ticket gives them, and returns its path."""
    if not unix_time.isdigit():
        raise Refused(mctx("the unix time `{time}` is not a number").format(time=unix_time))
    for part in (source, agent):
        if not NAME_PART.fullmatch(part):
            raise Refused(mctx("`{part}` is not one word without `/`").format(part=part))
    form = LEGACY_FORM.match(text)
    if not form:
        raise Refused(mctx("the issue on stdin does not have the form `--help` shows"))
    old = form.group("kind")
    try:
        kind = LEGACY_KINDS.get(old) or Kind(old)
    except ValueError:
        raise Refused(mctx("`{kind}` is no issue kind").format(kind=old))
    text = text.replace(f"kind: {old}\n", f"kind: {kind}\n", 1).replace("\n## Effect\n", "\n## Impact\n", 1)
    prefix = f"{unix_time}-{source}-{agent}-"
    taken = (int(m.group(1)) for d in statuses(tickets)
             for p in d.glob(f"{prefix}*.md")
             if (m := re.fullmatch(re.escape(prefix) + r"(\d+)\.md", p.name)))
    return write_after(tickets / Status.OPEN, logged(text, Status.OPEN, agent), taken,
                       lambda n: f"{prefix}{n}.md")


def legacy_main(args: list[str]) -> int:
    help_text = LEGACY_HELP.format(invocation=LEGACY_FILING.invocation)
    return run(args, help_text, 3, lambda unix_time, source, agent: file_legacy(
        main_tickets(), unix_time, source, agent, sys.stdin.read()), LEGACY_FILING, args)


if __name__ == "__main__":
    sys.exit(legacy_main(sys.argv[1:]))
