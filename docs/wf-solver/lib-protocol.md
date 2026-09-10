<!-- When editing this doc:
- Write in the imperative mood.
- Avoid justifications, unless there is necessary reason.
- Avoid contrastive structures, unless the alternative needs to be addressed. -->

# Lib addition protocol

Qualify a new primitive for `programs/lib.dl` by real use in the corpus and by generality.

- **Trigger.** When an encoding in the solver needs a form banned in the program, or when a grep for its shape over `programs/solvers/` finds another solver that writes it, apply this protocol to that encoding.
- **Generality.** An operation is general when it names one prior-level operation and takes its domain as an input, fixing no configuration beyond the frame.
    - An operation should be as abstract as possible. It only involves geometric types if there is no way to abstract away the geometry. It never involves the Color type.

## The entry

Give a candidate an entry, `docs/wf-solver/proposals/<name>.md`, named for the operation. `head -n 3 docs/wf-solver/proposals/*.md` lists every entry's title and index sentence.

**The entry's fields.** An entry holds:

- a `# <name> — <operation>` title
- an index sentence that stands alone
- the code form, when it has one
- a `Not:` line naming what is not this operation
- a `Match:` line with a search signature that covers every statement of the operation, including statements whose atoms sit in different lines or rules, and statements that reach the operation through another primitive. State the shape in prose and match it with the parser (`tests/test_ast_match.py`)
- a `Survey: <date time>` line per dispatch, the dispatch time to the minute, each followed by its own result
    - the result that is relevant to the operation: the near-misses, the spec question, and a `Callers` list of the solvers that would call it
    - a result with no `Survey:` line above it counts as no result
- a `Closed: <date time>` line with the judgment, when the operation is closed

Put in the entry what a reader needs to judge the operation, and nothing else.

### The entry's life

Remove the entry's file at these points:

- after its callers are migrated
- at promotion, when the entry lists no callers

## The order

1. Write the primitive as plain program relations.
    - When cases share those relations, key them.
    - **Proposal comp.** If the linter would flag the primitive, write it as a proposal comp: a `.comp` named for the primitive.
    - **Extension of a lib comp.** Write no comp for an extension of a lib comp. Keep its local rule beside the instance.
    - Run the solver and confirm that the primitive works in context.
2. Report the operation: name it, describe it, and show the solver-local version. Then read the entries to find one with the same operation.
    - **Match by operation.** Match by what an operation does, not by its name.
    - When an entry exists, use that entry's name for the comp.
    - Read a solver's proposal comp with its entry.

    The entry's state decides what to do next.

    - If no entry exists, write one with its `Survey:` line. Then send the `survey` agent the entry's path, the scope (the whole corpus), and the scratch path (`.scratch/<task_id>/`).
    - If an entry is closed, keep its judgment. Encode the solver without the operation, in the way the entry records.
    - If an entry has a survey result, add this solver under `Callers`.
        - **Newer solvers.** If some solvers postdate the entry's `Survey:` time, send the `survey` agent the path, the scope, and the scratch path, and append the relevant results to the entry. The scope is the solvers that `uv run python scripts/run_dl.py since <time>` lists.
    - If an entry has no result and no survey of yours is running, dispatch the survey.

    **Dispatch.** Dispatch early, and do not survey yourself. The agent reports callers, near-misses, the spec question, and reimplementations.

    - Count a family (`// family:` siblings with their representative) as one caller.
    - Add the callers, near-misses, and spec question to the entry.
    - Put the reimplementations in the session's report.
    - Include the agent's result in the report or review.
3. Decide whether to close the proposal. This is the only judgment in the protocol.
    - **Close grounds.** Base that judgment on whether the operation does not follow principles, or whether it is not general and the solvers encode their tasks without it. The solvers encode their tasks without it when:
        - lib already holds the operation
        - a plain relation states it and no other solver writes it
        - a relational form replaces the arithmetic
    - **Closing.** When closing a proposal, put the judgment in the entry as the `Closed:` line, remove the proposal comp, and rethink the solver's encoding in relational form. Leave plain relations as written.
        - An entry closed with no `Survey:` line above its result is reopened: write the line and dispatch the survey.
        - If the proposal closes before it has an entry, write the entry and close it in the same step.
        - Include the close in the review as a judgment call.
    - **No close.** If the proposal does not close, nothing is decided. Write no text that implies an outcome.
    - **Need.** Measure need against the task, not against a case.
        - A comp that serves one case while another case encodes the task without it is not needed.
        - Remove the case whose hypothesis has no relational form without that comp.
    - **Not a caller.** Do not count a near-miss, or a lib primitive that holds the operation over its own domain, as a caller.
4. Leave promotion to the user, at the time they choose. The `Callers` list is their evidence. No step reads its count.
    - On `promote`: move the primitive to `programs/lib.dl` and update the solver that introduced the proposal.
    - On `migrate`:
        1. Send the `migrate` agent the entry's path, the call site in the solver that introduced the proposal, and the promotion's time.
        2. Send the `cleanup` agent the regions that `migrate` changed and the primitive they now call.
        3. List in the review the callers that `migrate` skipped.

**Reimplementations.** Fix every reimplementation a survey reports in the same pass.

- Send them to the `migrate` agent, then the `cleanup` agent.
- If either agent finds another problem that Simplify or Prune covers in a file it has open, that agent fixes that problem in the same pass.
- Put a finding in a file no agent has open in the review.
- Fix a target file even when it has uncommitted edits.

## Changes to existing definitions

Use the same protocol for changes to existing definitions, such as an edit to an existing `lib.dl` primitive.

- Start such a change at step 2, with the change as the survey's target.
- The change has no comp form. Write the whole spec in the entry's fields.
- Count as its callers the places the change would benefit.
