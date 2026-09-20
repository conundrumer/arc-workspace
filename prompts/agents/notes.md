# Shared notes
- The statements an entry document inlines into its lead, which the bare render does not carry.

* comment: When editing this doc, keep a statement here only while more than one entry document inlines it.

## abridgement
- A heading with nothing under it names a section this rendering abridges.
- `uv run python scripts/context.py section 'docs/handbook/<doc>.md#<heading>'` prints that section in full.
    - `<doc>` is the `##` heading the section sits under, in lower case, with a hyphen for each space.
    - A link to a section already reads this way, so one written in the text is pasted as it stands.
- A pattern shown as one bold phrase and a sentence is abridged the same way, and its bold phrase is the heading to name.

## citations
- A bare task id cites a solver that works out the statement it sits under, and this rendering leaves out the line saying what that solver shows.
- The same command prints the section with those lines, under the heading the id sits below.

## lib-index
- The lib below is an index, one line per component.
- `uv run python scripts/context.py section 'programs/lib/<module>.dl#<Component>'` prints one component's interface.
- `programs/lib/<module>.md` holds a whole module's interface, and `programs/lib.md` the top-level lib's.
