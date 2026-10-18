+ budget: 900
* comment: when editing this doc
    - The code reviewer reads this document by the link of the item `Find the places of a whole unit` of its [checklist](prompts/agents/code-reviewer/checklist.md).
    - Acts, each with its section:
        - Finding the places of a whole unit: [Places of a whole unit](#places-of-a-whole-unit).

# Places of a whole unit
- Read each function, record, class and module the diff touches whole, as it stands at this code review's commit, to find its places. Where its growth over earlier commits decides whether it is a place, run `git log -L` on it in the worktree of that commit.
- The kinds of a whole unit are those [unit-kinds](prompts/agents/notes/code.md#unit-kinds) gives.
    + xref: prompts/agents/notes/code.md#unit-kinds
