+ lib: index

# Solver session
- The docs and the lib as a solver session reads them, with the passes it runs.
- Read [Editing the agent-facing documents](docs/handbook/editing.md) before editing any of it.

* inline: agents/notes.md#lib-index

* include: handbook.md

## Passes
- **Creation pass.** The first pass, in this order:
    1. [Draft](docs/handbook/procedure.md#draft)
    2. [Develop](docs/handbook/procedure.md#develop)
    3. [Determine](docs/handbook/procedure.md#determine)
    4. [Witness](docs/handbook/procedure.md#witness)
    5. [Simplify](docs/handbook/procedure.md#simplify)
    6. [Prune](docs/handbook/procedure.md#prune)
    7. [Promote](docs/handbook/procedure.md#promote)
        - When the user says `promote` or `migrate` over an entry under `docs/wf-solver/proposals/`.
    8. [Review](docs/handbook/procedure.md#review)
- **Cleanup pass.** When the user says `cleanup`, in this order:
    1. [Simplify](docs/handbook/procedure.md#simplify)
    2. [Prune](docs/handbook/procedure.md#prune)
- **Outside the pass.** Fix a problem in a file the pass does not edit when the docs say how and the fix raises no new issue.
    - Otherwise put it in the review.
- **Delivery.** Write the review as a reply to the user.
    - Finish all task updates first.
    - End the turn with the review.
