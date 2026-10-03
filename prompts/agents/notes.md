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
    - <a judgment>: <what it rests on>

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

## code-working-rules
- Run every command in the foreground, with an explicit timeout of at most 600000 ms on the Bash call.
- Never use `run_in_background`.
    * comment: An agent ran a gate call in the background and had to be stopped.
- When a run does not finish inside one call, split it into parts that each finish inside one call, or record it as over its limit, and do not run it again.
- Run no git command that changes state.
- Read nothing under `../arc-synth-bun/`.
- Launch no agents.
- Keep `progress.md` in your scratch directory, with your start time, what is done and what is next. After your context is compacted, read it before anything else.
- When your time since the start passes one and a half times your estimate, write your report with what is done and what is left, and end your turn with a message to main that says the estimate is passed.

## place-kinds
- Defects:
    - One idea in two places: a computation, selection, rule, rendering or sentence written twice, in one module or across modules.
    - Solver text read or written outside the `souffle` package.
    - A lookup that defaults where the value could be unknown, or a closed vocabulary held as `str`.
    - An iteration whose order reaches output, run in hash order.
    - A value that crosses a package boundary as a string the other side parses.
- A defect place stands, with its reason, where a package boundary forces the second copy, where a rule requires it, or where an absent value has a known meaning.
    - Each check quotes for itself the handbook passage it rests on, so one passage quoted at several checks stands.
        * comment: Of scan 7's 30 items, 9 stood with reasons, among them one style.md sentence quoted at four checks, which the quote rule requires.
- Places listed for main's judgment:
    - A condition that names one solver, one command or one shape of input.
    - A check whose docstring names no principle.
    - What each check and each survey reads and quotes.
    - Each test, with what it constructs and what it asserts.
