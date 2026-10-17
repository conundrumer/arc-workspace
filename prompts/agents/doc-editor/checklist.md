+ budget: 2809
* comment: when editing this doc
    - The doc editor's checklist: `uv run python scripts/step.py doc-editor` prints its items one at a time, by [Doc editor](prompts/agents/doc-editor.md#doc-editor), each as the doc editor reaches its step.
    - Acts, each with its section: each step of its work, under the item of that step.

# Work out the readers
- Work out each reader of each place you will edit: who it is, how it arrives at that place, what its context already holds there, what it is doing there, and what it does next.

# Make the whole-document pass
- This part applies where the `Design` of your change's ticket gives a whole-document pass: [Whole-document pass](prompts/agents/doc-editor/whole-document.md).

## Judge each line of the Scope's documents
- Judge each line of each document your change's Scope gives, as [Whole-document pass](prompts/agents/doc-editor/whole-document.md#whole-document-pass) gives.

# Write the edit
- Write the edit your request and each later message need, as [Writing the edit](prompts/agents/doc-editor.md#writing-the-edit) and [Building the Design](prompts/agents/doc-editor/design.md#building-the-design) give.

# Check and review the edit
- Check and review the edit, as [Reviewing your edit](prompts/agents/doc-editor.md#reviewing-your-edit) gives.

# Cut what no rule keeps
- Judge each line of each place you edited again as each of its readers, by the rules of [Writing the edit](prompts/agents/doc-editor.md#writing-the-edit), cut each line there that those rules do not keep, and check and review the cut, as [Reviewing your edit](prompts/agents/doc-editor.md#reviewing-your-edit) gives.

# Set the budgets
- Where you made a whole-document pass, set the `+ budget:` line of each document your change's Scope gives, as [Whole-document pass](prompts/agents/doc-editor/whole-document.md#whole-document-pass) gives, and check and review that edit, as [Reviewing your edit](prompts/agents/doc-editor.md#reviewing-your-edit) gives.

# Run the gate
- Where you have accepted gate outputs to write, read [Gate](prompts/agents/notes/worktree.md#gate), and run the gate as it gives.

# Launch the doc review
- Run `uv run python scripts/operate.py review <agent id>`, with your own agent id, and do as it prints. Where it prints an Agent call, read [Background agents](prompts/agents/notes/commands.md#background-agents) and make that call.

# Reply
- Give your final reply, as [Your reply](prompts/agents/doc-editor.md#your-reply) gives, once each doc reviewer you launched has replied after your last edit, and where you launched none, at once.
