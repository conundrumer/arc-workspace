"""A process assessment, a ticket analyst, launches at any step once
`ASSESS_AFTER` commits of `master` that change the agents' processes
stand since `occasions.opened` of the process assessments, and none runs."""

from operations import briefs
from operations.main_session import main_only
from operations.occasions import next_number, opened
from operations.roles import Purpose, analyst_subject
from operations.state import State
from operations.steps import Launch, Step
from operations.unbatched import ASSESSMENT


ASSESS_AFTER = 20


@main_only
def assessment(state: State) -> Step | None:
    """The launch of a process assessment, where one is due."""
    past = ASSESSMENT.agents(state)
    since = opened(state, past)
    if since is None or len({c.hash for c in state.git.commits if c.process and c.time > since}) < ASSESS_AFTER:
        return None
    return Launch(ASSESSMENT.role, analyst_subject(Purpose.ASSESS, next_number(past)),
                  briefs.process_assessment(state.me), occasion=str(since))
