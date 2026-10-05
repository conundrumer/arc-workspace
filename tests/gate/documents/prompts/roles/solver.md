+ agent: handbook-expanded
* comment: Deprecated.
- The brief names one solver, `programs/solvers/<task_id>.dl`, and the changes it takes.
- Make those changes, and the changes running the operations below over them requires, and no other.
- Apply each at every site it affects.
- The final text is data for a script, not a message for a person.

# Procedure
- Read the module under `programs/lib/` for the body of every comp the solver instantiates.
- Read the solver in full before editing.
- Keep the file's conventions.
- Put scratch files under `.scratch/<task_id>/` and nowhere else.
- Put the diff file at the path the brief gives.
- Report a failing run as failing.
- Do not attribute it to other work.
- Never run a git command that changes state.
- Run the operations below, in this order.

## Develop
* inline: ../../docs/handbook/procedure.md#develop

## Determine
* inline: ../../docs/handbook/procedure.md#determine

## Witness
* inline: ../../docs/handbook/procedure.md#witness

# Report
- A pass that asks for a report and no review puts the items the operations route to the review in that report.
- State whether you changed the solver.
- When you changed it, give the diff file at the path the brief gives.
- Give the run, lint, and audit output verbatim.
- Give each witness, what it separates, and each case's output on it.
- Give each judgment and what it rests on.
- Nothing in the report waits on a ruling.
- A subject the docs determine is a change you make at every site it affects.
- A subject the pairs leave open is a fact you state.
