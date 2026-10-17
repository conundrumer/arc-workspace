"""After a batch, and the reviews, the gate, the process assessment and
the cost audit, which no batch holds.

After a batch: once every agent of a batch has returned, or once the
batch has stood `BATCH_SPAN` since its first launch, the release of
tickets, and an agent on the profile of the batch's runs.

A batch is the agents the session's operators launched since the launch
of the previous batch's profile agent, other than the agents of After a
batch, the code reviews, the lib reviews, the gates, the standing doc
reviews, the process assessments and the cost audits, with the changes
merged since: those an operator's merge call merged, as `state.Merge`
reads it, and those the coordinator gives as merged. The launch of the profile agent opens the
next batch.

The sweep (`file_ticket.py sweep`) runs once a profile launch closes a
batch, where a `validation` ticket of the session stands under `tickets/deferred/`,
and no call of it on the runs of the batch that profile launch closed, the
runs the profile's brief gives, was made since that launch. No batch
holds it, so no profile launch waits on it.

The check of the script calls (`scripts/check_script_calls.py`) runs
once a profile launch closes a batch, where no call of it was made since
that launch, on the calls since the closed batch's start. No batch holds
it, so no profile launch waits on it.

The code review, the lib review, the standing doc reviews, the process
assessment and the cost audit launch only at a step of an operator of
the main session, as `file_ticket.py main --help-all` gives it, so that
concurrent sessions launch each of them once. An operator of another
session launches none of them.

Each review of `state.Review`, the code review and the lib review,
launches at any step where a commit of `master` that changes the paths it reviews is one
the tag of its last baseline does not reach, and no reviewer of its role
of the session runs. Its occasion is the newest such commit, so a review
that ended with no tag launches again only once newer code of its paths
merges. Where the read gives no baseline (`NoBaseline`), the unreviewed
commits are unknown, and the step is undecided on the newest commit of
`master` that changes its paths, so that an operator hands it on once
for each such commit.

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

A gate agent, on the gate's timings and outputs, launches at any step
where a change merged since the last one an operator of the session
launched, or since the session's start where none was, none runs, and
that last launch stands at least `BATCH_SPAN` back.

A process assessment, a ticket analyst, launches at any step once
`ASSESS_AFTER` commits of `master` that change the agents' processes
stand since the launch of the last one an operator of the session
launched, or since the session's start where none was, and none runs.

A cost audit launches at any step once the spend of its window
(`state.AuditWindow`) is at least `AUDIT_AFTER`, and the last cost audit
an operator of the session launched does not run.

No batch holds a code review, a lib review, a gate, a standing doc
review, a process assessment or a cost audit, so no profile launch waits
on its run.

A standing doc review is a doc reviewer on one reader's whole context at
the head of `master`. The one that launches after a merge is on the
first of the readers of `State.readers` that no standing doc review of
the session runs on that no tag records, or, where each of those has
one, on the one whose tag points at the oldest commit.

The profile agent profiles each run `profile_runs.py --under` takes, and
may launch a transcript review only of those that no batch holds: a
review of After a batch's own runs files tickets whose triage opens the
next batch. The ticket analyst on the tickets the
batch filed is the one `triage` launches on any open ticket."""

import re
import shlex
from collections.abc import Callable
from dataclasses import dataclass
from functools import wraps

import script_calls

from controlled_markdown import mctx
from operations import briefs
from operations.taking import release
from operations.filing import scratch_dir
from operations.directives import Directive, numbers
from operations.roles import AGENT_ID, Purpose, Role, analyst_of, analyst_subject
from operations.state import (DOC_REVIEW, Agent, Call, Merge, NoBaseline, NotComputed, Reader, Review,
                              State)
from operations.handled import bash_calls, done
from operations.steps import Bash, Launch, Step, Undecided
from operations.log_commands import FILE_TICKET
from ticketing.times import utc_stamp
from ticketing.vocabulary import Kind, Status

OWN = frozenset({Role.BATCH_PROFILE, Role.BATCH_GATE, Role.CODE_REVIEWER, Role.LIB_REVIEWER,
                 Role.COST_AUDIT})
"""The roles of After a batch, the code review, the lib review, the gate
and the cost audit, which no batch holds."""

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
    return max((p.launched for p in state.agents_of(Role.BATCH_PROFILE)
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


def follows(role: Role, subject: str) -> bool:
    """Whether a launch of `role` on `subject` is one no batch holds."""
    return role in OWN or standing(role, subject) or assesses(role, subject)


def standing(role: Role, subject: str) -> bool:
    """Whether a launch of `role` on `subject` is a standing doc review."""
    return role is Role.DOC_REVIEWER and subject.startswith(DOC_REVIEW)


def assesses(role: Role, subject: str) -> bool:
    """Whether a launch of `role` on `subject` is a process assessment."""
    parsed = analysis(role, subject)
    return parsed is not None and parsed[0] is Purpose.ASSESS


def analysis(role: Role, subject: str) -> tuple[Purpose, str] | None:
    """The purpose and the rest of the subject of a launch of `role` on
    `subject`, or None where it is no ticket analyst's or its subject opens
    with no purpose."""
    return analyst_of(subject) if role is Role.TICKET_ANALYST else None


def merged(state: State, since: float) -> bool:
    return (any(c.time > since and c.merge is Merge.MERGED for c in state.transcripts.calls)
            or any(t > since for _, t in numbers(state, Directive.MERGED)))


def step(state: State) -> Step | None:
    if (s := validation(state)) is not None:
        return s
    if (s := script_check(state)) is not None:
        return s
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
    n = len(state.agents_of(Role.BATCH_PROFILE)) + 1
    ids = {a.agent_id for a in batched(state)}
    return Launch(Role.BATCH_PROFILE, str(n),
                  briefs.batch_profile(runs, [r for r in runs if r in ids], state.git.commits[0].hash),
                  occasion=str(since))


def main_only(procedure: Callable[[State], Step | None]) -> Callable[[State], Step | None]:
    """`procedure`, giving no step where the session is not the main."""
    @wraps(procedure)
    def guarded(state: State) -> Step | None:
        return procedure(state) if state.sessions.main else None
    return guarded


@main_only
def code_review(state: State) -> Step | None:
    return review(state, Review.CODE)


@main_only
def lib_review(state: State) -> Step | None:
    return review(state, Review.LIB)


def review(state: State, of: Review) -> Step | None:
    """The launch of the review `of`, where one is due."""
    if any(a.pending for a in state.agents_of(of.role)):
        return None
    baseline = state.git.reviews[of]
    if isinstance(baseline, NoBaseline):
        newest = next((c.hash for c in state.git.commits if of in c.reviews), None)
        if newest is None:
            return None
        return Undecided(mctx("the last {name}'s baseline, its `{prefix}<n>` tag of the highest `<n>`, is "
                              "unknown, with `{commit}` the newest "
                              "commit of `master` that changes the paths it reviews: {why}").format(
            name=of.noun, prefix=of.value, commit=newest, why=baseline.value))
    if not baseline.unreviewed:
        return None
    return Launch(of.role, of.tag(baseline.number + 1),
                  briefs.review(of, baseline.number, scratch_dir(of.stem, state.scratch)),
                  occasion=baseline.unreviewed[0])


def standing_reviews(state: State) -> list[Agent]:
    return [a for a in state.transcripts.agents if standing(a.role, a.subject)]


@main_only
def standing_review(state: State) -> Step | None:
    """The launch of a standing doc review, where one is due."""
    past = standing_reviews(state)
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
    past = standing_reviews(state)
    left = {a.subject for a in past if a.pending or a.launched > head.time}

    def overdue(r: Reader) -> bool:
        t = times.get(r.tag)
        return t is None or (t < state.now - STANDING_SPAN and any(c.time > t for c in state.git.commits))

    reader = next((r for r in readers if r.tag not in left and overdue(r)), None)
    return None if reader is None else standing_launch(state, reader)


def gate(state: State) -> Step | None:
    """The launch of a gate agent, where one is due."""
    past = state.agents_of(Role.BATCH_GATE)
    since = merged_since(state, past)
    if since is None or (past and state.now - since < BATCH_SPAN):
        return None
    n = len(past) + 1
    return Launch(Role.BATCH_GATE, str(n), briefs.batch_gate(scratch_dir(f"batch-{n}", state.scratch)),
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


def validation(state: State) -> Step | None:
    """The sweep of the batch the last profile launch closed, where one is
    due."""
    profiles = state.agents_of(Role.BATCH_PROFILE)
    if not profiles:
        return None
    closing = profiles[-1].launched
    if not any(t.kind is Kind.VALIDATION and t.status is Status.DEFERRED and state.mine(t)
               for t in state.tracker.tickets.values()):
        return None
    runs = batch_runs(state, followed(state, closing), start(state, closing), closing)
    # No batch waits on the sweep: where the runs do not read, the `validation`
    # tickets stay under `deferred` for the next profile launch.
    if not isinstance(runs, list):
        return None
    sweep = Bash(sweep_command(runs), "sweep", occasion=str(closing))
    return None if done(state, sweep) else sweep


def script_check(state: State) -> Step | None:
    """The check of the script calls since the start of the batch the last
    profile launch closed, where one is due; where that batch has no start,
    of the calls of the window before that launch."""
    profiles = state.agents_of(Role.BATCH_PROFILE)
    if not profiles:
        return None
    closing = profiles[-1].launched
    since = start(state, closing) or closing - script_calls.WINDOW_SECONDS
    check = Bash(check_command(since), "script check", occasion=str(closing))
    return None if done(state, check) else check


def check_command(since: float) -> str:
    return f"uv run python scripts/check_script_calls.py --since {utc_stamp(since)}"


def sweep_command(runs: list[str]) -> str:
    return shlex.join([*FILE_TICKET, "sweep", *runs])


UNREAD_TAGS = mctx("a `doc-review/<reader>` tag does not read as a commit")


def doc_review(state: State) -> Step | None:
    """The launch of a standing doc review, on the reader it is due on."""
    readers = state.readers.value
    if not readers:
        return Undecided(mctx("no reader is listed for a standing doc review"))
    if state.git.doc_reviews is None:
        return Undecided(UNREAD_TAGS)
    times = state.git.doc_reviews
    running = {a.subject for a in standing_reviews(state) if a.pending}
    free = [r for r in readers if r.tag not in running]
    if not free:
        return None
    unreviewed = [r for r in free if r.tag not in times]
    return standing_launch(state, unreviewed[0] if unreviewed else min(free, key=lambda r: times[r.tag]))


def standing_launch(state: State, reader: Reader) -> Launch:
    """The launch of a standing doc review on `reader`, at the head of
    `master`."""
    return Launch(Role.DOC_REVIEWER, reader.tag,
                  briefs.standing_doc_review(" ".join((reader.name, *reader.args)), reader.tag,
                                             state.git.commits[0].hash, state.me),
                  occasion=state.git.commits[0].hash)


ASSESS_AFTER = 20


@main_only
def assessment(state: State) -> Step | None:
    """The launch of a process assessment, where one is due."""
    past = [a for a in state.transcripts.agents if assesses(a.role, a.subject)]
    since = opened(state, past)
    if since is None or len({c.hash for c in state.git.commits if c.process and c.time > since}) < ASSESS_AFTER:
        return None
    return Launch(Role.TICKET_ANALYST, analyst_subject(Purpose.ASSESS, str(len(past) + 1)),
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
    past = state.agents_of(Role.COST_AUDIT)
    if opened(state, past) is None:
        return None
    window = state.computed.audit_window
    if isinstance(window, NotComputed):
        return Undecided(mctx("the window of the next cost audit is unknown: {why}").format(why=window.why))
    if window.spend < AUDIT_AFTER:
        return None
    return Launch(Role.COST_AUDIT, str(len(past) + 1),
                  briefs.cost_audit(window.start, state.transcripts_dir, state.me),
                  occasion=str(window.start))


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
    """The last call of `--under` on `operator`, of those made after
    `since` and before `until`, each where it is given, whose output
    `read_under` reads, with what it reads; None where there is none."""
    calls = [(c, u) for c in under_calls(state, operator, since, until)
             if c.result is not None and (u := read_under(c.result)) is not None]
    return calls[-1] if calls else None


def under_calls(state: State, operator: str, since: float | None,
                until: float | None) -> list[Call]:
    """The calls of `--under` on `operator`, of those made after `since`
    and before `until`, each where it is given."""
    return [c for c in bash_calls(state, under_command(operator))
            if (since is None or c.time > since) and (until is None or c.time < until)]
