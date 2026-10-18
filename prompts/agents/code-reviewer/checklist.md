+ budget: 2858
* comment: when editing this doc
    - The code reviewer's checklist: `uv run python scripts/step.py code-reviewer` prints its items one at a time, by [Code reviewer](prompts/agents/code-reviewer.md#code-reviewer), each as the code reviewer reaches its step.
    - Acts, each with its section: each step of its work, under the item of that step.

# Record this code review's commit
- Record this code review's commit, as [This code review's commit and diff](prompts/agents/code-reviewer.md#this-code-reviews-commit-and-diff) gives.

# Diff the trees
- Add the worktrees of the earlier baseline and of this code review's commit, and make the diff, as [This code review's commit and diff](prompts/agents/code-reviewer.md#this-code-reviews-commit-and-diff) gives.

# Find the places of a whole unit
- Find every place of each kind of a whole unit, other than many ideas in one place, in the units the diff touches, as [Places of a whole unit](prompts/agents/code-reviewer/whole-units.md#places-of-a-whole-unit) gives.

# Find the places of many ideas in one place
- Find the places of many ideas in one place, as [Places of many ideas in one place](prompts/agents/code-reviewer/module-sizes.md#places-of-many-ideas-in-one-place) gives.

# Judge the listed modules
- This part applies where the command of the step before this one listed a module: [Many ideas in one place](prompts/agents/code-reviewer/many-ideas.md).

## Judge each listed module
- Judge the subjects each listed module splits into, as [Many ideas in one place](prompts/agents/code-reviewer/many-ideas.md#many-ideas-in-one-place) gives.

# Find the line-level places
- Find the line-level places, as [Line-level places](prompts/agents/code-reviewer/line-places.md#line-level-places) gives.

# Find the breaks of the rules on prose in code
* comment: The user's words, session 129de8fc, 2026-10-17T16:23:08Z: "they get reviewed according to writing standards right", and 16:59:50Z: "go", which chose that a reviewer other than the editor checks a change's prose in code against those rules. Code reviewer aab0fd573a1baabdd, review 171 of commit dc9e6c94, whose diff adds Rust doc comments, read Prose in code through Line-level places alone, and judged no doc comment by it. In a trial that doc reviewer a4eebf99819a95f96 of change 9-972 ran, the code reviewer read Prose in code by a grep that ended before the rule on a consumer's rule, and missed the break of that rule.
- Read [Prose in code](src/controlled_markdown/writing.md#prose-in-code) whole, and find, as a defect place, each break of one of its rules in the diff, in each of its languages, in its docstrings, comments and `--help` texts and the strings the check reads, and, in the words of each docstring and comment the diff adds or changes, each break of a rule of [Writing a file](docs/handbook/editing.md#writing-a-file) that Prose in code applies to them, in the code that no place of a whole unit is to restructure or remove.

# Judge the places
- Judge each defect place, as [place-judgment](prompts/agents/notes/code.md#place-judgment) gives.

# File the tickets on the listed modules
- Where the command that lists the places of many ideas in one place listed a module, file the ticket on each such place, as [Many ideas in one place](prompts/agents/code-reviewer/many-ideas.md#many-ideas-in-one-place) gives.

# File the tickets
- File the tickets on the other places, as [review-tickets](prompts/agents/notes/code.md#review-tickets) and [place-tickets](prompts/agents/notes/code.md#place-tickets) give.

# Make the baseline tag
- Make this code review's baseline tag, as [The baseline tag](prompts/agents/code-reviewer/baseline-tag.md#the-baseline-tag) gives.

# Report
- Remove each worktree you added, then end your turn with your final reply, as [Your reply](prompts/agents/code-reviewer.md#your-reply) gives.
