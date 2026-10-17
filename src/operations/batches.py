"""After a batch: once every agent of a batch has returned, or once the
batch has stood `BATCH_SPAN` since its first launch, the release of
tickets, a code review where the batch merged a change to the code, a
standing doc review where the batch merged a change, and two agents
launched for the rest, one on the profile of the batch's runs and one,
where the batch merged a change, on the gate's timings and outputs.

A batch is the agents the session's operators launched since the launch
of the previous batch's profile agent, other than the agents of After a
batch, the standing doc reviews, the process assessments and the cost
audits, with the changes merged since: those an operator's merge call merged, as
`state.Merge` reads it, and those the coordinator gives as merged. The
launch of the profile agent opens the next batch.

The sweep (`file_ticket.py sweep`) runs once a profile launch closes a
batch, where a `validation` ticket of the session stands under `tickets/deferred/`,
and no call of it on the runs of the batch that profile launch closed, the
runs the profile's brief gives, was made since that launch. No batch
holds it, so no profile launch waits on it.

The check of the script calls (`scripts/check_script_calls.py`) runs
once a profile launch closes a batch, where no call of it was made since
that launch, on the calls since the closed batch's start. No batch holds
it, so no profile launch waits on it.

A process assessment, a ticket analyst, launches at the end of a batch
once `ASSESS_AFTER` commits of `master` that change the agents' processes
stand since the launch of the last one an operator of the session
launched, or since the session's start where none was, and none runs. No
batch holds it, so no profile launch waits on its run.

A cost audit launches at any step, with no wait on a batch's end, once
the spend of its window (`state.AuditWindow`) is at least `AUDIT_AFTER`, and
the last cost audit an operator of the session launched does not run.
No batch holds it, so no profile launch waits on its run.

A standing doc review is a doc reviewer on one reader's whole context at
the head of `master`: the first reader of `State.readers` that no tag
records, or, where each has one, the reader whose tag points at the
oldest commit.

The profile agent profiles each run `profile_runs.py --under` takes, and
may launch a transcript review only of those that no batch holds: a
review of After a batch's own runs files tickets whose triage opens the
next batch. The ticket analyst on the tickets the
batch filed is the one `triage` launches on any open ticket."""

import re
import shlex
from dataclasses import dataclass

import script_calls

from controlled_markdown import mctx
from operations import briefs
from operations.taking import release
from operations.filing import scratch_dir
from operations.directives import Directive, numbers
from operations.roles import AGENT_ID, Purpose, Role, analyst_of, analyst_subject
from operations.state import DOC_REVIEW, Agent, Call, Merge, State, NotComputed, code_review_tag
from operations.handled import bash_calls, done
from operations.steps import Bash, Launch, Step, Undecided
from operations.log_commands import FILE_TICKET
from ticketing.times import utc_stamp
from ticketing.vocabulary import Kind, Status

OWN = frozenset({Role.BATCH_PROFILE, Role.BATCH_GATE, Role.CODE_REVIEWER, Role.COST_AUDIT})
"""The roles of After a batch and the cost audit, which no batch holds."""

BATCH_SPAN = 3600
"""The seconds since a batch's first launch after which the batch closes
with members pending."""


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
    merges = merged(state, since)
    if not batch and not merges:
        return None
    if any(a.pending for a in batch) and state.now - min(a.launched for a in batch) < BATCH_SPAN:
        return None
    if (s := release(state)) is not None:
        return s
    if merges and any(c.code and c.time > since for c in state.git.commits):
        reviewers = [a for a in state.agents_of(Role.CODE_REVIEWER) if a.launched > since]
        if not reviewers:
            if state.git.code_review is None:
                return Undecided("no `code-review/<n>` tag gives the last code review's baseline")
            return Launch(Role.CODE_REVIEWER, code_review_tag(state.git.code_review + 1),
                          briefs.code_review(state.git.code_review, scratch_dir("code-review", state.scratch)),
                          occasion=str(since))
        if reviewers[-1].pending:
            return None
    if merges:
        reviews = [a for a in state.transcripts.agents if standing(a.role, a.subject) and a.launched > since]
        if not reviews:
            return doc_review(state)
        if reviews[-1].pending:
            return None
    n = len(state.agents_of(Role.BATCH_PROFILE)) + 1
    head = state.git.commits[0].hash
    if merges and not any(a.launched > since for a in state.agents_of(Role.BATCH_GATE)):
        return Launch(Role.BATCH_GATE, str(n), briefs.batch_gate(scratch_dir(f"batch-{n}", state.scratch)),
                      occasion=str(since))
    runs = batch_runs(state, batch, since, None)
    if not isinstance(runs, list):
        return runs
    if (s := assessment(state)) is not None:
        return s
    ids = {a.agent_id for a in batched(state)}
    return Launch(Role.BATCH_PROFILE, str(n),
                  briefs.batch_profile(runs, [r for r in runs if r in ids], head), occasion=str(since))


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


def doc_review(state: State) -> Step:
    """The launch of a standing doc review, on the reader it is due on."""
    readers = state.readers.value
    if not readers:
        return Undecided(mctx("no reader is listed for a standing doc review"))
    if state.git.doc_reviews is None:
        return Undecided(mctx("a `doc-review/<reader>` tag does not read as a commit"))
    times = state.git.doc_reviews
    unreviewed = [r for r in readers if r.tag not in times]
    reader = unreviewed[0] if unreviewed else min(readers, key=lambda r: times[r.tag])
    return Launch(Role.DOC_REVIEWER, reader.tag,
                  briefs.standing_doc_review(" ".join((reader.name, *reader.args)), reader.tag,
                                             state.git.commits[0].hash, state.me),
                  occasion=state.git.commits[0].hash)


ASSESS_AFTER = 20


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


AUDIT_AFTER = 200.0
"""The spend, in dollars, of a cost audit's window at which it launches."""


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
    """Step 1 of After a batch, which an operator runs itself: the
    previous call of `--under` that `profile_runs.py --help under` defines is an
    operator's, and `read_under` gives whether a call of it stands."""
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
