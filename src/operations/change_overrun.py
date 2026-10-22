"""A change past its cost budget.

`change_budget` gives a change's cost budget. Once its spend passes
that budget, at the command's next call, whether or not an agent of the
change is at work, the command writes the line that `change_budget`
gives once per take, with that spend. That line stops nothing: the
change goes on as a change within its budget does."""

from controlled_markdown import mctx
from operations.change_budget import past_budget, past_note, stopped, taken
from operations.state import UnpricedSpend, State, Ticket
from operations.steps import Bash, Step, Undecided
from operations.log_commands import log
from ticketing.vocabulary import Status


def over_budget(state: State, t: Ticket) -> Step | None:
    """The line on the change `t` past the budget its take gives, where
    none was written since its take, or None where it is not past
    it, a line since its take gives that it is, or no take line gives a
    budget."""
    take_line = taken(t)
    if take_line is None:
        return None
    spent = state.computed.spent.get(t.number)
    if spent is None:
        return Undecided(mctx("the spend of change {number} since its take is unknown").format(
            number=t.number))
    overrun = past_budget(take_line, spent)
    if overrun is None:
        if isinstance(spent, UnpricedSpend) or spent.codex is None \
                or not spent.codex.dollars_known:
            return Undecided(mctx(
                "change {number}: a cost measurement is incomplete or unavailable"
            ).format(number=t.number))
        return None
    if stopped(t) is None:
        return Bash(log(t.number, Status.ASSIGNED, Status.ASSIGNED, past_note(overrun),
                        state.me), f"{t.number} past its budget", occasion=str(t.taken))
    return None
