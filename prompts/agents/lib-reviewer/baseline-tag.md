+ budget: 700
* comment: when editing this doc
    - The lib reviewer reads this document by the link of the item `Make the baseline tag` of its [checklist](prompts/agents/lib-reviewer/checklist.md).
    - Acts, each with its section:
        - Making this lib review's baseline tag: [The baseline tag](#the-baseline-tag).

# The baseline tag
- `uv run python scripts/review_tag.py lib-reviewer <n> <commit> <agent id>`, with this lib review's commit as `<commit>` and your own agent id as `<agent id>`, makes this lib review's baseline tag. Where it refuses, do what it prints.
    + xref: scripts/review_tag.py:main
