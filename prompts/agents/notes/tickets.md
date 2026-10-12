# Ticket notes
- The statements on filing and tracking a ticket that more than one entry point inlines or links.

## pass-tickets
- What you file a ticket on is a doc line or a tool behavior that added to the pass's time or token cost, or that made its output wrong, or a step that a line below has you file a `delay` ticket for; a problem in the task's own files is not one.
- As each one happens, note it in `work/task/<task_id>/progress.md`, under a heading that is the name of this pass's report.
- When the report's other sections are settled, file a ticket for each one noted under that heading, whether or not an earlier pass hit it, with `task` as `<domain>`, the task id as `<subject>`, and your agent's name as `<agent>`.
    - Give each ticket the kind `interference` or `delay`.
    - Cite the target as a link as this rendering shows it, a step and the phrase quoted, or a command.
    - Write under `Impact` what it cost the pass, and for `interference`, what was wrong in the output and whether it still is.
- File a `delay` ticket for each step of your work whose run time is far out of proportion to the work the step does.

## Ticket files
- Where your instructions, your brief or a later message ask you to file a ticket, file it with `uv run python scripts/file_ticket.py`, in the form its `--help` gives.
    - Where the ticket has an `Evidence` section, write under it the line quoted, or the command and its output, or the grid, as you saw it, and leave out what the fix should be.

## Noticed faults
- File a `bug` ticket on each fault you notice in a tool, a document or an agent's run, when you notice it, whether or not it lies within your work, where no other line of your documents has you fix, send, report or file it, and no ticket of any session outside `tickets/closed/` records it.

## Ticket fields
- `<agent>` is your agent's name, or `coordinator` where you are the coordinator.
- `<domain>` and `<subject>` give what a ticket of another kind than `change` and `request` is about:
    - `task` and the task id: a solver pass's ticket, and a transcript review's ticket on a pass.
    - `change` and the number of the change's ticket: an editor's or a doc reviewer's ticket on its change where its brief gives that number, the ticket the agent that merges a change files on that change, and a transcript review's ticket on such an editor's run.
    - `commit` and the commit's hash: a code reviewer's ticket, on the commit its baseline tag gives, and a ticket a brief has its agent file on a commit of `master` that the brief gives.
    - `ticket` and the ticket's number: a ticket on another ticket.
    - `agent` and the agent's id: every ticket no entry above fits, on the agent whose run it concerns, or, where it concerns no agent's run, the agent in whose run the fault showed, your own included.
- A subagent's own agent id is the one the line `Your agent id is <id>.` in its context gives, or, where its context holds no such line, the agent id of its own entry in the listing `uv run python scripts/profile_runs.py --running <session id>` prints, with the id `echo $CLAUDE_CODE_SESSION_ID` prints as `<session id>`: the entry whose call in flight is that listing's command.
- The coordinator's own agent id is the session id `echo $CLAUDE_CODE_SESSION_ID` prints.

## Tracking
- `tickets/` is in the main tree, the parent of the directory `git rev-parse --path-format=absolute --git-common-dir` prints, and in no other worktree. Git ignores it.
- Every session on the repository shares the ticket tracker. A ticket belongs to the session whose index its number gives before the `-`, and a ticket with a bare number belongs to no session. `uv run python scripts/file_ticket.py index` prints the index of your session.
- Take, release, move and settle only your session's tickets, those your brief or a message gives, and each `change` of another session that your documents have you take or release.
- Where you look for a ticket that already exists, look among every session's tickets.
- Where you read the titles of tickets, print the path and title of each with one `grep -m1 -H '^# '` call whose arguments are all those ticket files.
- The directories `tickets/draft/`, `tickets/open/`, `tickets/watching/`, `tickets/assigned/`, `tickets/blocked/` and `tickets/closed/` are a ticket's statuses, and moving its file between them is its transition. `uv run python scripts/file_ticket.py path <number>` prints the path of the ticket with that number.
- Read a ticket you do not edit with `uv run python scripts/file_ticket.py show <number> [<section> ...]`, with each section your step needs, and with none where it needs the whole ticket.
- A ticket under `tickets/watching/` is a `delay` ticket whose summed loss is below what its fix costs. `uv run python scripts/file_ticket.py` files it there and appends its cases, and moves it to `tickets/open/` once that loss reaches that cost or an appended case leaves either unknown, and, where a filing would put one more ticket there than that directory's cap, which `uv run python scripts/file_ticket.py case --help-all` gives, first closes `wontfix` the one there with the lowest loss rate. Move no ticket into or out of `tickets/watching/`.
- A ticket under `tickets/blocked/` waits on what the last line of its log whose note opens with a wait gives, as `uv run python scripts/file_ticket.py log --help` defines that wait, and no agent holds it.
- Make each transition, and write each other line of a ticket's log, with `uv run python scripts/file_ticket.py log`, in the form its `--help` gives, with your agent's name as `<agent>`.
- Take a ticket with its transition to `assigned`, and leave alone each ticket whose transition the command refuses.
- Close the ticket of a place that is judged and kept with `wontfix`, and give the judgment in the note after it.

## Change tickets
- A ticket that asks for a change, a `change` or a `request`, takes `change` as `<domain>`, and as `<subject>` the namespace a `change`'s Scope touches most, or the one it creates, or the one a `request`'s target lies in, then two or three words, joined by `-`.
    - A namespace takes its existing name, with `-` in place of `_`: a package under `src/`, a script under `scripts/` without `.py`, `lib`, `solver-<task_id>`, `witnesses`, `handbook`, `agents`, `notes`, `tickets` or `tests`.
- Give each `change` you file or revise the `mechanical` field where its Intent meets the condition `uv run python scripts/file_ticket.py --help` gives for that field, and leave the field out of it where its Intent does not.
- Give in the `depends-on` of each `change` you file or revise only tickets that stand outside `tickets/draft/` or were filed before it, and give there each `change` outside `tickets/closed/` that stands outside `tickets/draft/` or was filed before it and whose result its Design reads, or that edits a part of a file its Scope edits and does not stand under `tickets/blocked/` waiting on the user, where no chain of links leads from that change to it.
    - A part is the innermost section of a document, or the innermost definition in code, that holds an edited line, in a file git does not ignore, and the new sections at one place are one part.
    - One ticket was filed before another where the first line of its log has the earlier time, or the same time and the number that sorts first as text.
    - A link leads from one ticket to the next where the first gives the next in its `depends-on`, or stands under `tickets/blocked/` and waits on the next, as `uv run python scripts/file_ticket.py log --help` defines that wait.
- When you revise a ticket under `tickets/draft/`, write a log line with `draft` as its status and `revised` as its note.
