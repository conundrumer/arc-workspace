"""After a batch: once every agent of a batch has returned, the release of
tickets, a code review where the batch merged a change to the code, a
standing doc review where the batch merged a change, and two agents
launched for the rest, one on the profile of the batch's runs and one,
where the batch merged a change, on the gate's timings and outputs.

A batch is the agents the session's operators launched since the launch
of the previous batch's profile agent, other than the agents of After a
batch, the standing doc reviews and the process assessments, with the
changes merged since: those an operator's merge call merged, as
`state.Merge` reads it, and those the coordinator gives as merged. The
launch of the profile agent opens the next batch.

A process assessment, a ticket analyst, launches at the end of a batch
once `ASSESS_AFTER` commits of `master` that change the agents' processes
stand since the launch of the last one an operator of the session
launched, or since the session's start where none was, and none runs. No
batch holds it, so no profile launch waits on its run.

A standing doc review is a doc reviewer on one reader's whole context at
the head of `master`: the first reader of `State.readers` that no tag
records, or, where each has one, the reader whose tag points at the
oldest commit.

The profile agent profiles each run `profile_runs.py --under` takes, and
may launch a transcript review only of those that are members of the
batch: a review of After a batch's own runs files tickets whose triage
opens the next batch. The ticket analyst on the tickets the
batch filed is the one `triage` launches on any open ticket."""

import re
from dataclasses import dataclass

from controlled_markdown import mctx
from operations import briefs
from operations.changes import release
from operations.filing import scratch_dir
from operations.directives import Directive, numbers
from operations.roles import AGENT_ID, Purpose, Role, analyst_of, analyst_subject
from operations.state import DOC_REVIEW, Agent, Merge, State
from operations.handled import bash_calls
from operations.steps import Bash, Launch, Step, Undecided

OWN = frozenset({Role.BATCH_PROFILE, Role.BATCH_GATE, Role.CODE_REVIEWER})
"""The roles of After a batch, which no batch holds."""



def start(state: State, before: float | None = None) -> float:
    """The launch time of the last profile launch, of those before
    `before` where it is given, or 0.0 where there is none."""
    return max((p.launched for p in state.agents_of(Role.BATCH_PROFILE)
                if before is None or p.launched < before), default=0.0)


def members(state: State, since: float) -> list[Agent]:
    return [a for a in state.agents if a.launched > since and not follows(a.role, a.subject)]


def followed(state: State, at: float) -> list[Agent]:
    """The members of the batch that a launch of After a batch made at
    `at` follows: the batch opened by the last profile launch before it."""
    return [a for a in members(state, start(state, at)) if a.launched < at]


def follows(role: Role, subject: str) -> bool:
    """Whether a launch of `role` on `subject` is one no batch holds: one
    of After a batch, a standing doc review or a process assessment."""
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
    return (any(c.time > since and c.merge is Merge.MERGED for c in state.calls)
            or any(t > since for _, t in numbers(state, Directive.MERGED)))


def step(state: State) -> Step | None:
    since = start(state)
    batch = members(state, since)
    merges = merged(state, since)
    if not batch and not merges:
        return None
    if any(a.pending for a in batch):
        return None
    if (s := release(state)) is not None:
        return s
    if merges and any(c.code and c.time > since for c in state.commits):
        reviewers = [a for a in state.agents_of(Role.CODE_REVIEWER) if a.launched > since]
        if not reviewers:
            if state.code_review is None:
                return Undecided("no `code-review/<n>` tag gives the last code review's baseline")
            return Launch(Role.CODE_REVIEWER, f"code-review/{state.code_review + 1}",
                          briefs.code_review(state.code_review, scratch_dir("code-review", state.scratch)))
        if reviewers[-1].pending:
            return None
    if merges:
        reviews = [a for a in state.agents if standing(a.role, a.subject) and a.launched > since]
        if not reviews:
            return doc_review(state)
        if reviews[-1].pending:
            return None
    n = len(state.agents_of(Role.BATCH_PROFILE)) + 1
    head = state.commits[0].hash
    if merges and not any(a.launched > since for a in state.agents_of(Role.BATCH_GATE)):
        return Launch(Role.BATCH_GATE, str(n), briefs.batch_gate(scratch_dir(f"batch-{n}", state.scratch)))
    runs: list[str] = []
    for op in sorted({a.operator for a in batch} or {state.me}):
        command = under_command(op)
        calls = [(c, u) for c in bash_calls(state, command) if c.time > since
                 and c.result is not None and (u := read_under(c.result)) is not None]
        if not calls:
            return Bash(command)
        if calls[-1][0].error:
            return Undecided(mctx("`{command}` failed").format(command=command))
        runs += calls[-1][1].taken
    if (s := assessment(state)) is not None:
        return s
    ids = {a.agent_id for a in batch}
    return Launch(Role.BATCH_PROFILE, str(n),
                  briefs.batch_profile(runs, [r for r in runs if r in ids], head))


def doc_review(state: State) -> Step:
    """The launch of a standing doc review, on the reader it is due on."""
    if not state.readers:
        return Undecided(mctx("no reader is listed for a standing doc review"))
    if state.doc_reviews is None:
        return Undecided(mctx("a `doc-review/<reader>` tag does not read as a commit"))
    times = state.doc_reviews
    unreviewed = [r for r in state.readers if r.tag not in times]
    reader = unreviewed[0] if unreviewed else min(state.readers, key=lambda r: times[r.tag])
    return Launch(Role.DOC_REVIEWER, reader.tag,
                  briefs.standing_doc_review(" ".join((reader.name, *reader.args)), reader.tag,
                                             state.commits[0].hash, state.me))


ASSESS_AFTER = 20


def assessment(state: State) -> Step | None:
    """The launch of a process assessment, where one is due."""
    past = [a for a in state.agents if assesses(a.role, a.subject)]
    if past and past[-1].pending:
        return None
    since = past[-1].launched if past else state.started
    if len({c.hash for c in state.commits if c.process and c.time > since}) < ASSESS_AFTER:
        return None
    return Launch(Role.TICKET_ANALYST, analyst_subject(Purpose.ASSESS, str(len(past) + 1)),
                  briefs.process_assessment(state.me))


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
