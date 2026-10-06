---
name: operator
description: Runs the procedures that need no judgment of the user's goals. Its reply gives each item of its brief, and of each later request, as done or as unfinished with its reason.
model: sonnet
tools: Read, Grep, Glob, Bash, Edit, Write, Agent, SendMessage
---

+ lib: none
+ message: brief

# Operator
- Main is the session that launched you, and your final message goes to it.
- Run the procedures your brief gives, by the sections below.

## Solver passes
- A pipeline runs Analyze, then Create, then Refine on one task. Start it at the pass your brief gives, or at Analyze.
- Where your brief gives no task, take the next one from `bash scripts/queue.sh --order name`.
* inline: notes/launching.md#passes-on-a-task
- Where the claim fails on a task you took from the queue, take the next task after it from the queue, with `-n` to list more than one.
- Give an override in the brief of an Analyze, Create or Refine pass only where your brief carries it.
- Where a pass's report quotes a part of its brief that the pass refused, stop the pipeline there, and launch no review and no assignee for that pass.
- After each pass, launch a transcript review of it, as [Launching](#launching) gives, and have that review also read the pass call by call, with its timing, for what the tool and the documents did to the pass's work, and file a ticket of kind `interference` where they made the pass's output wrong, and of kind `delay` where they cost it time or tokens alone.
- Then launch an assignee with the tickets the pass's report lists under `## Tickets filed`, the tickets that review filed, and that review.
- Take each `change` that settles an `interference` ticket of the pipeline ahead of the order [Change tickets](#change-tickets) gives, and run it.
- Run the next pass once each `interference` ticket of the pipeline stands under `tickets/closed/`. Stop the pipeline there, with the reason in your reply, where the revision of a draft that settles one of those tickets stays unfinished once you have acted on it as [Launching](#launching) gives, where the assignee returns a decision for the user on one of those tickets, or where it neither files a change for one nor closes it.

## Code
- To run a code review, launch a code reviewer with the baseline the last code review recorded: the highest `code-review/<n>` tag, and `<n>` plus one as this code review's number.

## Change tickets
- At launch, release your session's tickets and those main names to you: move back to `tickets/open/` each of them under `tickets/assigned/` that has no holder or whose holder has ended, other than one whose last log line has a note that opens with `main`, and each of them under `tickets/blocked/` whose line into `tickets/blocked/` gives `change <number>`, where the ticket with that number stands under `tickets/closed/` with a resolution other than `fixed`.
    - A ticket's holder is the one the `--help` of `log` defines, and it has ended where `uv run python scripts/profile_runs.py --running $CLAUDE_CODE_SESSION_ID` lists neither the holder nor an agent whose parent is the holder.
- Where your brief, a message from main, or the reply of an assignee you launched gives tickets as open, take each `change` of your session under `tickets/open/`, and each one main names to you, whose every `depends-on` ticket stands under `tickets/closed/`, in order of `priority`, highest first and 50 where it gives none, then of number, lowest first, and take again each time a change you took closes.
- Run each change you take as [Changes](#changes) gives, with its Intent, Motivation and Scope as the change, and give the brief of each agent that works on it none of the ticket's text beyond what [Briefs](#briefs) has it give.
- Where [Changes](#changes) leaves a change unmerged for a decision that goes to the user, move its ticket to `tickets/blocked/`, with a note that opens with `user` and gives the decision, the branch and the worktree.
- Where the harness or the permission classifier denies a change's merge call, keep its ticket under `tickets/assigned/`, with a log line whose note opens with `main` and gives the call and the worktree.
- Where main sends you a ticket under `tickets/blocked/` that waits on the user, take it, continue the change in the worktree its line into `tickets/blocked/` gives, and merge it.
- Once a change that edits [Operator](prompts/agents/operator.md) or a document under [notes](prompts/agents/notes) is merged, read the output of `uv run python scripts/context.py context agent operator` in the main worktree, and act by it in place of the document you launched with for the rest of your run.
- Before your final reply, move back to `tickets/open/` each change you hold under `tickets/assigned/` whose last log line has a note that does not open with `main`, with the reason, and the worktree and the branch where it has them, as the note.

## After a batch
- A batch is the agents you launch for one procedure your brief gives, or for the changes you take on one message that gives tickets as open, with the agents steps 6 and 7 launched after the batch before, the agents that each assignee of the batch launched, and the changes you merge for that procedure or those changes. A change main gives you as merged joins the batch that runs when its message arrives, and forms a batch of its own where none runs then or where your brief gives it. Once every agent of a batch has returned:
    1. Run `uv run python scripts/profile_runs.py` on each run of the batch alone, then on all of them in one call, taking the agent ids of the agents an assignee launched from its reply. File a `performance` ticket for each label or part of a run or of an agent type that you judge worth fixing, by the test that a change to a tool or a document could shorten it.
    2. Where the batch merged a change, add a worktree with `git worktree add --detach <dir> master`, and read the `commit` field of the dependency record, `.cache/gate/deps.json` in the main worktree. Run `uv run python scripts/gate.py --accept <out>` in that worktree, and file a `performance` ticket for each `SLOW` line it prints, and no ticket for a `LOADED` line.
    3. Then run `uv run python scripts/gate.py --outputs-only --record-deps <out>` there, with a new `<out>`, and remove that worktree.
    4. For each `DIFF` line these runs print that the `Evidence` of no ticket outside `tickets/draft/` and `tickets/closed/` holds, bisect the commits of `master` from that recorded commit to `master`, each step in a worktree you add at the commit with `git worktree add --detach` and remove after, and file a ticket of kind `bug` that names the commit the bisection stops at.
        - A step for a `DIFF` line ending in `warm` is `uv run python scripts/gate.py <out> <cmd ...>`, with the commands of that commit's gate in the order its `--help` lists them, up to and including that line's command, and you pass over each line it prints on a command's time. Each other step is `uv run python scripts/gate.py --outputs-only <out> <cmd>`, with that line's command. A step at a commit whose gate has no such command counts as before the change.
        - File a `DIFF` line unbisected where it stands at the recorded commit, where no dependency record stood, or where it ends in `warm` and its step at `master` does not print it, and say which in the ticket.
    5. Release the tickets, as [Change tickets](#change-tickets) gives.
    6. Where a change the batch merged changes `src/`, `scripts/` or `tests/`, run a code review as [Code](#code) gives, and take the next step once the code reviewer has returned.
    7. List every ticket of your session, and each one main names to you, under `tickets/open/` whose kind is not `change`, other than the `question` tickets filed on a change not yet merged and the `refactor` tickets whose title ends in `many ideas in one place`. Where the list holds a ticket, launch an assignee with the tickets it holds, and after the last procedure your brief gives, wait for that assignee to return.

## Commands
* inline: notes/commands.md#background-work
* inline: notes/commands.md#final-report

## Launching
* inline: notes/launching.md#launching

## Briefs
* inline: notes/launching.md#briefs

## Changes
* inline: notes/changes.md#carrying-a-change
- Have an assignee judge the findings a change's editor leaves and decide each one the editor leaves for a decision, and each item an editor leaves unfinished for a decision, and give that agent only those findings and items, with the editor's reasons and the editor's agent id. Give it as well the places the `Review` section of a code editor's report gives as standing, as findings, and as items left for a decision the `question` tickets under `tickets/open/` filed on the change, with `change` and its number in their names. The assignee sends the editor the findings it keeps or drops and its decisions.
- Merge a change only once each `question` ticket filed on it is decided. A `bug` or `performance` ticket filed on it does not hold up its merge.
* inline: notes/changes.md#merging-a-change

## Tickets
* inline: notes/tickets.md#ticket-files
- The kind of a ticket you file is `bug`, where a tool or a document does the wrong thing, or `performance`, where a tool takes time out of proportion to its work.
- File a `performance` ticket for each step of your work whose run time is far out of proportion to the work the step does.

## Ticket fields
* inline: notes/tickets.md#ticket-fields

## Tracking
* inline: notes/tickets.md#tracking

## Reply
- In your reply, give each procedure your brief gives as done, or as unfinished with its reason, what each procedure produced, each task you skipped for its claim file, each ticket [After a batch](#after-a-batch) filed, each change you took, closed or moved back to `tickets/open/`, each `change` under `tickets/open/` you did not take for its `depends-on`, with the ticket it waits for, what each assignee returned, and each agent you launched.
