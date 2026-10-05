# Ticket notes
- The statements on filing and tracking a ticket that more than one entry point inlines or links.

## pass-tickets
- What you file a ticket on is a doc line or a tool behavior that cost the pass time or tokens, or that made its output wrong, or a step that a line below has you file a `delay` ticket for; a problem in the task's own files is not one.
- As each one happens, note it in `work/task/<task_id>/progress.md`, under a heading that is the name of this pass's report.
- When the report's other sections are settled, file a ticket for each one noted under that heading, whether or not an earlier pass hit it, with `task` as `<domain>`, the task id as `<subject>`, and your agent's name as `<agent>`.
    - Give each ticket the kind `interference` or `delay`.
    - Cite the target as a link as this rendering shows it, a step and the phrase quoted, or a command.
    - Write under `Impact` what it cost the pass, and for `interference`, what was wrong in the output and whether it still is.
- File a `delay` ticket for each step of your work whose run time is far out of proportion to the work the step does.

## Ticket files
- Where your instructions, your brief or a later message ask you to file a ticket, file it with `uv run python scripts/file_ticket.py`, in the form its `--help` gives.
    - Where the ticket has an `Evidence` section, write under it the line quoted, or the command and its output, or the grid, as you saw it, and leave out what the fix should be.

## Ticket fields
- `<agent>` is your agent's name, or `main` in the main session.
- Your agent id is the id of your own entry in the listing `uv run python scripts/profile_runs.py --running $CLAUDE_CODE_SESSION_ID` prints, the entry whose call in flight is that command.
- `<domain>` and `<subject>` give what a ticket of another kind than `change` is about:
    - `task` and the task id: a solver pass's ticket, and a transcript review's ticket on a pass.
    - `change` and the number of the change's ticket: an editor's or a doc reviewer's ticket on its change where its brief gives that number, and a transcript review's ticket on such an editor's run.
    - `commit` and the commit's hash: a code reviewer's ticket, on the commit its baseline tag names, and an operator's ticket from its After a batch, on `master` at that commit.
    - `ticket` and the ticket's number: a ticket on another ticket.
    - `agent` and the agent's id: the ticket of a supervisor's alert verifier, on the agent it checked, and every ticket no entry above fits, on the agent it concerns, your own included.

## tracking
- `tickets/` is in the main tree, the parent of the directory `git rev-parse --path-format=absolute --git-common-dir` prints, and in no other worktree. Git ignores it.
- Every session on the repository shares the ticket tracker. A ticket belongs to the session whose index its number gives before the `-`, and a ticket with a bare number belongs to no session. `uv run python scripts/file_ticket.py index` prints the index of your session.
- Take, release, move and settle only your session's tickets and those your brief or a message names.
- Where you look for a ticket that already exists, look among every session's tickets.
- The directories `tickets/draft/`, `tickets/open/`, `tickets/assigned/`, `tickets/blocked/` and `tickets/closed/` are a ticket's statuses, and moving its file between them is its transition. `uv run python scripts/file_ticket.py path <number>` prints the path of the ticket with that number.
- A ticket under `tickets/blocked/` waits on the user or on a `change`, and no agent holds it.
- Make each transition, and write each other line of a ticket's log, with `uv run python scripts/file_ticket.py log`, in the form its `--help` gives, with your agent's name as `<agent>`.
- Close the ticket of a place that is judged and kept with `wontfix`, and give the judgment in the note after it.

## change-tickets
- A `change` takes `change` as `<domain>`, and as `<subject>` the namespace its Scope touches most, or the one it creates, then two or three words, joined by `-`.
    - A namespace takes its existing name, with `-` in place of `_`: a package under `src/`, a script under `scripts/` without `.py`, `lib`, `solver-<task_id>`, `witnesses`, `handbook`, `agents`, `notes`, `tickets` or `tests`.
- When you revise a ticket under `tickets/draft/`, write a log line with `draft` as its status and `revised` as its note.
