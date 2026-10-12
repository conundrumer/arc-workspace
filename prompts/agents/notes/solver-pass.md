+ budget: 1500

# Solver pass notes
- The statements on a solver pass's brief and report that more than one entry point inlines.

## brief-form
* inline: launching.md#solver-work

## solver-pass-lead
- What an operation routes to the review goes in your report, under the section it fits.
- Write under `programs/solvers/`, `programs/witnesses/`, `work/task/<task_id>/`, and `tickets/open/`, and nowhere else, apart from a `work` link to the main worktree's `work/`.
- Change no Analyze file.
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

    ## Tickets filed
    - <the name of a file the pass wrote under `tickets/open/`>
    ```
- A section with nothing holds `none`.
