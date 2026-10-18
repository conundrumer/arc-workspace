"""The read of the calls of `profile_runs.py --under`, the runs of a
batch's profile: the command, the lines of its output, and the last call
of an operator that reads."""

import re
from dataclasses import dataclass

from controlled_markdown import mctx
from operations.handled import bash_calls
from operations.roles import AGENT_ID
from operations.state import Call, State


def under_command(operator: str) -> str:
    """Step 1 of After a batch, a Bash step that `next` runs:
    `profile_runs.py --help under` defines the previous call of `--under`,
    and `read_under` gives whether a call of it stands."""
    return f"uv run python scripts/profile_runs.py --under {operator}"


RUN = re.compile(AGENT_ID)
LEFT_OPEN = mctx("left open:")
"""What leads the line of `profile_runs.py --under` that gives the runs it
left out because their work is open."""

NO_RUN = mctx("none")
"""What the `LEFT_OPEN` line gives where it left out no run."""

RUNS_TAKEN = mctx("runs taken:")
"""What leads the line of `profile_runs.py --under` that gives the runs it
takes."""


def lines(output: str, lead: str) -> list[list[str]]:
    """The words after `lead` of each line of `output` that opens with
    `lead`, one list per line. The last piece of `output` has no line break
    after it, so a pipe or the harness may have cut it, and it counts as no
    line."""
    return [line.removeprefix(lead).split()
            for line in output.split("\n")[:-1] if line.startswith(lead)]


@dataclass(frozen=True)
class Under:
    """What a call of `profile_runs.py --under` gives: the agent ids of the
    runs it left open, and of the runs it took."""
    left: frozenset[str]
    taken: tuple[str, ...]


def read_under(output: str) -> Under | None:
    """What the call of `--under` whose output is `output` gives, where the
    call stands as `profile_runs.py --help under` has it: one `LEFT_OPEN` line and
    one `RUNS_TAKEN` line, each ended by a line break, the count on the
    `RUNS_TAKEN` line followed by as many agent ids. None otherwise."""
    left, took = lines(output, LEFT_OPEN), lines(output, RUNS_TAKEN)
    if len(left) != 1 or len(took) != 1 or not took[0] or not took[0][0].isdigit():
        return None
    open_ids = [] if left[0] == [NO_RUN] else left[0]
    ids = took[0][1:]
    if len(ids) != int(took[0][0]) or not all(RUN.fullmatch(i) for i in open_ids + ids):
        return None
    return Under(frozenset(open_ids), tuple(ids))


def last_under(state: State, operator: str, since: float | None,
               until: float | None) -> tuple[Call, Under] | None:
    calls = [(c, u) for c in under_calls(state, operator, since, until)
             if c.result is not None and (u := read_under(c.result)) is not None]
    return calls[-1] if calls else None


def under_calls(state: State, operator: str, since: float | None,
                until: float | None) -> list[Call]:
    """The calls of `--under` on `operator`, of those made after `since`
    and before `until`, each where it is given."""
    return [c for c in bash_calls(state, under_command(operator))
            if (since is None or c.time > since) and (until is None or c.time < until)]
