# Launching notes
- The statements on launching an agent, that more than one entry point inlines or links.

## Launching
- After an agent's definition changes, wait 30 seconds before you launch that agent, so the harness reloads its file.
- Give an agent a brief with what its description says the brief gives, and restate neither a docstring of the code nor the agent's definition.
- In a brief that asks for an edit, give the meaning to state, the case that shows the need, and the span the edit may change, and no wording.
- Split work between agents where the split saves at least 30 minutes of wall-clock per 150k tokens of overhead.
- An agent's budget is the N of the `Budget: N minutes` line of its brief, or of your latest message to it that has one, which replaces the brief's. Set it from the budget that `uv run python scripts/profile_runs.py ~/.claude/projects/-Users-davidlu-code-arc-workspace/*.jsonl --type <agent type>` prints for its agent type, over the window that command's `--help` gives, and change it for the work the brief or that message asks for. An agent that runs until you tell it to stop has no budget.
- When an agent you launched ends a turn more than its budget after its brief or your latest message to it arrived, change its brief or split its work, in the same turn.
- When a supervisor's flag of kind `budget` reaches you, tell the agent to write its progress and end where its documents say what it does when its budget passes, and otherwise tell it what to finish and to end, and kill or retry no agent. The agent reads your message only when its current command ends.
- Act on each item that an agent you launched gives as unfinished, by its reason:
    - Where it needs more work or more budget, change that agent's brief or split its work, and send the item again, in the same turn.
    - Where a tool or a document stopped it, file that obstacle as an issue of the kind that fits it, and send the item again once that issue is resolved, or at once by a way around the obstacle where one exists.
    - Where it needs a decision, act on it as that decision rules, once the decision is made.
- Where an agent whose description says its reply gives each item of its brief as done or as unfinished has replied, and gives an item you sent it as neither, send that item again, file its drop as an `interference` issue, and leave finding the drop's cause to the triage agent that takes that issue.
- Launch a triage agent with each issue you file for an obstacle or a drop, as the lines above give, before you end your turn with no other work. Where you are a triage agent, settle those issues yourself.
- In your reply, give each item an agent you launched left unfinished that you have not finished, as unfinished with its reason.
- A transcript review is a `general-purpose` agent that reviews a run's transcript. Give it the run's agent id, `python3 ~/.claude/skills/retrieve/transcripts.py --help`, and the lines of [Issue files](prompts/agents/notes/issues.md#issue-files), with that agent id as `<source>` and `transcript-review` as `<agent>`. Have it file an issue of kind `delay` for each place where the run explored to find what a docstring or a document line could have led it to.
- Where a completed run's active time, its wall time less its `idle` time as `uv run python scripts/profile_runs.py <agent id>` prints them, is past its agent type's budget, and the run is no Analyze, Create or Refine pass, launch a transcript review of it.
- Pause or serialize agents only where the user agreed to it.

## Operators
- When you launch an operator while no supervisor runs, launch a supervisor in the background. When a supervisor's reply says it ended for its context while an operator runs, launch a new one, with the flags and the states found not to hold that reply gives.
- Once no operator of yours runs, tell the supervisor to stop, with SendMessage.
- Ask an operator for no message to you before its final reply.
- Give each draft of an operator's launch brief, and of a message to a running operator with that operator's agent id, to the session's dispatcher: launch the dispatcher with the first draft, and send each later draft with SendMessage. The dispatcher sends a message with no finding to the operator itself.
- Launch an operator only once the dispatcher returns no finding on its brief. Where the dispatcher returns findings, revise the draft and send it again.
- When a dispatcher's reply says it ended for its context, launch a new one with that reply and the next draft.
- Once an operator has returned, send it further work only while a procedure its brief gives is unfinished and its context is under about 300k tokens. Otherwise launch a new operator, and give in its brief that work and the work the old operator's last reply leaves unfinished, each as the operator's description gives a procedure.

## While the user gives feedback
- Gather each request the user approves into a batch, and when the user pauses or asks you to send it, send the whole batch at once: give each request to the agent whose description covers its work, as the split line above allows, with one brief per agent.
- Where a request touches the files of a change that has not passed, send it to that change's editor with SendMessage. Add every other request to the batch.
