"""The briefs of the agents the operator launches, each in the form
[Briefs](prompts/agents/notes/launching.md#briefs) gives for its work. A
brief gives the agent id of the operator that launches the agent, which
the agent replies to."""

import re
import shlex
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from controlled_markdown import form, mctx
from operations.reports import LEFT_FOR_DECISION, WORKTREE
from operations.roles import Role, description
from operations.state import SETTLED, Agent, Place, code_review_tag
from operations.log_commands import AGENT, FILE_TICKET
from ticketing.times import utc_stamp

if TYPE_CHECKING:
    from operations.change_agents import Reported, Settled

TICKET_PATH = shlex.join([*FILE_TICKET, "path"]) + " {number}"
WORK_IN = mctx("Work in the worktree {worktree}.")
TESTS = mctx("Tests directory: `tests/`.")
SCRATCH = mctx("Scratch directory: {scratch}.")
SCRATCH_LINE = re.compile(form(SCRATCH, {"scratch": r"(?P<scratch>\S.*)"}))
LAUNCHER = mctx("The agent that launches you: {operator}.")
LEFT_REPLY = mctx("The item checker's reply on {number}, from after its last `{heading}` line "
                  "where it has one; judge what it leaves for a decision:")
MAY_EDIT = mctx("The files you may edit: {files}.")
FILE_AS = mctx("with {domain_subject} as `<domain>` and `<subject>`, and {agent} as `<agent>`")
"""The clause of a brief that gives its agent the domain, the subject and
the agent to file its tickets with."""
CODE_WORD = mctx("`{word}`")
OPERATOR = CODE_WORD.format(word=AGENT)
AT_MASTER = FILE_AS.format(domain_subject=mctx("`commit` and the hash `master` stands at"),
                           agent=OPERATOR)
REPORT_FILE = mctx("Report file: `{path}`.")
"""The line of each brief the operator gives that gives the file the agent
writes its final reply to, for an agent whose documents say what it does
with that file."""
REPORT_RULE = mctx("Write your final reply to the file `{path}`, in place of what it holds, "
                   "and give that file's path alone, on one line, as your final reply itself.")
"""That line for an agent no document gives (`roles.GENERAL_ROLES`)."""


def read_ticket(number: str) -> str:
    return mctx("Change {number}: read the ticket with `{command}`.").format(
        number=number, command=TICKET_PATH.format(number=number))

PARTS: dict[Role, str] = {
    Role.CODE_EDITOR: mctx("each file outside the documents, the lib, its modules, the solvers under "
                           "`programs/` and the accepted gate outputs that their items change, "
                           "with a draft of the text of each `mctx` fragment it needs"),
    Role.HANDBOOK_EXPANDED: mctx("the lib, its modules and the solvers under `programs/`, with "
                                 "the accepted gate outputs its items change"),
    Role.DOC_EDITOR: mctx("the documents and the text of the `mctx` fragments"),
}
"""The part of a change each editor takes, where the change has more than
one, as [Carrying a change](prompts/agents/notes/changes.md#carrying-a-change)
splits it."""


FRAGMENTS_PART = mctx("Your part: the text of the `mctx` fragments below, with the moves "
                      "that text needs.")
"""The part of the doc editor `change_fragments` launches on a change's fragments,
which keys that editor apart from the change's doc editor of the
documents."""

YOUR_PART = mctx("Your part: {part}.")
OF_FRAGMENTS = mctx("the text of the `mctx` fragments that editor's brief gives, with the moves "
                    "that text needs")
QUOTES_ITEMS = mctx("Your items: repair each `quotes` call the `controlled_markdown` check "
                    "reports below.")
QUOTES_PART = mctx("the repair of each `quotes` call that editor's brief gives")
WHOLE_CHANGE = mctx("the whole change")


def _whole(role: Role) -> tuple[Role, str | None, str]:
    return role, None, WHOLE_CHANGE


def _own(role: Role) -> tuple[Role, str | None, str]:
    return role, YOUR_PART.format(part=PARTS[role]), PARTS[role]


class Part(Enum):
    """The role of an editor of a change with the part of it that editor
    takes: the line that gives its brief that part (`line`), or None where
    it takes the whole change, and the part as `part_of` reads it
    (`part`)."""
    role: Role
    line: str | None
    part: str

    def __init__(self, role: Role, line: str | None, part: str) -> None:
        self.role, self.line, self.part = role, line, part


class EditorPart(Part):
    """The parts of an editor whose brief gives no fragments."""
    CODE_EDITOR = _whole(Role.CODE_EDITOR)
    CODE_EDITOR_PART = _own(Role.CODE_EDITOR)
    HANDBOOK_EXPANDED = _whole(Role.HANDBOOK_EXPANDED)
    HANDBOOK_EXPANDED_PART = _own(Role.HANDBOOK_EXPANDED)


class DocEditorPart(Part):
    """The parts of a doc editor, the fragments part included."""
    DOC_EDITOR = _whole(Role.DOC_EDITOR)
    DOC_EDITOR_PART = _own(Role.DOC_EDITOR)
    FRAGMENTS = Role.DOC_EDITOR, FRAGMENTS_PART, OF_FRAGMENTS


def part_taken(role: Role, split: bool) -> EditorPart | DocEditorPart:
    """The part an editor of `role` takes of a change split between
    editors where `split`, and otherwise the whole change."""
    taken = _own(role) if split else _whole(role)
    return next(p for p in (*EditorPart, *DocEditorPart) if p.value == taken)


@dataclass(frozen=True)
class DocEditor:
    """A doc editor by its part, with the fragments its brief gives and the
    agent ids of the change's code editors."""
    part: DocEditorPart
    fragments: tuple[Place, ...]
    code_editors: tuple[str, ...]


@dataclass(frozen=True)
class Before:
    """The agent id and the scratch directory of the last editor of a role
    in a change's worktree that an operator of another session launched."""
    agent: str
    scratch: Path


BRIEF_PARTS: tuple[tuple[str, str], ...] = (
    (QUOTES_ITEMS, QUOTES_PART),
    *((p.line, p.part) for p in (*DocEditorPart, *EditorPart) if p.line is not None))
"""Each line that gives an editor's brief its part, beside the part as
another brief gives it."""


def part_of(agent: Agent) -> str:
    """The part of a change its editor `agent` takes, as its own brief
    gave it."""
    return next((part for line, part in BRIEF_PARTS if line in agent.brief), WHOLE_CHANGE)


def editor(editor: EditorPart | DocEditor, number: str, worktree: Path, scratch: Path,
           operator: str, settled: "Settled", before: Before | None = None) -> str:
    """The brief of the editor `editor` of the change `number`, in the
    change's worktree `worktree`, with what the agents before it settled
    (`settled_lines`). A doc editor's brief gives its fragments, and the
    agent ids of the change's code editors. `before` gives the last editor
    of the role in that worktree that an operator of another session
    launched, where there is one, whose latest report that block gives."""
    part = editor.part if isinstance(editor, DocEditor) else editor
    lines = [read_ticket(number)]
    if part.line is not None:
        lines.append(part.line)
    lines.append(WORK_IN.format(worktree=worktree))
    if isinstance(editor, DocEditor) and editor.fragments:
        lines.append(FRAGMENTS)
        lines += [FRAGMENT.format(file=f.file, line=f.line) for f in editor.fragments]
        if editor.code_editors:
            lines.append(CODE_EDITORS.format(ids=", ".join(editor.code_editors)))
    lines.append(mctx("Accepted gate outputs under `tests/gate/accepted/` you may write: each "
                      "that a `DIFF` of the gate your items cause names."))
    if part.role is Role.CODE_EDITOR:
        lines.append(TESTS)
    lines.append(SCRATCH.format(scratch=scratch))
    lines.append(LAUNCHER.format(operator=operator))
    if before is not None:
        lines.append(BEFORE.format(agent=before.agent, scratch=before.scratch))
    return "\n".join(lines + settled_lines(settled))


BEFORE = mctx("An editor of your role that another session launched, {agent}, worked in this "
              "worktree before you, with the scratch directory {scratch}.")


def scratch_of(brief: str) -> Path | None:
    """The scratch directory the first `SCRATCH` line of `brief` gives, or
    None where it gives none."""
    found = [m.group("scratch") for line in brief.split("\n")
             if (m := SCRATCH_LINE.fullmatch(line))]
    return Path(found[0]) if found else None


FRAGMENTS = mctx("Judge whether the text of each `mctx` fragment below, which a code editor "
                 "drafted for you to write, belongs in its program, by [What goes "
                 "where](docs/handbook/editing.md#what-goes-where), move what does not to "
                 "where it belongs, then write the text that stays.")

FRAGMENT = mctx("- `{file}`, line {line}")


def gives_fragments(agent: Agent) -> bool:
    """Whether `agent` is a doc editor whose brief gave it fragments of its
    change: `FRAGMENTS_PART`, or the `FRAGMENTS` line that leads the
    `FRAGMENT` lines."""
    return agent.role is Role.DOC_EDITOR and (FRAGMENTS_PART in agent.brief
                                              or FRAGMENTS in agent.brief)


CODE_EDITORS = mctx("Where a move needs the code to change, send that code change by "
                    "SendMessage to the code editor of the change: {ids}.")


FINGERPRINT = mctx("Before you write each final reply, run `uv run python "
                   "scripts/change_worktree.py --fingerprint {worktree}`, and end that reply with "
                   "the line `{opening} <what it printed>`.")


def fingerprint_line(worktree: Path) -> str:
    return FINGERPRINT.format(worktree=worktree, opening=WORKTREE)


def editor_lines(editors: list[tuple[Agent, str]]) -> list[str]:
    """The line of each editor of a change, with its agent id beside its
    record, that gives its part."""
    return [mctx("Its {role}: {aid}, whose part is {part}.").format(
        role=agent.role, aid=aid, part=part_of(agent)) for agent, aid in editors]


def doc_review(number: str, worktree: Path, editors: list[tuple[Agent, str]],
               operator: str, settled: "Settled") -> str:
    lines = [mctx("Review the change to the documents of change {number}: the diff that "
                  "`git -C {worktree} diff --merge-base master` prints, and each file that "
                  "`git -C {worktree} ls-files --others --exclude-standard` prints.").format(
                      number=number, worktree=worktree)]
    lines.extend(editor_lines(editors))
    lines.append(fingerprint_line(worktree))
    lines.append(LAUNCHER.format(operator=operator))
    return "\n".join(lines + settled_lines(settled))


def quotes_fix(number: str, worktree: Path, calls: list[str], files: list[str], scratch: Path,
               operator: str, settled: "Settled") -> str:
    """The brief of a code editor on the `quotes` calls a change to the
    documents broke, as [Carrying a change](prompts/agents/notes/changes.md#carrying-a-change)
    gives it."""
    return "\n".join([
        read_ticket(number), WORK_IN.format(worktree=worktree),
        QUOTES_ITEMS,
        *calls,
        MAY_EDIT.format(files=", ".join(files)), TESTS, SCRATCH.format(scratch=scratch),
        LAUNCHER.format(operator=operator), *settled_lines(settled)])


# The lines on a check whose event has not happened and on a check of what
# a session reads at its start: ticket 2-354 records checks closed at the
# merge with no one holding them (2-334, 4-29), and a running session's
# launches checking hooks it had not reloaded.
AFTER_MERGE = mctx("""
    - Change {number} is merged into `master` at {head}.
    - Run each step and each check its ticket places after the merge, which `{command}` prints, in the order it gives them: {items}.
    - File each step and each check that fails as a `bug` ticket, by the lines of [Ticket files](prompts/agents/notes/tickets.md#ticket-files), {filing}.
    - Give each check whose subject is an event that has not happened yet in your reply as unfinished, with that reason.
    - Run a check of what a running Claude Code session reads only at its start in a `claude -p` session you start in the main worktree.
    - Reply with each step and each check as done or passed, failed with its ticket, or unfinished with its reason.
    """)


def after_merge(number: str, items: str, head: str) -> str:
    filing = FILE_AS.format(domain_subject=mctx("`change` and {number}").format(number=number),
                            agent=OPERATOR)
    return AFTER_MERGE.format(number=number, head=head, items=items, filing=filing,
                              command=TICKET_PATH.format(number=number))


REVIEW_DRAFTS = mctx("Review the drafts {numbers}.")
SETTLE = mctx("Settle the tickets under `tickets/open/` {numbers}.")
REVISE = mctx("Revise each draft `change` ticket {numbers}, whose log holds findings or "
              "suggestions.")
PASS_SETTLE = mctx("Settle the tickets under `tickets/open/` {numbers}, which the solver pass on "
                   "task {task} and the review of its transcript, agent {review}, filed, and "
                   "read that review's report by `python3 ~/.claude/skills/retrieve/"
                   "transcripts.py --help`.")
ITEM_LINES = (REVIEW_DRAFTS, SETTLE, REVISE, PASS_SETTLE)
"""The first lines of the briefs that give several items of the same
work, each item a ticket number in the slot `numbers`."""


ITEM_SEPARATOR = ", "


def item_list(numbers: list[str]) -> str:
    return ITEM_SEPARATOR.join(numbers)


def ticket_review(numbers: list[str], operator: str) -> str:
    return "\n".join([REVIEW_DRAFTS.format(numbers=item_list(numbers)),
                      LAUNCHER.format(operator=operator)])


def settle(numbers: list[str], operator: str) -> str:
    return "\n".join([SETTLE.format(numbers=item_list(numbers)),
                      LAUNCHER.format(operator=operator)])


def revise(numbers: list[str], last: list[str], operator: str,
           overruns: list[tuple[str, str, str | None]]) -> str:
    """The brief of a ticket analyst that revises the drafts `numbers`,
    with, for each draft `overruns` gives by its number, the line of the
    operator's that moved it past its cost budget to `tickets/draft/`, and
    the item checker's reply that line names, from after its last
    `LEFT_FOR_DECISION` line, or the whole reply where it has none."""
    lines = revise_lines(numbers, last)
    for number, line, left in overruns:
        lines.append(mctx("The findings of draft {number} include the operator's line below, "
                          "which moved it past its cost budget to `tickets/draft/`:").format(
                              number=number))
        lines.append(f"\n{line}\n")
        if left is not None:
            lines.append(LEFT_REPLY.format(number=number, heading=LEFT_FOR_DECISION))
            lines.append(f"\n{left}\n")
    return "\n".join([*lines, LAUNCHER.format(operator=operator)])


def weigh_suggestions(number: str, reviewers: list[str], last: bool) -> str:
    """The message to the ticket analyst that last revised or filed the
    draft `number`, whose log gives only the suggestions of `reviewers`
    since."""
    return "\n".join([*revise_lines([number], [number] if last else []), mctx(
        "Its suggestions are those of {role} {reviewers}.").format(
            role="ticket reviewer" if len(reviewers) == 1 else "ticket reviewers",
            reviewers=", ".join(reviewers))])


def revise_lines(numbers: list[str], last: list[str]) -> list[str]:
    lines = [REVISE.format(numbers=item_list(numbers))]
    if last:
        lines.append(mctx(
            "The revision of {last} is the last: once it is written, the operator moves the draft to "
            "`tickets/open/` with no further ticket review, and the change's own review checks "
            "what the change writes.").format(
                last=", ".join(last)))
    return lines


def change_lines(number: str, worktree: Path) -> list[str]:
    """The opening lines of a brief on the built change `number`."""
    return [read_ticket(number), mctx("Its worktree: {worktree}.").format(worktree=worktree)]


def editor_reports(reports: list[tuple[str, str]]) -> list[str]:
    lines: list[str] = []
    for editor_id, report in reports:
        lines.append(mctx("The latest report of editor {editor}:").format(editor=editor_id))
        lines.append(f"\n{report}\n")
    return lines


def item_check(number: str, worktree: Path, reports: list[tuple[str, str]], gate: list[str],
               editors: list[tuple[Agent, str]], operator: str, settled: "Settled",
               past: bool = False) -> str:
    """The brief of an item checker that checks the items of the editors
    of a change it checks, by each editor's agent id and latest report,
    and the accepted gate outputs `gate` it reads, with the agent id and
    part of each of those editors, each beside its record in `editors`,
    and what the agents before it settled (`settled_lines`). `past` gives
    that the change is past its cost budget."""
    lines = [*change_lines(number, worktree), *editor_lines(editors)]
    if past:
        lines.append(OVER_BUDGET.format(number=number))
    lines.extend(editor_reports(reports))
    if gate:
        lines.append(mctx(
            "Read the diff of each accepted gate output the change writes, {gate}, and send "
            "each difference there that the change's items do not ask for to its editors, "
            "{editors}, as a finding of its checks.").format(
                gate=", ".join(gate), editors=", ".join(i for _, i in editors)))
    lines.append(fingerprint_line(worktree))
    lines.append(LAUNCHER.format(operator=operator))
    return "\n".join(lines + settled_lines(settled))


def findings(number: str, worktree: Path, left: str | None, questions: list[str],
             editors: list[tuple[Agent, str]], reports: list[tuple[str, str]],
             unfinished: list[str], operator: str, settled: "Settled") -> str:
    """The brief of a ticket analyst that judges what a change's editors
    leave for a decision, by the latest item checker's reply from after
    its last `LEFT_FOR_DECISION` line, or the whole reply where it has none,
    the `question` tickets filed on the change, and the
    items the latest report of each editor of `unfinished`, by agent id,
    gives as unfinished, with
    the agent id and part of each of its editors, each beside its record
    in `editors`, and each editor's agent id and latest report in
    `reports`, which that reply refers to, and what the agents before it
    settled (`settled_lines`)."""
    lines = [*change_lines(number, worktree), *editor_lines(editors)]
    if left is not None:
        lines.append(LEFT_REPLY.format(number=number, heading=LEFT_FOR_DECISION))
        lines.append(f"\n{left}\n")
    lines.extend(editor_reports(reports))
    if questions:
        lines.append(mctx("Decide, as items left for a decision, the `question` tickets filed "
                          "on the change, {questions}, and send each decision to its "
                          "editors.").format(questions=", ".join(questions)))
    if unfinished:
        lines.append(mctx("Decide, as items left for a decision, the items that the latest "
                          "report above of each of {editors} gives as "
                          "unfinished.").format(editors=", ".join(unfinished)))
    lines.append(LAUNCHER.format(operator=operator))
    return "\n".join(lines + settled_lines(settled))


DECIDED = mctx("Raise, keep or leave for a decision, in any words, no finding or item, or place "
               "a code editor's report gives as standing, that a report of a ticket analyst or a "
               "ruling below settles, unless you have, or an editor's report gives, a reason for "
               "it that the report or the ruling did not judge.")
EARLIER = mctx("Raise again, in any words, no finding or item that the latest report below of an "
               "earlier {role} on the change gives as settled, unless you have a reason for it "
               "that the report did not judge.")
REPORT_FILED = mctx("- The latest report of {role} {agent} is in the file `{path}`.")
REPORT_BELOW = mctx("- The latest report of {role} {agent} follows.")
RULED = mctx("- A ruling gave the hold below the choice `{choice}`: {meaning}.")
RESTS_FILED = mctx("- That hold rests on the reply of {agent}, whose latest report is in the "
                   "file `{path}`.")
RESTS_BELOW = mctx("- That hold rests on the reply of {agent}, whose latest report follows.")


def report_lines(filed: str, below: str, r: "Reported", **holes: str) -> list[str]:
    """The lines that give the latest report of `r`: the line `filed`
    with the path of its report file, or, where it was read from none, the
    line `below` with its text."""
    if r.report.file is not None:
        return [filed.format(agent=r.agent_id, path=r.report.file, **holes)]
    return [below.format(agent=r.agent_id, **holes), f"\n{r.report.text}\n"]


def settled_lines(settled: "Settled") -> list[str]:
    """The block that ends the brief of an agent launched on a change,
    which gives what the agents launched on it before settled, or no
    line where they settled nothing."""
    if not (settled.analysts or settled.earlier or settled.ruled):
        return []
    lines = [SETTLED.format(number=settled.number)]
    if settled.analysts or settled.ruled:
        lines.append(DECIDED)
        for r in settled.analysts:
            lines += report_lines(REPORT_FILED, REPORT_BELOW, r, role=Role.TICKET_ANALYST)
        for ruled in settled.ruled:
            lines += [RULED.format(choice=ruled.choice, meaning=ruled.meaning),
                      f"\n{ruled.hold}\n"]
            if ruled.reply is not None:
                lines += report_lines(RESTS_FILED, RESTS_BELOW, ruled.reply)
    if settled.earlier:
        lines.append(EARLIER.format(role=settled.role))
        for r in settled.earlier:
            lines += report_lines(REPORT_FILED, REPORT_BELOW, r, role=settled.role)
    return lines


def pass_settle(numbers: list[str], task: str, review: str, operator: str) -> str:
    return PASS_SETTLE.format(numbers=item_list(numbers), task=task, review=review) + "\n" + (
        LAUNCHER.format(operator=operator))


HELD_STEP = mctx("Rule the step below, which the operator that launches you holds and its "
                 "command cannot decide.")


UNPLACED_STEP = mctx("Make the act the step below needs, which the operator that launches you "
                     "holds and its command cannot place, and give no ruling line.")


def held_step(what: str, operator: str, rulable: bool, settled: "Settled | None") -> str:
    """The brief of a ticket analyst on the undecided step `what`, which
    gives the `Decision:` line that rules it where `rulable`, with, where
    the step is of a change, what the agents launched on it settled
    (`settled_lines`)."""
    head = HELD_STEP if rulable else UNPLACED_STEP
    block = [] if settled is None else settled_lines(settled)
    return "\n".join([head, "", what, "", LAUNCHER.format(operator=operator), *block])


# "read no ticket's body to match": the user's words, "if there's a brief
# description then they can browse over those instead of the contents"
# (ticket 6-440, 21:44:14Z).
DEFERRED_TITLES = mctx("list the titles under `tickets/deferred/` in one `grep -m1 -H '^# '` call, "
                       "and read no ticket's body to match")

TRANSCRIPT_REVIEW = mctx("""
    - Review the transcript of run {run}, which `python3 ~/.claude/skills/retrieve/transcripts.py --help` reads.
    - File each ticket by the lines of [Ticket files](prompts/agents/notes/tickets.md#ticket-files), {filing}.
    - Find each place where the run explored to find what a docstring or a document line could have led it to.
    - At the first such place, {deferred_titles}.
    - At each such place:
        - Where a title of that listing, or of a ticket you filed after it, states the same place and that ticket is a `delay` under `tickets/deferred/`, append the place as a case to that ticket, by `uv run python scripts/file_ticket.py case --help`.
        - Otherwise file a ticket of kind `delay` on the place, with its case and its `fix`, by `uv run python scripts/file_ticket.py case --help`.
    """)

PASS_REVIEW = mctx("""
    - Read the pass call by call, with its timing, for what the tool and the documents did to the pass's work, and file a ticket of kind `interference` where they made the pass's output wrong, and of kind `delay` where they added only to its time or token cost.
    """)


def transcript_review(run: str, domain: str, subject: str, solver_pass: bool) -> str:
    filing = FILE_AS.format(
        domain_subject=mctx("`{domain}` and `{subject}`").format(domain=domain, subject=subject),
        agent=CODE_WORD.format(word=Role.TRANSCRIPT_REVIEW))
    text = TRANSCRIPT_REVIEW.format(run=run, filing=filing, deferred_titles=DEFERRED_TITLES)
    return f"{text}\n{PASS_REVIEW}" if solver_pass else text


OVERRIDE = mctx("Override: {text}")
"""An override a ruling gives a solver pass, labelled as one in its brief."""


def solver_pass(task: str, overrides: list[str]) -> str:
    return "\n".join([mctx("Task {task}.").format(task=task),
                      *(OVERRIDE.format(text=text) for text in overrides)])


def code_review(baseline: int, scratch: Path) -> str:
    return mctx("The earlier code review's baseline is the tag `{tag}`, and "
                "this code review's number is {number}.").format(
        tag=code_review_tag(baseline), number=baseline + 1) + "\n" + SCRATCH.format(scratch=scratch)


STANDING_DOC_REVIEW = mctx("""
    - A standing doc review of the reader `{reader}`.
    - The commit of `master` it reviews: {commit}.
    - Its record in git: the tag `{tag}`.
    """)


def standing_doc_review(reader: str, tag: str, commit: str, operator: str) -> str:
    return (STANDING_DOC_REVIEW.format(reader=reader, commit=commit, tag=tag) + "\n"
            + LAUNCHER.format(operator=operator))


# "file none": the user's words on change 6-313's filing rule, "will it
# cause a flood of won't fix" (ticket 10-212).
BATCH_PROFILE = mctx("""
    - Run `uv run python scripts/profile_runs.py --each <id> ...` once, with the agent ids of all these runs as `<id> ...`: {runs}.
    - Before you give your first case, {deferred_titles}.
    - For each cause across these runs that you judge worth fixing, by the test that a change to a tool or a document could cut the time or the token cost it made, take each run the cause cost time or tokens in, in turn:
        - Where a ticket outside `tickets/closed/` and `tickets/deferred/` records the cause, file none.
        - Otherwise give a case on that run, by `uv run python scripts/file_ticket.py case --help`: append it to the `delay` ticket under `tickets/deferred/` whose title in that listing states the cause, or that you filed on it, and where the cause has none, file a ticket of kind `delay` on the cause with it, {filing}, and the `fix` the cause needs.
    {review}
    - Reply only once each transcript review you launched has replied, with the tickets you filed, the tickets you appended cases to, and the reviews you launched.
    """)


# "launch no further review": ticket 6-584 records a batch profile that
# launched 14 transcript reviews after the filing crash was known.
REVIEW = mctx("""
    - Launch a transcript review of each of these runs that is no solver work and of which the output of that `--each` call marks a message `past budget`, and of no other run: {reviewable}.
    - Once a ticket filing of yours, or the reply of a review you launched, gives that a command the brief of a transcript review has it run failed, launch no further review.
    - A transcript review is a `general-purpose` agent, with `{model}` as the Agent call's `model`, and with the brief that {review_brief} gives, with the run's agent id in place of `{run}`.
    """)

NO_REVIEW = mctx("- Launch no transcript review.")

RUN = "<run>"


def batch_profile(runs: list[str], reviewable: list[str], commit: str) -> str:
    filing = FILE_AS.format(domain_subject=mctx("`commit` and `{commit}`").format(commit=commit),
                            agent=OPERATOR)
    if not reviewable:
        return BATCH_PROFILE.format(runs=", ".join(runs), filing=filing, review=NO_REVIEW,
                                    deferred_titles=DEFERRED_TITLES)
    review = REVIEW.format(reviewable=", ".join(reviewable),
                           review_brief=mctx("the block below"), run=RUN,
                           model=Role.TRANSCRIPT_REVIEW.model)
    text = BATCH_PROFILE.format(runs=", ".join(runs), filing=filing, review=review,
                                deferred_titles=DEFERRED_TITLES)
    brief = transcript_review(RUN, "agent", RUN, False)
    return f"{text}\n\n```\n{brief}\n```"


# "no ticket for a `LOADED` line": the user's ruling, option 1, in ticket
# 1791213581-gate-slow-load-triage-1.
BATCH_GATE = mctx("""
    - Add a worktree with `git worktree add --detach <dir> master`, with a new directory under {scratch} as `<dir>`.
    - Run `uv run python scripts/gate.py --accept --since-timed <out>` in that worktree, and file a `performance` ticket for each `SLOW` line it prints, and no ticket for a `LOADED` line.
    - Then run `uv run python scripts/gate.py --outputs-only --record-deps <out>` there, with a new `<out>`, and remove that worktree.
    - For each `DIFF` line these runs print that the `Evidence` of no ticket outside `tickets/draft/` and `tickets/closed/` holds, bisect the commits of `master` from the commit that the `affected:` line of the run that printed it gives after `the change from` to `master`, and file a ticket of kind `bug` that names the commit the bisection stops at.
        - Run each step in a worktree you add at the commit with `git worktree add --detach` and remove after.
        - A step for a `DIFF` line ending in `warm` is `uv run python scripts/gate.py <out> <cmd ...>`, with the commands of that commit's gate in the order its `--help` lists them, up to and including that line's command, and you pass over each line it prints on a command's time.
        - Each other step is `uv run python scripts/gate.py --outputs-only <out> <cmd>`, with that line's command.
        - A step at a commit whose gate has no such command counts as before the change.
        - File a `DIFF` line unbisected where it stands at that commit, where no `affected:` line of that run gives one, or where it ends in `warm` and its step at `master` does not print it, and say which in the ticket.
    - File each ticket {filing}.
    - Reply with the tickets you filed.
    """)


def batch_gate(scratch: Path) -> str:
    return BATCH_GATE.format(scratch=scratch, filing=AT_MASTER)


PROCESS_ASSESSMENT = mctx("Make the process assessment of the agents' processes.")


def process_assessment(operator: str) -> str:
    return PROCESS_ASSESSMENT + "\n" + LAUNCHER.format(operator=operator)


COST_AUDIT = mctx("""
    - Audit the cost of the runs of each session in `{transcripts}` that were active in the window from {since}, or from the launch of the latest other cost audit of any session where that launch is later, to now.
        - Another cost audit is a run under that directory whose `.meta.json` gives a `description` of the form `{description}`, and its launch is that run's first entry.
    - Profile the runs with `uv run python scripts/profile_runs.py` and its `--each`, `--runs`, `--type` and `--top` options, read a run's transcript where a line of its profile looks suspect, and read a ticket's log for what an agent was launched for.
    - Where a run has entries before the window's start, count only the share of its cost from its entries in the window, as an estimated figure with that basis.
    - Find each kind of step whose summed cost over the window exceeds what it finds, and each cost that bought no work or that a cheaper path would have cut.
    - Run `uv run python scripts/bottlenecks.py --since <the window's start>`. Each row of its output whose cost, with its hours priced at the rate [The user's preferences](prompts/agents/notes/decisions.md#the-users-preferences) gives for time, exceeds the cost of the change that would remove its cause is a finding, and no churn figure is one.
    - Leave out what a process covers and did not miss: the checks that [Quality assurance (quality assurance, incident management, problem management)](prompts/agents/notes/process.md#quality-assurance-quality-assurance-incident-management-problem-management) gives cover each run, and file nothing on a cause that a ticket outside `tickets/closed/` records.
    - File one `performance` ticket per finding, {filing}. Give in it the cost in dollars, the agent type, the evidence as agent ids, ticket numbers and times, the cause in one line, each figure labeled measured or estimated with the basis of each estimate, and what a cut of its step would trade off.
    - Edit no tracked file and launch no agent.
    - Reply with the tickets you filed, and the files of highest churn in the `bottlenecks.py` output, with their waits and rebase conflicts.
    """)


def cost_audit(since: float, transcripts: Path, operator: str) -> str:
    return (COST_AUDIT.format(since=utc_stamp(since), transcripts=transcripts,
                              description=description(Role.COST_AUDIT, "<n>"), filing=AT_MASTER)
            + "\n" + LAUNCHER.format(operator=operator))


OVER_BUDGET = mctx("Change {number} is past its cost budget.")


AT_BUDGET = mctx("Where your documents give what you do at your budget, do that at it, and "
                 "otherwise do all your work, past your budget where it takes longer.")
"""What an agent does at its budget."""

BUDGET = "Budget: {minutes} minutes. " + AT_BUDGET
"""The line of a brief that gives the agent its budget and what it does at
its budget."""
