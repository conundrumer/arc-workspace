# Shared notes
- The statements an entry point inlines into its lead.

* comment: When editing this doc, keep a statement here when an entry point inlines it into its lead.

## abridgement
- `uv run python scripts/context.py section '<chapter>#<heading>'` prints a section this rendering abridges, in full.
    - The target of a link in the text also works as the argument.
    - A link into a document this rendering does not carry is followed the same way.

## citations
- A bare task id cites a solver that works out the statement it sits under, and this rendering leaves out the line saying what that solver shows.
- The same command prints the section with those lines, under the heading the id sits below.

## lib-index
- The lib below is an index, one line per declaration.
- `uv run python scripts/context.py section 'programs/lib/<module>.dl#<name>'` prints one declaration's interface.
- `programs/lib/<module>.md` holds a whole module's interface, and `programs/lib.md` the top-level lib's.

## citations-carried
- A bare task id cites a solver that works out the statement it sits under, and the line under the id says what that solver shows.
