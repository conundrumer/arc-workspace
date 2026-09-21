# Shared notes
- The statements an entry point inlines into its lead.

* comment: When editing this doc, keep a statement here when an entry point inlines it into its lead.

## abridged-headings
- A heading with no statement directly under it names a section this rendering abridges.

## abridgement
- `uv run python scripts/context.py section '<chapter>#<heading>'` prints that heading's section in full, as in `section 'Solver file#Header'`.
    - `<chapter>` is the document's title, as a heading of this rendering shows it.
    - The target of a link in the text also works as the argument.
    - A link into a document this rendering does not carry is followed the same way.
- A pattern shown as one bold phrase and a sentence is abridged, and its bold phrase is the heading to name.

## citations
- A bare task id cites a solver that works out the statement it sits under, and this rendering leaves out the line saying what that solver shows.
- The same command prints the section with those lines, under the heading the id sits below.

## lib-index
- The lib below is an index, one line per declaration.
- `uv run python scripts/context.py section 'programs/lib/<module>.dl#<name>'` prints one declaration's interface.
- `programs/lib/<module>.md` holds a whole module's interface, and `programs/lib.md` the top-level lib's.
