"""The briefs of the agents the operator launches, each in the form
[Briefs](prompts/agents/notes/launching.md#briefs) gives for its work, and
the messages the operator sends them, and the number of items a brief
that gives several items of the same work gives. A brief gives the agent
id of the operator that launches the agent, which the agent replies to."""

import re
from pathlib import Path
from string import Formatter

from controlled_markdown import mctx
from operating.roles import Role

TICKET_PATH = "uv run python scripts/file_ticket.py path {number}"
WORK_IN = mctx("Work in the worktree {worktree}.")
TESTS = mctx("Tests directory: `tests/`.")
SCRATCH = mctx("Scratch directory: {scratch}.")
LAUNCHER = mctx("The agent that launches you: {operator}.")
MAY_EDIT = mctx("The files you may edit: {files}.")


def read_ticket(number: str) -> str:
    return mctx("Change {number}: read the ticket with `{command}`.").format(
        number=number, command=TICKET_PATH.format(number=number))

PARTS: dict[Role, str] = {
    Role.CODE_EDITOR: mctx("the code under `src/`, `scripts/` and `tests/`"),
    Role.HANDBOOK_EXPANDED: mctx("the lib, its modules and the solvers under `programs/`, with "
                                 "the accepted gate outputs its items change"),
    Role.DOC_EDITOR: mctx("the documents"),
}
"""The part of a change each editor takes, where the change has more than
one, as [Carrying a change](prompts/agents/notes/changes.md#carrying-a-change)
splits it."""


def editor(role: Role, number: str, part: bool, worktree: Path | None, scratch: Path,
           operator: str) -> str:
    """The brief of an editor of the change `number`, with its part where
    `part`, in `worktree` where the change has one."""
    lines = [read_ticket(number)]
    if part:
        lines.append(mctx("Your part: {part}.").format(part=PARTS[role]))
    if worktree is not None:
        lines.append(WORK_IN.format(worktree=worktree))
    lines.append(mctx("Accepted gate outputs under `tests/gate/accepted/` you may write: each "
                      "that a `DIFF` of the gate your items cause names."))
    if role is Role.CODE_EDITOR:
        lines.append(TESTS)
    lines.append(SCRATCH.format(scratch=scratch))
    lines.append(LAUNCHER.format(operator=operator))
    return "\n".join(lines)


def doc_review(number: str, worktree: Path, editors: list[tuple[Role, str]],
               operator: str) -> str:
    lines = [mctx("Review the change to the documents of change {number}: the diff that "
                  "`git -C {worktree} diff master` prints.").format(
                      number=number, worktree=worktree)]
    for role, aid in editors:
        lines.append(mctx("Its {role}: {aid}, whose files are {part}.").format(
            role=role, aid=aid, part=PARTS[role]))
    lines.append(LAUNCHER.format(operator=operator))
    return "\n".join(lines)


def new_editor(aid: str) -> str:
    """The message that gives a doc reviewer the editor launched for its
    findings."""
    return mctx("Send your findings on the change to its new doc editor, {aid}.").format(aid=aid)


def review_fix(role: Role, number: str, worktree: Path, reviewer: str, files: list[str],
               scratch: Path, operator: str) -> str:
    """The brief of an editor launched for a doc reviewer's findings: a doc
    editor for those on the documents, a code editor, with `files` as the
    files it may edit, for those on prose in code."""
    lines = [read_ticket(number), WORK_IN.format(worktree=worktree),
             mctx("Your items: the findings doc reviewer {reviewer} sends you, each corrected "
                  "in its line.").format(reviewer=reviewer)]
    if role is Role.CODE_EDITOR:
        lines += [MAY_EDIT.format(files=", ".join(files)), TESTS]
    lines += [SCRATCH.format(scratch=scratch), LAUNCHER.format(operator=operator)]
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


def merge_finding(number: str, output: str) -> str:
    return mctx("A finding of your checks on change {number}: the merge refused it, as "
                "below.").format(number=number) + f"\n{output}"


AFTER_MERGE = mctx("""
    - Change {number} is merged into `master` at {head}. Run each check its ticket places after the merge, which `{command}` prints: {checks}.
    - File each check that fails as a `bug` ticket, by the lines of the section `Ticket files` of `prompts/agents/notes/tickets.md`, with `change` and {number} as `<domain>` and `<subject>`, and `operator` as `<agent>`.
    - Give each check whose subject is an event that has not happened yet in your reply as unfinished, with that reason.
    - Run a check of what a running Claude Code session reads only at its start, such as its hooks, in a `claude -p` session you start in the main worktree.
    - Reply with each check as passed, failed with its ticket, or unfinished with its reason.
    """)


def after_merge(number: str, checks: str, head: str) -> str:
    return AFTER_MERGE.format(number=number, head=head, checks=checks,
                              command=TICKET_PATH.format(number=number))


def later_line(number: str, time: float, note: str) -> str:
    """The message that gives a running ticket analyst a line the
    coordinator wrote on ticket `number` after its launch."""
    return "\n".join([
        mctx("The coordinator wrote on ticket {number}, in its log at {time:.0f}, after your "
             "launch: {note}").format(number=number, time=time, note=note),
        mctx("Take it into your work on that ticket.")])


REVIEW_DRAFTS = mctx("Review the drafts {numbers}.")
SETTLE = mctx("Settle the tickets under `tickets/open/` {numbers}.")
REVISE = mctx("Revise each draft `change` ticket {numbers}, whose log holds findings.")
PASS_SETTLE = mctx("Settle the tickets under `tickets/open/` {numbers}, which the solver pass on "
                   "task {task} and the review of its transcript filed. That review is agent "
                   "{review}: read its report with `python3 ~/.claude/skills/retrieve/"
                   "transcripts.py --help`.")
ITEM_LINES = (REVIEW_DRAFTS, SETTLE, REVISE, PASS_SETTLE)
"""The first lines of the briefs that give several items of the same
work, each item a ticket number in the slot `numbers`."""


ITEM_SEPARATOR = ", "
ITEM = r"[^\s,]+"


def item_list(numbers: list[str]) -> str:
    return ITEM_SEPARATOR.join(numbers)


def item_pattern(template: str) -> re.Pattern[str]:
    """The lines `template` renders, with the item list in the group
    `numbers`."""
    parts = []
    for literal, slot, _, _ in Formatter().parse(template):
        parts.append(re.escape(literal))
        if slot == "numbers":
            parts.append(rf"(?P<numbers>{ITEM}(?:{ITEM_SEPARATOR}{ITEM})*)")
        elif slot is not None:
            parts.append(".*?")
    return re.compile("".join(parts))


ITEM_PATTERNS = tuple(item_pattern(t) for t in ITEM_LINES)


def items(brief: str) -> int | None:
    """The number of items a brief gives, where its first line is one of
    `ITEM_LINES`, or None where it is none of them."""
    first = brief.split("\n", 1)[0]
    for pattern in ITEM_PATTERNS:
        if (m := pattern.fullmatch(first)) is not None:
            return len(m["numbers"].split(ITEM_SEPARATOR))
    return None


def ticket_review(numbers: list[str], operator: str) -> str:
    return "\n".join([REVIEW_DRAFTS.format(numbers=item_list(numbers)),
                      LAUNCHER.format(operator=operator)])


def settle(numbers: list[str], operator: str) -> str:
    return "\n".join([SETTLE.format(numbers=item_list(numbers)),
                      LAUNCHER.format(operator=operator)])


def revise(numbers: list[str], last: list[str], operator: str) -> str:
    lines = [REVISE.format(numbers=item_list(numbers))]
    if last:
        lines.append(mctx(
            "The revision of {last} is the last: the draft then opens with no further ticket "
            "review, and the change's own review checks what the change writes.").format(
                last=", ".join(last)))
    lines.append(LAUNCHER.format(operator=operator))
    return "\n".join(lines)


def findings(number: str, worktree: Path, reports: list[tuple[str, str]],
             questions: list[str], gate: list[str], editors: list[str], operator: str) -> str:
    """The brief of a ticket analyst on what a change's editors leave, by
    each editor's agent id and latest report, and on the `question`
    tickets filed on the change."""
    lines = [read_ticket(number), mctx("Its worktree: {worktree}.").format(worktree=worktree)]
    for editor_id, report in reports:
        lines.append(mctx(
            "Judge each finding, and decide each finding and each item left for a decision, "
            "that the report of its editor {editor} below leaves, with that editor's reasons, "
            "and judge each place the `Review` section of that report gives as standing.").format(
                editor=editor_id))
        lines.append(f"\n{report}\n")
    if questions:
        lines.append(mctx("Decide, as items left for a decision, the `question` tickets filed "
                          "on the change: {questions}.").format(questions=", ".join(questions)))
    if gate:
        lines.append(mctx(
            "Read the diff of each accepted gate output the change writes, {gate}, and send "
            "each difference there that the change's items do not ask for to its editors, "
            "{editors}, as a finding of its checks.").format(
                gate=", ".join(gate), editors=", ".join(editors)))
    lines.append(LAUNCHER.format(operator=operator))
    return "\n".join(lines)


def pass_settle(numbers: list[str], task: str, review: str, operator: str) -> str:
    return PASS_SETTLE.format(numbers=item_list(numbers), task=task, review=review) + "\n" + (
        LAUNCHER.format(operator=operator))


TRANSCRIPT_REVIEW = mctx("""
    - Review the transcript of run {run}, which `python3 ~/.claude/skills/retrieve/transcripts.py --help` reads.
    - File each ticket by the lines of the section `Ticket files` of `prompts/agents/notes/tickets.md`, with `{domain}` as `<domain>`, `{subject}` as `<subject>`, and `transcript-review` as `<agent>`.
    - File a ticket of kind `delay` for each place where the run explored to find what a docstring or a document line could have led it to.
    """)

PASS_REVIEW = mctx("""
    - Read the pass call by call, with its timing, for what the tool and the documents did to the pass's work, and file a ticket of kind `interference` where they made the pass's output wrong, and of kind `delay` where they added only to its time or token cost.
    """)


def transcript_review(run: str, domain: str, subject: str, solver_pass: bool) -> str:
    text = TRANSCRIPT_REVIEW.format(run=run, domain=domain, subject=subject)
    return f"{text}\n{PASS_REVIEW}" if solver_pass else text


def solver_pass(task: str) -> str:
    return mctx("Task {task}.").format(task=task)


def code_review(baseline: int, scratch: Path) -> str:
    return mctx("The earlier code review's baseline: the tag `code-review/{baseline}`. This "
                "code review's number: {number}. The new code the diff holds: the commits of "
                "`master` since that tag.").format(
        baseline=baseline, number=baseline + 1) + "\n" + SCRATCH.format(scratch=scratch)


BATCH_PROFILE = mctx("""
    - Run `uv run python scripts/profile_runs.py <id>` with the agent id of each of these runs, one run per call: {runs}.
    - File a `performance` ticket, with `commit` and `{commit}` as `<domain>` and `<subject>` and `operator` as `<agent>`, for each label or part of a run or of an agent type that you judge worth fixing, by the test that a change to a tool or a document could shorten it.
    - Launch a transcript review of each of those runs that is no solver work and that `uv run python scripts/profile_runs.py <agent id>` shows past its budget: where a message from its parent has a `Budget: N minutes` line, by a message that command marks `past budget`, and otherwise, where its agent type has a budget, by its active time, its wall time less its `idle` time as that command prints them, past that budget. A transcript review is a `general-purpose` agent, with the brief that {review_brief} gives, with the run's agent id in place of `{run}`.
    - Reply with the tickets you filed and the reviews you launched.
    """)


RUN = "<run>"


def batch_profile(runs: list[str], commit: str) -> str:
    review = transcript_review(RUN, "agent", RUN, False)
    text = BATCH_PROFILE.format(runs=", ".join(runs), commit=commit,
                                review_brief=mctx("the block below"), run=RUN)
    return f"{text}\n\n```\n{review}\n```"


BATCH_GATE = mctx("""
    - Add a worktree with `git worktree add --detach <dir> master`, with a new directory under {scratch} as `<dir>`. Run `uv run python scripts/gate.py --accept --since-timed <out>` in that worktree, and file a `performance` ticket for each `SLOW` line it prints, and no ticket for a `LOADED` line.
    - Then run `uv run python scripts/gate.py --outputs-only --record-deps <out>` there, with a new `<out>`, and remove that worktree.
    - For each `DIFF` line these runs print that the `Evidence` of no ticket outside `tickets/draft/` and `tickets/closed/` holds, bisect the commits of `master` from the commit that the `affected:` line of the first run gives after `the change from` to `master`, each step in a worktree you add at the commit with `git worktree add --detach` and remove after, and file a ticket of kind `bug` that names the commit the bisection stops at.
        - A step for a `DIFF` line ending in `warm` is `uv run python scripts/gate.py <out> <cmd ...>`, with the commands of that commit's gate in the order its `--help` lists them, up to and including that line's command, and you pass over each line it prints on a command's time. Each other step is `uv run python scripts/gate.py --outputs-only <out> <cmd>`, with that line's command. A step at a commit whose gate has no such command counts as before the change.
        - File a `DIFF` line unbisected where it stands at that commit, where no `affected:` line of that run gives one, or where it ends in `warm` and its step at `master` does not print it, and say which in the ticket.
    - File each ticket with `commit` and the hash `master` stands at as `<domain>` and `<subject>`, and `operator` as `<agent>`.
    - Reply with the tickets you filed.
    """)


def batch_gate(scratch: Path) -> str:
    return BATCH_GATE.format(scratch=scratch)


def stop_work(number: str) -> str:
    """The message that tells an agent at work on a change or a draft whose
    ticket the operator no longer carries to end."""
    return mctx("Write nothing further on {number}, and end with your open work in your "
                "reply.").format(number=number)


BUDGET = "Budget: {minutes} minutes"
"""The line of a brief that gives the agent its budget, in the form
`profile_runs.py --help` reads."""
