+ budget: 1500
* comment: when editing this doc
    - The lib reviewer reads this document by the link of the item `Find the places` of its [checklist](prompts/agents/lib-reviewer/checklist.md).
    - Acts, each with its section:
        - Finding places: [Finding places](#finding-places).

# Finding places
- Read each relation, rule, functor, component and module the diff touches whole, as it stands at this lib review's commit, to find its places. Where its growth over earlier commits decides whether it is a place, run `git log -L` on it in the worktree of that commit.
- Find the places of each kind [unit-kinds](prompts/agents/notes/code.md#unit-kinds) gives that Datalog or C++ code can hold, other than many ideas in one place.
    + xref: prompts/agents/notes/code.md#unit-kinds
- The line-level places are the places in the diff of each kind [line-kinds](prompts/agents/notes/code.md#line-kinds) gives, and each break of a rule on prose in code that [Docstrings, comments and help text](src/controlled_markdown/writing.md#docstrings-comments-and-help-text) gives, in the code that no place of a whole unit is to restructure or remove.
    + xref: prompts/agents/notes/code.md#line-kinds, src/controlled_markdown/writing.md#docstrings-comments-and-help-text
- A line in the diff that breaks a line of the handbook is a line-level defect place too.
