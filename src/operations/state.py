"""The state the loop's procedures read, as `scripts/operate.py` reads it
from the ticket tracker, git, the worktrees, the loop's record and the
transcripts of the session and of the agents the loop launched.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from operations.roles import Model, Purpose, Role, analyst_of, subjects
from ticketing.vocabulary import Domain, Kind, Status


@dataclass(frozen=True)
class LogLine:
    """A line of a ticket's log: its time, the status it leaves the ticket
    in, the agent name and the agent id its bracket gives, and its note.
    `on_user` is whether the note opens with the wait on the user, and
    `on_change` the number of the change the note opens with a wait on."""
    time: float
    status: Status
    agent: str
    agent_id: str | None
    note: str
    on_user: bool
    on_change: str | None


@dataclass(frozen=True)
class Ticket:
    """A ticket of the tracker. `editors` is None where a `change` gives no
    `editors` field, `mechanical` is whether a `change` gives the
    `mechanical` field, and `holder` is the holder `file_ticket.py log
    --help` defines."""
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
        code editor of a `mechanical` change, and otherwise the one the
        agent's definition gives."""
        return Model.SONNET if self.mechanical and role is Role.CODE_EDITOR else None


@dataclass(frozen=True)
class Report:
    """A report of an agent the loop launched: the final reply in its
    transcript, with its time and the text the agent wrote."""
    time: float
    text: str


@dataclass(frozen=True)
class Agent:
    """An agent the loop `loop` launched with a description the command
    gave. `pending` holds until its transcript gives its turn ended, and
    while no transcript of it is found yet. Its `reports` hold the final
    reply in its transcript. `pending` does not hold for an agent in
    `State.stalled`, and the final reply in its transcript ends its
    `reports`. `notifies` holds where the notification of its end reaches
    the coordinator's session, which the loop reads. `messaged` holds, for
    a doc reviewer whose transcript is known, the agent ids its SendMessage
    calls went to, and is None for any other agent."""
    agent_id: str | None
    loop: str
    role: Role
    subject: str
    brief: str
    launched: float
    pending: bool
    reports: tuple[Report, ...]
    notifies: bool
    messaged: frozenset[str] | None = None

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
    script gives (`merge_change.ran`, `merge_change.conflicted`), never
    ran, as where the harness denied the call, refused for a conflict in
    its rebase, or refused otherwise."""
    LEFT_EDITS = "left edits"
    MERGED = "merged"
    NOT_RUN = "not run"
    CONFLICT = "conflict"
    REFUSED = "refused"


@dataclass(frozen=True)
class Call:
    """A call the loop `loop` made, as its record gives it: its tool,
    its input, and its result, None while it is pending, each with the
    text of each file the command wrote for it in place of the line that
    gives that file (`steps.FILED`), with whether its result is an error,
    and for a call of `scripts/merge_change.py` that has its result, what
    it did."""
    loop: str
    time: float
    tool: str
    input: Mapping[str, Any]
    result: str | None
    error: bool
    merge: Merge | None = None


class Printed(Enum):
    """The tool of a step the loop's record gives as made, other than a
    launch, by the name the harness gives that tool."""
    SEND_MESSAGE = "SendMessage"
    BASH = "Bash"


@dataclass(frozen=True)
class Made:
    """A step the loop's record gives as made, and the call that made it:
    the step's key, None where the record gives none, the tool of the call,
    the recipient of a message, and the message or the command."""
    key: str | None
    tool: Printed
    to: str | None
    text: str
    call: Call


@dataclass(frozen=True)
class Message:
    """A message that reached the loop `loop`: a line of the
    coordinator's (`operate.py tell`), where `sender` is None, or otherwise
    a message to the coordinator's session from the agent `sender`, which
    the loop launched."""
    loop: str
    time: float
    sender: str | None
    text: str


@dataclass(frozen=True)
class Commit:
    """A commit of `master`: its hash, its time, whether it changes
    `src/`, `scripts/` or `tests/`, and its subject."""
    hash: str
    time: float
    code: bool
    subject: str


@dataclass(frozen=True)
class State:
    """What the procedures read. `me` is the loop's id. `pass_tickets`
    gives, for each solver pass
    that reported, the numbers of the tickets its report lists under
    `## Tickets filed`, or None where its reply is no report's path.
    `to_settle` is the list `file_ticket.py to-settle` prints for the
    session, with the numbers the coordinator names, keeping only the
    tickets that `tickets` holds. `claims` gives the
    session id each claimed task's claim file holds, and `open_holders`
    the holders of tickets under `tickets/assigned/` whose work is open, as
    `profile_runs.py --open` gives it. `index` is the session's index.
    `gate_outputs` gives, for the worktree of each
    change `me` holds, the accepted gate outputs under
    `tests/gate/accepted/` its change writes. `branches` gives the branch
    of each worktree that stands on one, and `stalled` the final reply in
    the transcript of each agent a stall alert names that reached no
    loop as a report. `passed` gives, by its key (`steps.key`), each
    step an `Override: pass over` ruling passed over, with the line that
    gives it (`directives.passed_over`). `made` holds each step the loop's
    record gives as made, with the call that made it. `messages` holds
    the messages that reached the loop, and `received` those that reached
    `me`."""
    me: str
    now: float
    session: str
    index: int
    main_tree: Path
    scratch: Path
    open_holders: frozenset[str]
    tickets: Mapping[str, Ticket]
    agents: tuple[Agent, ...]
    calls: tuple[Call, ...]
    messages: tuple[Message, ...]
    to_settle: tuple[str, ...]
    worktrees: frozenset[Path]
    claims: Mapping[str, str]
    commits: tuple[Commit, ...]
    code_review: int | None
    gate_outputs: Mapping[Path, tuple[str, ...]] = field(default_factory=dict)
    branches: Mapping[Path, str] = field(default_factory=dict)
    stalled: Mapping[str, Report] = field(default_factory=dict)
    pass_tickets: Mapping[str, tuple[str, ...] | None] = field(default_factory=dict)
    passed: Mapping[str, str] = field(default_factory=dict)
    made: tuple[Made, ...] = ()

    @property
    def arrived(self) -> list[Message]:
        """`messages`, in the order they arrived."""
        return sorted(self.messages, key=lambda m: m.time)

    @property
    def received(self) -> list[Message]:
        """The messages that reached `me`, its brief included, in the order
        they arrived."""
        return [m for m in self.arrived if m.loop == self.me]

    def agents_of(self, role: Role | None = None, subject: str | None = None) -> list[Agent]:
        return [a for a in self.agents
                if (role is None or a.role is role) and (subject is None or a.subject == subject)]

    def analysts(self) -> list[tuple[Agent, Purpose, list[str]]]:
        """Each ticket analyst the loop launched, with its purpose
        and the ticket numbers or the task its subject gives."""
        out: list[tuple[Agent, Purpose, list[str]]] = []
        for a in self.agents_of(Role.TICKET_ANALYST):
            parsed = analyst_of(a.subject)
            if parsed is not None:
                out.append((a, parsed[0], subjects(parsed[1])))
        return out

    def ticket(self, number: str) -> Ticket | None:
        return self.tickets.get(number)

    def mine(self, t: Ticket) -> bool:
        """Whether `t` is of the session."""
        return t.session == self.index
