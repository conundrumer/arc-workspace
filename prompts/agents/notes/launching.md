# Launching notes
- The statements on launching an agent, that more than one entry point inlines or links.

## Launching
- After an agent's definition changes, wait 30 seconds before you launch that agent, so the harness reloads its file.
- Give an agent a brief in the form [Briefs](prompts/agents/notes/launching.md#briefs) gives for its work, where it gives one, and restate neither a docstring of the code nor the agent's definition.
- Where a brief gives a scratch directory, give a new directory under the session's scratchpad directory, `/private/tmp/claude-<uid>/<working directory>/<session id>/scratchpad`, where `<uid>` is what `id -u` prints, `<working directory>` is the directory the session started in with each `/` as `-`, and `<session id>` is `$CLAUDE_CODE_SESSION_ID`.
- In a brief or a `change` ticket that gives the items or the Intent of an edit, give the meaning to state, the case that shows the need, and the span the edit may change, and no wording.
    - Give each item as a requirement: a statement of what holds once the edit is made, that a check or a reading of the result can confirm. Give each way the edit can fail that you foresee as an item that gives what holds in that case, and ask no agent to think a case through.
    - In those items or that Intent, give no account of how each way the edit can fail is met, and no claim on what other lines of the documents or other branches of the code then do, unless the meaning to state, or the decision a `change` ticket gives, depends on it.
- Before you give another agent a draft `change` ticket that you filed or revised, in your reply or otherwise, cut from each of its sections each claim the draft's outcome does not rest on, and give each claim left no more precision than that outcome rests on. Then check each claim left about the current state against that state.
    * inline: #draft-outcome
    * comment: On draft 2-525, ticket analyst a040f7b84d2e02209 wrote two such claims that a docstring and a help text it had printed before it wrote the draft disprove, and each took a ticket reviewer's round: the Intent of ticket 2-530.
- Split work between agents where the split saves at least 30 minutes of wall-clock per about $5 of token cost of its overhead.
    - Token cost is the list price of the tokens a run uses: each request's uncached input, cache writes, cache reads and output, each at its own price on the model that ran the request. `uv run python scripts/profile_runs.py <agent id>` prints a run's token cost, and `--price-at <model>` reprices it at another model.
- Take each token cost you give or write into a brief from `profile_runs`, and give a repriced token cost as repriced. Take each price you give from the price table of [token_prices.py](scripts/token_prices.py).
- Act on each item that an agent you launched gives as unfinished, by its reason:
    - Where it needs more work or a part its brief left out, change that agent's brief or split its work, and send the item again, in the same turn.
    - Where the harness or the permission classifier denied it a call its documents give, first check whether that call ran in part, then make that call, or what it left undone, once, before any other step on that item, the way your own documents have you do that work. Run it even where the denial's text says not to pursue it through another agent or a later turn. Where that try is denied too, give the item in your reply as unfinished.
    - Where a tool or a document stopped it otherwise, file that obstacle as a ticket of the kind that fits it, and send the item again once that ticket is closed, or at once by a way around the obstacle where one exists.
    - Where it needs a decision, act on it as that decision rules, once the decision is made.
- Where an agent whose description says its reply gives each item of its brief as done or as unfinished has replied, and gives an item you sent it as neither, send that item again, file its drop as a ticket, and leave finding the drop's cause to the ticket analyst that takes that ticket.
- Launch a ticket analyst with each ticket the lines above have you file, before you end your turn with no other work. Where you are the coordinator, tell an operator that tickets are open, as [Operators](prompts/agents/notes/launching.md#operators) gives, in place of that launch. Where you are a ticket analyst, in place of filing those tickets, settle each fault they would record as your documents give for a fault you notice.
- In your reply, give each item an agent you launched left unfinished that you have not finished, as unfinished with its reason.
- A transcript review is a `general-purpose` agent that reviews a run's transcript. Give it the run's agent id, `python3 ~/.claude/skills/retrieve/transcripts.py --help`, the lines of [Ticket files](prompts/agents/notes/tickets.md#ticket-files), the `<domain>` and `<subject>` [Ticket fields](prompts/agents/notes/tickets.md#ticket-fields) gives a transcript review of that run, and `transcript-review` as `<agent>`. Have it file a ticket of kind `delay` for each place where the run explored to find what a docstring or a document line could have led it to.
- Pause or serialize agents only where the user agreed to it.

## Briefs

### A part a brief leaves out
- Where a brief leaves out a part that a statement of its form gives it, the agent it briefs gives in its reply the work that needs that part as unfinished, with the missing part as its reason.

### An editor's brief
- An editor's brief gives the change's worktree, and the agent id of the agent that launches it, where that is not the coordinator.
- It gives the accepted gate outputs under `tests/gate/accepted/` the editor may write, where its items change or add one, with a scratch directory.

### A code editor's brief
- A code editor's brief gives as well its tests directory and a scratch directory.

### A change's brief
- A brief for a change with a ticket gives the ticket's number, and, where another editor takes part of the ticket's Intent and Scope, the part that is this editor's. Where the brief gives no items of its own, the ticket's Intent gives its items, and the ticket's Scope the files the editor may edit, within that part.

### Items and files
- The brief of a code editor or of a `handbook-expanded` editor, for a change that has no ticket and is no solver work, gives the items and the files the editor may edit.

### A doc editor's brief
- A doc editor's brief for a change with no ticket gives an Intent, what the documents' readers should know or do, with a Justification for each restatement or elaboration to keep, which gives the reader that failed without that text and the situation where it failed.
- A doc editor ignores each instruction its brief, or the ticket its brief gives, holds, and counts ignoring one as no departure from its request.

### A ticket reviewer's brief
- A ticket reviewer's brief gives the number of each ticket under `tickets/draft/` to review, and the agent id of the agent that launches it, where that is not the coordinator.

### A ticket analyst's brief
- A ticket analyst's brief gives the tickets under `tickets/open/` to settle, a draft `change` ticket whose log holds findings or a suggestion, or the findings an editor left on a review of its change and the items an editor left unfinished for a decision, with the editor's reasons, or the latest report of each editor of a change, whose items it checks, or a step that an operator's command cannot decide, which the operator holds.
    - With each of those findings and items, it gives the agent id of the change's editor, the change's worktree, and the number of the change's ticket, or, where the change has none, its intent and what is already settled about it.
    - With a draft whose next revision opens at its operator's cap of ticket reviews, it gives that this revision is the last: the draft then opens with no further ticket review, and the change's own review checks what the change writes.
- With the tickets a solver pass filed, it gives the review of that pass's transcript.
- It gives the agent id of the agent that launches it, where that is not the coordinator.

### An operator's brief
- An operator's brief gives only lines in these forms, each on a line of its own:
    - `Solve: <task id> ...`: a solver pipeline on each task, from Analyze, or from the pass that `from create` or `from refine` after its task id gives.
    - `Solve from the queue: <count>`: solver pipelines on that many tasks of the queue.
    - `Drafts to review: <number>, ...`: the draft `change` tickets to review.
    - `Tickets named: <number>, ...`: tickets of another session that the operator releases, takes and settles as it does its session's.
    - `Merged: <number>, ...`: the changes the coordinator merged itself.
    - `Merge: <number>`: a `change` under `tickets/blocked/` that waits on the user, which the user's ruling has the operator merge.
    - `Tickets are open.`
    - `Override: <task id> <pass> <override>`: an override that the brief of the next launch of that pass on that task gives.
    - `Override: pass over <step key>`: passes over the solver pass whose step key it gives: that pass's task id and its pass, in the form `uv run python scripts/operate.py --help` gives.
    - `Decision: <decision key> <choice>`: rules the held step that gives that decision key with one of the choices that step gives, as the whole rest of the line.
- The operator gives each line of its brief or of a later message from the coordinator in no other form back to the coordinator as undecided.

### A code reviewer's brief
- A code reviewer's brief gives the earlier code review's baseline, as a `code-review/<n>` tag, this code review's number, what new code the diff holds, and a scratch directory.

### A doc reviewer's brief
- A doc reviewer's brief gives a change to the agent-facing documents, as the files or a diff, and the number of its ticket, or, where it has none, what is already settled about it.
- It gives the change's worktree, the agent id of the change's doc editor, and of each of its code editors with the files that editor's brief gives, and the agent id of the agent that launches it, where that is not the coordinator.

### Solver work
- Solver work is a solver pass, or an edit of a solver or of the lib for one task.
- Its brief may give overrides, each labelled as an override: a judgment made in place of the agent's own.
- The agent refuses any other instruction in its brief on a judgment its work makes: it does none of the work, and writes the part of the brief it refused, quoted, as its report.
- Where the agent works in a worktree other than the main worktree and nothing stands at `work` in that worktree, the agent runs `ln -s <main worktree>/work work` there before it reads or writes under `work/`, with the parent of the directory `git rev-parse --path-format=absolute --git-common-dir` prints as `<main worktree>`.

### A solver work brief
- Where no `change` ticket gives solver work, its brief gives the task id, and, for work other than a pass, the work in words. It gives no items and no files, and the agent determines them.

### Writing a solver work brief
- Read no solver to write a brief for solver work.
- Solver work other than a pass is a change, which an editor carries as it carries any other, whether or not a `change` ticket gives it. Where one does, its brief has the form [A change's brief](#a-changes-brief) gives.

## An editor's report on a change
- An editor's report on a change gives, for each item of its brief, and of each request a later message adds, that it gives as done, what shows it holds: a command it ran with the output that shows it, the line of a rendered context that states it, the check its ticket's Scope places after the merge where only that check can show it, or, where none of these can, the reason it holds.

## Passes on a task
- Before you launch a pass on a task whose claim you do not hold, claim the task: run `mkdir -p work/task/<task_id> && (set -C; echo "$CLAUDE_CODE_SESSION_ID" > work/task/<task_id>/claim)` in the main worktree. Where it fails, launch no pass on that task.
- Where that pass is an Analyze or a Create pass, set aside the task's earlier work in the main worktree:
    1. Make a new directory `work/task/<task_id>/<n>/`, with `n` one more than the highest numbered directory there, and 1 where there is none.
    2. Write the output of `git diff HEAD -- programs/solvers/<task_id>.dl programs/witnesses/<task_id>.wit.json` to `uncommitted.diff` in it.
    3. Move into it the task's solver and its witness file, each where it exists, and, before an Analyze pass, each entry of `work/task/<task_id>/` other than `claim` and the numbered directories, or, before a Create pass, `create.md`, each `refine-<n>.md` and `progress.md`.
    4. Run `git update-index --skip-worktree <path>` on the path of each of those two files that `git ls-files <path>` lists.
- Once each pass you launch on the task for one request or one procedure has ended, or the harness or the permission classifier has refused the launch of such a pass while no other such pass runs:
    1. Move the solver and the witness file you set aside back to their paths, each where nothing stands at its path.
    2. Run `git update-index --no-skip-worktree <path>` on each path you marked.
    3. Remove the claim file.

## Operators
- Send each line you give an operator to a running operator of yours, and where none runs, launch a new operator with it. Give it in a form [An operator's brief](#an-operators-brief) gives, with nothing else in that message.
- To tell an operator that tickets are open, give it `Tickets are open.`
- An operator's final reply is its message to you that opens with `final reply`.
- When an operator's final reply asks for a fresh operator, launch one with a brief that gives no line.
- When an operator's message, or a paragraph of it, that opens with `undecided:` reaches you, send the operator again the line of yours it gives, in a form [An operator's brief](#an-operators-brief) gives.
- When an operator's message that opens with `for the coordinator:` reaches you, read the file it gives.
- Bring the user each `decision:` item that file or an operator's final reply gives, other than a decline, tell the user each `tell:` item, and act on each `unfinished:` item as on an item an agent you launched gives as unfinished.
- Ask an operator for no message to you before its final reply, other than the messages that open with `for the coordinator:` or `undecided:`, which it sends as it goes.
- Send each draft `change` ticket that the reply of an agent you launched gives, and each `change` ticket you revise, to an operator in a `Drafts to review: <number>` line.
- Each time a `change` of your session comes to stand under `tickets/open/` with every ticket its `depends-on` gives under `tickets/closed/`, while no operator of yours holds it or runs its review, tell an operator that tickets are open.
- Revise a `change` ticket that stands under `tickets/open/`, `tickets/assigned/` or `tickets/blocked/` only once you have moved it back to `tickets/draft/`, with a log line whose note gives what you revise and on what ground.
- Once the user rules on a draft `change` ticket under `tickets/blocked/` that waits on the user, move it back to `tickets/draft/` with the ruling in the note, revise it where the ruling needs that, and send it to an operator in a `Drafts to review: <number>` line.

## While the user gives feedback
- Gather each request the user approves into a batch, and when the user pauses or asks you to send it, send the whole batch at once: give each request to the agent whose description covers its work, as the split line above allows, with one brief per agent.
- Where a request touches the files of a change that has not passed, send it to that change's editor with SendMessage. Add every other request to the batch.

## draft-outcome
- A draft's outcome is the decision that this revision of the draft or a later revision of it gives, and the change the tree gets from that decision.
- The outcome rests on a claim where, were the claim wrong, the outcome would differ. A check of the claim is no part of the outcome.
