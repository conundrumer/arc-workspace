+ lib: none
+ budget: 6100
* comment: when editing this doc
    - The code reviewer loads this document, rendered to `.claude/code-reviewer-next.md`, once it has found the places of the steps of [Code reviewer](prompts/agents/code-reviewer.md) before its `cat` line, to find the line-level places in the diff.
    - Acts, each with its section:
        - Finding line-level defect places and those of prose in code: [Code reviewer: second stage](#code-reviewer-second-stage).

# Code reviewer: second stage
- Find every place in the diff of each kind below, in the code that no place you found before is to restructure or remove.
    * inline: notes/code.md#line-kinds
    - A rule on prose in code is one of these:
        * inline: ../../src/controlled_markdown/writing.md#prose-in-code
