# Shared notes
- The statements more than one entry point inlines.

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

## solver-pass-lead
- What an operation routes to the review goes in your report, under the section it fits.
- Write under `programs/solvers/`, `programs/witnesses/`, and `.scratch/<task_id>/`, and nowhere else; the Analyze files are not changed.
- Report a failing run as failing.
- Do not read `../arc-synth-bun/`.
- Never run a git command that changes state.
- Your reply is the report's path.

## report-form
- The report's form:
    ```
    # <task_id>

    ## Departures
    - <how the solver or the witness file differs from the Analyze files>: <the condition or fact it rests on>

    ## Judgments
    - <a judgment the files do not show>: <what it rests on>

    ## Open
    - <what the pass leaves unsettled>: <what would settle it>

    ## Lib
    - <an operation the trigger fires on>: <its solver-local form, and the sites the grep found>

    ## Fixes elsewhere
    - <a file the pass does not edit, and the line>: <the fix it needs>

    ## Doc and tool issues
    - `delay` or `interference`: <the doc or tool line, and how it slowed the pass, or what the pass wrote wrong because of it>
    ```
- A section with nothing holds `none`.
- Nothing in the report waits on a ruling.
