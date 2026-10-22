"""A cost audit launches at any step once the priced Claude and Codex spend
of its window (`state.AuditWindow`), in subscription dollars, a lower bound
of its spend, is at least `AUDIT_AFTER`, and the last cost audit an operator
of the session launched does not run."""

from controlled_markdown import mctx
from operations import briefs
from operations.completion import occupies
from operations.main_session import main_only
from operations.occasions import next_number, opened
from operations.state import NotComputed, State
from operations.steps import Launch, Step, Undecided
from operations.unbatched import COST_AUDIT
from ticketing.subscription import CLAUDE_WEEK_PRICE


AUDIT_AFTER = 0.1 * CLAUDE_WEEK_PRICE
"""The spend, in subscription dollars, of a cost audit's window at which it
launches: 10% of the Claude week."""


@main_only
def audit(state: State) -> Step | None:
    """The launch of a cost audit, where one is due."""
    past = COST_AUDIT.agents(state)
    if opened(state, past) is None:
        return None
    window = state.computed.audit_window
    if isinstance(window, NotComputed):
        return Undecided(mctx("the window of the next cost audit is unknown: {why}").format(why=window.why))
    retry = bool(past) and not occupies(past[-1])
    if window.priced_spend < AUDIT_AFTER and not retry:
        return None
    return Launch(COST_AUDIT.role, next_number(past),
                  briefs.cost_audit(min(window.start, opened(state, past) or state.started)
                                    if retry else window.start, state.transcripts_dir, state.me),
                  occasion=str(window.start))
