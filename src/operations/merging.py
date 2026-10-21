"""A change's merge and what follows it, as
[Merging a change](prompts/agents/notes/changes.md#merging-a-change) gives.

The merge is `scripts/merge_change.py`, whose checks cover the
`controlled_markdown` check. What a merge call did is read by that
script's own forms and by `master` (`state.Merge`,
`merge_reads.merge_outcome`, `merged`):

- a call that left edits in the worktree after its commit leaves the
  change unmerged, and once no editor of the change runs, the merge call
  on that worktree is given again;
- a call that ran and was stopped before the script wrote its footer, as
  where the step journal ended it (`state.Merge`), reaches no agent of
  the change, and the merge call is given again with the key of the step
  that was stopped, which the step journal counts as a failure of it;
- a call that never ran, as where the harness denied it, hands the change
  to the coordinator (`HANDED_OFF`), with a note that gives the call, the
  first line of its result and the worktree;
- a call that ran and ended with no refusal line, as one that ends on a
  `failed:` line of the script or on a traceback, hands the change to the
  coordinator, with a note that gives the call, the line of its output
  that gives why it ended (`FAILED`) and the worktree;
- a conflict in the rebase leaves the change in its worktree, put by the
  script onto `master` as `scripts/merge_change.py --help` gives it: the
  command writes the paths that conflict on the ticket in a line whose
  note opens with `conflict`, once per such call, and the refusal then
  goes as a finding as any other refusal goes;
- a conflict where the script could not put the change onto `master`
  (`NOT_PUT_ON`) hands the change to the coordinator, with a note that
  gives the call, the script's refusal line and the worktree, since no
  editor may move the branch;
- a refusal because the change's branch holds no change against `master`
  (`NO_CHANGE`) reaches a held-step ruling. A `passes` ruling admits the
  closing sequence; `again` gives the editor the missing work and permits
  a new merge after its report;
- a hand-off moves the change to `tickets/released/` and back to
  `tickets/assigned/` with the session id as its holder, which holds it
  live while the coordinator's session runs, so no operator takes it; the
  command then sends the coordinator the note as an `unfinished:` item,
  once (`handoffs`). Once an operator takes the change from
  `tickets/released/` after the hand-off, or a line moves it from
  `tickets/blocked/` back to `tickets/assigned/` after the call, the merge
  call is given again;
- a refusal whose output reports a `quotes` call a change to the documents
  broke goes to a new code editor in the change's worktree, with those
  calls as its items and their files as the files it may edit;
- any other refusal goes as a finding of its checks to the change's doc
  editor, where the change has one and the check its refusal line gives
  as failed is a check of the documents (`DOCUMENT_CHECKS`), or each path
  its rebase conflicts in, or each path it reports a leftover conflict
  marker in (`marker_paths`), is a document (`documents_only`), and
  otherwise to the change's first editor;
- a refusal or a conflict that no agent of the change's editors can take
  as a finding, as where the change passed from an operator of another
  session and no editor of it has an agent in the worktree, goes in the
  brief of the editor that `changes.staff_editor` launches for the first
  role with none;
- two refusals that give one tree (`REFUSED_TREE`) give one finding
  message, with the output of the first refused merge call on that
  worktree that gives that tree. Whether two refusals give one message
  rests on the tree alone: the change rebased on another commit of
  `master` gives another tree, unless the checks ran on the same content,
  and the output that message gives holds the `master` commit of the
  first call.

Other than after a `NO_CHANGE` refusal, once an agent launched on the
change since its last move out of `tickets/draft/`
(`change_agents.of_change`), or a ticket analyst launched on the step
`handled.unmoved` gives for that finding, reports after the latest merge
call, the merge call is given again.

Once the change is merged or its empty-merge ruling passes, an agent runs the steps and checks of each item
of its ticket's Scope that opens `After the merge`, then the command closes each `refactor` ticket
on a module a code editor of the change reports it split, or logs the part
the report gives as left unsplit, then each open `question` ticket filed on
the change (`change_holds.open_questions`), then the change's own ticket."""

import re
import shlex
from collections.abc import Callable, Iterable, Sequence
from dataclasses import replace
from functools import cache
from pathlib import Path

from controlled_markdown import form, mctx
from controlled_markdown.nodes import Rule, finding_lines
from engine.duration import FOOTER_RE
from operations import briefs, messages
from operations.directives import (Decision, Directive, Ruling, held_on, numbers_in, ruling,
                                   session_lines)
from operations.change_agents import of_change, settled
from operations.change_holds import open_questions
from operations.change_budget import TIME_NOTE, TIME_OPENING, left_draft, taken
from operations.filing import editor_scratch
from operations.completion import occupies
from operations.reports import splits, unread_split
from operations.roles import Role
from operations.constants import COORDINATOR
from operations.state import (Agent, Call, Commit, LogLine, Merge, State, Ticket, Tool,
                              memoized_by_transcripts)
from operations.command_words import command_words
from operations.handled import ask_again, decided_by, held_aside, sent, unmoved
from operations.steps import Bash, Launch, Send, Step, Undecided, labeled
from operations.log_commands import log
from operations.tracker import last_index
from operations.worktrees import WORKTREE
from ticketing.vocabulary import MANY_IDEAS, Kind, Note, Resolution, Status

MERGE_SCRIPT = "scripts/merge_change.py"

TOOL = "merge_change"
"""The name `merge_change.py` gives itself in its lines and its footer
(`engine.duration.footer`)."""

PREFIX = TOOL + ": "
"""The opening of each line `merge_change.py` prints, on stdout and on
stderr."""

REFUSED = PREFIX + "refused: "
"""The opening of the line of a refusal."""

FAILED_LINE = PREFIX + "failed: "
"""The opening of the line of a run the script ended on a failure of its
own."""

REFUSED_TREE = mctx("; the refused commit's tree is {tree}")
"""The end of a refusal of a change after its rebase: the tree of the
commit it refused."""

TREE = re.compile(form(REFUSED_TREE, {"tree": r"(?P<tree>[0-9a-f]+)"}) + "$", re.M)

CONTEXT_WRITE = ("scripts/context.py", "--write")
"""The command, after `uv run python`, that writes the generated files."""


def check_name(argv: Sequence[str], files: Sequence[str] = ()) -> str:
    """The name the lines of `merge_change.py` and `change_checks.py` give
    the check whose command is `argv` with `files` after it."""
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

FAILED = mctx("failed: {why}")
"""The outcome that a `HANDED_OFF` note gives for a merge call that ran
and ended with no refusal line. `why` is the line of its output that
gives why it ended (`failed_why`)."""

NO_TEXT = "no result text"
"""What a `HANDED_OFF` note gives in place of a line of a call's output
where the output has none."""

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

NO_CHANGE = mctx("{branch} holds no change against {base}")
"""The refusal of `scripts/merge_change.py` of a change whose branch
holds no change against `master` outside the paths
`change_checks.changed_outside_work` leaves out."""

NO_CHANGE_LINE = re.compile("^" + re.escape(REFUSED)
                            + form(NO_CHANGE, {"branch": r"\S+", "base": r"\S+"}) + "$", re.M)

NOT_PUT_ON_NOTE = mctx("could not put the change onto `master`: {refusal}")
"""The outcome a `HANDED_OFF` note gives of a merge call that conflicts and
could not put the change onto `master`."""

PATHS_SEP = ", "
"""What stands between two paths of `RERUN_CONFLICT`, of `CONFLICT_NOTE`
and of the `CONFLICT` refusal of `scripts/merge_change.py`."""

MARKERS = mctx("`git diff --check` reports a leftover conflict marker in the change of {branch}, "
               "so the index is put back as it was and nothing is committed:")
"""The refusal of a change whose staged change holds a leftover conflict
marker, followed by one line of `git diff --check` for each marker."""

MARKER_LINE = "leftover conflict marker"
"""The end of a line of `git diff --check` that reports a conflict
marker."""

MARKED = re.compile(form(REFUSED + MARKERS, {"branch": r"\S+"}), re.M)

DOCUMENT_SUFFIX = ".md"
"""The suffix of a document's path."""


def documents_only(paths: Iterable[str]) -> bool:
    return all(p.endswith(DOCUMENT_SUFFIX) for p in paths)


def marker_paths(output: str) -> tuple[str, ...] | None:
    """The paths whose lines of `git diff --check` report a leftover
    conflict marker, where `output`, what a merge call printed, holds the
    refusal `MARKERS`, or None where it holds not."""
    m = MARKED.search(output)
    if m is None:
        return None
    lines = output[m.end():].splitlines()
    return tuple(dict.fromkeys(ln.rsplit(":", 2)[0] for ln in lines if ln.endswith(MARKER_LINE)))


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


@cache
def merge_words(command: str) -> tuple[str, ...] | None:
    """The words of the call of `merge_change.py` that the Bash command
    `command` runs, from the script's word on, none where it runs none, or
    None where the shell's quoting in `command` is unbalanced, found once
    for each command: the state gives each operator's commands at each
    read."""
    found = command_words(command)
    if not found:
        return None
    for words in found:
        at = next((i for i, w in enumerate(words) if w.endswith(MERGE_SCRIPT)), None)
        if at is not None:
            return words[at:]
    return ()


def merge_messages(command: str) -> list[str] | None:
    """The commit message after each `MESSAGE` of the call of `merge_change.py`
    that the Bash command `command` runs, by `merge_words`."""
    words = merge_words(command)
    if words is None:
        return None
    return [words[i + 1] for i, w in enumerate(words[:-1]) if w == MESSAGE]


def names_any(call: Call, paths: set[str]) -> bool:
    """Whether a word of the call of `merge_change.py` that the Bash call
    `call` runs is any of `paths`, with a trailing `/` of the word
    stripped: a call on `change-11-512` names no worktree `change-11-51`."""
    return any(w.rstrip("/") in paths for w in merge_words(call.command) or ())


def log_worktrees(t: Ticket) -> set[str]:
    """The worktrees `t`'s log gives."""
    return {m[1] for line in t.log for m in WORKTREE.finditer(line.note)}


def merge_calls(state: State, t: Ticket) -> list[Call]:
    """The operators' merge calls on any worktree `t`'s log gives: those
    pending, and those with an outcome (`state.Merge`), which a call that
    merges no change, as a call of the script's `--help`, has not."""
    paths = log_worktrees(t)
    return [c for c in merge_script_calls(state) if names_any(c, paths)
            and (c.result is None or c.merge is not None)]


@memoized_by_transcripts
def merge_script_calls(state: State) -> tuple[Call, ...]:
    """The operators' Bash calls that run `merge_change.py` (`merge_words`),
    in the order of `TranscriptsRead.calls`."""
    return tuple(c for c in state.transcripts.calls
                 if c.tool == Tool.BASH and merge_words(c.command))


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
    session may have made it, whose calls this session does not read.
    An `Op merged:` line to any operator of the session also counts,
    including a coordinator merge with a different commit subject."""
    if any(n == t.number for n, _ in numbers_in(session_lines(state), Directive.MERGED)):
        return True
    gone = {p for p in log_worktrees(t) if Path(p) not in state.git.worktrees}
    if any(c.merge is Merge.MERGED or (c.result is None and names_any(c, gone))
           for c in merge_calls(state, t)):
        return True
    return merge_commit(state, t) is not None


type Staff = Callable[[str | None], Step | None]
"""The launch of an editor for a role of the change with none
(`changes.staff_editor`), with the finding of a refused merge in its
brief, where one is given."""


def merge(state: State, t: Ticket, w: Path, latest: list[Agent], staff: Staff) -> Step | None:
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
    return merge_steps(state, t, w, latest, staff)


def merge_steps(state: State, t: Ticket, w: Path, latest: list[Agent],
                staff: Staff) -> Step | None:
    """The merge of the change in `w`, once its editors and its review have
    passed, again after a call that left the worktree with changes made
    after its commit or that a report of an agent on the change follows,
    and the step on a failed merge call. A `NO_CHANGE` refusal needs a
    ruling on readiness for the closing sequence. A refusal or a
    conflict that no agent of `latest` can take as a finding goes in the
    brief of the editor that `staff` launches."""
    command = merge_command(t, w)
    calls = [c for c in merge_calls(state, t) if names_any(c, {str(w)})]
    last = calls[-1] if calls else None
    quotes = [] if last is None else list(QUOTE_LINE.finditer(last.result or ""))
    message = None if last is None else finding(t, last, calls, latest, quotes)
    on_step = [] if message is None else decided_by(state, unmoved(t, message))
    reported = [r.time for a in [*of_change(state, t), *on_step]
                if (r := a.last_report) is not None]
    at = f"{t.last_time} {max(reported, default=0.0)} {'' if last is None else last.time}"
    empty = None if last is None else NO_CHANGE_LINE.search(last.result or "")
    if last is not None and empty is not None and not came_back(t, last.time):
        decision = empty_ruling(state, t, w, last)
        if isinstance(decision, Undecided):
            return decision
        if decision.choice is Decision.PASSES:
            return close(state, t, of_change(state, t), NO_MERGE_EVIDENCE)
        editor_reports = [r.time for a in latest if (r := a.last_report) is not None]
        if not editor_reports or max(editor_reports) <= decision.time:
            missing = messages.merge_finding(t.number, last.result or "")
            reports = [r for a in decided_by(state, held_on(empty_hold(t, w, last), EMPTY_CHOICES))
                       if (r := a.last_report) is not None]
            if reports:
                missing += "\n" + reports[-1].text
            to = finding_recipient(last, latest)
            if to is not None and to.agent_id is not None:
                return Send(to.agent_id, missing,
                            f"empty merge rework {t.number} {decision.time}")
            return staff(missing)
    if (last is None or (reported and max(reported) > last.time)
            or came_back(t, last.time)):
        return Bash(command, f"{t.number} merge {w}", occasion=at)
    match last.merge:
        case None:
            return None
        case Merge.NOT_RUN:
            first = (last.result or "").strip().splitlines()
            return hand_off(state, t, command, w, NOT_RUN.format(
                first=first[0] if first else NO_TEXT))
        case Merge.FAILED:
            return hand_off(state, t, command, w, FAILED.format(why=failed_why(last.result or "")))
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
            return message or unreceived(t, last, calls, latest, quotes, staff)
        case Merge.REFUSED:
            return (refused(state, t, w, last, latest, quotes) or message
                    or unreceived(t, last, calls, latest, quotes, staff))
        case Merge.LEFT_EDITS:
            return Bash(command, f"{t.number} merge {w}", occasion=at)
        case Merge.MERGED:
            return None


EMPTY_CHOICES = {
    Decision.PASSES: mctx("the work required before the merge is complete; run the closing sequence"),
    Decision.AGAIN: mctx("give the editor the missing work and merge again after its report"),
}
EMPTY_MERGE = mctx("change {number}: merge refused for an empty diff in `{worktree}`; ticket revision {revision}; "
                   "refused call at {time}: `{command}`. Refusal: {refusal}.")
NO_MERGE_EVIDENCE = "no-merge"


def empty_hold(t: Ticket, w: Path, call: Call) -> str:
    at = last_index(t, (Note.FILED, Note.REVISED))
    revision = t.log[at].time if at >= 0 else left_draft(t)
    return EMPTY_MERGE.format(number=t.number, worktree=w, revision=revision,
                              time=call.time, command=call.command,
                              refusal=refusal_line(call.result or ""))


def empty_ruling(state: State, t: Ticket, w: Path, call: Call) -> Ruling | Undecided:
    decision = ruling(state, empty_hold(t, w, call), EMPTY_CHOICES)
    return replace(decision, change=t.number) if isinstance(decision, Undecided) else decision


def empty_completion(state: State, t: Ticket) -> Ruling | None:
    """The passing ruling on the latest empty refusal in the current worktree,
    or None. A new refusal or ticket revision needs a new ruling."""
    calls = merge_calls(state, t)
    if not calls:
        return None
    call = calls[-1]
    if NO_CHANGE_LINE.search(call.result or "") is None or came_back(t, call.time):
        return None
    paths = [w for w in state.git.worktrees if names_any(call, {str(w)})]
    if len(paths) != 1:
        return None
    decision = empty_ruling(state, t, paths[0], call)
    return decision if isinstance(decision, Ruling) and decision.choice is Decision.PASSES else None


def ready_to_close(state: State, t: Ticket) -> bool:
    return merged(state, t) or empty_completion(state, t) is not None


def handed_off(line: LogLine) -> bool:
    return line.status is Status.ASSIGNED and line.note.startswith(HANDED_OFF_OPENING)


def hand_off(state: State, t: Ticket, command: str, w: Path, outcome: str) -> Bash:
    """The step that hands the change `t` to the coordinator, after its
    merge call `command` on `w` gave `outcome`. The move back is refused
    where an operator took the change between the two moves."""
    note = HANDED_OFF.format(command=command, outcome=outcome, worktree=w)
    return Bash(log(t.number, Status.RELEASED, Status.ASSIGNED, note, None) + " && "
                + log(t.number, Status.ASSIGNED, Status.RELEASED, note, state.session),
                f"{t.number} hand off", occasion=str(t.last_time))


def came_back(t: Ticket, since: float) -> bool:
    """Whether the change `t` came back to an operator after `since` from a
    state off the merge path: a line moved it from `tickets/blocked/` back
    to `tickets/assigned/`, or an operator took it from `tickets/released/`
    after a hand-off."""
    handed = False
    for prev, ln in zip(t.log, t.log[1:]):
        handed = handed or (ln.time > since and handed_off(ln))
        if ln.time > since and ln.status is Status.ASSIGNED and (
                prev.status is Status.BLOCKED
                or (handed and prev.status is Status.RELEASED and not handed_off(ln))):
            return True
    return False


def handoffs(state: State) -> Step | None:
    """The message that gives the coordinator, once, each change a
    hand-off line gives to the session's coordinator while it holds it."""
    for t in sorted(state.tracker.tickets.values(), key=lambda t: t.order):
        if t.status is not Status.ASSIGNED or t.holder != state.session:
            continue
        line = next((ln for ln in reversed(t.log) if handed_off(ln)), None)
        if line is None or line.agent_id != state.session:
            continue
        key = HANDED_OFF_KEY.format(number=t.number, time=f"{line.time:.0f}")
        step = Send(COORDINATOR, labeled(key, mctx("- unfinished: {note}").format(note=line.note)),
                    key)
        if not sent(state, step.to, step.message, key) and not held_aside(state, step):
            return step
    return None


HANDED_OFF_KEY = mctx("change {number}, handed off at {time}")


def refused(state: State, t: Ticket, w: Path, last: Call, latest: list[Agent],
            quotes: list[re.Match[str]]) -> Step | None:
    """The launch of a code editor that fixes the `quotes` calls the
    refusal `last` reports, whose `QUOTE_LINE` matches are `quotes`, or
    None where it reports none or such an editor launched after it."""
    if quotes:
        if any(a.role is Role.CODE_EDITOR and a.launched > last.time and occupies(a) for a in latest):
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


def refusal_line(output: str) -> str | None:
    """The first line of `output`, what a merge call printed, that opens
    with `REFUSED`, or None where no line does."""
    return next((ln for ln in output.splitlines() if ln.startswith(REFUSED)), None)


def failed_why(output: str) -> str:
    """The line that gives why a merge call ended, where its output
    `output` holds no refusal line: the first line of `output` that opens
    with `FAILED_LINE`, else its last line once the footer is taken out,
    else `NO_TEXT`."""
    lines = output.splitlines()
    rest = FOOTER_RE.sub("", output).strip().splitlines()
    return next((ln for ln in lines if ln.startswith(FAILED_LINE)),
                rest[-1] if rest else NO_TEXT)


def documents_failed(output: str) -> bool:
    """Whether the refusal line of `output` gives a check of the documents
    as failed."""
    line = refusal_line(output) or ""
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


def unreceived(t: Ticket, last: Call, calls: list[Call], latest: list[Agent],
               quotes: list[re.Match[str]], staff: Staff) -> Step | None:
    """The launch of an editor with the finding on the refusal `last` in
    its brief, where `last` is no `quotes` refusal and no agent of `latest`
    takes the finding (`finding_recipient`), or None."""
    if quotes or finding_recipient(last, latest) is not None:
        return None
    return staff(messages.merge_finding(t.number, finding_output(last, calls)))


def finding_recipient(last: Call, latest: list[Agent]) -> Agent | None:
    """The agent of `latest` that the finding on the refused merge call
    `last` goes to."""
    marked = marker_paths(last.result or "")
    on_documents = (documents_failed(last.result or "")
                    or (last.merge is Merge.CONFLICT and documents_only(last.conflicts))
                    or (bool(marked) and documents_only(marked or ())))
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


def unsplit(t: Ticket) -> str:
    """The opening of the note the split step of the change `t` logs on a
    `refactor` ticket that the change left unsplit."""
    return f"left unsplit by change {t.number}"


def close(state: State, t: Ticket, agents: list[Agent], evidence: str | None = None) -> Step | None:
    """The closing sequence admitted by a merge or readiness ruling, or None while its `after-merge`
    agent runs. A split step is given while its `refactor` ticket holds no
    line that the step logs as left unsplit (`unsplit`)."""
    head = state.git.commits[0].hash
    if t.after_merge is not None:
        runs = state.agents_of(Role.AFTER_MERGE, t.number)
        runs = [a for a in runs if occupies(a)]
        if not runs:
            return Launch(Role.AFTER_MERGE, t.number, briefs.after_merge(
                t.number, t.after_merge, head, evidence), occasion=head)
        if runs[-1].pending:
            return None
    commit = merge_commit(state, t)
    proof = evidence if evidence is not None else head if commit is None else commit.hash
    note = f"{Resolution.FIXED.value} {t.number} {proof}"
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
                   log(r.number, r.status, r.status, f"{unsplit(t)}: {part}", None))
        if not any(ln.note.startswith(unsplit(t)) for ln in r.log):
            return Bash(command, f"{r.number} split by {t.number}", occasion=str(left_draft(t)))
    if questions := open_questions(state, t.number):
        q = questions[0]
        return Bash(log(q.number, Status.CLOSED, q.status, note, None), f"{q.number} close",
                    occasion=str(q.last_time))
    ids = [a.agent_id for a in agents]
    # An agent with no known id leaves the line with no run, and the
    # change with no known cost (`scripts/spends.py`).
    runs = "" if None in ids else "".join(f" {i}" for i in ids)
    return Bash(log(t.number, Status.CLOSED, t.status, note + runs, None),
                f"{t.number} close", occasion=str(t.last_time))
