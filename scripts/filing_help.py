"""The help of filing a ticket with `file_ticket.py`: `HELP`, which the
bare `--help` prints, `FORMS`, the form of each kind that `--help PART`
prints, and `RULES`, which `--help-all` prints after `HELP` and each of
`FORMS`."""

from enum import StrEnum

from controlled_markdown import mctx
from ticketing.vocabulary import Kind


class FormPart(StrEnum):
    """Each kind whose form a part of the help gives, by the word `--help`
    takes to print it, in the order the bare `--help` lists them."""
    CHANGE = Kind.CHANGE.value
    REQUEST = Kind.REQUEST.value


def form_part(kind: Kind) -> FormPart | None:
    """The part of the help that gives the form of `kind`, None where the
    bare `--help` gives it."""
    return next((p for p in FormPart if p.value == kind.value), None)


FORM_PURPOSES = {
    FormPart.CHANGE: mctx("the form of a `change`"),
    FormPart.REQUEST: mctx("the form of a `request`, with its `## Validation` section")}
"""The purpose of each part, as the bare `--help` gives it."""

# The `<target>` line: ticket 11-700, from the user's words, session
# 2384db39, 2026-10-18T02:16:02Z: "Well I hope I have sufficiently expressed
# my intention w op scope own", which chooses the coordinator's version of
# 02:14:05Z, whose own work holds the "refactor and bug tickets on files in
# their Scope".
HELP = mctx("""
    - `{invocation} <domain> <subject> <agent>` files the ticket on its stdin under the main tree's `tickets/`, and prints the path it wrote.
    {subcommands}
    - After the usage form, this text gives the `<target>` lines, the parts of the help, the values of `<domain>` and `<subject>`, `<agent>` and the case of a `{delay}`.
    - Usage:
        ```
        {invocation} <domain> <subject> <agent> <<'EOF'
        ---
        kind: <kind>
        ---
        # <target>: <what is wrong in it>{defect_sections}
        EOF
        ```
    - Where the ticket is about one or more files, `<target>` gives the path of each.
    - Where the ticket is about an agent's context, `<target>` gives the path of that agent's prompt under [agents](prompts/agents).
    {parts}
    - `<domain>` is one of {domains}, and `<subject>` is the id of the thing it names: a task id for `task`, a ticket's number for `change` and `ticket`, a commit hash for `commit`, an agent id for `agent`.
        - A `change` or a `request` takes `change` as `<domain>` and `<namespace>-<short-title>` as `<subject>`, with `-` in place of each `_`.
    - `<agent>` is your agent's name.
    - A `{delay}` may give one case, `--case <source> <start> <end>` after `<agent>`, and then gives `fix: <editor>` in its front matter: `{invocation} case --help` gives the case's form, and `{invocation} case {full_flag}` how the command prices it and where the ticket files.
    {further}
    """)
"""The help of filing, which `--help` with no subcommand prints, with the
lines of the parts, or, under `--help-all`, with each of `FORMS`, in place
of `{parts}`."""

FORMS = {
    FormPart.CHANGE: mctx("""
        - A `change` takes `kind: change` and `editors: <editor>, <editor>`, with each editor whose part, as [Making a change](prompts/agents/notes/changes.md#making-a-change) gives it, holds a file of its Scope, among {editors}.
            - It may add `depends-on: <number>, <number>` and `mechanical: {mechanical}` to the front matter, and no operator takes it while a ticket `depends-on` gives stands outside `tickets/closed/`.
                * comment: Ticket 11-3475: a coordinator read this line as saying a change cannot depend on a request.
            - It gives `mechanical` where its Intent and its `Design` settle each choice of the code editor's part other than how the code is written.
            - Where it gives steps or checks at or after its merge, it places them in one item of its Scope that opens `After the merge`.
            - It has `# <title>` as its title, and the sections {change_sections} in place of {defect_headings}.
            - Where it adds a mechanism to code, it has a `{design}` section after `## Intent` that gives the existing operations the change uses or extends and each new operation with its module.
            - Where it adds or changes a rule or a fact in the agent-facing documents, it has that section.
            - It may have a `## Load` section after `## Design`, with one item for each run that [Checks](prompts/agents/ticket-reviewer/review.md#checks) has the section give: the command in backticks, its estimate of the machine it takes (cores, memory, run time), and why no run of less load shows what its Intent item states.
        """),
    FormPart.REQUEST: mctx("""
        - A `request` has `# <target>: <what the user asks for>` as its title, and the sections {request_sections} in place of {defect_headings}.
            - It may add `depends-on: <number>, <number>` to the front matter, and no ticket analyst is given it while a ticket that field gives stands outside `tickets/closed/`.
            - A `request` that a `change` serves also has, before `## Log`, a `{validation}` section: what a later run must show for its need to count as met.
                - It may hold lines `- {exercised_field} <regular expression>`, the expression with no backticks, each of which matches a line of the transcript of a run that exercises the change, and, for a change to code, no line of a run that only reads that code or its diff. Where it holds none, a run needs no match.
                    - A transcript line is a JSON line, so the expression matches a quote or a backslash in its JSON escape, and the sweep, and `log` on the request's move into `{waiting}`, refuse an expression that matches its own text in that escape, applied once or twice.
                - It may hold lines `- {agent_field} <agent type>`, `main` for the main run of any session, the coordinator's included. Where it holds one or more, a run of a type none of them gives does not exercise the change, so neither does a run of another type that reads other runs' transcripts.
                    * comment: Tickets 14-17 and 14-44: each `Validation` gave `- Agent: main` for the load watch session's main run, and the sweep moved each out of `tickets/deferred/` as exercised by the coordinator's main run of session 19071443, which did no load watch work.
                - Where a command, run from the main tree, exits 0 within {seconds} seconds only where the need is met, it holds one line `- {command_field} <command>`, the command in backticks with nothing after them, and otherwise a statement that an agent judges against a run.
                - Where the need is to cut an agent type's context, the need is met where `uv run python scripts/profile_runs.py ID [ID ...] --split TIME`, with the merge time of the change as TIME and as the IDs the sessions that ran that type before and after it, gives that type's median context per request and median cost per run both lower after TIME than before.
        """)}
"""The form of each kind a part gives, which `--help PART` prints."""

RULES = mctx("""
    - A ticket's number is `<session>-<n>`: `<session>` is the index of the session that filed it, and `<n>` counts that session's tickets from 1.
        - A ticket filed before a number gave the filing session's index has a bare number, and the command takes either form wherever it takes a number.
    - Numbers order with every bare number before every `<session>-<n>` number.
        - Bare numbers compare as integers, and `<session>-<n>` numbers compare by `<session>`, then by `<n>`, each as an integer.
    - The session that files is the one whose id the filing agent's shell holds in `{session_var}`, in a subagent as in the main session.
        - The command refuses a filing where the shell holds none.
    - A session's index has a file under `tickets/{sessions}/`, named by the index, that holds the session's id.
        - A session forked from another takes the index of the session it was forked from, and the file then holds both ids, one per line.
    - The command reserves the ticket's number and names the ticket `{name_form}`.
        - It writes the ticket in the main tree, under `tickets/draft/` for a `change`, where `case {full_flag}` gives for a `{delay}` that gives a case, and under `tickets/{new}/` for any other, with the filing time in the first line of its `## Log`.
    - Run from a worktree, the command files with the main tree's copy of `scripts/file_ticket.py`, and refuses where the main tree has none.
    - Each `<number>` in `depends-on` is the number of a ticket the ticket tracker holds.
    - The paths a section of a `change` gives are each path it gives with a `/` or at the root of the main tree, with no `:<line>` or `:<first>-<last>` after it, and the witness file of each solver it gives.
    - The command refuses, and writes nothing, where the text on stdin does not have the form above.
    """)
"""The rules of numbers, sessions and filing, which `--help-all` with no
subcommand prints after `HELP`."""
