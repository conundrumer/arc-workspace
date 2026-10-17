+ budget: 1800
* comment: when editing this doc
    - The lib reviewer's checklist: `uv run python scripts/step.py lib-reviewer` prints its items one at a time, by [Lib reviewer](prompts/agents/lib-reviewer.md#lib-reviewer), each as the lib reviewer reaches its step.
    - Acts, each with its section: each step of its work, under the item of that step.

# Record this lib review's commit
- Record this lib review's commit, as [This lib review's commit and diff](prompts/agents/lib-reviewer.md#this-lib-reviews-commit-and-diff) gives.

# Diff the trees
- Add the worktrees of the earlier baseline and of this lib review's commit, and make the diff, as [This lib review's commit and diff](prompts/agents/lib-reviewer.md#this-lib-reviews-commit-and-diff) gives.

# Find the places
- Find every place in the units and the lines the diff touches, as [Finding places](prompts/agents/lib-reviewer.md#finding-places) gives.

# Judge the places
- Judge each defect place, as [Judging places](prompts/agents/lib-reviewer.md#judging-places) gives.

# File the tickets
- File the tickets on the places, as [Tickets on places](prompts/agents/lib-reviewer.md#tickets-on-places) gives.

# Make the baseline tag
- Make this lib review's baseline tag, as [The baseline tag and your reply](prompts/agents/lib-reviewer.md#the-baseline-tag-and-your-reply) gives.

# Report
- Remove each worktree you added, then end your turn with your final reply, as [The baseline tag and your reply](prompts/agents/lib-reviewer.md#the-baseline-tag-and-your-reply) gives.
