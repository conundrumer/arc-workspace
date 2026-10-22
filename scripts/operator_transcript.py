"""The read of the transcript of one operator (`read_operator`): its
calls, with the outcome of each, the messages that reached it, each read
in place of the filed line that gives it, and the agents it launched, with
their reports, the agents each doc reviewer sent a message, and the
reports of its solver passes."""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from agent_launches import children_of, launched
from agent_resumes import resumes, sent_to
from agents_pending import turn_signs
from agent_turns import latest_time
from agent_reports import ENDED, Sign, last_sign
from controlled_markdown import mctx
from merge_reads import merge_outcome, merge_subjects
from filed_texts import brief_report_file, filed_report, unfiled
from agent_listings import agent_listing
from agent_ends import ended_with, reply_to
from operator_reads import MESSAGE_FROM, AgentsRead, from_parent
from pass_reads import pass_read
from run_reads import (BACKGROUND_TASK, MAIN, agent_messages, blocks, is_prompt,
                       notifications, output_file, parent_id, run_sessions, tool_results)
from run_reads import Status as TaskStatus
from senders import Origin, Sender, origin, sender
from file_reads import file_text, is_file
from state_reads import DERIVED, Kept, state_cache
from transcripts import chain
from entry_reads import line_entries
from transcript_entries import epoch
from transcript_folds import Makes, fold
from transcript_snapshots import Entry

from operations.merge_outcomes import call_conflicts
from operations.roles import LAUNCHING_EDITORS, PASSES, Role, described
from operations.state import (
    Agent, AttemptState, Call, Ended, Message, PassReport, Report, Running, Tool, Waits,
)
from operations.command_words import is_next
from operations.printing import unfenced


FILED_FIELDS: dict[str, str] = {Tool.AGENT: "prompt", Tool.SEND_MESSAGE: "message"}
"""The field of each tool's input that may give a file the command wrote."""


def unfiled_call(aid: str, tool: str, inp: dict[str, Any], result: str | None,
                 undecided: list[str]) -> tuple[dict[str, Any], str | None]:
    """The input and the result of a call of the operator `aid`, with each
    file the command wrote, that the field `FILED_FIELDS` gives or the
    result of a call of `next` gives, read in place of the line that gives
    it (`filed_texts.unfiled`), and that field read without the fence
    lines an operator passed with it (`operations.printing.unfenced`)."""
    where = mctx("{run}: a call of {tool}").format(run=aid, tool=tool)
    if (name := FILED_FIELDS.get(tool)) is not None:
        inp = {**inp, name: unfiled(unfenced(str(inp.get(name, ""))), where, undecided)}
    elif tool == Tool.BASH and result is not None and is_next(str(inp.get("command", "")), aid):
        result = unfiled(result, where, undecided)
    return inp, result


MESSAGING = frozenset({Role.DOC_REVIEWER, Role.ITEM_CHECKER})
"""The roles whose `TranscriptsRead.messaged` the command reads."""


@dataclass(frozen=True)
class OperatorRead:
    """What the transcript of one operator gives: its launches, its calls,
    the messages that reached it, `passes`, for each solver pass it
    launched with an agent id, the read of its report
    (`TranscriptsRead.pass_reports`), and `listing`, as `agent_listing`
    gives it."""
    launched: AgentsRead
    calls: tuple[Call, ...]
    messages: tuple[Message, ...]
    passes: Mapping[str, PassReport]
    listing: frozenset[str] | None = None

    @property
    def agents(self) -> tuple[Agent, ...]:
        return self.launched.agents


def read_operator(aid: str, path: Path, main: Path, undecided: list[str],
                  subjects: Mapping[str, float]) -> OperatorRead:
    """What the transcript at `path` of the operator `aid` gives. A message
    from the operator's parent, the coordinator or the operator launcher
    that launched it, or from the coordinator where the parent is an
    operator launcher, is read as a message of the coordinator's."""
    merged = merge_subjects(path)
    return listed(operator_read(aid, path, main, undecided,
                                frozenset((m, t) for m, t in subjects.items() if m in merged)),
                  path)


def read_launches(aid: str, path: Path, main: Path, undecided: list[str]) -> OperatorRead:
    """`read_operator` of the operator `aid` for the agents it launched,
    whose calls no step reads. It reads no call's outcome and gives no
    `Call`, and of each `Agent` call it reads only the filed text of its
    `prompt`, which is the brief of the agent that call launches."""
    return listed(launch_read(aid, path, main, undecided), path)


def listed(read: OperatorRead, path: Path) -> OperatorRead:
    """`read` with the listing of the operator whose transcript is at
    `path`."""
    return replace(read, listing=agent_listing(path))


type Uses = dict[str, tuple[float, dict[str, Any], str]]
"""Each call of an operator, by the id of its use, with its time, its
input and its tool."""


def use_of(stamp: str, b: dict[str, Any]) -> tuple[float, dict[str, Any], str]:
    """The time, the input and the tool of the use `b` of an entry whose
    time is `stamp`, as `Uses` gives them."""
    return epoch(stamp), b.get("input") or {}, b.get("name", "")


@dataclass
class LaunchingLines:
    """What `lines_of` reads of an operator's entries for `launch_read`,
    for an operator whose parent is `parent` and whose run spans
    `sessions`: each call of the `Agent` tool with its time, input and
    tool, and each prompt that has a time, by its line, with its time,
    whether it is from the operator's parent, and whether it is from the
    coordinator. A prompt's text is read at each read, as the files it
    gives may change."""
    parent: str
    sessions: list[Path]
    uses: Uses = field(default_factory=dict)
    prompts: list[tuple[Path, int, float, bool, bool]] = field(default_factory=list)

    def step(self, p: Path, i: int, e: Entry) -> None:
        """Add the entry `e` of line `i` of the transcript at `p`."""
        stamp = e.get("timestamp")
        if e.get("type") == "assistant" and stamp:
            for b in blocks(e, "tool_use"):
                if b.get("name") == Tool.AGENT:
                    self.uses[b.get("id", "")] = use_of(stamp, b)
        self.add_prompt(p, i, e)

    def add_prompt(self, p: Path, i: int, e: Entry) -> None:
        """Add the entry `e` of line `i` of the transcript at `p`, where it
        is a prompt that has a time. The first prompt is the operator's
        brief, from its parent."""
        stamp = e.get("timestamp")
        if stamp and is_prompt(e):
            direct = origin(e)[1] is Origin.COORDINATOR
            briefed = not self.prompts or direct or sender(
                e, self.parent, frozenset(), self.sessions) is Sender.PARENT
            self.prompts.append((p, i, epoch(stamp), briefed, direct))

    def messages(self, aid: str, children: frozenset[str],
                 undecided: list[str]) -> list[Message]:
        """The messages that reached the operator `aid` that launched
        `children`, in their order: each prompt from its parent or the
        coordinator, and each message of an agent other than `children`."""
        out: list[Message] = []
        where = MESSAGE_FROM.format(run=aid)
        for p, i, t, briefed, direct in self.prompts:
            for e in line_entries(p, i):
                if briefed:
                    out.append(Message(aid, t, None, from_parent(
                        aid, e, MAIN if direct else self.parent, undecided)))
                else:
                    out += [Message(aid, t, s, unfiled(unfenced(text), f"{where} {s}", undecided))
                            for s, text in agent_messages(e) if s not in children]
        return out


@dataclass
class OperatorLines(LaunchingLines):
    """What `lines_of` reads of an operator's entries for `operator_read`:
    what `LaunchingLines` reads, with each call of any tool, the text of
    each call's result and whether it is an error, the task and output file
    of each call the harness ran or moved to the background, and the status
    each notification that gives a status gives each id."""
    results: dict[str, tuple[str | None, bool]] = field(default_factory=dict)
    moved: dict[str, tuple[str, Path | None]] = field(default_factory=dict)
    tasks: dict[str, TaskStatus | None] = field(default_factory=dict)

    def step(self, p: Path, i: int, e: Entry) -> None:
        """Add the entry `e` of line `i` of the transcript at `p`."""
        stamp = e.get("timestamp")
        if e.get("type") == "assistant" and stamp:
            for b in blocks(e, "tool_use"):
                self.uses[b.get("id", "")] = use_of(stamp, b)
        elif e.get("type") == "user":
            result = e.get("toolUseResult")
            for call, b, text in tool_results(e):
                self.results[call] = (text, bool(b.get("is_error")))
                if isinstance(result, dict) and result.get(BACKGROUND_TASK):
                    self.moved[call] = (str(result[BACKGROUND_TASK]), output_file(b))
        if e.get("type") != "assistant":
            for n in notifications(e):
                if n.has_status:
                    for v in n.ids:
                        self.tasks[v] = n.status
        self.add_prompt(p, i, e)


type MadeCall = tuple[Call, bool]
"""A `Call` as `calls_of` made it from a use, with whether the operator's
last merge call of the use's command, up to the use's own, was denied."""


_calls_made: Makes[MadeCall] = Makes()
"""The calls `calls_of` last made for each operator, by the id of their
use, with the commits they were made from as the further key."""


def lines_of[L: LaunchingLines](lines: type[L], aid: str, path: Path) -> L:
    """What `lines` reads of the entries of the operator `aid` whose
    transcript is at `path`, by the fold of its step."""
    parent = parent_id(path)
    sessions = run_sessions(path)
    return fold(lines.step, lambda: lines(parent, sessions),
                (aid, path, parent, tuple(sessions)), chain(path))


@state_cache(DERIVED, notes="undecided", kept=Kept.DISK)
def operator_read(aid: str, path: Path, main: Path, undecided: list[str],
                  commits: frozenset[tuple[str, float]]) -> OperatorRead:
    """`read_operator`, with `subjects` as the pairs `commits` gives, those
    of `merge_subjects`."""
    read = lines_of(OperatorLines, aid, path)
    calls, uses = calls_of(aid, path, read, commits, undecided)
    return built(aid, path, main, read, calls, uses, undecided)


@state_cache(DERIVED, notes="undecided", kept=Kept.DISK)
def launch_read(aid: str, path: Path, main: Path, undecided: list[str]) -> OperatorRead:
    """`read_launches`, with no listing."""
    read = lines_of(LaunchingLines, aid, path)
    uses = {call: (t, unfiled_call(aid, tool, inp, None, undecided)[0], tool)
            for call, (t, inp, tool) in read.uses.items()}
    return built(aid, path, main, read, (), uses, undecided)


def built(aid: str, path: Path, main: Path, read: LaunchingLines, calls: tuple[Call, ...],
          uses: Uses, undecided: list[str]) -> OperatorRead:
    """The read of the operator `aid` whose transcript at `path` gives
    `read`, with `calls`, and with the launches of the calls of `uses`."""
    messages = read.messages(aid, children_of(path, aid), undecided)
    launched, passes = launches_of(aid, path, main, uses, undecided)
    return OperatorRead(launched, calls, tuple(messages), passes)


def calls_of(aid: str, path: Path, read: OperatorLines, commits: frozenset[tuple[str, float]],
             undecided: list[str]) -> tuple[tuple[Call, ...], Uses]:
    """The calls of the operator `aid` that `read` gives, each with its
    outcome, with `subjects` as the pairs `commits` gives, the result of a
    call that is not an error held as empty where `reads_output` does not
    hold, and the uses of
    `read` with each input read as `unfiled_call` gives it. The `Call` of a
    use is made anew only where a value it is made from changed since the
    last read on the same fold."""
    subjects = dict(commits)
    parent = read.parent
    calls: list[Call] = []
    uses = dict(read.uses)
    results, moved, tasks = read.results, read.moved, read.tasks
    making = _calls_made.read((aid, path, parent), read, commits)
    denied: set[str] = set()
    for call, (t, inp, tool) in uses.items():
        text, error = results.get(call, (None, False))
        if call in moved:
            text, error = background_output(aid, call, *moved[call], tasks, undecided)
        inp, text = unfiled_call(aid, tool, inp, text, undecided)
        uses[call] = (t, inp, tool)
        command = str(inp.get("command", "")) if tool == Tool.BASH else ""
        given = (t, tool, inp, text, error, command in denied)

        def make(lines: list[str]) -> MadeCall:
            merge = merge_outcome(aid, command, t, text, error, subjects, denied, lines)
            held = text if text is None or error or reads_output(tool, command, aid) else ""
            return (Call(aid, t, tool, inp, held, error, merge, call_conflicts(merge, text)),
                    command in denied)

        made, last_denied = making.item(call, lambda _: given, make, undecided)
        if last_denied:
            denied.add(command)
        else:
            denied.discard(command)
        calls.append(made)
    return tuple(calls), uses


def reads_output(tool: str, command: str, aid: str) -> bool:
    """Whether a step may read the text of the result of a call of the
    operator `aid` that is not an error: that of a Bash call other than a
    call of `next`, such as a merge or a call of `--under`, or of a
    SendMessage call, whose result tells whether the harness refused the
    message (`Agent.refused`)."""
    return tool == Tool.SEND_MESSAGE or (tool == Tool.BASH and not is_next(command, aid))


def launches_of(aid: str, path: Path, main: Path, uses: Uses,
                undecided: list[str]) -> tuple[AgentsRead, dict[str, PassReport]]:
    """The agents the operator `aid` launched by the calls of `uses`, and,
    for each solver pass it launched with an agent id, the read of its
    report."""
    agents: list[Agent] = []
    passes: dict[str, PassReport] = {}
    messaged: dict[str, frozenset[str]] = {}
    limited: dict[str, float] = {}
    from codex_reads import native_agents
    from review_anchor import read_anchor
    from run_reads import session_of
    from tree_reads import scratch

    session_scratch = scratch(session_of(path).name)
    native = native_agents(aid, session_scratch)
    if not any(tool == Tool.AGENT and described(str(inp.get("description", "")))
               for _, inp, tool in uses.values()):
        return native, {}
    found = launched(path, undecided)
    signs = turn_signs(path, [launch for launch in found if launch.pending])
    own = resumes(path, undecided)
    for launch in found:
        use = uses.get(launch.call)
        if use is None:
            continue
        d = described(str(use[1].get("description", "")))
        if d is None:
            continue
        reports = tuple(Report(r.time, r.text, r.file) for r in launch.reports(0.0, undecided))
        signed = (signs.get(launch.agent or "") if launch.pending else
                  last_sign(launch.entries, launch.since, {launch.agent or "", launch.call}))
        if signed is not None and signed[0] is Sign.LIMITED and ran_since(launch.path, signed[1]):
            signed = None
        prompt = str(use[1].get("prompt", ""))
        a = Agent(launch.agent, aid, d.role, d.subject, prompt,
                  use[0], launch.since, sign_state(signed, launch.pending), reports,
                  notifies=launch.since <= max(use[0], own.get(launch.agent or "", 0.0)),
                  report_file=brief_report_file(prompt),
                  reviewing=read_anchor(session_scratch, launch.agent)
                  if d.role in LAUNCHING_EDITORS and launch.pending else None)
        if d.role in MESSAGING and launch.path and launch.agent is not None:
            messaged[launch.agent] = sent_to(launch.path)
        if (signed is not None and signed[0] is Sign.LIMITED and launch.agent is not None
                and a.notifies):
            limited[launch.agent] = signed[1]
        if a.unreported and launch.agent:
            a = ended_with(a, reply_to(a, launch.since, undecided))
        a = filed_report(a)
        agents.append(a)
        if d.role in PASSES and launch.agent:
            passes[launch.agent] = pass_read(d.subject, d.role, use[0], main)
    enrolled = {a.agent_id for a in native.agents}
    return AgentsRead(tuple(a for a in agents if a.agent_id not in enrolled) + native.agents,
                      {**messaged, **native.messaged}, {**limited, **native.limited}), passes


def ran_since(path: Path | None, at: float) -> bool:
    """Whether the run whose transcript is at `path` has an entry later
    than `at`, as a run resumed or woken after a stop at `at` has, whoever
    resumed it. A run whose transcript is not known, `path` None, has
    none."""
    return path is not None and (t := latest_time(path)) is not None and t > at


def sign_state(signed: tuple[Sign, float] | None, pending: bool) -> AttemptState:
    """`Agent.state` of a launch whose latest sign is the first of
    `signed`, where `pending` gives whether the launch's result has not
    reached its operator: `Running` with the `Waits` the sign gives, or
    `Ended`."""
    match signed:
        case (Sign.STILL_RUNNING, _):
            return Running(Waits.STILL_RUNNING)
        case (Sign.LIMITED, _):
            return Running(Waits.LIMITED)
        case (sign, _) if sign in ENDED:
            return Ended()
        case _:
            return Running(Waits.AT_WORK) if pending else Ended()


def background_output(aid: str, call: str, task: str, output: Path | None,
                      tasks: dict[str, TaskStatus | None],
                      undecided: list[str]) -> tuple[str | None, bool]:
    """The result of the Bash call `call`, which the harness ran or moved
    to the background as task `task`, writing to `output`: None while no
    notification of the task reached the operator, and otherwise the
    output, as an error where the notification's status is not
    `completed`. An output whose file is gone, or named by no result, and
    a notification whose status is of no known form, are unknown: the call
    stays pending, and an `undecided` line names it."""
    if task not in tasks:
        return None, False
    status = tasks[task]
    if status is None or output is None or not is_file(output):
        undecided.append(mctx("{run}: the outcome of call {call}, which ran in the background "
                              "as task {task}, is unknown: {why}").format(
            run=aid, call=call, task=task,
            why=mctx("its notification's status is of no known form") if status is None
            else mctx("its output file is unknown or gone")))
        return None, False
    return file_text(output, "replace"), status is not TaskStatus.COMPLETED
