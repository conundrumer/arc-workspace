"""The state the operator's procedures read, as `scripts/operate.py` reads
it from the ticket tracker, git, the worktrees and the transcripts of the
session's operators.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from pathlib import Path
from typing import Any

from handbook.reader_names import ReaderName
from operations.roles import Model, Purpose, Role, analyst_of, subjects
from ticketing.vocabulary import Domain, Kind, Resolution, Status


@dataclass(frozen=True)
class LogLine:
    """A line of a ticket's log: its time, the status it leaves the ticket
    in, the agent name and the agent id its bracket gives, and its note.
    `on_user` is whether the note opens with the wait on the user, and
    `on_change` the number of the change the note opens with a wait on.
    `waits` is whether the note opens with a wait of any kind.
    `resolution` is the resolution the note opens with, and `closed_by`
    the number of the change a note of the form `ticket_log.CLOSED_BY`
    gives."""
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


@dataclass(frozen=True)
class Unread:
    """A ticket file the operator's read refused or failed on, which no
    procedure reads as a ticket: `why` is the read's failure, `digest` a
    digest of the file's bytes, so that each content it has gives its own
    step, or where those bytes do not read, of that failure's text, and
    `modified` the time of its last write, or 0 where that time does not
    read."""
    path: Path
    why: str
    digest: str
    modified: float


@dataclass(frozen=True)
class Ticket:
    """A ticket of the tracker. `editors` is None where a `change` gives no
    `editors` field, `mechanical` is whether a `change` gives the
    `mechanical` field, and `holder` is the holder `file_ticket.py
    log --help-all` defines."""
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
    priority: int
    editors: tuple[Role, ...] | None
    after_merge: str | None
    mechanical: bool
    log: tuple[LogLine, ...]
    holder: str | None
    path: Path

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
    session, made its first entry, at `later_first`, as `monitor.ALERTS`
    gives a resume, at `time`."""
    time: float
    later: str
    later_first: float


@dataclass(frozen=True)
class Agent:
    """An agent an operator of the session launched with a description the
    command gave, or a doc reviewer that a doc editor such an operator
    launched launched, which is read as a launch of that doc editor's, with
    the doc editor as its `operator`. `pending` holds where that operator holds neither the
    result of a launch in the foreground nor a sign since its launch or
    its last resume, in any transcript of the session, that its turn
    ended, as `agent_reports.last_sign` gives the latest sign: a
    notification that it stopped, or its SubagentHandback message. It
    holds too where the latest sign is a notification that it stopped
    with work of its own still running, and then `still_running` holds:
    it has not reported yet, and the operator's turn may not end on it.
    It holds as well where the latest sign is a notification that the
    usage limit stopped it, and then `limited` gives that sign's time: it
    has not ended its work, and waits for a resume (`limit_resume`).
    Where a sign ends it and no report of it reached that operator since
    its launch or its last resume, the final reply in its transcript, where
    it gives one after them and it went to that operator or is the path of
    a report file alone, read from that file, ends its `reports`.
    `pending` does not hold either for an agent in `TranscriptsRead.stalled`, nor
    for an agent of another operator whose work is no longer open, and
    the final reply in its transcript, where it gives one and it went to
    that operator or is the path of a report file alone, read from that
    file, then ends its `reports`. `notifies` holds where that
    operator launched or last resumed it itself, so the notification of
    its end and its final reply reach that operator. `messaged` holds, for
    a doc reviewer or an item checker whose transcript is known, the agent
    ids its SendMessage calls went to, and is None for any other agent."""
    agent_id: str | None
    operator: str
    role: Role
    subject: str
    brief: str
    launched: float
    pending: bool
    reports: tuple[Report, ...]
    still_running: bool
    notifies: bool
    messaged: frozenset[str] | None = None
    limited: float | None = None

    @property
    def last_report(self) -> Report | None:
        return self.reports[-1] if self.reports else None


class Merge(Enum):
    """What a call of `scripts/merge_change.py` did: left edits, where its
    output gives that `master` is fast-forwarded and the worktree stays
    for changes made after the commit (`merge_change.left_edits`), which
    leaves the change unmerged; merged, where `master` otherwise holds a
    commit made at or after the call with the message it gives, whatever
    its exit status; and otherwise, by the forms of its output that
    script gives (`merge_change.ran`, `merge_change.conflict_paths`), never
    ran, as where the harness denied the call, refused for a conflict in
    its rebase, or refused otherwise."""
    LEFT_EDITS = "left edits"
    MERGED = "merged"
    NOT_RUN = "not run"
    CONFLICT = "conflict"
    REFUSED = "refused"


@dataclass(frozen=True)
class Call:
    """A tool call of an operator of the session: its tool, its input, and
    its result, None while it is pending, each with the text of each file
    the command wrote for a call it printed in place of the line that gives
    that file (`filing.FILED_LINE`), with whether the harness gave the
    result as an error, and for a call of `scripts/merge_change.py` that
    has its result, what it did, and for one refused for a conflict in its
    rebase, the paths it conflicts in, which are empty for every other
    call. The result of a Bash call the harness ran
    or moved to the background is the output its command wrote, once a
    notification of its end reached the operator, and it is an error
    where that notification gives a status other than `completed`."""
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


class Tool(StrEnum):
    """A tool an operator calls, by the name the harness gives that tool."""
    AGENT = "Agent"
    SEND_MESSAGE = "SendMessage"
    BASH = "Bash"
    SUBAGENT_HANDBACK = "SubagentHandback"


@dataclass(frozen=True)
class Made:
    """A step the command printed to an operator, read from the result of
    that operator's call of `operate.py next`, and the call that operator
    made next, which made it: the step's key, None where the result was
    cut before it, the tool of the printed call, the recipient of a
    message, and the message or the command as far as the result gives
    it."""
    key: str | None
    tool: Tool
    to: str | None
    text: str
    call: Call


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
    """A commit of `master`: its hash, its time, whether it changes
    `src/`, `scripts/` or `tests/`, its subject, and whether it changes
    a directory of `tree_reads.PROCESS_DIRS`, a change to the agents'
    processes."""
    hash: str
    time: float
    code: bool
    subject: str
    process: bool


DOC_REVIEW = "doc-review/"
"""What leads the tag of a reader's last standing doc review, and the
subject of a standing doc review's launch."""


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
    under it summed with it (`scripts/ticket_watch.py`)."""
    dollars: float
    seconds: float
    by_role: dict[str, float]


@dataclass(frozen=True)
class Budget:
    """A change's cost budget in dollars and its time budget in seconds,
    with the median spend of each agent type over the changes the budget
    is taken over (`scripts/ticket_watch.py`)."""
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
class Seen:
    """A file `tree_reads.py seen` wrote for a change: the time of its
    write, and the file and text of each place it holds, or None where the
    file does not read."""
    time: float
    places: frozenset[tuple[str, str]] | None


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
class TranscriptsRead:
    """What the operator reads of the transcripts of the session's
    operators. `agents` holds their launches, in the order of their launch,
    `calls` their calls, in the order of their time, and `messages` the
    messages that reached any of them. `made` holds each step the command
    printed to an operator with the call that operator made next
    (`handled.made`). `late_resumes` gives, for each operator of
    `State.operators`, its resumes, as `monitor.ALERTS` gives them, after
    the next operator of `State.operators` made its first entry, in the
    order of their time. `stalled` gives the final reply in the transcript
    of each agent a stall alert names that reached no operator as a
    report. `pass_tickets` gives, for each
    solver pass with an agent id, the numbers of the tickets the report
    file it wrote under the task's work directory since its launch lists
    under `## Tickets filed`, or None where it wrote no such file with
    that section, whatever its reply."""
    agents: tuple[Agent, ...]
    calls: tuple[Call, ...]
    messages: tuple[Message, ...]
    made: tuple[Made, ...]
    late_resumes: Mapping[str, tuple[LateResume, ...]]
    stalled: Mapping[str, Report]
    pass_tickets: Mapping[str, tuple[str, ...] | None]


@dataclass(frozen=True)
class TrackerRead:
    """What the operator reads of the ticket tracker: its `tickets` by
    number, the ticket files the read left out of `tickets` (`unread`),
    and the session's `index`."""
    tickets: Mapping[str, Ticket]
    unread: tuple[Unread, ...]
    index: int


@dataclass(frozen=True)
class GitRead:
    """What the operator reads of git and the main tree. `commits` holds the
    commits `tree_reads.COMMITS` gives, `worktrees` the worktrees of the repo, and
    `branches` the branch of each worktree that stands on one. `claims`
    gives the session id each claimed task's claim file holds.
    `code_review` is the highest number of a `code-review/<n>` tag.
    `doc_reviews` gives the time of the commit each `Reader.tag` points
    at, by that tag, or is None where the tags do not read. `definitions` gives the
    `st_mtime` of each rendered definition `.claude/agents/<agent
    type>.md` of the main tree, by agent type."""
    commits: tuple[Commit, ...]
    worktrees: frozenset[Path]
    branches: Mapping[Path, str]
    claims: Mapping[str, str]
    code_review: int | None
    doc_reviews: Mapping[str, float] | None
    definitions: Mapping[str, float]


@dataclass(frozen=True)
class HeldRead:
    """What the operator reads of the changes `me` holds. `gate_outputs`
    gives, for the worktree of each, the accepted gate outputs under
    `tests/gate/accepted/` its change writes, and `fragments` the
    fragments whose text that change adds or changes, as
    `tree_reads.fragments` gives them, and `seen` the files
    `tree_reads.py seen` wrote for each change, by its number, in the
    order of their time."""
    gate_outputs: Mapping[Path, tuple[str, ...]]
    fragments: Mapping[Path, tuple[Place, ...]]
    seen: Mapping[str, tuple[Seen, ...]]


@dataclass(frozen=True)
class Computed:
    """The values `operator_state.read_state` computes over the `State` of
    the reads. `to_settle` is the list `file_ticket.py to-settle` prints
    for the session, with the numbers the coordinator names, keeping only
    the tickets that `tracker.tickets` holds. `spent` gives, for each
    change `me` holds, the spend of the agents `changes.of_change` gives
    for it. `budgets` gives the budget of each change `changes.take` takes
    next, taken at `State.now`, and of each held change whose spend passes
    the budget its take gives, taken at the line that gives that budget
    (`change_budget.Take`). `doc_budgets` gives, for each held change that
    `changes.lacking_doc_editor` gives an `editors` field for, the budget,
    taken at `State.now`, of that field's set with the doc editor.
    `run_starts` gives what the script of each `Run:` line gave at this
    read, by its run (`runs.run_id`), and `run_takes` what its `takes`
    gave."""
    to_settle: tuple[str, ...] = ()
    spent: Mapping[str, Spend] = field(default_factory=dict)
    budgets: Mapping[str, Budget] = field(default_factory=dict)
    doc_budgets: Mapping[str, Budget] = field(default_factory=dict)
    run_starts: Mapping[str, Starts] = field(default_factory=dict)
    run_takes: Mapping[str, Takes] = field(default_factory=dict)

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
    """What the operator reads of the tracker's sessions. `idle_indexes`
    holds the idle indexes `idle_sessions.read_sessions` gives, `adopted`
    those of them the operators act on as on the session's own
    (`file_ticket.py main --help`), `main_live` whether the main session
    runs an agent, and `main_wanted` the session id `tickets/main-wanted`
    holds with the time of its write, as `idle_sessions` gives them."""
    idle_indexes: frozenset[int]
    adopted: frozenset[int]
    main_live: bool
    main_wanted: tuple[str, float] | None


@dataclass(frozen=True)
class State:
    """What the procedures read. `operators` holds the agent ids of the
    session's operators in the order of their launch, `parents` the parent
    of each, `main` or the agent id of the operator launcher that launched
    it, and `open_operators` those after `me` whose work is open, the only
    ones a procedure asks after. `transcripts` is the read of the
    operators' transcripts. `open_holders` gives
    the holders of tickets under `tickets/assigned/` whose work is open, as
    `profile_runs.py --open` gives it, and `session_holders` those of
    them whose run is of the session: its main transcript, or a run under
    that transcript's session directory. `tracker` is the read of the
    ticket tracker, `held` is the read of the changes `me` holds, and `git` the read of
    git and the main tree. `received` holds the messages that reached `me`
    or an operator it takes up the lines of (`taken_up`, as
    `plan.taken_up` gives it). `started` is the time of the session's
    start, and `transcripts_dir` the directory that holds the session's
    transcript. `readers` holds the readers a standing doc
    review rotates over, in the order `context.py contexts` lists them.
    `limit_lifted` is the time of the reading of the usage limit that
    gives it as lifted, or None where the reading gives it in force, as
    `operator_state.limit_lifted` gives it. `sessions` is the read of the
    tracker's sessions, and `computed` the values computed over the
    reads."""
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
    readers: tuple[Reader, ...] = ()
    limit_lifted: float | None = None
    parents: Mapping[str, str] = field(default_factory=dict)
    computed: Computed = field(default_factory=lambda: Computed())

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

    def analysts(self) -> list[tuple[Agent, Purpose, list[str]]]:
        """Each ticket analyst of the session's operators, with its purpose
        and the ticket numbers or the task its subject gives."""
        out: list[tuple[Agent, Purpose, list[str]]] = []
        for a in self.agents_of(Role.TICKET_ANALYST):
            parsed = analyst_of(a.subject)
            if parsed is not None:
                out.append((a, parsed[0], subjects(parsed[1])))
        return out

    def ticket(self, number: str) -> Ticket | None:
        return self.tracker.tickets.get(number)

    def mine(self, t: Ticket) -> bool:
        """Whether the operators act on `t` as on a ticket of the session."""
        return t.session == self.tracker.index or t.session in self.sessions.adopted
