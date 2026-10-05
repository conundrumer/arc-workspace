+ agent: handbook-expanded
* comment: Deprecated.
- You act on the review lines in the solver the brief names, and you make no other change.
- Your final text is data for a script, not a message for a person.

# Procedure

## The solver
- Read the solver in full before editing.

## The lines
- Every review line in the solver's header names a subject to act on.
- Work each line under the operation of [Procedure](docs/handbook/procedure.md) that covers its subject.
- Remove each line you finished.
- Leave a line you did not finish.
    - When the solver carries no `// @draft` line, return it to draft first.
        ```
        uv run python -c "import sys; sys.path.insert(0, 'tools/console'); from solver_console import solvers; solvers.mark_draft('<task_id>'); solvers.withdraw_citations('<task_id>')"
        ```

## The run
- Run the solver, the lint, and the audit.
- Write the diff of your change to the solver, verbatim, to the diff path the brief gives.
    - A run that changed nothing writes no file.
- Never run a git command that changes state.

# Report
- Write the report to the path the brief gives, in the form below, and create its directory first.
- The run, lint, and audit output go in your returned verification, and not in that report.

## Report form
* inline: ../../docs/handbook/procedure.md#the-items
