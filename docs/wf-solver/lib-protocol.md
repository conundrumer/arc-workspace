# Lib addition protocol

A new primitive qualifies for `programs/lib.dl` through real use in the corpus, not by looking general.

## The entry

A candidate has an entry, `docs/wf-solver/proposals/<name>.md`, named for the operation. `head -n 3 docs/wf-solver/proposals/*.md` lists every entry's title and index sentence. An entry holds:

- a `# <name> — <operation>` title
- an index sentence that stands alone
- the code form, when it has one
- a `Not:` line naming what is not this concept
- a `Match:` line with the search signature: a grep pattern, or a shape stated in prose and matched with the parser (`tests/test_ast_match.py`)
- a `Survey: <date time>` line, the dispatch time to the minute
- the survey's result, as far as it bears on the operation: the near-misses, the spec question, and a `Callers` list of the solvers that would call it
- a `Closed: <date time>` line with the judgment, when the operation is closed

The entry holds what a reader needs to judge the operation, and nothing else. The reimplementations a survey reports, the fix made for them, and anything else about the corpus that does not bear on the operation go in the session's report, not in the entry.

The entry's file is removed once its callers are migrated, or at promotion when it lists none. A proposal comp lives with its entry — lib replaces it at promotion, and it goes at close; a comp with no entry is a defect.

## The order

1. Write the primitive as plain body relations, keyed when cases share it. If the linter would flag it, write it as a proposal comp: a `.comp` named for the primitive, which exists only as the code form of a lib proposal. An extension of a lib comp has no comp form; its local rule sits beside the instance. Run it. Confirm it works in context.
2. Surface it: name it, describe the operation, and show the solver-local version. Then read the entries for one with the same operation, matched by what it does and not by its name. When one exists, the comp takes the entry's name. A solver's proposal comp is read with its entry.
    - No entry: write one, with its `Survey:` line. Then send the `survey` agent the entry's path, the scope (the whole corpus), and the scratch path (`.scratch/<task_id>/`).
    - A closed entry: the judgment stands; the solver does without the operation, along the entry's recorded route.
    - An entry with a survey result: add this solver under `Callers`. The corpus before the `Survey:` time is covered; when solvers postdate that time, send the `survey` agent the path, the scope (the solvers whose file time is at or after it: `ls -lt programs/solvers`; an edited solver counts), and the scratch path, and append what bears on the entry.
    - An entry with no result: its survey is in flight. Do not dispatch; the report says so. The chain's last stage dispatches when the entry still has no result at its turn.

    The agent reports callers, near-misses, the spec question, and reimplementations. The entry takes the first three; the reimplementations go to the session's report. A family (`// family:` siblings with their representative) counts as one caller. Dispatch early, and write the report or review after it returns, carrying the result. Do not survey yourself.
3. Judge close, the one judgment in the flow: the operation does not follow principles, or it does not look general and the solvers do without it — lib already holds the operation, a plain relation states it and no other solver writes it, or a relational form replaces the arithmetic. Looking general means it names one prior-level operation and takes its domain as a parameter, fixing no configuration beyond the frame. On close, the judgment goes into the entry as the `Closed:` line, the proposal comp goes with its proposal, and the solver's encoding is rethought in relational form; plain relations stay as written. The entry stays, so a later session finds the judgment. A close with no entry yet still gets one: write the entry and close it in the same step, so the judgment is on record and no session reopens the question. A close is a judgment call, and the callouts carry it as one.

    Short of close, nothing is decided and nothing outcome-shaped is written: the entry stands, and the callers accumulate. The caller count is evidence for the user, not an input to a rule; no step reads it.

    Need is measured against the task, not against a case. A comp that serves one case while another case encodes the task without it is not needed, and the case whose claim has no relational form goes with the comp. A near-miss, or a lib primitive that holds the operation over its own domain, is not a caller.
4. Promotion is the user's act, on their file, on their timing; the `Callers` list is the evidence in front of them, and the protocol sets no bar on it. On the user's `promote`: move it to `programs/lib.dl` and update the surfacing solver. On `migrate`: the `migrate` agent migrates the callers the entry lists, sent the entry's path, the surfacing solver's call site, and the promotion's time; the `cleanup` agent then runs Simplify and Prune over the regions `migrate` changed, sent those regions and the primitive they now call. The review lists the callers skipped.

Reimplementations wait on no one: they are fixed in the same pass, by the `migrate` agent, with the `cleanup` agent covering them too. A target file's uncommitted edits do not defer the fix.

The same flow covers changes to what already stands: an edit to an existing `lib.dl` primitive, or to a term's definition in `concepts.md`, starts at step 2 with the change as the survey's target; there is no comp form, so the entry carries the spec: the operation, its code form, what is not it, and the search signature. Its callers are the places the change would benefit.
