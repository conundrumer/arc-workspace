"""The operator's command: it reads the state from the ticket tracker, git,
the worktrees and the transcripts of the session's operators, and prints
the next step of the operator's procedures, which the package `operating`
computes. `HELP`, which `--help` prints, gives its usage forms.

The command keeps no file of its own: each fact it reads is in the
tracker, in git, under `work/`, or in a transcript."""

import argparse
import math
import os
import re
import sys
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from controlled_markdown import mctx
from engine import checkout
from handbook.paths import console_importable, importable

console_importable()
# `scripts/` is no package: a test loads this module by its path, with
# `scripts/` off `sys.path`, and the modules below import from there.
importable(checkout.scripts())

from agent_launches import (Launch as Launched, launched, pending_agents, resumes,  # noqa: E402
                            run_launches, timed_entries)
from agent_reports import STILL_RUNNING, agent_notifications  # noqa: E402
from agent_turns import first_time, has_ended, turns  # noqa: E402
from context_bound_hook import OPERATOR, past_bound  # noqa: E402
from merge_change import conflicted, ran  # noqa: E402
from open_agents import work_open  # noqa: E402
from profile_runs import budget_of  # noqa: E402
from run_reads import (BACKGROUND_TASK, MAIN, agent_messages, agent_type, blocks,  # noqa: E402
                       context_size, is_prompt, message_text, notified, run_entries,
                       session_agents, text_of)
from senders import Sender, sender  # noqa: E402
from ticket_files import TICKET_NAME, ticket_files, ticket_name  # noqa: E402
from ticket_form import FRONT, title  # noqa: E402
from ticket_log import MINUTE_FORM, TIME_FORM, holder, log_lines  # noqa: E402
from ticket_numbers import TICKET_NUMBER, session_index, ticket_number  # noqa: E402
from ticket_settle import to_settle  # noqa: E402
from transcripts import (Refused, entries_back, epoch, find, read_entries,  # noqa: E402
                         session_directory)

from operating import alerts, briefs, plan, steps  # noqa: E402
from operating.directives import named  # noqa: E402
from operating.roles import PASSES, Role, described, editors_of  # noqa: E402
from operating.merging import MERGE_SCRIPT  # noqa: E402
from operating.state import (Agent, Call, Commit, LogLine, Merge, Message,  # noqa: E402
                             Report, State, Ticket)
from operating.steps import (COMMAND, FOREGROUND_MS, KEY_LENGTH, WAIT_SECONDS,  # noqa: E402
                             Again,
                             Bash, EndTurn, Launch, Send, Stop, Wait, key, next_command,
                             pass_over, printed, wait_command)
from operating.task_work import restore, set_aside  # noqa: E402
from operating.tracker import worktree  # noqa: E402
from ticketing.vocabulary import Domain, Kind, Status  # noqa: E402

HELP = mctx("""
    - Usage:
        ```
        uv run python scripts/operate.py next <agent id>
        uv run python scripts/operate.py wait <agent id>
        uv run python scripts/operate.py set-aside <task id> analyze|create
        uv run python scripts/operate.py restore <task id>
        uv run python scripts/operate.py pass-over <agent id> <key> '<line>'
        ```
    - `next` prints the next step of the operator whose agent id it is given: one call to make, with its parameters in full, or the final reply. The brief of a launch other than a solver pass's ends with the line `Budget: N minutes`, where the budget of its agent type over every run of that type, as `profile_runs.py --help` gives a type's budget, is N minutes rounded up, and where that type has none, it has no such line. It holds back the launch of an agent type whose definition under `.claude/agents/` a commit of `master` changed less than {reload} seconds ago until those seconds have passed. Where no step is ready and no agent runs that this operator launched or last resumed itself, other than one a notification said has not reported yet, it blocks for up to {block} seconds until one is, then prints it, or prints that the operator runs it again.
    - After each call it prints, `next` prints that step's key, which is the same at each read of the state that gives the same step. `pass-over` passes over the step whose key it is given, by the `Override:` or `Decision:` line it is given, which rules the step out. From then on, `next` passes that step over for each operator, gives the coordinator that step, once, as one its procedure waits on, and goes on with the other procedures. A pipeline whose next pass is passed over stops instead.
    - `wait` is the operator's wait in the background: it ends once the state gives a step, or after {wait} seconds.
    - `set-aside` sets aside a task's earlier work in the main worktree before an Analyze or a Create pass, and `restore` puts it back and removes the task's claim, as the section `Passes on a task` of `prompts/agents/notes/launching.md` gives.
    - The session is the one `CLAUDE_CODE_SESSION_ID` gives, and the command refuses where the shell gives none.
    """)

BLOCK_SECONDS = (FOREGROUND_MS // 1000) - 30
"""The longest foreground block of `next`, under the bound on a
foreground call, with room for the read of the state."""

POLL_SECONDS = 15
CALLS = (Launch, Send, Bash, Stop)
"""The steps after whose call the operator runs `next` again."""
COMMITS = 300
"""The commits of `master` read for After a batch, newest first."""

CODE_DIRS = ("src/", "scripts/", "tests/")
TASK_ID = re.compile(r"[0-9a-f]{8}")
STEP_KEY = re.compile(rf"[0-9a-f]{{{KEY_LENGTH}}}")


def main_tree() -> Path:
    return checkout.main_worktree(checkout.ROOT)


def log_time(text: str) -> float:
    """The time of a log line, which the log gives to the second or, in
    older lines, to the minute."""
    for form in (TIME_FORM, MINUTE_FORM):
        try:
            return datetime.strptime(text, form).replace(tzinfo=UTC).timestamp()
        except ValueError:
            continue
    raise Refused(mctx("`{text}` is no log line's time").format(text=text))


def read_ticket(path: Path) -> Ticket:
    name = ticket_name(path)
    text = path.read_text()
    head = re.match(FRONT, text)
    if head is None:
        raise Refused(mctx("{path} has no front matter").format(path=path))
    fields = dict(line.split(": ", 1) for line in head.group("fields").splitlines())
    lines = tuple(LogLine(log_time(m.group().split(" ", 1)[0]), Status(m["status"]),
                          m["agent"], m["id"], m["note"] or "") for m in log_lines(text))
    editors = fields.get("editors")
    return Ticket(
        number=str(name.number), order=name.number.order, session=name.number.session,
        status=Status(path.parent.name), kind=Kind(head["kind"]), domain=Domain(name.domain),
        subject=name.subject, filer=name.agent, filed=lines[0].time if lines else 0.0,
        title=title(path, text),
        depends_on=tuple(d.strip() for d in fields.get("depends-on", "").split(",") if d.strip()),
        priority=int(fields.get("priority", "50")),
        editors=None if editors is None else editors_of(editors),
        after_merge=fields.get("after-merge"), log=lines, holder=holder(text), path=path)


def read_tickets(tickets: Path) -> dict[str, Ticket]:
    """Each ticket of the tracker. A ticket that moves between the listing
    and its read is read again from a new listing. A closed ticket whose
    name has no number in the form `ticket_files.TICKET_NAME` gives is one
    no number finds, so no procedure reads it."""
    for _ in range(3):
        try:
            out = {}
            for s in Status:
                for path in ticket_files(tickets, s):
                    if s is Status.CLOSED and not TICKET_NAME.fullmatch(path.name):
                        continue
                    t = read_ticket(path)
                    out[t.number] = t
            return out
        except FileNotFoundError:
            continue
    raise Refused(mctx("the tickets moved during three reads of the tracker"))


def git(main: Path, *argv: str) -> str:
    return checkout.git_out(main, *argv)


def worktrees(main: Path) -> dict[Path, str | None]:
    """Each worktree, with its branch, or None where it stands on none."""
    out: dict[Path, str | None] = {}
    tree: Path | None = None
    for line in git(main, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            tree = Path(line.split(" ", 1)[1])
            out[tree] = None
        elif line.startswith("branch refs/heads/") and tree is not None:
            out[tree] = line.removeprefix("branch refs/heads/")
    return out


def merge_outcome(command: str, result: str | None, error: bool) -> Merge | None:
    """What a Bash call of `command` that `merge_change.py` runs did, by
    that script's forms, or None for any other call and one still
    pending."""
    if MERGE_SCRIPT not in command or result is None:
        return None
    if not error:
        return Merge.MERGED
    if not ran(result):
        return Merge.NOT_RUN
    return Merge.CONFLICT if conflicted(result) else Merge.REFUSED


def commits(main: Path) -> tuple[Commit, ...]:
    out: list[Commit] = []
    for chunk in git(main, "log", "master", f"-n{COMMITS}", "--format=%x00%H %ct",
                     "--name-only").split("\0")[1:]:
        head, _, names = chunk.partition("\n")
        sha, ct = head.split()
        out.append(Commit(sha, float(ct), any(n.startswith(CODE_DIRS) for n in names.split())))
    return tuple(out)


def code_review(main: Path) -> int | None:
    tags = [int(t.rsplit("/", 1)[1]) for t in git(main, "tag", "-l", "code-review/*").split()
            if t.rsplit("/", 1)[1].isdigit()]
    return max(tags) if tags else None


def claims(main: Path) -> dict[str, str]:
    return {p.parent.name: p.read_text().strip()
            for p in (main / "work" / "task").glob("*/claim")}


def pass_tickets(report: str, main: Path) -> tuple[str, ...] | None:
    """The numbers the report whose path a pass replied with lists under
    `## Tickets filed`, or None where the reply is no report's path."""
    text = report.strip()
    if "\n" in text or not text:
        return None
    path = Path(text) if Path(text).is_absolute() else main / text
    if not path.is_file():
        return None
    body = path.read_text().split("## Tickets filed", 1)
    if len(body) < 2:
        return None
    section = body[1].split("\n## ", 1)[0]
    return tuple(m.group(0).rstrip("_") for m in re.finditer(
        rf"{TICKET_NUMBER.pattern}_", section))


def ran_command(path: Path) -> bool:
    """Whether the transcript at `path` holds a Bash call of the command."""
    return any(b.get("name") == "Bash" and COMMAND in str((b.get("input") or {}).get("command"))
               for e in read_entries(path, naming={COMMAND}) if e.get("type") == "assistant"
               for b in blocks(e, "tool_use"))


def operator_runs(session: str, me: str) -> list[tuple[str, Path]]:
    """The operator `me` and each other operator of the session that ran
    the command, by agent id, in the order of their first entry. An
    operator that never ran the command left no work under its procedures.
    An operator whose transcript holds no timestamped entry has made no
    call yet, and is left out."""
    directory = session_directory(find(session))
    runs = [(aid, p, t) for aid, p in session_agents(directory).items()
            if agent_type(p) == OPERATOR and (aid == me or ran_command(p))
            and (t := first_time(p)) is not None]
    return [(aid, p) for aid, p, _ in sorted(runs, key=lambda r: r[2])]


WRAP = ("The coordinator sent a message while you were working:",
        "Address this before completing your current task.")
"""The lines the harness puts around a message from the coordinator that
arrives while the operator works."""


def unwrapped(text: str) -> str:
    return "\n".join(line for line in text.splitlines() if line.strip() not in WRAP)


def read_operator(aid: str, path: Path, main: Path, undecided: list[str],
                  agents: list[Agent], calls: list[Call], messages: list[Message],
                  passes: dict[str, tuple[str, ...] | None]) -> None:
    entries = run_entries(path)
    uses: dict[str, tuple[float, dict[str, Any], str]] = {}
    results: dict[str, tuple[str, bool]] = {}
    briefed = False
    children = run_launches(path)[1].get(aid, frozenset())
    for e in entries:
        stamp = e.get("timestamp")
        if e.get("type") == "assistant" and stamp:
            for b in blocks(e, "tool_use"):
                uses[b.get("id", "")] = (epoch(stamp), b.get("input") or {}, b.get("name", ""))
        elif e.get("type") == "user":
            for b in blocks(e, "tool_result"):
                results[b.get("tool_use_id", "")] = (text_of(b.get("content")),
                                                      bool(b.get("is_error")))
        if stamp and is_prompt(e):
            if not briefed or sender(e, MAIN, frozenset()) is Sender.PARENT:
                briefed = True
                messages.append(Message(aid, epoch(stamp), None, unwrapped(message_text(e))))
            else:
                messages += [Message(aid, epoch(stamp), s, text)
                             for s, text in agent_messages(e) if s not in children]
    for call, (t, inp, tool) in uses.items():
        result = results.get(call)
        text, error = (None, False) if result is None else result
        calls.append(Call(aid, t, tool, inp, text, error, merge_outcome(
            str(inp.get("command", "")) if tool == "Bash" else "", text, error)))
    if not any(tool == "Agent" and described(str(inp.get("description", "")))
               for _, inp, tool in uses.values()):
        return
    found = launched(path, undecided)
    pending = (set(pending_agents(path, undecided))
               if any(launch.pending and launch.agent for launch in found) else set())
    own = resumes(timed_entries(path), path.stem, None, undecided)
    for launch in found:
        use = uses.get(launch.call)
        if use is None:
            continue
        d = described(str(use[1].get("description", "")))
        if d is None:
            continue
        reports = tuple(Report(r.time, r.text) for r in launch.reports(0.0, undecided))
        a = Agent(launch.agent, aid, d.role, d.subject, str(use[1].get("prompt", "")),
                  use[0], launch.pending, reports,
                  still_running=launch.pending and still_running(launch, undecided),
                  notifies=launch.since <= max(use[0], own.get(launch.agent or "", 0.0)))
        if launch.pending and launch.agent and launch.agent not in pending:
            a = ended_with(a, None if any(r.time > launch.since for r in reports)
                           else reply_since(launch.agent, launch.since))
        agents.append(a)
        if d.role in PASSES and launch.agent and reports:
            passes[launch.agent] = pass_tickets(reports[-1].text, main)


def final_reply(path: Path) -> Report | None:
    """The final reply in the transcript at `path`: the text of the entry
    that ends its last turn, or the message of the call that ends it, where
    its turn has ended."""
    if not has_ended(path):
        return None
    entries = run_entries(path)
    _, ends = turns(entries)
    if not ends:
        return None
    e = entries[max(ends)]
    stamp = e.get("timestamp")
    if not stamp:
        return None
    if e.get("type") == "assistant":
        text = "\n".join(str(b.get("text", "")) for b in blocks(e, "text"))
    else:
        ended = {b.get("tool_use_id") for b in blocks(e, "tool_result")}
        text = next((str((b.get("input") or {}).get("message", ""))
                     for x in entries if x.get("type") == "assistant"
                     for b in blocks(x, "tool_use") if b.get("id") in ended), "")
    return Report(epoch(stamp), text) if text.strip() else None


def reply_since(agent: str, since: float) -> Report | None:
    """The final reply in the transcript of `agent`, where it gives one
    after `since`."""
    r = final_reply(find(agent))
    return r if r is not None and r.time > since else None


def stalled_reports(agents: list[Agent], messages: list[Message]) -> dict[str, Report]:
    """The final reply in the transcript of each agent a stall alert names
    that is pending, given after its launch."""
    out: dict[str, Report] = {}
    pending = {a.agent_id: a for a in agents if a.pending and a.agent_id}
    for m in messages:
        alert = alerts.parsed(m) if m.sender is not None else None
        if alert is None or alert.kind is not alerts.AlertKind.STALL:
            continue
        a = pending.get(alert.agent)
        if a is None or alert.agent in out:
            continue
        r = reply_since(alert.agent, a.launched)
        if r is not None:
            out[alert.agent] = r
    return out


def ended_with(a: Agent, reply: Report | None) -> Agent:
    """`a` as no longer pending, with `reply` as its last report."""
    return replace(a, pending=False, reports=a.reports if reply is None else (*a.reports, reply))


def ended_elsewhere(agents: list[Agent], me: str) -> dict[str, Report | None]:
    """For each pending agent of another operator whose work is no longer
    open, an agent whose report reaches no running operator, the final
    reply in its transcript, where it gives one after its launch, or
    None."""
    out: dict[str, Report | None] = {}
    for a in agents:
        if not a.pending or a.operator == me or a.agent_id is None or a.agent_id in out:
            continue
        path = find(a.agent_id)
        if work_open(path, []):
            continue
        out[a.agent_id] = reply_since(a.agent_id, a.launched)
    return out


def still_running(launch: Launched, undecided: list[str]) -> bool:
    """Whether a notification since the launch or the last resume of
    `launch` says its agent stopped with work of its own still running."""
    return any((n.note or "").startswith(STILL_RUNNING)
               for e in launch.entries if e.get("timestamp") and epoch(e["timestamp"]) > launch.since
               for n in agent_notifications(e, launch.agent, launch.call, undecided))


def wait_task(me: str, path: Path) -> str | None:
    """The ID of the operator's wait in the background that has not ended:
    no notification of it reached the operator, and no TaskStop call of
    the operator on it has its result."""
    entries = run_entries(path)
    waits: set[str] = set()
    stops: dict[str, str] = {}
    for e in entries:
        for b in blocks(e, "tool_use") if e.get("type") == "assistant" else []:
            inp = b.get("input") or {}
            if not (call := b.get("id")):
                continue
            if b.get("name") == "Bash" and inp.get("command") == wait_command(me):
                waits.add(call)
            elif b.get("name") == "TaskStop" and inp.get("task_id"):
                stops[call] = str(inp["task_id"])
    started: list[str] = []
    ended: set[str] = set()
    for e in entries:
        if e.get("type") != "user":
            continue
        result = e.get("toolUseResult")
        for b in blocks(e, "tool_result"):
            call = b.get("tool_use_id")
            if call in waits and isinstance(result, dict) and result.get(BACKGROUND_TASK):
                started.append(str(result[BACKGROUND_TASK]))
            if call in stops:
                ended.add(stops[call])
        ended.update(notified(e))
    running = [t for t in started if t not in ended]
    return running[-1] if running else None


def read_state(me: str) -> State:
    session = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session:
        raise Refused(mctx("the shell gives no `CLAUDE_CODE_SESSION_ID`"))
    main = main_tree()
    tickets_dir = main / "tickets"
    undecided: list[str] = []
    runs = operator_runs(session, me)
    if me not in dict(runs):
        runs.append((me, find(me)))
    agents: list[Agent] = []
    calls: list[Call] = []
    messages: list[Message] = []
    passes: dict[str, tuple[str, ...] | None] = {}
    for aid, path in runs:
        read_operator(aid, path, main, undecided, agents, calls, messages, passes)
    stalled = stalled_reports(agents, messages)
    ended: dict[str, Report | None] = {**ended_elsewhere(agents, me), **stalled}
    agents = [ended_with(a, ended[a.agent_id]) if a.pending and a.agent_id in ended else a
              for a in agents]
    known = {a.agent_id for a in agents if a.agent_id}
    for line in dict.fromkeys(undecided):
        if line.split(":", 1)[0] in known:
            print(f"operate: undecided: {line}", file=sys.stderr)
    tickets = read_tickets(tickets_dir)
    index = session_index(tickets_dir, session)
    holders = {t.holder for t in tickets.values() if t.status is Status.ASSIGNED and t.holder}
    my_path = dict(runs)[me]
    trees = worktrees(main)
    state = State(
        me=me, now=time.time(), session=session, index=index, main_tree=main,
        scratch=scratch(session), operators=tuple(aid for aid, _ in runs),
        open_operators=frozenset(aid for aid, p in runs[[a for a, _ in runs].index(me) + 1:]
                                 if work_open(p, [])),
        past_bound=past_bound(context_size(entries_back(my_path))),
        open_holders=frozenset(h for h in holders if work_open(find(h), [])),
        tickets=tickets, agents=tuple(sorted(agents, key=lambda a: a.launched)),
        calls=tuple(sorted(calls, key=lambda c: c.time)), messages=tuple(messages),
        to_settle=(), worktrees=frozenset(trees), claims=claims(main),
        commits=commits(main), code_review=code_review(main), wait_task=wait_task(me, my_path),
        pass_tickets=passes, stalled=stalled,
        passed={p[0]: p[1] for c in calls if c.tool == "Bash" and not c.error
                and c.result is not None
                and (p := pass_over(str(c.input.get("command", "")))) is not None},
        branches={w: b for w, b in trees.items() if b is not None})
    given = [ticket_number(n) for n in named(state) if n in tickets]
    held = {w for t in tickets.values() if t.status is Status.ASSIGNED and t.holder == me
            and (w := worktree(t, state)) is not None}
    return replace(state, to_settle=tuple(str(n) for n in to_settle(tickets_dir, index, given)),
                   gate_outputs={w: gate_outputs(w) for w in held})


ACCEPTED = "tests/gate/accepted"


def gate_outputs(tree: Path) -> tuple[str, ...]:
    """The accepted gate outputs the change in the worktree `tree` writes,
    against `master`."""
    changed = git(tree, "diff", "--name-only", "master", "--", ACCEPTED).split()
    added = git(tree, "ls-files", "--others", "--exclude-standard", "--", ACCEPTED).split()
    return tuple(sorted({*changed, *added}))


def scratch(session: str) -> Path:
    """The session's scratchpad directory, as the section `Launching` of
    `prompts/agents/notes/launching.md` gives it, for a session that
    started in the main worktree, as the coordinator's does."""
    started = str(main_tree())
    return (Path(f"/private/tmp/claude-{os.getuid()}") / started.replace("/", "-") / session
            / "scratchpad")


def with_budget(step: Launch) -> Launch:
    """`step` with the budget line HELP gives."""
    if step.role in PASSES:
        return step
    seconds = budget_of(step.role.agent_type, [])
    if seconds is None:
        return step
    return replace(step, brief=step.brief + "\n" + briefs.BUDGET.format(minutes=math.ceil(seconds / 60)))


RELOAD_SECONDS = 30
"""How long after a change to an agent's definition the harness takes to
load it, as the section `Launching` of `prompts/agents/notes/launching.md`
gives."""


def reloading(step: Launch) -> float:
    """The seconds left until the harness has loaded the definition of the
    agent type `step` launches, after the last commit of `master` that
    changed it, or 0."""
    path = f".claude/agents/{step.role.agent_type}.md"
    out = git(main_tree(), "log", "-1", "--format=%ct", "master", "--", path).strip()
    return max(0.0, float(out) + RELOAD_SECONDS - time.time()) if out else 0.0


def next_step(me: str) -> int:
    deadline = time.monotonic() + BLOCK_SECONDS
    while True:
        step = plan.next_step(read_state(me))
        if isinstance(step, Launch) and (left := reloading(step)) > 0:
            if time.monotonic() + left > deadline:
                step = Again(mctx("the reload of `{type}`").format(type=step.role.agent_type))
            else:
                time.sleep(left)
                continue
        if not isinstance(step, Again) or time.monotonic() + POLL_SECONDS > deadline:
            print(printed(with_budget(step) if isinstance(step, Launch) else step, me))
            if isinstance(step, CALLS):
                print(f"\nThen run `{next_command(me)}`. Step key: {key(step)}.")
            return 0
        time.sleep(POLL_SECONDS)


def wait(me: str) -> int:
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() + POLL_SECONDS < deadline:
        time.sleep(POLL_SECONDS)
        step = plan.next_step(read_state(me))
        if not isinstance(step, (Wait, EndTurn)):
            print(mctx("A step is ready: run `{command}`.").format(command=next_command(me)))
            return 0
    print(mctx("The wait ended: run `{command}`.").format(command=next_command(me)))
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("--help", "-h"):
        print(HELP.format(block=BLOCK_SECONDS, wait=WAIT_SECONDS, reload=RELOAD_SECONDS))
        return 0
    parser = argparse.ArgumentParser(prog="operate.py", add_help=False)
    parser.add_argument("action", choices=["next", "wait", "set-aside", "restore",
                                           steps.PASS_OVER])
    parser.add_argument("ident")
    parser.add_argument("rest", nargs="*")
    args = parser.parse_args(argv)
    try:
        match args.action:
            case "next":
                return next_step(args.ident)
            case "wait":
                return wait(args.ident)
            case "set-aside":
                if (len(args.rest) != 1 or args.rest[0] not in (Role.ANALYZE, Role.CREATE)
                        or not TASK_ID.fullmatch(args.ident)):
                    parser.error("set-aside takes a task id and `analyze` or `create`")
                print(set_aside(main_tree(), args.ident, Role(args.rest[0])))
                return 0
            case steps.PASS_OVER:
                if len(args.rest) != 2 or not STEP_KEY.fullmatch(args.rest[0]):
                    parser.error("pass-over takes an agent id, a step's key and a line")
                print(mctx("Step {key} is passed over.").format(key=args.rest[0]))
                return 0
            case _:
                if args.rest:
                    parser.error("restore takes a task id alone")
                restore(main_tree(), args.ident)
                return 0
    except Refused as exc:
        print(f"operate: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
