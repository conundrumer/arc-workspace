+ budget: 11199
* comment: when editing this doc
    - Readers: each agent that files tickets inlines the sections for its work; the coordinator links them from [Tickets](prompts/agents/notes/requests.md#tickets); the ticket analyst, the draft analyst and the ticket reviewer link Change tickets.
    - Acts, each with its section:
        - A solver pass's tickets: [pass-tickets](#pass-tickets).
        - Filing a ticket: [Ticket files](#ticket-files), [Ticket fields](#ticket-fields) with its part [Agent names and ids](#agent-names-and-ids), which the code reviewer and the lib reviewer inline in place of Ticket fields, and [Ticket subjects](#ticket-subjects) where no other line of its reader's documents gives its `<domain>` and `<subject>`.
        - A `performance` ticket: [performance-tickets](#performance-tickets).
        - A noticed fault: [Noticed faults](#noticed-faults).
        - Finding, moving and closing a ticket: [Tracking](#tracking) with its part [Reading and logging tickets](#reading-and-logging-tickets), which the code reviewer and the lib reviewer inline in place of Tracking.
        - A `change` ticket's fields: [Change tickets](#change-tickets).

# Ticket notes
- The statements on filing and tracking a ticket that more than one entry point inlines or links.

## pass-tickets
- What you file a ticket on is a doc line or a tool behavior that added to the pass's time or token cost, or that made its output wrong, a train pair whose output no reading reproduces, or a step that a line below has you file a `delay` ticket for; another problem in the task's own files is not one.
    - Give in that ticket the output the concept gives the pair, and judge by that output the Fit of the concept and of each branch at that pair, and the verdict of each witness on it.
- As each one happens, note it in `work/task/<task_id>/progress.md`, under a heading that is the name of this pass's report.
- When the report's other sections are settled, file a ticket for each one noted under that heading, whether or not an earlier pass hit it, with `task` as `<domain>`, the task id as `<subject>`, and your agent's name as `<agent>`.
    - Give each ticket the kind `interference` or `delay`.
    - Cite the target as a link as this rendering shows it, a step and the phrase quoted, or a command.
    - Write under `Impact` what it cost the pass, and for `interference`, what was wrong in the output and whether it still is.
- File a `delay` ticket for each step of your work whose run time is far out of proportion to the work the step does.

## Ticket files
- Where your instructions, your brief or a later message ask you to file a ticket, file it with `uv run python scripts/file_ticket.py`, in the form its `--help` gives, and, where no other line of your documents gives its `<domain>` and `<subject>`, with those that [Ticket subjects](prompts/agents/notes/tickets.md#ticket-subjects) gives.
    - Where the ticket has an `Evidence` section, write under it the line quoted, or the command and its output, or the grid, as you saw it, and leave out what the fix should be.

## performance-tickets
- File a `performance` ticket for each step of your work whose run time is far out of proportion to the work the step does.

## Noticed faults
- File a `bug` ticket on each fault you notice in a tool, a document or an agent's run, when you notice it, whether or not it lies within your work, where no other line of your documents has you fix, send, report or file it, and no ticket of any session outside `tickets/closed/` records it.

## Ticket fields
* inline: #agent-names-and-ids
- The coordinator's own agent id is the session id `echo $CLAUDE_CODE_SESSION_ID` prints.

## Agent names and ids
- `<agent>` is your agent's name, or `coordinator` where you are the coordinator.
- A subagent's own agent id is the one the line `Your agent id is <id>.` in its context gives, or, where its context holds no such line, the agent id of its own entry in the listing `uv run python scripts/profile_runs.py --running <session id>` prints, with the id `echo $CLAUDE_CODE_SESSION_ID` prints as `<session id>`: the entry whose call in flight is that listing's command.

## Ticket subjects
- `<domain>` and `<subject>` give what a ticket of another kind than `change` and `request` is about:
    - `task` and the task id: a solver pass's ticket, and a transcript review's ticket on a pass.
    - `change` and the number of the change's ticket: an editor's or a doc reviewer's ticket on its change where its brief gives that number, the ticket the agent that merges a change files on that change, and a transcript review's ticket on such an editor's run.
    - `commit` and the commit's hash: a code reviewer's or a lib reviewer's ticket, on its review's commit, and a ticket a brief has its agent file on a commit of `master` that the brief gives.
    - `ticket` and the ticket's number: a ticket on another ticket.
    - `agent` and the agent's id: every ticket no entry above fits, on the agent whose run it concerns, or, where it concerns no agent's run, the agent in whose run the fault showed, your own included.

## Tracking
* inline: #reading-and-logging-tickets
- Every session on the repository shares the ticket tracker. A ticket belongs to the session whose index its number gives before the `-`, and a ticket with a bare number belongs to no session. `uv run python scripts/file_ticket.py index` prints the index of your session.
- Take, release, move and settle only your session's tickets, those your brief or a message gives, each `change` of another session that your documents have you take or release, and each ticket a step that a merged change's ticket places at or after the merge moves.
    * comment: Trial a7255e0c2ce99edd3, the `after-merge` agent of change 6-1020, ran none of the steps its Scope places after the merge, with this line as its reason.
- A ticket under `tickets/deferred/` waits on a condition that `uv run python scripts/file_ticket.py` checks and acts on: a `delay` ticket on its group's summed loss, as `uv run python scripts/file_ticket.py case --help-all` gives, and a `validation` ticket on the check of its `## Validation` section, as `uv run python scripts/file_ticket.py --help` gives. Move no ticket into or out of `tickets/deferred/` other than by a step that a merged change's ticket places at or after the merge, or by closing a `validation` ticket whose need the user withdrew.
    * comment: Trial a7255e0c2ce99edd3, the `after-merge` agent of change 6-1020, ran none of the steps its Scope places after the merge, with this line as its reason. Trial ac04c8fcff1e01693 of the coordinator read this line as barring the closes of `request` tickets out of `tickets/deferred/` that change 9-212's Scope places at the merge.
- A ticket under `tickets/blocked/` waits on the user, and one under `tickets/waiting/` on a change, as `uv run python scripts/file_ticket.py log --help` gives. No agent holds either.
- Take a ticket with its transition to `assigned`, and leave alone each ticket whose transition the command refuses.
- Close the ticket of a place that is judged and kept with `wontfix`, and give the judgment in the note after it.

## Reading and logging tickets
- `tickets/` is in the main tree, the parent of the directory `git rev-parse --path-format=absolute --git-common-dir` prints, and in no other worktree. Git ignores it.
- Where you look for a ticket that already exists, look among every session's tickets.
- Where you read the titles of tickets, print the path and title of each with one `grep -m1 -H '^# '` call whose arguments are all those ticket files.
- The directories `tickets/draft/`, `tickets/open/`, `tickets/deferred/`, `tickets/assigned/`, `tickets/blocked/`, `tickets/waiting/` and `tickets/closed/` are a ticket's statuses, and moving its file between them is its transition. `uv run python scripts/file_ticket.py path <number>` prints the path of the ticket with that number.
- Read a ticket you do not edit with `uv run python scripts/file_ticket.py show <number> [<section> ...]`, with each section your step needs, and with none where it needs the whole ticket.
- Make each transition, and write each other line of a ticket's log, with `uv run python scripts/file_ticket.py log`, in the form its `--help` gives, with your agent's name as `<agent>`.

## Change tickets
- A ticket that asks for a change, a `change` or a `request`, takes `change` as `<domain>`, and as `<subject>` the namespace a `change`'s Scope touches most, or the one it creates, or the one a `request`'s target lies in, then two or three words, joined by `-`.
    - A namespace takes its existing name, with `-` in place of `_`: a package under `src/`, a script under `scripts/` without `.py`, `lib`, `solver-<task_id>`, `witnesses`, `handbook`, `agents`, `notes`, `tickets` or `tests`.
- Give each `change` you file or revise each front matter field that `uv run python scripts/file_ticket.py --help` gives a `change` only under a condition, where the change meets that condition, and leave the field out of it where the change does not.
- Give in the `depends-on` of each `change` you file or revise only tickets that stand outside `tickets/draft/` or were filed before it, and give there each `change` outside `tickets/closed/` that stands outside `tickets/draft/` or was filed before it and whose result its Design reads, where no chain of links leads from that change to it.
    - One ticket was filed before another where the first line of its log has the earlier time, or the same time and the number that sorts first as text.
    - A link leads from one ticket to the next where the first gives the next in its `depends-on`, or stands under `tickets/waiting/` and waits on the next, as `uv run python scripts/file_ticket.py log --help` defines that wait.
- A part of a file is the innermost section of a document, or the innermost definition in code, that holds an edited line, in a file git does not ignore, and the new sections at one place are one part.
- When you revise a ticket under `tickets/draft/`, write a log line with `draft` as its status and `revised` as its note.
