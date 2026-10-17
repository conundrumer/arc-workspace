+ budget: 3700
* comment: when editing this doc
    - The code editor reads this document by the links of the items `Find the refactor tickets on your modules` and `Write the code` of its [checklist](prompts/agents/code-editor/checklist.md), once it has written its `Reuse` list.
    - Acts, each with its section:
        - Writing the code against the spec, and finding the `refactor` tickets on its modules: [Writing the code](#writing-the-code).

# Writing the code
- Implement your brief against the spec: the docstrings of the modules you touch.
    - Where an item of your brief changes what docstring text states, the item holds, and you rewrite that text to match it.
    - Change no other docstring text that stands before your edit, apart from text that the rules on prose in code below have you cut.
    - The rules on prose in code are those of [Docstrings, comments and help text](src/controlled_markdown/writing.md#docstrings-comments-and-help-text).
        - Where you write or change a string a program puts in an agent's context, a `quotes` or `guard` decorator, or a `///` or `//!` comment in a Souffle file, read [Text the check reads in code](src/controlled_markdown/writing.md#text-the-check-reads-in-code).
- In code, a case the spec does not cover becomes an `undecided` finding or a fault, never a default, and you file it as [Tickets](prompts/agents/code-editor.md#tickets) gives.
- Use the code your `Reuse` list gives, as it gives it; then decide the shape, so that it makes illegal states unrepresentable and is DRY: each idea in one operation, called from every site that needs it, as the `Design` of your change's ticket gives it, where it gives one. Where the code shows a better shape than that `Design`, build that shape, and give in your report the departure with its reason.
    * comment: The user's words, session 7fd429fb, 2026-10-13T14:46:25Z: "im curious if this could be part of a planning principle"; 14:47:10Z: "what about just poitnting at the core idea", the core idea being "Make illegal states unrepresentable"; 14:47:43Z, on reading the bare name as license for big refactors: "i dont expect that to happen but if it did i would welcome it". On the standard names, the user's words, session 7fd429fb, 2026-10-15T22:44:57Z: "Let’s try it. Principles are short and well known in training set"; 2026-10-16T02:19:36Z: "almost seems liek a regression".
- Where your brief gives the places of `refactor` tickets, fix the defect at each.
- The `refactor` tickets that cite a module are those `grep -lE '^# .<module>.: many ideas in one place$' tickets/open/*.md` lists, with the module's path as `<module>`.
    - When you come to edit a module that the step that found these tickets did not cover, find its tickets, and where one cites it, run `uv run python scripts/step.py code-editor --enter split-the-cited-modules`, or, where your context still holds that part's file from an earlier entry, `uv run python scripts/step.py code-editor --reenter split-the-cited-modules`, split it, and then edit it.
