+ budget: 1201
* comment: when editing this doc
    - The code reviewer receives this file from `uv run python scripts/step.py code-reviewer --enter judge-the-listed-modules`, by its [checklist](prompts/agents/code-reviewer/checklist.md), with the modules that the command of [Places of many ideas in one place](prompts/agents/code-reviewer/module-sizes.md#places-of-many-ideas-in-one-place) listed in its run.
    - Acts, each with its section:
        - Judging a module of many ideas in one place, and filing its ticket: [Many ideas in one place](#many-ideas-in-one-place).

# Many ideas in one place
- A module the command lists is a defect place of many ideas in one place, which stands where the module holds one subject. Judge the subjects it splits into along its section banners or its classes.
    + xref: prompts/agents/code-reviewer/module-sizes.md#places-of-many-ideas-in-one-place
- File its ticket as [review-tickets](prompts/agents/notes/code.md#review-tickets) and [place-tickets](prompts/agents/notes/code.md#place-tickets) give, with `many ideas in one place` as what is wrong in the module, each subject it splits into, with the section banners or the classes that hold it, under `Impact`, and the module's line count as `wc -l` prints it under `Evidence`.
    + xref: src/ticketing/vocabulary.py:MANY_IDEAS, prompts/agents/notes/code.md#review-tickets, prompts/agents/notes/code.md#place-tickets
