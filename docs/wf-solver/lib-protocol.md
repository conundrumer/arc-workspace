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
- the survey's result, and a `Callers` list of the solvers that would call it
- a `Recommendation: <verdict>. <date time>` line, which becomes `Verdict: <verdict>. <date time>` on the user's word

The entry's file is removed once its callers are migrated, or at the verdict when it has none. A proposal comp outlives its verdict only when parked: after the verdict, a comp with no entry is a defect.

## The order

1. Write the primitive as plain body relations, keyed when cases share it. If the linter would flag it, write it as a proposal comp: a `.comp` named for the primitive, which exists only as the code form of a lib proposal. An extension of a lib comp has no comp form; its local rule sits beside the instance. Run it. Confirm it works in context.
2. Surface it: name it, describe the operation, and show the solver-local version. Then read the entries for one with the same operation, matched by what it does and not by its name. When one exists, the comp takes the entry's name. A solver's proposal comp is read with its entry.
    - No entry: write one, with its `Survey:` line. Then send the `survey` agent the entry's path, the scope (the whole corpus), and the scratch path (`.scratch/<task_id>/`).
    - An entry with a verdict: the corpus before its `Survey:` time (or the verdict's date, when it has none) is surveyed. Send the `survey` agent the path, the scope (the solvers whose file time is at or after that time: `ls -lt programs/solvers`; an edited solver counts), and the scratch path, and append what it finds.
    - An entry with no verdict and no `Callers` list: its survey is in flight. Do not dispatch; the report says so. The chain's last stage dispatches when the entry still has no result at its turn.
    - An entry with no verdict and a `Callers` list: add this solver under `Callers`.

    The agent reports callers, near-misses, the spec question, and reimplementations. A family (`// family:` siblings with their representative) counts as one caller. Dispatch early, and write the report or review after it returns, carrying the result. Do not survey yourself.
3. Write the recommendation. The survey's result and the `Recommendation` line go into the entry, in place of any earlier `Recommendation` line, and the review carries the recommendation. The verdict is the user's word, like `next` and `commit`; act on none without it.

    The recommendation is a judgment against the principles and style; the survey is its evidence, and the caller bar is more than 4 callers. Beside the bar, the judgment asks whether the operation looks general: it names one prior-level operation and takes its domain as a parameter, fixing no configuration beyond the frame.
    - promote — it follows principles, and the survey clears the bar
    - park — the survey does not clear the bar, and the operation looks general or the surfacing solver's claim has no relational form. The entry stays, with the spec, the callers, and the bar as the gate a later caller must meet. Any proposal comp stays.
    - close — it does not follow principles, or it neither clears the bar nor looks general, and the solvers do without it: lib already holds the operation, a plain relation states it, or a relational form replaces the arithmetic. Plain relations stay as written. A proposal comp goes with its proposal, and the solver's encoding is rethought in relational form. The entry stays.

    Need is measured against the task, not against a case. A comp that serves one case while another case encodes the task without it is not needed, and the case whose claim has no relational form goes with the comp. The evidence is the survey's callers; a near-miss, or a lib primitive that holds the operation over its own domain, argues for no verdict.
4. On `promote`: move it to `programs/lib.dl` and update the surfacing solver. On `migrate`: the `migrate` agent migrates the callers the entry lists, sent the entry's path, the surfacing solver's call site, and the recommendation's time; the `cleanup` agent then runs Simplify and Prune over the regions `migrate` changed, sent those regions and the primitive they now call. The review lists the callers skipped.

Reimplementations need no verdict: they are fixed in the same pass, by the `migrate` agent, with the `cleanup` agent covering them too.

The same gates cover changes to what already stands: an edit to an existing `lib.dl` primitive, or to a term's definition in `concepts.md`, starts at step 2 with the change as the survey's target; there is no entry, so the brief carries the spec: the operation, its code form, what is not it, and the search signature. Its callers are the places the change would benefit.
