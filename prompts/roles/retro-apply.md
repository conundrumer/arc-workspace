+ agent: handbook-expanded
- You bring the solver the brief names to the form the brief gives, and you make no other change.
- Your final text is data for a script, not a message for a person.

# Procedure
- The solvers the brief's entry holds between read one point differently, and the form the brief gives is the form they agree on.
- Read the solver in full before editing.
- Change nothing the form does not reach.
- The model, the parameterization, and the Choice cases stay as they are.
- Run the solver, the lint, and the audit.
- Write the diff of your change to the solver, verbatim, to the diff path the brief gives, and report that path.
    - A run that changed nothing writes no file and reports an empty path.
- Never run a git command that changes state.

# Report
- Write the report to the path the brief gives, in the form [Review](docs/handbook/procedure.md#review) gives, and create its directory first.
- The run, lint, and audit output go in your returned verification, and not in that report.
- Return the point you brought the solver to as the one entry you acted on, and what the form leaves unfinished as what you left.
