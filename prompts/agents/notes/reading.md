+ budget: 2000
* comment: when editing this doc
    - Each reader of the handbook inlines its sections where it starts to read the handbook: the `analyze`, `create`, `refine`, `handbook`, `handbook-expanded` and `lib-reviewer` agents, [Solver session](prompts/session.md), [User session](prompts/user-session.md) and [Codex on arc-workspace](prompts/codex.md).
    - Acts, each with its section:
        - Reading a whole section of the handbook: [abridgement](#abridgement).
        - Reading a cited task id: [citations](#citations).
        - Reading the lib as an index: [lib-index](#lib-index).
        - Reading the lib's interface: [lib-interface](#lib-interface), inlined by create and refine.

# Reading notes
- The statements on reading the handbook and the lib that more than one entry point inlines.

## abridgement
- `uv run python scripts/context.py section '<chapter>#<heading>'` prints a whole section.
    - The target of a link into `docs/handbook/` also works as the argument.

## citations
- A bare task id cites a solver that works out the statement it sits under, and this rendering leaves out the line saying what that solver shows.
- The same command prints the section with those lines, under the heading the id sits below.

## lib-index
- The lib below is an index.
- `uv run python scripts/context.py section 'programs/lib/<module>.dl#<name>'` prints one declaration's interface.
- `programs/lib/<module>.md` holds a whole module's interface, and `programs/lib.md` the top-level lib's.

## lib-interface
- Each section below gives one module's interface.
- Read the module's source under `programs/lib/` for the body of every comp the solver instantiates.
