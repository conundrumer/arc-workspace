"""The duration footer: the last line a long-running tool writes, on
stderr, which says how long the run took, in the one form `FOOTER` gives.
A tool writes it however the run ends, by an exit code, an error or an
interrupt, and writes none only where a signal kills it. So an output with
no footer is that of a run that was stopped, and says nothing of how long
it took.

A tool that runs in steps writes a step line (`STEP`) on stderr as each
step ends, however it ends, which says how long that step took. A footer
says the run ended, and a step line says a step ended while the run goes
on."""

import contextlib
import re
import sys
import time
from collections.abc import Callable, Iterator

from controlled_markdown import mctx

FOOTER = mctx("{tool}: finished in {secs:.0f} s")
_BEFORE, _AFTER = FOOTER.removeprefix("{tool}").split("{secs:.0f}")
FOOTER_RE = re.compile(rf"^.*{re.escape(_BEFORE)}[0-9]+{re.escape(_AFTER)}\n?", re.M)
"""A footer line, with its line end, as a reader of an output finds it."""

STEP = mctx("{tool}: {step} took {secs:.0f} s")
"""A step line, with the step after the tool."""


def footer(tool: str) -> contextlib.AbstractContextManager[None]:
    """Run the block, then write the footer of `tool` on stderr, however the
    block ends."""
    return _timed(lambda secs: FOOTER.format(tool=tool, secs=secs))


def step(tool: str, name: str) -> contextlib.AbstractContextManager[None]:
    """Run the block, then write the step line of step `name` of `tool` on
    stderr, however the block ends."""
    return _timed(lambda secs: STEP.format(tool=tool, step=name, secs=secs))


@contextlib.contextmanager
def _timed(line: Callable[[float], str]) -> Iterator[None]:
    start = time.monotonic()
    try:
        yield
    finally:
        sys.stdout.flush()
        print(line(time.monotonic() - start), file=sys.stderr, flush=True)
