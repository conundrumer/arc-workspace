# Reading notes
- The statements on reading the handbook and the lib that more than one entry point inlines.

* comment: When editing this doc, keep a statement here when more than one entry point inlines it.

## abridgement
- `uv run python scripts/context.py section '<chapter>#<heading>'` prints a whole section.
    - The target of a link in the text also works as the argument.
    - A link into a document this rendering does not carry is followed the same way.

## citations
- A bare task id cites a solver that works out the statement it sits under, and this rendering leaves out the line saying what that solver shows.
- The same command prints the section with those lines, under the heading the id sits below.

## lib-index
- The lib below is an index, one line per declaration.
- `uv run python scripts/context.py section 'programs/lib/<module>.dl#<name>'` prints one declaration's interface.
- `programs/lib/<module>.md` holds a whole module's interface, and `programs/lib.md` the top-level lib's.

## lib-interface
- Each section below gives one module's interface.
- Read the module's source under `programs/lib/` for the body of every comp the solver instantiates.
