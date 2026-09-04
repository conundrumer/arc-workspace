# Lib addition protocol

A new primitive qualifies for `programs/lib.dl` through real use in the corpus. Looking general does not qualify it.

## The entry

A candidate has an entry, `docs/wf-solver/proposals/<name>.md`, named for the operation. `head -n 3 docs/wf-solver/proposals/*.md` lists every entry's title and index sentence. An entry holds:

- a `# <name> — <operation>` title
- an index sentence that stands alone
- the code form, when it has one
- a `Not:` line naming what is not this concept
- a `Match:` line with the search signature: a grep pattern, or a shape stated in prose and matched with the parser (`tests/test_ast_match.py`)
- a `Survey: <date time>` line, the dispatch time to the minute
- the survey's result that is relevant to the operation: the near-misses, the spec question, and a `Callers` list of the solvers that would call it
- a `Closed: <date time>` line with the judgment, when the operation is closed

The entry holds what a reader needs to judge the operation, and nothing else. The reimplementations a survey reports, the fix made for them, and anything else about the corpus that is not relevant to the operation go in the session's report, not in the entry.

After its callers are migrated, remove the entry's file. If the entry lists no callers, remove its file at promotion. Keep a proposal comp with its entry. At promotion, lib replaces that comp. At close, remove that comp. A comp with no entry is a defect.

## The order

1. If an operation's encoding needs a banned form, or if a grep for its shape over `programs/solvers/` finds another solver that writes it, apply this protocol to that operation. Write the primitive as plain body relations. When cases share those relations, key them. If the linter would flag the primitive, write it as a proposal comp: a `.comp` named for the primitive, which exists only as the code form of a lib proposal. An extension of a lib comp has no comp form; its local rule remains beside the instance. Run the solver and confirm that the primitive works in context.
2. Report the operation: name it, describe it, and show the solver-local version. Then read the entries to find one with the same operation. Match by what an operation does, not by its name. When an entry exists, use that entry's name for the comp. Read a solver's proposal comp with its entry.
    - If no entry exists, write one with its `Survey:` line. Then send the `survey` agent the entry's path, the scope (the whole corpus), and the scratch path (`.scratch/<task_id>/`).
    - If an entry is closed, keep its judgment. Encode the solver without the operation, in the way the entry records.
    - If an entry has a survey result, add this solver under `Callers`. The corpus before the `Survey:` time is covered. If some solvers postdate that time, send the `survey` agent the path, the scope (the solvers whose file time is at or after it: `ls -lt programs/solvers`; an edited solver counts), and the scratch path, and append the relevant results to the entry.
    - If an entry has no result, its survey is still running. Do not dispatch another survey. State this in the report. If the entry still has no result when the chain's last stage runs, that stage dispatches the survey.

    The agent reports callers, near-misses, the spec question, and reimplementations. Add the callers, near-misses, and spec question to the entry. Put the reimplementations in the session's report. A family (`// family:` siblings with their representative) counts as one caller. Dispatch early. After the agent returns, include its result in the report or review. Do not survey yourself.
3. Decide whether to close the proposal. This is the only judgment in the protocol. Base that judgment on whether the operation does not follow principles, or whether it does not look general and the solvers encode their tasks without it (lib already holds the operation, a plain relation states it and no other solver writes it, or a relational form replaces the arithmetic). Looking general means it names one prior-level operation and takes its domain as a parameter, fixing no configuration beyond the frame. When closing a proposal, put the judgment in the entry as the `Closed:` line, remove the proposal comp, and rethink the solver's encoding in relational form; plain relations stay as written. Keep the entry so a later session finds the judgment. If the proposal closes before it has an entry, write the entry and close it in the same step. This records the judgment so no session reopens the question. A close is a judgment call; include it as one in the callouts.

    If the proposal does not close, nothing is decided, no text can imply an outcome, the entry stays, and new callers are added to it. The caller count is evidence for the user, not an input to a rule; no step reads it.

    Need is measured against the task, not against a case. A comp that serves one case while another case encodes the task without it is not needed. Remove the case whose claim has no relational form with that comp. A near-miss, or a lib primitive that holds the operation over its own domain, is not a caller.
4. Promotion is an action that the user takes on their file at the time they choose. The `Callers` list gives them the evidence. The protocol sets no caller-count threshold for promotion.
    - On `promote`: move it to `programs/lib.dl` and update the solver that introduced the proposal.
    - On `migrate`:
        1. Send the `migrate` agent the entry's path, the call site in the solver that introduced the proposal, and the promotion's time.
        2. The `migrate` agent migrates the callers that the entry lists.
        3. Send the `cleanup` agent the regions that `migrate` changed and the primitive they now call.
        4. The `cleanup` agent runs Simplify and Prune over those regions.
        5. The review lists the callers that `migrate` skipped.

Nothing defers the fix of a reimplementation. The `migrate` agent fixes reimplementations in the same pass, and the `cleanup` agent also covers them. A target file's uncommitted edits do not defer the fix.

Use the same protocol for changes to existing definitions, such as an edit to an existing `lib.dl` primitive or to a term's definition in `concepts.md`. Start such a change at step 2, with the change as the survey's target. There is no comp form, so the entry contains the spec: the operation, its code form, what is not it, and the search signature. Its callers are the places the change would benefit.
