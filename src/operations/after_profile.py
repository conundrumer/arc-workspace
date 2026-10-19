"""The Bash steps given once after the last profile launch of After a
batch (`batches`), each its own procedure of `order.LATE`.

The sweep (`file_ticket.py sweep`) runs where a `validation` ticket of
the session stands under `tickets/deferred/`, on the runs of the batch
that profile launch closed, the runs the profile's brief gives, and on
the session's operators, its operator launchers and its main run, which
stand under no operator, so no batch holds them. The sweep checks a
ticket only on the lines of those runs timestamped at or after the
ticket's last move into `deferred`.

The check of the script calls (`scripts/check_script_calls.py`) runs on
the calls since the closed batch's start."""

import shlex
from collections.abc import Callable

import script_calls

from operations import batches
from operations.constants import COORDINATOR
from operations.handled import done
from operations.log_commands import FILE_TICKET
from operations.state import State
from operations.steps import Bash
from operations.unbatched import PROFILE
from ticketing.times import utc_stamp
from ticketing.vocabulary import Kind, Status


def once_after_profile(state: State, label: str,
                       command: Callable[[float], str | None]) -> Bash | None:
    """The Bash step of what `command` gives for the launch time of the
    last profile launch, where no step of it was done since that launch;
    None where no profile launch stands or `command` gives None."""
    profiles = PROFILE.agents(state)
    if not profiles:
        return None
    closing = profiles[-1].launched
    if (line := command(closing)) is None:
        return None
    step = Bash(line, label, occasion=str(closing))
    return None if done(state, step) else step


def validation(state: State) -> Bash | None:
    """The sweep of the batch the last profile launch closed, where one is
    due."""
    def sweep(closing: float) -> str | None:
        if not any(t.kind is Kind.VALIDATION and t.status is Status.DEFERRED and state.mine(t)
                   for t in state.tracker.tickets.values()):
            return None
        runs = batches.batch_runs(state, batches.followed(state, closing),
                                  batches.start(state, closing), closing)
        # No batch waits on the sweep: where the runs do not read, the `validation`
        # tickets stay under `deferred` for the next profile launch.
        return sweep_command([*runs, *unbatched_runs(state)]) if isinstance(runs, list) else None
    return once_after_profile(state, "sweep", sweep)


def unbatched_runs(state: State) -> list[str]:
    """The session's operators, its operator launchers, and its main run,
    in that order."""
    launchers = dict.fromkeys(p for o in state.operators
                              if (p := state.parents.get(o)) not in (None, COORDINATOR))
    return [*state.operators, *launchers, state.session]


def script_check(state: State) -> Bash | None:
    """The check of the script calls since the start of the batch the last
    profile launch closed, where one is due; where that batch has no start,
    of the calls of the window before that launch."""
    return once_after_profile(state, "script check", lambda closing: check_command(
        batches.start(state, closing) or closing - script_calls.WINDOW_SECONDS))


def check_command(since: float) -> str:
    return f"uv run python scripts/check_script_calls.py --since {utc_stamp(since)}"


def sweep_command(runs: list[str]) -> str:
    return shlex.join([*FILE_TICKET, "sweep", *runs])
