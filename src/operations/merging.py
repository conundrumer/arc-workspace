"""A change's merge and what follows it, as
[Merging a change](prompts/agents/notes/changes.md#merging-a-change) gives.

The merge is `scripts/merge_change.py`, whose checks cover the
`controlled_markdown` check. What a merge call did is read by that
script's own forms and by `master` (`state.Merge`,
`operator_reads.merge_outcome`, `merged`):

- a call that left edits in the worktree after its commit leaves the
  change unmerged, and once no editor of the change runs, the merge call
  on that worktree is given again;
- a call that never ran, as where the harness denied it, hands the change
  to the coordinator (`HANDED_OFF`), with a note that gives the call, the
  first line of its result and the worktree;
- a conflict in the rebase leaves the change in its worktree, put by the
  script onto `master` with git's conflict markers in the paths that
  conflict: the command writes those paths on the ticket in a line whose
  note opens with `conflict`, once per such call, and the refusal then
  goes as a finding as any other refusal goes;
- a conflict where the script could not put the change onto `master`
  (`NOT_PUT_ON`) hands the change to the coordinator, with a note that
  gives the call, the script's refusal line and the worktree, since no
  editor may move the branch;
- a hand-off moves the change to `tickets/open/` and back to
  `tickets/assigned/` with the session id as its holder, which holds it
  live while the coordinator's session runs, so no operator takes it; the
  command then sends the coordinator the note as an `unfinished:` item,
  once (`handoffs`). Once an operator takes the change from
  `tickets/open/` after the hand-off, or a line moves it from
  `tickets/blocked/` back to `tickets/assigned/` after the call, the merge
  call is given again;
- a refusal whose output reports a `quotes` call a change to the documents
  broke goes to a new code editor in the change's worktree, with those
  calls as its items and their files as the files it may edit;
- any other refusal goes as a finding of its checks to the change's doc
  editor, where the change has one and the check its refusal line gives
  as failed is a check of the documents (`DOCUMENT_CHECKS`), or each path
  its rebase conflicts in is a document (`DOCUMENT_SUFFIX`), and
  otherwise to the change's first editor;
- two refusals that give one tree (`REFUSED_TREE`) give one finding
  message, with the output of the first refused merge call on that
  worktree that gives that tree. Whether two refusals give one message
  rests on the tree alone: the change rebased on another commit of
  `master` gives another tree, unless the checks ran on the same content,
  and the output that message gives holds the `master` commit of the
  first call.

Once an agent launched on the change since its last move out of
`tickets/draft/` (`change_agents.of_change`), or a ticket analyst launched
on the step `handled.unmoved` gives for that finding, reports after the
latest merge call, the merge call is given again.

Once the change is merged, an agent runs the steps and checks its
ticket's `after-merge` field gives, then the command closes each `refactor` ticket
on a module a code editor of the change reports it split, or logs the part
the report gives as left unsplit, then each `question` ticket filed on the
change, then the change's own ticket."""

import re
import shlex
from collections.abc import Sequence
from pathlib import Path

from controlled_markdown import form, mctx
from controlled_markdown.nodes import Rule, finding_lines
from operations import briefs, messages
from operations.change_agents import of_change, settled
from operations.change_budget import TIME_NOTE, TIME_OPENING, left_draft, taken
from operations.filing import editor_scratch
from operations.reports import splits, unread_split
from operations.roles import Role
from operations.constants import COORDINATOR
from operations.state import Agent, Call, Commit, LogLine, Merge, State, Ticket, Tool
from operations.command_words import simple_commands
from operations.handled import ask_again, decided_by, done, sent, unmoved
from operations.steps import Bash, Launch, Send, Step, labeled
from operations.log_commands import log
from operations.worktrees import WORKTREE
from ticketing.vocabulary import MANY_IDEAS, Domain, Kind, Note, Resolution, Status

MERGE_SCRIPT = "scripts/merge_change.py"

PREFIX = "merge_change: "
"""The opening of each line `merge_change.py` prints, on stdout and on
stderr."""

REFUSED = PREFIX + "refused: "
"""The opening of the line of a refusal."""

REFUSED_TREE = mctx("; the refused commit's tree is {tree}")
"""The end of a refusal of a change after its rebase: the tree of the
commit it refused."""

TREE = re.compile(form(REFUSED_TREE, {"tree": r"(?P<tree>[0-9a-f]+)"}) + "$", re.M)

CONTEXT_WRITE = ("scripts/context.py", "--write")
"""The command, after `uv run python`, that writes the generated files."""


def check_name(argv: Sequence[str], files: Sequence[str] = ()) -> str:
    """The name a merge's lines give the check whose command is `argv`
    with `files` after it."""
    command = " ".join(argv)
    return CHECK_FILES.format(command=command, n=len(files)) if files else command


CHECK_FILES = mctx("{command} on {n} files")
"""The name of a check that takes files, which the files would make too
long for a line."""


CHECK_FAILED = mctx("the check `{s}` failed:")
"""The line that opens a failed check's output in a refusal, `s` the
check's `check_name`."""

MARKDOWN_ARGV = ("uv", "run", "python", "-m", "controlled_markdown", "check")

DOCUMENT_CHECKS = (MARKDOWN_ARGV, ("uv", "run", "python", *CONTEXT_WRITE))
"""The checks of the documents a merge runs, first among its checks."""

FINDING_TAIL = 40
"""The lines of a refused merge's output a finding gives."""

BROKEN_QUOTES = (Rule.QUOTE_DOCUMENT, Rule.QUOTE_HEADING, Rule.QUOTE_WORDS)
"""The rules a `quotes` call breaks where a change to the documents moved
what it quotes."""

QUOTE_LINE = finding_lines(BROKEN_QUOTES)
"""A line of the `controlled_markdown` check that reports such a call."""


HANDED_OFF = mctx("handed to the coordinator: the merge call `{command}` {outcome}; "
                  "worktree {worktree}")
"""The note of the lines that hand a change to the coordinator."""

HANDED_OFF_OPENING = HANDED_OFF.split("{", 1)[0]

NOT_RUN = mctx("did not run: {first}")
"""The outcome a `HANDED_OFF` note gives of a merge call that did not run."""

RERUN_CONFLICT = mctx("{rerun}: the rebase conflicts in {paths}; the old worktree is {worktree} "
                      "on branch {branch}")
"""The note of a line that ran a change again after a conflict in its
rebase. No step writes such a line now. A note of that line written before
the note gave the paths opens with `RERUN_OPENING` and gives none."""

RERUN_OPENING = mctx("{rerun}: the rebase conflicts").format(rerun=Note.RERUN)
"""The opening of a note of `RERUN_CONFLICT`. No step writes such a note
now."""

CONFLICT_NOTE = mctx("{conflict}: the rebase onto `master` conflicts in {paths}")
"""The note of the line that gives the paths a merge call's rebase
conflicts in."""

CONFLICT_OPENING = mctx("{conflict}: the rebase onto `master` conflicts").format(
    conflict=Note.CONFLICT)

NOT_PUT_ON = mctx("the rebase is aborted, putting the change onto {onto}'s commit {commit} "
                  "failed, and the worktree is as it was:")
"""The outcome a `CONFLICT` refusal of `scripts/merge_change.py` gives
where it could not put the change onto `master`."""

NOT_PUT = re.compile(form(NOT_PUT_ON, {"onto": r"\S+", "commit": r"[0-9a-f]+"}))

NOT_PUT_ON_NOTE = mctx("could not put the change onto `master`: {refusal}")
"""The outcome a `HANDED_OFF` note gives of a merge call that conflicts and
could not put the change onto `master`."""

PATHS_SEP = ", "
"""What stands between two paths of `RERUN_CONFLICT`, of `CONFLICT_NOTE`
and of the `CONFLICT` refusal of `scripts/merge_change.py`."""

DOCUMENT_SUFFIX = ".md"
"""The suffix of a document's path."""


def split_paths(text: str) -> tuple[str, ...]:
    return tuple(p for p in text.split(PATHS_SEP) if p)


def conflict_note_paths(note: str) -> tuple[str, ...] | None:
    """The paths a note that opens with `RERUN_OPENING` or with
    `CONFLICT_OPENING` gives the rebase conflicts in, empty where it gives
    none, or None for any other note."""
    if note.startswith(CONFLICT_OPENING):
        m = re.match(form(CONFLICT_NOTE.format(conflict=Note.CONFLICT, paths="{paths}"),
                          {"paths": r"(?P<paths>.*)"}) + "$", note)
        return () if m is None else split_paths(m["paths"])
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


def merge_words(command: str) -> list[str] | None:
    """The words of the call of `merge_change.py` that the Bash command
    `command` runs, from the script's word on, none where it runs none, or
    None where the shell's quoting in `command` is unbalanced."""
    found = simple_commands(command)
    if not found:
        return None
    for words in found:
        at = next((i for i, w in enumerate(words) if w.endswith(MERGE_SCRIPT)), None)
        if at is not None:
            return words[at:]
    return []


def merge_messages(command: str) -> list[str] | None:
    """The commit message after each `MESSAGE` of the call of `merge_change.py`
    that the Bash command `command` runs, by `merge_words`."""
    words = merge_words(command)
    if words is None:
        return None
    return [words[i + 1] for i, w in enumerate(words[:-1]) if w == MESSAGE]


def names_any(call: Call, paths: set[str]) -> bool:
    """Whether a word of the call of `merge_change.py` that the Bash call
    `call` runs holds any of `paths`."""
    return any(p in w for w in merge_words(str(call.input.get("command", ""))) or ()
               for p in paths)


def log_worktrees(t: Ticket) -> set[str]:
    """The worktrees `t`'s log gives."""
    return {m[1] for line in t.log for m in WORKTREE.finditer(line.note)}


def merge_calls(state: State, t: Ticket) -> list[Call]:
    """The operators' merge calls on any worktree `t`'s log gives: those
    pending, and those with an outcome (`state.Merge`), which a call that
    merges no change, as a call of the script's `--help`, has not."""
    paths = log_worktrees(t)
    return [c for c in state.transcripts.calls if c.tool == Tool.BASH and names_any(c, paths)
            and (c.result is None or c.merge is not None)]


def merge_commit(state: State, t: Ticket) -> Commit | None:
    """The newest commit of `master` that merged the change `t`: its
    subject is `t`'s title, since the merge call gives that title as the
    commit message, and it was made since `t` left `tickets/draft/`."""
    since = left_draft(t)
    return next((c for c in state.git.commits if c.subject == t.title and c.time >= since), None)


def merged(state: State, t: Ticket) -> bool:
    """Whether the change `t` landed on `master`. A pending call that
    names a worktree that is gone counts as landed: `merge_change.py`
    removes a worktree only after it lands the change, and a call that
    runs `operate.py next` after the merge has no result yet. A
    `merge_commit` counts as landed too, since an operator of another
    session may have made it, whose calls this session does not read."""
    gone = {p for p in log_worktrees(t) if Path(p) not in state.git.worktrees}
    if any(c.merge is Merge.MERGED or (c.result is None and names_any(c, gone))
           for c in merge_calls(state, t)):
        return True
    return merge_commit(state, t) is not None


def merge(state: State, t: Ticket, w: Path, latest: list[Agent]) -> Step | None:
    """The line that gives the change's agent-running time since its take,
    where none follows that take and that time reads; then, for each code
    editor whose latest report holds a `split:` item that `reports.SPLIT`
    does not read, the request to send that report again, and the wait for
    its reply, while the change's worktree, which the merge removes, still
    stands; and then the merge. A reply that still holds such an item goes
    on to the merge."""
    take_line = taken(t)
    start = take_line.time if take_line is not None else left_draft(t)
    spent = state.computed.spent.get(t.number)
    if spent is not None and not any(ln.time >= start and ln.note.startswith(TIME_OPENING)
                                     for ln in t.log):
        return Bash(log(t.number, Status.ASSIGNED, Status.ASSIGNED,
                        TIME_NOTE.format(seconds=spent.seconds), state.me), f"{t.number} time",
                    occasion=str(t.last_time))
    for a in latest:
        if a.agent_id is None or not unread_split(a):
            continue
        match ask_again(state, a.agent_id, [r.time for r in a.reports], messages.SPLIT_FORM):
            case Send() as asked:
                return asked
            case False:
                return None
            case True:
                pass
    return merge_steps(state, t, w, latest)


def merge_steps(state: State, t: Ticket, w: Path, latest: list[Agent]) -> Step | None:
    """The merge of the change in `w`, once its editors and its review have
    passed, again after a call that left the worktree with changes made
    after its commit or that a report of an agent on the change follows,
    and the step on a failed merge call."""
    command = merge_command(t, w)
    calls = [c for c in merge_calls(state, t) if names_any(c, {str(w)})]
    last = calls[-1] if calls else None
    quotes = [] if last is None else list(QUOTE_LINE.finditer(last.result or ""))
    message = None if last is None else finding(t, last, calls, latest, quotes)
    on_step = [] if message is None else decided_by(state, unmoved(t, message))
    reported = [r.time for a in [*of_change(state, t), *on_step]
                if (r := a.last_report) is not None]
    at = f"{t.last_time} {max(reported, default=0.0)} {'' if last is None else last.time}"
    if (last is None or (reported and max(reported) > last.time)
            or came_back(t, last.time)):
        return Bash(command, f"{t.number} merge {w}", occasion=at)
    match last.merge:
        case None:
            return None
        case Merge.NOT_RUN:
            first = (last.result or "").strip().splitlines()
            return hand_off(state, t, command, w, NOT_RUN.format(
                first=first[0] if first else "no result text"))
        case Merge.CONFLICT if NOT_PUT.search(last.result or "") is not None:
            refusal = next(ln for ln in (last.result or "").splitlines()
                           if NOT_PUT.search(ln) is not None)
            return hand_off(state, t, command, w, NOT_PUT_ON_NOTE.format(refusal=refusal))
        case Merge.CONFLICT:
            if not any(ln.time > last.time and ln.note.startswith(CONFLICT_OPENING)
                       for ln in t.log):
                return Bash(log(t.number, Status.ASSIGNED, Status.ASSIGNED, CONFLICT_NOTE.format(
                    conflict=Note.CONFLICT, paths=PATHS_SEP.join(last.conflicts)), state.me),
                            f"{t.number} conflict", occasion=str(last.time))
            return message
        case Merge.REFUSED:
            return refused(state, t, w, last, latest, quotes) or message
        case Merge.LEFT_EDITS:
            return Bash(command, f"{t.number} merge {w}", occasion=at)
        case Merge.MERGED:
            return None


def handed_off(line: LogLine) -> bool:
    return line.status is Status.ASSIGNED and line.note.startswith(HANDED_OFF_OPENING)


def hand_off(state: State, t: Ticket, command: str, w: Path, outcome: str) -> Bash:
    """The step that hands the change `t` to the coordinator, after its
    merge call `command` on `w` gave `outcome`. The move back is refused
    where an operator took the change between the two moves."""
    note = HANDED_OFF.format(command=command, outcome=outcome, worktree=w)
    return Bash(log(t.number, Status.OPEN, Status.ASSIGNED, note, None) + " && "
                + log(t.number, Status.ASSIGNED, Status.OPEN, note, state.session),
                f"{t.number} hand off", occasion=str(t.last_time))


def came_back(t: Ticket, since: float) -> bool:
    """Whether the change `t` came back to an operator after `since` from a
    state off the merge path: a line moved it from `tickets/blocked/` back
    to `tickets/assigned/`, or an operator took it from `tickets/open/`
    after a hand-off."""
    handed = False
    for prev, ln in zip(t.log, t.log[1:]):
        handed = handed or (ln.time > since and handed_off(ln))
        if ln.time > since and ln.status is Status.ASSIGNED and (
                prev.status is Status.BLOCKED
                or (handed and prev.status is Status.OPEN and not handed_off(ln))):
            return True
    return False


def handoffs(state: State) -> Step | None:
    """The message that gives the coordinator, once, each change a
    hand-off line gives to the session's coordinator while it holds it."""
    for t in sorted(state.tracker.tickets.values(), key=lambda t: t.order):
        line = next((ln for ln in reversed(t.log) if handed_off(ln)), None)
        if (line is None or t.status is not Status.ASSIGNED or t.holder != state.session
                or line.agent_id != state.session):
            continue
        key = HANDED_OFF_KEY.format(number=t.number, time=f"{line.time:.0f}")
        step = Send(COORDINATOR, labeled(key, mctx("- unfinished: {note}").format(note=line.note)),
                    key)
        if not sent(state, step.to, step.message, key):
            return step
    return None


HANDED_OFF_KEY = mctx("change {number}, handed off at {time}")


def refused(state: State, t: Ticket, w: Path, last: Call, latest: list[Agent],
            quotes: list[re.Match[str]]) -> Step | None:
    """The launch of a code editor that fixes the `quotes` calls the
    refusal `last` reports, whose `QUOTE_LINE` matches are `quotes`, or
    None where it reports none or such an editor launched after it."""
    if quotes:
        if any(a.role is Role.CODE_EDITOR and a.launched > last.time for a in latest):
            return None
        files = sorted({m["path"] for m in quotes})
        return Launch(Role.CODE_EDITOR, t.number, briefs.quotes_fix(
            t.number, w, [m.group(0) for m in quotes], files,
            editor_scratch(t.number, Role.CODE_EDITOR, state.scratch), state.me,
            settled(state, t, Role.CODE_EDITOR, briefs.EditorPart.QUOTES)),
            model=t.model(Role.CODE_EDITOR), occasion=str(last.time))
    return None


def refused_tree(output: str) -> str | None:
    """The tree of the refused commit that `output`, a refused merge
    call's, gives, or None where it gives none."""
    m = TREE.search(output)
    return None if m is None else m["tree"]


def documents_failed(output: str) -> bool:
    """Whether the refusal line of `output` gives a check of the documents
    as failed."""
    line = next((ln for ln in output.splitlines() if ln.startswith(REFUSED)), "")
    m = re.match(form(REFUSED + CHECK_FAILED, {"s": r"(?P<s>[^`]*)"}), line)
    return m is not None and m["s"] in {check_name(argv) for argv in DOCUMENT_CHECKS}


def finding(t: Ticket, last: Call, calls: list[Call], latest: list[Agent],
            quotes: list[re.Match[str]]) -> Send | None:
    """The message that gives the refusal of the merge call `last`, one of
    `calls`, the merge calls on its worktree in order, whose `QUOTE_LINE`
    matches are `quotes`, where `last` was refused for a conflict in its
    rebase or on no `quotes` call."""
    to = finding_recipient(last, latest)
    if (last.merge not in (Merge.REFUSED, Merge.CONFLICT) or quotes
            or to is None or to.agent_id is None):
        return None
    return Send(to.agent_id, messages.merge_finding(t.number, finding_output(last, calls)),
                f"merge finding {t.number} {last.time}")


def finding_recipient(last: Call, latest: list[Agent]) -> Agent | None:
    """The agent of `latest` that the finding on the refused merge call
    `last` goes to."""
    on_documents = (documents_failed(last.result or "")
                    or (last.merge is Merge.CONFLICT
                        and all(p.endswith(DOCUMENT_SUFFIX) for p in last.conflicts)))
    docs = [a for a in latest if a.role is Role.DOC_EDITOR] if on_documents else []
    return docs[0] if docs else latest[0] if latest else None


def finding_output(last: Call, calls: list[Call]) -> str:
    """The merge output that the finding on the refusal `last`, one of
    `calls`, gives."""
    text = last.result or ""
    tree = refused_tree(text)
    if tree is not None:
        text = next(c.result or "" for c in calls if c.merge is Merge.REFUSED
                    and refused_tree(c.result or "") == tree)
    return "\n".join(text.splitlines()[-FINDING_TAIL:])


def close(state: State, t: Ticket, agents: list[Agent]) -> Step | None:
    """The steps after a change's merge, or None while its `after-merge`
    agent runs. A split step carries the change's number, so the journal's
    record of it, which is under the key of the step with that number,
    reads; its occasion is the time the change left
    `tickets/draft/`."""
    head = state.git.commits[0].hash
    if t.after_merge is not None:
        runs = state.agents_of(Role.AFTER_MERGE, t.number)
        if not runs:
            return Launch(Role.AFTER_MERGE, t.number, briefs.after_merge(
                t.number, t.after_merge, head), occasion=head)
        if runs[-1].pending:
            return None
    commit = merge_commit(state, t)
    note = f"{Resolution.FIXED.value} {t.number} {head if commit is None else commit.hash}"
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
        step = Bash(command, f"{r.number} split by {t.number}", change=t.number,
                    occasion=str(left_draft(t)))
        if not done(state, step):
            return step
    for q in sorted(state.tracker.tickets.values(), key=lambda q: q.order):
        if (q.kind is Kind.QUESTION and q.domain is Domain.CHANGE and q.subject == t.number
                and q.status is not Status.CLOSED):
            return Bash(log(q.number, Status.CLOSED, q.status, note, None), f"{q.number} close",
                        occasion=str(q.last_time))
    ids = [a.agent_id for a in agents]
    # An agent with no known id leaves the line with no run, and the
    # change with no known cost (`scripts/spends.py`).
    runs = "" if None in ids else "".join(f" {i}" for i in ids)
    return Bash(log(t.number, Status.CLOSED, Status.ASSIGNED, note + runs, None),
                f"{t.number} close", occasion=str(t.last_time))
