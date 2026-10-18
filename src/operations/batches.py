"""After a batch, and the standing doc reviews, the gate, the process
assessment and the cost audit.

No batch holds the sweep and the script check (`after_profile`), nor
the launches `unbatched` declares: the profile agent of After a batch,
the code and lib reviews (`reviews`), the gate, the standing doc review,
the process assessment and the cost audit. So no profile launch waits on
them.

After a batch: once every agent of a batch has returned, or once the
batch has stood `BATCH_SPAN` since its first launch, the release of
tickets, and an agent on the profile of the batch's runs.

A batch is the agents the session's operators launched since the launch
of the previous batch's profile agent, other than those no batch holds,
with the changes merged since: those an operator's merge call merged, as
`state.Merge` reads it, and those the coordinator gives as merged. The
launch of the profile agent opens the next batch.

The launches that only an operator of the main session makes are those
`main_session.main_only` gives.

A standing doc review launches at any step where none runs and a change
merged after the launch of the last one an operator of the session
launched: where the head of `master` is not the commit that launch's
brief gives. `master` only fast-forwards, so another head means a change
merged after that launch, whichever session merged it. Where none was
launched, or its brief gives no commit, it launches where a commit of
`master` has a time after the session's start.

A standing doc review also launches at any step on an overdue reader: one
that no tag records, or whose tag points at a commit older than
`STANDING_SPAN` that a later commit of `master` follows, where no
standing doc review of the session on that reader runs or launched after
the head commit of `master`. Each step launches the first overdue reader
of `State.readers`, so the overdue readers launch in turn, with no wait
on each other's runs.

A gate agent, on the gate's outputs, launches at any step
where a change merged since the last one an operator of the session
launched, or since the session's start where none was, none runs, and
that last launch stands at least `BATCH_SPAN` back.

A process assessment, a ticket analyst, launches at any step once
`ASSESS_AFTER` commits of `master` that change the agents' processes
stand since the launch of the last one an operator of the session
launched, or since the session's start where none was, and none runs.

A cost audit launches at any step once the priced spend of its window
(`state.AuditWindow`), a lower bound of its spend, is at least
`AUDIT_AFTER`, and the last cost audit
an operator of the session launched does not run.

A standing doc review is a doc reviewer on one reader's whole context at
the head of `master`. The one that launches after a merge is on the
first of the readers of `State.readers` that no standing doc review of
the session runs on that no tag records, or, where each of those has
one, on the one whose tag points at the oldest commit.

The profile agent profiles each run `profile_runs.py --under` takes, and
may launch a transcript review only of those a batch holds: a review of
the runs no batch holds, After a batch's own among them, files tickets
whose triage opens the next batch. The ticket analyst on the tickets the
batch filed is the one `triage` launches on any open ticket."""

from controlled_markdown import mctx
from operations import briefs
from operations.taking import release
from operations.filing import scratch_dir
from operations.directives import Directive, numbers
from operations.roles import Purpose, analyst_subject
from operations.main_session import main_only
from operations.state import Agent, Merge, NotComputed, Reader, State
from operations.steps import Bash, Launch, Step, Undecided
from operations.under_reads import last_under, under_calls, under_command
from operations.unbatched import ASSESSMENT, COST_AUDIT, GATE, PROFILE, STANDING, follows

BATCH_SPAN = 3600
"""The seconds since a batch's first launch after which the batch closes
with members pending, and the least span between two gate launches."""

STANDING_SPAN = 86400
"""The age, in seconds, of the commit a reader's standing doc review tag
points at, past which the reader is overdue where a later commit of
`master` follows that commit."""


def start(state: State, before: float | None = None) -> float:
    """The launch time of the last profile launch, of those before
    `before` where it is given, or 0.0 where there is none."""
    return max((p.launched for p in PROFILE.agents(state)
                if before is None or p.launched < before), default=0.0)


def members(state: State, since: float) -> list[Agent]:
    return [a for a in batched(state) if a.launched > since]


def batched(state: State) -> list[Agent]:
    """The agents of the session that a batch holds."""
    return [a for a in state.transcripts.agents if not follows(a.role, a.subject)]


def followed(state: State, at: float) -> list[Agent]:
    """The members of the batch that a launch of After a batch made at
    `at` follows: the batch opened by the last profile launch before it."""
    return [a for a in members(state, start(state, at)) if a.launched < at]


def merged(state: State, since: float) -> bool:
    return (any(c.time > since and c.merge is Merge.MERGED for c in state.transcripts.calls)
            or any(t > since for _, t in numbers(state, Directive.MERGED)))


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


def next_number(past: list[Agent]) -> str:
    """The subject of the next launch of the kind whose launches are
    `past`: its number, counted from 1."""
    return str(len(past) + 1)


@main_only
def standing_review(state: State) -> Step | None:
    """The launch of a standing doc review, where one is due."""
    past = STANDING.agents(state)
    if opened(state, past) is None:
        return None
    commit = briefs.standing_commit(past[-1].brief) if past else None
    if commit is None:
        due = any(c.time > state.started for c in state.git.commits)
    else:
        due = state.git.commits[0].hash != commit
    return doc_review(state) if due else None


@main_only
def overdue_review(state: State) -> Step | None:
    """The launch of a standing doc review on an overdue reader, where one
    is due."""
    readers = state.readers.value
    if not readers:
        return None
    times = state.git.doc_reviews
    if times is None:
        return Undecided(UNREAD_TAGS)
    head = state.git.commits[0]
    past = STANDING.agents(state)
    left = {a.subject for a in past if a.pending or a.launched > head.time}

    def overdue(r: Reader) -> bool:
        t = times.get(r.tag)
        return t is None or (t < state.now - STANDING_SPAN and any(c.time > t for c in state.git.commits))

    reader = next((r for r in readers if r.tag not in left and overdue(r)), None)
    return None if reader is None else standing_launch(state, reader)


def gate(state: State) -> Step | None:
    """The launch of a gate agent, where one is due."""
    past = GATE.agents(state)
    since = merged_since(state, past)
    if since is None or (past and state.now - since < BATCH_SPAN):
        return None
    n = next_number(past)
    return Launch(GATE.role, n, briefs.batch_gate(scratch_dir(f"batch-{n}", state.scratch)),
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


UNREAD_TAGS = mctx("a `doc-review/<reader>` tag does not read as a commit")


def doc_review(state: State) -> Step | None:
    """The launch of a standing doc review, on the reader it is due on."""
    readers = state.readers.value
    if not readers:
        return Undecided(mctx("no reader is listed for a standing doc review"))
    if state.git.doc_reviews is None:
        return Undecided(UNREAD_TAGS)
    times = state.git.doc_reviews
    running = {a.subject for a in STANDING.agents(state) if a.pending}
    free = [r for r in readers if r.tag not in running]
    if not free:
        return None
    unreviewed = [r for r in free if r.tag not in times]
    return standing_launch(state, unreviewed[0] if unreviewed else min(free, key=lambda r: times[r.tag]))


def standing_launch(state: State, reader: Reader) -> Launch:
    """The launch of a standing doc review on `reader`, at the head of
    `master`."""
    return Launch(STANDING.role, reader.tag,
                  briefs.standing_doc_review(" ".join((reader.name, *reader.args)), reader.tag,
                                             state.git.commits[0].hash, state.me),
                  occasion=state.git.commits[0].hash)


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


def opened(state: State, past: list[Agent]) -> float | None:
    """The time from which the next launch of the kind whose launches are
    `past` counts what stands: the launch of the last of `past`, or the
    session's start where `past` is empty. None where the last of `past`
    runs."""
    if past and past[-1].pending:
        return None
    return past[-1].launched if past else state.started


def merged_since(state: State, past: list[Agent]) -> float | None:
    """`opened` of `past`, where the session merged a change since that
    time; None otherwise."""
    since = opened(state, past)
    return since if since is not None and merged(state, since) else None


AUDIT_AFTER = 200.0
"""The spend, in dollars, of a cost audit's window at which it launches."""


@main_only
def audit(state: State) -> Step | None:
    """The launch of a cost audit, where one is due."""
    past = COST_AUDIT.agents(state)
    if opened(state, past) is None:
        return None
    window = state.computed.audit_window
    if isinstance(window, NotComputed):
        return Undecided(mctx("the window of the next cost audit is unknown: {why}").format(why=window.why))
    if window.priced_spend < AUDIT_AFTER:
        return None
    return Launch(COST_AUDIT.role, next_number(past),
                  briefs.cost_audit(window.start, state.transcripts_dir, state.me),
                  occasion=str(window.start))
