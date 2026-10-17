+ budget: 3403
* comment: when editing this doc
    - The doc editor receives this document from the step command as it enters a whole-document pass, once it has worked out the readers of the places it will edit, and before it writes the edit.
    - Acts, each with its section:
        - Judging each line of the pass's documents, and setting their budgets: [Whole-document pass](#whole-document-pass).

# Whole-document pass
* comment: The user's words, request 6-1481, session 7fd429fb, 2026-10-16T16:59:32Z: "\"does the reader need this right now\" and \"does the reader need this at all\" and \"is there a shorter way to say all these things\" (shorter as in higher level not like mechanically dropping words and making it telegraphic)", and 16:52:24Z: "The doc budget might have failure modes, the same as in agent memory: important things get cut".
- A whole-document pass judges each line of each document your change's Scope gives, and not only the lines a diff changes, as each reader that loads that line, by [What a file holds](docs/handbook/editing.md#what-a-file-holds), [What stays and its whole unit](docs/handbook/editing.md#what-stays-and-its-whole-unit) and these questions:
    - Does the reader need it at the step where it reaches it?
    - Does the reader need it at all?
    - Can a rule at a higher level say it in fewer words? Dropping words from the line is no answer.
- The classes of bloat to look for first:
    - A shared note inlined whole where its reader acts on part of it.
    - A harness or tool quirk written as a standing rule, such as the `unattended-wait:` lead of a wait in [commands](prompts/agents/notes/commands.md#commands).
    - A line that stacks a clause for each incident it was to stop.
    - A rule that a check or a generator enforces, restated in prose, such as the markup rules that `uv run python -m controlled_markdown check` reports with their messages.
    - Text for the launcher that reaches the agent it launches, such as the brief forms of [Briefs](prompts/agents/notes/launching.md#briefs) that an editor inlines.
    - One rule written in two notes that one reader loads both of.
- Move text that a reader needs only at a later step or in a rare case behind a link whose condition gives that step or case. Cut a quirk that a tool, a hook or its error message enforces or gives at the moment of failure, and where none does, file a `bug` ticket on the tool or the hook whose failure the quirk is to stop.
- Cut no line that a reader needs, whatever the budget: the size is the outcome of the pass.
- Cut or reword no line of [Principles](docs/handbook/principles.md), which the user judges. You may change which readers load it.
- The pass sets the `+ budget:` line of each document your change's Scope gives to the size of its bounded text divided by `BAND` in [budget.py](src/handbook/budget.py), rounded down, plus one, so that its next growth draws a warning before a pass. `uv run python -c 'from handbook import budgeted; [print(s.doc, s.size) for s in budgeted.sizes()]'` prints each size.
