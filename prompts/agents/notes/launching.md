# Launching notes
- The statements on launching an agent, that more than one entry point inlines or links.

## Launching
- After an agent's definition changes, wait 30 seconds before you launch that agent, so the harness reloads its file.
- Give an agent a brief with what its description says the brief gives, and restate neither the spec nor the agent's definition.
- In a brief that asks for an edit, give the meaning to state, the case that shows the need, and the span the edit may change, and no wording.
- Split work between agents where the split saves at least 30 minutes of wall-clock per 150k tokens of overhead.
- When an agent you launched ends its turn past its estimate, or with items left, change its brief or split its work, in the same turn.
- When a run of an agent you launched completes, append a line for it to `issues/runs.log`, in the form `<time> <agent type>: <tokens> tokens, <tool calls> tool calls, <minutes> minutes, estimate <estimate>`, with the figures its completion notification gives, and the estimate in minutes its brief gave, or `none`.
- A transcript review is a `general-purpose` agent that reviews a run's transcript. Give it the run's agent id, `python3 ~/.claude/skills/retrieve/transcripts.py --help`, and the form [Issue files](prompts/agents/notes/issues.md#issue-files) gives, with that agent id as `<source>` and `transcript-review` as `<agent>`. Have it file an issue of kind `delay` for each place where the run explored to find what a docstring or a document line could have led it to.
- Where a completed run's tokens exceed one and a half times the median of the runs of its agent type in that log, and the run is no Analyze, Create or Refine pass, launch a transcript review of it.
- Pause or serialize agents only where the user agreed to it.

## While the user gives feedback
- Gather each request the user approves into a batch, and when the user pauses or asks you to send it, send the whole batch at once: give each request to the agent whose description covers its work, as the split line above allows, with one brief per agent.
- Where a request touches the files of a change that has not passed, send it to that change's editor with SendMessage. Add every other request to the batch.
