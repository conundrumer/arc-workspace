# Launching notes
- The statements on launching an agent, that more than one entry point inlines or links.

## Launching
- After an agent's definition changes, wait 30 seconds before you launch that agent, so the harness reloads its file.
- Give an agent a brief with what its description says the brief gives, and restate neither a docstring of the code nor the agent's definition.
- In a brief that asks for an edit, give the meaning to state, the case that shows the need, and the span the edit may change, and no wording.
- Split work between agents where the split saves at least 30 minutes of wall-clock per 150k tokens of overhead.
- An agent's budget, in minutes, is the budget that `uv run python scripts/profile_runs.py ~/.claude/projects/-Users-davidlu-code-arc-workspace/*.jsonl --type <agent type> --since <date>` prints for its agent type, where `<date>` is what `git log -1 --format=%cI -- <path> ...` prints over the paths of that type's prompt, of each document it includes or inlines, and of the tools it runs.
- When an agent you launched ends a turn more than its budget after the brief or message that started that turn, or with items left, change its brief or split its work, in the same turn.
- A transcript review is a `general-purpose` agent that reviews a run's transcript. Give it the run's agent id, `python3 ~/.claude/skills/retrieve/transcripts.py --help`, and the lines of [Issue files](prompts/agents/notes/issues.md#issue-files), with that agent id as `<source>` and `transcript-review` as `<agent>`. Have it file an issue of kind `delay` for each place where the run explored to find what a docstring or a document line could have led it to.
- Where a completed run's active time, its wall time less its `idle` time as `uv run python scripts/profile_runs.py <agent id>` prints them, is past its agent type's budget, and the run is no Analyze, Create or Refine pass, launch a transcript review of it.
- Pause or serialize agents only where the user agreed to it.

## Operators
- Once an operator has returned, send it further work only while a procedure its brief gives is unfinished and its context is under about 300k tokens. Otherwise launch a new operator, and give in its brief that work and the work the old operator's last reply leaves unfinished, each as a procedure and its inputs.

## While the user gives feedback
- Gather each request the user approves into a batch, and when the user pauses or asks you to send it, send the whole batch at once: give each request to the agent whose description covers its work, as the split line above allows, with one brief per agent.
- Where a request touches the files of a change that has not passed, send it to that change's editor with SendMessage. Add every other request to the batch.
