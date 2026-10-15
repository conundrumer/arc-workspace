+ budget: 1400
* comment: when editing this doc
    - The code editor loads this document from [Code editor: second stage](prompts/agents/code-editor-next.md#code-editor-second-stage), where a `refactor` ticket for many ideas in one place cites a module it is to edit.
    - Acts, each with its section:
        - Splitting the module and reporting the split: [A split](#a-split).

# A split
- Split the module into one module for each subject of the `refactor` ticket's `Impact` that the module still holds, with each module's docstring saying what that module holds, and the docstring of their package saying what the package holds as a whole and the rules its modules keep.
- The modules of the split, and each file whose imports the split changes, count among the files your brief gives.
- Where you have a budget and the whole split would run past it, move only the subjects your edit touches into modules beside it, and leave the rest at the path the ticket cites.
- Give in your report each module you split in a list item of one line that opens with `split:`, then gives the path the ticket cites in backticks, with no ticket number, and then, where you left a part of it unsplit, `; left unsplit:` and that part.
