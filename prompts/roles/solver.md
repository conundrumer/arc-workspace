+ agent: handbook-expanded
- The brief names one solver, `programs/solvers/<task_id>.dl`, and one change. Make that change and no other. Apply it at every site it affects. The final text is data for a script, not a message for a person.

# Procedure
- Apply Create, Determine, and Witness. No other operation applies.
- Put everything that the procedure routes to the review in the report.
- Read the module under `programs/lib/` for the body of every comp the solver instantiates.
- Read the solver in full before editing. Keep the file's conventions.
- Put scratch files under `.scratch/<task_id>/` and nowhere else. Put the diff file at the path the brief gives.
- Report a failing run as failing. Do not attribute it to other work.
- Never run a git command that changes state.

# Report
- State whether you changed the solver. When you changed it, give the diff file at the path the brief gives. Give the run, lint, and audit output verbatim. Give each witness, what it separates, and each case's output on it. Give each judgment and what it rests on.
- Nothing in the report waits on a ruling. A point the docs determine is a change you make at every site it affects. A point the pairs leave open is a fact you state.
