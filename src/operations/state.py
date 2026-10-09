"""The state the operator's procedures read, as `scripts/operate.py` reads
it from the ticket tracker, git, the worktrees and the transcripts of the
session's operators.
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
    """A report of an agent that reached the operator that launched it: a
    notification, the result of a foreground launch, or a message, with
    the text the agent wrote, as `agent_reports` reads it."""
    time: float
    text: str


@dataclass(frozen=True)
class Agent:
    """An agent an operator of the session launched with a description the
    command gave. `pending` holds where that operator holds neither the
    result of a launch in the foreground nor a sign since its launch or
    its last resume, in any transcript of the session, that its turn
    ended, as `agent_reports.last_sign` gives the latest sign: a
    notification that it stopped, or its SubagentHandback message. It
    holds too where the latest sign is a notification that it stopped
    with work of its own still running, and then `still_running` holds:
    it has not reported yet, and the operator's turn may not end on it.
    Where a sign ends it and no report of it reached that operator since
    its launch or its last resume, the final reply in its transcript, where
    it gives one after them and went to that operator, ends its `reports`.
    `pending` does not hold either for an agent in `State.stalled`, nor
    for an agent of another operator whose work is no longer open, and
    the final reply in its transcript, where it gives one and it went to
    that operator, then ends its `reports`. `notifies` holds where that
    operator launched or last resumed it itself, so the notification of
    its end and its final reply reach that operator. `messaged` holds, for
    a doc reviewer whose transcript is known, the agent ids its SendMessage
    calls went to, and is None for any other agent."""
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
    """A tool call of an operator of the session: its tool, its input, and
    its result, None while it is pending, each with the text of each file
    the command wrote for a call it printed in place of the line that gives
    that file (`steps.FILED`), with whether the harness gave the
    result as an error, and for a call of `scripts/merge_change.py` that
    has its result, what it did. The result of a Bash call the harness ran
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


class Printed(Enum):
    """The tool of a step the command prints to an operator for it to call
    in the foreground, by the name the harness gives that tool."""
    SEND_MESSAGE = "SendMessage"
    BASH = "Bash"


@dataclass(frozen=True)
class Made:
    """A step the command printed to an operator, read from the result of
    that operator's call of `operate.py next`, and the call that operator
    made next, which made it: the step's key, None where the result was
    cut before it, the tool of the printed call, the recipient of a
    message, and the message or the command as far as the result gives
    it."""
    key: str | None
    tool: Printed
    to: str | None
    text: str
    call: Call


@dataclass(frozen=True)
class Message:
    """A message that reached an operator: from the coordinator, as its
    brief or a later message, where `sender` is None, or otherwise from the
    agent `sender`, which that operator did not launch or launched as an
    auditor. A message from an auditor that opens with no alert line, as
    its hand-back does, gives no step (`alerts`)."""
    operator: str
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
    """What the procedures read. `operators` holds the agent ids of the
    session's operators in the order of their launch, and `open_operators`
    those after `me` whose work is open, the only ones a procedure asks
    after. `pass_tickets` gives, for each solver pass
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
    operator as a report. `made` holds each step the command printed to an operator
    with the call that operator made next (`steps.made`). `messages` holds
    the messages that reached any operator of the session, and `received`
    those that reached `me` or an operator it takes up the lines of
    (`taken_up`, as `plan.taken_up` gives it)."""
    me: str
    now: float
    session: str
    index: int
    main_tree: Path
    scratch: Path
    operators: tuple[str, ...]
    open_operators: frozenset[str]
    past_bound: bool
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
    made: tuple[Made, ...] = ()
    taken_up: frozenset[str] = frozenset()

    @property
    def arrived(self) -> list[Message]:
        """`messages`, in the order they arrived."""
        return sorted(self.messages, key=lambda m: m.time)

    @property
    def received(self) -> list[Message]:
        """The messages that reached `me`, its brief included, or an
        operator of `taken_up`, in the order they arrived."""
        return [m for m in self.arrived if m.operator == self.me or m.operator in self.taken_up]

    def agents_of(self, role: Role | None = None, subject: str | None = None) -> list[Agent]:
        return [a for a in self.agents
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
        return self.tickets.get(number)

    def mine(self, t: Ticket) -> bool:
        """Whether `t` is of the session."""
        return t.session == self.index
