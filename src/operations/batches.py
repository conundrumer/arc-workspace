"""After a batch.

No batch holds the sweep and the script check (`after_profile`), nor
the launches `unbatched` declares. So no profile launch waits on them.

After a batch: once every agent of a batch has returned, or once the
batch has stood `BATCH_SPAN` since its first launch, the release of
tickets, and an agent on the profile of the batch's runs.

A batch is the agents the session's operators launched since the launch
of the previous batch's profile agent, other than those no batch holds,
with the changes merged since: those an operator's merge call merged, as
`state.Merge` reads it, and those the coordinator gives as merged. The
launch of the profile agent opens the next batch.

The profile agent profiles each run `profile_runs.py --under` takes, and
may launch a transcript review only of those a batch holds: a review of
the runs no batch holds, After a batch's own among them, files tickets
whose triage opens the next batch. The ticket analyst on the tickets the
batch filed is the one `triage` launches on any open ticket."""

from controlled_markdown import mctx
from operations import briefs
from operations.taking import release
from operations.occasions import merged, next_number
from operations.state import Agent, State, memoized_by_transcripts
from operations.steps import Bash, Launch, Step, Undecided
from operations.under_reads import last_under, under_calls, under_command
from operations.unbatched import PROFILE, follows


BATCH_SPAN = 3600
"""The seconds since a batch's first launch after which the batch closes
with members pending, and the least span between two gate launches."""


def start(state: State, before: float | None = None) -> float:
    """The launch time of the last profile launch, of those before
    `before` where it is given, or 0.0 where there is none."""
    return max((p.launched for p in PROFILE.agents(state)
                if before is None or p.launched < before), default=0.0)


def members(state: State, since: float) -> list[Agent]:
    return [a for a in batched(state) if a.launched > since]


@memoized_by_transcripts
def batched(state: State) -> tuple[Agent, ...]:
    """The agents of the session that a batch holds."""
    return tuple(a for a in state.transcripts.agents if not follows(a.role, a.subject))


def followed(state: State, at: float) -> list[Agent]:
    """The members of the batch that a launch of After a batch made at
    `at` follows: the batch opened by the last profile launch before it."""
    return [a for a in members(state, start(state, at)) if a.launched < at]


def step(state: State) -> Step | None:
    since = start(state)
    batch = members(state, since)
    if not batch and not merged(state, since):
        return None
    if any(a.pending for a in batch) and state.now - min(a.launched for a in batch) < BATCH_SPAN:
        return None
    if (s := release(state)) is not None:
        return s
    runs = batch_runs(state, batch, since, None)
    if not isinstance(runs, list):
        return runs
    ids = {a.agent_id for a in batched(state)}
    return Launch(PROFILE.role, next_number(PROFILE.agents(state)),
                  briefs.batch_profile(runs, [r for r in runs if r in ids], state.git.commits[0].hash),
                  occasion=str(since))


def batch_runs(state: State, batch: list[Agent], since: float,
               until: float | None) -> list[str] | Step:
    """The runs the last call of `--under` of each operator made after
    `since`, and before `until` where it is given, takes, or the step that
    stands in their place. The operators are those of `batch`, or this
    operator where `batch` is empty, and each operator of an agent of the
    session whose last call of `--under` before `since` left a run open,
    so that a run still at work at one batch's close is taken at a later
    one, whether or not that operator still runs. A call of `--under` in
    that span whose output does not read (`read_under`) is undecided, and
    the command is not run again."""
    ops = {a.operator for a in batch} or {state.me}
    ops |= {op for op in {a.operator for a in state.transcripts.agents}
            if (last := last_under(state, op, None, since)) is not None and last[1].left}
    runs: list[str] = []
    for op in sorted(ops):
        command = under_command(op)
        last = last_under(state, op, since, until)
        if last is None:
            if any(c.result is not None for c in under_calls(state, op, since, until)):
                return Undecided(mctx("the output of `{command}` does not read as "
                                      "`profile_runs.py --help under` gives it").format(
                    command=command))
            return Bash(command, f"under {op}", occasion=str(since))
        if last[0].error:
            return Undecided(mctx("`{command}` failed").format(command=command))
        runs += last[1].taken
    return runs
