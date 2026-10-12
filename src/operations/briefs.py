"""The briefs of the agents the operator launches, each in the form
[Briefs](prompts/agents/notes/launching.md#briefs) gives for its work. A
brief gives the agent id of the operator that launches the agent, which
the agent replies to."""

import shlex
from dataclasses import dataclass
from pathlib import Path

from controlled_markdown import mctx
from operations.reports import LEFT_FOR_DECISION, WORKTREE
from operations.roles import Role, description
from operations.state import Place
from operations.tracker import AGENT, FILE_TICKET
from ticketing.text import VALIDATION
from ticketing.times import utc_stamp
from ticketing.vocabulary import Domain, Status, Verdict

TICKET_PATH = shlex.join([*FILE_TICKET, "path"]) + " {number}"
WORK_IN = mctx("Work in the worktree {worktree}.")
TESTS = mctx("Tests directory: `tests/`.")
SCRATCH = mctx("Scratch directory: {scratch}.")
LAUNCHER = mctx("The agent that launches you: {operator}.")
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
    Role.CODE_EDITOR: mctx("the code under `src/`, `scripts/` and `tests/`, with a draft of the "
                           "text of each `mctx` fragment it needs"),
    Role.HANDBOOK_EXPANDED: mctx("the lib, its modules and the solvers under `programs/`, with "
                                 "the accepted gate outputs its items change"),
    Role.DOC_EDITOR: mctx("the documents and the text of the `mctx` fragments"),
}
"""The part of a change each editor takes, where the change has more than
one, as [Carrying a change](prompts/agents/notes/changes.md#carrying-a-change)
splits it."""


FRAGMENTS_PART = mctx("Your part: the text of the `mctx` fragments below, with the moves "
                      "that text needs.")
"""The part of the doc editor `changes` launches on a change's fragments,
which keys that editor apart from the change's doc editor of the
documents."""


def editor(role: Role, number: str, part: bool, worktree: Path, scratch: Path,
           operator: str, fragments: tuple[Place, ...] = (),
           code_editors: tuple[str, ...] = (), of_fragments: bool = False) -> str:
    """The brief of an editor of the change `number`, with its part where
    `part`, or `FRAGMENTS_PART` where `of_fragments`, in the change's
    worktree `worktree`. A doc editor's brief gives the `fragments`, and
    the agent ids of the change's `code_editors`."""
    lines = [read_ticket(number)]
    if of_fragments:
        lines.append(FRAGMENTS_PART)
    elif part:
        lines.append(mctx("Your part: {part}.").format(part=PARTS[role]))
    lines.append(WORK_IN.format(worktree=worktree))
    if role is Role.DOC_EDITOR and fragments:
        lines.append(FRAGMENTS)
        lines += [FRAGMENT.format(file=f.file, line=f.line) for f in fragments]
        if code_editors:
            lines.append(CODE_EDITORS.format(ids=", ".join(code_editors)))
    lines.append(mctx("Accepted gate outputs under `tests/gate/accepted/` you may write: each "
                      "that a `DIFF` of the gate your items cause names."))
    if role is Role.CODE_EDITOR:
        lines.append(TESTS)
    lines.append(SCRATCH.format(scratch=scratch))
    lines.append(LAUNCHER.format(operator=operator))
    return "\n".join(lines)


FRAGMENTS = mctx("Judge whether the text of each `mctx` fragment below, which a code editor "
                 "drafted for you to write, belongs in its program, by [What goes "
                 "where](docs/handbook/editing.md#what-goes-where), move what does not to "
                 "where it belongs, then write the text that stays.")

FRAGMENT = mctx("- `{file}`, line {line}")

CODE_EDITORS = mctx("Where a move needs the code to change, send that code change by "
                    "SendMessage to the code editor of the change: {ids}.")


FINGERPRINT = mctx("Before you write each final reply, run `uv run python "
                   "scripts/change_worktree.py --fingerprint {worktree}`, and end that reply with "
                   "the line `{opening} <what it printed>`.")


def fingerprint_line(worktree: Path) -> str:
    return FINGERPRINT.format(worktree=worktree, opening=WORKTREE)


def doc_review(number: str, worktree: Path, editors: list[tuple[Role, str]],
               operator: str) -> str:
    lines = [mctx("Review the change to the documents of change {number}: the diff that "
                  "`git -C {worktree} diff --merge-base master` prints.").format(
                      number=number, worktree=worktree)]
    for role, aid in editors:
        lines.append(mctx("Its {role}: {aid}, whose files are {part}.").format(
            role=role, aid=aid, part=PARTS[role]))
    lines.append(fingerprint_line(worktree))
    lines.append(LAUNCHER.format(operator=operator))
    return "\n".join(lines)


def quotes_fix(number: str, worktree: Path, calls: list[str], files: list[str], scratch: Path,
               operator: str) -> str:
    """The brief of a code editor on the `quotes` calls a change to the
    documents broke, as [Carrying a change](prompts/agents/notes/changes.md#carrying-a-change)
    gives it."""
    return "\n".join([
        read_ticket(number), WORK_IN.format(worktree=worktree),
        mctx("Your items: repair each `quotes` call the `controlled_markdown` check reports "
             "below."),
        *calls,
        MAY_EDIT.format(files=", ".join(files)), TESTS, SCRATCH.format(scratch=scratch),
        LAUNCHER.format(operator=operator)])


# The lines on a check whose event has not happened and on a check of what
# a session reads at its start: ticket 2-354 records checks closed at the
# merge with no one holding them (2-334, 4-29), and a running session's
# launches checking hooks it had not reloaded.
AFTER_MERGE = mctx("""
    - Change {number} is merged into `master` at {head}.
    - Run each check its ticket places after the merge, which `{command}` prints: {checks}.
    - File each check that fails as a `bug` ticket, by the lines of the section `Ticket files` of `prompts/agents/notes/tickets.md`, {filing}.
    - Give each check whose subject is an event that has not happened yet in your reply as unfinished, with that reason.
    - Run a check of what a running Claude Code session reads only at its start in a `claude -p` session you start in the main worktree.
    - Reply with each check as passed, failed with its ticket, or unfinished with its reason.
    """)


def after_merge(number: str, checks: str, head: str) -> str:
    filing = FILE_AS.format(domain_subject=mctx("`change` and {number}").format(number=number),
                            agent=OPERATOR)
    return AFTER_MERGE.format(number=number, head=head, checks=checks, filing=filing,
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
    operator's that moved it past its cost budget to `tickets/draft/`, and the
    part of the item checker's reply that line names that gives what it
    leaves for a decision."""
    lines = revise_lines(numbers, last)
    for number, line, left in overruns:
        lines.append(mctx("The findings of draft {number} include the operator's line below, "
                          "which moved it past its cost budget to `tickets/draft/`:").format(
                              number=number))
        lines.append(f"\n{line}\n")
        if left is not None:
            lines.append(mctx("What that item checker leaves for a decision:"))
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
    """The lines that give each editor's agent id and latest report."""
    lines: list[str] = []
    for editor_id, report in reports:
        lines.append(mctx("The latest report of editor {editor}:").format(editor=editor_id))
        lines.append(f"\n{report}\n")
    return lines


def item_check(number: str, worktree: Path, reports: list[tuple[str, str]],
               decisions: list[tuple[str, str]], gate: list[str], editors: list[str],
               operator: str, past: bool = False) -> str:
    """The brief of an item checker that checks the items of a change's
    editors, by each editor's agent id and latest report, and the accepted
    gate outputs the change writes, with the agent ids of its editors.
    Where `decisions` gives the agent id and latest report of ticket
    analysts on the change, it tells the checker to leave out of its
    `LEFT_FOR_DECISION` part what those decisions settle, unless the
    editor's report gives a reason they did not judge. `past` gives that
    the change is past its cost budget."""
    lines = change_lines(number, worktree)
    if past:
        lines.append(OVER_BUDGET.format(number=number))
    lines.extend(editor_reports(reports))
    if decisions:
        lines.append(mctx(
            "Leave out of your `{heading}` part each finding, item or standing place that a "
            "decision of a ticket analyst on the change, {analysts}, settles in its report "
            "below, where the editor's report gives no reason for it that the decision did "
            "not judge.").format(
                analysts=", ".join(i for i, _ in decisions), heading=LEFT_FOR_DECISION))
    for analyst_id, report in decisions:
        lines.append(mctx("The latest report of ticket analyst {analyst}:").format(analyst=analyst_id))
        lines.append(f"\n{report}\n")
    if gate:
        lines.append(mctx(
            "Read the diff of each accepted gate output the change writes, {gate}, and send "
            "each difference there that the change's items do not ask for to its editors, "
            "{editors}, as a finding of its checks.").format(
                gate=", ".join(gate), editors=", ".join(editors)))
    lines.append(fingerprint_line(worktree))
    lines.append(LAUNCHER.format(operator=operator))
    return "\n".join(lines)


def findings(number: str, worktree: Path, left: str | None, questions: list[str],
             editors: list[str], reports: list[tuple[str, str]], operator: str) -> str:
    """The brief of a ticket analyst that judges what a change's editors
    leave for a decision, by the part of the latest item checker's reply
    that gives it, and the `question` tickets filed on the change, with
    the agent ids of its editors and each editor's agent id and latest
    report in `reports`, which that part refers to."""
    lines = [*change_lines(number, worktree), mctx("Its editors: {editors}.").format(editors=", ".join(editors))]
    if left is not None:
        lines.append(mctx("What the item checker on the change leaves for a decision:"))
        lines.append(f"\n{left}\n")
    lines.extend(editor_reports(reports))
    if questions:
        lines.append(mctx("Decide, as items left for a decision, the `question` tickets filed "
                          "on the change, {questions}, and send each decision to its "
                          "editors.").format(questions=", ".join(questions)))
    lines.append(LAUNCHER.format(operator=operator))
    return "\n".join(lines)


def pass_settle(numbers: list[str], task: str, review: str, operator: str) -> str:
    return PASS_SETTLE.format(numbers=item_list(numbers), task=task, review=review) + "\n" + (
        LAUNCHER.format(operator=operator))


HELD_STEP = mctx("Rule the step below, which the operator that launches you holds and its "
                 "command cannot decide.")


UNPLACED_STEP = mctx("Make the act the step below needs, which the operator that launches you "
                     "holds and its command cannot place, and give no ruling line.")


def held_step(what: str, operator: str, rulable: bool) -> str:
    """The brief of a ticket analyst on the undecided step `what`, which
    gives the `Decision:` line that rules it where `rulable`."""
    head = HELD_STEP if rulable else UNPLACED_STEP
    return "\n".join([head, "", what, "", LAUNCHER.format(operator=operator)])


# "read no ticket's body to match": the user's words, "if there's a brief
# description then they can browse over those instead of the contents"
# (ticket 6-440, 21:44:14Z).
TRANSCRIPT_REVIEW = mctx("""
    - Review the transcript of run {run}, which `python3 ~/.claude/skills/retrieve/transcripts.py --help` reads.
    - File each ticket by the lines of the section `Ticket files` of `prompts/agents/notes/tickets.md`, {filing}.
    - Find each place where the run explored to find what a docstring or a document line could have led it to.
    - At the first such place, list the titles under `tickets/watching/` in one `grep -m1 -H '^# '` call, and read no ticket's body to match.
    - At each such place:
        - Where a title of that listing, or of a ticket you filed after it, states the same place and that ticket stands under `tickets/watching/`, append the place as a case to that ticket, by `uv run python scripts/file_ticket.py case --help`.
        - Otherwise file a ticket of kind `delay` on the place, with its case and its `fix`, by `uv run python scripts/file_ticket.py case --help`.
    """)

PASS_REVIEW = mctx("""
    - Read the pass call by call, with its timing, for what the tool and the documents did to the pass's work, and file a ticket of kind `interference` where they made the pass's output wrong, and of kind `delay` where they added only to its time or token cost.
    """)


def transcript_review(run: str, domain: str, subject: str, solver_pass: bool) -> str:
    filing = FILE_AS.format(
        domain_subject=mctx("`{domain}` and `{subject}`").format(domain=domain, subject=subject),
        agent=CODE_WORD.format(word=Role.TRANSCRIPT_REVIEW))
    text = TRANSCRIPT_REVIEW.format(run=run, filing=filing)
    return f"{text}\n{PASS_REVIEW}" if solver_pass else text


OVERRIDE = mctx("Override: {text}")
"""An override a ruling gives a solver pass, labelled as one in its brief."""


def solver_pass(task: str, overrides: list[str]) -> str:
    return "\n".join([mctx("Task {task}.").format(task=task),
                      *(OVERRIDE.format(text=text) for text in overrides)])


def code_review(baseline: int, scratch: Path) -> str:
    return mctx("The earlier code review's baseline is the tag `code-review/{baseline}`, and "
                "this code review's number is {number}.").format(
        baseline=baseline, number=baseline + 1) + "\n" + SCRATCH.format(scratch=scratch)


STANDING_DOC_REVIEW = mctx("""
    - A standing doc review of the reader `{reader}`.
    - The commit of `master` it reviews: {commit}.
    - Its record in git: the tag `{tag}`.
    """)


def standing_doc_review(reader: str, tag: str, commit: str, operator: str) -> str:
    return (STANDING_DOC_REVIEW.format(reader=reader, commit=commit, tag=tag) + "\n"
            + LAUNCHER.format(operator=operator))


# "File none on a cause ... already records": the user's words on change
# 6-313's filing rule, "will it cause a flood of won't fix" (ticket 10-212).
BATCH_PROFILE = mctx("""
    - Run `uv run python scripts/profile_runs.py --each <id> ...` once, with the agent ids of all these runs as `<id> ...`: {runs}.
    - File one `performance` ticket, {filing}, for each cause across these runs that you judge worth fixing, by the test that a change to a tool or a document could cut the time or the token cost it made, and give in it the time and the token cost that cause made in these runs.
        - File none on a cause that a ticket outside `tickets/closed/` already records.
    {review}
    - Reply only once each transcript review you launched has replied, with the tickets you filed and the reviews you launched.
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
        return BATCH_PROFILE.format(runs=", ".join(runs), filing=filing, review=NO_REVIEW)
    review = REVIEW.format(reviewable=", ".join(reviewable),
                           review_brief=mctx("the block below"), run=RUN,
                           model=Role.TRANSCRIPT_REVIEW.model)
    text = BATCH_PROFILE.format(runs=", ".join(runs), filing=filing, review=review)
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


VALIDATION_REVIEW = mctx("""
    - Judge the check of each request below against these runs: {runs}.
        - `{show} <number> {section_name}` prints a request's check.
        - `python3 ~/.claude/skills/retrieve/transcripts.py --help` lists the subcommands that read a run's transcript.
    - The requests:
        {checks}
    - Where a check gives a command, run it once, and judge its output in place of the runs.
    - Write each line on a request as `{log} <number> {closed} {agent} --from {closed} "<note>"`.
    - File each ticket by the lines of the section `Ticket files` of `prompts/agents/notes/tickets.md`, {filing}.
    - Where the command's output or a run shows that the check holds, write a line whose note opens with `{validated}`, then gives that run's agent id or the command.
    - Where it shows that the check fails, write a line whose note opens with `{failed}`, then gives that run's agent id or the command, then file a `bug` ticket with the request's number and that run's agent id or the command's output in its `Evidence`.
    - Where the check gives no command, none of those runs exercises what it checks, and the request closed {days} days ago or more, write a line whose note opens with `{unexercised}`, then file a `question` ticket that gives the request's number.
    - Otherwise write nothing on the request.
    - Reply with the lines you wrote and the tickets you filed.
    """)

CHECK = mctx("- `{number}`: change `{change}`, closed at {time}.")

CHECK_NO_CHANGE = mctx("- `{number}`: no change, closed at {time}.")

UNEXERCISED_DAYS = 7
"""The age of a close past which a check no run exercised gets its
`unexercised` line."""


@dataclass(frozen=True)
class Check:
    """A pending check: its request's number, the change that closed it,
    None where the note of its close gives none, and the time of that
    close."""
    request: str
    change: str | None
    closed: float


def validation_review(runs: list[str], checks: list[Check]) -> str:
    return VALIDATION_REVIEW.format(
        runs=", ".join(runs), section_name=VALIDATION,
        show=shlex.join([*FILE_TICKET, "show"]),
        log=shlex.join([*FILE_TICKET, "log"]), closed=Status.CLOSED, agent=Role.VALIDATION_REVIEW,
        validated=Verdict.VALIDATED, failed=Verdict.FAILED, unexercised=Verdict.UNEXERCISED,
        filing=FILE_AS.format(
            domain_subject=mctx("`{change}` and the change's number, or `{ticket}` and the "
                                "request's number where its close gives no change,").format(
                change=Domain.CHANGE, ticket=Domain.TICKET),
            agent=CODE_WORD.format(word=Role.VALIDATION_REVIEW)),
        days=UNEXERCISED_DAYS,
        checks="\n    ".join(check_line(c) for c in checks))


def check_line(c: Check) -> str:
    if c.change is None:
        return CHECK_NO_CHANGE.format(number=c.request, time=utc_stamp(c.closed))
    return CHECK.format(number=c.request, change=c.change, time=utc_stamp(c.closed))


PROCESS_ASSESSMENT = mctx("Make the process assessment of the agents' processes.")


def process_assessment(operator: str) -> str:
    return PROCESS_ASSESSMENT + "\n" + LAUNCHER.format(operator=operator)


COST_AUDIT = mctx("""
    - Audit the cost of the runs of each session in `{transcripts}` that were active in the window from {since}, or from the launch of the latest other cost audit of any session where that launch is later, to now.
        - Another cost audit is a run under that directory whose `.meta.json` gives a `description` of the form `{description}`, and its launch is that run's first entry.
    - Profile the runs with `uv run python scripts/profile_runs.py` and its `--each`, `--runs`, `--type` and `--top` options, read a run's transcript where a line of its profile looks suspect, and read a ticket's log for what an agent was launched for.
    - Where a run has entries before the window's start, count only the share of its cost from its entries in the window, as an estimated figure with that basis.
    - Find each kind of step whose summed cost over the window exceeds what it finds, and each cost that bought no work or that a cheaper path would have cut.
    - Leave out what a process covers and did not miss: the checks that [Quality assurance (quality assurance, incident management, problem management)](prompts/agents/notes/process.md#quality-assurance-quality-assurance-incident-management-problem-management) gives cover each run, and file nothing on a cause that a ticket outside `tickets/closed/` records.
    - File one `performance` ticket per finding, {filing}. Give in it the cost in dollars, the agent type, the evidence as agent ids, ticket numbers and times, the cause in one line, each figure labeled measured or estimated with the basis of each estimate, and what a cut of its step would trade off.
    - Edit no tracked file and launch no agent.
    - Reply with the tickets you filed.
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
its budget, in the form `profile_runs.py --help messages` reads."""
