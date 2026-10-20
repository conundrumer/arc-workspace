+ document-size-budget: 900
* comment: when editing this doc
    - The code reviewer reads this document by the link of the item `Find the places of many ideas in one place` of its [checklist](prompts/agents/code-reviewer/checklist.md).
    - Acts, each with its section:
        - Finding the places of many ideas in one place: [Places of many ideas in one place](#places-of-many-ideas-in-one-place).

# Places of many ideas in one place
- The places of many ideas in one place are the modules this command lists, run in the worktree of this code review's commit:
    ```
    { find src scripts -name '*.py' -exec wc -l {} +; find engine -name '*.rs' -not -path 'engine/target/*' -exec wc -l {} +; } | awk '$1 > 500 && $2 != "total"' | sort -rn
    ```
