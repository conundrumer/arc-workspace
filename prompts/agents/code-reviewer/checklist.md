+ budget: 2858
* comment: when editing this doc
    - The code reviewer's checklist: `uv run python scripts/step.py code-reviewer` prints its items one at a time, by [Code reviewer](prompts/agents/code-reviewer.md#code-reviewer), each as the code reviewer reaches its step.
    - Acts, each with its section: each step of its work, under the item of that step.

# Record this code review's commit
- Record this code review's commit, as [This code review's commit and diff](prompts/agents/code-reviewer.md#this-code-reviews-commit-and-diff) gives.

# Diff the trees
- Add the worktrees of the earlier baseline and of this code review's commit, and make the diff, as [This code review's commit and diff](prompts/agents/code-reviewer.md#this-code-reviews-commit-and-diff) gives.

# Find the places of a whole unit
- Find every place of each kind of a whole unit, other than many ideas in one place, in the units the diff touches, as [Finding places](prompts/agents/code-reviewer.md#finding-places) gives.

# Find the places of many ideas in one place
- Find the places of many ideas in one place, as [Finding places](prompts/agents/code-reviewer.md#finding-places) gives.

# Judge the listed modules
- This part applies where the command of the step before this one listed a module: [Many ideas in one place](prompts/agents/code-reviewer/many-ideas.md).

## Judge each listed module
- Judge the subjects each listed module splits into, as [Many ideas in one place](prompts/agents/code-reviewer/many-ideas.md#many-ideas-in-one-place) gives.

# Find the line-level places
- Find the line-level places, as [Finding places](prompts/agents/code-reviewer.md#finding-places) gives.

# Judge the places
- Judge each defect place, as [Judging places](prompts/agents/code-reviewer.md#judging-places) gives.

# File the tickets on the listed modules
- Where the command that lists the places of many ideas in one place listed a module, file the ticket on each such place, as [Many ideas in one place](prompts/agents/code-reviewer/many-ideas.md#many-ideas-in-one-place) gives.

# File the tickets
- File the tickets on the other places, as [Tickets on places](prompts/agents/code-reviewer.md#tickets-on-places) gives.

# Make the baseline tag
- Make this code review's baseline tag, as [The baseline tag and your reply](prompts/agents/code-reviewer.md#the-baseline-tag-and-your-reply) gives.

# Report
- Remove each worktree you added, then end your turn with your final reply, as [The baseline tag and your reply](prompts/agents/code-reviewer.md#the-baseline-tag-and-your-reply) gives.
