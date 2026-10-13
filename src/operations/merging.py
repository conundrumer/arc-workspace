"""A change's merge and what follows it, as
[Merging a change](prompts/agents/notes/changes.md#merging-a-change) gives.

The merge is `scripts/merge_change.py`, whose checks cover the
`controlled_markdown` check. What a merge call did is read by that
script's own forms and by `master` (`state.Merge`,
`operator_reads.merge_outcome`, `merged`):

- a call that left edits in the worktree after its commit leaves the
  change unmerged, and once no editor of the change runs, the merge call
  on that worktree is given again;
- a call that never ran, as where the harness denied it, moves the change
  to `tickets/blocked/` with a line whose note opens with the wait on the
  user and gives the call, the first line of its result and the worktree;
  once a line moves the change from `tickets/blocked/` back to
  `tickets/assigned/` after that call, the merge call is given again;
- a conflict in the rebase runs the change again with a new first editor:
  the command writes the paths the rebase conflicts in, the old worktree
  and its branch on the ticket in a line whose note opens with `rerun`,
  which no read of the change's worktree takes, and the final reply gives
  that line;
- a refusal whose output reports a `quotes` call a change to the documents
  broke goes to a new code editor in the change's worktree, with those
  calls as its items and their files as the files it may edit;
- any other refusal goes to the change's first editor as a finding of its
  checks.

Once an agent launched on the change since its last move out of
`tickets/draft/` (`change_agents.of_change`), or a ticket analyst launched
on the step `handled.unmoved` gives for that finding, reports after the
latest merge call, the merge call is given again.

Once the change is merged, an agent runs the checks its ticket's
`after-merge` field gives, then the command closes each `refactor` ticket
on a module a code editor of the change reports it split, or logs the part
the report gives as left unsplit, then each `question` ticket filed on the
change, then the change's own ticket."""

import re
import shlex
from pathlib import Path

from controlled_markdown import form, mctx
from controlled_markdown.nodes import Rule, finding_lines
from operations import briefs, messages
from operations.change_agents import of_change
from operations.change_budget import TIME_NOTE, TIME_OPENING, left_draft, taken
from operations.filing import editor_scratch
from operations.reports import splits
from operations.roles import Role
from operations.state import Agent, Call, Merge, State, Ticket, Tool
from operations.command_words import simple_commands
from operations.handled import bash_calls, decided_by, unmoved
from operations.steps import Bash, Launch, Send, Step
from operations.log_commands import log
from operations.worktrees import WORKTREE
from ticketing.vocabulary import MANY_IDEAS, Domain, Kind, Note, Resolution, Status, Wait

MERGE_SCRIPT = "scripts/merge_change.py"
FINDING_TAIL = 40
"""The lines of a refused merge's output a finding gives."""

BROKEN_QUOTES = (Rule.QUOTE_DOCUMENT, Rule.QUOTE_HEADING, Rule.QUOTE_WORDS)
"""The rules a `quotes` call breaks where a change to the documents moved
what it quotes."""

QUOTE_LINE = finding_lines(BROKEN_QUOTES)
"""A line of the `controlled_markdown` check that reports such a call."""


NOT_RUN = mctx("{wait}: the merge call `{command}` did not run: {first}; worktree {worktree}")
"""The note of the line that moves a change whose merge call did not run
to `tickets/blocked/`."""

RERUN_CONFLICT = mctx("{rerun}: the rebase conflicts in {paths}; the old worktree is {worktree} "
                      "on branch {branch}")
"""The note of the line that runs a change again after a conflict in its
rebase. A note of that line written before the note gave the paths opens
with `RERUN_OPENING` and gives none."""

RERUN_OPENING = mctx("{rerun}: the rebase conflicts").format(rerun=Note.RERUN)

PATHS_SEP = ", "
"""What stands between two paths of `RERUN_CONFLICT` and of the `CONFLICT`
refusal of `scripts/merge_change.py`."""


def split_paths(text: str) -> tuple[str, ...]:
    return tuple(p for p in text.split(PATHS_SEP) if p)


def rerun_paths(note: str) -> tuple[str, ...] | None:
    """The paths a note that opens with `RERUN_OPENING` gives the rebase
    conflicts in, empty where it gives none, or None for any other note."""
    if not note.startswith(RERUN_OPENING):
        return None
    m = re.match(form(RERUN_CONFLICT.format(rerun=Note.RERUN, paths="{paths}",
                                            worktree="{worktree}", branch="{branch}"),
                      {"paths": r"(?P<paths>.*?)", "worktree": r".*", "branch": r".*"}), note)
    return () if m is None else split_paths(m["paths"])


MESSAGE = "-m"
"""The option of `merge_change.py` that gives a change's commit message."""


def merge_command(t: Ticket, w: Path) -> str:
    return shlex.join(["uv", "run", "python", MERGE_SCRIPT, str(w), MESSAGE, t.title])


def merge_messages(command: str) -> list[str] | None:
    """The commit message after each `MESSAGE` of the call of `merge_change.py`
    that the Bash command `command` runs, none where it runs none, or None
    where the shell's quoting in `command` is unbalanced."""
    found = simple_commands(command)
    if not found:
        return None
    for words in found:
        at = next((i for i, w in enumerate(words) if w.endswith(MERGE_SCRIPT)), None)
        if at is not None:
            rest = words[at + 1:]
            return [rest[i + 1] for i, w in enumerate(rest[:-1]) if w == MESSAGE]
    return []


def log_worktrees(t: Ticket) -> set[str]:
    """The worktrees `t`'s log gives."""
    return {m[1] for line in t.log for m in WORKTREE.finditer(line.note)}


def merge_calls(state: State, t: Ticket) -> list[Call]:
    """The operators' merge calls on any worktree `t`'s log gives: those
    pending, and those with an outcome (`state.Merge`), which a call that
    merges no change, as a call of the script's `--help`, has not."""
    paths = log_worktrees(t)
    return [c for c in state.transcripts.calls if c.tool == Tool.BASH and MERGE_SCRIPT in str(
        c.input.get("command", "")) and any(p in str(c.input.get("command", "")) for p in paths)
        and (c.result is None or c.merge is not None)]


def merged(state: State, t: Ticket) -> bool:
    """Whether the change `t` landed on `master`. A pending call that
    names a worktree that is gone counts as landed: `merge_change.py`
    removes a worktree only after it lands the change, and a call that
    runs `operate.py next` after the merge has no result yet. A commit of
    `master` whose subject is `t`'s title, made since `t` left
    `tickets/draft/`, counts as landed too, since the merge call gives
    that title as the commit message and an operator of another session
    may have made it, whose calls this session does not read."""
    gone = {p for p in log_worktrees(t) if Path(p) not in state.git.worktrees}
    if any(c.merge is Merge.MERGED or (c.result is None and any(
            p in str(c.input.get("command", "")) for p in gone)) for c in merge_calls(state, t)):
        return True
    since = left_draft(t)
    return any(c.subject == t.title and c.time >= since for c in state.git.commits)


def merge(state: State, t: Ticket, w: Path, latest: list[Agent]) -> Step | None:
    """The line that gives the change's agent-running time since its take,
    where none follows that take and that time reads, and then the merge."""
    take_line = taken(t)
    start = take_line.time if take_line is not None else left_draft(t)
    spent = state.computed.spent.get(t.number)
    if spent is not None and not any(ln.time >= start and ln.note.startswith(TIME_OPENING)
                                     for ln in t.log):
        return Bash(log(t.number, Status.ASSIGNED, Status.ASSIGNED,
                        TIME_NOTE.format(seconds=spent.seconds), state.me))
    return merge_steps(state, t, w, latest)


def merge_steps(state: State, t: Ticket, w: Path, latest: list[Agent]) -> Step | None:
    """The merge of the change in `w`, once its editors and its review have
    passed, again after a call that left the worktree with changes made
    after its commit or that a report of an agent on the change follows,
    and the step on a failed merge call."""
    command = merge_command(t, w)
    calls = [c for c in merge_calls(state, t) if str(w) in str(c.input.get("command", ""))]
    last = calls[-1] if calls else None
    message = None if last is None else finding(t, last, latest)
    on_step = [] if message is None else decided_by(state, unmoved(t, message))
    reported = [r.time for a in [*of_change(state, t.number), *on_step]
                if (r := a.last_report) is not None]
    if (last is None or (reported and max(reported) > last.time)
            or any(prev.status is Status.BLOCKED and ln.status is Status.ASSIGNED
                   and ln.time > last.time for prev, ln in zip(t.log, t.log[1:]))):
        return Bash(command)
    match last.merge:
        case None:
            return None
        case Merge.NOT_RUN:
            first = (last.result or "").strip().splitlines()
            return Bash(log(t.number, Status.BLOCKED, Status.ASSIGNED, NOT_RUN.format(
                wait=Wait.USER, command=command, first=first[0] if first else "no result text",
                worktree=w), state.me))
        case Merge.CONFLICT:
            branch = state.git.branches[w]
            return Bash(log(t.number, Status.ASSIGNED, Status.ASSIGNED, RERUN_CONFLICT.format(
                rerun=Note.RERUN, paths=PATHS_SEP.join(last.conflicts), worktree=w,
                branch=branch), state.me))
        case Merge.REFUSED:
            return refused(state, t, w, last, latest)
        case Merge.LEFT_EDITS:
            return Bash(command)
        case Merge.MERGED:
            return None


def refused(state: State, t: Ticket, w: Path, last: Call, latest: list[Agent]) -> Step | None:
    text = last.result or ""
    quotes = [m.group(0) for m in QUOTE_LINE.finditer(text)]
    if quotes:
        if any(a.role is Role.CODE_EDITOR and a.launched > last.time for a in latest):
            return None
        files = sorted({m["path"] for m in QUOTE_LINE.finditer(text)})
        return Launch(Role.CODE_EDITOR, t.number, briefs.quotes_fix(
            t.number, w, quotes, files,
            editor_scratch(t.number, Role.CODE_EDITOR, state.scratch), state.me),
            model=t.model(Role.CODE_EDITOR))
    return finding(t, last, latest)


def finding(t: Ticket, last: Call, latest: list[Agent]) -> Send | None:
    """The message that gives the refusal of the merge call `last` to the
    change's first editor, where `last` was refused on no `quotes` call."""
    text = last.result or ""
    first = latest[0] if latest else None
    if (last.merge is not Merge.REFUSED or QUOTE_LINE.search(text) is not None
            or first is None or first.agent_id is None):
        return None
    tail = "\n".join(text.splitlines()[-FINDING_TAIL:])
    return Send(first.agent_id, messages.merge_finding(t.number, tail))


def close(state: State, t: Ticket, agents: list[Agent]) -> Step | None:
    """The steps after a change's merge, or None while its checks after
    the merge run."""
    head = state.git.commits[0].hash
    if t.after_merge is not None:
        checks = state.agents_of(Role.AFTER_MERGE, t.number)
        if not checks:
            return Launch(Role.AFTER_MERGE, t.number, briefs.after_merge(
                t.number, t.after_merge, head))
        if checks[-1].pending:
            return None
    note = f"{Resolution.FIXED.value} {t.number} {head}"
    split: dict[str, str | None] = {}
    for a in agents:
        split.update(splits(a))
    for r in sorted(state.tracker.tickets.values(), key=lambda r: r.order):
        target = r.title.split(":", 1)[0].strip(" `")
        if (r.kind is not Kind.REFACTOR or r.status is Status.CLOSED
                or not r.title.endswith(MANY_IDEAS) or target not in split):
            continue
        part = split[target]
        command = (log(r.number, Status.CLOSED, r.status, note, None) if part is None else
                   log(r.number, r.status, r.status,
                       f"left unsplit by change {t.number}: {part}", None))
        if not any(not c.error for c in bash_calls(state, command)):
            return Bash(command)
    for q in sorted(state.tracker.tickets.values(), key=lambda q: q.order):
        if (q.kind is Kind.QUESTION and q.domain is Domain.CHANGE and q.subject == t.number
                and q.status is not Status.CLOSED):
            return Bash(log(q.number, Status.CLOSED, q.status, note, None))
    ids = [a.agent_id for a in agents]
    # An agent with no known id leaves the line with no run, and the
    # change with no known cost (`scripts/ticket_watch.py`).
    runs = "" if None in ids else "".join(f" {i}" for i in ids)
    return Bash(log(t.number, Status.CLOSED, Status.ASSIGNED, note + runs, None))
