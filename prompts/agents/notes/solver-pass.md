+ document-size-budget: 2200
* comment: when editing this doc
    - [Analyze agent](prompts/agents/analyze.md), [Create agent](prompts/agents/create.md) and [Refine agent](prompts/agents/refine.md) inline its sections, each at the start of a solver pass or at its report.
    - Acts, each with its section:
        - Reading a solver pass's brief: [brief-form](#brief-form), inlined by each of the three.
        - Where a pass writes and what it leaves alone: [solver-pass-lead](#solver-pass-lead), inlined by create and refine.
        - Writing a pass's report: [report-form](#report-form), inlined by create and refine.

# Solver pass notes
- The statements on a solver pass's brief and report that more than one entry point inlines.

## brief-form
* inline: launching.md#solver-work

## solver-pass-lead
- Your report is the review that the operations name: what an operation routes to the review goes in your report, under the section it fits.
- Write under `programs/solvers/`, `programs/witnesses/`, `work/task/<task_id>/`, `tickets/new/` and `tickets/deferred/`, and nowhere else, apart from a `work` link to the main worktree's `work/`.
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

    ## Concept faults
    - <task_id> `<claim slug>`: <the form the program bans that the claim needs>

    ## Fixes elsewhere
    - <another task's file, and the line>: <the fix it needs>

    ## Tickets filed
    - <the name of a file the pass wrote under `tickets/new/` or `tickets/deferred/`>
    ```
- A section with nothing holds `none`.
