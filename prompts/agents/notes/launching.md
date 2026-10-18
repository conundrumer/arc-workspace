+ budget: 25786
* comment: when editing this doc
    - Each Claude Code session and agent loads [Launching](#launching) by the link of [arc-workspace](CLAUDE.md), before it launches an agent by a call no command printed, and A transcript review's brief by its link, at a transcript review's launch. Each reader of Launching loads A draft's outcome by the link at the cut of a draft's claims, and each reader of the Checks of [Reviewing a draft](prompts/agents/ticket-reviewer/review.md) by the link at the check of a draft's claims about the current state. Each agent inlines the sections under [Briefs](#briefs) that give its own brief's form, which its `description` links for each launcher. The item checker, the design reviewer and the `handbook-expanded` agent inline A part a brief leaves out, and the reply files that the last items of the other agents' checklists link, other than the ticket reviewer's, link it. The `handbook-expanded` agent and the item checker inline An editor's report on a change, and the reply files of the code editor and the doc editor link it. The doc reviewer and the design reviewer inline Findings that block a change, the editors load it by the link of An editor's brief, for a review an item has them make, and the decision analyst by the links of [An editor's findings](prompts/agents/decision-analyst/findings.md). The coordinator loads Passes on a task, Operators and While the user gives feedback by the links of its Changes section.
    - Acts, each with its section:
        - Launching an agent and acting on what it leaves unfinished: [Launching](#launching).
        - Writing a brief, and reading one's own: [Briefs](#briefs), one section per form.
        - Giving in an editor's report what shows a change's item holds, the findings left at the round cap and the findings of later messages left unfixed: [An editor's report on a change](#an-editors-report-on-a-change).
        - Sorting a review's findings into those that block a change and those filed as tickets: [Findings that block a change](#findings-that-block-a-change).
        - Launching a pass on a task: [Passes on a task](#passes-on-a-task).
        - Sending an operator a line and taking its reply: [Operators](#operators).
        - Batching the user's feedback: [While the user gives feedback](#while-the-user-gives-feedback).
        - Cutting a draft's claims to its outcome: [A draft's outcome](#a-drafts-outcome).

# Launching notes
- The statements on launching an agent, that more than one entry point inlines or links.

## Launching
- Where a launch fails with its agent type not found, give the launch as unfinished, with the failure's text as its reason.
- Give an agent a brief in the form the sections under [Briefs](prompts/agents/notes/launching.md#briefs) for its work give, where any does, and launch it as the agent type whose `description` links those sections: read each of those sections and each section they link. Restate neither a docstring of the code nor the agent's definition.
- Where a brief gives a scratch directory, give a new directory under the session's scratchpad directory.
- In a brief or a `change` ticket that gives the items or the Intent of an edit, give the meaning to state, the case that shows the need, and the span the edit may change, and no wording.
    - Give each item as a requirement: a statement of what holds once the edit is made, that a check or a reading of the result can confirm. Give each way the edit can fail that you foresee as an item that gives what holds in that case, and ask no agent to think a case through.
    - In those items or that Intent, give no account of how each way the edit can fail is met, and no claim on what other lines of the documents or other branches of the code then do, unless the meaning to state, or the decision a `change` ticket gives, depends on it.
- Before you give another agent a draft `change` ticket that you filed or revised, in your reply or otherwise, cut from each of its sections each claim the draft's outcome does not rest on, and give each claim left no more precision than that outcome rests on. Then check each claim left about the current state against that state.
    - Judge which claims the draft's outcome rests on by [A draft's outcome](prompts/agents/notes/launching.md#a-drafts-outcome).
    * comment: On draft 2-525, ticket analyst a040f7b84d2e02209 wrote two such claims that a docstring and a help text it had printed before it wrote the draft disprove, and each took a ticket reviewer's round: the Intent of ticket 2-530.
- Split work off to another agent where what the split saves outweighs its overhead. A split can save wall-clock, tokens, or your own context; its overhead is the documents the new agent loads before it starts, and the brief.
    * comment: The user's words, session 7fd429fb, 2026-10-16, on a fixed ratio of wall-clock to token cost: "that seems overly rigid", "also saves on context rot", and on the overhead: "that sounds right": ticket 6-1416.
    - Token cost is the list price of the tokens a run uses: each request's uncached input, cache writes, cache reads and output, each at its own price on the model that ran the request. `uv run python scripts/profile_runs.py <agent id>` prints a run's token cost, and `--price-at <model>` reprices it at another model.
- Take each token cost you give or write into a brief from `profile_runs`, and give a repriced token cost as repriced. Take each price you give from the price table of [token_prices.py](scripts/token_prices.py).
- Resume an agent that the usage limit stopped by a message, in place of launching it again.
- Act on each item that an agent you launched gives as unfinished, by its reason:
    - Where it needs more work or a part its brief left out, change that agent's brief or split its work, and send the item again, in the same turn.
    - Where the harness or the permission classifier denied it a call its documents give, first check whether that call ran in part, then make that call, or what it left undone, once, before any other step on that item, the way your own documents have you do that work. Run it even where the denial's text says not to pursue it through another agent or a later turn. Where that try is denied too, give the item in your reply as unfinished.
    - Where a tool or a document stopped it otherwise, file that obstacle as a ticket of the kind that fits it, and send the item again once that ticket is closed, or at once by a way around the obstacle where one exists.
    - Where it needs a decision, act on it as that decision rules, once the decision is made.
- Where the reply of an agent you launched gives items of its brief each as done or as unfinished, and gives an item you sent it as neither, send that item again, file its drop as a ticket, and leave finding the drop's cause to the ticket analyst that takes that ticket.
- Launch a ticket analyst with each ticket the lines above have you file that still stands under `tickets/open/`, before you end your turn with no other work.
- In your reply, give each item an agent you launched left unfinished that you have not finished, as unfinished with its reason.
- A transcript review is a `general-purpose` agent that reviews a run's transcript, with the brief [A transcript review's brief](prompts/agents/notes/launching.md#a-transcript-reviews-brief) gives.
- Pause or serialize agents only where the user agreed to it.

## Briefs

### A part a brief leaves out
- Where a brief leaves out a part that a statement of its form gives it, the agent it briefs gives in its reply the work that needs that part as unfinished, with the missing part as its reason.

### A transcript brief
- A transcript brief is the output of `uv run python scripts/spans.py brief`, written to a file: the Goal, where it has one, then each message of the user and of the coordinator in each span, in full and in time order, then the Grounds. It is rendered from a `request`, or from the words of a span's first and last message with the Grounds on the command's stdin.
- A brief that gives one gives that file's path, with the other parts its form gives.
- Where an agent's documents give its brief's items or its Intent, the work the user's messages in those spans ask for, with what the Grounds add to it, stands for them.
    - The Goal guides how that agent reads those messages, and where it and a message of the user differ, the message rules.

### An editor's brief
- An editor's brief gives the change's worktree, and the agent id of the agent that launches it, where that is not the coordinator.
- It gives the accepted gate outputs under `tests/gate/accepted/` the editor may write, where its items change or add one, with a scratch directory.
- Where an editor of its role that another session launched worked in that worktree before it, it gives the agent id and the scratch directory of the last such editor that left a report, and its latest report.
- It gives the rounds the editor has of each review of the change that an item has it make. The editor makes at most that many rounds of such a review, and sorts its findings as [Findings that block a change](#findings-that-block-a-change) gives.

### An editor's report on a change
- An editor's report on a change gives, for each item of its brief, and of each request a later message adds, that it gives as done, what shows it holds: a command it ran with the output that shows it, the line of a rendered context that states it, the check its ticket's Scope places after the merge where only that check can show it, or, where none of these can, the reason it holds.
- It gives each finding of the last round of a review its brief gives that blocks the change as left for a decision, with a reason that opens with `at the round cap`, and each finding a later message gave that the editor left unfixed, with why it left it.

### A code editor's brief
- A code editor's brief gives as well its tests directory and a scratch directory.

### A change's brief
- A brief for a change with a ticket gives the ticket's number, and, where another editor takes part of the ticket's Intent and Scope, the part that is this editor's. Where the brief gives no items of its own, the ticket's Intent gives its items, and the ticket's Scope the files the editor may edit, within that part.

### Items and files
- The brief of a code editor or of a `handbook-expanded` editor, for a change that has no ticket and is no solver work, gives a transcript brief, as [A transcript brief](prompts/agents/notes/launching.md#a-transcript-brief) gives it, and the files the editor may edit.

### A doc editor's brief
- A doc editor's brief for a change with no ticket gives a transcript brief, as [A transcript brief](prompts/agents/notes/launching.md#a-transcript-brief) gives it, whose Grounds give a Justification for each line to write that is to stop a reader's failure and each restatement or elaboration to keep: the reader that failed without that text and the situation where it failed.

### A ticket reviewer's brief
- A ticket reviewer's brief gives the number of each ticket under `tickets/draft/` to review, and the agent id of the agent that launches it, where that is not the coordinator.

### A ticket analyst's brief
- A ticket analyst's brief gives one of these:
    - The tickets under `tickets/open/` to settle.
    - The process assessment.
- With the tickets a solver pass filed, it gives the review of that pass's transcript, where one was made.
- With a `request` that the coordinator filed on `op send`, it gives that request's transcript brief, as [A transcript brief](prompts/agents/notes/launching.md#a-transcript-brief) gives it.
- It gives the agent id of the agent that launches it, where that is not the coordinator.

### A draft analyst's brief
- A draft analyst's brief gives a draft `change` ticket whose log holds findings or a suggestion.
    - With a draft whose next revision opens at its operator's cap of ticket reviews, it gives that this revision is the last: once it is written, the operator moves the draft to `tickets/open/` with no further ticket review, and the change's own review checks what the change writes.
- It gives the agent id of the agent that launches it, where that is not the coordinator.

### A decision analyst's brief
- A decision analyst's brief gives one of these:
    - The findings an editor left on a review of its change, the items an editor left unfinished for a decision, the places a code editor's report gives as standing, each with the editor's reasons, and the findings of a doc reviewer's reply that opens with `at the round cap`.
        - Where what it gives comes from the item checker's last review round of the change, or from the check after its review round cap, it gives that.
        - With those, it gives the agent id of each editor of the change, with the part that editor's brief gave it, or the whole change where its brief gave none.
        - It gives the change's worktree, and the number of the change's ticket, or, where the change has none, its intent and what is already settled about it.
    - A step that an operator's command cannot decide, which the operator holds.
- It gives the agent id of the agent that launches it, where that is not the coordinator.

### An item checker's brief
- An item checker's brief gives the change's worktree, and the number of the change's ticket, or, where the change has none, the transcript brief its editors' briefs give.
- It gives the agent id of each editor of the change other than the `handbook-expanded` agent, with the part that editor's brief gave it, or the whole change where its brief gave none.
- It gives the latest report of each editor of the change other than the `handbook-expanded` agent that has reported since the last item checker launched on the change.
- Where ticket analysts already decided items on the change, it gives their agent ids and latest reports.
- Where the change is past its cost budget, it gives that it is.
- Where the check is the change's last review round, or the check after its review round cap, it gives that it is.
- Where the change writes accepted gate outputs, it gives them, other than those a `run_dl.py` command writes where the change has the `handbook-expanded` agent.
- Where the operator launches it, it gives the command whose output its final reply ends with.
- It gives the agent id of the agent that launches it, where that is not the coordinator.

### An operator's brief
- An operator's brief gives only lines in these forms, each on a line of its own:
    - `Op solve: <task id> ...`: a solver pipeline on each task, from Analyze, or from the pass that `from create` or `from refine` after its task id gives.
    - `Op run: <path>`: the solver pipelines that the run script at that path starts, and the open tickets the operator takes from then on, as `uv run python scripts/operate.py --help run` gives the script.
    - `Op drafts to review: <number>, ...`: the draft `change` tickets to review.
    - `Op expedite: <number>, ...`: tickets of any session, and each `change` that a chain of links, as [Change tickets](prompts/agents/notes/tickets.md#change-tickets) gives a link, reaches from them. The operator releases, takes and settles each of them as it does its session's, and takes each of those changes ahead of the other changes it may take.
    - `Op merged: <number>, ...`: the changes the coordinator merged itself.
    - `Op merge: <number>`: a `change` under `tickets/blocked/`, which the user's ruling has the operator merge.
    - `Op tickets are open.`
    - `Op allow: <number>, ...`: tickets of any session, and each `change` that a chain of links, as [Change tickets](prompts/agents/notes/tickets.md#change-tickets) gives a link, reaches from them. The operators of the session settle and take each of them under `Op scope: own.` too, with no priority over other work.
    - `Op scope: own.`: the operators of the session settle no ticket under `tickets/open/` and take no `change`, other than these:
        - The tickets the session's coordinator filed, and each ticket filed for one of them: a ticket a link leads to from it, a ticket filed on it, or a `change` whose Motivation gives its number, and so on down each chain.
        - The tickets and changes an `Op allow:` or an `Op expedite:` line gives.
        - The work an operator of the session took and each `change` that work waits on, which they carry to its end.
    - `Op scope: all.`: ends the limit of `Op scope: own.`.
    - `Op pace: <preset> [<argument> ...]` or `Op pace: <path>`: the usage pace, as `uv run python scripts/operate.py --help pace` gives it. Past that pace, the operators of the session admit only the tickets and changes an `Op allow:` or an `Op expedite:` line gives, and the work an operator of the session took and each `change` that work waits on.
    - `Op override: <task id> <pass> <override>`: an override that the brief of the next launch of that pass on that task gives.
    - `Op override: pass over <step key>`: passes over the solver pass whose step key it gives: that pass's task id and its pass, in the form `uv run python scripts/operate.py --help rulings` gives.
    - `Op override: give again <step key>`: makes the step whose key it gives due again, past its retirement, its outcomes and a pass-over, in the form `uv run python scripts/operate.py --help rulings` gives.
        * comment: The user's words, session 19c17548, 2026-10-17T13:59:40Z: "10-947 feels like would be better to have escape hatch for exceptions? Like you can modify op state or intervene or whatever", and 14:01:05Z: "2 The most robust thing": ticket 10-950.
    - `Op decision: <decision key> <choice>`: rules the held step that gives that decision key with one of the choices that step gives, as the whole rest of the line.
- The operator gives each line of its brief or of a later message from the coordinator in no other form back to the coordinator as undecided.

### A code reviewer's brief
- A code reviewer's brief gives the earlier code review's baseline, as a `code-review/<n>` tag, this code review's number and a scratch directory.

### A lib reviewer's brief
- A lib reviewer's brief gives the earlier lib review's baseline, as a `lib-review/<n>` tag, this lib review's number and a scratch directory.

### A design reviewer's brief
- A design reviewer's brief gives the change's worktree, the number of its ticket and a scratch directory.
- Where the operator launches it, it gives the command whose output its final reply ends with.
- It gives the agent id of the agent that launches it, where that is not the coordinator.

### A doc reviewer's brief
- A doc reviewer's brief gives a change to the agent-facing documents, as the files or a diff, and the number of its ticket, or, where it has none, what is already settled about it.
- It gives the change's worktree, and the agent id of each editor of the change, with the part that editor's brief gave it, or the whole change where its brief gave none.
- On a change with a ticket, it gives the rounds of review the reviewer has.
- Where the operator launches it on a change, it gives the command whose output its final reply ends with.
- It gives the agent id of the agent that launches it, where that is not the coordinator.
- A doc reviewer's brief on a commit of `master` that the coordinator merged with no `change` ticket gives that commit's hash in place of a worktree and editors.
- A doc reviewer's brief on a standing doc review gives the reader with its arguments, the commit of `master` it reviews, and the tag `doc-review/<reader>` that records that review in git, in place of a change, a worktree and editors.

### A transcript review's brief
- A transcript review's brief gives the run's agent id, `python3 ~/.claude/skills/retrieve/transcripts.py --help`, the lines of [Ticket files](prompts/agents/notes/tickets.md#ticket-files), the `<domain>` and `<subject>` [Ticket subjects](prompts/agents/notes/tickets.md#ticket-subjects) gives a transcript review of that run, and `transcript-review` as `<agent>`. It has the review file a ticket of kind `delay` for each place where the run explored to find what a docstring or a document line could have led it to.

### Solver work
- Solver work is a solver pass, or an edit of a solver or of the lib for one task.
- Its brief may give overrides, each labelled as an override: a judgment made in place of the agent's own.
- The agent refuses any other instruction in its brief on a judgment its work makes: it does none of the work, and writes the part of the brief it refused, quoted, as its report.
- Where the agent works in a worktree other than the main worktree and nothing stands at `work` in that worktree, the agent runs `ln -s <main worktree>/work work` there before it reads or writes under `work/`, with the parent of the directory `git rev-parse --path-format=absolute --git-common-dir` prints as `<main worktree>`.

### A solver work brief
- Where no `change` ticket gives solver work, its brief gives the task id, and, for work other than a pass, a transcript brief, as [A transcript brief](prompts/agents/notes/launching.md#a-transcript-brief) gives it, or, for the fix of what the closure of an `interference` ticket on the task leaves wrong in its solver, that ticket, and no worktree. It gives no items, and no files but the solver and the witness file of such a fix, and the agent determines the rest.

### Writing a solver work brief
- Read no solver to write a brief for solver work.
- Solver work other than a pass, or than the fix of a solver after an `interference` ticket on its task closes, is a change, which an editor carries as it carries any other, whether or not a `change` ticket gives it. Where one does, its brief has the form [A change's brief](#a-changes-brief) gives.

## Findings that block a change
- A finding of a review of a built change before its merge blocks the change only where it is a defect in what an item of the change asks for, an edit that carries out an item wrongly, or a defect that an edit made to fix an earlier finding of the change.
- File each other finding as a ticket, in the form your documents give a ticket, and have no editor fix it: that ticket does not block the change.

## Passes on a task
- Before you launch a pass on a task whose claim you do not hold, claim the task: run `uv run python scripts/operate.py claim <task_id>`. Where it fails, launch no pass on that task.
- Where that pass is an Analyze or a Create pass, set aside the task's earlier work in the main worktree:
    1. Make a new directory `work/task/<task_id>/<n>/`, with `n` one more than the highest numbered directory there, and 1 where there is none.
    2. Write the output of `git diff HEAD -- programs/solvers/<task_id>.dl programs/witnesses/<task_id>.wit.json` to `uncommitted.diff` in it.
    3. Move into it the task's solver and its witness file, each where it exists, and, before an Analyze pass, each entry of `work/task/<task_id>/` other than `claim` and the numbered directories, or, before a Create pass, `create.md`, each `refine-<n>.md` and `progress.md`.
    4. Run `git update-index --skip-worktree <path>` on the path of each of those two files that `git ls-files <path>` lists.
- Once each pass you launch on the task for one request or one procedure has ended, or the harness or the permission classifier has refused the launch of such a pass while no other such pass runs:
    1. Move the solver and the witness file you set aside back to their paths, each where nothing stands at its path.
    2. Run `git update-index --no-skip-worktree <path>` on each path you marked.
    3. Remove the claim file, `work/task/<task_id>/claim` in the main worktree.

## Operators
- Send each line you give an operator to your running operator launcher, and where none runs, launch a new operator launcher with it. Give it in a form [An operator's brief](#an-operators-brief) gives, with nothing else in that message.
- The final reply of an operator or of an operator launcher is the text from a line `final reply` on in a message to you.
- When an operator launcher's final reply asks for a fresh operator launcher, launch one with a brief that gives each line of yours that reply gives, and no line where it gives none.
- When an operator's message, or a paragraph of it, that opens with `undecided:` reaches you, send the operator again the line of yours it gives, in a form [An operator's brief](#an-operators-brief) gives.
- When an operator's message that opens with `for the coordinator:` reaches you, read the file it gives.
- Bring the user each `decision:` item that file or an operator's final reply gives, other than a decline, tell the user each `tell:` item, and act on each `unfinished:` item as on an item an agent you launched gives as unfinished.
- Ask an operator for no message to you before its final reply, other than the messages that open with `for the coordinator:` or `undecided:`, which it sends as it goes.
- Send each draft `change` ticket that the reply of an agent you launched gives, and each `change` ticket you revise, to an operator in an `Op drafts to review: <number>` line.
- Each time a `change` of your session comes to stand under `tickets/open/` with every ticket its `depends-on` gives under `tickets/closed/`, while no operator of your session holds it or runs its review, tell an operator that tickets are open.
- Revise a `change` ticket that stands under `tickets/open/`, `tickets/assigned/`, `tickets/blocked/` or `tickets/waiting/` only once you have moved it back to `tickets/draft/`, with a log line whose note gives what you revise and on what ground.
- Once the user rules on a draft `change` ticket under `tickets/blocked/`, move it back to `tickets/draft/` with the ruling in the note, revise it where the ruling needs that, and send it to an operator in an `Op drafts to review: <number>` line.

## While the user gives feedback
- Gather each request the user approves into a batch, and when the user pauses or asks you to send it, send the whole batch at once: give each request to the agent a line of your documents gives for its work, or else to the handbook agent whose description covers it, as the split line of [Launching](#launching) allows, with one brief per agent.
- Where a request touches the files of a change that has not passed, send it to that change's editor with SendMessage. Add every other request to the batch.

## A draft's outcome
- A draft's outcome is the decision that this revision of the draft or a later revision of it gives, and the change the tree gets from that decision.
- The outcome rests on a claim where, were the claim wrong, the outcome would differ. A check of the claim is no part of the outcome.
