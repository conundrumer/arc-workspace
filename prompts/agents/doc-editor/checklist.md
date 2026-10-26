+ document-size-budget: 3151
* comment: when editing this doc
    - The doc editor's checklist: `uv run python scripts/step.py doc-editor` prints its items one at a time, by [Doc editor](prompts/agents/doc-editor.md#doc-editor), each as the doc editor reaches its step.
    - Acts, each with its section: each step of its work, under the item of that step.

# Work out the readers
- Work out each reader of each place you will edit: who it is, how it arrives at that place, what its context already holds there, what it is doing there, and what it does next.

# Make the whole-document pass
- This part applies where the `Design` of your change's ticket gives a whole-document pass: [Whole-document pass](prompts/agents/doc-editor/whole-document.md).

## Judge each line of the Scope's documents
- Judge each line of each document your change's Scope gives, as [Whole-document pass](prompts/agents/doc-editor/whole-document.md#whole-document-pass) gives.
    + xref: prompts/agents/doc-editor/whole-document.md#whole-document-pass

# Write the edit
- Write the edit your request and each later message need, as [Writing the edit](prompts/agents/doc-editor.md#writing-the-edit) and [Building the Design](prompts/agents/doc-editor/design.md#building-the-design) give.
    + xref: prompts/agents/doc-editor.md#writing-the-edit, prompts/agents/doc-editor/design.md#building-the-design

# Check and review the edit
- Check and review the edit, as [Reviewing your edit](prompts/agents/doc-editor.md#reviewing-your-edit) gives.
    + xref: prompts/agents/doc-editor.md#reviewing-your-edit

# Cut what no rule keeps
- Judge each line of each place you edited again as each of its readers, by the rules of [Writing the edit](prompts/agents/doc-editor.md#writing-the-edit), cut each line there that those rules do not keep, and check and review the cut, as [Reviewing your edit](prompts/agents/doc-editor.md#reviewing-your-edit) gives.
    + xref: prompts/agents/doc-editor.md#writing-the-edit, prompts/agents/doc-editor.md#reviewing-your-edit

# Judge the document lines your diff touches
* comment: The user's words, session 2384db39, 2026-10-18T16:01:04Z: "send request for general resolution for cross doc consistency. would +attr links make sense? or md links?". Ticket 11-1390.
- Run `uv run python -m controlled_markdown xrefs $(git merge-base master HEAD)`, and judge each line it prints against the text and the code your edit leaves. Edit a line that no longer holds where your change's Scope gives its document, and otherwise give it in your reply as unfinished.
    + xref: src/controlled_markdown/__main__.py:main

# Set the budgets
- Where you made a whole-document pass, set the `+ document-size-budget:` line of each document your change's Scope gives, as [Whole-document pass](prompts/agents/doc-editor/whole-document.md#whole-document-pass) gives, and check and review that edit, as [Reviewing your edit](prompts/agents/doc-editor.md#reviewing-your-edit) gives.
    + xref: prompts/agents/doc-editor/whole-document.md#whole-document-pass, prompts/agents/doc-editor.md#reviewing-your-edit

# Write your reply
- Where your brief gives a report file, write your reply to it, as [Your reply](prompts/agents/doc-editor/reply.md#your-reply) gives.
    + xref: prompts/agents/doc-editor/reply.md#your-reply

# Launch the checks
- Run `uv run python scripts/operate.py review <agent id>`, with your own agent id, and do as it prints. Where it prints an Agent call, read [Background agents](prompts/agents/notes/commands.md#background-agents) and make that call. Run it again after each Agent call it prints.
    + xref: scripts/operate_review.py:review
    * if: codex
        - `review` prints nothing for up to 210 s. Start it with `yield_time_ms` 30000, then wait with one `write_stdin` call with empty `chars` and `yield_time_ms` 240000, in the same cell. Make no other poll.

# Reply
- Give your final reply, as [Your reply](prompts/agents/doc-editor/reply.md#your-reply) gives, once each agent you launched has replied after your last edit, and where you launched none, once `review` prints that you give it.
    + xref: prompts/agents/doc-editor/reply.md#your-reply
