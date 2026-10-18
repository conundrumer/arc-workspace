+ budget: 1800
* comment: when editing this doc
    - The lib reviewer's checklist: `uv run python scripts/step.py lib-reviewer` prints its items one at a time, by [Lib reviewer](prompts/agents/lib-reviewer.md#lib-reviewer), each as the lib reviewer reaches its step.
    - Acts, each with its section: each step of its work, under the item of that step.

# Record this lib review's commit
- Record this lib review's commit, as [This lib review's commit and diff](prompts/agents/lib-reviewer.md#this-lib-reviews-commit-and-diff) gives.
    + xref: prompts/agents/lib-reviewer.md#this-lib-reviews-commit-and-diff

# Diff the trees
- Add the worktrees of the earlier baseline and of this lib review's commit, and make the diff, as [This lib review's commit and diff](prompts/agents/lib-reviewer.md#this-lib-reviews-commit-and-diff) gives.
    + xref: prompts/agents/lib-reviewer.md#this-lib-reviews-commit-and-diff

# Find the places
- Find every place in the units and the lines the diff touches, as [Finding places](prompts/agents/lib-reviewer/places.md#finding-places) gives.
    + xref: prompts/agents/lib-reviewer/places.md#finding-places

# Judge the places
- Judge each defect place, as [place-judgment](prompts/agents/notes/code.md#place-judgment) gives.
    + xref: prompts/agents/notes/code.md#place-judgment

# File the tickets
- File the tickets on the places, as [review-tickets](prompts/agents/notes/code.md#review-tickets) and [place-tickets](prompts/agents/notes/code.md#place-tickets) give.
    + xref: prompts/agents/notes/code.md#review-tickets, prompts/agents/notes/code.md#place-tickets

# Make the baseline tag
- Make this lib review's baseline tag, as [The baseline tag](prompts/agents/lib-reviewer/baseline-tag.md#the-baseline-tag) gives.
    + xref: prompts/agents/lib-reviewer/baseline-tag.md#the-baseline-tag

# Report
- Remove each worktree you added, then end your turn with your final reply, as [Your reply](prompts/agents/lib-reviewer/reply.md#your-reply) gives.
    + xref: prompts/agents/lib-reviewer/reply.md#your-reply
