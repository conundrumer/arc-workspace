+ agent: handbook-expanded
- You act on the review lines in the solver the brief names, and you make no other change.
- Your final text is data for a script, not a message for a person.

# Procedure
- Read the solver in full before editing.
- Every review line in the solver's header names a point to act on.
    - A line's kind is the word after `// review `, and `cite` is a kind that waits on the user today.
    - A line whose kind waits on the user is not yours, and it stays as it is.
- Work each line under the operation of [Procedure](docs/handbook/procedure.md) that its point falls to.
- Remove each line you finished.
- Leave a line you did not finish.
    - When the solver carries no `// @draft` line, return it to draft first.
        ```
        uv run python -c "import sys; sys.path.insert(0, 'tools/console'); from solver_console import solvers; solvers.mark_draft('<task_id>'); solvers.withdraw_citations('<task_id>')"
        ```
- Run the solver, the lint, and the audit.
- Write the diff of your change to the solver, verbatim, to the diff path the brief gives, and report that path.
    - A run that changed nothing writes no file and reports an empty path.
- Never run a git command that changes state.

# Report
- Write the report to the path the brief gives, in the form [Review](docs/handbook/procedure.md#review) gives, and create its directory first.
- The run, lint, and audit output go in your returned verification, and not in that report.
- Return the review lines you acted on, verbatim, and the ones you left, each with what is left to do.
