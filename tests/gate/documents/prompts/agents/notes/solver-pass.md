# Solver pass notes
- The statements on a solver pass's brief and report that more than one entry point inlines.

## brief-form
- Your brief may give overrides, each labelled as an override: a judgment made in place of the pass's own.
- Refuse any other instruction in your brief on a judgment the pass makes: run no operation, and write the part of the brief you refused, quoted, as your report.

## solver-pass-lead
- What an operation routes to the review goes in your report, under the section it fits.
- Write under `programs/solvers/`, `programs/witnesses/`, `work/task/<task_id>/`, and `issues/new/`, and nowhere else; the Analyze files are not changed.
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
    - <another task's file, and the line>: <the fix it needs>

    ## Issues filed
    - <the name of a file the pass wrote under `issues/new/`>
    ```
- A section with nothing holds `none`.
