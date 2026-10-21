"""A load check launches on the newest alert file of the machine watcher
of the session (`State.machine_alerts`) where no load check of the session
has that file's stem as its subject. Only the newest file is tested: the
processes of an older one are either gone or in the newer one."""

from operations import briefs
from operations.completion import occupies
from operations.main_session import main_only
from operations.state import State
from operations.steps import Launch, Step
from operations.unbatched import LOAD_CHECK


@main_only
def load_check(state: State) -> Step | None:
    """The launch of the load check of the newest alert, where one is due."""
    if not state.machine_alerts:
        return None
    newest = state.machine_alerts[-1]
    if any(a.subject == newest.stem and occupies(a) for a in LOAD_CHECK.agents(state)):
        return None
    return Launch(LOAD_CHECK.role, newest.stem, briefs.load_check(newest, state.me),
                  occasion=newest.stem)
