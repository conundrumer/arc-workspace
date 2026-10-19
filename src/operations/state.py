"""The state the operator's procedures read, as `scripts/operate.py` reads
it from the ticket tracker, git, the worktrees, the transcripts of the
session's operators, and those of the operators of another session on a
change `me` holds.
"""

import re
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from functools import cached_property, wraps
from enum import Enum, StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

from controlled_markdown import form, mctx
from handbook.reader_names import ReaderName
from operations.roles import Model, Purpose, Role, analyst_of, subjects
from ticketing.vocabulary import Domain, Kind, Resolution, Status

if TYPE_CHECKING:
    from operations.journal import Journal
    from operations.pacing import Pace


@dataclass(frozen=True, slots=True)
class LogLine:
    """A line of a ticket's log: its time, the status it leaves the ticket
    in, the agent name and the agent id its bracket gives, and its note.
    `on_user` is whether the note opens with the wait on the user, and
    `on_change` the number of the change the note opens with a wait on.
    `waits` is whether the note opens with a wait of any kind.
    `resolution` is the resolution the note opens with, `closed_by`
    the number of the change a note of the form `ticket_log.CLOSED_BY`
    gives, and `duplicate_of` the number of the ticket a note of the form
    `ticket_log.DUPLICATE_OF` gives."""
    time: float
    status: Status
    agent: str
    agent_id: str | None
    note: str
    on_user: bool
    on_change: str | None
    waits: bool
    resolution: Resolution | None
    closed_by: str | None
    duplicate_of: str | None


@dataclass(frozen=True)
class Unread:
    """A ticket file the operator's read refused or failed on, which no
    procedure reads as a ticket: `why` is the read's failure, `digest` a
    digest of the file's bytes, so that each content it has gives its own
    step, or where those bytes do not read, of that failure's text,
    `modified` the time of its last write, or 0 where that time does not
    read, and `session` the session index of the ticket number its file
    name gives, None where that number is bare or the parser of ticket
    file names refuses the name."""
    path: Path
    why: str
    digest: str
    modified: float
    session: int | None


@dataclass(frozen=True, slots=True)
class Ticket:
    """A ticket of the tracker. `editors` is None where a `change` gives no
    `editors` field, `mechanical` is whether a `change` gives the
    `mechanical` field, `motivation` holds the ticket numbers its
    `## Motivation` section gives, `log` holds the lines of its log other
    than its allow lines, `allowers` the session ids of those allow lines,
    each once, in the order of their first lines, and `holder` is the
    holder `file_ticket.py log --help-all` defines."""
    number: str
    order: tuple[int, int]
    session: int | None
    status: Status
    kind: Kind
    domain: Domain
    subject: str
    filer: str
    filed: float
    title: str
    depends_on: tuple[str, ...]
    motivation: tuple[str, ...]
    editors: tuple[Role, ...] | None
    after_merge: str | None
    mechanical: bool
    log: tuple[LogLine, ...]
    allowers: tuple[str, ...]
    holder: str | None
    path: Path

    @property
    def last_time(self) -> float:
        """The time of the last line of its log, or of its filing where the
        log has none: the occasion of a step on it with no event of its
        own (`steps.key`)."""
        return self.log[-1].time if self.log else self.filed

    def model(self, role: Role) -> Model | None:
        """The model a launch of `role` on this ticket gives: Sonnet for a
        code editor of a `mechanical` change, in place of the one the
        agent's document gives, and otherwise None, for the one the
        agent's document gives."""
        return Model.SONNET if self.mechanical and role is Role.CODE_EDITOR else None


@dataclass(frozen=True)
class Report:
    """A report of an agent that reached the operator that launched it: a
    notification, the result of a foreground launch, or a message, with
    the text the agent wrote, as `agent_reports` reads it, and the report
    file that text was read from, or None where it was read from none."""
    time: float
    text: str
    file: Path | None = None


@dataclass(frozen=True)
class LateResume:
    """A resume of an operator after `later`, a later operator of the
    session, made its first entry, at `later_first`, as `resumed_at` in
    `scripts/operator_reads.py` gives a resume, at `time`."""
    time: float
    later: str
    later_first: float


class Waits(Enum):
    """How a pending agent waits. `STILL_RUNNING`: it stopped with work of
    its own still running, has not reported yet, and the operator's turn
    may not end on it. `LIMITED`: the usage limit stopped it, it has not
    ended its work, it has not run since, and it waits for a resume (`limit_resume`)."""
    AT_WORK = "at work"
    STILL_RUNNING = "still running"
    LIMITED = "limited"


SETTLED = mctx("What is already settled on change {number} follows.")
"""The line that opens the block of a brief on a change that gives what
the agents launched on it before settled (`briefs.settled_lines`)."""
SETTLED_LINE = re.compile(form(SETTLED, {"number": r"\S+"}))


def own(brief: str) -> str:
    """`brief` cut at its first `SETTLED` line, or the whole of it where it
    has none."""
    lines = brief.split("\n")
    cut = next((i for i, line in enumerate(lines) if SETTLED_LINE.fullmatch(line)), len(lines))
    return "\n".join(lines[:cut])


@dataclass(frozen=True)
class Agent:
    """An agent an operator of any session launched with a description the
    command gave, or a check that an editor an operator launched
    launched (`changes.editor_step`), which is read as a launch of that
    editor's, with the editor as its `operator`. `waits` is None where it
    no longer waits: where that operator holds the result of a launch in the
    foreground, or a sign since its launch or its last resume, in any
    transcript of the session, that its turn ended, as
    `agent_reports.last_sign` gives the latest sign: a notification that
    it stopped, or its SubagentHandback message. A notification that it
    stopped with work of its own still running, or that the usage limit
    stopped it where it has not run since, leaves it waiting, as
    `Waits.STILL_RUNNING` and `Waits.LIMITED` give.
    Where a sign ends it and no report of it reached that operator since
    its launch or its last resume, the final reply in its transcript, where
    it gives one after them and it went to that operator or is the path of
    a report file alone, read from that file, ends its `reports`.
    It no longer waits either where it is in `TranscriptsRead.stalled`, or
    is an agent of another operator whose work is no longer open, and
    the final reply in its transcript, where it gives one and it went to
    that operator or is the path of a report file alone, read from that
    file, then ends its `reports`. `notifies` holds where that
    operator launched or last resumed it itself, so the notification of
    its end and its final reply reach that operator. Where it stopped
    with work of its own still running and it is quiet
    (`TranscriptsRead.quiet`), it no longer waits, and its work ends with
    the reports it has, as for an agent of another operator whose work is
    no longer open.
    `report_file` is the report file the brief it was launched with gives
    (`briefs.REPORT_FILE`, `briefs.REPORT_RULE`), or None where it gives
    none. Where that file is there, its last report, whatever its last
    turn ended with, has that file's text, at the time it was read with,
    whichever of the ways above ends it, and while it waits. Where no file
    is there, as where the agent never wrote it, its reports stay as read,
    and no `undecided` line names the file.
    `brief` is the brief it was launched with cut at its `SETTLED` line
    (`own`), so that no read of it sees the text that block quotes.
    `launched` is the time of its launch, and `since` the time of that
    launch or of the last call of any agent of the session that resumed
    it. `reviewing`, for an editor of `roles.LAUNCHING_EDITORS` that
    waits, is the time of the first of its calls of `operate.py review`
    since its last other tool call, where its last tool call is such a
    call, with or without its result, and None otherwise: its transcript
    holds a call before the call runs, so a call that still runs counts."""
    agent_id: str | None
    operator: str
    role: Role
    subject: str
    brief: str
    launched: float
    since: float
    waits: Waits | None
    reports: tuple[Report, ...]
    notifies: bool
    report_file: Path | None = None
    reviewing: float | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "brief", own(self.brief))

    @property
    def pending(self) -> bool:
        return self.waits is not None

    @property
    def last_report(self) -> Report | None:
        return self.reports[-1] if self.reports else None

    @property
    def unreported(self) -> bool:
        """Whether it no longer waits and gave no report since its launch
        or its last resume, so that it did none of the work it was given."""
        return not self.pending and not any(r.time > self.since for r in self.reports)


def last_reported(agents: Iterable[Agent]) -> float:
    """The time of the latest report of `agents`, or 0.0 where none
    reported: the occasion of a step on their reports (`steps.key`)."""
    return max((r.time for a in agents if (r := a.last_report) is not None), default=0.0)


class Merge(Enum):
    """What a call of `scripts/merge_change.py` did: left edits, where its
    output gives that `master` is fast-forwarded and the worktree stays
    for changes made after the commit (`merge_outcomes.left_edits`), which
    leaves the change unmerged; merged, where `master` otherwise holds a
    commit made at or after the call with the message it gives, whatever
    its exit status; and otherwise, by the forms of its output that
    script gives, never ran, where the output holds no line of that
    script (`merge_outcomes.ran`), as where the harness denied the call.
    A call whose output holds a line of that script and not its footer
    (`merge_outcomes.ended`) was stopped, and has no outcome. A call that
    `pending_wait_hook` denied for its timeout has no outcome either, so
    the merge call is given again, unless the last merge call of its
    command was denied so too, in which case that second denial never ran.
    A call that ended was refused for a conflict in its rebase where its
    output gives the paths that conflict (`merge_outcomes.conflict_paths`), refused
    otherwise where its output holds a refusal line
    (`merge_outcomes.refused`), and failed otherwise, as where it ended on
    a `failed:` line of that script or on a traceback, whatever form its
    output takes."""
    LEFT_EDITS = "left edits"
    MERGED = "merged"
    NOT_RUN = "not run"
    CONFLICT = "conflict"
    REFUSED = "refused"
    FAILED = "failed"


@dataclass(frozen=True)
class Call:
    """A tool call of an operator of the session: its tool, its input, and
    its result, None while it is pending, each with the text of each file
    the command wrote for a call it printed in place of the line that gives
    that file (`printed_forms.FILED_LINE`), with whether the harness gave the
    result as an error, and for a call of `scripts/merge_change.py` that
    has its result, what it did, and for one refused for a conflict in its
    rebase, the paths it conflicts in, which are empty for every other
    call. The result of a Bash call the harness ran
    or moved to the background is the output its command wrote, once a
    notification of its end reached the operator, and it is an error
    where that notification gives a status other than `completed`. The
    result of a call that is not an error is empty, other than that of a
    Bash call that is not a call of `next`: no step reads it."""
    operator: str
    time: float
    tool: str
    input: Mapping[str, Any]
    result: str | None
    error: bool
    merge: Merge | None = None
    conflicts: tuple[str, ...] = ()

    @property
    def message(self) -> str:
        """The message text of a SendMessage call, which the harness takes as
        empty where its input gives none."""
        return str(self.input.get("message", ""))

    @property
    def command(self) -> str:
        """The command of a Bash call, empty where its input gives none."""
        return str(self.input.get("command", ""))


class Tool(StrEnum):
    """A tool an operator calls, by the name the harness gives that tool."""
    AGENT = "Agent"
    SEND_MESSAGE = "SendMessage"
    BASH = "Bash"
    SUBAGENT_HANDBACK = "SubagentHandback"


@dataclass(frozen=True)
class Message:
    """A message that reached an operator: from the coordinator, or from
    the operator launcher that launched it, which passes on the
    coordinator's lines, as its brief or a later message, where `sender`
    is None, or otherwise from the
    agent `sender`, which that operator did not launch."""
    operator: str
    time: float
    sender: str | None
    text: str


@dataclass(frozen=True)
class Commit:
    """A commit of `master`: its hash, its time, the reviews whose paths,
    as `ReviewFacts.paths` gives them, it changes, its subject,
    whether it changes a directory of `tree_reads.PROCESS_DIRS`, a change
    to the agents' processes, and the files it changes."""
    hash: str
    time: float
    reviews: frozenset["Review"]
    subject: str
    process: bool
    files: frozenset[str]


DOC_REVIEW = "doc-review/"
"""What leads the tag of a reader's last standing doc review, and the
subject of a standing doc review's launch."""

class Review(Enum):
    """A review of the code merged to `master` that a tag records, by what
    leads the tag of its baseline and the subject of its launch."""
    CODE = "code-review/"
    LIB = "lib-review/"

    @property
    def facts(self) -> "ReviewFacts":
        return REVIEW_FACTS[self]

    @property
    def role(self) -> Role:
        return self.facts.role

    @property
    def stem(self) -> str:
        """The name of its scratch directory."""
        return self.value.removesuffix("/")

    def tag(self, n: int) -> str:
        return f"{self.value}{n}"

    def number(self, tag: str) -> int | None:
        n = tag.removeprefix(self.value)
        return int(n) if tag.startswith(self.value) and n.isdigit() else None


@dataclass(frozen=True)
class PathSet:
    """A set of paths of the tree, such as those a review covers: each path
    under a prefix of `covered` and under no prefix of `excluded`.
    Iterating it gives the same set as git pathspecs, which
    `review_tag.py commit` stages and prints for the reviewer's diff, so
    the two readings agree."""
    covered: tuple[str, ...]
    excluded: tuple[str, ...] = ()

    def covers(self, path: str) -> bool:
        return path.startswith(self.covered) and not path.startswith(self.excluded)

    def __iter__(self) -> Iterator[str]:
        yield from self.covered
        yield from (f":!{e}" for e in self.excluded)


@dataclass(frozen=True)
class ReviewFacts:
    """What a review is: the role of its reviewer, its noun, the paths it
    covers, and the item of its reviewer's checklist whose completion the
    tag of its baseline needs, by that item's heading text."""
    role: Role
    noun: str
    paths: PathSet
    item: str


REVIEW_FACTS = {
    Review.CODE: ReviewFacts(
        Role.CODE_REVIEWER, mctx("code review"),
        PathSet(("src/", "scripts/", "tests/", "engine/", "theory/", "tools/", ".claude/workflows/",
                 ".claude/settings.json", "justfile"),
                # `tools/console/vendor/` holds third-party code the project does not own.
                ("tools/console/vendor/",)),
        "Find the line-level places"),
    Review.LIB: ReviewFacts(
        Role.LIB_REVIEWER, mctx("lib review"),
        PathSet(("programs/lib.dl", "programs/lib/", "programs/proposers.dl",
                 "programs/lib_functors.cpp")),
        "Find the places"),
}


@dataclass(frozen=True)
class Baseline:
    """A review's last baseline: the highest `<n>` of a tag of its
    baseline, and the hashes of the commits of `master` that change the
    paths it reviews and that tag's commit does not reach, newest first."""
    number: int
    unreviewed: tuple[str, ...]


class NoBaseline(Enum):
    """Why the read gives no `Baseline`."""
    NO_TAG = mctx("no such tag exists")
    GIT_FAILED = mctx("`git log <tag>..master` failed on that tag")


@dataclass(frozen=True)
class Reader:
    """A reader the `context` command knows, with one argument list it
    takes. `tag` is the tag of its last standing doc review."""
    name: ReaderName
    args: tuple[str, ...]

    @property
    def tag(self) -> str:
        return DOC_REVIEW + "-".join((self.name, *self.args))


@dataclass(frozen=True)
class Spend:
    """The spend of runs: their token cost and that of the runs under
    them, their agent-running time, the union of the wall time of all
    those runs, and their cost by the agent type of each run, the runs
    under it summed with it (`scripts/spends.py`)."""
    dollars: float
    seconds: float
    by_role: dict[str, float]


@dataclass(frozen=True)
class Budget:
    """A change's cost budget in dollars and its time budget in seconds,
    with the median spend of each agent type over the changes the budget
    is taken over (`scripts/spends.py`)."""
    dollars: float
    seconds: float
    role_medians: dict[str, float]


@dataclass(frozen=True)
class Place:
    """A fragment by its file, relative to the worktree, and its line, with
    its text, or None for the place of a file that does not read as
    fragments."""
    file: str
    line: int
    text: str | None


@dataclass(frozen=True)
class Start:
    """A pipeline a run script starts: its task and its passes, in their
    order (`runs`)."""
    task: str
    passes: tuple[Role, ...]


type Starts = tuple[Start, ...] | str
"""What a run script gave at a read: its starts, or the text of its fault."""


type Takes = frozenset[str] | str | None
"""What a run script's `takes` gave at a read: the numbers of the tickets
it admits, the text of its fault, or None where the script defines no
`takes`."""


@dataclass(frozen=True)
class PassReport:
    """The read of a solver pass's report file: the numbers of the tickets
    it lists under `## Tickets filed`, or None where the pass wrote no
    such file with that section, and the items of its `## Concept faults`
    section (`reports.section_items`)."""
    tickets: tuple[str, ...] | None
    faults: tuple[str, ...]


@dataclass(frozen=True)
class Stuck:
    """An agent that showed no sign of progress for `STUCK_SECONDS`, or whose
    Bash calls repeated with the same result for it: its `session`, the
    start of that stretch (`since`), and the command line of each span of
    the work of its own still running (`running`)."""
    session: str
    since: float
    running: tuple[str, ...]


@dataclass(frozen=True)
class TranscriptsRead:
    """What the operator reads of the transcripts of the session's
    operators. `agents` holds their launches, in the order of their launch,
    `calls` their calls, with each Bash step the command ran for one of
    them, as the step journal gives it (`scripts/step_journal.py`), in the
    order of their time, and `messages` the messages that reached any of
    them. `late_resumes` gives, for each operator of
    `State.operators`, its resumes, as `resumed_at` in `scripts/operator_reads.py`
    gives them, after
    the next operator of `State.operators` made its first entry, in the
    order of their time. `stalled` gives the final reply in the transcript
    of each agent a stall alert names that reached no operator as a
    report. `quiet` gives the time of the latest sign of progress of each
    agent of `agents` that is quiet, as `quiet_since` in
    `scripts/open_agents.py` gives it, by agent id, read while it was
    pending and the usage limit had not stopped it (`limit_resume` covers
    that agent). `stuck` gives, by agent id, each agent of `quiet`, each
    live holder of a ticket held elsewhere (`plan.elsewhere`) and each
    operator of `plan.earlier_open` that is quiet, and each watched agent
    whose `Watched.stuck` holds.
    `messaged` gives, for each doc reviewer and item checker of `agents`
    and of `elsewhere` whose transcript is known, the agent ids its
    SendMessage calls went to. `limited` gives, by agent id, the time of
    the usage-limit stop of each agent of `agents` and of `elsewhere` whose
    latest sign is that stop and whose own transcript, where it is known,
    holds no entry later than that stop, and, of an agent of `agents`,
    that reports to its operator at that stop (`Agent.notifies`), as an
    agent another agent resumed is that agent's to resume, kept where a
    later read ends the agent, so
    that the work of such an agent of `agents` is resumed once the limit
    lifts. `pass_reports` gives, for each
    solver pass with an agent id, the read of the report file it wrote
    under the task's work directory since its launch (`PassReport`),
    whatever its reply. `elsewhere` holds, for each change `State.me`
    holds whose log gives a line of an operator of another session since
    its last move out of `tickets/draft/`, the agents that operator
    launched on it since then, with the checks its editors launched,
    in the order of their launch. No step sends to one of them: a
    subagent of another session reports to that session."""
    agents: tuple[Agent, ...]
    calls: tuple[Call, ...]
    messages: tuple[Message, ...]
    late_resumes: Mapping[str, tuple[LateResume, ...]]
    stalled: Mapping[str, Report]
    pass_reports: Mapping[str, PassReport]
    quiet: Mapping[str, float]
    stuck: Mapping[str, Stuck]
    elsewhere: tuple[Agent, ...]
    messaged: Mapping[str, frozenset[str]]
    limited: Mapping[str, float]

    @cached_property
    def memo(self) -> dict[tuple[Any, ...], Any]:
        """The results `memoized_by_transcripts` holds for this read, by
        function and arguments, shared by each state that keeps this read."""
        return {}

    @cached_property
    def analysts(self) -> tuple[tuple[Agent, Purpose, list[str]], ...]:
        """Each ticket analyst of `agents`, with its purpose and the ticket
        numbers or the task its subject gives."""
        out: list[tuple[Agent, Purpose, list[str]]] = []
        for a in self.agents:
            if a.role is Role.TICKET_ANALYST and (parsed := analyst_of(a.subject)) is not None:
                out.append((a, parsed[0], subjects(parsed[1])))
        return tuple(out)

    def sent_by(self, a: Agent) -> frozenset[str] | None:
        """The agent ids of `messaged` for `a`, or None where `a` is not a
        doc reviewer or an item checker, or its transcript is unknown."""
        return None if a.agent_id is None else self.messaged.get(a.agent_id)


@dataclass(frozen=True)
class TrackerRead:
    """What the operator reads of the ticket tracker: its `tickets` by
    number, the ticket files the read left out of `tickets` (`unread`),
    and the session's `index`."""
    tickets: Mapping[str, Ticket]
    unread: tuple[Unread, ...]
    index: int


@dataclass(frozen=True)
class Restore:
    """A `restore` call on a task that did not fail, by any agent: its
    time, and the argument it gave after the task id, None where it gave
    the task id alone."""
    time: float
    argument: str | None


@dataclass(frozen=True)
class GitRead:
    """What the operator reads of git and the main tree. `commits` holds the
    commits `tree_reads.COMMITS` gives, `worktrees` the worktrees of the repo, and
    `branches` the branch of each worktree that stands on one. `claims`
    gives the session id each claimed task's claim file holds, and
    `restores` the `restore` calls on each task, in order, as
    `task_dirs.restores_file` records them.
    `solvers` holds the tasks whose solver stands in the main tree.
    `reviews` gives each review's last baseline, or why the read gives
    none.
    `doc_reviews` gives the time of the commit each `Reader.tag` points
    at, by that tag, or is None where the tags do not read. `definitions` gives the
    `st_mtime` of each rendered definition `.claude/agents/<agent
    type>.md` of the main tree, by agent type."""
    commits: tuple[Commit, ...]
    worktrees: frozenset[Path]
    branches: Mapping[Path, str]
    claims: Mapping[str, str]
    restores: Mapping[str, tuple[Restore, ...]]
    solvers: frozenset[str]
    reviews: Mapping[Review, Baseline | NoBaseline]
    doc_reviews: Mapping[str, float] | None
    definitions: Mapping[str, float]


class Deferred[T]:
    """A read that runs at the first use of its `value`, which is held from
    then on: the procedures of a state read it only where a step reaches
    it."""

    def __init__(self, read: Callable[[], T]) -> None:
        self._read = read
        self._value: tuple[T] | None = None

    @property
    def value(self) -> T:
        if self._value is None:
            self._value = (self._read(),)
        return self._value[0]


class ReadOnUse[K, V](Mapping[K, V]):
    """A mapping of `keys`, whose value at a key is `read` of it as a
    `Deferred` gives it."""

    def __init__(self, keys: Iterable[K], read: Callable[[K], V]) -> None:
        self._held = {k: Deferred(lambda k=k: read(k)) for k in keys}

    def __getitem__(self, key: K) -> V:
        return self._held[key].value

    def __iter__(self) -> Iterator[K]:
        return iter(self._held)

    def __len__(self) -> int:
        return len(self._held)


@dataclass(frozen=True)
class HeldRead:
    """What the operator reads of the changes `me` holds. `gate_outputs`
    gives, for the worktree of each, the accepted gate outputs under
    `tests/gate/accepted/` its change writes, and `fragments` the
    fragments whose text that change adds or changes, as
    `tree_reads.fragments` gives them, each read at its first use
    (`ReadOnUse`)."""
    gate_outputs: Mapping[Path, tuple[str, ...]]
    fragments: Mapping[Path, tuple[Place, ...]]


@dataclass(frozen=True)
class AuditWindow:
    """The window of the next cost audit: its start, and the spend in
    dollars of its priced requests alone, a lower bound of its spend
    (`audit_records.start_and_spend`)."""
    start: float
    priced_spend: float


@dataclass(frozen=True)
class NotComputed:
    """A value that a read did not compute, with the text of why: a value of
    `Computed`, or a pace (`pacing`)."""
    why: str = mctx("the read of the state did not compute it")


@dataclass(frozen=True)
class Computed:
    """The values `state_assembly.read_state` computes over the `State` of
    the reads. `to_settle` is the list `file_ticket.py to-settle` prints
    for the session, with the numbers the coordinator names and the
    tickets of `taking.allowed`, keeping only the tickets that
    `tracker.tickets` holds. `spent` gives, for each
    change `me` holds, the spend of the agents `change_agents.of_change` gives
    for it. `budgets` gives the budget of each change of `taking.takeable`,
    taken at `State.now`, and of each held change whose spend passes
    the budget its take gives, taken at the line that gives that budget
    (`change_budget.Take`). `doc_budgets` gives, for each held change where
    `change_fragments.fragments_due` holds and that
    `change_fragments.lacking_doc_editor` gives an `editors` field for, the budget,
    taken at `State.now`, of that field's set with the doc editor.
    `run_starts` gives what the script of each `Op run:` line gave at this
    read, by its run (`runs.run_id`), and `run_takes` what its `takes`
    gave. `pace` is the usage pace at `State.now` (`pacing`), NotComputed
    until the read computes it. `audit_window` is the window of the next
    cost audit (`audit_window`), NotComputed until the read computes it."""
    to_settle: tuple[str, ...] = ()
    spent: Mapping[str, Spend] = field(default_factory=dict)
    budgets: Mapping[str, Budget] = field(default_factory=dict)
    doc_budgets: Mapping[str, Budget] = field(default_factory=dict)
    run_starts: Mapping[str, Starts] = field(default_factory=dict)
    run_takes: Mapping[str, Takes] = field(default_factory=dict)
    pace: "Pace" = field(default_factory=NotComputed)
    audit_window: AuditWindow | NotComputed = field(default_factory=NotComputed)

    def admitted(self) -> frozenset[str] | None:
        """The tickets each run whose script defines `takes` admits, a run
        with a fault admitting none, or None where no script defines
        `takes`, so that every ticket is admitted."""
        given = [t for t in self.run_takes.values() if t is not None]
        if not given:
            return None
        return frozenset.intersection(*(frozenset() if isinstance(t, str) else t for t in given))


@dataclass(frozen=True)
class SessionsRead:
    """What the operator reads of the tracker's sessions, as
    `idle_sessions.read_sessions` gives it: `idle` holds each idle index,
    other than the reading session's, that holds a ticket outside
    `vocabulary.SETTLED`, and `ended` each idle index other than the
    reading session's, whatever its tickets; `main` is whether the reading
    session is the main, `main_live` whether a main is named and live, and
    `main_wanted` the session id `tickets/main-wanted` holds with the time
    of its write."""
    idle: frozenset[int]
    ended: frozenset[int]
    main: bool
    main_live: bool
    main_wanted: tuple[str, float] | None

    @property
    def adopted(self) -> frozenset[int]:
        """The indexes of other sessions whose tickets the reading session's
        operators act on as on its own (`file_ticket.py main --help`): the
        idle ones, where it is the main."""
        return self.idle if self.main else frozenset()

    @property
    def fixed_for(self) -> frozenset[int]:
        """The indexes of other sessions whose closed `interference` tickets
        the reading session's operators give a solver fix
        (`passes.fixes`): the ended ones, where it is the main, since a
        ticket's closure can leave its index with no ticket outside
        `vocabulary.SETTLED`."""
        return self.ended if self.main else frozenset()


@dataclass(frozen=True)
class DueEntry:
    """A ticket's entry in the session's record of due steps
    (`State.due_since`): `since` is the time from which an operator's step
    has been due on it, and `last` the time of the last read that found
    that step due."""
    since: float
    last: float


@dataclass(frozen=True)
class State:
    """What the procedures read. `operators` holds the agent ids of the
    session's operators in the order of their launch, `parents` the parent
    of each, `main` or the agent id of the operator launcher that launched
    it, and `open_operators` those other than `me` whose work is open,
    before and after `me`, the only ones a procedure asks after.
    `transcripts` is the read of the operators' transcripts. `open_holders` gives
    the holders of tickets under `tickets/assigned/` whose work is open, as
    `profile_runs.py --open` gives it, or, for a holder whose run is a main
    transcript, whose session runs (`idle_sessions.running`), and `session_holders` those of
    them whose run is of the session: its main transcript, or a run under
    that transcript's session directory. `tracker` is the read of the
    ticket tracker, `held` is the read of the changes `me` holds, and `git` the read of
    git and the main tree. `received` holds the messages that reached `me`
    or an operator it takes up the lines of (`taken_up`, as
    `plan.taken_up` gives it). `started` is the time of the session's
    start, and `transcripts_dir` the directory that holds the session's
    transcript. `readers` holds the readers a standing doc
    review rotates over, read at its first use, in the order `context.py contexts` lists them.
    `limit_lifted` is the time of the reading of the usage limit that
    gives it as lifted, or None where the reading gives it in force, as
    `usage_limit.read_usage` gives it. `sessions` is the read of the
    tracker's sessions, and `computed` the values computed over the
    reads. `aside` holds the keys (`steps.key`) of the steps that
    `order.batch` set aside on this state, each as its procedure gave it,
    and is empty in each state the read gives. `journal` is the session's
    step journal (`journal`). `listing` holds the agent types the agent
    listing of `me` holds, or is None where its transcript gives none
    (`agent_listings.agent_listing`). `due_since` holds, for each ticket,
    the time from which an operator's step has been due on it and the time
    of the last read that found it due (`DueEntry`), as the session's
    record of those times gives it (`ticket_stall.due_times`), and is
    empty where that record is missing or unreadable."""
    me: str
    now: float
    session: str
    started: float
    transcripts_dir: Path
    main_tree: Path
    scratch: Path
    operators: tuple[str, ...]
    open_operators: frozenset[str]
    past_bound: bool
    open_holders: frozenset[str]
    session_holders: frozenset[str]
    tracker: TrackerRead
    transcripts: TranscriptsRead
    git: GitRead
    taken_up: frozenset[str]
    held: HeldRead
    sessions: SessionsRead
    journal: "Journal"
    listing: frozenset[str] | None
    readers: Deferred[tuple[Reader, ...]] = field(default_factory=lambda: Deferred(tuple))
    limit_lifted: float | None = None
    parents: Mapping[str, str] = field(default_factory=dict)
    computed: Computed = field(default_factory=lambda: Computed())
    aside: frozenset[str] = frozenset()
    due_since: Mapping[str, DueEntry] = field(default_factory=dict)

    @cached_property
    def memo(self) -> dict[tuple[Any, ...], Any]:
        """The results `memoized` holds for this state, by function and
        arguments."""
        return {}

    @property
    def arrived(self) -> list[Message]:
        """`transcripts.messages`, in the order they arrived."""
        return sorted(self.transcripts.messages, key=lambda m: m.time)

    @property
    def received(self) -> list[Message]:
        """The messages that reached `me`, its brief included, or an
        operator of `taken_up`, in the order they arrived."""
        return [m for m in self.arrived if m.operator == self.me or m.operator in self.taken_up]

    def agents_of(self, role: Role | None = None, subject: str | None = None) -> list[Agent]:
        return [a for a in self.transcripts.agents
                if (role is None or a.role is role) and (subject is None or a.subject == subject)]

    def analysts(self) -> tuple[tuple[Agent, Purpose, list[str]], ...]:
        """`TranscriptsRead.analysts` of the session's operators."""
        return self.transcripts.analysts

    def ticket(self, number: str) -> Ticket | None:
        return self.tracker.tickets.get(number)

    def mine(self, t: Ticket) -> bool:
        """Whether the operators act on `t` as on a ticket of the session."""
        return self.acts_on(t.session)

    def acts_on(self, session: int | None) -> bool:
        """Whether the operators act on the tickets of the session index
        `session` as on tickets of the session: the session's own index
        or one it adopts."""
        return session == self.tracker.index or session in self.sessions.adopted


def memo_in[*A, R](held: Callable[[State], dict[tuple[Any, ...], Any]]
                   ) -> Callable[[Callable[[State, *A], R]], Callable[[State, *A], R]]:
    """A decorator that runs its function once for each of its arguments
    other than the state, and holds the result in the memo `held` gives for
    the state; the result is shared by each caller, which changes none of
    it."""
    def decorate(f: Callable[[State, *A], R]) -> Callable[[State, *A], R]:
        @wraps(f)
        def once(state: State, *args: *A) -> R:
            memo = held(state)
            key = (f, *args)
            if key not in memo:
                memo[key] = f(state, *args)
            return memo[key]
        return once
    return decorate


memoized = memo_in(lambda state: state.memo)
"""For a function the procedures ask of one state many times."""

memoized_by_transcripts = memo_in(lambda state: state.transcripts.memo)
"""For a function that reads, of its state, only `State.transcripts`: a
state that `dataclasses.replace` derives and that keeps that read shares
its results."""
