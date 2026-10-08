"""A change's merge and what follows it, as
[Merging a change](prompts/agents/notes/changes.md#merging-a-change) gives.

The merge is `scripts/merge_change.py`, whose checks cover the
`controlled_markdown` check. What a merge call did is read by that
script's own forms and by `master` (`state.Merge`):

- a call that never ran, as where the harness denied it, is written on the
  ticket in a line whose note opens with `coordinator`, which takes the
  change out of the operator's hands;
- a conflict in the rebase runs the change again with a new first editor:
  the command writes the old worktree and its branch on the ticket in a
  line that opens with `RERUN`, which no read of the change's worktree
  takes, and the final reply gives that line;
- a refusal whose output reports a `quotes` call a change to the documents
  broke goes to a new code editor in the change's worktree, with those
  calls as its items and their files as the files it may edit;
- any other refusal goes to the change's first editor as a finding of its
  checks.

Once the change is merged, an agent runs the checks its ticket's
`after-merge` field gives, then the command closes each `refactor` ticket
on a module a code editor of the change reports it split, or logs the part
the report gives as left unsplit, then each `question` ticket filed on the
change, then the change's own ticket."""

import re
import shlex
from pathlib import Path

from controlled_markdown.nodes import Rule
from operating import briefs
from operating.reports import splits
from operating.roles import Role
from operating.state import Agent, Call, Merge, State, Ticket
from operating.steps import Bash, Launch, Send, Step, bash_calls, simple_commands
from operating.tracker import COORDINATOR, RERUN, WORKTREE, log
from ticketing.vocabulary import MANY_IDEAS, Domain, Kind, Status

MERGE_SCRIPT = "scripts/merge_change.py"
FINDING_TAIL = 40
"""The lines of a refused merge's output a finding gives."""

BROKEN_QUOTES = (Rule.QUOTE_DOCUMENT, Rule.QUOTE_HEADING, Rule.QUOTE_WORDS)
"""The rules a `quotes` call breaks where a change to the documents moved
what it quotes."""

QUOTE_LINE = re.compile(rf"^(?P<path>\S+):(?P<line>\d+): (?:{'|'.join(BROKEN_QUOTES)}): .*$",
                        re.MULTILINE)
"""A line of the `controlled_markdown` check that reports such a call, in
the form `ControlledMarkdownError` prints."""


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


def merge_calls(state: State, t: Ticket) -> list[Call]:
    """The operators' merge calls on any worktree `t`'s log gives: those
    pending, and those with an outcome (`state.Merge`), which a call that
    merges no change, as a call of the script's `--help`, has not."""
    paths = {m[1] for line in t.log for m in WORKTREE.finditer(line.note)}
    return [c for c in state.calls if c.tool == "Bash" and MERGE_SCRIPT in str(
        c.input.get("command", "")) and any(p in str(c.input.get("command", "")) for p in paths)
        and (c.result is None or c.merge is not None)]


def merged(state: State, t: Ticket) -> bool:
    return any(c.merge is Merge.MERGED for c in merge_calls(state, t))


def merge_steps(state: State, t: Ticket, w: Path, latest: list[Agent]) -> Step | None:
    """The merge of the change in `w`, once its editors and its review have
    passed, and the step on a failed merge call."""
    command = merge_command(t, w)
    calls = [c for c in merge_calls(state, t) if str(w) in str(c.input.get("command", ""))]
    last = calls[-1] if calls else None
    reported = [r.time for a in latest if (r := a.last_report) is not None]
    if last is None or (reported and max(reported) > last.time):
        return Bash(command)
    match last.merge:
        case None:
            return None
        case Merge.NOT_RUN:
            first = (last.result or "").strip().splitlines()
            return Bash(log(t.number, Status.ASSIGNED, Status.ASSIGNED,
                            f"{COORDINATOR}: the merge call `{command}` did not run: "
                            f"{first[0] if first else 'no result text'}; worktree {w}",
                            state.me))
        case Merge.CONFLICT:
            branch = state.branches[w]
            return Bash(log(t.number, Status.ASSIGNED, Status.ASSIGNED,
                            f"{RERUN}: the rebase conflicts; the old worktree is {w} on "
                            f"branch {branch}", state.me))
        case Merge.REFUSED:
            return refused(state, t, w, last, latest)
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
            t.number, w, quotes, files, state.scratch / t.number, state.me),
            model=t.model(Role.CODE_EDITOR))
    first = latest[0] if latest else None
    if first is None or first.agent_id is None:
        return None
    tail = "\n".join(text.splitlines()[-FINDING_TAIL:])
    return Send(first.agent_id, briefs.merge_finding(t.number, tail))


def close(state: State, t: Ticket, agents: list[Agent]) -> Step | None:
    """The steps after a change's merge, or None while its checks after
    the merge run."""
    head = state.commits[0].hash
    if t.after_merge is not None:
        checks = state.agents_of(Role.AFTER_MERGE, t.number)
        if not checks:
            return Launch(Role.AFTER_MERGE, t.number, briefs.after_merge(
                t.number, t.after_merge, head))
        if checks[-1].pending:
            return None
    note = f"fixed {t.number} {head}"
    split: dict[str, str | None] = {}
    for a in agents:
        split.update(splits(a))
    for r in sorted(state.tickets.values(), key=lambda r: r.order):
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
    for q in sorted(state.tickets.values(), key=lambda q: q.order):
        if (q.kind is Kind.QUESTION and q.domain is Domain.CHANGE and q.subject == t.number
                and q.status is not Status.CLOSED):
            return Bash(log(q.number, Status.CLOSED, q.status, note, None))
    return Bash(log(t.number, Status.CLOSED, Status.ASSIGNED, note, None))
